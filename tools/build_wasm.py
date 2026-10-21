#!/usr/bin/env python3
"""Build the browser PRG32 core (static/wasm/) from a PRG32-QT checkout.

    python3 tools/build_wasm.py [--prg32qt ../PRG32-QT] [--prg32 ../PRG32] [--check]

Needs Emscripten (emcc, emcmake) and CMake. The core's C++ sources are
compiled straight from PRG32-QT's src/core (with the kit's host-call hook added to a
copy, see wasm/CMakeLists.txt), and its sound from the PRG32 firmware's audio engine
(components/prg32_audio of a PRG32 checkout, ADR-0021): the kit adds only the C
interface in wasm/prg32_core_api.cpp and the audio port in wasm/audio/. The result is written to

    static/wasm/prg32-core.js     JavaScript loader (createPrg32Core)
    static/wasm/prg32-core.wasm   the core: RV32IMAC interpreter + PRG32 ABI 1.6
    static/wasm/BUILD.json        what it was built from, with SHA-256 fingerprints

With --check nothing is copied: the script only says whether static/wasm
matches what a build from that checkout would produce.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit.provenance import git_revision

OUTPUT = ROOT / "static" / "wasm"
FILES = ("prg32-core.js", "prg32-core.wasm")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emscripten_version() -> str:
    output = subprocess.run(["emcc", "--version"], capture_output=True, text=True, check=True).stdout
    return output.splitlines()[0].strip()


def build(prg32qt: Path, prg32: Path, build_dir: Path) -> Path:
    subprocess.run(["emcmake", "cmake", "-S", str(ROOT / "wasm"), "-B", str(build_dir), "-G", "Ninja",
                    f"-DPRG32QT_DIR={prg32qt}", f"-DPRG32_DIR={prg32}", "-DCMAKE_BUILD_TYPE=Release"], check=True,
                   stdout=subprocess.DEVNULL)
    subprocess.run(["cmake", "--build", str(build_dir)], check=True)
    return build_dir


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--prg32qt", type=Path, default=ROOT.parent / "PRG32-QT", help="PRG32-QT checkout")
    parser.add_argument("--prg32", type=Path, default=ROOT.parent / "PRG32", help="PRG32 SDK checkout (audio engine)")
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build" / "wasm")
    parser.add_argument("--check", action="store_true", help="compare with static/wasm instead of copying")
    args = parser.parse_args()
    prg32qt = args.prg32qt.resolve()
    if not (prg32qt / "src" / "core" / "Runtime.cpp").is_file():
        print(f"Not a PRG32-QT checkout: {args.prg32qt}", file=sys.stderr)
        return 2
    prg32 = args.prg32.resolve()
    if not (prg32 / "components" / "prg32_audio" / "audio_synth.c").is_file():
        print(f"Not a PRG32 SDK checkout: {args.prg32}", file=sys.stderr)
        return 2
    for tool in ("emcc", "emcmake", "cmake", "ninja"):
        if shutil.which(tool) is None:
            print(f"{tool} is not installed (see docs/wasm_runtime.md)", file=sys.stderr)
            return 2
    built = build(prg32qt, prg32, args.build_dir.resolve())
    record = {
        "schema": "prg32-kit-wasm-build-1",
        "core": {"repository": "https://github.com/riscv-prg32/PRG32-QT",
                 "revision": git_revision(prg32qt),
                 "version": (prg32qt / "VERSION.txt").read_text(encoding="utf-8").strip()
                 if (prg32qt / "VERSION.txt").is_file() else None,
                 "license": "MIT"},
        "audio": {"repository": "https://github.com/riscv-prg32/PRG32",
                  "revision": git_revision(prg32),
                  "sources": "components/prg32_audio (audio.c, audio_assets.c, audio_mixer.c, audio_synth.c, "
                             "audio_tracker.c)",
                  "license": "MIT"},
        "abi": {"major": 1, "minor": 6, "hash": "0x260f6136"},
        "emscripten": emscripten_version(),
        "files": {name: {"sha256": sha256(built / name), "bytes": (built / name).stat().st_size} for name in FILES},
    }
    if args.check:
        current = json.loads((OUTPUT / "BUILD.json").read_text(encoding="utf-8"))
        same = current["files"] == record["files"]
        print("static/wasm is up to date" if same else "static/wasm differs from a fresh build")
        return 0 if same else 1
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        shutil.copyfile(built / name, OUTPUT / name)
    (OUTPUT / "BUILD.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {', '.join(FILES)} and BUILD.json to static/wasm/ (PRG32-QT {record['core']['revision']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
