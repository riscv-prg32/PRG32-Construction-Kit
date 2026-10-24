# Claude refinement brief after audit `fea31c0`

Continue PRG32-Construction-Kit from audited commit `fea31c02348af2adc28e96c3795d38ae18a8f8e9`. Read `AGENTS.md`, ADR-0010 through ADR-0019, and the current `audit/` records first.

## Audit result

- Score: **103/132 (78.0%)**.
- Decision: **NO-GO for the complete Full IDE scope; GO for a bounded classroom deployment with documented platform limits**.
- Verified now: 815 feasible tests, 77 required Chromium tests, 45 shared-contract/disposable-Store tests, 94 Store-egress tests and 9 disposable-Keycloak tests passed.
- Reference-verified: academic identity/RBAC, guest/registered storage, shared Store contract, language services and the required debugger baseline.
- Implemented but externally conditional: Google Drive and OneDrive; no real provider account was available.

Do not redesign closed features. Preserve their tests and security boundaries.

## 1. Repair current-state documentation

- Remove the stale statement in `docs/architecture/current-state.md` that no live Store or IdP was used. Distinguish disposable local services from production systems.
- Remove the stale `cloud sync open` wording in `docs/implementation-status.md`; state that both adapters are implemented but real-tenant evidence is pending.
- Record immutable commit SHAs and retain commit-specific CI artifacts.
- Do not change auditor scores. Render `docs/capabilities.md` only from `docs/capabilities.json`.

## 2. Validate Google Drive and OneDrive with dedicated test tenants

Use only the opt-in environment-driven harness in `tests/test_cloud_live.py` and dedicated non-personal test accounts.

- Verify refresh after expiry, app identity, create/list/load/conditional save, stale-revision refusal, least-privilege visibility and trash cleanup for each provider.
- Exercise revoked refresh tokens and provider outages without changing local or remote data.
- For Google, verify `drive.file` and document the check-then-write race honestly.
- For Microsoft, verify `Files.ReadWrite.AppFolder`, `User.Read`, `offline_access`, conditional `If-Match`, and the simple-upload size limit.
- Tests may touch only files they create. Never enumerate, modify or delete unrelated files.
- Never commit tokens, return them to the browser or log them. Keep encrypted storage and fixed provider hosts.
- A cloud/local replacement must remain an explicit choice naming the exact version/revision the student saw.

If tenant credentials are unavailable, improve mocks and documentation but do not claim reference verification.

## 3. Complete delivery evidence

- Transfer and launch representative C, generated-assembly and handwritten-assembly PRG32 cartridges on physical PRG32 hardware. Record artifact hashes, firmware/tool versions and outcomes.
- Exercise the end-user PRG32-QT import/open/run workflow, not only headless runtime parity.
- Implement and verify the documented iOS handoff or explicitly remove/defer that product claim.
- Keep delivery instructions classroom-readable and offline-capable.

## 4. Harden the production build boundary

- Enforce a total build-root disk budget, including safe accounting under concurrent builds and cleanup.
- Evaluate per-build OS users/namespaces or an equivalently strong isolation boundary.
- Provide a confined AppArmor profile for supported Linux hosts and remove `apparmor=unconfined` there.
- Fuzz DWARF/source-map inputs for size/count/time/path limits and prove malformed data cannot disclose host files.
- Run bubblewrap/seccomp/resource and real three-mode cartridge tests in required Linux CI.
- Preserve one private `<build_id>/tmp/` per build, approved debug flags only, cartridge/debug load-image equality and the prohibition on serving debug ELF files.

## 5. Resolve the Store lifecycle gaps

Coordinate with CartridgeStore rather than hiding incompatibilities:

- Define safe expiry/rotation for Store API tokens.
- Resolve duplicate pending cartridge identity/version semantics.
- Update `contracts/prg32-store-contract-1.json` only compatibly; use a new version for breaking changes.
- Regenerate fixtures only with `tools/build_contract_fixtures.py`.
- Keep `store_contract.validate_bundle` before every upload and preserve signed review/confirmation plus egress controls.
- Live tests must remain limited to a throwaway loopback Store. Never test against a real Store.

## 6. Complete QA, accessibility and operations

- Add representative classroom-device performance budgets.
- Conduct and record a real keyboard plus screen-reader session.
- Restore an actual backup into a clean deployment and verify accounts, projects, artifacts and build references.
- Add dependency hash locking where practical, generate an SBOM and document vulnerability/update handling.
- Add useful lint/type/coverage gates without making readable educational code harder to maintain.

## 7. Polish advanced debugging

- Persist and enable/disable breakpoints safely across deterministic regeneration.
- Improve optimized/inlined frame presentation where debug data supports it.
- Show unavailable/optimized-out values honestly; never invent values.
- Retain block/source/address fallback, conditional breakpoints, watches, call stack, registers, CSR, stack, accessibility and byte identity.

## Non-negotiable invariants

1. Blockly JSON -> validated game IR -> deterministic C and optional RV32IM assembly -> PRG32 toolchain.
2. Never compile arbitrary unvalidated LLM-supplied C.
3. Keep generated C and assembly visible and pedagogically commented.
4. Language suggestions remain browser-only, portable and validator-accepted; server validation is authoritative.
5. Guests store nothing on the server. Registered saves and cloud replacement remain conflict-safe.
6. Preserve issuer+subject identity, PKCE, single-use state/nonce, explicit account linking, read-only supervision and token scopes.
7. Preserve CRUD/action routes, owner/shared rules, `409 user_changed`, strict CSP, vendored assets and static-only service-worker caching.
8. Keep `sso_protocol.py` byte-identical to CartridgeStore.
9. Preserve **PRG32 cartridge** terminology for `.prg32` files.

## Minimum verification

```sh
python3 -m compileall -q app.py prg32_construction_kit tests tools
python3 tools/service_worker_lock.py --check
python3 tools/render_capabilities.py --check
python3 tools/build_language_index.py --check
python3 tools/build_contract_fixtures.py --check
python3 -m pytest -q
PRG32_REQUIRE_BROWSER=1 PRG32QT_DIR=../PRG32-QT python3 -m pytest -q -rs \
  tests/test_browser_offline.py tests/test_ide_browser.py \
  tests/test_debugger_browser.py tests/test_accounts_browser.py \
  tests/test_storage_browser.py tests/test_cloud_browser.py \
  tests/test_frontend_offline.py
PRG32_REQUIRE_STORE=1 PRG32_LIVE_STORE=local \
PRG32_CARTRIDGE_STORE_SOURCE=../CartridgeStore \
  python3 -m pytest -q -rs tests/test_store_contract.py \
  tests/test_store_live.py tests/test_sso_with_cartridge_store.py
python3 -m pytest -q -rs tests/test_store_egress.py
git diff --check
```

Run the Keycloak, real-cloud, Linux/toolchain and device suites when their safe test environments are available. Required CI dependencies must fail rather than skip.

## Handoff

Report changed capability IDs, exact files and commands, pass/skip counts, external systems used, credentials/test-data safety, residual risks and intentionally deferred work. Confirm generation determinism, validation, cartridge/debug identity, API compatibility, identity separation, conflict semantics, Store contract enforcement, CSP and offline classroom behavior remain intact.
