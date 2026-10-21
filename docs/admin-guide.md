# Admin guide

1. **Install:** `deployment.md` (it links the detailed guides).
2. **First sign-in:** see *The first admin* below.
3. **Settings:** the **Settings** menu item changes access, maintenance mode, email,
   appearance, classroom limits, privacy contacts, Store and cloud, and build limits without a
   restart: `admin_settings.md`.
4. **Users, roles and groups:** `accounts_and_sso.md`. The **Users** page is
   for admins.
5. **Single sign-on with a Cartridge Store:** `accounts_and_sso.md`.
6. **Builds under load:** `concurrent_builds.md`; tune
   `PRG32_MAX_PARALLEL_BUILDS`, `PRG32_BUILD_QUEUE_TIMEOUT` and
   `PRG32_BUILD_TIMEOUT`.
7. **What made a cartridge:** `build_provenance.md`. **How compiles are isolated:** `build_sandbox.md`.
8. **Project history and deleted projects:** `project_history.md`; tune
   `PRG32_KIT_MAX_REVISIONS`. Admins can delete a project for good from
   Recently deleted.
9. **Sign-in limits and the audit log:** below, and `security.md`.
10. **What is planned:** `implementation-plan.md`, `implementation-status.md`.

## The first admin

The kit has **no default password**. The first start, while no admin exists:

| `PRG32_ADMIN_PASSWORD` | Development (`python app.py`) | Production (`PRG32_KIT_ENV=production`, the Docker image) |
| --- | --- | --- |
| unset | random password in `<data>/initial_admin_password` | the same |
| long and not well known | used | used |
| short (< 10) or well known (`password`, `change-me-before-class`, …) | used, with an `INSECURE` warning in the log | **refused: the server does not start** |

- Read the random password with `cat data/initial_admin_password`
  (Docker: `docker compose exec prg32-construction-kit cat /data/initial_admin_password`).
- Sign in as `admin`, then change the password on **My account**. The file
  is deleted as soon as an admin sets a new password.
- Passwords are never written to the log, and the file is never served as a
  download.
- Nothing happens on later starts, or once the account is renamed or
  deleted while another admin exists.
- There is no password-reset back door. If no admin can sign in any more,
  restore a database backup (and keep backups for that reason).

## Publishing to a Store

The kit only sends bundles to Stores you approve (ADR-0008, audit finding H-01):

| Variable | Meaning |
| --- | --- |
| `PRG32_STORE_ALLOWED_ORIGINS` | Comma-separated origins, e.g. `https://store.school.example`. Unset: the origins of `PRG32_STORE_URL` and `PRG32_SSO_PEER_URL`. |
| `PRG32_STORE_TRUSTED_LOCAL` | `1` when the Store is on the school's private network or the same machine. Without it, Stores resolving to loopback/private addresses are refused. |
| `PRG32_STORE_CA_BUNDLE` | A CA file for a Store with a school-issued certificate. |

Rules that always apply: https (plain http only with `PRG32_STORE_TRUSTED_LOCAL=1`
on a non-production server), no user name/password/query/fragment in the URL,
no numeric tricks like `2130706433`, link-local and metadata addresses
(`169.254.169.254`) never, no redirects, 5 s connect / 30 s read timeouts,
at most 64 KiB of the Store's answer read. Every allowed and refused attempt
is in the audit log (action `publish`, `metadata.reason`).

A developer laptop with a Store on `http://127.0.0.1:5080`: set
`PRG32_STORE_TRUSTED_LOCAL=1` (and keep `PRG32_KIT_ENV` unset or
`development`).

## Sign-in limits

Wrong passwords, registration requests and new API tokens are limited (see
`security.md` for the numbers). A class sharing one address is fine: wrong
passwords lock only *that username from that address*, for 15 minutes.

To unlock everybody at once (for example after a lesson where the class mistyped
a shared password), send, as an admin:

```bash
curl -X DELETE -H "Authorization: Bearer <admin API token>" http://kit.example/api/admin/throttles
```

Behind nginx, Caddy or Traefik, set `PRG32_KIT_PROXY_COUNT` to the number of
proxies, or every student looks like the proxy's address.

## Audit log

`GET /api/admin/audit` (admins only) lists security events, newest first:
user created/updated/deleted, role and group changes, password changes, API
tokens created/revoked, the first-admin bootstrap, registrations, sign-in
locks, publishing attempts and results, single-sign-on syncs and throttle
clearing. Each event has the actor, action, target, time, outcome, client
address and short safe metadata. Passwords, tokens, tickets and cookies are
never stored. Filters: `?action=user_create&limit=100&before=<id>`.
