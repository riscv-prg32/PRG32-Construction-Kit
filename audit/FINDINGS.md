# Findings

## Resolved since audit `5dd98a9`

- Academic sign-in now uses PKCE, signed ID-token validation and issuer+subject identity; matching email never silently links accounts.
- Multiple IdPs, explicit linking/recovery, academic/class roles, scoped tokens, session revocation and deprovisioning are implemented.
- Guest games are local-only IndexedDB data with export/import and safe migration after sign-in.
- Registered storage has atomic version conflicts, autosave, account quotas, retention and administrator-controlled deletion.
- Required account and storage browser scenarios run in CI with skipping forbidden.

## Critical and high

No critical or high implementation defect was confirmed in the audited scope.

## Medium

### M-01 — External identity lifecycle is not independently integrated

The cryptographic and authorization paths are strongly tested against a signed in-process provider, but no institutional IdP, SCIM lifecycle, or provider-initiated logout was exercised. Complete enterprise/academic identity claims remain conditional.

### M-02 — Drive and OneDrive are absent

OAuth scope, refresh/revoke, conflict and network-loss scenarios cannot run.

### M-03 — Store validation remains local rather than shared/live conformance

The kit checks manifests and hashes but duplicates selected contract knowledge and lacks a controlled live duplicate/version/update/visibility matrix.

### M-04 — Delivery targets remain unverified

No physical PRG32 transfer/launch, end-user Qt import or verified iOS handoff was executed.

### M-05 — Production sandbox operational gaps remain

No enforceable total build-directory quota or per-build UID; AppArmor remains unconfined in the documented container flags. Linux escape and real debug-build tests were not independently rerun here.

### M-06 — Source debugger is intentionally incomplete for advanced optimized C

Inlined frames are not represented separately and unsupported/optimized-out values are unavailable. This fails safely but must remain clearly bounded.

## Low

### L-01 — Minor status/evidence drift remains

The phase-6 current-state evidence row says “this change” rather than the immutable `e2d0cef` revision, and the G1 line in `docs/implementation-status.md` still says the guest policy is open.

### L-02 — Quality and supply-chain gates remain incomplete

No lint/type/coverage threshold, representative performance budget, hash-locked dependency set, complete SBOM/security inventory or real screen-reader session.

### L-03 — Exact build evidence was not reproducible on this host

Real cartridge/debug fixture regeneration, Linux sandbox execution and exact Emscripten rebuilding were unavailable. Preserve CI artifacts for release audits.

## Release conclusion

Identity and storage no longer block a bounded classroom deployment. The complete Full IDE remains **NO-GO** because cloud, shared/live Store conformance, and delivery requirements remain materially incomplete. A deployment claiming institutional SSO also remains conditional until tested with its real provider and lifecycle controls.
