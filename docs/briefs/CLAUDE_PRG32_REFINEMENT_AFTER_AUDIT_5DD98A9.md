# Claude refinement brief after audit `5dd98a9`

Use this note as the implementation brief for the next refinement of **PRG32-Construction-Kit**. Read the repository `AGENTS.md` and applicable ADRs before changing code. Treat the audit files in `audit/` and `docs/capabilities.json` as the current evidence baseline.

## Current audited state

- Audited Construction Kit commit: `5dd98a95a0f910091896eb1149d29a5f96265b3d`.
- Audit score: **79/132 (59.8%)** across 33 requirements.
- Decision: **NO-GO for the complete Full IDE scope**; **conditional GO for a bounded classroom preview**.
- The browser language-service and source/block debugger milestones are substantially complete. Do not redesign them or weaken their safety properties while addressing later phases.
- Verified locally: 614 broad tests passed; 65 required-browser tests passed with `PRG32_REQUIRE_BROWSER=1`; 94 Store-egress tests passed; the focused language/debug/documentation suite passed.

## Non-negotiable invariants

1. Keep the normal generation pipeline: Blockly JSON -> validated game IR -> deterministic C and optional deterministic RV32IM assembly -> PRG32 toolchain.
2. Never compile arbitrary, unvalidated LLM-supplied C.
3. Keep generated C and assembly visible, deterministic, small, freestanding, and pedagogically commented.
4. Browser language services may suggest only validator-accepted, portable ABI functions. Server validation remains authoritative.
5. Debug builds may add only the approved debug flags. The cartridge must remain byte-identical, debug ELF files must never be served, and source-map markers must not change generated code.
6. Preserve handwritten-assembly validation, ownership rules, authentication boundaries, API routes, strict CSP, vendored browser libraries, static-only service-worker caching, and per-build isolation.
7. Preserve compatibility with PRG32 firmware, PRG32-QT, and Cartridge Store. Keep the phrase **PRG32 cartridge** for `.prg32` artifacts.
8. Do not change audit scores unless performing a new evidence-based audit. Update `docs/capabilities.json` first and render `docs/capabilities.md` from it.

## Refinement objectives, in priority order

### 1. Repair evidence and documentation drift

- Replace stale phase-2 commit references, especially the `731e378` wording in current-state documentation, with accurate milestone/evidence references.
- Ensure every capability ID appears exactly once in `docs/architecture/current-state.md` and all `[ID]` tags agree.
- Document the required-browser CI evidence, debugger fixtures, language-index regeneration, and immutable cartridge/debug identity checks.
- Keep `README.md` short and setup-focused; place explanations and operational detail under `docs/`.

Acceptance evidence:

- `python3 tools/render_capabilities.py --check`
- `python3 tools/build_language_index.py --check`
- `python3 tools/service_worker_lock.py --check`
- `python3 -m pytest -q tests/test_capabilities.py tests/test_doc_consistency.py`

### 2. Complete academic identity and authorization

- Implement standards-based academic identity with Authorization Code + PKCE.
- Key external identities by verified issuer and subject, not email alone; support more than one configured identity provider without account collisions.
- Define and enforce scoped roles for students, teachers, classroom facilitators, administrators, and service/API clients.
- Preserve Cartridge Store alignment for roles, groups, API tokens, and `/auth/*` behavior. Keep `prg32_construction_kit/sso_protocol.py` byte-identical to the Store counterpart.
- Specify account-linking, group/class membership, deprovisioning, session expiry, token revocation, and audit-event behavior.
- Add negative authorization tests for cross-owner reads/writes, shared read-only items, role escalation, stale sessions, invalid redirect/state/nonce/PKCE data, and user-switch `409 user_changed` handling.

Do not log bearer tokens or store plaintext passwords. Do not silently merge identities on matching email addresses.

### 3. Make guest and registered storage policies explicit

- Define offline guest storage in IndexedDB, including capacity messaging, export/import, migration after sign-in, and safe clearing behavior.
- Add registered-user quotas, deterministic conflict handling, autosave semantics, retention/deletion policy, and deprovisioning behavior.
- Keep block programs in `projects.blocks_json`; use artifact CRUD for generated/uploaded artifacts; keep large bundles on disk and metadata in SQLite.
- Preserve idempotent database initialization and ensure every build uses only its private `<build_id>/` tree and `tmp/` directory.
- Never make cloud identity mandatory for ordinary classroom use.

### 4. Stabilize Store and cartridge contracts

- Define one versioned, machine-readable contract for project export, cartridge metadata, publish profiles, Store publishing, and compatibility errors.
- Reuse shared fixtures or schemas where possible instead of maintaining subtly different copies.
- Add controlled live conformance tests that are opt-in, credential-safe, and incapable of mutating production data by default.
- Preserve the existing CRUD/action routes and the discovery document's `cartridge_builds` field.
- Prove that Store protocol and cartridge schema changes fail clearly and do not partially publish.

### 5. Add Drive and OneDrive only after identity/storage contracts are stable

- Implement providers behind a small, documented storage-provider interface.
- Use least-privilege scopes, explicit consent, secure token storage, revocation, retry/backoff, conflict handling, and provider-independent project semantics.
- Keep local/offline storage fully functional when providers are unavailable.
- Use contract tests and mocked provider failures; do not make routine unit tests depend on live cloud accounts.

### 6. Harden build and debug isolation

- Add enforceable per-build disk quotas and resource accounting.
- Evaluate per-build OS identities or an equivalent boundary, plus AppArmor/other host policy where supported.
- Fuzz malformed DWARF/source-map/debug payloads and prove bounded parsing, path stripping, and no host-file disclosure.
- Preserve the existing no-debug-ELF response boundary and cartridge/debug byte-identity check.
- Keep clean skips when optional RISC-V tools are absent, but make required CI environments fail when their declared tools are unavailable.

### 7. Polish advanced debugger behavior without inventing data

- Improve breakpoint persistence, enable/disable behavior, diagnostics for unresolved breakpoints, and navigation across regenerated source.
- Define honest behavior for optimized/inlined frames, unavailable variables, and incomplete location information. Show “unavailable” rather than fabricated values.
- Retain source, Blocks, call-stack, variables, watches, conditional breakpoints, CSR and stack views, keyboard accessibility, strict CSP, and compressed-instruction fixtures.
- Keep marker removal and generated cartridge bytes invariant.

### 8. Finish delivery, accessibility, operations, and supply-chain evidence

- Exercise real hardware and PRG32-QT compatibility with recorded versions and artifacts.
- Complete iOS/PWA install and offline checks where the product claims support.
- Add screen-reader/keyboard audits and representative performance budgets for classroom hardware.
- Test backup and restore, not merely backup creation.
- Lock dependency hashes where practical, generate an SBOM, and document vulnerability/update handling.
- Keep CI browser suites non-skippable and publish useful failure artifacts.

## Required implementation discipline

- Work in small, reviewable commits grouped by capability ID.
- For every behavior change, update or add pytest coverage and a short teacher/student explanation under `docs/`.
- Regenerate the language index only through `tools/build_language_index.py` when SDK ABI/headers or validators change.
- Regenerate debugger fixtures only through `tools/build_debug_fixtures.py` when their inputs legitimately change.
- Bump and lock the service-worker cache version whenever cached static files change.
- Do not add CDNs, inline scripts, `unsafe-inline`, or `unsafe-eval`.
- Do not silently alter user projects through AI assistance.
- Never mask missing required browser/toolchain coverage with skips.

## Minimum verification before handoff

Run the broad suite plus focused gates appropriate to the changed areas. At minimum:

```sh
python3 -m compileall -q app.py prg32_construction_kit tests tools
python3 tools/service_worker_lock.py --check
python3 tools/render_capabilities.py --check
python3 tools/build_language_index.py --check
python3 -m pytest -q
PRG32_REQUIRE_BROWSER=1 PRG32QT_DIR=../PRG32-QT python3 -m pytest -q \
  tests/test_browser_offline.py \
  tests/test_ide_browser.py \
  tests/test_debugger_browser.py \
  tests/test_frontend_offline.py
git diff --check
```

Also run Store egress, SDK ABI, real cartridge/toolchain, Docker, and platform delivery checks whenever the needed sibling repositories and tools are available. Record exact commands, versions, commit SHAs, pass/fail/skip counts, and reasons for every skip.

## Handoff format

Return:

1. a concise outcome summary;
2. changed capability IDs and their evidence;
3. files changed;
4. exact test commands and results;
5. remaining risks and intentionally deferred work;
6. confirmation that generated cartridge bytes, security boundaries, API contracts, CSP, offline behavior, and educational visibility were preserved.

Do not claim Full IDE readiness until the identity, storage, cloud, delivery, and operational gaps have objective evidence and the complete audit is rerun.
