# Findings

## Resolved since audit `e2d0cef`

- OIDC behavior is independently exercised against disposable Keycloak, including PKCE, state, expiry, audience, rotation, collisions/linking, deactivation and local logout semantics.
- A versioned Store contract, deterministic fixtures and a mandatory disposable live-Store CI job align Kit and Store validation without touching production.
- Google Drive and OneDrive implementations share a provider-neutral contract, least-privilege scopes, encrypted tokens, fixed hosts and explicit revision conflict choices.
- Required Chromium coverage now includes the cloud workflow.

## Critical and high

No critical or high implementation defect was confirmed in the audited scope.

## Medium

### M-01 — Cloud providers lack real-tenant evidence

Both implementations pass extensive in-process contract and browser tests, and opt-in tests are safety-bounded, but no real Google or Microsoft test account was available. Provider behavior, consent configuration, refresh/revocation and concurrency remain externally unverified.

### M-02 — Delivery targets remain unverified

No physical PRG32 transfer/launch, end-user PRG32-QT import or verified iOS handoff was executed.

### M-03 — Production sandbox operational gaps remain

No enforceable total build-root quota or per-build UID; AppArmor remains unconfined in documented container flags. Linux escape and real debug-build tests were not independently rerun here.

### M-04 — Store lifecycle gaps are explicit but unresolved

The contract records CartridgeStore behavior for duplicate pending identity/version and tokens without expiry. Contract drift is now detected, but the upstream lifecycle limitations remain.

### M-05 — Source debugger remains bounded for optimized C

Inlined frames are not represented separately and unsupported/optimized-out values are unavailable. The fallback is safe but advanced debugging remains incomplete.

## Low

### L-01 — Current-state prose contradicts current evidence

`docs/architecture/current-state.md` still says there is no live Store or IdP even though disposable live suites are recorded. `docs/implementation-status.md` still says cloud sync is open despite both adapters being implemented.

### L-02 — Quality and supply-chain gates remain incomplete

No lint/type/coverage threshold, representative performance budget, complete dependency hash lock/SBOM, real screen-reader session or restored-backup drill.

### L-03 — Exact build evidence was not reproduced on this host

Real cartridge/debug fixture regeneration, Linux sandbox execution and exact Emscripten rebuilding were unavailable. Preserve immutable CI artifacts.

## Release conclusion

The audited code is suitable for a bounded local classroom deployment that documents cloud and platform limits. Complete Full IDE release remains **NO-GO** until real cloud-provider and delivery evidence, plus the remaining operational hardening, is available.
