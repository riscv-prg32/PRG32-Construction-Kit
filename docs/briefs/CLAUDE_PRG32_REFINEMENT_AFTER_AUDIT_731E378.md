# Claude refinement brief after audit `731e378`

## Objective

Continue refining **PRG32-Construction-Kit** toward the approved Full IDE while preserving its educational transparency, deterministic generation, security controls, offline behavior, and compatibility with PRG32, PRG32-QT, and CartridgeStore.

This brief is based on the independent reassessment performed on 2026-10-19 at:

- PRG32-Construction-Kit `development`: `731e378e811744ffecd4bf346d4f48a6715a13d2`
- PRG32 `main`: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT `main`: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore `main`: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`

Audit result: **NO-GO for a Full IDE release**, scoring **70/132 (53.0%)** across 33 requirements.

Read before changing code:

1. `AGENTS.md`
2. `audit/EXECUTIVE_SUMMARY.md`
3. `audit/REQUIREMENTS_MATRIX.md`
4. `audit/FINDINGS.md`
5. `audit/TEST_REPORT.md`
6. `audit/ARCHITECTURE_REVIEW.md`
7. `audit/SECURITY_REVIEW.md`
8. `audit/REMEDIATION_PLAN.md`
9. `audit/EVIDENCE_INDEX.md`
10. `docs/capabilities.json`
11. All accepted ADRs

## What is already implemented and must be preserved

Do not regress or reimplement these areas without evidence of a defect:

- Editable canonical Blockly JSON.
- Deterministic Blockly → validated IR → explained C and RV32IM assembly.
- Inspectable generated C, assembly and IR.
- Validated Advanced C and handwritten assembly projects.
- Versioned project archives, migrations, revisions and identity-preserving restore.
- Per-build directories and production-required bubblewrap isolation.
- Store-origin/DNS/IP/TLS/redirect/response controls.
- Publisher-only authorization, immutable signed review, explicit confirmation and idempotent submission.
- PRG32-QT-derived WebAssembly runtime and machine-level debugger.
- Locally vendored Bootstrap, Bootstrap Icons, jQuery, Blockly and Monaco.
- Strict CSP without `unsafe-inline` or `unsafe-eval`.
- Static-only service-worker caching; never cache authenticated pages or API responses.
- Offline Blockly scratchpad and local real-cartridge player.
- Responsive IDE shell with tree, tabs, panels, command palette, keyboard regions and mobile fallback.
- `sso_protocol.py` byte identity with CartridgeStore.

The repeated audit executed all ten Chrome offline/IDE tests successfully. Preserve those workflows and their accessibility assertions.

## Immediate corrective PRs

### PR 1 — Put the IDE browser suite in CI

The browser job currently runs:

```text
tests/test_browser_offline.py tests/test_frontend_offline.py
```

It omits `tests/test_ide_browser.py`. Add it to `.github/workflows/tests.yml` so keyboard, Monaco, phone layout and axe regressions block every push and pull request.

Acceptance:

- CI installs Chromium and executes all three frontend/browser files.
- `test_ide_browser.py` does not silently skip in CI.
- Browser results are uploaded or otherwise clearly visible.
- Local fallback skips remain clean when no browser is installed.

### PR 2 — Repair documentation drift

Update `docs/architecture/current-state.md`, which still says the IDE shell, Monaco and offline shell are absent. Update the Construction Kit SHA and test evidence. Ensure the current-state page, implementation status, capability manifest, release notes and ADRs agree.

Add or extend a test that detects contradictory capability claims, not merely missing paths and symbols.

Acceptance:

- No document describes phases 1–2 as missing.
- Current repository SHAs and test results are dated and accurate.
- `docs/capabilities.md` remains generated from `docs/capabilities.json`.
- Audit scores remain controlled by the auditor rather than implementation code.

## Phase 3 — Deterministic language intelligence

The IDE shell exists, but IDE-03 and IDE-04 remain partial. Add offline, deterministic language assistance without exposing the host filesystem or introducing an unrestricted language server.

### C editor

Implement:

- completion for the permitted PRG32 cartridge ABI;
- function signatures and short student-readable documentation;
- navigation to vendored/generated SDK declarations;
- diagnostics mapped to exact Monaco ranges;
- compiler-error normalization without host paths;
- awareness of resident-only versus portable APIs;
- project entry-point checks and safe quick explanations.

### RISC-V assembly editor

Implement:

- RV32IM/RV32IMC instruction completion appropriate to project mode;
- register and ABI-name completion;
- allowed-directive completion only;
- portable PRG32 ABI symbols and calling-convention help;
- exact-range diagnostics for invalid directives, registers, instructions and required entry labels;
- deterministic navigation/help without remote requests.

### Safety constraints

- Do not weaken `validate_c_source` or `validate_asm_source`.
- Do not add arbitrary includes, file reads, compiler plugins or host language servers.
- Do not suggest directives or APIs that the validators reject.
- Do not expose server paths, tokens, environment values or build internals.
- Generated C and assembly remain readable teaching material.

Acceptance:

- Exact fixture tests for completion, hover/help, navigation and diagnostics.
- Unknown/unsafe API and directive fixtures remain rejected.
- Language assistance works with network disabled.
- Results are deterministic from pinned SDK/ABI inputs.
- Monaco keyboard and accessibility tests remain passing.

## Phase 4 — Mandatory source and block debugger

This is the primary Full IDE release blocker. Implement one deterministic coordinate chain:

```text
Blockly block ID
  → validated IR node
  → generated C/assembly source range
  → ELF/DWARF or guest address range
```

Required functionality:

- C source breakpoints;
- assembly source breakpoints;
- active Blockly block highlighting;
- locals and globals;
- call stack;
- watches;
- relevant CSR view;
- explicit stack view;
- conditional breakpoints if supported by the approved design;
- dedicated compressed-instruction stepping fixture;
- graceful address-only fallback when debug information is absent or invalid.

Do not change normal generated-code semantics to simplify debugging. Debug instrumentation must not change deterministic output or guest results.

Acceptance:

- Mandatory audit scenario D passes end-to-end.
- Browser and PRG32-QT/native snapshots agree at fixed checkpoints.
- Pause and instrumentation do not alter final guest state.
- Block/source maps are deterministic saved artifacts with tests.
- Bad or missing DWARF degrades safely to address-level debugging.
- Existing instruction/over/out/frame/breakpoint tests remain passing.

## Phase 5 — Academic identity and scoped authorization

Implement ADR-0007 or replace it with a newly accepted ADR before schema changes.

Required behavior:

- Authorization Code with PKCE S256;
- state and nonce validation;
- issuer, audience, signature and expiry validation;
- JWKS rotation;
- identity keyed by issuer plus subject;
- multiple administrator-configured providers;
- safe bootstrap and locked-out administrator recovery;
- claim/group mapping;
- first-login, disabled-user and changed-group lifecycle;
- scoped student, TA, teacher, publisher and administrator capabilities;
- provider logout semantics and MFA delegation;
- Store tokens must never become IDE sessions.

Coordinate shared account/protocol changes with CartridgeStore. Preserve `sso_protocol.py` identity unless both repositories deliberately migrate together.

Acceptance:

- Full mandatory scenario E passes.
- Cross-issuer identical `sub` values never merge accounts.
- Role/group changes take effect predictably and cannot escalate privileges.
- Ordinary students cannot publish or administer another course/project.
- Secrets do not enter logs, responses or exports.

## Phase 6 — Guest and registered project policy

The offline scratchpad is not sufficient for ACC-01. Implement administrator-selectable guest policies with IndexedDB project storage, export and eviction behavior. Guests must not persist projects on the server.

For registered projects implement:

- quotas;
- autosave;
- explicit optimistic concurrency/version checks;
- recoverable conflict handling;
- revision retention;
- deprovisioning policy;
- compatible migrations for existing databases and exports.

Acceptance:

- Mandatory scenarios A and B pass.
- Tests prove no guest project reaches server storage.
- Account switching does not expose another user's IndexedDB or server data.
- Export-before-eviction and quota failures are understandable and recoverable.
- Concurrent edits never silently overwrite another saved version.

## Phase 7 — Shared PRG32 and CartridgeStore contracts

Replace duplicated cartridge and bundle constants with a versioned shared schema, generated source, or conformance fixtures agreed across repositories.

Validate:

- cartridge header and payload integrity;
- ABI version/hash and compatible hashes;
- architecture and ISA flags;
- portable import model;
- bundle manifest/assets/hashes;
- duplicate and version conflicts;
- pending review, update and visibility behavior;
- interrupted upload and retry behavior.

Acceptance:

- Stale/mismatched ABI and malformed cartridges are rejected.
- Controlled Store integration matches actual response/status behavior.
- No live public artifact is published without explicit human authorization.
- Local schema changes cannot drift unnoticed from PRG32 or CartridgeStore.

## Phase 8 — Cloud providers

Only begin after identity, versioning and conflict semantics are stable.

Implement Google Drive, then OneDrive, behind a provider-neutral interface using minimum OAuth scopes. Cover refresh, expiry, revocation, disconnect, network loss and concurrent conflicts. Provider tokens must never appear in logs, browser exports or project archives.

Acceptance:

- Approved sandbox-tenant tests cover all mandatory scenario B cloud cases.
- Local unsynced work remains recoverable after expiry/revocation/network failure.
- Disconnect removes or invalidates stored credentials as documented.

## Phase 9 — Delivery, operations and release evidence

Verify rather than infer:

- physical PRG32 transfer and launch with artifact hashes;
- PRG32-QT end-user import workflow;
- actual PRG32-iOS import contract and handoff;
- total build-directory quotas and per-build identity where feasible;
- AppArmor-compatible sandbox operation;
- backup and restore;
- TLS/reverse-proxy deployment;
- metrics and secret-safe logs;
- dependency hash locks, SBOM and license inventory;
- browser memory/build latency budgets;
- real screen-reader workflow.

Acceptance:

- Mandatory scenarios C and G pass.
- Device/app evidence records exact versions, hashes and outcomes.
- Linux sandbox escape/resource suites pass on x86_64 and aarch64.
- Tests requiring unavailable hardware/toolchains skip cleanly and are never reported as passes.

## Commands required for every refinement PR

Run and report at minimum:

```bash
python3 -m compileall -q app.py prg32_construction_kit tests tools
for file in static/js/*.js static/js/ide/*.js static/service-worker.js tools/*.mjs; do node --check "$file"; done
python3 tools/service_worker_lock.py --check
python3 tools/render_capabilities.py --check
python3 -m pytest -q -rs
git diff --check
```

For frontend changes also run in a real browser:

```bash
python3 -m pytest -q -rs \
  tests/test_browser_offline.py \
  tests/test_frontend_offline.py \
  tests/test_ide_browser.py
```

Run relevant WASM, Store, sandbox, real-cartridge, identity, cloud or device suites for the phase. Record exact pass/fail/skip counts and explain every skip.

## Reporting requirements

For every PR provide:

1. branch and exact HEAD;
2. changed files and primary symbols;
3. user-visible behavior;
4. security and trust-boundary impact;
5. schema/migration and rollback impact;
6. exact commands and results;
7. browser/device/provider artifacts where applicable;
8. requirements whose evidence changed;
9. documentation updated for students, teachers and administrators;
10. remaining gaps without inflated claims.

Use exact `path:line` references. Distinguish source inspection, automated execution and manual validation. Do not score a requirement 4 unless it was demonstrated against the relevant reference or external system.

## Full IDE release gate

Do not recommend Full IDE release until all of the following hold:

- IDE shell and C/assembly language services are complete and continuously tested.
- Blocks remain editable and have deterministic source/address mappings.
- all three authoring modes build real portable PRG32 cartridges;
- browser execution remains the pinned PRG32-QT-derived core;
- the complete source/block debugger scenario passes;
- guest and registered storage isolation/conflict policies pass;
- academic OIDC/RBAC negative tests pass;
- Store publishing matches the real controlled contract;
- cloud requirements are implemented and verified or formally removed from approved scope;
- hardware, Qt and iOS claims have executed evidence;
- no critical security release gate is open;
- documentation and the machine-checked capability table match shipped behavior.

Until those conditions hold, describe the product as the implemented classroom PRG32 construction kit with an evolving IDE, not as a complete Full IDE.
