# Security review

No critical exploit was confirmed. OIDC uses PKCE, single-use state/nonce, signature and issuer/audience/time validation, bounded no-redirect metadata requests, issuer+subject identity, and explicit linking. Email equality cannot take over an account. Session epochs, expiry, scoped tokens, deactivation and audit events close important lifecycle gaps. Academic/class permissions are read-only where supervision is intended.

Guest work stays in IndexedDB and is never sent to anonymous server storage. Registered writes use atomic expected-version checks; quotas constrain account growth; retention is explicit and administrator-controlled. Existing CSP, vendoring, ownership, stale-window checks, Store egress policy and publish confirmation remain intact.

Residual risks: no live institutional IdP/SCIM/logout evidence; Store credentials remain recoverable server-side; no total build-root quota, per-build UID or confined AppArmor profile; Linux sandbox tests were unavailable locally; complex DWARF inputs warrant continued fuzzing; dependency hashes/SBOM and restoration exercises remain incomplete.
