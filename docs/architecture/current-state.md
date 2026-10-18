# Current state

What the PRG32 repositories contain **now**, read from source and from test
runs on 2026-10-18. The per-requirement status, with the source symbol and test
behind every claim, is `../capabilities.md` (generated from
`../capabilities.json`, checked by `tests/test_capabilities.py`). The original
G0 discovery is summarised at the end for history.

## Repositories

| Repository | Branch | Commit | Role |
| --- | --- | --- | --- |
| PRG32-Construction-Kit | `development` | `6b7aac9` + refinement phase 0 | This repository. Flask + SQLAlchemy + Bootstrap + jQuery + Blockly PWA. MIT. |
| PRG32 | `main` | `679dfb5` | SDK, firmware, `prg32` CLI, portable cartridge builder, ABI 1.6 (`prg32/abi/abi_generated.py`). |
| PRG32-QT | `main` | `f6d80ad` (0.4.1) | Qt host; its Qt-free `src/core` is compiled into the kit's browser runtime (`static/wasm/BUILD.json`). |
| CartridgeStore | `main` | `820f74b` local (upstream `fb33fda`: CI/metrics only) | Store, accounts, `/api/publish/bundle` (pending review). `sso_protocol.py` identical to the kit's. |
| PRG32-iOS | `main` | `547fa45` | Private. Imports cartridges with a SwiftUI file importer; no URL scheme, no debugger. |

## Test runs (refinement phase 0)

| Command | Result |
| --- | --- |
| `python3 -m pytest -q -rs` (macOS, no toolchain), before phase 0 | 475 passed, 21 skipped |
| same with `riscv32-esp-elf-gcc` 14.2.0 and `PYTHONPATH=../PRG32` | 480 passed, 16 skipped |
| `compileall`, `node --check`, `git diff --check` | clean |

Skips: 9 assembly/C differential tests need a host GCC (macOS has Apple clang);
6 bubblewrap escape tests need Linux user namespaces (they pass in the kit's
Docker image, see `../build_sandbox.md`); real-build and SDK-ABI tests need the
PRG32 toolchain/SDK; `RLIMIT_AS` is Linux-only. Emscripten 6.0.12 is installed;
the WASM module matches `static/wasm/BUILD.json`.

## What the kit is today

A **classroom PRG32 construction kit**, not yet the Full IDE of the design
baseline (`../briefs/`, ADR-0011). Implemented and tested:

- **Projects:** Blocks (canonical Blockly JSON), Advanced C and handwritten
  assembly (ADR-0004); versioned `prg32.project.json`, deterministic archives,
  migrations, history with identity-preserving restore, soft delete.
- **Generation:** Blocks → validated IR → deterministic, explained C and RV32IM
  assembly.
- **Builds:** real `.prg32` through the PRG32 SDK, each compile isolated by
  bubblewrap + seccomp + limits (ADR-0010), per-build folders, provenance with
  SHA-256 of sources and cartridges.
- **Browser runtime and debugger:** PRG32-QT's core compiled to WebAssembly;
  Player with pause/continue/step instruction/over/out/frame, speeds,
  persistent address breakpoints, registers, disassembly, memory; WASM = native
  = `prg32qt-headless` in differential tests.
- **Publishing:** Store egress policy (ADR-0008), publisher role, signed review
  and explicit confirmation, idempotent attempts (ADR-0009).
- **Accounts:** local accounts, roles, groups, API tokens, secure first-admin
  bootstrap, throttling, audit log, SSO with CartridgeStore.

Not implemented (see `../capabilities.md` for the full list): IDE shell and
Monaco with language services; source/block debugging (DWARF, locals, call
stack, watches, Blockly highlighting); guest mode and IndexedDB; academic
OIDC/PKCE and scoped roles; Google Drive/OneDrive; verified hardware, Qt-import
and iOS delivery; offline app shell (the pages still load Bootstrap, jQuery and
Blockly from CDNs).

## Risks

1. **Scope gap:** the release goal is a Full IDE; the IDE shell, language
   services and source-level debugging are the largest missing pieces.
2. **Offline/CSP:** third-party CDN assets break cold-offline use and prevent a
   strict Content Security Policy (refinement phase 1).
3. **Sandbox deployment:** AppArmor hosts need `apparmor=unconfined` today; no
   per-build disk quota or UID (`../build_sandbox.md`).
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
