"""Handwritten RISC-V assembly projects (docs/adr/0004-handwritten-assembly-mode.md)."""
from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest
from test_source_languages import built_source, fake_builder

from prg32_construction_kit.asm_generator import ir_to_asm
from prg32_construction_kit.generator import blocks_to_c
from prg32_construction_kit.source_project import validate_asm_source

ROOT = Path(__file__).resolve().parent.parent

GAME = """/* A tiny handwritten cartridge. */
    .option norelax
    .section .data
    .balign 4
counter: .word 0            # frames seen so far
    .section .text
    .globl my_asm_init
    .globl my_asm_update
    .globl my_asm_draw
my_asm_init:
    ret
my_asm_update:
    la   t0, counter        # t0 = &counter
    lw   t1, 0(t0); addi t1, t1, 1; sw t1, 0(t0)
    ret
my_asm_draw:
    ret
"""


def asm_project(client, source=GAME, title="My Asm", features=None):
    game = {"source_mode": "asm", "source_asm": source, "required_features": features or []}
    return client.post("/api/projects", json={"title": title, "game_json": game}).get_json()


def test_valid_assembly_is_accepted():
    assert validate_asm_source(GAME, "My Asm") == "my_asm"


@pytest.mark.parametrize("path", sorted((ROOT / "examples" / "games").glob("*.json")))
def test_kit_generated_assembly_passes_the_same_check(path):
    project = json.loads(path.read_text())["project"]
    game_ir, _ = blocks_to_c(project["blocks_json"], project)
    assert validate_asm_source(ir_to_asm(game_ir), project["title"]) == game_ir["entry_prefix"]


@pytest.mark.parametrize("line", [
    '#include "/etc/passwd"',
    '%:include "/etc/passwd"',
    '#\\\ninclude "/etc/passwd"',
    '/**/ #include "x.h"',
    '#import "x.h"',
    '#embed "/etc/passwd"',
    '#pragma GCC poison x',
    '#define F(a) a',
    '#define D .incbin',
    '#define CAT a##b',
    '    .incbin "/etc/passwd"',
    '    .INCBIN "/etc/passwd"',
    '    .include "other.S"',
    '    .macro boom',
    '    .irp r, a0, a1',
    '    .fill 4, 1, 0',
    '    .section .init_array',
    '    .section .text.x; .incbin "/etc/passwd"',
    '    nop; .print "hi"',
    'label: .rept 3',
    '??=include "x"',
])
def test_file_reading_and_unknown_directives_are_rejected(line):
    with pytest.raises(ValueError):
        validate_asm_source(line + "\n" + GAME, "My Asm")


def test_strings_and_comments_may_mention_anything():
    source = GAME + '    .section .rodata\nmsg: .asciz "#include .incbin"   # not .incbin\n/* .include */\n'
    assert validate_asm_source(source, "My Asm") == "my_asm"


def test_file_words_are_refused_anywhere_in_code():
    # A macro could turn any word into a directive, so these words are refused even as names.
    with pytest.raises(ValueError, match="incbin"):
        validate_asm_source(GAME + "    .equ incbinx, 1\n", "My Asm")


def test_textbook_comment_lines_are_allowed():
    source = "# --- PADDLE INPUT ---\n     # 256 = 320 - 64\n#define SPEED 3\n#ifdef SPEED\n#endif\n" + GAME
    assert validate_asm_source(source, "My Asm") == "my_asm"


@pytest.mark.parametrize("change, message", [
    (("my_asm_draw:\n", "other_draw:\n"), "define the label my_asm_draw"),
    (("    .globl my_asm_update\n", ""), "visible with .globl my_asm_update"),
])
def test_entry_points_must_exist_and_be_global(change, message):
    with pytest.raises(ValueError, match=message):
        validate_asm_source(GAME.replace(*change), "My Asm")


def test_size_and_empty_limits():
    with pytest.raises(ValueError, match="empty"):
        validate_asm_source("  \n", "My Asm")
    with pytest.raises(ValueError, match="never ends"):
        validate_asm_source(GAME + "/* never closed\n", "My Asm")
    with pytest.raises(ValueError, match="256 KiB"):
        validate_asm_source(GAME + "/*" + "x" * 300_000 + "*/", "My Asm")


def test_convert_returns_the_handwritten_assembly(client):
    project = asm_project(client)
    data = client.post(f"/api/projects/{project['id']}/convert", json={}).get_json()
    assert data["source_language"] == "asm"
    assert data["asm_source"] == GAME and "c_source" not in data
    assert data["artifact"]["kind"] == "asm_source"
    response = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "c"})
    assert response.status_code == 400
    assert "builds the assembly you wrote" in response.get_json()["error"]


def test_bad_assembly_is_refused_before_building(client, monkeypatch):
    commands = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    project = asm_project(client, GAME + '    .incbin "/etc/passwd"\n')
    response = client.post(f"/api/projects/{project['id']}/package", json={})
    assert response.status_code == 400 and "incbin" in response.get_json()["error"]
    assert commands == []


def test_package_builds_the_handwritten_assembly(client, monkeypatch):
    commands = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    project = asm_project(client, features=["sprites"])
    result = client.post(f"/api/projects/{project['id']}/package",
                         json={"expected_source_asm": GAME}).get_json()
    assert result["build"]["metadata"]["built_from"] == "asm"
    assert {built_source(command) for command in commands} == {"game.S"}
    assert all(command[command.index("--required-feature") + 1] == "sprites" for command in commands)
    with zipfile.ZipFile(io.BytesIO(client.get(
            f"/api/artifacts/{result['bundle_artifact']['id']}/download").data)) as bundle:
        assert bundle.read("source/game.S").decode() == GAME


def test_package_notices_assembly_saved_elsewhere(client):
    project = asm_project(client)
    response = client.post(f"/api/projects/{project['id']}/package", json={"expected_source_asm": "older"})
    assert response.status_code == 409


def test_assembly_archive_round_trip(client):
    project = asm_project(client, features=["audio"])
    data = client.get(f"/api/projects/{project['id']}/archive").data
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        manifest = json.loads(archive.read("prg32.project.json"))
        assert archive.read("src/game.S").decode() == GAME
    assert manifest["authoring_mode"] == "assembly" and manifest["source"] == "src/game.S"
    assert manifest["build_profiles"]["default"]["source_language"] == "asm"
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(data), "a.zip")},
                           content_type="multipart/form-data").get_json()
    assert imported["game_json"] == {"source_mode": "asm", "source_asm": GAME, "required_features": ["audio"]}


def _real_toolchain_missing(command: str) -> bool:
    from prg32_construction_kit.build_check import check_command

    return not all(ok for ok, _ in check_command(command))


def test_handwritten_assembly_builds_a_real_cartridge(app, client):
    """Uses the real PRG32 toolchain when it is installed (skipped otherwise)."""
    if _real_toolchain_missing(app.config["PRG32_BUILD_COMMAND"]):
        pytest.skip("PRG32 build toolchain is not installed")
    project = asm_project(client)
    result = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
    assert result["build"]["status"] == "ready", result["build"]["log"]
    cartridge = client.get(f"/api/artifacts/{result['cartridge_artifacts'][0]['id']}/download").data
    assert cartridge[:4] == b"PRG2"
