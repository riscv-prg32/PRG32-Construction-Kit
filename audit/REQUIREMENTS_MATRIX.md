# Requirements matrix

Scale: 0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against a reference. All 33 rows apply; denominator = 132. Earlier audit editions miscounted this matrix as 32 rows/128 points.

| ID | Score | Status | Evidence and missing proof |
|---|---:|---|---|
| IDE-01 | 3 | Implemented/tested | Tree, tabs, panels, palette, keyboard regions and phone layout (`templates/ide.html`; `static/js/ide/shell.js`). Five Chrome tests passed, including axe. No screen-reader session; IDE browser suite is omitted from CI. |
| IDE-02 | 2 | Partial | Blockly remains editable and canonical; deterministic generation tested. Block→source/address maps missing. |
| IDE-03 | 2 | Partial | Monaco C editor and line markers work; no completion, hover, navigation or SDK awareness (`static/js/ide/ide.js`). |
| IDE-04 | 2 | Partial | Monaco assembly grammar and exact-line validation work; no instruction/register/ABI completion (`static/js/ide/monaco_setup.js`). |
| PRJ-01 | 3 | Implemented/tested | Versioned model, CRUD, archive, migrations, history and soft delete; no autosave/search/semantic merge. |
| BLD-01 | 2 | Partial | Three real-build paths and CI exist; real local builds skipped for missing toolchain. |
| BLD-02 | 3 | Implemented/tested | Isolated per-build folders, provenance and diagnostics; exact clean rebuild/container not repeated. |
| WASM-01 | 4 | Reference-verified | Pinned PRG32-QT core; native/WASM/headless differential tests. |
| WASM-02 | 4 | Reference-verified | Chrome proved same-origin offline shell, Blockly preview and real-cartridge WASM execution; audio remains approximate. |
| DBG-01 | 4 | Reference-verified | Pause/continue/restart/speed parity tests. |
| DBG-02 | 3 | Implemented/tested | Instruction/over/out/frame tests; no dedicated compressed-instruction fixture. |
| DBG-03 | 3 | Implemented/tested | Persistent address breakpoints; source/block breakpoints absent. |
| DBG-04 | 2 | Partial | Registers, PC, memory and disassembly; no CSR/stack/watch views. |
| DBG-05 | 0 | Missing | DWARF locals/call stack/watches and active Blockly mapping remain open. |
| DBG-06 | 4 | Reference-verified | Browser/native/Qt-core snapshots and framebuffer comparisons. |
| ACC-01 | 0 | Missing | Guest policies and IndexedDB guest projects absent. Offline scratchpad is not policy-complete guest storage. |
| ACC-02 | 2 | Partial | Ownership/history/import/export/account isolation; no quotas, autosave conflicts, retention or deprovisioning. |
| SSO-01 | 1 | Prototype | One OIDC provider, no explicit PKCE, issuer-bound identity or executed IdP matrix. |
| SSO-02 | 1 | Prototype | Environment-only provider; no multi-IdP admin configuration/claim mapping/recovery. |
| SSO-03 | 1 | Prototype | Ordered generic roles, not scoped student/TA/teacher model; publisher boundary works. |
| SSO-04 | 3 | Implemented/tested | Store protocol files identical and unit-tested; no live Store authorization. |
| CLD-01 | 0 | Missing | Google Drive absent. |
| CLD-02 | 0 | Missing | OneDrive/Graph absent. |
| STR-01 | 2 | Partial | Manifest/magic/hash checks; no shared Store schema or live version/visibility conformance. |
| STR-02 | 3 | Implemented/tested | Publisher-only signed review, explicit confirmation, idempotency and egress controls; no live Store proof. |
| DEP-01 | 0 | Missing | No physical-device transfer/launch evidence. |
| DEP-02 | 2 | Partial | Qt runtime parity strong; user import workflow not executed. |
| DEP-03 | 0 | Missing | iOS source/contract and handoff unavailable. |
| SEC-01 | 3 | Implemented/tested | SSRF and build isolation suites; Linux escape suite not repeated and quota/AppArmor gaps remain. |
| SEC-02 | 2 | Partial | Credentials, throttling, audit, CSP and redaction; no hash locks, quotas, retention or broad limits. |
| OPS-01 | 3 | Implemented/tested | CI/Docker/migrations/health; no restore drill, metrics/SLO or TLS proof. IDE E2E omitted from CI command. |
| DOC-01 | 3 | Implemented/tested | Baseline and machine-checked capability table now exist; `docs/architecture/current-state.md:55-60` is stale after phases 1–2. |
| QLT-01 | 3 | Implemented/tested | Large pytest suite and real-browser keyboard/a11y tests; no lint/type/coverage/performance gates, and IDE browser tests are not run by CI. |

## Domain totals

| Domain | Earned / possible | Percent |
|---|---:|---:|
| IDE | 9 / 16 | 56.3% |
| Project | 3 / 4 | 75.0% |
| Build | 5 / 8 | 62.5% |
| WASM | 8 / 8 | 100.0% |
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
| **Total** | **70 / 132** | **53.0%** |
