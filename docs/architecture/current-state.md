# Current state

What the PRG32 repositories contain **now**, read from source and from test
runs on 2026-10-19 at `731e378` (refinement phase 2) plus the CI and
documentation fixes that follow the audit of that commit. The per-requirement
status, with the source symbol and test behind every claim, is
`../capabilities.md` (generated from `../capabilities.json`). The lists below
are a summary of that file, and `tests/test_doc_consistency.py` fails when they
disagree with it. Audit scores belong to the auditor (`../../audit/`).

## Repositories

| Repository | Branch | Commit | Role |
| --- | --- | --- | --- |
| PRG32-Construction-Kit | `development` | `731e378` (refinement phases 0–2) | This repository. Flask + SQLAlchemy + Bootstrap + jQuery + Blockly + Monaco PWA, all served from `static/vendor/`. MIT. |
| PRG32 | `main` | `679dfb5` | SDK, firmware, `prg32` CLI, portable cartridge builder, ABI 1.6 (`prg32/abi/abi_generated.py`). |
| PRG32-QT | `main` | `f6d80ad` (0.4.1) | Qt host; its Qt-free `src/core` is compiled into the kit's browser runtime (`static/wasm/BUILD.json`). |
| CartridgeStore | `main` | `820f74b` local (upstream `fb33fda`: CI/metrics only) | Store, accounts, `/api/publish/bundle` (pending review). `sso_protocol.py` identical to the kit's. |
| PRG32-iOS | `main` | `547fa45` (read 2026-10-18, not checked out here) | Private. Imports cartridges with a SwiftUI file importer; no URL scheme, no debugger. |

## Test runs (2026-10-19, macOS, after the CI and documentation fixes)

| Command | Result |
| --- | --- |
| `python3 -m pytest -q -rs` (no RISC-V toolchain) | 654 passed, 21 skipped |
| same with `riscv32-esp-elf-gcc` 14.2.0 and `PYTHONPATH=../PRG32` | 659 passed, 16 skipped |
| `python3 -m pytest -q -rs tests/test_browser_offline.py tests/test_frontend_offline.py tests/test_ide_browser.py` (Chrome) | 61 passed (`PRG32_REQUIRE_BROWSER=1`: no skips) |
| `compileall`, `node --check`, `service_worker_lock.py --check`, `render_capabilities.py --check`, `git diff --check` | clean |

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
- Versioned projects (Blocks, Advanced C, handwritten assembly), archives,
  migrations, history with identity-preserving restore, soft delete. [PRJ-01]
- Real `.prg32` builds from Blocks, C and assembly; every compile isolated by
  bubblewrap + seccomp + limits, with provenance and SHA-256. [BLD-01] [BLD-02]
- Browser runtime: the PRG32-QT core as WebAssembly, equal to the native core
  and `prg32qt-headless`; browser host with framebuffer, input, timing, audio
  and an offline subset (scratchpad, Blocks preview, local player). [WASM-01] [WASM-02]
- Player debugger: pause, continue, restart, speeds, instruction/over/out
  stepping, address breakpoints, browser state equal to PRG32-QT's. [DBG-01] [DBG-02] [DBG-03] [DBG-06]
- Accounts shared with CartridgeStore; authorized, reviewed, confirmed
  publishing behind a Store egress policy. [SSO-04] [STR-02]
- Threat model, SSRF controls, build isolation; CI, Docker, migrations,
  health; documentation and traceability. [SEC-01] [OPS-01] [DOC-01]
- Self-contained frontend: every library from `static/vendor/`, strict CSP,
  static-only service worker at `/` (ADR-0012). [WASM-02]

### Partly implemented

- Blocks with deterministic generation, but no block → IR → source/address
  maps. [IDE-02]
- Monaco editors for C and assembly with colours, the allowed-directive
  grammar and line-exact server/compiler problems; no completion, hover or
  navigation yet (refinement phase 3). [IDE-03] [IDE-04]
- Registers, memory and disassembly views; no CSR, stack or watch views. [DBG-04]
- Registered storage with ownership and history; no quotas, autosave or
  retention. [ACC-02]
- Prototype OIDC (one provider, no PKCE) and an ordinal role ladder. [SSO-01] [SSO-02] [SSO-03]
- Store bundle preparation without a shared schema or live conformance; PRG32-QT
  delivery with runtime parity but no executed import. [STR-01] [DEP-02]
- Credentials, throttling and audit log; quality gates without lint, type,
  coverage or performance budgets. [SEC-02] [QLT-01]

### Not implemented

- Source/block debugging: C locals, call stack, watches (DWARF), active Blockly
  block (refinement phase 4). [DBG-05]
- Guest mode and IndexedDB guest projects (phase 6). [ACC-01]
- Google Drive and OneDrive (phase 8). [CLD-01] [CLD-02]
- Verified hardware and PRG32-iOS delivery. [DEP-01] [DEP-03]

## Risks

1. **Scope gap:** language services, source-level debugging, identity and
   guest storage are the largest missing pieces of the Full IDE.
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
