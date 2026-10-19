# Implementation status

Status of the full-IDE plan (`implementation-plan.md`). The per-requirement,
evidence-checked view is `capabilities.md` (from `capabilities.json`). A gate is marked
**complete** only when its acceptance tests pass. Updated 2026-10-19 (at `5dd98a9`, refinement phase 4; milestones in `architecture/current-state.md`).

| Gate | State | Summary |
| --- | --- | --- |
| G0 Discovery | **Complete** | `architecture/current-state.md`, ADR-0001…0007, baseline tests recorded. |
| G1 Foundation | **In progress** | Manifest, migrations, archive, duplicate, handwritten assembly mode, revisions, soft delete done; guest policy open. |
| G2 IDE shell | **In progress** | IDE shell with Monaco, keyboard model, small-screen fallback and browser/a11y tests done (refinement phase 2, ADR-0013) [IDE-01]; the browser suites run in CI and may not skip there. Offline language services for C and assembly done (phase 3, ADR-0014) [IDE-03] [IDE-04]; block-to-source maps next (phase 4). |
| G3 Toolchain | In progress | Server builds produce real `.prg32`; build provenance and cartridge SHA-256 done; every compile runs in a bubblewrap sandbox (ADR-0010, audit H-03). Browser toolchain open. |
| G4 WASM runtime | **Complete** (core scope) | PRG32-QT core as WebAssembly, `/player`, golden tests WASM = native = `prg32qt-headless`. Multiplayer/Wi-Fi host services and exact audio open. |
| G5 Debugger | **In progress** (source and block slice complete) | Player debugger on the WASM core (Qt parity, ADR-0006) plus, for kit-compiled cartridges, source and block debugging (ADR-0015) [DBG-05]: block → IR → source → address maps, C/assembly/block breakpoints with conditions, active block, locals/globals, call stack, watches, counter CSRs, stack view, compressed-instruction fixture; differential tests at source checkpoints. Open: inlined frames, operand-level checks, a PRG32-QT desktop equivalent. |
| G6 Identity/storage | In progress (identity slice complete) | Secure first-admin bootstrap, throttling, audit log (quality round 1); OIDC + PKCE, issuer+subject accounts, several providers, explicit linking, academic roles and classes, scoped tokens, session epochs and deprovisioning (ADR-0016) [SSO-01] [SSO-02] [SSO-03]. Guest policy, quotas, autosave, retention and cloud sync open. |
| G7 Delivery | Not started | Store publish exists (pre-existing); Store egress policy closes audit H-01 (ADR-0008); publisher role + confirmed review close H-02 (ADR-0009). Draft/update/visibility states not applicable (no Store API). |
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
| 2026-10-18 | After refinement phase 2 (`731e378`): `python3 -m pytest -q -rs` | 587 passed, 21 skipped |
| 2026-10-18 | same, with the real toolchain and PRG32 SDK | 592 passed, 16 skipped |
| 2026-10-19 | After the CI and documentation fixes: `python3 -m pytest -q -rs` | 654 passed, 21 skipped |
| 2026-10-19 | same, with the real toolchain and PRG32 SDK | 659 passed, 16 skipped (9 host-GCC differential, 6 bubblewrap, 1 `RLIMIT_AS`: Linux only) |
| 2026-10-19 | Browser, IDE and frontend suites with Chrome (`tests/test_browser_offline.py tests/test_ide_browser.py tests/test_frontend_offline.py`) | 61 passed |
| 2026-10-19 | After refinement phase 3 (language services): `python3 -m pytest -q -rs` | 677 passed, 21 skipped |
| 2026-10-19 | same, with the real toolchain and PRG32 SDK `679dfb5` | 682 passed, 16 skipped |
| 2026-10-19 | Browser suites with `PRG32_REQUIRE_BROWSER=1` | 63 passed |
| 2026-10-19 | After refinement phase 4 (source and block debugger): `python3 -m pytest -q -rs` | 723 passed, 23 skipped |
| 2026-10-19 | same, with the real toolchain and PRG32 SDK `679dfb5` | 730 passed, 16 skipped |
| 2026-10-19 | Browser suites (incl. scenario D, `tests/test_debugger_browser.py`) with `PRG32_REQUIRE_BROWSER=1` | 65 passed; scenario D 3/3 repeated runs |
| 2026-10-19 | `tests/test_wasm_runtime.py` with PRG32-QT `f6d80ad` (native vs WebAssembly at source checkpoints) | 37 passed, 1 skipped |
| 2026-10-19 | Kit Docker image, production sandbox (`bwrap`): `test_source_debugger.py` real debug build, `check_build.py` | pass: identical cartridge with and without `-g`; 8 cartridges |
| 2026-10-19 | After refinement phase 5 (identity and scoped roles): `python3 -m pytest -q -rs` | 798 passed, 23 skipped |
| 2026-10-19 | same, with the real toolchain and PRG32 SDK `679dfb5` | 805 passed, 16 skipped |
| 2026-10-19 | Browser suites incl. `tests/test_accounts_browser.py`, `PRG32_REQUIRE_BROWSER=1` | 70 passed |
| 2026-10-19 | `cmp prg32_construction_kit/sso_protocol.py ../CartridgeStore/cartridge_store/sso_protocol.py` | identical |

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
- (Fixed in quality round 1: restoring a revision now updates sprites and assets
  in place and keeps artifact links; `tests/test_restore_relationships.py`.)
- The editor's Blocks preview still runs the game IR, not RV32 machine code
  (the Player runs and debugs the real cartridge).
- Debugger: source/block features need a kit-compiled cartridge (ADR-0015);
  values optimised out at `-Os` are shown as such; inlined functions are not
  separate frames; music tracks pause in debug mode, as in PRG32-QT.
- No hardware or IdP tenant was available; nothing here claims hardware or
  SSO-provider validation. (Emscripten 6.0.12 has been available since G4: the
  WASM runtime is verified against the native core.)

## Rollback

The first G1 slice added no database columns. The revisions slice adds the
`project_revisions` table and the `projects.deleted_at` column (both created
on start, idempotently). Rolling back the code leaves them unused and
harmless, but projects that were soft-deleted would show up again in lists:
purge or restore them before rolling back. Archives already downloaded stay
readable by any later version.
