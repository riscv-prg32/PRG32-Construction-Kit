# Claude implementation brief — PRG32 Construction Kit Full IDE

**Purpose:** Execute a staged, test-driven implementation that turns PRG32 Construction Kit into a self-contained, browser-first educational IDE. This is an implementation instruction, not a claim that functionality exists.

**Primary repositories (inspect current branches and source before editing):**
- https://github.com/riscv-prg32/PRG32-Construction-Kit — primary application; preserve existing Blockly, tutorials, simulator, C generation and bundle workflows.
- https://github.com/riscv-prg32/PRG32 — authoritative SDK, portable cartridge ABI, format, toolchain, hardware and tests.
- https://github.com/riscv-prg32/PRG32-QT — reference portable guest execution core, debug capabilities, host adapters and conformance.
- https://github.com/riscv-prg32/CartridgeStore — authoritative store API, authentication, publication and bundle conventions.
- Identify the actual PRG32-iOS repository and capabilities before designing an iOS adapter. Never invent an API.

## Instructions to Claude

1. Clone/read all repositories, identify branch/commit SHAs, read `AGENTS.md`, README, API specs, CI, licensing, and tests. Produce `docs/architecture/current-state.md` with a **verified capability matrix** (implemented / partial / absent / unknown), actual APIs, cross-repo dependencies, and risks. Do not rely on this note as proof of existing APIs.
2. Produce an ADR set and phased implementation plan with file-level tasks and dependency ordering; then implement incrementally, committing logical slices. Prefer backward-compatible changes and shared upstream components to forks. Do not rewrite the Flask backend wholesale without evidence.
3. Run existing tests first, add focused regression tests, and run relevant tests after every phase. Record exact commands, outcomes, blocked tests and environmental limitations. No fake passing results, mock-only proof of native compatibility, or claims of hardware validation without hardware.
4. Maintain `docs/implementation-status.md`, `docs/traceability.md`, `docs/compatibility.md`, `docs/security.md`, `docs/deployment.md`, `docs/user-guide.md`, `docs/admin-guide.md`, and migration/release notes. Every requirement below needs evidence and a test reference.
5. Ask for credentials, physical devices, signing keys, institutional IdP access, or publication approval when required. Never store secrets in git, auto-publish, or perform external deployment without authorization.

## Target architecture

- **Unified project model:** versioned `prg32.project.json` with schema version, authoring mode (`blocks`, `assembly`, `c`), entry points, assets, tests, SDK/ABI requirements, targets, metadata and build profiles. Support create/open/rename/duplicate/delete, file tree, templates, import/export as a portable archive, snapshots/history, autosave, search, and deterministic project migrations. The canonical source stays in its chosen mode; generated C/Assembly is derived and must never silently overwrite Blockly source. Add source maps from blocks to generated code and machine instructions where feasible.
- **JetBrains-inspired IDE shell:** responsive multi-pane interface with project explorer, tabs, Monaco for C and RISC-V Assembly, Blockly editor, run/debug toolbar, inspector, terminal/build output, problems, search, asset browser, store/publish, device targets, status bar, command palette, shortcuts, layout persistence, accessibility and small-screen fallback. Integrate syntax highlighting, semantic completion, hover/help, go-to-definition, diagnostics, formatting, symbols and SDK/ABI-aware suggestions. Use a documented LSP/worker strategy and test degraded/offline modes.
- **One build pipeline:** Blocks -> validated IR -> generated C or Assembly; handwritten C/Assembly -> compiler/assembler/linker; all modes -> **real portable `.prg32`** artifact using the authoritative PRG32 SDK/ABI. Validate RV32IMAC and compressed-instruction semantics, relocations/imports, ABI hash/version, asset sizes, memory layout, linker behavior and reproducibility. Separate debug/release builds, record toolchain provenance and hashes. Never replace native guest execution with a superficially similar JS game implementation.
- **Browser toolchain:** aim for offline-capable, browser-local WebAssembly compilation/linking of C and Assembly. Feasibility spike must measure actual LLVM/Clang/binutils/RISC-V target availability, WASM bundle size, caching, memory, startup time and browser constraints. A clearly marked sandboxed server-build fallback is allowed during rollout; ensure quotas, resource limits, no arbitrary host execution, isolation and abuse controls. PWA/service-worker caching should enable a documented offline subset.
- **Browser runtime:** port or reuse the **Qt-free PRG32-QT guest core** as WebAssembly; host adapters for framebuffer (320x200 indexed where applicable), sprites, palettes, audio, input, timing, storage and service calls. The RISC-V guest remains interpreted/emulated inside WASM; WebAssembly is not a direct RV32 execution target. Match PRG32-QT and PRG32 ABI behavior via golden cartridges and differential tests. Handle deterministic test clocks and input playback without changing guest semantics.

## Debugger — mandatory parity with PRG32-QT

Implement a shared debug protocol/adapter, preferring reusable additions to the Qt-free core over browser-only semantics. **First inspect what PRG32-QT actually implements** and document parity gaps. Required controls:

- Play/continue, pause, stop/restart, **execution-speed adjustment** (instruction budget/throttling; distinguish guest time from wall time), slow educational mode, full speed.
- Step one guest instruction, step into, step over, step out; correct RV32IMAC 16/32-bit instruction boundaries, call/return semantics and breakpoint behavior.
- Set/clear/enable/disable persistent instruction-address and source breakpoints; hit counts/conditional breakpoints if feasible; correct behavior on continue and after reload.
- Inspect all x0–x31 registers, aliases, PC, supported CSRs, guest memory, stack and disassembly; changed-value highlighting, multiple numeric formats, watches.
- Inspect C locals/globals and call stacks using DWARF/debug symbols where available, with explicit graceful degradation for optimized/stripped builds. Inspect Blockly variables and highlight active blocks via generated source/IR maps.
- Structured events for running/paused/breakpoint/exception/terminated, inspectable trace and deterministic replay fixtures. Beginner UI (blocks, variables, play/pause/step/speed) and advanced UI (registers, memory, disassembly, call stack, watches) share one execution state.
- Build differential tests comparing browser and PRG32-QT on identical cartridges and scripted input: register/PC/memory state after N steps, pause/continue, breakpoint hits, frame hashes and relevant ABI calls. Record unsupported Qt features explicitly until closed.

## Accounts, projects and cloud storage

- Admin-selectable guest policy: (A) login required; (B) guest local create/edit/build/run/debug/download; (C) optional temporary server storage with TTL/quota. Guests use IndexedDB with clear export/backup guidance, storage eviction handling, no implicit server persistence and upgrade-to-account flow.
- Registered users: private server projects, revision history, quotas, ownership/sharing policy, soft delete/recovery, conflict handling, and migration. Use transactional metadata database (e.g. PostgreSQL) and object storage as justified; provide migrations from current storage and deployment defaults.
- Optional Google Drive and OneDrive project import/export/sync via OAuth authorization, Google Drive API and Microsoft Graph. Minimize scopes, keep tokens server-side or use secure platform flows, rotate/revoke credentials, implement ETag/version conflict detection, explicit sync status, retry/backoff, deletion handling and tests. Distinguish cloud project sync from login identity.

## Academic SSO, security and RBAC

- Follow **actual CartridgeStore authentication conventions** where compatible. Support admin-configurable OIDC (Authorization Code + PKCE, state, nonce, discovery/JWKS, issuer/audience validation), multiple institutional IdPs, Google Workspace and Microsoft Entra ID via OIDC, optional local accounts and guest policy. SAML 2.0 / LDAP / AD may be integrated via an identity broker such as Keycloak; do not call plain OAuth2 an authentication protocol.
- Admin UI: provider enablement, discovery/issuer, client ID, secure secret reference, scopes, redirect URIs, allowed domains, claim/group mapping, auto-provisioning, session/MFA policies, test connection, audit and emergency admin access. Never expose client secrets to browser or logs. Support safe bootstrap and rollback if SSO is misconfigured.
- RBAC roles: guest, student, teaching assistant, teacher, publisher, administrator; institution/course/project scoping; least privilege; never grant admin/publisher solely from email domain. Link accounts by immutable issuer+subject. Explicit authorization for publishing and store actions; no session-cookie sharing between apps. Store OAuth tokens must be audience/scope-correct.
- Threat model for untrusted source/builds, uploads, WASM runtime, plugins, OAuth, SSRF, CSRF, XSS, tenant isolation, IDOR, secret storage, token replay, publishing, rate limiting and resource exhaustion. Add audit logging, retention/deprovisioning and privacy/GDPR documentation.

## Build, test, publish and deploy

- Tests: unit, integration, E2E, guest ISA/ABI conformance, browser-vs-Qt differential, offline PWA, accessibility, authentication/RBAC, cloud conflict, packaging, security and CI matrix. Provide sample fixtures for Pong/Breakout/etc. and for handcrafted C/Assembly/Blocks programs. Tests must exercise real `.prg32` output.
- Store: discover CartridgeStore's current bundle manifest/API/auth flows. Add preparation wizard, metadata/assets/screenshots, license/visibility/version validation, artifact checksum, preview, authenticated draft upload, explicit publish confirmation, update/status/error handling and idempotency. No invented endpoints; don't publish automatically.
- Physical PRG32: implement capability detection and compatibility checks; choose verified supported WebSerial/WebUSB/local bridge/SD transfer workflow; checksum verification, launch and meaningful errors. Require user permission and avoid firmware flashing unless separately approved.
- PRG32-QT: documented cartridge import, local companion or supported deep-link protocol based on actual Qt host capability; avoid assuming browser can directly control a local process.
- PRG32-iOS: verify actual app interfaces; provide file/share-sheet or supported handoff; document iOS sandbox/browser constraints and do not promise remote installation without a receiver.
- Deployment: local developer setup, Docker/Compose production baseline, config examples, reverse proxy/TLS, IdP setup, database migrations, object storage, backup/restore, quotas, observability, supply-chain controls and CI release artifacts.

## Suggested implementation gates

**G0 Discovery:** verified repo/ABI/API matrix, baseline tests, ADRs, dependency map, acceptance traceability.

**G1 Foundation:** project schema and migration, portable archive, storage abstraction, guest policies, regression tests.

**G2 IDE:** editor shell, Blockly/Monaco, C and Assembly language services, diagnostics, templates, accessibility.

**G3 Toolchain:** real browser/server-fallback C+Assembly+Blocks build, reproducible `.prg32`, ABI checks.

**G4 WASM:** Qt-free guest core compiled to WASM, browser host adapters, golden-cartridge tests.

**G5 Debugger:** speed/pause/step/registers/variables/breakpoints, source maps/DWARF, Qt parity evidence.

**G6 Identity/storage:** registered projects, guest controls, OIDC/broker SSO, roles, Drive/OneDrive, security tests.

**G7 Delivery:** CartridgeStore bundle/publish, physical, Qt and iOS verified adapters.

**G8 Release:** security/performance/accessibility audits, documentation, reproducible deployment and CI.

At each gate deliver: changed files, migrations, user/admin docs, automated tests, results, screenshots where useful, known gaps, risks and rollback instructions. **Do not mark a gate complete unless its acceptance tests actually pass.**

## Definition of done

For each mode (Blocks, C, Assembly), a user can create, edit with appropriate assistance, build a genuine cartridge, run and debug it in-browser, inspect state and export the project. Registered users can persist/sync projects; guest access follows admin policy. Authorized users can prepare/publish Store bundles and deploy to verified targets. Cross-runtime compatibility and SSO/RBAC are evidenced by tests, not assumptions. CI, security, documentation and deployment are reproducible. If a capability depends on absent upstream APIs or hardware, record it as blocked with an explicit interface proposal and test plan rather than claiming completion.
