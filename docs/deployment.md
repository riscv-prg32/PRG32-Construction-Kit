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
- Change the default admin password (`PRG32_ADMIN_PASSWORD`).
- Use PostgreSQL through `DATABASE_URL` when more than one server process
  writes (`architecture.md`, *Persistence*).
- Back up the data folder (database, `builds/`, `artifacts/`). Students can
  also keep their own backups as project archives (`project_archive.md`).
- Only trusted users should compile C until per-build containers exist
  (`security.md`).

## Upgrading

The full-IDE work so far needs no database migration. See
`release-notes.md` for each release's notes.
