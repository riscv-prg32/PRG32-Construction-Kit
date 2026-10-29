"""Fuzzing the debug-information readers (ADR-0015): damaged input stays harmless.

Seeds: real debug ELFs from the PRG32 toolchain (tests/fixtures/debug/fuzz/, made by
tools/build_debug_fixtures.py) and the example Blocks games. Mutations are
deterministic (fixed random seeds), so a failure always reproduces.

For every mutant, build_debug_map / build_source_map must:
- never raise (debug maps) or raise only the errors the build already catches (source maps);
- finish quickly and give a bounded answer;
- open no file but the one it was given;
- put no folder into a map: only file names (no '/' or '\\').
"""

from __future__ import annotations

import builtins
import io
import json
import random
import struct
import threading
import time
from pathlib import Path

import pytest

from prg32_construction_kit import debug_info
from prg32_construction_kit.source_maps import build_source_map

ROOT = Path(__file__).resolve().parent.parent
SEEDS = sorted((ROOT / "tests" / "fixtures" / "debug" / "fuzz").glob("*.elf"))
MUTANTS_PER_SEED = 120
SECONDS_PER_INPUT = 5.0
MAX_MAP_BYTES = 8 * 1024 * 1024
HOSTILE_NAMES = [b"/etc/passwd", b"../../../../etc/shadow", b"C:\\Windows\\win.ini", b"/proc/self/environ",
                 b"/data/construction_kit.sqlite"]


def debug_sections(data: bytes) -> list[tuple[int, int]]:
    """(file offset, size) of the .debug_* sections, where most mutations go."""
    from elftools.elf.elffile import ELFFile

    elf = ELFFile(io.BytesIO(data))
    return [(section["sh_offset"], section["sh_size"]) for section in elf.iter_sections()
            if section.name.startswith(".debug") and section["sh_size"]]


def mutants(seed: bytes, rng: random.Random):
    sections = debug_sections(seed)
    for number in range(MUTANTS_PER_SEED):
        data = bytearray(seed)
        kind = number % 5
        if kind == 0:     # flip bytes inside the debug information
            offset, size = rng.choice(sections)
            for _ in range(rng.randint(1, 16)):
                data[offset + rng.randrange(size)] = rng.randrange(256)
        elif kind == 1:   # truncate
            data = data[:rng.randrange(64, len(data))]
        elif kind == 2:   # huge counts and lengths in the debug information
            offset, size = rng.choice(sections)
            spot = offset + rng.randrange(max(1, size - 4))
            data[spot:spot + 4] = struct.pack("<I", rng.choice([0xFFFFFFFF, 0x7FFFFFFF, 0x10000000, 0xFFFFFFF0]))
        elif kind == 3:   # a hostile file name written over a string, same length kept
            name = rng.choice(HOSTILE_NAMES)
            offset, size = rng.choice(sections)
            spot = offset + rng.randrange(max(1, size - len(name)))
            data[spot:spot + len(name)] = name
        else:             # flip anywhere (headers included)
            for _ in range(rng.randint(1, 8)):
                data[rng.randrange(len(data))] = rng.randrange(256)
        yield bytes(data)


def no_folders(value) -> None:
    """Every file name in a map is a bare name."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in ("files", "file"):
                for name in (item if isinstance(item, list) else [item]):
                    assert "/" not in str(name) and "\\" not in str(name), name
            no_folders(item)
    elif isinstance(value, list):
        for item in value:
            no_folders(item)


@pytest.fixture()
def opened(monkeypatch):
    """Every path the test's own thread opens through open() while a reader runs.

    Background threads left by other tests (the mail queue's slot locks) are not the reader's."""
    seen: list[str] = []
    real_open = builtins.open
    reader = threading.get_ident()

    def watching_open(file, *args, **kwargs):
        if threading.get_ident() == reader:
            seen.append(str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", watching_open)
    return seen


@pytest.mark.skipif(not SEEDS, reason="no fuzz seeds (run tools/build_debug_fixtures.py with the toolchain)")
@pytest.mark.parametrize("seed_path", SEEDS, ids=lambda path: path.stem)
def test_damaged_debug_elfs_are_harmless(seed_path, tmp_path, opened):
    rng = random.Random(f"prg32-{seed_path.stem}")
    assert debug_info.build_debug_map(seed_path)["status"] == "ok"
    statuses = {"ok": 0, "unavailable": 0}
    target = tmp_path / "mutant.elf"
    for data in mutants(seed_path.read_bytes(), rng):
        target.write_bytes(data)
        opened.clear()
        started = time.monotonic()
        answer = debug_info.build_debug_map(target)         # must not raise
        assert time.monotonic() - started < SECONDS_PER_INPUT
        statuses[answer["status"]] += 1
        assert answer["schema"] == debug_info.SCHEMA
        text = json.dumps(answer)
        assert len(text) < MAX_MAP_BYTES
        no_folders(answer)
        for name in HOSTILE_NAMES:
            assert name.decode() not in text
        assert all(Path(path) == target for path in opened), opened
    assert statuses["unavailable"] > 0          # the mutations did reach the reader


@pytest.mark.skipif(not SEEDS, reason="no fuzz seeds")
def test_a_crafted_load_address_cannot_make_the_server_allocate_gigabytes(tmp_path):
    from elftools.elf.elffile import ELFFile

    data = bytearray(SEEDS[0].read_bytes())
    elf = ELFFile(io.BytesIO(bytes(data)))
    header = elf.header
    for index, section in enumerate(elf.iter_sections()):
        if section["sh_flags"] & 0x2 and section["sh_type"] != "SHT_NOBITS" and section["sh_size"]:
            entry = header["e_shoff"] + index * header["e_shentsize"]
            struct.pack_into("<I", data, entry + 12, 0xF0000000)     # sh_addr of a 32-bit ELF
            break
    target = tmp_path / "far.elf"
    target.write_bytes(bytes(data))
    started = time.monotonic()
    answer = debug_info.build_debug_map(target)
    assert answer["status"] == "unavailable" and "1 MiB" in answer["reason"]
    assert time.monotonic() - started < SECONDS_PER_INPUT


# --- source maps from a student's Blocks JSON ------------------------------------------

def example_projects() -> list[dict]:
    projects = []
    for path in sorted((ROOT / "examples" / "games").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        projects.append(data.get("project", data))
    return projects


def walk_blocks(value):
    if isinstance(value, dict):
        if "type" in value and "id" in value:
            yield value
        for item in value.values():
            yield from walk_blocks(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_blocks(item)


HOSTILE_IDS = ["\n\x00prg32-map-end x", "\x00prg32-map-begin y", "a\nb", "../../etc/passwd", "*/ int evil; /*",
               "x" * 100_000, "", "\u202e", "\\\"'"]


def test_hostile_block_ids_never_change_the_code_or_escape_the_map():
    rng = random.Random("prg32-source-maps")
    checked = 0
    for project in example_projects():
        for language in ("c", "asm"):
            _ir, clean, _map = build_source_map(project["blocks_json"], project, language)
            for _ in range(6):
                blocks = json.loads(json.dumps(project["blocks_json"]))
                for block in walk_blocks(blocks):
                    if rng.random() < 0.3:
                        block["id"] = rng.choice(HOSTILE_IDS)
                started = time.monotonic()
                try:
                    _ir, text, source_map = build_source_map(blocks, project, language)
                except (ValueError, RuntimeError, IndexError):
                    continue          # the build catches these and keeps source/address debugging
                assert time.monotonic() - started < SECONDS_PER_INPUT
                assert text == clean  # ids are never part of the code students and the compiler see
                lines = text.count("\n") + 1
                assert all(1 <= entry["lines"][0] <= entry["lines"][1] <= lines for entry in source_map["entries"])
                assert source_map["file"] in ("game.c", "game.S")
                checked += 1
    assert checked > 0


def test_huge_and_duplicated_blocks_stay_bounded():
    project = example_projects()[0]
    blocks = json.loads(json.dumps(project["blocks_json"]))
    tops = blocks["blocks"]["blocks"]
    blocks["blocks"]["blocks"] = tops * 50            # the same blocks, ids repeated, many times
    started = time.monotonic()
    try:
        _ir, text, source_map = build_source_map(blocks, project, "c")
        assert len(json.dumps(source_map)) < MAX_MAP_BYTES
    except (ValueError, RuntimeError, IndexError):
        pass
    assert time.monotonic() - started < 4 * SECONDS_PER_INPUT
