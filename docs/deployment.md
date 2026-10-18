# Deployment

The deployment guides already in this folder are authoritative; this page
ties them together.

| Situation | Read |
| --- | --- |
| A laptop or one classroom server, Python | `setup.md` |
| Docker / Docker Compose | `docker.md` |
| Real `.prg32` builds (toolchain on Docker, macOS, Linux, Windows) | `install_cartridge_build.md` |
| systemd service, environment file | `../examples/deploy/README.md` |
| Many students building at once | `concurrent_builds.md` |
| Accounts and single sign-on with a Cartridge Store | `accounts_and_sso.md` |
| CI and published container images | `ci_cd.md` |

## Production checklist

- Put the kit behind a reverse proxy with TLS; set `SECRET_KEY` (or keep the
  generated `data/secret_key` on a persistent volume).
- First admin: leave `PRG32_ADMIN_PASSWORD` unset and read
  `data/initial_admin_password`, or set a long random one. The Docker image
  runs with `PRG32_KIT_ENV=production` and refuses weak values
  (`admin-guide.md`).
- Behind a reverse proxy, set `PRG32_KIT_PROXY_COUNT` (sign-in limits,
  `security.md`) and `PRG32_KIT_SECURE_COOKIES=true` for HTTPS.
- Build the image with `--build-arg PRG32_KIT_REVISION=$(git rev-parse HEAD)`
  so build provenance names the kit's commit (CI does this).
- Use PostgreSQL through `DATABASE_URL` when more than one server process
  writes (`architecture.md`, *Persistence*).
- Back up the data folder (database, `builds/`, `artifacts/`). Students can
  also keep their own backups as project archives (`project_archive.md`).
- Only trusted users should compile C until per-build containers exist
  (`security.md`).

## Upgrading

Start the new version on the old data folder: missing tables
(`audit_events`, `auth_throttle`) are created and missing columns
(`project_revisions.child_ids`) added automatically, and running it twice is
harmless. Existing admins and passwords are kept. Take a backup first; see
`release-notes.md` for each release's notes and rollback.
