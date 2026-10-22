# Security review

No new critical security issue was confirmed. The compiler-on-save path first applies the existing C/assembly validators, runs in an isolated build directory and returns sanitized diagnostics without preserving a build. Live Store evidence confirms one-time sign-on/upload tickets reject reuse and forgery, while publisher authorization remains enforced by the Kit.

AudioStudio retains ownership, conflict, quota and bounded-data validation. Patch tests operate on clean copies rather than mutating neighboring repositories. Buzzer compatibility remains silent and reserved rather than repurposing ABI slots.

Residual risks remain: builds share a host UID outside Linux namespaces; institutional/cloud tenants are untested; upstream patch supply-chain adoption is pending; and physical target resource behavior has not been observed. The recorded PRG32-QT delivery also deserves a small evidence-tool review because asynchronous runtime state must always be tied unambiguously to the cartridge just selected.

## GDPR and privacy

`GDPR-01` scores **3/4** but remains a hard release blocker. The code now has
meaningful tests for a complete per-person export, request deadlines and identity
verification, erasure across every classified table and file, provider token
revocation, restriction, pseudonymised audit continuity, backup re-erasure and
retention. Notices are versioned and recorded. The generated ROPA covers every
database table plus browser, file, provider, Store, log, backup and evidence stores.

The missing point is operational/legal demonstration for the actual deployment.
`docs/privacy/decisions.md` leaves the controller, applicable legal bases,
Member-State children's rules, retention choices, processor contracts, transfers,
DPIA, DPO/counsel approval and staffed breach exercise open. The technical
rehearsal is useful but is not the required controller/DPO tabletop.

Therefore this audit makes no claim of GDPR certification or legal
non-compliance. It finds that the release has insufficient technical,
operational and legal evidence to pass the expressly required gate.

## Shared-account interoperability

Fresh execution found one regression in the adjacent CartridgeStore contract.
Credentials and authentication succeed, but the Store exposes a generated
`player-*` username instead of the Kit username. No privilege escalation was
observed, but identity display/mapping semantics now disagree with the committed
test and must be reconciled before claiming reference-verified shared accounts.
