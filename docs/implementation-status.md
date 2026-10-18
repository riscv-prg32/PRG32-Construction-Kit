# Implementation status

Status of the full-IDE plan (`implementation-plan.md`). A gate is marked
**complete** only when its acceptance tests pass. Updated 2026-10-18.

| Gate | State | Summary |
| --- | --- | --- |
| G0 Discovery | **Complete** | `architecture/current-state.md`, ADR-0001…0007, baseline tests recorded. |
| G1 Foundation | **In progress** | Manifest, migrations, archive, duplicate, handwritten assembly mode, revisions, soft delete done; guest policy open. |
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
| 2026-10-18 | `python3 -m pytest -q` (after revisions + soft delete) | 220 passed, 12 skipped |
| 2026-10-18 | Browser check on a local server: export Pong archive, re-import, duplicate | Pass (7248-byte archive, 201 on import, no skipped files) |
| 2026-10-18 | `python3 -m pytest -q` (after handwritten assembly) | 250 passed, 12 skipped |
| 2026-10-18 | same, with the real toolchain | 253 passed, 9 skipped (incl. a real `.prg32` from handwritten assembly) |
| 2026-10-18 | Browser check: Assembly editor mode, Check Assembly | Pass |

Skipped and why:

- 9 × `tests/test_asm_generator.py` differential tests: need a host GCC with
  the PRG32 argument order; the macOS machine has Apple clang only. They run
  in CI (Ubuntu).
- Real-build tests (`tests/test_concurrency.py`,
  `tests/test_handwritten_assembly.py`) and the SDK ABI check
  (`tests/test_project_format.py`) skip when the PRG32 SDK or toolchain is
  missing; all pass with `PYTHONPATH=../PRG32` and `riscv32-esp-elf-gcc`.

## Known gaps and limitations

- Autosave snapshots and project search are not done (history is kept on
  every save that changes the source, not on a timer).
- Restoring a revision replaces the project's sprites with new rows (new ids);
  artifacts that pointed at the old sprites keep their files but lose the link.
- The browser simulator still runs the game IR, not RV32 machine code.
- No hardware, IdP tenant or Emscripten was available; nothing here claims
  hardware, SSO-provider or WASM validation.

## Rollback

The first G1 slice added no database columns. The revisions slice adds the
`project_revisions` table and the `projects.deleted_at` column (both created
on start, idempotently). Rolling back the code leaves them unused and
harmless, but projects that were soft-deleted would show up again in lists:
purge or restore them before rolling back. Archives already downloaded stay
readable by any later version.
