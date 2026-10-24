# Claude refinement brief — PRG32-Construction-Kit Full IDE

## Mission

Refine **PRG32-Construction-Kit** from its current classroom construction-kit foundation into the Full IDE described by the quality audit, without weakening its deterministic generation, educational transparency, security boundaries, or compatibility with PRG32, PRG32-QT, and CartridgeStore.

Work from the repository's actual source and tests. Do not treat roadmaps, implementation summaries, screenshots, or CI configuration as proof that a feature works. Preserve the phrase **PRG32 cartridge** for `.prg32` artifacts.

## Starting point

The independent audit was performed on:

- PRG32-Construction-Kit `development`: `6b7aac93554bcdbbeeb0c7b80fcad576b1a9bea6`
- PRG32 `main`: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT `main`: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore `main`: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`

Audit result: **NO-GO for a Full IDE release**, scoring **64/128 (50.0%)**. Read these files before changing code:

1. `AGENTS.md`
2. `audit/EXECUTIVE_SUMMARY.md`
3. `audit/REQUIREMENTS_MATRIX.md`
4. `audit/FINDINGS.md`
5. `audit/TEST_REPORT.md`
6. `audit/ARCHITECTURE_REVIEW.md`
7. `audit/SECURITY_REVIEW.md`
8. `audit/REMEDIATION_PLAN.md`
9. `audit/EVIDENCE_INDEX.md`
10. Committed ADRs and `docs/traceability.md`

The earlier Store SSRF, publisher-authorization, explicit-confirmation, and unsandboxed-production-build findings are addressed. Preserve their protections and regression tests.

## Non-negotiable constraints

- Keep Blockly JSON canonical for Blocks projects.
- Keep generated C and generated RISC-V assembly visible and understandable to students.
- Keep generation deterministic from saved Blocks JSON and project metadata.
- Never compile arbitrary unvalidated LLM-generated C.
- Generate assembly only from validated game IR, except validated handwritten assembly projects governed by ADR-0004.
- Keep C and assembly source validation strict. Do not weaken directive, include, file-reading, expression, or entry-point checks.
- Preserve production build isolation: bubblewrap, no network, read-only toolchain/SDK, cleared environment, seccomp, resource limits, per-build folders, and refusal when the required sandbox is unavailable.
- Preserve publisher-only authorization, publishable-bundle validation, immutable signed review, explicit confirmation, idempotency, Store-origin policy, DNS/IP checks, address pinning, TLS verification, redirect refusal, response limits, and secret redaction.
- Preserve ownership and shared-read-only semantics, account-switch refusal, signed-in route protection, token/password hashing, and `sso_protocol.py` identity with CartridgeStore.
- Continue using Bootstrap, jQuery, Blockly, pytest, and the current Flask architecture unless a new accepted ADR explicitly changes one.
- Do not silently modify student projects. AI functionality may propose changes or explain errors only.
- Do not claim hardware, iOS, IdP, cloud-provider, Store, accessibility, performance, offline, or browser validation unless it was actually executed and recorded.

## Required refinement sequence

Implement this as reviewable PR-sized phases. Do not combine unrelated phases merely to increase the apparent completion score.

### Phase 0 — Baseline and documentation integrity

1. Re-run the feasible test suite and record exact pass/fail/skip counts.
2. Update `docs/architecture/current-state.md`, which contains stale commit and capability statements.
3. Locate and commit `CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md`, or document through an ADR that it has been superseded.
4. Add a machine-checkable capability/status table whose evidence links point to source symbols and tests.
5. Do not change audit scores merely because work is planned.

Acceptance:

- Documentation describes the current source accurately.
- Every “implemented” status names at least one source symbol and one meaningful test.
- `git diff --check`, syntax checks, and the existing pytest suite pass subject only to documented environment skips.

### Phase 1 — Self-contained offline frontend

Vendor and pin Bootstrap, Bootstrap Icons, jQuery, Blockly, and later Monaco. Remove runtime dependence on public CDNs. Record versions, licenses, hashes, and provenance. Add a Content Security Policy compatible with the application. Update the service-worker cache version and static-only cache list.

Acceptance:

- Cold and warm offline starts work after installation without third-party requests.
- Signed-in pages and API responses are never cached.
- Blockly remains editable offline.
- CSP and dependency-provenance tests pass.
- Cached static changes bump the cache version.

### Phase 2 — IDE shell and Monaco

Build a responsive, keyboard-operable shell with:

- project/file tree;
- editor tabs;
- reusable panels for output, diagnostics, generated code, IR and debugger;
- command palette;
- clear focus model and shortcuts;
- small-screen fallback;
- Monaco editing for C and RISC-V assembly;
- Blockly retained as the editable Blocks surface.

Use readable jQuery wiring rather than introducing a second application framework. Generated source panels must remain inspectable and copyable.

Acceptance:

- IDE-01, IDE-03 and IDE-04 have browser E2E tests.
- Full workflow is usable using only the keyboard.
- Automated accessibility checks have no serious or critical violations.
- Existing Blockly, source-mode, conversion, packaging and history tests remain passing.

### Phase 3 — Deterministic language intelligence

Add offline, deterministic C and RV32IM/RV32IMC language support:

- syntax highlighting;
- ABI-aware completion;
- register, instruction and directive completion for assembly;
- source validation diagnostics mapped to exact editor ranges;
- navigation to permitted SDK declarations;
- actionable compiler diagnostics without exposing host paths;
- explainable diagnostic text appropriate for students.

Generate indexes from pinned PRG32 SDK inputs where practical. Do not enable arbitrary host filesystem access or a general untrusted language server.

Acceptance:

- Fixture-based tests assert exact completion and diagnostic output.
- Unknown or forbidden APIs/directives remain rejected.
- Results work offline and are deterministic.
- No server path, token or secret appears in diagnostics.

### Phase 4 — Source and block debugging

Add a debug build profile and deterministic mappings:

`Blockly block id -> validated IR node -> generated C/assembly line -> guest address/DWARF location`

Implement:

- C source and address breakpoints;
- active Blockly block highlighting;
- locals and globals;
- call stack;
- watches;
- relevant CSR and explicit stack views;
- graceful address-only fallback when debug information is unavailable;
- a dedicated compressed-instruction stepping fixture.

Do not change normal-build output or semantics merely to support debugging. The browser must continue using the PRG32-QT-derived execution core.

Acceptance:

- Mandatory debugger scenario D passes.
- Browser and native/PRG32-QT snapshots agree at fixed checkpoints.
- Pause, instrumentation and debug builds do not alter deterministic program results.
- Generated block/source maps are deterministic artifacts with tests.

### Phase 5 — Academic identity and scoped RBAC

Implement accepted identity decisions through an ADR before schema changes:

- Authorization Code with PKCE S256;
- state, nonce, issuer, audience, signature and expiry validation;
- JWKS rotation;
- identity keyed by issuer plus subject;
- multiple providers;
- administrator configuration and safe bootstrap/recovery;
- claim/group mapping;
- disabled-user and group-change lifecycle;
- scoped student, TA, teacher, publisher and administrator capabilities;
- logout behavior and MFA delegation to the provider;
- no reuse of Store tokens as IDE sessions.

Keep CartridgeStore compatibility explicit. Coordinate shared protocol or role-contract changes across both repositories.

Acceptance:

- Full mandatory scenario E passes against fixtures and approved test tenants.
- Cross-issuer subject collisions cannot merge accounts.
- Students cannot self-escalate or publish without scope.
- Lockout recovery is tested without a default production password.

### Phase 6 — Guest and registered storage policy

Implement administrator-selectable guest policies and IndexedDB project storage. Guests must be able to export before eviction and must not persist projects on the server. For registered users add:

- storage quotas;
- autosave with explicit version/conflict semantics;
- revision retention;
- deprovisioning behavior;
- concurrent-edit detection and recovery;
- migrations from existing saved projects.

Acceptance:

- Mandatory scenarios A and B pass for each guest policy.
- Tests prove no unintended guest server persistence.
- Account switching cannot expose another user's browser or server data.
- Quota, eviction, conflict, migration and rollback tests pass.

### Phase 7 — Shared Store and cartridge contracts

Replace incompatible duplicated constants with versioned generated/shared schemas or conformance fixtures agreed across PRG32 and CartridgeStore. Validate:

- cartridge header/version/ABI/hash;
- architecture and ISA flags;
- portable ABI imports;
- bundle manifest and asset hashes;
- duplicate/version conflicts;
- pending review, update and visibility behavior;
- interrupted upload and retry semantics.

Acceptance:

- Stale or mismatched ABI artifacts are rejected.
- Bundle behavior matches the inspected CartridgeStore source and a controlled integration environment.
- No live public artifact is published without explicit human authorization.

### Phase 8 — Google Drive and OneDrive

Only begin cloud integration after identity, storage versioning and conflict semantics stabilize. Use provider-neutral interfaces with minimum OAuth scopes. Implement refresh, revocation, disconnect, network loss and conflict recovery. Never place provider tokens in logs or project exports.

Acceptance:

- Mandatory scenario B cloud cases pass in approved provider sandboxes.
- Token expiry/revocation and concurrent conflicts preserve recoverable local work.
- Disconnect removes or invalidates stored credentials as documented.

### Phase 9 — Delivery and release evidence

Verify and document:

- physical PRG32 transfer and launch with artifact integrity checks;
- PRG32-QT import/delivery;
- actual PRG32-iOS import contract and handoff, without inventing URL schemes or APIs;
- backup and restore;
- TLS/reverse-proxy configuration;
- metrics/logging without secrets;
- SBOM, licenses and dependency vulnerability review;
- browser memory, build latency and performance budgets.

Acceptance:

- Mandatory scenarios C and G pass.
- Device, Qt and iOS evidence records exact versions, hashes and outcomes.
- Tests that require unavailable hardware/toolchains skip cleanly and never masquerade as passes.

## Required tests on every phase

At minimum run and report:

```text
python3 -m compileall -q app.py prg32_construction_kit tests tools
for file in static/js/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done
python3 -m pytest -q -rs
git diff --check
```

Also run the phase-specific browser, WASM, sandbox, real-cartridge, Store, identity or cloud suites. For the WASM core, record the PRG32-QT revision and Emscripten version. For real cartridge builds, inspect the actual header, ABI hash, architecture, payload and provenance rather than accepting a `.prg32` filename as proof.

## Evidence and reporting format

For every phase, report:

1. exact repository branch and HEAD;
2. files and symbols changed;
3. migrations and backward-compatibility impact;
4. security/trust-boundary impact;
5. exact commands and pass/fail/skip counts;
6. artifacts, screenshots or logs produced;
7. requirements moved between missing, partial, implemented or reference-verified;
8. remaining blockers and environmental limitations;
9. rollback approach;
10. documentation updated for teachers and students.

Use `path:line` references. Distinguish source inspection from executed validation. Do not mark a matrix row 4 unless it was demonstrated against the relevant reference implementation or external system.

## Definition of Full IDE release readiness

A Full IDE release is ready only when:

- IDE-01 through IDE-04 are functional and tested;
- all three source modes build real ABI-compatible PRG32 cartridges;
- browser execution uses the pinned PRG32-QT-derived core;
- mandatory debugger scenario D passes, including source/block state;
- guest and registered storage policies pass isolation/conflict tests;
- academic OIDC/RBAC negative tests pass;
- Store publishing matches the real contract and remains explicitly confirmed;
- Drive and OneDrive requirements are either implemented and verified or removed from the approved release scope through a documented decision;
- hardware, Qt and iOS claims are backed by actual evidence;
- no critical release-gate security defect is open;
- audit documents, traceability and user/teacher documentation match the shipped behavior.

Until then, describe the product accurately as the implemented PRG32 classroom construction kit and identify incomplete Full IDE features explicitly.
