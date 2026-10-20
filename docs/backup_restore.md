# Backing up and restoring the kit

Everything a kit keeps is in its data folder (`PRG32_KIT_DATA`, `/data` in Docker):
the database, `builds/`, `artifacts/` and `secret_key`. `tools/backup_restore.py`
backs it up while the kit runs, restores it into a clean folder, and checks the
result.

## Backing up

```bash
python3 tools/backup_restore.py backup --data /srv/prg32-kit/data --out kit-backup-2026-10-20.tar
```

- The database is copied with SQLite's online backup, so students can keep working.
- The archive contains password **hashes**, the session key (`secret_key`, which also
  protects stored cloud tokens) and Store tokens of publish profiles. Keep it as
  private as the server itself.
- With PostgreSQL (`DATABASE_URL`), back up the database with `pg_dump` and add
  `--skip-database` here for the folders.

## Restoring

```bash
python3 tools/backup_restore.py restore --archive kit-backup-2026-10-20.tar --data /srv/new/data
```

```bash
python3 tools/backup_restore.py verify --archive kit-backup-2026-10-20.tar --data /srv/new/data
```

- The target folder must be empty: the tool never mixes a backup into a running kit.
- Every file's SHA-256 is checked before anything is written; a damaged archive is
  refused.
- Artifacts remember their files by full path; the restore moves those paths from the
  old data folder to the new one.
- `verify` compares the row counts (accounts, projects, history, sprites, assets,
  artifacts, builds, publish profiles, school accounts, classes, cloud links) with the
  backup, checks that every artifact's file is there and inside the new folder and that
  every build's bundle exists, and starts the kit on the restored folder.

Then start the kit on the new folder (for Docker: mount it as `/data`).

## The restore drill

`tests/test_backup_restore.py` runs the whole drill on every test run: a kit with
accounts, a project with a sprite and history, and a compiled build is backed up
while running, restored into a clean folder elsewhere and verified; the student then
signs in with their password, sees the project and its history and downloads the
PRG32 cartridge. Damaged archives and non-empty folders are refused.

**Rollback of an upgrade:** stop the kit, restore the backup taken before the upgrade
into a clean folder, and start the previous version on it. Upgrades only add tables
and columns (`deployment.md`, *Upgrading*), so the previous version also runs on the
newer database, but restoring the backup is the safe way.
