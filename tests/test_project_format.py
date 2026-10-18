from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pytest

from prg32_construction_kit import project_format as pf
from prg32_construction_kit.sample_data import default_blocks

ROOT = Path(__file__).resolve().parent.parent
C_SOURCE = """#include "prg32.h"
void c_game_init(void) {}
void c_game_update(void) {}
void c_game_draw(void) { prg32_gfx_clear(0); }
"""


def make_zip(files: dict[str, bytes | str], mode: int | None = None) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            info = zipfile.ZipInfo(name)
            if mode is not None:
                info.external_attr = mode << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def manifest(**extra) -> str:
    base = {"schema": pf.SCHEMA, "schema_version": 1, "title": "Zip Game", "authoring_mode": "blocks",
            "source": "src/blocks.json", "assets": []}
    return json.dumps({**base, **extra})


def upload(client, data: bytes, name: str = "game.prg32project.zip"):
    return client.post("/api/projects/import", data={"file": (io.BytesIO(data), name)},
                       content_type="multipart/form-data")


def blocks_project(client, title="Archive Game"):
    project = client.post("/api/projects", json={"title": title, "author": "Ada", "description": "d",
                                                 "tags": ["t"], "blocks_json": default_blocks()}).get_json()
    client.post("/api/sprites", json={"project_id": project["id"], "name": "Ship", "width": 2, "height": 1,
                                      "pixels": [["#ffffff", "transparent"]]})
    client.post("/api/sprites", json={"project_id": project["id"], "name": "Ship", "width": 1, "height": 1,
                                      "pixels": [["#ff0000"]]})
    client.post("/api/assets", json={"project_id": project["id"], "name": "Level 1", "data": {"rows": [1, 2]}})
    return project


def test_sdk_abi_matches_the_prg32_sdk_when_installed():
    abi = pytest.importorskip("prg32.abi.abi_generated")
    assert (abi.ABI_MAJOR, abi.ABI_MINOR, f"0x{abi.ABI_HASH:08x}") == (
        pf.SDK_ABI["major"], pf.SDK_ABI["minor"], pf.SDK_ABI["hash"])


def test_manifest_describes_a_blocks_project(client):
    project = blocks_project(client)
    data = client.get(f"/api/projects/{project['id']}/manifest").get_json()
    assert data["schema"] == "prg32-project" and data["schema_version"] == 1
    assert data["authoring_mode"] == "blocks" and data["source"] == "src/blocks.json"
    assert data["entry_points"] == {"prefix": "archive_game", "init": "archive_game_init",
                                    "update": "archive_game_update", "draw": "archive_game_draw"}
    assert [entry["path"] for entry in data["assets"]] == [
        "assets/sprites/01-ship.json", "assets/sprites/02-ship.json", "assets/data/01-level-1.json"]
    assert data["sdk"]["hash"] == "0x260f6136"


def test_archive_is_deterministic_and_holds_only_source(client):
    project = blocks_project(client)
    first = client.get(f"/api/projects/{project['id']}/archive")
    assert first.status_code == 200
    assert "archive-game.prg32project.zip" in first.headers["Content-Disposition"]
    assert first.data == client.get(f"/api/projects/{project['id']}/archive").data
    names = zipfile.ZipFile(io.BytesIO(first.data)).namelist()
    assert names[0] == pf.MANIFEST_NAME
    assert names[1:] == sorted(names[1:])
    assert not any(name.endswith((".c", ".S", ".prg32")) for name in names)  # generated code is derived


def test_archive_round_trip_keeps_blocks_sprites_and_assets(client):
    project = blocks_project(client)
    data = client.get(f"/api/projects/{project['id']}/archive").data
    response = upload(client, data)
    assert response.status_code == 201, response.get_json()
    imported = response.get_json()
    assert imported["id"] != project["id"] and imported["ignored_files"] == []
    assert imported["blocks_json"] == project["blocks_json"]
    assert imported["title"] == "Archive Game" and imported["tags"] == ["t"]
    sprites = client.get(f"/api/sprites?project_id={imported['id']}").get_json()["sprites"]
    assert sorted(sprite["width"] for sprite in sprites) == [1, 2]
    assets = client.get(f"/api/assets?project_id={imported['id']}").get_json()["assets"]
    assert assets[0]["data"] == {"rows": [1, 2]}
    # Exporting the copy gives the same files again.
    again = client.get(f"/api/projects/{imported['id']}/archive").data
    assert again == data


def test_advanced_c_archive_round_trip(client):
    project = client.post("/api/projects", json={
        "title": "C Game", "blocks_json": {},
        "game_json": {"source_mode": "c", "source_c": C_SOURCE, "required_features": ["sprites"]}}).get_json()
    data = client.get(f"/api/projects/{project['id']}/archive").data
    files = zipfile.ZipFile(io.BytesIO(data))
    assert files.read("src/game.c").decode() == C_SOURCE
    meta = json.loads(files.read(pf.MANIFEST_NAME))
    assert meta["authoring_mode"] == "c" and meta["required_features"] == ["sprites"]
    imported = upload(client, data).get_json()
    assert imported["game_json"] == {"source_mode": "c", "source_c": C_SOURCE, "required_features": ["sprites"]}


def test_legacy_json_export_is_migrated(client):
    legacy = json.loads((ROOT / "examples" / "games" / "pong.json").read_text())
    response = upload(client, json.dumps(legacy).encode(), "pong.json")
    assert response.status_code == 201
    imported = response.get_json()
    assert imported["blocks_json"] == legacy["project"]["blocks_json"]
    assert imported["game_json"] == {}  # the game IR is derived and is made again on convert
    assert client.post(f"/api/projects/{imported['id']}/convert", json={}).status_code == 200


def test_legacy_c_export_keeps_its_source(client):
    project = client.post("/api/projects", json={
        "title": "C Game", "game_json": {"source_mode": "c", "source_c": C_SOURCE}}).get_json()
    legacy = json.loads(client.get(f"/api/projects/{project['id']}/export").data)
    imported = client.post("/api/projects/import", json=legacy).get_json()
    assert imported["game_json"]["source_c"] == C_SOURCE


def test_upgrade_rejects_newer_and_foreign_documents():
    with pytest.raises(pf.ProjectFormatError, match="newer kit"):
        pf.upgrade({"schema": pf.SCHEMA, "schema_version": pf.SCHEMA_VERSION + 1})
    with pytest.raises(pf.ProjectFormatError, match="not a PRG32 project"):
        pf.upgrade({"schema": "something-else", "schema_version": 1})
    with pytest.raises(pf.ProjectFormatError, match="whole number"):
        pf.upgrade({"schema": pf.SCHEMA, "schema_version": "1"})
    assert pf.upgrade({"schema": pf.SCHEMA, "schema_version": 1})["schema_version"] == 1


@pytest.mark.parametrize("files, message", [
    ({"../evil.json": "{}", pf.MANIFEST_NAME: manifest()}, "Unsafe file name"),
    ({"/abs.json": "{}", pf.MANIFEST_NAME: manifest()}, "Unsafe file name"),
    ({"src\\x.json": "{}", pf.MANIFEST_NAME: manifest()}, "Unsafe file name"),
    ({"src/blocks.json": "{}"}, "missing prg32.project.json"),
    ({pf.MANIFEST_NAME: manifest()}, "missing src/blocks.json"),
    ({pf.MANIFEST_NAME: "not json"}, "not valid JSON"),
    ({pf.MANIFEST_NAME: manifest(authoring_mode="assembly", source="src/game.S")}, "missing src/game.S"),
    ({pf.MANIFEST_NAME: manifest(authoring_mode="python")}, "authoring_mode must be"),
    ({pf.MANIFEST_NAME: manifest(source="src/game.c")}, "keeps its source in src/blocks.json"),
    ({pf.MANIFEST_NAME: manifest(required_features=["teleport"]), "src/blocks.json": "{}"}, "feature"),
    ({pf.MANIFEST_NAME: manifest(assets=[{"kind": "sprite", "path": "../x.json"}]), "src/blocks.json": "{}"},
     "Unknown asset entry"),
    ({pf.MANIFEST_NAME: manifest(assets=[{"kind": "sprite", "path": "assets/data/a.json"}]),
      "src/blocks.json": "{}", "assets/data/a.json": "{}"}, "wrong folder"),
    ({pf.MANIFEST_NAME: manifest(assets=[{"kind": "sprite", "path": "assets/sprites/a.json"}]),
      "src/blocks.json": "{}", "assets/sprites/a.json": json.dumps({"width": 9999})}, "width and height"),
])
def test_unsafe_or_broken_archives_are_refused(client, files, message):
    response = upload(client, make_zip(files))
    assert response.status_code == 400
    assert message in response.get_json()["error"]


def test_symlinks_and_oversized_entries_are_refused(client, monkeypatch):
    link = make_zip({pf.MANIFEST_NAME: manifest(), "src/blocks.json": "{}"}, mode=0o120777)
    assert "Links are not allowed" in upload(client, link).get_json()["error"]
    monkeypatch.setattr(pf, "MAX_ENTRY_BYTES", 100)
    big = make_zip({pf.MANIFEST_NAME: manifest(), "src/blocks.json": json.dumps({"x": "y" * 500})})
    assert "larger than" in upload(client, big).get_json()["error"]
    monkeypatch.setattr(pf, "MAX_ENTRY_BYTES", 4 * 1024 * 1024)
    monkeypatch.setattr(pf, "MAX_ENTRIES", 2)
    many = make_zip({pf.MANIFEST_NAME: manifest(), "src/blocks.json": "{}", "notes.txt": "hi"})
    assert "more than 2 files" in upload(client, many).get_json()["error"]


def test_unlisted_files_are_ignored_and_reported(client):
    data = make_zip({pf.MANIFEST_NAME: manifest(), "src/blocks.json": "{}", "notes.txt": "hello"})
    response = upload(client, data)
    assert response.status_code == 201
    assert response.get_json()["ignored_files"] == ["notes.txt"]


def test_failed_child_insert_leaves_no_half_project(client, monkeypatch):
    from prg32_construction_kit import routes

    real_create = routes.create_resource

    def failing(resource, payload):
        if resource == "assets":
            raise RuntimeError("disk full")
        return real_create(resource, payload)

    project = blocks_project(client, "Half Game")
    data = client.get(f"/api/projects/{project['id']}/archive").data
    before = len(client.get("/api/projects").get_json()["projects"])
    sprites_before = len(client.get("/api/sprites").get_json()["sprites"])
    monkeypatch.setattr(routes, "create_resource", failing)
    with pytest.raises(RuntimeError):
        upload(client, data)
    monkeypatch.setattr(routes, "create_resource", real_create)
    assert len(client.get("/api/projects").get_json()["projects"]) == before
    assert len(client.get("/api/sprites").get_json()["sprites"]) == sprites_before  # no orphaned sprites


def test_duplicate_copies_children_and_belongs_to_the_caller(app, client):
    from prg32_construction_kit.auth import create_user

    project = blocks_project(client)
    copy = client.post(f"/api/projects/{project['id']}/duplicate", json={}).get_json()
    assert copy["title"] == "Archive Game (copy)"
    assert len(client.get(f"/api/sprites?project_id={copy['id']}").get_json()["sprites"]) == 2

    with app.app_context():
        create_user("bob", "bob@example.org", "bob-password-123")
    bob = app.test_client(login=("bob", "bob-password-123"))
    # Bob cannot see the admin's private project, so he cannot copy or export it.
    assert bob.post(f"/api/projects/{project['id']}/duplicate", json={}).status_code == 404
    assert bob.get(f"/api/projects/{project['id']}/archive").status_code == 404
    assert bob.get(f"/api/projects/{project['id']}/manifest").status_code == 404
    # A shared classroom game can be copied; the copy is Bob's and he can change it.
    shared = next(p for p in bob.get("/api/projects").get_json()["projects"] if p["owner_id"] is None)
    mine = bob.post(f"/api/projects/{shared['id']}/duplicate", json={"title": "My Pong"}).get_json()
    assert mine["title"] == "My Pong" and mine["can_edit"] is True
    assert bob.post(f"/api/projects/{shared['id']}/duplicate", json={"title": ""}).status_code == 400


def test_imported_archive_belongs_to_the_importer(app, client):
    from prg32_construction_kit.auth import create_user

    with app.app_context():
        create_user("carol", "carol@example.org", "carol-password-123")
    carol = app.test_client(login=("carol", "carol-password-123"))
    data = make_zip({pf.MANIFEST_NAME: manifest(owner_id=1), "src/blocks.json": "{}"})
    imported = upload(carol, data).get_json()
    me = carol.get("/auth/me").get_json()["user"]
    assert imported["owner_id"] == me["id"]
