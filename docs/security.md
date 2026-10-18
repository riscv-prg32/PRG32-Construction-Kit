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
| Path disclosure | Build logs redacted; artifact paths never returned | `packager.py`, `routes.py` `public` |
| Secret exposure | Downloads never serve the database or `secret_key`; publish tokens hidden | `routes.py` `stored_file` |
| SSO forgery | HMAC-signed requests and one-time tickets | `sso_protocol.py` |
| Host files in handwritten assembly | Directive allow-list; no `include`/`incbin`/`_Pragma` words; only simple `#define` and `#if` lines; entry labels checked | `source_project.py` `validate_asm_source` |
| Malicious project archives | Size, entry-count and per-file limits; no `..`, absolute paths, backslashes, links or encryption; only manifest-listed files are read; imported project always owned by the importer | `project_format.py` |

## Threat model — open items

| Area | Risk | Plan |
| --- | --- | --- |
| Untrusted builds | GCC runs on the server without an OS sandbox | Container-per-build (ADR-0005) before guest or internet use |
| WASM runtime | Guest code in the browser | Interpreted in WASM; no host calls except the PRG32 ABI (ADR-0003) |
| OAuth / OIDC | No PKCE; users linked by provider + `sub`, not issuer | ADR-0007 |
| Cloud sync | Token storage, scope creep | Server-side tokens, minimal scopes, revocation (G6) |
| Rate limiting | Login and API are not rate limited | Reverse-proxy limits now; app limits in G6 |
| Audit log | No audit trail for admin actions | G6 |
| Plugins | None exist; none are loaded | Keep it that way until a design exists |

## Privacy

The kit stores usernames, e-mail addresses, password hashes, projects and
build logs. Project archives contain only the project (title, author field,
source, sprites, assets) — no account data. Retention, deletion on request
and data-processing notes for schools are a G6 deliverable.
