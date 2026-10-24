# Claude refinement brief after audit `e2d0cef`

Implement the next PRG32-Construction-Kit refinement from audited commit `e2d0cef834bbe75e1fd3fd5c2ea69ce7f1560954`. Read `AGENTS.md`, the applicable ADRs, and the current files under `audit/` before editing.

## Audit outcome

- Score: **93/132 (70.5%)** across 33 requirements.
- Decision: **NO-GO for the complete Full IDE scope; CONDITIONAL GO for a bounded classroom deployment**.
- Closed in phases 5–6: academic PKCE/issuer+subject identity, multiple IdPs, explicit account linking, scoped academic/class roles, scoped tokens and session revocation; local-only IndexedDB guest projects; atomic save conflicts, autosave, quotas, retention and deprovisioning.
- Verified: 710 broad feasible tests passed; 74 required Chromium tests passed without skips; 94 Store-egress tests passed.

Do not reimplement closed features. Preserve their security and educational invariants while addressing the gaps below.

## Priority 1 — Evidence drift and release records

- Replace the phase-6 `this change` marker in `docs/architecture/current-state.md` with `e2d0cef` or an immutable successor.
- Correct the G1 statement in `docs/implementation-status.md` that says guest policy is still open.
- Preserve commit-specific CI artifacts for browser, container/toolchain and fixture generation checks.
- Keep capability scores auditor-controlled and render `docs/capabilities.md` only from `docs/capabilities.json`.

## Priority 2 — External academic identity integration

The implementation has strong signed fake-provider coverage but lacks real institutional lifecycle evidence.

- Add an opt-in integration harness for at least one standards-compliant institutional OIDC tenant without committing secrets.
- Exercise discovery/JWKS rotation, PKCE, state, nonce, issuer, audience/azp, expiry, account collision, explicit linking, deactivation and recovery.
- Specify whether SCIM or another provisioning feed is required. If supported, make creation/update/deactivation idempotent and fully audited.
- Specify front-/back-channel or local-only logout behavior honestly. Never claim IdP-wide logout unless demonstrated.
- Preserve identity keys as `(issuer, subject)` and never merge accounts by email.
- Preserve global CartridgeStore roles separately from kit academic/class roles. Keep `sso_protocol.py` byte-identical to CartridgeStore.

## Priority 3 — Shared Store and cartridge contracts

- Replace duplicated contract knowledge with a versioned, machine-readable shared schema or generated fixtures for project bundles, cartridge metadata, publish profiles and compatibility errors.
- Add a controlled, opt-in live conformance suite covering duplicate identity/version, updates, visibility, rejected manifests, token expiry/revocation, network loss and partial-failure recovery.
- Default all live tests to non-production or dry-run behavior; never publish or delete production data implicitly.
- Keep approved-origin/SSRF checks and the signed review/confirmation boundary.

## Priority 4 — Provider-neutral Drive and OneDrive storage

Begin only from the now-stable identity, version-conflict and quota semantics.

- Define a small provider interface with list/load/save/create/delete/revoke operations and deterministic revision/conflict metadata.
- Use least-privilege scopes, explicit consent, secure token storage, refresh/revocation and bounded retry/backoff.
- Keep local/offline and guest modes fully usable without cloud accounts.
- Never silently overwrite either local or remote work. Present copy/take-remote/explicit-overwrite choices consistent with registered project conflicts.
- Add mocked contract tests plus opt-in tenant tests for expiry, revoke, disconnect, outage, concurrent edits and account switching.

## Priority 5 — Build and debug operational hardening

- Enforce a total build-root/disk budget in addition to account quotas and per-process limits.
- Evaluate per-build OS identities or an equivalent isolation boundary.
- Provide a confined AppArmor profile or accurately document why a target host cannot use one; remove `apparmor=unconfined` where supported.
- Fuzz bounded DWARF/source-map parsers and prove malformed inputs cannot disclose host paths/files or cause unbounded work.
- Run Linux bubblewrap/seccomp/resource suites and real C/generated-assembly/handwritten-assembly cartridges in CI.
- Preserve private `<build_id>/tmp/`, approved debug flags, cartridge/debug load-image identity, stripped paths and the rule that debug ELF files are never served.

## Priority 6 — Delivery, accessibility and operations

- Execute physical PRG32 transfer and launch with hashes/logs.
- Exercise the end-user PRG32-QT import workflow, not only runtime parity.
- Implement and verify the claimed iOS handoff, or explicitly remove/defer the claim.
- Run a real screen-reader session and representative classroom-device performance budgets.
- Test backup restoration and rollback for identity/storage migrations.
- Add dependency hash locking where practical, an SBOM and documented vulnerability/update handling.

## Priority 7 — Debugger polish

- Improve breakpoint persistence and enable/disable controls across regeneration.
- Represent optimized/inlined frames and unavailable variables honestly; never fabricate values.
- Retain safe address-only fallback and all existing source/block, watch, call-stack, CSR and stack behavior.

## Non-negotiable project constraints

1. Blockly JSON -> validated game IR -> deterministic C/optional RV32IM assembly -> PRG32 toolchain remains the normal pipeline.
2. Never compile arbitrary unvalidated LLM C.
3. Generated C and assembly remain visible, deterministic and pedagogically commented.
4. Browser language services suggest only portable, validator-accepted constructs; server validation is authoritative.
5. AI may propose or explain edits but must never silently alter projects.
6. Preserve all documented CRUD/action routes, ownership rules, `409 user_changed`, CSP, vendored libraries, static-only service-worker caching and offline classroom use.
7. Every build stays inside its private build directory. Never expose debug ELF files.
8. Preserve the phrase **PRG32 cartridge** for `.prg32` artifacts.

## Required verification

```sh
python3 -m compileall -q app.py prg32_construction_kit tests tools
python3 tools/service_worker_lock.py --check
python3 tools/render_capabilities.py --check
python3 tools/build_language_index.py --check
python3 -m pytest -q
PRG32_REQUIRE_BROWSER=1 PRG32QT_DIR=../PRG32-QT python3 -m pytest -q -rs \
  tests/test_browser_offline.py tests/test_ide_browser.py \
  tests/test_debugger_browser.py tests/test_accounts_browser.py \
  tests/test_storage_browser.py tests/test_frontend_offline.py
python3 -m pytest -q -rs tests/test_store_egress.py
git diff --check
```

Run real toolchain, Docker/Linux sandbox, Store, IdP, cloud and device checks whenever their environments are available. Required CI jobs must fail rather than skip when declared dependencies are missing.

## Handoff requirements

Report capability IDs changed, files changed, exact commands/results, external systems used, skipped evidence and residual risks. Confirm explicitly that generation determinism, cartridge/debug byte identity, validation, ownership, API contracts, CSP, offline behavior, identity separation and conflict-safe storage remain intact.
