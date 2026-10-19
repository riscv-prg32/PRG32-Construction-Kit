# Requirements matrix

Scale: 0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against a reference. All 33 rows apply; denominator = 132.

| ID | Score | Status | Evidence and missing proof |
|---|---:|---|---|
| IDE-01 | 3 | Implemented/tested | Shell, tree, tabs, panels, palette, keyboard/mobile/a11y; required Chrome CI now includes all browser suites. No real screen-reader session. |
| IDE-02 | 3 | Implemented/tested | Blockly remains canonical/editable; deterministic block→IR→C/assembly→address maps and active block demonstrated. |
| IDE-03 | 3 | Implemented/tested | Offline C completion, hover, signatures, F12, portable ABI filtering and exact diagnostics; deliberately not a full C semantic engine. |
| IDE-04 | 3 | Implemented/tested | Offline RV32IMC/register/ABI/directive completion, hover/navigation and exact diagnostics; no external language-server reference. |
| PRJ-01 | 3 | Implemented/tested | Versioned CRUD/archive/migrations/history; autosave/search/conflict merge absent. |
| BLD-01 | 2 | Partial | Three real-build paths exist; local toolchain absent in this audit. |
| BLD-02 | 3 | Implemented/tested | Isolation/provenance/diagnostics/debug-image identity; container/exact rebuild not rerun. |
| WASM-01 | 4 | Reference-verified | Pinned PRG32-QT core and native/WASM/headless differential tests. |
| WASM-02 | 4 | Reference-verified | Chrome demonstrated offline real-cartridge runtime; audio approximate. |
| DBG-01 | 4 | Reference-verified | Pause/continue/restart/speed parity. |
| DBG-02 | 4 | Reference-verified | Instruction/over/out/frame plus committed 16/32-bit compressed fixture agree natively and in WASM. |
| DBG-03 | 3 | Implemented/tested | Address/source/block/conditional breakpoints and hit behavior; persistence/enabling coverage is stronger for address breakpoints than source conditions. |
| DBG-04 | 3 | Implemented/tested | Registers, PC, memory, disassembly, counter CSRs, explicit stack and watches; CSR scope intentionally limited. |
| DBG-05 | 4 | Reference-verified | Real-toolchain DWARF fixtures, locals/globals/call stack/watches, block variables/active mapping, Chrome scenario D and graceful fallback. |
| DBG-06 | 4 | Reference-verified | Browser/native/Qt-core snapshots, framebuffer and source checkpoints agree. |
| ACC-01 | 0 | Missing | Guest policies and IndexedDB guest projects absent. |
| ACC-02 | 2 | Partial | Ownership/history/import/export/isolation; quotas/autosave/conflicts/retention absent. |
| SSO-01 | 1 | Prototype | One OIDC provider; no explicit PKCE, issuer+subject identity or live IdP matrix. |
| SSO-02 | 1 | Prototype | No multi-IdP admin configuration, claims lifecycle or recovery workflow. |
| SSO-03 | 1 | Prototype | Generic ordinal roles, not scoped academic RBAC; publisher boundary works. |
| SSO-04 | 3 | Implemented/tested | Shared Store protocol identical/unit-tested; no live Store authorization. |
| CLD-01 | 0 | Missing | Google Drive absent. |
| CLD-02 | 0 | Missing | OneDrive/Graph absent. |
| STR-01 | 2 | Partial | Local manifest/magic/hash validation; no shared schema or live conformance. |
| STR-02 | 3 | Implemented/tested | Authorized signed review/confirm/idempotency/egress; no live Store proof. |
| DEP-01 | 0 | Missing | No physical-device transfer/launch evidence. |
| DEP-02 | 2 | Partial | Qt runtime parity; end-user import workflow unexecuted. |
| DEP-03 | 0 | Missing | iOS source/contract and handoff unavailable. |
| SEC-01 | 3 | Implemented/tested | SSRF, sandbox and debug-artifact boundaries tested; Linux escape rerun and quotas remain gaps. |
| SEC-02 | 2 | Partial | Credentials, throttling, audit, CSP and redaction; no hash locks, quotas, retention or broad limits. |
| OPS-01 | 3 | Implemented/tested | CI enforces browser suites without skips; Docker/migrations/health exist. No restore drill, metrics/SLO or TLS proof. |
| DOC-01 | 3 | Implemented/tested | Machine-checked capability/status consistency and ADRs; current SHA wording still trails the audited HEAD. |
| QLT-01 | 3 | Implemented/tested | Large backend/browser/a11y/differential suites; no lint/type/coverage/performance gates or screen-reader session. |

## Domain totals

| Domain | Earned / possible | Percent |
|---|---:|---:|
| IDE | 12 / 16 | 75.0% |
| Project | 3 / 4 | 75.0% |
| Build | 5 / 8 | 62.5% |
| WASM | 8 / 8 | 100.0% |
| Debugger | 22 / 24 | 91.7% |
| Accounts | 2 / 8 | 25.0% |
| SSO/RBAC | 6 / 16 | 37.5% |
| Cloud | 0 / 8 | 0.0% |
| Store | 5 / 8 | 62.5% |
| Delivery | 2 / 12 | 16.7% |
| Security | 5 / 8 | 62.5% |
| Operations | 3 / 4 | 75.0% |
| Documentation | 3 / 4 | 75.0% |
| Quality | 3 / 4 | 75.0% |
| **Total** | **79 / 132** | **59.8%** |
