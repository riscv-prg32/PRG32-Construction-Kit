"""Build the source-debugger test fixtures (ADR-0015) with the real PRG32 toolchain.

    python3 tools/build_debug_fixtures.py           # write tests/fixtures/debug/*.prg32 and *.map.json
    python3 tools/build_debug_fixtures.py --check   # fail if the committed files differ
    python3 tools/build_debug_fixtures.py --check-if-comparable --out DIR
        # CI: check only when this machine has the SDK and compiler of BUILD.json
        # (otherwise say so and succeed); keep what was built in DIR as evidence

Each fixture (tests/fixtures/debug/compressed.S, locals.c, and the Pong example's
Blocks program, with its block map as pong.source_map.json) is built exactly as the kit
builds a student's game: the PRG32 builder (python -m prg32 cartridge build --portable,
architecture qemu) through debug_build's tool wrappers. The cartridge and its debug map
are committed, so the debugger tests run without a RISC-V toolchain; with one, --check
proves they are what the toolchain makes. Each debug ELF is also kept in
tests/fixtures/debug/fuzz/ as the starting point of tests/test_debug_fuzz.py (a test
input only: the kit never serves a debug ELF). The toolchain writes the build folder's
path into the assembler stub's debug information, so those paths are overwritten with
same-length filler, and the seeds are not compared by --check (they differ by machine).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit import debug_build, debug_info  # noqa: E402
from prg32_construction_kit.build_check import toolchain_present  # noqa: E402
from prg32_construction_kit.config import Config  # noqa: E402
from prg32_construction_kit.packager import run_prg32_build  # noqa: E402
from prg32_construction_kit.source_maps import build_source_map  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "debug"
# fixture source -> entry prefix
SOURCES = {"compressed.S": "cfix", "locals.c": "dbg"}
# Blocks fixtures: name -> example project (its generated C is built, with a block map)
BLOCKS = {"pong": ROOT / "examples" / "games" / "pong.json"}
ARCHITECTURE = "qemu"
RECORD = FIXTURES / "BUILD.json"


def inputs() -> dict[str, str]:
    """What the fixtures depend on besides their sources: the PRG32 SDK and the compiler."""
    import subprocess

    def first_line(command: list[str]) -> str:
        try:
            lines = subprocess.run(command, capture_output=True, text=True, check=False).stdout.splitlines()
        except OSError:  # git or the compiler is not installed here
            return "unknown"
        return lines[0].strip() if lines else "unknown"

    # Read from the SDK's .git files (or PRG32_SDK_REVISION), as build provenance does: the
    # toolchain image keeps the SDK's .git but not the git program.
    from prg32_construction_kit.provenance import sdk_identity

    revision = sdk_identity()["revision"]
    return {"prg32_sdk": revision[:7] if revision else "unknown",
            "compiler": first_line(["riscv32-esp-elf-gcc", "--version"])}


def scrubbed(elf: bytes, work: Path) -> bytes:
    """The ELF with host paths (build folder, toolchain and SDK folders) replaced by 'x's of the
    same length, so offsets stay valid and no machine's folders end up in the repository."""
    elf = re.sub(rb"prg32-cart-[A-Za-z0-9_]{8}", lambda match: b"prg32-cart-" + b"x" * 8, elf)
    # Every absolute folder in a NUL-terminated string, up to its last '/': the file name stays.
    return re.sub(rb"/(?:Users|home|private|var|tmp|opt|root|usr|builds?|work|github)/[^\x00]*/",
                  lambda match: b"x" * len(match.group(0)), elf)


def build(source: Path, prefix: str, build_command: str, work: Path) -> tuple[bytes, str, bytes]:
    work.mkdir(parents=True)
    copy = work / ("game" + source.suffix)
    shutil.copyfile(source, copy)
    tools = debug_build.prepare(work, "riscv32-esp-elf-", build_command)
    if tools is None:
        raise SystemExit("debug builds need the PRG32 builder and riscv32-esp-elf-gcc on PATH")
    out = work / f"{source.stem}.prg32"
    ok, log = run_prg32_build(build_command, copy, out, prefix, source.stem, ARCHITECTURE, 64, [], 120, None,
                              ["--tool-prefix", tools.prefix])
    if not ok:
        raise SystemExit(f"{source.name} did not build:\n{log}")
    elf = debug_build.collect(tools, ARCHITECTURE, out)
    if elf is None:
        raise SystemExit(f"{source.name}: the debug ELF does not match the cartridge")
    return (out.read_bytes(), json.dumps(debug_info.build_debug_map(elf), indent=1, sort_keys=True) + "\n",
            scrubbed(elf.read_bytes(), work))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-if-comparable", action="store_true",
                        help="like --check, but only when the SDK and compiler match BUILD.json")
    parser.add_argument("--out", type=Path, help="also write what was built here (CI evidence)")
    args = parser.parse_args()
    if args.check_if_comparable:
        recorded = json.loads(RECORD.read_text()) if RECORD.is_file() else {}
        if toolchain_present(Config.PRG32_BUILD_COMMAND) and inputs() != recorded:
            print(f"not comparable: the fixtures were built with {recorded}; this machine has {inputs()}")
            args.check = False
            args.out = args.out or None
            if args.out is None:
                return 0
        else:
            args.check = True
    build_command = Config.PRG32_BUILD_COMMAND
    if not toolchain_present(build_command):
        print("the PRG32 toolchain is not installed", file=sys.stderr)
        return 2
    stale = []
    with tempfile.TemporaryDirectory() as tmp:
        jobs = [(FIXTURES / name, prefix, {}) for name, prefix in SOURCES.items()]
        for stem, example in BLOCKS.items():
            data = json.loads(example.read_text(encoding="utf-8"))
            project = data.get("project", data)
            game_ir, c_source, source_map = build_source_map(project["blocks_json"], project, "c")
            generated = Path(tmp) / f"{stem}.c"
            generated.write_text(c_source, encoding="utf-8")
            jobs.append((generated, game_ir["entry_prefix"],
                         {FIXTURES / f"{stem}.source_map.json": json.dumps(source_map, indent=1, sort_keys=True) + "\n"}))
        for source, prefix, extra in jobs:
            cartridge, debug_map, elf = build(source, prefix, build_command, Path(tmp) / ("build-" + source.stem))
            targets = {FIXTURES / f"{source.stem}.prg32": cartridge, FIXTURES / f"{source.stem}.map.json": debug_map,
                       FIXTURES / "fuzz" / f"{source.stem}.elf": elf, **extra}
            for path, content in targets.items():
                data = content if isinstance(content, bytes) else content.encode("utf-8")
                if args.out:
                    args.out.mkdir(parents=True, exist_ok=True)
                    (args.out / path.name).write_bytes(data)
                if args.check_if_comparable and not args.check:
                    continue      # built for the evidence only: not the committed inputs
                if args.check and path.suffix == ".elf":
                    continue      # fuzz seeds: machine-dependent, see the docstring
                if args.check:
                    if not path.is_file() or path.read_bytes() != data:
                        stale.append(path.name)
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
                    print(f"Wrote {path.relative_to(ROOT)}")
    record = json.dumps(inputs(), indent=1, sort_keys=True) + "\n"
    if args.out:
        (args.out / RECORD.name).write_text(record)
    if args.check_if_comparable and not args.check:
        print("built for the record only (inputs differ from BUILD.json); nothing compared")
        return 0
    if args.check:
        if not RECORD.is_file() or RECORD.read_text() != record:
            stale.append(RECORD.name)
    else:
        RECORD.write_text(record)
        print(f"Wrote {RECORD.relative_to(ROOT)}")
    if stale:
        print("out of date: " + ", ".join(stale) + " (run python3 tools/build_debug_fixtures.py)", file=sys.stderr)
        return 1
    if args.check:
        print("debug fixtures are up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
