# Requirements matrix

Scale: 0 missing; 1 prototype/stub; 2 partial; 3 implemented with meaningful tests; 4 implemented, tested and demonstrated against a reference. All 32 rows are applicable; denominator = 128.

| ID | Score | Status | Evidence and missing proof |
|---|---:|---|---|
| IDE-01 | 0 | Missing | Bootstrap page, not IDE shell (`templates/editor.html:63-133`); roadmap explicitly open (`docs/traceability.md:32`). No project tree, command palette, workspace tabs, keyboard audit, or accessibility test. |
| IDE-02 | 2 | Partial | Blockly JSON persists and generators are heavily tested; history exists. Block-to-source/instruction mapping is open (`docs/traceability.md:25-26,49-50`). |
| IDE-03 | 1 | Prototype | C textarea only (`templates/editor.html:72-82`). No Monaco, completion, diagnostics, navigation, or SDK language service. |
| IDE-04 | 1 | Prototype | Assembly textarea and server validator exist; no editor syntax/completion/diagnostics (`templates/editor.html:72-82`). |
| PRJ-01 | 3 | Implemented/tested | Versioned manifest/migrations/archive/history/CRUD tests (`project_format.py:38-47`, project/revision tests). Autosave, search, and robust concurrent merge remain open (`docs/implementation-status.md:54-57`). |
| BLD-01 | 2 | Partial | Code paths and CI cover Blocks/C/assembly real builds; local real-toolchain scenarios skipped (`tests/test_wasm_runtime.py:336-361`). No artifact produced during this audit. |
| BLD-02 | 3 | Implemented/tested | Per-build folders, hashes, provenance and diagnostics (`packager.py:164-260`). Fresh-WASM byte check was environment-blocked; no full clean-container reproduction here. |
| WASM-01 | 4 | Reference-verified | Pinned PRG32-QT core, matching hashes, differential golden tests (`tests/test_wasm_runtime.py:126-152`). Feasible suite passed. |
| WASM-02 | 3 | Implemented/tested | Framebuffer/input/timing/audio/offline tests; audio is approximate and Wi-Fi/multiplayer hosts are open (`docs/traceability.md:41-43`). External CDN shell dependencies undermine full offline start. |
| DBG-01 | 4 | Reference-verified | Pause/resume/stop/restart/speed share core state and differential tests (`tests/test_wasm_runtime.py:155-220`). |
| DBG-02 | 3 | Implemented/tested | Instruction, over/out/frame tests pass (`tests/test_wasm_runtime.py:223-234`). No dedicated compressed-instruction acceptance fixture found. |
| DBG-03 | 3 | Implemented/tested | Address breakpoints persist by cartridge hash (`prg32_runtime.js:48-52,443-452`); no source breakpoint mapping. |
| DBG-04 | 2 | Partial | x0-x31, PC, disassembly and bounded memory exposed. Relevant CSR, explicit stack view, and watches absent. |
| DBG-05 | 0 | Missing | DWARF locals/call stack/watches and active Blockly mapping explicitly open (`docs/implementation-status.md:60-62`). |
| DBG-06 | 4 | Reference-verified | Native/WASM command-by-command state equality and PRG32-QT headless framebuffer comparison (`tests/test_wasm_runtime.py:129-163`). |
| ACC-01 | 0 | Missing | Guest policy and IndexedDB are roadmap-only (`docs/implementation-plan.md:39`; `traceability.md:51`). Pages require sign-in. |
| ACC-02 | 2 | Partial | Owner isolation, revisions, import/export and stale-window refusal tested. No quotas, autosave merge, mature conflict resolution, retention/deprovisioning policy. |
| SSO-01 | 1 | Prototype | Optional Authlib OIDC exists but has no explicit PKCE configuration and links `("oidc", sub)` (`auth_adapters.py:41-81`); provider matrix scenarios were not run. |
| SSO-02 | 1 | Prototype | One environment-configured provider; no admin IdP UI, multiple IdPs, or recovery workflow. Client secret is environment-only. |
| SSO-03 | 1 | Prototype | Generic hierarchy is reader/user/player/publisher/admin (`auth.py:49-55`), not student/TA/teacher scopes. Publisher is not enforced on publish. |
| SSO-04 | 3 | Implemented/tested | Shared protocol file matches local Store exactly and tests exercise tickets/sync. Store authorization contract was not live-tested; local Store is behind one commit. |
| CLD-01 | 0 | Missing | No Google Drive implementation; traceability says open (`docs/traceability.md:56`). |
| CLD-02 | 0 | Missing | No OneDrive/Graph implementation; traceability says open. |
| STR-01 | 2 | Partial | Manifest, SHA-256, source/binary bundle created (`packager.py:211-260`). No independent Store contract validator before upload. |
| STR-02 | 1 | Prototype | POST integration and error response exist, but no publisher gate, draft/update/visibility workflow, recovery state, or explicit confirmation (`publish.js:51-56`). |
| DEP-01 | 0 | Missing | Download button/instructions only; no verified device transfer, launch, or integrity handshake. |
| DEP-02 | 2 | Partial | Portable cartridge and Qt differential execution are strong; user-facing Qt import/delivery workflow was not executed. |
| DEP-03 | 0 | Missing | No PRG32-iOS source/contract or verified handoff. |
| SEC-01 | 2 | Partial | Security docs and many negative tests exist. SSRF and unsandboxed compiler trust boundaries remain; no complete malicious-build/tenant suite. |
| SEC-02 | 2 | Partial | Has hashed tokens/passwords, throttling, secret redaction, and audit log. No dependency lock hashes, retention/deprovisioning, artifact quotas, or broad API/build rate limits. |
| OPS-01 | 3 | Implemented/tested | CI, Docker, migrations, health/discovery and build smoke job exist. Backup/restore, metrics/SLOs and TLS operational proof are incomplete. |
| DOC-01 | 3 | Implemented/tested | Strong ADRs/tutorials/traceability/API docs. Named implementation baseline missing; some status claims exceed this audit's executed evidence. |
| QLT-01 | 3 | Implemented/tested | 346 local passes, clear code, negative tests. No lint/type-check configuration, coverage measurement, automated accessibility/performance/E2E browser suite. |

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
| Store | 3 / 8 | 37.5% |
| Delivery | 2 / 12 | 16.7% |
| Security | 4 / 8 | 50.0% |
| Operations | 3 / 4 | 75.0% |
| Documentation | 3 / 4 | 75.0% |
| Quality | 3 / 4 | 75.0% |
| **Total** | **61 / 128** | **47.7%** |
