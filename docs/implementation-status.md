# Implementation status

Status of the full-IDE plan (`implementation-plan.md`). A gate is marked
**complete** only when its acceptance tests pass. Updated 2026-10-18.

| Gate | State | Summary |
| --- | --- | --- |
| G0 Discovery | **Complete** | `architecture/current-state.md`, ADR-0001…0007, baseline tests recorded. |
| G1 Foundation | **In progress** | Manifest, migrations, archive, duplicate done; revisions, soft delete, guest policy open. |
| G2 IDE shell | Not started | |
| G3 Toolchain | Not started | Server builds already produce real `.prg32` (pre-existing). |
| G4 WASM runtime | Not started | Needs Emscripten (not installed on the dev machine). |
| G5 Debugger | Not started | |
| G6 Identity/storage | Not started | |
| G7 Delivery | Not started | Store publish exists (pre-existing). |
| G8 Release | Not started | |

## Test runs

| Date | Command | Result |
| --- | --- | --- |
| 2026-10-18 | `python3 -m pytest -q` (baseline, before changes) | 187 passed, 10 skipped |
| 2026-10-18 | `python3 -m pytest -q` (after G1 slice) | 212 passed, 11 skipped |
| 2026-10-18 | same, with `riscv32-esp-elf-gcc` 14.2.0 on `PATH` and `PYTHONPATH=../PRG32` | 214 passed, 9 skipped |
| 2026-10-18 | Browser check on a local server: export Pong archive, re-import, duplicate | Pass (7248-byte archive, 201 on import, no skipped files) |

Skipped and why:

- 9 × `tests/test_asm_generator.py` differential tests: need a host GCC with
  the PRG32 argument order; the macOS machine has Apple clang only. They run
  in CI (Ubuntu).
- 1 × `tests/test_concurrency.py` real-build test and 1 ×
  `tests/test_project_format.py` SDK ABI check: skip when the PRG32 SDK is not
  importable; both pass with `PYTHONPATH=../PRG32`.

## Known gaps and limitations

- Handwritten assembly mode is blocked on ADR-0004.
- Revision history, autosave snapshots, soft delete and search are not done.
- The browser simulator still runs the game IR, not RV32 machine code.
- No hardware, IdP tenant or Emscripten was available; nothing here claims
  hardware, SSO-provider or WASM validation.

## Rollback

The G1 slice adds no database columns. Rolling back is a plain `git revert`
of the commits; archives already downloaded stay readable by any later
version.
