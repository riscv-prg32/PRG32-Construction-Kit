"""A restore drill (tools/backup_restore.py, docs/backup_restore.md).

A kit with accounts, a project with a sprite, a compiled build (bundle and cartridges)
and its history is backed up while running, restored into a clean folder somewhere
else, verified, and used: the student signs in, sees the project and downloads the
cartridge. Damaged archives and non-empty folders are refused before anything is written.
"""

from __future__ import annotations

import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace

import pytest
from conftest import ADMIN_PASSWORD, make_app

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import backup_restore  # noqa: E402

CARTRIDGE = b"PRG2" + b"\x07" * 60


@pytest.fixture()
def kit(tmp_path, monkeypatch):
    from prg32_construction_kit.sample_data import default_blocks

    def fake(command, **_kwargs):
        with open(command[command.index("--out") + 1], "wb") as out:
            out.write(CARTRIDGE)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    data = tmp_path / "old" / "data"
    data.mkdir(parents=True)
    app = make_app(data, DB_PATH=data / "construction_kit.sqlite", BUILD_ROOT=data / "builds",
                   ARTIFACT_ROOT=data / "artifacts", SQLALCHEMY_DATABASE_URI=f"sqlite:///{data / 'construction_kit.sqlite'}")
    admin = app.test_client()
    admin.post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": "ada-password-123",
                                   "role": "user"})
    ada = app.test_client(login=("ada", "ada-password-123"))
    project = ada.post("/api/projects", json={"title": "Backed Up", "blocks_json": default_blocks()}).get_json()
    ada.post("/api/sprites", json={"project_id": project["id"], "name": "hero", "width": 8, "height": 8,
                                   "pixels": [0] * 64})
    ada.put(f"/api/projects/{project['id']}", json={"blocks_json": {"changed": 1}, "expected_version": project["version"]})
    built = ada.post(f"/api/projects/{project['id']}/package", json={}).get_json()
    return SimpleNamespace(data=data, app=app, project=project, built=built, tmp=tmp_path)


def test_backup_restore_verify_and_use(kit):
    archive = kit.tmp / "kit-backup.tar"
    manifest = backup_restore.backup(kit.data, archive, None, False)    # while the kit is running
    assert manifest["counts"]["projects"] >= 1 and manifest["counts"]["artifacts"] >= 3   # with the seeded examples
    new = kit.tmp / "elsewhere" / "restored"
    backup_restore.restore(archive, new)
    assert backup_restore.verify(archive, new) == []
    app = make_app(new, DB_PATH=new / "construction_kit.sqlite", BUILD_ROOT=new / "builds",
                   ARTIFACT_ROOT=new / "artifacts", SQLALCHEMY_DATABASE_URI=f"sqlite:///{new / 'construction_kit.sqlite'}")
    ada = app.test_client(login=("ada", "ada-password-123"))       # password hashes came back
    projects = ada.get("/api/projects").get_json()["projects"]
    assert "Backed Up" in [item["title"] for item in projects]
    assert ada.get(f"/api/projects/{kit.project['id']}/revisions").get_json()["revisions"]
    assert ada.get(f"/api/sprites?project_id={kit.project['id']}").get_json()["sprites"][0]["name"] == "hero"
    cartridge = kit.built["cartridge_artifacts"][0]
    download = ada.get(f"/api/artifacts/{cartridge['id']}/download")
    assert download.status_code == 200 and download.data == CARTRIDGE      # the file, found at its new place
    assert app.test_client(login=("admin", ADMIN_PASSWORD)).get("/api/users").status_code == 200


def test_a_damaged_archive_is_refused_before_anything_is_written(kit):
    archive = kit.tmp / "kit-backup.tar"
    backup_restore.backup(kit.data, archive, None, False)
    damaged = kit.tmp / "damaged.tar"
    with tarfile.open(archive) as source, tarfile.open(damaged, "w") as target:
        for member in source.getmembers():
            payload = source.extractfile(member).read()
            if member.name.endswith(".prg32"):
                payload = b"PRG2" + b"\x00" * 60
            member.size = len(payload)
            import io

            target.addfile(member, io.BytesIO(payload))
    new = kit.tmp / "never"
    with pytest.raises(SystemExit, match="SHA-256"):
        backup_restore.restore(damaged, new)
    assert not new.exists()


def test_restore_refuses_a_folder_that_is_not_empty(kit):
    archive = kit.tmp / "kit-backup.tar"
    backup_restore.backup(kit.data, archive, None, False)
    with pytest.raises(SystemExit, match="not empty"):
        backup_restore.restore(archive, kit.data)


def test_verify_finds_a_missing_file(kit):
    archive = kit.tmp / "kit-backup.tar"
    backup_restore.backup(kit.data, archive, None, False)
    new = kit.tmp / "restored"
    backup_restore.restore(archive, new)
    next((new / "builds").rglob("*.prg32")).unlink()
    assert any("file is missing" in problem for problem in backup_restore.verify(archive, new))
