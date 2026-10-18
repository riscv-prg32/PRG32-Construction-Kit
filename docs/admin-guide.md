# Admin guide

1. **Install:** `deployment.md` (it links the detailed guides).
2. **First sign-in:** see *The first admin* below.
3. **Users, roles and groups:** `accounts_and_sso.md`. The **Users** page is
   for admins.
4. **Single sign-on with a Cartridge Store:** `accounts_and_sso.md`.
5. **Builds under load:** `concurrent_builds.md`; tune
   `PRG32_MAX_PARALLEL_BUILDS`, `PRG32_BUILD_QUEUE_TIMEOUT` and
   `PRG32_BUILD_TIMEOUT`.
6. **What made a cartridge:** `build_provenance.md`.
7. **Project history and deleted projects:** `project_history.md`; tune
   `PRG32_KIT_MAX_REVISIONS`. Admins can delete a project for good from
   Recently deleted.
8. **Sign-in limits and the audit log:** below, and `security.md`.
9. **What is planned:** `implementation-plan.md`, `implementation-status.md`.

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
