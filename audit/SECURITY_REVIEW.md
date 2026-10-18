# Security review

## Overall assessment

The application has solid baseline controls for a classroom prototype: password hashing, hashed API tokens, secure bootstrap rules, request throttling, owner-scoped CRUD, account-switch refusal, audit events, upload size limits, path redaction, deterministic archive parsing, and signed Store peer synchronization. Automated negative tests substantiate many of these claims.

It is not ready for hostile multi-user deployment because the compiler trust boundary and publisher authorization remain open. The former Store-egress SSRF boundary is now substantially hardened and independently verified.

## Authentication and sessions

- Local passwords use hashes; API tokens are only returned once and stored hashed (`auth.py:820-836`). Cookies are HttpOnly and SameSite=Lax; Secure defaults false outside configured deployment (`config.py:60-65`).
- JSON/custom-header CSRF defense and stale-window `X-PRG32-User` refusal exist (`auth.py:603-625`). This is useful but should be complemented by a clear same-origin/CSP policy and tests for all mutation verbs/content types.
- OIDC uses Authlib discovery but does not meet the demanded explicit PKCE/multi-IdP/issuer+subject/admin configuration profile (`auth_adapters.py:41-81`). No live issuer/audience/JWKS/nonce rotation matrix was run.
- Store peer tickets are short-lived and nonce-tracked; protocol identity matches the local Store file. Store tokens are not IDE session cookies.

## Authorization and tenant isolation

Owner filtering and shared-read-only behavior are implemented in `routes.py:72-130` and exercised by tests. Artifact host paths and publish tokens are removed from public responses (`routes.py:139-187`).

RBAC is too coarse for the requested academic model. `reader/user/player/publisher/admin` is a level hierarchy, not scoped student/TA/teacher administration. Most CRUD is authenticated-owner based, while publish fails to require `publisher`. This is H-02.

## Build/upload sandbox

Archive validation rejects traversal/symlinks/oversized entries. Handwritten assembly uses a directive allow-list and blocks file-reading directives. Advanced C restricts headers/directives/inline assembly. These are valuable layers.

They are not a process sandbox. The compiler runs with the web service's user, inherited environment and network access (`packager.py:117-150`). A private TMPDIR prevents accidental cross-build temp collisions but does not prevent reads outside the build or exploitation of compiler/toolchain vulnerabilities. Containerize each build with cgroups, no network, read-only SDK, non-root UID and seccomp.

## OAuth/cloud/guest privacy

Guest storage, Google Drive and OneDrive do not exist, so their consent, refresh/revoke, scopes, conflicts and eviction behavior cannot be evaluated. Registered storage has no documented quota/retention/deprovisioning enforcement. These are missing requirements, not N/A.

## SSRF, XSS and dependencies

- Former H-01 is closed: `store_policy.py` enforces approved origins, URL/address validation and pinned connections; `publisher.py` disables redirects, verifies TLS hostnames and bounds/sanitizes responses. All 94 Store-egress tests passed. Production configuration and a live public Store remain untested.
- Templates generally use Jinja escaping and dynamic JS commonly calls `Kit.escape`; no exploitable stored XSS was demonstrated. A CSP was not found, and remote scripts/styles lack SRI (`templates/base.html:12-13,60-61`; `editor.html:137`).
- Python dependencies use ranges rather than hash locks. CI dependency review covers PR diffs, not a scheduled full inventory/SBOM.

## Secrets, logs and audit

Publish bearer tokens are hidden from API responses (`routes.py:155-159`), build paths/secret-looking options are redacted, API tokens are hashed, and security events avoid secret values. Publish profiles nevertheless store bearer tokens reversibly in SQLite (`db.py:121-135`); encrypt them with a deployment-managed key or replace them with delegated short-lived credentials. Audit retention, export, tamper resistance and deprovisioning are unspecified.
