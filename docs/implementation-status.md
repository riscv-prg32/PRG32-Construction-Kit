# Implementation status

Status of the full-IDE plan (`implementation-plan.md`). A gate is marked
**complete** only when its acceptance tests pass. Updated 2026-10-18.

| Gate | State | Summary |
| --- | --- | --- |
| G0 Discovery | **Complete** | `architecture/current-state.md`, ADR-0001…0007, baseline tests recorded. |
| G1 Foundation | **In progress** | Manifest, migrations, archive, duplicate, handwritten assembly mode, revisions, soft delete done; guest policy open. |
| G2 IDE shell | Not started | |
| G3 Toolchain | In progress | Server builds produce real `.prg32` (pre-existing); build provenance and cartridge SHA-256 done (quality round 1). Browser toolchain and container isolation open. |
| G4 WASM runtime | **Complete** (core scope) | PRG32-QT core as WebAssembly, `/player`, golden tests WASM = native = `prg32qt-headless`. Multiplayer/Wi-Fi host services and exact audio open. |
| G5 Debugger | **In progress** (Qt-parity slice complete) | Player debugger on the WASM core: pause/continue, step instruction/over/out/frame, speeds 0.01×–4×, gutter breakpoints remembered per cartridge SHA-256, registers with change highlighting, disassembly following the PC, memory view, game vs real time, beginner/advanced views; PRG32-QT's `/api/debug` vocabulary (ADR-0006); differential tests WASM = native. DWARF/C locals, watches, conditional breakpoints and Blockly block highlighting open. |
| G6 Identity/storage | In progress | Secure first-admin bootstrap, sign-in throttling, admin audit log done (quality round 1). OIDC/PKCE, roles, guest policy, cloud sync open. |
| G7 Delivery | Not started | Store publish exists (pre-existing). |
| G8 Release | Not started | |

## Test runs

| Date | Command | Result |
| --- | --- | --- |
| 2026-10-18 | `python3 -m pytest -q` (baseline, before changes) | 187 passed, 10 skipped |
| 2026-10-18 | `python3 -m pytest -q` (after G1 slice) | 212 passed, 11 skipped |
| 2026-10-18 | same, with `riscv32-esp-elf-gcc` 14.2.0 on `PATH` and `PYTHONPATH=../PRG32` | 214 passed, 9 skipped |
| 2026-10-18 | `python3 -m pytest -q` (after revisions + soft delete, on top of assembly mode) | 259 passed, 13 skipped |
| 2026-10-18 | Browser check on a local server: export Pong archive, re-import, duplicate | Pass (7248-byte archive, 201 on import, no skipped files) |
| 2026-10-18 | `python3 -m pytest -q` (after handwritten assembly) | 250 passed, 12 skipped |
| 2026-10-18 | same, with the real toolchain | 253 passed, 9 skipped (incl. a real `.prg32` from handwritten assembly) |
| 2026-10-18 | Browser check: Assembly editor mode, Check Assembly | Pass |
| 2026-10-18 | Quality round 1 baseline on `development` @ `dfed78e`: `python3 -m pytest -q -rs` | 266 passed, 12 skipped |
| 2026-10-18 | same, with the real toolchain | 269 passed, 9 skipped |
| 2026-10-18 | After quality round 1: `python3 -m pytest -q -rs` | 317 passed, 13 skipped |
| 2026-10-18 | same, with `riscv32-esp-elf-gcc` 14.2.0 and PRG32 SDK `679dfb5` | 321 passed, 9 skipped (only the 9 host-GCC differential tests) |
| 2026-10-18 | `PRG32_KIT_ENV=production python3 tools/check_build.py --students 2 --windows 2` (real toolchain) | Pass: 8 cartridges, isolation intact |
| 2026-10-18 | After G4: `python3 -m pytest -q -rs` (Node, CMake, clang++, PRG32-QT `f6d80ad` present) | 328 passed, 14 skipped |
| 2026-10-18 | same, with the real toolchain and PRG32 SDK | 333 passed, 9 skipped (only the 9 host-GCC differential tests) |
| 2026-10-18 | Browser check on a local server: Pong compiled with the real toolchain, opened in `/player` | Pass: 151 frames in 5.0 s at 1×; at 0.25× 4 s real = 1 s game time; Enter started the match; no console errors |
| 2026-10-18 | After G5 (debugger): `python3 -m pytest -q -rs` | 347 passed, 14 skipped |
| 2026-10-18 | same, with the real toolchain and PRG32 SDK | 352 passed, 9 skipped (only the 9 host-GCC differential tests) |
| 2026-10-18 | Browser check: Advanced C cartridge compiled by the kit, `/player` debugger | Pass: gutter breakpoint stops once per frame and Continue moves past it; step/step over (whole call, 10 instructions)/step out (lands on draw); changed registers highlighted; 0.01× walks the PC; breakpoint remembered after reload; decimal and invalid memory addresses; no horizontal scroll at 375 px; no console errors |

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
- The editor's Blocks preview still runs the game IR, not RV32 machine code
  (the Player runs and debugs the real cartridge).
- Debugger: no C variables, call stack, watches or conditional breakpoints
  (needs DWARF), no Blockly block highlighting (needs IR source maps); music
  tracks pause in debug mode, as in PRG32-QT.
- No hardware, IdP tenant or Emscripten was available; nothing here claims
  hardware, SSO-provider or WASM validation.

## Rollback

The first G1 slice added no database columns. The revisions slice adds the
`project_revisions` table and the `projects.deleted_at` column (both created
on start, idempotently). Rolling back the code leaves them unused and
harmless, but projects that were soft-deleted would show up again in lists:
purge or restore them before rolling back. Archives already downloaded stay
readable by any later version.
