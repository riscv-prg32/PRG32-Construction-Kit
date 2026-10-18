# Requirements matrix

Scale: 0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against a reference. All 32 rows apply; denominator = 128.

| ID | Score | Status | Evidence and missing proof |
|---|---:|---|---|
| IDE-01 | 0 | Missing | Bootstrap page, not IDE shell (`templates/editor.html:63-133`); roadmap open (`docs/traceability.md:32`). No tree, palette, workspace tabs, keyboard/a11y proof. |
| IDE-02 | 2 | Partial | Editable Blockly JSON and deterministic generation are tested; block-to-source/address mapping is open (`docs/traceability.md:25-26,49-50`). |
| IDE-03 | 1 | Prototype | C is a textarea (`templates/editor.html:72-82`); no Monaco, completion, diagnostics, navigation, or SDK index. |
| IDE-04 | 1 | Prototype | Assembly textarea and server validator exist; no editor syntax/completion/diagnostics (`templates/editor.html:72-82`). |
| PRJ-01 | 3 | Implemented/tested | Versioned manifest, migrations, CRUD, archives, history and soft delete tested. Autosave/search/conflict merge remain open (`docs/implementation-status.md:54-57`). |
| BLD-01 | 2 | Partial | Three real-build paths and CI exist, but local real builds skipped because the PRG32 toolchain is absent; no new `.prg32` was produced. |
| BLD-02 | 3 | Implemented/tested | Per-build folders, provenance, diagnostics and production sandbox. Exact clean WASM rebuild was environment-blocked. |
| WASM-01 | 4 | Reference-verified | Pinned PRG32-QT core and differential native/WASM tests (`tests/test_wasm_runtime.py`). |
| WASM-02 | 3 | Implemented/tested | Graphics/input/timing/audio/resource tests exist; external CDN UI dependencies prevent a demonstrated cold-offline authoring shell. |
| DBG-01 | 4 | Reference-verified | Pause/continue/stop/restart/speed differential coverage. |
| DBG-02 | 3 | Implemented/tested | Instruction/over/out/frame tests pass; no dedicated compressed-instruction acceptance result in this audit. |
| DBG-03 | 3 | Implemented/tested | Persistent address breakpoints; no source/block breakpoints. |
| DBG-04 | 2 | Partial | x0-x31, PC, disassembly and bounded memory; no CSR/stack/watch views. |
| DBG-05 | 0 | Missing | DWARF locals/call stack/watches and active-block mapping explicitly open (`docs/traceability.md:49-50`). |
| DBG-06 | 4 | Reference-verified | Native/WASM/Qt-core state and framebuffer comparisons pass. |
| ACC-01 | 0 | Missing | Guest policy and IndexedDB are roadmap-only (`docs/implementation-plan.md:39`). |
| ACC-02 | 2 | Partial | Ownership, revisions, import/export, account-switch refusal; no quotas, autosave merge, retention/deprovisioning. |
| SSO-01 | 1 | Prototype | One Authlib OIDC provider; no explicit PKCE and identity key omits issuer (`auth_adapters.py:41-81`). Required IdP matrix not run. |
| SSO-02 | 1 | Prototype | Environment-only single provider; no admin IdP UI, multiple IdPs, claim mapping, or recovery workflow. |
| SSO-03 | 1 | Prototype | Generic role hierarchy, not scoped student/TA/teacher model (`auth.py:49-55`). Publisher gate now works. |
| SSO-04 | 3 | Implemented/tested | Shared protocol matches Store byte-for-byte; no live Store authorization test. |
| CLD-01 | 0 | Missing | Google Drive absent (`docs/traceability.md:59`). |
| CLD-02 | 0 | Missing | OneDrive/Graph absent (`docs/traceability.md:59`). |
| STR-01 | 2 | Partial | Manifest, cartridge magic and hashes validated locally (`publishing.py:84-132`); no shared Store schema or live duplicate/version conformance. |
| STR-02 | 3 | Implemented/tested | Publisher gate, signed review, explicit confirm, idempotency and recovery tests (`routes.py:1004-1125`; `tests/test_publish_authorization.py`). No live Store proof. |
| DEP-01 | 0 | Missing | Download/instructions only; no physical transfer/launch/integrity execution. |
| DEP-02 | 2 | Partial | Runtime parity is strong; end-user PRG32-QT import workflow not executed. |
| DEP-03 | 0 | Missing | iOS source/contract unavailable; no handoff execution. |
| SEC-01 | 3 | Implemented/tested | SSRF and sandbox controls have extensive tests; Linux bubblewrap escape suite not rerun here, and threat model retains quota/AppArmor gaps. |
| SEC-02 | 2 | Partial | Has hashed credentials/tokens, throttling, audit log and redaction; lacks hash locks, quotas, retention/deprovisioning and broad rate limits. |
| OPS-01 | 3 | Implemented/tested | CI, Docker, migrations, health and real-build job exist; no independent Docker run, restore drill, metrics/SLO or TLS proof. |
| DOC-01 | 3 | Implemented/tested | Strong ADRs/tutorials/traceability. Named design baseline is absent and some current-state text is stale. |
| QLT-01 | 3 | Implemented/tested | Large negative-test suite and readable code; no lint/type/coverage gate, browser E2E, automated a11y or performance budget. |

## Domain totals

| Domain | Earned / possible | Percent |
|---|---:|---:|
| IDE | 4 / 16 | 25.0% |
| Project | 3 / 4 | 75.0% |
| Build | 5 / 8 | 62.5% |
| WASM | 7 / 8 | 87.5% |
| Debugger | 16 / 24 | 66.7% |
| Accounts | 2 / 8 | 25.0% |
| SSO/RBAC | 6 / 16 | 37.5% |
| Cloud | 0 / 8 | 0.0% |
| Store | 5 / 8 | 62.5% |
| Delivery | 2 / 12 | 16.7% |
| Security | 5 / 8 | 62.5% |
| Operations | 3 / 4 | 75.0% |
| Documentation | 3 / 4 | 75.0% |
| Quality | 3 / 4 | 75.0% |
| **Total** | **64 / 128** | **50.0%** |
