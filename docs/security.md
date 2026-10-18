# Security

How the kit protects classrooms today, the threats it is designed against,
and what is still open. Reporting: contact the maintainers privately.

## Controls in place

| Threat | Control | Where |
| --- | --- | --- |
| Unauthenticated access | Every page and `/api/` route except sign-in, static, docs and discovery needs a signed-in user | `auth.py` |
| IDOR between students | Items have `owner_id`; reads/writes checked per item; shared items read-only | `routes.py` `can_read`/`can_write` |
| CSRF / stale windows | Non-JSON POSTs need the `X-PRG32-Kit` header (another site cannot add it); `409 user_changed` when the window's user differs | `auth.py`, `static/js/app.js` |
| Host files in C builds | Include allow-list, no inline asm, `_Pragma`, `__has_include`, token pasting | `source_project.py` |
| Build interference / exhaustion | Per-build folders, build slots, queue timeout, compile timeout | `build_slots.py`, `packager.py` |
| Path disclosure | Build folder shown as `<build>`, other absolute folders dropped from logs; the build command shown by program name; artifact paths and `source_path` never returned | `packager.py` `redact_build_path`/`public_command`, `routes.py` `public`/`public_build_result` |
| Secret exposure | Downloads never serve the database, `secret_key` or `initial_admin_password`; publish tokens hidden; secret-looking build-command options hidden | `routes.py` `stored_file`, `packager.py` |
| Well-known admin password | No built-in default; random first-admin password in a 0600 file; production refuses weak `PRG32_ADMIN_PASSWORD`; never re-created after rename/delete; passwords never logged | `auth.py` `bootstrap_admin` |
| Password guessing, registration and token abuse | Database-backed limits (shared by all workers); `429` + `Retry-After`; same answer for known and unknown names; only hashes of names/addresses stored | `security.py`, `auth.py` |
| Untraceable admin actions | Audit log of account, role, group, token, bootstrap, publish, SSO-sync and unlock actions; admin-only API; secret-looking metadata dropped | `security.py` `record`, `GET /api/admin/audit` |
| SSRF through publishing (audit H-01) | Admin allow-list of Store origins; https; strict URL parsing (no credentials, numeric-IP tricks); every resolved address must be public unless `PRG32_STORE_TRUSTED_LOCAL`; connection pinned to the checked address; no redirects; timeouts; 64 KiB answer cap; student-safe errors; audited | `store_policy.py`, `publisher.py`, ADR-0008 |
| Untrusted compilers (audit H-03) | Every compile in bubblewrap: all namespaces unshared, no network, read-only system/SDK/compiler, only its build folder writable, fresh `/tmp`, no `/proc`, read-only root, cleared environment, no capabilities, kit seccomp filter; guard limits (CPU, memory, processes, file size, open files), timeout kills the whole group; production refuses builds without it | `build_sandbox.py`, `build_guard.py`, `docker/seccomp-kit.json`, ADR-0010 |
| Publishing without approval (audit H-02) | `publisher`/`admin` role checked in the backend; only publishable bundles with real `PRG2` cartridges matching the build; signed, expiring review token bound to the summary digest, user, profile and bundle; explicit `confirm`; one attempt per review (no double upload); audited by stage | `publishing.py`, `routes.api_publish_review`/`api_publish`, ADR-0009 |
| Script injection, third-party code (audit M-02) | All libraries vendored and pinned with integrity/licence records; strict CSP (`script-src 'self' 'wasm-unsafe-eval'`, no inline scripts or `unsafe-*`, styles only `'self'` + Blockly's two stylesheet hashes, `object-src 'none'`, `frame-ancestors 'none'`); `no-store` on pages and API | `prg32_construction_kit/__init__.py` `content_security_policy`, `static/vendor/VENDOR.json`, ADR-0012 |
| Unexplained cartridges | Build provenance with SHA-256 of source and every cartridge | `provenance.py`, `build_provenance.md` |
| SSO forgery | HMAC-signed requests and one-time tickets | `sso_protocol.py` |
| Host files in handwritten assembly | Directive allow-list; no `include`/`incbin`/`_Pragma` words; only simple `#define` and `#if` lines; entry labels checked | `source_project.py` `validate_asm_source` |
| Malicious project archives | Size, entry-count and per-file limits; no `..`, absolute paths, backslashes, links or encryption; only manifest-listed files are read; imported project always owned by the importer | `project_format.py` |

## Threat model — open items

| Area | Risk | Plan |
| --- | --- | --- |
| Build sandbox gaps | No total disk quota per build folder, no per-build UID, AppArmor hosts need `apparmor=unconfined` today | Tailored AppArmor profile; quotas (Phase 7) |
| WASM runtime | Guest code in the browser | Interpreted in WASM; no host calls except the PRG32 ABI (ADR-0003) |
| OAuth / OIDC | No PKCE; users linked by provider + `sub`, not issuer | ADR-0007 |
| Cloud sync | Token storage, scope creep | Server-side tokens, minimal scopes, revocation (G6) |
| Rate limiting | Only sign-in, registration and token creation are limited; other API routes (builds have their own slots) are not | Reverse-proxy limits for the whole site |
| Audit log | No retention limit or export; the log lives in the same database an admin controls | Retention policy and off-host export (G6) |
| SSO | Records synced from the Cartridge Store are not audited one by one (only manual syncs) | Decide with CartridgeStore |
| Plugins | None exist; none are loaded | Keep it that way until a design exists |

## Sign-in limits

| Limit | Default | Counted per | Variable |
| --- | --- | --- | --- |
| Wrong passwords for one name | 5 per 15 min | address + username | `PRG32_KIT_THROTTLE_LOGIN_USER` |
| Wrong passwords, any name | 100 per 15 min | address | `PRG32_KIT_THROTTLE_LOGIN_ADDRESS` |
| Registration requests | 10 per hour | address | `PRG32_KIT_THROTTLE_REGISTER_ADDRESS` |
| Registration requests | 3 per hour | e-mail address | `PRG32_KIT_THROTTLE_REGISTER_EMAIL` |
| Invalid registration links | 20 per hour | address | `PRG32_KIT_THROTTLE_REGISTER_COMPLETE` |
| New API tokens | 20 per hour | user | `PRG32_KIT_THROTTLE_TOKEN_CREATE` |

Values are `attempts/seconds`, e.g. `PRG32_KIT_THROTTLE_LOGIN_USER=5/900`.
A successful sign-in resets that name's count. Counters expire by
themselves; an admin can clear all of them (`DELETE /api/admin/throttles`).

**Addresses and proxies.** The address is the TCP peer. `X-Forwarded-For`
is used only when `PRG32_KIT_PROXY_COUNT=N`; the kit then takes the N-th
entry from the end (the one your own proxy added), so a client cannot forge
it. A reverse proxy may add its own, coarser limits; keep them above the
kit's so students see the kit's explanation instead of a bare proxy error.
SSO and OIDC/SAML sign-ins are limited by the identity provider, not here.

## Threat boundaries

- **Trusted:** the server operator, admins (they can read everything and the
  audit log), the PRG32 SDK and compiler installed on the server.
- **Untrusted:** students' Blocks, C, assembly and archives (validated, but
  compiled by the real GCC without an OS sandbox), uploaded files, browsers,
  anything in `X-Forwarded-For` unless a proxy is configured.
- **Outside the kit:** the Cartridge Store's own review and authentication,
  identity providers, and the TLS/reverse-proxy layer.

## Privacy

The kit stores usernames, e-mail addresses, password hashes, projects,
build logs, and audit events (actor name, client address, and for account
changes the old and new username/e-mail/role/groups). Throttle counters keep
only hashes. Project archives contain only the project (title, author field,
source, sprites, assets) — no account data. Retention, deletion on request
and data-processing notes for schools are a G6 deliverable.
