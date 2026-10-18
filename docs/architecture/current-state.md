# Current state (G0 discovery)

This page records what the PRG32 repositories **actually contain today**, so the
full-IDE plan (`docs/implementation-plan.md`) starts from facts rather than
assumptions. Everything here was read from source or measured on 2026-10-18.

## Repositories inspected

| Repository | Branch | Commit | Notes |
| --- | --- | --- | --- |
| PRG32-Construction-Kit | `main` | `b360678` | This repository. Flask + SQLAlchemy + Bootstrap + jQuery + Blockly PWA. MIT. |
| PRG32 | `main` | `679dfb5` | SDK, firmware, `prg32` Python CLI, portable cartridge builder, ABI generator. |
| PRG32-QT | `main` | `f6d80ad` (v0.4.1) | Qt host; **Qt-free core** in `src/core` (`prg32qt_core` static library). MIT. |
| CartridgeStore | `main` | `820f74b` | Flask store, accounts, OIDC/SAML/LDAP adapters, bundle publish + review. |
| PRG32-iOS | `main` | `547fa45` | **Private** repository. Swift re-implementation of the runtime (`PRG32iOS/Core`). |

## Baseline tests

| Command | Result |
| --- | --- |
| `python3 -m pytest -q` | 187 passed, 10 skipped (9 assembly differential tests: no RISC-V GCC with the PRG32 argument order; 1 concurrency test: PRG32 toolchain not installed). |
| `PATH=~/.espressif/tools/riscv32-esp-elf/esp-14.2.0_20241119/riscv32-esp-elf/bin:$PATH PYTHONPATH=../PRG32 python3 -m pytest -q` | 188 passed, 9 skipped (real cartridges compiled; the assembly differential tests still need a host GCC, macOS has Apple clang only). |

Environment: macOS 26 (arm64), Python 3.12.10, Node 26.10, Apple clang 21,
Homebrew `llvm@22`, ESP-IDF `riscv32-esp-elf-gcc` 14.2.0. **No Emscripten**
is installed, so no WebAssembly build was attempted.

## Verified facts that shape the plan

- **Portable cartridge ABI.** PRG32 `prg32/abi/abi_generated.py`: ABI 1.6,
  hash `0x260f6136`, compatible hashes `0x006427c2` and `0x6be6e8d0`.
  PRG32-QT `Runtime.h` declares the same three hashes. The SDK compiles with
  `-march=rv32imc_zicsr_zifencei` by default; PRG32-QT interprets RV32IMAC.
- **Cartridge format.** PRG2 header v1/v2 (`PRG32-QT/src/core/Cartridge.h`):
  magic, ABI major/minor, load address, entry offsets for init/update/draw,
  payload CRC-32, v2 ABI hash, feature masks, ISA flags, relocations, import
  model `1` (ABI table). Metadata trailers follow the payload.
- **The kit's simulator is not a guest runtime.** `static/js/simulator.js`
  interprets the kit's *game IR*, not RV32 machine code. It is a teaching
  preview, not a PRG32 emulator. Advanced C projects cannot run in it.
- **PRG32-QT core is Qt-free.** `src/core/*.cpp` (≈2.9k lines) has no Qt
  includes and builds as `prg32qt_core` plus `prg32qt-headless`. It is the
  natural candidate for a WebAssembly port (G4). Not yet attempted.
- **PRG32-QT debugger** (`docs/DEBUGGING.md`, `Runtime::debugStep`):
  pause, resume, single-instruction step, speed `0.01×–4×`, address
  breakpoints (cleared on cartridge load, no conditions or hit counts),
  x0–x31 in hex, bounded memory reads (≤1024 bytes over HTTP), disassembly,
  Init/Update/Draw/PC views, telemetry. **Absent in Qt:** step over/into/out,
  CSR view, DWARF locals, call stack, watches, conditional breakpoints, source
  breakpoints. HTTP control: `GET/POST /api/debug` on the Qt host's local
  web server.
- **PRG32-QT local web API** (`src/qt/WebApiServer.cpp`): `/api/runtime`,
  `/api/games` (GET/POST), `/api/games/select`, `/api/screenshot.bmp`,
  `/api/debug`, discovered via mDNS `_prg32._tcp.local.`. A browser page
  cannot rely on reaching it (mixed content, CORS, private-network access).
- **PRG32-iOS** imports cartridges through a SwiftUI `fileImporter`
  (`ContentView.swift`) accepting any data file. No URL scheme or document
  type is declared in `Info.plist`, no debugger. Hand-off is "share the
  `.prg32` file and import it", nothing more.
- **CartridgeStore publish contract.** `POST /api/publish/bundle`
  (multipart `bundle=@game.zip`, `manifest.json` with
  `abi: prg32-metadata-1.0`, `icon.png`, one or more `.prg32`). Upload makes a
  *pending submission*; editors verify or reject. The kit already uses this.
- **CartridgeStore roles** are `user`/`admin` plus the `editors` group; OIDC
  uses Authlib with discovery from the issuer. The kit mirrors this model and
  shares `sso_protocol.py` byte-for-byte.

## Capability matrix

Legend: **I** implemented, **P** partial, **A** absent, **U** unknown / not
verifiable here.

| Area | Capability | State | Evidence |
| --- | --- | --- | --- |
| Project model | Projects with Blocks JSON, game IR, Advanced C | I | `db.py`, `source_project.py`, `tests/test_source_project.py` |
| Project model | Versioned `prg32.project.json` manifest | A → G1 | — |
| Project model | Portable archive import/export | P | JSON export `prg32-construction-kit-project-1.0`; no sprites/assets, no zip |
| Project model | Duplicate | P | "Make my copy" is client-side only (`editor.js`) |
| Project model | Revision history, snapshots, soft delete | A | — |
| Project model | Handwritten assembly mode | I (after G0) | ADR-0004 accepted; `validate_asm_source`, `tests/test_handwritten_assembly.py` |
| Editor | Blockly editor, sprite editor | I | `static/js/blockly_blocks.js`, `sprite_editor.js` |
| Editor | Advanced C text editing | P | Plain textarea, no language services |
| Editor | Monaco, LSP, command palette, multi-pane IDE shell | A | — |
| Build | Blocks → IR → C / RV32IM assembly, deterministic | I | `generator.py`, `asm_generator.py`, tests |
| Build | Real `.prg32` through the PRG32 SDK on the server | I | `packager.py`, `tools/check_build.py`, CI container job |
| Build | Per-build isolation, slots, timeouts, log redaction | I | `build_slots.py`, `tests/test_concurrency.py` |
| Build | Toolchain provenance and artifact hashes recorded | A | — |
| Build | Browser-local (WASM) compilation | A | No Emscripten/WASM toolchain evaluated yet |
| Build | OS-level sandbox for C builds | A | Documented as "not an OS sandbox" (`docs/architecture.md`) |
| Runtime | IR simulator in the browser | I | `simulator.js`, `tests/test_simulator_js.py` |
| Runtime | Real RV32 guest execution in the browser | A | PRG32-QT core exists natively only |
| Debugger | Kit debugger | P | IR-level pause/step in the simulator; no machine state |
| Debugger | Qt-parity instruction debugger in the browser | A | — |
| Accounts | Local accounts, roles, groups, API tokens | I | `auth.py`, `tests/test_auth.py` |
| Accounts | SSO with CartridgeStore (signed sync, tickets) | I | `sso.py`, `tests/test_sso*.py` |
| Accounts | OIDC/SAML directly in the kit | P | `auth_adapters.py`: one env-configured OIDC provider via Authlib (discovery, state, nonce), **no PKCE**, users linked by `("oidc", sub)` rather than issuer+subject; optional SAML via python3-saml. No admin UI, no multi-IdP. |
| Accounts | Guest policy, IndexedDB guest projects | A | — |
| Accounts | Teacher/TA/publisher roles, course scoping | A | — |
| Cloud | Google Drive / OneDrive sync | A | — |
| Store | Bundle preparation and publish | I | `packager.py`, `publisher.py`, `/api/publish` |
| Store | Wizard, checksums, explicit confirmation step | P | Publish page exists; no checksum display |
| Targets | PRG32-QT hand-off | P | Download `.prg32` works; Qt import is manual |
| Targets | PRG32-iOS hand-off | P | Download + Files import only |
| Targets | Physical PRG32 transfer (WebSerial/SD) | U | Firmware transport not yet inspected |
| Delivery | PWA, service worker, Docker, CI, GHCR | I | `static/service-worker.js`, `Dockerfile`, `.github/workflows/tests.yml` |

## Cross-repository dependencies

```text
Construction Kit --(python -m prg32 cartridge build)--> PRG32 SDK
Construction Kit --(POST /api/publish/bundle, SSO)----> CartridgeStore
Construction Kit --(sso_protocol.py identical copy)---> CartridgeStore
Construction Kit ..(planned WASM build of src/core)...> PRG32-QT
PRG32-QT / PRG32-iOS --(GET /api/games/*/download)----> CartridgeStore
```

## Risks

1. **Policy conflict (resolved).** The brief asked for a handwritten assembly
   mode that `AGENTS.md` forbade; ADR-0004 option 2 was accepted and
   `AGENTS.md` updated.
2. **Untrusted native compilation.** C builds run the real GCC on the server
   without an OS sandbox. Opening the kit to guests or the internet requires
   container/seccomp isolation first (ADR-0005).
3. **WASM runtime parity.** The browser must run the PRG32-QT core, not a
   re-implementation; the iOS app already diverged into a Swift copy, which is
   the drift we must avoid.
4. **Browser toolchain size.** A Clang/LLD WASM build for RISC-V is tens of
   megabytes; feasibility is unmeasured.
5. **Private iOS repository.** PRG32-iOS is private; integration docs must not
   leak its internals beyond the public hand-off behaviour.
