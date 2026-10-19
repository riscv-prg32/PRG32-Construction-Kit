# Current state

What the PRG32 repositories contain **now**: `development` at `5dd98a9`
(refinement phase 4, audited as 79/132) and the changes after it listed under
**Milestones**, read from source and from the test runs below. The per-requirement
status, with the source symbol and test behind every claim, is
`../capabilities.md` (generated from `../capabilities.json`). The lists below
are a summary of that file, and `tests/test_doc_consistency.py` fails when they
disagree with it. Audit scores belong to the auditor (`../../audit/`).

## Repositories

| Repository | Branch | Commit | Role |
| --- | --- | --- | --- |
| PRG32-Construction-Kit | `development` | `5dd98a9` (refinement phases 0–4) | This repository. Flask + SQLAlchemy + Bootstrap + jQuery + Blockly + Monaco PWA, all served from `static/vendor/`. MIT. |
| PRG32 | `main` | `679dfb5` | SDK, firmware, `prg32` CLI, portable cartridge builder, ABI 1.6 (`prg32/abi/abi_generated.py`). |
| PRG32-QT | `main` | `f6d80ad` (0.4.1) | Qt host; its Qt-free `src/core` is compiled into the kit's browser runtime (`static/wasm/BUILD.json`). |
| CartridgeStore | `main` | `820f74b` local (upstream `fb33fda`: CI/metrics only) | Store, accounts, `/api/publish/bundle` (pending review). `sso_protocol.py` identical to the kit's. |
| PRG32-iOS | `main` | `547fa45` (read 2026-10-18, not checked out here) | Private. Imports cartridges with a SwiftUI file importer; no URL scheme, no debugger. |

## Milestones

Every refinement phase and the audit that followed it. `tests/test_doc_consistency.py`
checks that each `Refinement phase` commit in the history is listed here by its
commit; the newest may say *this change* while it is the commit being made.

| Milestone | Commit | Evidence |
| --- | --- | --- |
| Refinement phase 0: baseline, machine-checked capabilities | `62eb5bf` | `capabilities.json`, `tests/test_capabilities.py` |
| Refinement phase 1: self-contained frontend, root service worker, strict CSP | `903cba0` | ADR-0012, `tests/test_frontend_offline.py`, `tests/test_browser_offline.py` |
| Refinement phase 2: IDE shell with Monaco | `731e378` | ADR-0013, `tests/test_ide_browser.py` (audited: 70/132) |
| CI browser suite, documentation drift repair | `7910e86`, `9332c8c` | `tests/test_frontend_offline.py::test_ci_runs_every_browser_suite_and_forbids_skipping`, `tests/test_doc_consistency.py` |
| Refinement phase 3: offline language services | `a9f2c97` | ADR-0014, `tests/test_language_services.py` |
| Refinement phase 4: source and block debugger | `5dd98a9` | ADR-0015, `tests/test_source_debugger.py`, `tests/test_debugger_browser.py` (audited: 79/132) |
| Evidence drift repair after the audit of `5dd98a9` | `e91b68b` | `../evidence.md`, `tests/test_doc_consistency.py` |
| Refinement phase 5: academic identity and scoped roles | this change | ADR-0016, `tests/test_identity.py`, `tests/test_authorization.py`, `tests/test_accounts_browser.py` |

How each kind of evidence is produced and checked: `../evidence.md`.

## Test runs (2026-10-19, macOS, at `5dd98a9`)

| Command | Result |
| --- | --- |
| `python3 -m pytest -q -rs` (no RISC-V toolchain) | 723 passed, 23 skipped |
| same with `riscv32-esp-elf-gcc` 14.2.0 and `PYTHONPATH=../PRG32` | 730 passed, 16 skipped |
| browser suites (`tests/test_*browser*.py`, `tests/test_frontend_offline.py`, Chrome) | 65 passed (`PRG32_REQUIRE_BROWSER=1`: no skips) |
| kit Docker image with the production sandbox (`bwrap`): `tests/test_build_sandbox.py`, `test_handwritten_assembly.py`, `test_source_debugger.py`; `tools/check_build.py` | pass (Node-based tests skip there; they run in the other jobs) |
| `compileall`, `node --check`, `service_worker_lock.py --check`, `render_capabilities.py --check`, `build_language_index.py --check`, `git diff --check` | clean |

Skips: 9 assembly/C differential tests need a host GCC (macOS has Apple clang);
6 bubblewrap escape tests need Linux user namespaces (they pass in the kit's
Docker image, see `../build_sandbox.md`); real-build and SDK-ABI tests need the
PRG32 toolchain/SDK; `RLIMIT_AS` is Linux-only. The browser suites skip without
Playwright and Chrome locally; the CI browser job sets `PRG32_REQUIRE_BROWSER=1`,
so there they run or fail. Emscripten 6.0.12 is installed; the WASM module
matches `static/wasm/BUILD.json`.

## What the kit is today

A **classroom PRG32 construction kit with an IDE shell**, not yet the Full IDE
of the design baseline (`../briefs/`, ADR-0011). Each line ends with its
capability IDs.

### Implemented

- IDE page `/ide/<id>`: project tree, editor tabs, Problems/Output/Preview/Run
  panels, status bar, command palette, F6 regions, keyboard-only use, phone
  layout, axe-core scan in a real browser (ADR-0013). [IDE-01]
- Offline language services for Advanced C and assembly: completion of the
  portable PRG32 ABI, allowed headers and directives, RV32IMC instructions and
  registers; hover, signature help, F12 into a generated `prg32.h (portable
  API)`; live problems at exact ranges that mirror the server's validators;
  compiler messages without server paths (ADR-0014). [IDE-03] [IDE-04]
- Versioned projects (Blocks, Advanced C, handwritten assembly), archives,
  migrations, history with identity-preserving restore, soft delete. [PRJ-01]
- Real `.prg32` builds from Blocks, C and assembly; every compile isolated by
  bubblewrap + seccomp + limits, with provenance and SHA-256. [BLD-01] [BLD-02]
- Browser runtime: the PRG32-QT core as WebAssembly, equal to the native core
  and `prg32qt-headless`; browser host with framebuffer, input, timing, audio
  and an offline subset (scratchpad, Blocks preview, local player). [WASM-01] [WASM-02]
- Player debugger: pause, continue, restart, speeds, instruction/over/out
  stepping, address breakpoints, browser state equal to PRG32-QT's. [DBG-01] [DBG-02] [DBG-03] [DBG-06]
- Source and block debugging for kit-compiled cartridges (ADR-0015): a saved
  block → IR → source → address map, C/assembly line and block breakpoints
  with conditions, the running block highlighted, locals, globals, call stack
  from DWARF call-frame rules, watches, counter CSRs and a stack view, a
  compressed-instruction fixture; the cartridge is byte-identical to one built
  without debug information, and without it the Player stays address-level.
  [IDE-02] [DBG-04] [DBG-05]
- Accounts shared with CartridgeStore; authorized, reviewed, confirmed
  publishing behind a Store egress policy. [SSO-04] [STR-02]
- Academic identity (ADR-0016): OIDC Authorization Code + PKCE with verified ID
  tokens, accounts by issuer + subject (never joined by email), several
  admin-configured providers, explicit account linking; academic roles and
  classes with read-only supervision, scoped and expiring API tokens, session
  epochs, deprovisioning. [SSO-01] [SSO-02] [SSO-03]
- Threat model, SSRF controls, build isolation; CI, Docker, migrations,
  health; documentation and traceability. [SEC-01] [OPS-01] [DOC-01]
- Self-contained frontend: every library from `static/vendor/`, strict CSP,
  static-only service worker at `/` (ADR-0012). [WASM-02]

### Partly implemented

- Registered storage with ownership, history and deprovisioning; no quotas,
  autosave or retention. [ACC-02]
- Store bundle preparation without a shared schema or live conformance; PRG32-QT
  delivery with runtime parity but no executed import. [STR-01] [DEP-02]
- Credentials, throttling and audit log; quality gates without lint, type,
  coverage or performance budgets. [SEC-02] [QLT-01]

### Not implemented

- Guest mode and IndexedDB guest projects (phase 6). [ACC-01]
- Google Drive and OneDrive (phase 8). [CLD-01] [CLD-02]
- Verified hardware and PRG32-iOS delivery. [DEP-01] [DEP-03]

## Risks

1. **Scope gap:** guest storage, quotas/autosave/retention, the shared Store
   contract, cloud storage and delivery evidence are the largest missing pieces
   of the Full IDE. School sign-in is tested against an in-process provider, not
   a live institutional tenant. The language services follow the
   kit's rules and the SDK, not C semantics (no types or scopes).
2. **Sandbox deployment:** AppArmor hosts need `apparmor=unconfined` today; no
   per-build disk quota or UID (`../build_sandbox.md`).
3. **Accessibility:** automated axe-core scans and keyboard tests only; no
   screen-reader session has been run.
4. **External validation:** no live Store, IdP, cloud provider, hardware or iOS
   device has been used; claims about them are absent on purpose.

---

## History: G0 discovery (2026-10-18, at `b360678`)

At the start of the Full IDE work the kit had Blocks, Advanced C, generated
C/assembly, server builds without a sandbox, an IR-level simulator, local
accounts and SSO with CartridgeStore, and Store publishing without an egress
policy or publisher gate. PRG32-QT's Qt-free core was identified as the browser
runtime (ADR-0003, done in G4). The baseline then was 187 passed, 10 skipped.
The ADRs in `../adr/` record every decision taken since.
