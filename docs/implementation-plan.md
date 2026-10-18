# Full-IDE implementation plan

Phased plan for turning the kit into a browser-first PRG32 IDE. It starts
from `docs/architecture/current-state.md` and the ADRs in `docs/adr/`.
Progress is tracked in `docs/implementation-status.md`; each requirement maps
to evidence in `docs/traceability.md`.

A gate is complete only when its acceptance tests pass in CI.

## Dependency order

```text
G0 discovery ─► G1 project model ─► G2 IDE shell ─┐
                       │                          ├─► G5 debugger ─► G7 delivery ─► G8 release
                       └─► G3 toolchain ─► G4 WASM ┘
G1 ─► G6 identity/storage ─► G7
```

## G0 Discovery — done

- `docs/architecture/current-state.md`: repositories, SHAs, capability matrix.
- `docs/adr/0001`–`0007`.
- Baseline test commands and results.

## G1 Foundation

| Task | Files | Status |
| --- | --- | --- |
| Manifest schema v1, builder, validator | `prg32_construction_kit/project_format.py` | done |
| Migrations (legacy export → v1) | `project_format.py` | done |
| Deterministic archive export | `project_format.py`, `GET /api/projects/<id>/archive` | done |
| Safe archive import | `project_format.py`, `POST /api/projects/import` | done |
| Manifest view | `GET /api/projects/<id>/manifest` | done |
| Server-side duplicate (with sprites/assets) | `POST /api/projects/<id>/duplicate` | done |
| Handwritten assembly mode (ADR-0004) | `source_project.py`, `routes.py`, `project_format.py`, editor | done |
| Editor/dashboard buttons | `templates/editor.html`, `templates/index.html`, `static/js/*.js` | done |
| Revision history (snapshot on save, list, restore) | new `project_revisions` table, routes | done |
| Soft delete + recovery | `deleted_at` column via idempotent `ALTER TABLE` | done |
| Guest policy A/B/C config + IndexedDB guest store | `config.py`, `static/js/guest_store.js` | later |

## G2 IDE shell

| Task | Files |
| --- | --- |
| New `/ide/<project_id>` page: explorer, tabs, output, problems, status bar | `templates/ide.html`, `static/js/ide/*.js` |
| Monaco (vendored, offline-cached) for C and RISC-V assembly | `static/vendor/monaco/`, service worker |
| C diagnostics from the server validator, then clangd-in-worker spike | `source_project.py`, `static/js/ide/c_language.js` |
| PRG32 ABI completion/hover from `prg32/abi` JSON | generated `static/data/prg32_abi.json` |
| Command palette, shortcuts, layout persistence (localStorage) | `static/js/ide/shell.js` |
| Keyboard and screen-reader pass; small-screen fallback to the current editor | — |

Constraint: Bootstrap + jQuery stay the app framework (`AGENTS.md`); Monaco
is an editor component, like Blockly.

## G3 Toolchain

| Task | Files |
| --- | --- |
| Build provenance: compiler version, SDK commit, ABI hash, SHA-256 per cartridge | `packager.py`, build metadata |
| Cartridge header check after every build (ABI hash, ISA flags, sizes) | new `cartridge_check.py` (port of `Cartridge::parse` checks) |
| Debug vs release build profiles (`-O0 -g` / `-Os`) | `packager.py`, manifest `build_profiles` |
| Container-isolated builds for untrusted users | `docker/`, `packager.py` |
| Browser toolchain spike: measure Clang/LLD WASM size, memory, time | `docs/spikes/browser-toolchain.md` |

## G4 WASM runtime

| Task | Repository |
| --- | --- |
| Emscripten build of `prg32qt_core` + C API | PRG32-QT (upstream PR) |
| Browser host: canvas, Web Audio, input, timing | this repo `static/js/runtime/` |
| Golden test: headless vs WASM under Node on `Asteroids.prg32`, `Bach.prg32` | both |

## G5 Debugger

Protocol per ADR-0006. Parity table in `docs/compatibility.md`. Start with
Qt's existing set (pause/resume/step/speed/breakpoints/registers/memory/
disassembly), then add step over/out and watches in the core, then DWARF for
`-g` builds, then Blockly block highlighting from IR source maps.

## G6 Identity and storage

PKCE and issuer+subject linking (ADR-0007), multi-provider admin UI, wider
roles together with CartridgeStore, guest policy, Drive/OneDrive sync behind
explicit OAuth consent.

## G7 Delivery

Store wizard with checksum and explicit confirmation; PRG32-QT and iOS
hand-off by file download/share (no invented URL schemes); physical device
transfer only after the firmware transport is inspected.

## G8 Release

Security review, accessibility audit, performance budget, reproducible
container, release notes.

## Blocked on the project owner

- Emscripten and a host GCC for differential assembly tests on the build
  machine.
- IdP test tenants (institutional OIDC, Google Workspace, Entra ID).
- Physical PRG32 hardware for device transfer tests.
