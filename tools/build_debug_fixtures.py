"""Build the source-debugger test fixtures (ADR-0015) with the real PRG32 toolchain.

    python3 tools/build_debug_fixtures.py           # write tests/fixtures/debug/*.prg32 and *.map.json
    python3 tools/build_debug_fixtures.py --check   # fail if the committed files differ

Each fixture (tests/fixtures/debug/compressed.S, locals.c, and the Pong example's
Blocks program, with its block map as pong.source_map.json) is built exactly as the kit
builds a student's game: the PRG32 builder (python -m prg32 cartridge build --portable,
architecture qemu) through debug_build's tool wrappers. The cartridge and its debug map
are committed, so the debugger tests run without a RISC-V toolchain; with one, --check
proves they are what the toolchain makes.
"""

from __future__ import annotations

import argparse
import json
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

    import prg32

    def first_line(command: list[str]) -> str:
        try:
            lines = subprocess.run(command, capture_output=True, text=True, check=False).stdout.splitlines()
        except OSError:  # git or the compiler is not installed here
            return "unknown"
        return lines[0].strip() if lines else "unknown"

    sdk = Path(prg32.__file__).resolve().parent.parent
    return {"prg32_sdk": first_line(["git", "-C", str(sdk), "rev-parse", "--short=7", "HEAD"]),
            "compiler": first_line(["riscv32-esp-elf-gcc", "--version"])}


def build(source: Path, prefix: str, build_command: str, work: Path) -> tuple[bytes, str]:
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
    return out.read_bytes(), json.dumps(debug_info.build_debug_map(elf), indent=1, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
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
            cartridge, debug_map = build(source, prefix, build_command, Path(tmp) / ("build-" + source.stem))
            targets = {FIXTURES / f"{source.stem}.prg32": cartridge, FIXTURES / f"{source.stem}.map.json": debug_map,
                       **extra}
            for path, content in targets.items():
                data = content if isinstance(content, bytes) else content.encode("utf-8")
                if args.check:
                    if not path.is_file() or path.read_bytes() != data:
                        stale.append(path.name)
                else:
                    path.write_bytes(data)
                    print(f"Wrote {path.relative_to(ROOT)}")
    record = json.dumps(inputs(), indent=1, sort_keys=True) + "\n"
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
