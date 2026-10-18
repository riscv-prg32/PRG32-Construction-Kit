# Security review

## Overall

Baseline security is stronger than the prior audit: the Store SSRF, unauthorized publishing and unsandboxed production compilation findings are addressed. No critical exploit was confirmed. The application is still not proven ready for a hostile multi-tenant Full IDE deployment because academic identity, guest/cloud storage, quotas, browser policy and operational validation are incomplete.

## Authentication and authorization

Passwords and API tokens are hashed; tokens are returned once. Cookie and stale-window controls exist. Owner-scoped CRUD and shared-read-only semantics have negative tests. Publishing now checks `role_at_least(..., "publisher")` before resource access (`routes.py:1004-1011`) and binds explicit confirmation to a time-limited content digest (`publishing.py:149-176`).

OIDC remains below the required profile: one environment-configured provider, no explicit PKCE, issuer is not part of the stored external identity, no multi-provider admin configuration/claim mapping, and no executed issuer/audience/JWKS/logout lifecycle matrix (`auth_adapters.py:41-81`). Generic ordered roles do not provide course-scoped student/TA/teacher administration (`auth.py:49-55`).

## Build and upload boundary

Archive validation and C/assembly allow-lists are defense in depth. Production compilation is now designed to run through bubblewrap with isolated namespaces, read-only dependencies, no network, cleared secrets, one writable build directory, seccomp, rlimits and process-group timeout. Production refuses fallback (`build_sandbox.py:17-20`; `packager.py:140-160`). Remaining gaps are total build-directory quota, per-build UID, AppArmor portability, and lack of this audit's independent Linux/container rerun.

## Store, browser and data

Store egress is origin/address constrained and publish is reviewed/idempotent. No live Store was contacted. Templates generally escape values, but no CSP was found and CDN scripts/styles lack local pinning/SRI (`templates/base.html:12-13,60-61`; `templates/editor.html:137`). Publish bearer tokens remain reversibly stored in the database; use encryption or delegated short-lived credentials.

Guest IndexedDB, Drive and OneDrive do not exist, so their scopes, consent, refresh/revoke, conflicts and eviction cannot be assessed. Registered storage lacks quotas and retention/deprovisioning. Audit-log retention/export/tamper resistance is unspecified. Dependencies are bounded but not hash-locked; CI reviews dependency changes but does not produce a full recurring SBOM/vulnerability inventory.
