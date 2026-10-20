"""Back up a kit's data folder, restore it into a clean one, and check the result (docs/backup_restore.md).

    python3 tools/backup_restore.py backup  --data /srv/prg32-kit/data --out kit-backup.tar
    python3 tools/backup_restore.py restore --archive kit-backup.tar --data /srv/new/data
    python3 tools/backup_restore.py verify  --archive kit-backup.tar --data /srv/new/data

SQLite deployments (the default). With PostgreSQL, back up the database with
``pg_dump`` and use this tool for the folders only (``--skip-database``).

- **backup** takes a consistent copy of the database while the kit runs (SQLite's
  online backup), the ``builds/`` and ``artifacts/`` folders and the ``secret_key``
  file (it signs sessions and encrypts cloud tokens: keep the archive private). A
  manifest records every file's SHA-256 and the row counts of the important tables.
- **restore** refuses a folder that is not empty, checks every hash before writing,
  and then rewrites the stored file paths of artifacts from the old data folder to
  the new one (they are absolute paths).
- **verify** compares the row counts with the manifest, checks that every artifact
  file exists inside the new folder and that every build's bundle artifact exists,
  and starts the kit on the restored folder.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sqlite3
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FORMAT = "prg32-kit-backup-1"
DATABASE = "construction_kit.sqlite"
FOLDERS = ("builds", "artifacts")
FILES = ("secret_key",)
COUNTED = ("users", "projects", "project_revisions", "sprites", "assets", "artifacts", "builds", "publish_profiles",
           "external_identities", "classes", "cloud_accounts", "cloud_links")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 - fixed names
            for table in COUNTED if table in tables}


def backup(data: Path, out: Path, database: Path | None, skip_database: bool) -> dict:
    data = data.resolve()
    entries: dict[str, str] = {}
    with tarfile.open(out, "w") as archive:
        def add(name: str, payload: bytes) -> None:
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(payload), 0o600, 0
            archive.addfile(info, io.BytesIO(payload))
            entries[name] = sha256(payload)

        manifest: dict = {"format": FORMAT, "data_dir": str(data), "counts": {}}
        if not skip_database:
            source = sqlite3.connect(database or data / DATABASE)
            with tempfile.TemporaryDirectory() as folder:
                copy = sqlite3.connect(Path(folder) / DATABASE)
                source.backup(copy)            # consistent even while the kit writes
                manifest["counts"] = counts(copy)
                copy.close()
                add(DATABASE, (Path(folder) / DATABASE).read_bytes())
            source.close()
        for name in FILES:
            if (data / name).is_file():
                add(name, (data / name).read_bytes())
        for folder_name in FOLDERS:
            for path in sorted((data / folder_name).rglob("*")) if (data / folder_name).is_dir() else []:
                if path.is_file() and not path.is_symlink() and ".slots" not in path.parts and ".budget" not in path.parts:
                    add(path.relative_to(data).as_posix(), path.read_bytes())
        manifest["files"] = entries
        add("MANIFEST.json", json.dumps(manifest, indent=1, sort_keys=True).encode())
    return manifest


def read_archive(archive_path: Path) -> tuple[dict, dict[str, bytes]]:
    files: dict[str, bytes] = {}
    with tarfile.open(archive_path, "r") as archive:
        for member in archive.getmembers():
            name = member.name
            if not member.isfile() or name.startswith("/") or ".." in Path(name).parts:
                raise SystemExit(f"refused: the archive has an unsafe entry {name!r}")
            files[name] = archive.extractfile(member).read()
    manifest = json.loads(files.pop("MANIFEST.json"))
    if manifest.get("format") != FORMAT:
        raise SystemExit("refused: not a PRG32-Construction-Kit backup")
    if set(files) != set(manifest["files"]):
        raise SystemExit("refused: the archive's files do not match its manifest")
    for name, payload in files.items():
        if sha256(payload) != manifest["files"][name]:
            raise SystemExit(f"refused: {name} does not match its SHA-256 (damaged or changed archive)")
    return manifest, files


def restore(archive_path: Path, data: Path) -> dict:
    manifest, files = read_archive(archive_path)          # everything checked before anything is written
    data = data.resolve()
    if data.exists() and any(data.iterdir()):
        raise SystemExit(f"refused: {data} is not empty; restore into a clean folder")
    data.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        target = data / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        os.chmod(target, 0o600)
    database = data / DATABASE
    if database.is_file():
        old, new = manifest["data_dir"].rstrip("/") + "/", str(data).rstrip("/") + "/"
        connection = sqlite3.connect(database)
        rows = connection.execute("SELECT id, path, metadata FROM artifacts").fetchall()
        for row_id, path, metadata in rows:
            path = new + path[len(old):] if path and path.startswith(old) else path
            metadata = (metadata or "{}").replace(json.dumps(old)[1:-1], json.dumps(new)[1:-1])
            connection.execute("UPDATE artifacts SET path = ?, metadata = ? WHERE id = ?", (path, metadata, row_id))
        connection.commit()
        connection.close()
    return manifest


def verify(archive_path: Path, data: Path) -> list[str]:
    manifest, _files = read_archive(archive_path)
    data = data.resolve()
    problems = []
    connection = sqlite3.connect(data / DATABASE)
    restored = counts(connection)
    for table, count in manifest["counts"].items():
        if restored.get(table) != count:
            problems.append(f"{table}: {restored.get(table)} rows, the backup had {count}")
    for row_id, path in connection.execute("SELECT id, path FROM artifacts WHERE path != ''"):
        resolved = Path(path).resolve()
        if not str(resolved).startswith(str(data) + os.sep):
            problems.append(f"artifact {row_id} points outside the restored folder")
        elif not resolved.is_file():
            problems.append(f"artifact {row_id}: its file is missing")
    for build_id, bundle in connection.execute("SELECT id, bundle_artifact_id FROM builds WHERE bundle_artifact_id IS NOT NULL"):
        if connection.execute("SELECT 1 FROM artifacts WHERE id = ?", (bundle,)).fetchone() is None:
            problems.append(f"build {build_id}: its bundle artifact is missing")
    connection.close()
    sys.path.insert(0, str(ROOT))
    from prg32_construction_kit import create_app

    app = create_app({"DATA_DIR": data, "DB_PATH": data / DATABASE, "BUILD_ROOT": data / "builds",
                      "ARTIFACT_ROOT": data / "artifacts", "SQLALCHEMY_DATABASE_URI": f"sqlite:///{data / DATABASE}"})
    # Starting the app opened the database (admin check, migrations); the sign-in page answers.
    answer = app.test_client().get("/auth/login")
    if answer.status_code != 200:
        problems.append(f"the kit does not start on the restored folder (sign-in page answered {answer.status_code})")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("backup")
    make.add_argument("--data", type=Path, required=True)
    make.add_argument("--database", type=Path, help="if the database is not <data>/construction_kit.sqlite")
    make.add_argument("--skip-database", action="store_true", help="PostgreSQL: back it up with pg_dump")
    make.add_argument("--out", type=Path, required=True)
    for name in ("restore", "verify"):
        command = commands.add_parser(name)
        command.add_argument("--archive", type=Path, required=True)
        command.add_argument("--data", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "backup":
        manifest = backup(args.data, args.out, args.database, args.skip_database)
        print(f"Wrote {args.out}: {len(manifest['files'])} files, rows {manifest['counts']}")
        return 0
    if args.command == "restore":
        restore(args.archive, args.data)
        print(f"Restored into {args.data.resolve()}; now run: verify --archive {args.archive} --data {args.data}")
        return 0
    problems = verify(args.archive, args.data)
    for problem in problems:
        print("PROBLEM: " + problem)
    print("restore verified" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
