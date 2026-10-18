# Claude remediation brief — PRG32-Construction-Kit

Use this document as the implementation prompt for improving the issues found by the independent quality audit.

## Role and objective

Act as a senior Python/JavaScript engineer and security-focused maintainer. Improve PRG32-Construction-Kit incrementally until the audit blockers are resolved, while preserving its educational purpose and existing compatibility.

Work from the actual repository state and tests. Do not trust summaries without inspecting source. Do not claim hardware, iOS, browser, OAuth-provider, Cartridge Store, or toolchain validation unless you actually execute it and retain evidence.

The audit baseline is:

- Construction Kit reassessment: branch `development`, commit `2ea8616f04e1b134d23e786acba2e536e6eef1e7`
- Original audit baseline: `7c2202c1554f7c7b2e04189f33b67e8bb88d14b4`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: local commit `820f74bfe9364c8727db92cb0f15f3b9dd85feab`; verify against its current upstream before changing shared contracts
- Audit recommendation: **NO-GO for the advertised Full IDE release**
- Audit score: **61/128 (47.7%)**

Read these files before modifying code:

1. `AGENTS.md`
2. `audit/EXECUTIVE_SUMMARY.md`
3. `audit/FINDINGS.md`
4. `audit/REQUIREMENTS_MATRIX.md`
5. `audit/SECURITY_REVIEW.md`
6. `audit/ARCHITECTURE_REVIEW.md`
7. `audit/TEST_REPORT.md`
8. `audit/EVIDENCE_INDEX.md`
9. `docs/adr/README.md` and all ADRs relevant to the current remediation phase
10. The matching PRG32, PRG32-QT, and CartridgeStore source when changing shared ABI/API behavior

## Non-negotiable repository constraints

- Preserve the application name **PRG32-Construction-Kit** and the phrase **PRG32 cartridge** for `.prg32` files.
- Keep Blockly JSON as the canonical Blocks source in `projects.blocks_json`.
- Preserve the deterministic pipeline: Blockly JSON → validated game IR → deterministic C/assembly → PRG32 toolchain.
- Generated C and assembly are teaching material. Keep them visible, deterministic, readable, and extensively commented.
- Generated assembly must continue to match generated C behavior. Keep `tests/test_asm_generator.py` passing.
- Handwritten assembly must remain separate from generated assembly and must pass `validate_asm_source` before assembly. Do not weaken its directive allow-list without a security test proving the added directive cannot read host files.
- Do not compile arbitrary unvalidated LLM-supplied C.
- Preserve all documented CRUD/action routes unless a documented migration is added.
- Preserve owner isolation, shared read-only records, `X-PRG32-Kit`, `X-PRG32-User`, and the `409 user_changed` behavior.
- Keep `prg32_construction_kit/sso_protocol.py` identical to the corresponding CartridgeStore file.
- Use Bootstrap, jQuery and Blockly. Monaco may be added as the code editor, but it must not replace the required application framework.
- The service worker must cache static files only, never authenticated pages or API responses. Bump its cache version whenever cached assets change.
- Every build must remain inside its unique `<build_id>/` directory with a private `tmp/`.
- Do not store plain-text passwords or expose bearer tokens, host paths, session secrets, or build secrets.
- Add or update pytest coverage for every behavior change. Tests requiring unavailable external toolchains must skip clearly.
- Do not publish public artifacts, change live infrastructure, rotate credentials, or flash hardware without explicit approval.

## Required working method

Implement the work as small, independently reviewable PRs. Complete and verify one phase before starting the next. Do not combine the first three security phases.

For every phase:

1. Inspect the current code and upstream contract.
2. Record the design decision in an ADR when it changes security, persistence, public API, ABI, or deployment architecture.
3. Write failing tests that reproduce the issue.
4. Implement the smallest complete fix.
5. Run syntax checks, focused tests, and the full feasible suite.
6. Update teacher/student documentation and traceability.
7. Report exact commands, pass/fail/skip counts, paths changed, limitations, and remaining risks.

Do not silently downgrade a requirement or relabel missing behavior as complete. Use these statuses: implemented and verified, implemented but unverified, partial, missing, blocked, or not applicable with justification.

## Phase 1 — Block authenticated SSRF in Store publishing — completed and verified

### Existing problem

Any signed-in user can create a publish profile with an arbitrary `store_url`. `prg32_construction_kit/publisher.py:10-16` then makes a server-side POST to that origin. There is no approved-host policy, HTTPS requirement, private-network rejection, redirect validation, or response-size limit.

### Required implementation

Implemented at `2ea8616` through ADR-0008, `store_policy.py`, the pinned-address transport in `publisher.py`, route-level validation and 94 passing adversarial tests. Preserve these controls and rerun the suite after any publishing/configuration change.

- Make Store origins administrator-controlled or constrained by an explicit administrator allow-list.
- Require HTTPS in production. Permit loopback HTTP only through an explicit development/test configuration.
- Reject URL credentials, fragments, malformed ports, unsupported schemes, and ambiguous hostnames.
- Resolve the hostname and reject loopback, link-local, multicast, unspecified, reserved, and private addresses for both IPv4 and IPv6 unless explicitly configured as a trusted local deployment.
- Defend against DNS rebinding by validating resolved addresses at connection time as far as the HTTP library permits.
- Disable redirects or revalidate every redirect target with the same policy.
- Bound connection/read timeout and response size.
- Return student-safe errors without leaking internal addresses or response bodies.
- Audit allowed and refused attempts without recording tokens.

### Acceptance tests

- Reject `localhost`, `127.0.0.1`, IPv6 loopback, RFC1918, link-local, integer/hex IP spellings, URL credentials, `file:`, and redirect-to-private targets.
- Reject an initially public hostname whose resolved destination violates policy.
- Accept the configured HTTPS Store origin.
- Confirm bearer tokens never appear in response bodies, logs, exceptions, or audit events.
- Preserve the supported local-development workflow behind explicit configuration.

## Phase 2 — Enforce publishing authorization and confirmation

### Existing problem

`POST /api/publish` does not require the `publisher` role. The UI publishes on one click and the backend accepts `source_bundle` artifacts as well as publishable Store bundles.

### Required implementation

- Enforce `publisher` or `admin` authorization in the backend. UI visibility is not an authorization control.
- Define and document the exact publisher permission shared with CartridgeStore.
- Reject source-only/non-publishable bundles regardless of client input.
- Add a server-generated review summary containing Store origin, cartridge identity, version, architectures, visibility, file sizes and SHA-256 values.
- Require explicit confirmation tied to that immutable summary. Prevent a bundle/profile swap between review and confirmation.
- Support draft/upload/publish/update states and recoverable errors where supported by the actual Store contract.
- Add an idempotency strategy for retries.
- Never perform a live public publication in automated tests.

### Acceptance tests

- `reader`, `user` and `player` receive 403 from the backend.
- `publisher` and `admin` can proceed only through review and explicit confirmation.
- Source-only bundles, missing cartridges, changed artifacts, mismatched hashes and stale confirmation tokens are rejected.
- Duplicate versions, unauthorized Store responses, timeouts and retried uploads produce clear recoverable states.
- Audit events distinguish review, refusal, attempted upload, success and failure without secrets.

## Phase 3 — Isolate untrusted cartridge builds

### Existing problem

The validators reduce source risk, and builds have time/concurrency limits, but the compiler subprocess runs under the web-service OS identity with inherited filesystem and network access. `validate_c_source` and `validate_asm_source` explicitly are not sandboxes.

### Required implementation

- Execute every compiler invocation in a disposable isolation boundary suitable for production: container, namespace sandbox, or dedicated build worker.
- Run as a non-root per-build identity.
- Mount only the build directory writable and the necessary SDK/toolchain read-only.
- Disable network access.
- Apply CPU, wall-clock, RAM, process-count, file-count and disk-size limits.
- Use a restrictive syscall policy such as seccomp/AppArmor where supported.
- Kill the whole build process group on timeout or cancellation.
- Pass a minimal allow-listed environment instead of `os.environ.copy()`.
- Keep build logs useful while redacting host paths and secrets.
- Preserve unique build folders, build slots, deterministic outputs and clean toolchain-missing skips.

### Acceptance tests

- Normal Blocks, Advanced C, generated assembly and handwritten assembly builds produce valid PRG32 cartridges.
- Attempts to read host files, use the network, fork excessively, consume excessive RAM/disk/CPU, create device nodes, or escape the build directory fail safely.
- Concurrent builds cannot observe or overwrite one another.
- A timeout leaves no child process running.
- Artifact hashes and provenance still record the actual compiler/SDK inputs.

## Phase 4 — Share and validate Store/cartridge contracts

- Compare exact cartridge headers, ABI versions/hashes, manifest schema, bundle paths, publish endpoints, permissions and error codes with current PRG32 and CartridgeStore source.
- Replace avoidable duplicated constants/layout definitions with generated or shared contract artifacts.
- Add Store bundle preflight validation before network upload.
- Reject stale/mismatched ABI and unsupported architecture/feature combinations.
- Add cross-repository conformance fixtures for valid, invalid, duplicate-version and compatibility cases.
- Do not invent a Store API that does not exist.

## Phase 5 — Make the PWA genuinely offline and tighten browser security

The authenticated shell currently loads Bootstrap, icons, jQuery and Blockly from CDNs, while the service worker caches only same-origin static assets.

- Vendor pinned, license-compatible versions of all required browser assets.
- Record versions, licenses and provenance.
- Serve all authoring/runtime dependencies from same-origin static paths.
- Add an appropriate Content Security Policy without introducing unsafe-inline exceptions unless narrowly justified.
- Update the service-worker asset list and bump its cache version.
- Preserve the rule that signed-in pages and API data are never cached.
- Add cold-offline and warm-offline browser tests, not only string assertions over the service-worker source.

## Phase 6 — Complete academic identity and scoped RBAC

Implement the accepted identity ADR or update it before code changes:

- Authorization Code flow with PKCE S256.
- State, nonce, issuer, audience, signature, expiry and JWKS-rotation validation.
- Identity key based on issuer plus subject, not a generic `("oidc", sub)` pair.
- Multiple administrator-configured IdPs with encrypted/managed secrets.
- Claim/group mapping and explicit collision handling.
- Student, TA, teacher, publisher and administrator capabilities expressed as scopes/permissions rather than only an ordinal role hierarchy.
- Disabled user, group-change, first-login, logout, IdP failure and locked-admin recovery behavior.
- Store tokens must never become IDE sessions.

Run the full audit scenario for incorrect issuer/audience/state/nonce, expired tokens, PKCE tampering, redirect tampering, JWKS rotation, logout, collisions and privilege boundaries.

## Phase 7 — Guest storage and registered-user lifecycle

- Add administrator policies for guest access.
- Store guest projects only in IndexedDB; do not silently persist them server-side.
- Provide export, import, eviction warnings and conversion to a registered account.
- Add registered-user quotas for projects, revisions, uploads, artifacts and build resources.
- Add autosave with explicit conflict detection/merge behavior.
- Define retention, deletion, account deprovisioning and restore behavior.
- Preserve existing versioned project archives and migrations.

Test every guest policy, browser reload, storage eviction, denied operation, account switch, quota boundary, concurrent edit and migration.

## Phase 8 — Implement the actual IDE shell

- Build a responsive JetBrains-inspired shell with project tree, editor tabs, panels, command palette and keyboard navigation.
- Keep Bootstrap and jQuery as required app-level frameworks.
- Integrate a vendored/offline Monaco editor for C and RISC-V assembly.
- Keep Blockly fully editable and canonical for Blocks projects.
- Preserve generated C and assembly as inspectable read-only or explicitly managed artifacts.
- Provide deterministic C completion/diagnostics/navigation based on the supported PRG32 SDK.
- Provide RISC-V instruction/register/ABI completion and diagnostics consistent with the supported RV32IM/IMC rules.
- Add focus management, screen-reader labels, contrast, reduced-motion and mobile-width tests.

Do not call this phase complete while the source editors remain plain textareas without language services.

## Phase 9 — Add source-level and block-level debugging

- Define a debug build profile with appropriate DWARF output.
- Add C source/address mappings, locals, globals, call stack and watches.
- Add deterministic block ID → IR → generated C/assembly → address mappings.
- Highlight the active Blockly block without changing the saved project.
- Keep address-only debugging as a graceful fallback when debug metadata is absent.
- Add explicit compressed-instruction fixtures for step, breakpoint, over and out correctness.
- Continue differential state comparisons against the PRG32-QT core.

## Phase 10 — Cloud integrations

Only begin after identity, guest/registered storage and conflict semantics are stable.

- Implement Google Drive and OneDrive through separate provider adapters.
- Use minimum OAuth scopes.
- Handle refresh, expiry, revocation, network loss, duplicate files and concurrent conflicts.
- Never log access/refresh tokens.
- Provide disconnect and local-export workflows.
- Test with provider sandboxes or recorded contract fixtures; clearly label anything not exercised against a real provider.

## Phase 11 — Delivery and release verification

- Verify physical-device transfer and launch with artifact integrity checks.
- Verify the PRG32-QT import/delivery workflow as a user would perform it.
- Locate and inspect the real PRG32-iOS source/contract before implementing handoff. Do not invent a URL scheme, file association or API.
- Add browser E2E, accessibility, performance and memory budgets.
- Add backup/restore drills, operational metrics, health checks, TLS documentation, SBOM and license inventory.
- Retain evidence for every claimed target and environment.

## Baseline test commands

Run at least:

```bash
python3 -m compileall -q app.py prg32_construction_kit tests tools
for file in static/js/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done
python3 -m pytest -q -rs
```

When sibling sources/toolchains are available, also run:

```bash
PYTHONPATH=../PRG32 python3 -m pytest -q -rs \
  tests/test_project_format.py::test_sdk_abi_matches_the_prg32_sdk_when_installed \
  tests/test_wasm_runtime.py
```

Run the container build and real-cartridge concurrency check before claiming build readiness. Run tests on Python 3.11 and 3.12 as CI does. Preserve clean skips when external tools are missing.

The audit baseline produced 346 passes, 14 skips and one sandbox-caused Emscripten cache failure in the full local run. A focused ABI/WASM run produced 30 passes and one real-toolchain skip. Do not introduce regressions below this baseline without explaining and fixing them.

## Documentation and evidence required in every PR

- Short teacher/student explanation under `docs/` or `docs/tutorials/`.
- Updated ADR/architecture/traceability/implementation-status entries.
- Exact test commands and results.
- Security assumptions and limitations.
- Migration and rollback notes where storage/configuration changes.
- Screenshots only when actually captured; never substitute mockups for working integration.
- No claims of hardware, iOS, IdP, cloud or Store validation without retained logs/artifacts.

## Definition of release readiness

Do not change the audit recommendation from NO-GO until all of these are true:

1. SSRF is closed and covered by adversarial tests.
2. Publisher authorization and explicit confirmation are enforced server-side.
3. Untrusted builds execute in a production-grade isolation boundary.
4. Blocks, C and assembly produce real ABI-compatible cartridges in reproducible CI.
5. The claimed IDE shell and language services are implemented and accessible.
6. The WASM runtime/debugger mandatory scenarios pass, including compressed instructions and required source-level features.
7. Guest/account/SSO/cloud claims match implemented and executed behavior.
8. Store, hardware, Qt and iOS delivery claims are backed by actual contract and execution evidence.
9. No Critical or release-blocking High finding remains open.

After each phase, update the audit matrix conservatively. A high numerical score never overrides a release-gate security or compatibility failure.
