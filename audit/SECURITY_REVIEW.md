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

The project now specifies a private shared username plus a separate pseudonymous
public handle. The supplied Store patch has meaningful privacy, collision,
migration, notice and CSRF tests, and retained clean-clone runs pass. No privilege
escalation was observed. The canonical Store is still unpatched, so the default
integration suite fails and this remains supply-chain/integration work rather
than a closed gate.

## Build process limit

The build guard's previous container-visible `/proc` count could set RLIMIT_NPROC
below the UID-wide kernel count and prevent every build from starting on shared
Docker hosts. The repair probes the kernel, then adds only the configured build
allowance. Exact-SHA Linux CI demonstrated ordinary and concurrent real builds
beside 300 hidden same-UID processes, while the fork, disk, time and confinement
tests remained enforced. The broader residual risk remains that builds share a
host UID outside their mount namespaces.
