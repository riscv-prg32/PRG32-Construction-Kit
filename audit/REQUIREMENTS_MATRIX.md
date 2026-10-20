# Requirements matrix

Scores: 0 missing, 1 prototype, 2 partial, 3 implemented/tested with an evidence gap, 4 reference-verified.

| ID | Score | State | Audit observation |
|---|---:|---|---|
| IDE-01 | 3 | Implemented/tested | Blockly/C/assembly modes and conversion are covered. |
| IDE-02 | 3 | Implemented/tested | Monaco shell, accessibility and responsive browser flows pass. |
| IDE-03 | 3 | Implemented/tested | Offline C service is validator-derived; no full compiler service. |
| IDE-04 | 3 | Implemented/tested | Offline assembly service is validator-derived; no full assembler service. |
| PRJ-01 | 3 | Implemented/tested | Deterministic project model, revisions and archive/import are covered. |
| BLD-01 | 2 | Partial | Real local toolchain build unavailable during this audit. |
| BLD-02 | 3 | Implemented/tested | Isolation/provenance/diagnostics/debug identity; Linux rerun unavailable. |
| WASM-01 | 4 | Reference-verified | Committed browser core and golden execution tests. |
| WASM-02 | 4 | Reference-verified | Deterministic input/audio/graphics behavior covered. |
| DBG-01 | 4 | Reference-verified | Address debugger and execution controls covered. |
| DBG-02 | 4 | Reference-verified | Breakpoints and compressed stepping covered. |
| DBG-03 | 3 | Implemented/tested | Registers, memory, CSR and stack views; physical target not used. |
| DBG-04 | 3 | Implemented/tested | Accessible debugger browser UI covered. |
| DBG-05 | 4 | Reference-verified | Source/block maps, locals, watches and safe fallback covered. |
| DBG-06 | 4 | Reference-verified | Browser/native state agreement covered. |
| ACC-01 | 4 | Reference-verified | IndexedDB guest projects, migration, capacity, import/export and local-only policy pass browser scenarios. |
| ACC-02 | 4 | Reference-verified | Ownership, atomic conflicts, autosave, quotas, retention and deprovisioning are covered. |
| SSO-01 | 4 | Reference-verified | PKCE and issuer+subject pass signed fake-provider tests and nine live Keycloak scenarios. |
| SSO-02 | 4 | Reference-verified | Multi-IdP, role claims, collision/linking, recovery, deactivation and documented local logout pass live/provider tests. |
| SSO-03 | 4 | Reference-verified | Academic/class RBAC and scoped token denial paths are covered. |
| SSO-04 | 3 | Implemented/tested | Shared Store protocol is identical/unit-tested; no live Store authorization. |
| CLD-01 | 3 | Implemented/tested | Drive provider, least privilege, encrypted tokens and conflicts pass fake/browser tests; no real Google account run. |
| CLD-02 | 3 | Implemented/tested | OneDrive provider, app-folder scope, encrypted tokens and conflicts pass fake/browser tests; no real Microsoft account run. |
| STR-01 | 4 | Reference-verified | Versioned contract and deterministic fixtures pass against CartridgeStore code and a throwaway live Store. |
| STR-02 | 3 | Implemented/tested | Store egress and confirmation boundaries pass 94 tests. |
| DEP-01 | 0 | Missing | Physical PRG32 transfer/launch not verified. |
| DEP-02 | 2 | Partial | Qt runtime parity exists; end-user import workflow not executed. |
| DEP-03 | 0 | Missing | iOS handoff not verified. |
| SEC-01 | 3 | Implemented/tested | SSRF/sandbox boundaries tested; per-build UID/AppArmor/disk limit gaps remain. |
| SEC-02 | 3 | Implemented/tested | Credential, session, secret-reference, quota, retention, audit, throttling and CSP controls covered; supply-chain gaps remain. |
| OPS-01 | 3 | Implemented/tested | Operational configuration and CI evidence; restore drill not executed. |
| DOC-01 | 3 | Implemented/tested | Consistency checks pass; one current-state row still says “this change”. |
| QLT-01 | 3 | Implemented/tested | Large automated suite and required browser CI; quality/performance gates incomplete. |

Domain totals: IDE 12/16; Project 3/4; Build 5/8; WASM 8/8; Debug 22/24; Accounts 8/8; SSO 15/16; Cloud 6/8; Store 7/8; Delivery 2/12; Security 6/8; Operations 3/4; Documentation 3/4; Quality 3/4.

**Total: 103/132 (78.0%).**
