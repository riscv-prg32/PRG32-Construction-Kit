# Reproducing the toolchain checks

Some checks need the PRG32 RISC-V toolchain:

- building real PRG32 cartridges;
- rebuilding the committed audio and debugger fixtures and the console audio check;
- the tests that compile.

Without the toolchain installed, Docker is enough:

```bash
python3 tools/reproduce_toolchain_checks.py --out toolchain-evidence
```

It builds the kit's own image from this checkout, with the PRG32 SDK at the revision the
fixtures were made with (`static/wasm/BUILD.json`, `audio.revision`), so the rebuilds
compare byte for byte. Inside the image, with the production container's security
settings, it runs:

| Step | What it proves |
|---|---|
| `check_build` | a class compiling at once, isolated by bubblewrap; one game written each way (Blocks as C and as assembly, Advanced C, handwritten assembly), for both targets, with their SHA-256 (`check_build.json`) |
| `audio_fixtures`, `debug_fixtures`, `hardware_audio_check` | the committed fixtures and the console audio check are exactly what the toolchain makes |
| `toolchain_tests` | the build sandbox, provenance, handwritten assembly, source debugging, concurrency and console-check tests, with the real toolchain (junit in `toolchain-tests.xml`) |

`summary.json` records the kit commit (and whether the tree had changes), the SDK
revision, the compiler and each step's outcome. The exit code is 0 only when every step
passed. The image stays local and is removed afterwards (`--keep-image` keeps it).
Tests that also need Node.js are skipped inside the image; the local suite and CI run them.

The run from 2026-10-21 (kit `b547d82`) is in `docs/evidence/toolchain/2026-10-21/`. All
steps passed, and the toolchain tests gave 112 passed and 19 skipped (Node.js). The
cartridges it built have the same SHA-256 as the ones built on macOS and delivered to
PRG32-QT (`docs/evidence/delivery/2026-10-21-prg32qt/`).
