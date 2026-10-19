# Findings

## Resolved since audit `731e378`

- CI now runs every real-browser suite with `PRG32_REQUIRE_BROWSER=1` and uploads JUnit evidence.
- Documentation contradictions are machine-checked by `tests/test_doc_consistency.py`.
- IDE-03/04 language services are implemented offline from a reproducible, pinned index and agree with server validators.
- The mandatory source/block debugger is implemented and demonstrated in Chrome using real-toolchain fixtures; compressed stepping and native/WASM parity pass.

## Critical

No exploitable critical issue was confirmed.

## High

### H-01 — Academic identity, scoped roles and guest policy are incomplete

- Evidence: ACC-01 is missing and SSO-01/02/03 remain prototypes (`docs/capabilities.md`).
- Reproduction: mandatory guest-policy and institutional OIDC scenarios cannot be executed as specified.
- Impact: complete Full IDE classroom tenancy/lifecycle claims are unsupported.
- Remedy: PKCE, issuer+subject, multi-IdP lifecycle/recovery, scoped student/TA/teacher RBAC, and administrator-controlled guest IndexedDB policies.

## Medium

### M-01 — Registered storage lacks quotas and conflict semantics

No autosave, optimistic conflict recovery, quotas, retention or deprovisioning. History alone does not satisfy ACC-02.

### M-02 — Drive and OneDrive are absent

Required OAuth scope, refresh/revoke, conflict and network-loss scenarios cannot run.

### M-03 — Store validation remains local rather than shared/live conformance

The kit checks manifests and hashes but still duplicates selected contract knowledge and has no controlled live duplicate/version/update/visibility matrix.

### M-04 — Delivery targets remain unverified

No physical PRG32 transfer/launch, end-user Qt import or verified iOS handoff was executed.

### M-05 — Production sandbox operational gaps remain

No total build-directory quota or per-build UID; AppArmor needs an exception. Linux escape and real debug-build tests were not independently rerun here.

### M-06 — Source debugger is intentionally incomplete for advanced optimized C

Inlined frames are not represented separately, unsupported DWARF expressions display unavailable, and optimized-out values cannot be recovered. These are documented and fail safely, but should be bounded clearly for advanced users.

## Low

### L-01 — Status documents still identify the phase-2 SHA as the repository revision

`docs/architecture/current-state.md:13` and `docs/implementation-status.md:5` describe later phases but retain `731e378`. Record the actual phase-4 HEAD or describe the revision range unambiguously.

### L-02 — Quality and dependency gates remain incomplete

No lint/type/coverage threshold, performance budget, hash-locked dependency set, complete SBOM/security inventory or real screen-reader session.

### L-03 — Exact build evidence was not reproducible on this host

Committed debug fixtures and documented container results are credible source evidence, but local fixture regeneration, real cartridge builds, Linux sandbox execution and exact Emscripten rebuilding were unavailable. Preserve CI artifacts so release audits can verify them independently.

## Release conclusion

The mandatory debugger NO-GO is closed. The complete Full IDE remains **NO-GO** because substantial approved account, identity, cloud and delivery scope is missing. A bounded classroom preview can be **CONDITIONAL** if it explicitly excludes those claims and uses the documented production controls.
