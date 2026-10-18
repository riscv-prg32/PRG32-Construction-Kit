"""Project history (revisions) and "Recently deleted" (soft delete)."""

from __future__ import annotations

import io
import json
import sqlite3
import zipfile
from pathlib import Path

from prg32_construction_kit import project_format as pf
from prg32_construction_kit.auth import create_user
from prg32_construction_kit.sample_data import default_blocks
from conftest import make_app

C_SOURCE = """#include "prg32.h"
void c_game_init(void) {}
void c_game_update(void) {}
void c_game_draw(void) { prg32_gfx_clear(0); }
"""


def blocks(label: str) -> dict:
    """A small Blockly workspace that differs by ``label``."""
    workspace = default_blocks()
    workspace["label"] = label
    return workspace


def new_project(client, title="History Game") -> dict:
    project = client.post("/api/projects", json={"title": title, "blocks_json": blocks("v1")}).get_json()
    client.post("/api/sprites", json={"project_id": project["id"], "name": "Ship", "width": 1, "height": 1,
                                      "pixels": [["#ffffff"]]})
    return project


def revisions(client, project_id: str) -> list[dict]:
    response = client.get(f"/api/projects/{project_id}/revisions")
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json()["revisions"]


def student(app, name: str):
    with app.app_context():
        create_user(name, f"{name}@example.org", f"{name}-password-123")
    return app.test_client(login=(name, f"{name}-password-123"))


# --- revisions -------------------------------------------------------------------

def test_a_save_that_changes_the_blocks_keeps_the_old_version(client):
    project = new_project(client)
    assert revisions(client, project["id"]) == []
    client.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})
    history = revisions(client, project["id"])
    assert len(history) == 1
    assert history[0]["number"] == 1 and history[0]["reason"] == "save"
    assert history[0]["authoring_mode"] == "blocks" and history[0]["sprite_count"] == 1
    assert "files" not in history[0]  # the list stays small


def test_saves_without_source_changes_are_not_kept(client):
    project = new_project(client)
    # Only the title changes, then the same blocks are saved again.
    client.put(f"/api/projects/{project['id']}", json={"title": "Renamed"})
    client.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v1"), "game_json": {"ops": []}})
    assert revisions(client, project["id"]) == []


def test_identical_consecutive_snapshots_are_skipped(app, client):
    from prg32_construction_kit.db import add_revision, get_resource

    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    client.put(path, json={"blocks_json": blocks("v2")})   # keeps v1
    client.put(path, json={"blocks_json": blocks("v1")})   # keeps v2
    client.put(path, json={"blocks_json": blocks("v2")})   # keeps v1 again: it differs from the newest (v2)
    assert [rev["number"] for rev in revisions(client, project["id"])] == [3, 2, 1]
    with app.app_context():
        saved = get_resource("projects", project["id"])
        files = pf.project_files(saved, [], [])
        assert add_revision(saved, files, "save", keep=50) is not None
        # The same files again right after: nothing new is kept.
        assert add_revision(saved, files, "save", keep=50) is None
    assert len(revisions(client, project["id"])) == 4


def test_advanced_c_source_changes_are_kept(client):
    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    client.put(path, json={"game_json": {"source_mode": "c", "source_c": C_SOURCE}})
    client.put(path, json={"game_json": {"source_mode": "c", "source_c": C_SOURCE + "/* more */\n"}})
    history = revisions(client, project["id"])
    assert [rev["authoring_mode"] for rev in history] == ["c", "blocks"]
    archive = client.get(f"{path}/revisions/{history[0]['id']}/archive")
    files = zipfile.ZipFile(io.BytesIO(archive.data))
    assert files.read("src/game.c").decode() == C_SOURCE


def test_handwritten_assembly_changes_are_kept_and_restored(client):
    asm_v1 = "    .section .text\n    .globl history_game_init\nhistory_game_init:\n    ret\n"
    asm_v2 = asm_v1 + "    /* a second version */\n"
    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    client.put(path, json={"game_json": {"source_mode": "asm", "source_asm": asm_v1}})
    client.put(path, json={"game_json": {"source_mode": "asm", "source_asm": asm_v1}})  # unchanged: nothing kept
    client.put(path, json={"game_json": {"source_mode": "asm", "source_asm": asm_v2}})
    history = revisions(client, project["id"])
    assert [rev["authoring_mode"] for rev in history] == ["assembly", "blocks"]
    archive = zipfile.ZipFile(io.BytesIO(client.get(f"{path}/revisions/{history[0]['id']}/archive").data))
    assert archive.read("src/game.S").decode() == asm_v1
    restored = client.post(f"{path}/revisions/{history[0]['id']}/restore").get_json()["project"]
    assert restored["game_json"]["source_mode"] == "asm" and restored["game_json"]["source_asm"] == asm_v1
    assert revisions(client, project["id"])[0]["reason"] == "restore"


def test_history_is_capped_per_project(tmp_path: Path):
    app = make_app(tmp_path, PRG32_KIT_MAX_REVISIONS=3)
    client = app.test_client()
    project = new_project(client)
    for number in range(2, 8):
        client.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks(f"v{number}")})
    history = revisions(client, project["id"])
    assert [rev["number"] for rev in history] == [6, 5, 4]


def test_revision_archive_is_a_project_archive(client):
    project = new_project(client)
    client.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})
    revision = revisions(client, project["id"])[0]
    response = client.get(f"/api/projects/{project['id']}/revisions/{revision['id']}/archive")
    assert response.status_code == 200
    assert "history-game-revision-1.prg32project.zip" in response.headers["Content-Disposition"]
    contents = pf.import_archive(response.data)
    assert contents["project"]["blocks_json"]["label"] == "v1"
    assert [sprite["name"] for sprite in contents["sprites"]] == ["Ship"]
    # Same files, same bytes: the archive is deterministic.
    again = client.get(f"/api/projects/{project['id']}/revisions/{revision['id']}/archive")
    assert again.data == response.data
    # And it can be imported like any other archive.
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(response.data), "old.zip")},
                           content_type="multipart/form-data")
    assert imported.status_code == 201


def test_restore_keeps_the_current_version_first(client):
    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    client.put(path, json={"blocks_json": blocks("v2")})
    # Change the sprites after the snapshot: restore brings back the old ones.
    sprite = client.get(f"/api/sprites?project_id={project['id']}").get_json()["sprites"][0]
    client.put(f"/api/sprites/{sprite['id']}", json={"name": "Rocket"})
    client.post("/api/sprites", json={"project_id": project["id"], "name": "Alien"})
    first = revisions(client, project["id"])[-1]

    result = client.post(f"{path}/revisions/{first['id']}/restore")
    assert result.status_code == 200
    body = result.get_json()
    assert body["project"]["blocks_json"]["label"] == "v1"
    assert body["restored_revision"] == first["id"] and body["saved_revision"]
    names = sorted(s["name"] for s in client.get(f"/api/sprites?project_id={project['id']}").get_json()["sprites"])
    assert names == ["Ship"]

    # Nothing was lost: the version before the restore is in the history.
    history = revisions(client, project["id"])
    assert history[0]["reason"] == "restore" and history[0]["sprite_count"] == 2
    saved = client.get(f"{path}/revisions/{history[0]['id']}/archive").data
    assert pf.import_archive(saved)["project"]["blocks_json"]["label"] == "v2"


def test_unknown_or_foreign_revisions_are_not_found(client):
    one, two = new_project(client, "One"), new_project(client, "Two")
    client.put(f"/api/projects/{one['id']}", json={"blocks_json": blocks("v2")})
    revision = revisions(client, one["id"])[0]
    # A revision id only works with its own project.
    assert client.get(f"/api/projects/{two['id']}/revisions/{revision['id']}/archive").status_code == 404
    assert client.post(f"/api/projects/{two['id']}/revisions/{revision['id']}/restore").status_code == 404
    assert client.post(f"/api/projects/{one['id']}/revisions/rev_missing/restore").status_code == 404


def test_only_the_owner_or_an_admin_sees_the_history(app, client):
    alice, bob = student(app, "alice"), student(app, "bob")
    project = new_project(alice)
    alice.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})
    revision = revisions(alice, project["id"])[0]
    base = f"/api/projects/{project['id']}/revisions"
    # Bob cannot even see that the project exists.
    assert bob.get(base).status_code == 404
    assert bob.get(f"{base}/{revision['id']}/archive").status_code == 404
    assert bob.post(f"{base}/{revision['id']}/restore").status_code == 404
    # The teacher can.
    assert len(revisions(client, project["id"])) == 1
    # Shared classroom projects: students can read them but not their history.
    shared = next(p for p in bob.get("/api/projects").get_json()["projects"] if p["owner_id"] is None)
    assert bob.get(f"/api/projects/{shared['id']}/revisions").status_code == 403


def test_restored_children_belong_to_the_project_owner(app, client):
    alice = student(app, "alice")
    project = new_project(alice)
    alice.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})
    revision = revisions(alice, project["id"])[0]
    # The teacher restores it for her; the sprites stay Alice's.
    client.post(f"/api/projects/{project['id']}/revisions/{revision['id']}/restore")
    sprites = alice.get(f"/api/sprites?project_id={project['id']}").get_json()["sprites"]
    assert sprites and all(sprite["can_edit"] for sprite in sprites)


# --- Recently deleted ------------------------------------------------------------------

def test_delete_hides_the_project_and_restore_brings_it_back(client):
    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    response = client.delete(path)
    assert response.status_code == 200
    assert response.get_json() == {"deleted": True, "id": project["id"]}  # same shape as before
    assert client.get(path).status_code == 404
    assert client.put(path, json={"title": "x"}).status_code == 404
    assert client.get(f"{path}/archive").status_code == 404
    assert project["id"] not in [p["id"] for p in client.get("/api/projects").get_json()["projects"]]
    deleted = client.get("/api/projects?deleted=1").get_json()["projects"]
    assert [p["id"] for p in deleted] == [project["id"]] and deleted[0]["deleted_at"]
    # A deleted project cannot get new sprites.
    assert client.post("/api/sprites", json={"project_id": project["id"], "name": "x"}).status_code == 403

    restored = client.post(f"{path}/restore")
    assert restored.status_code == 200 and restored.get_json()["deleted_at"] is None
    assert client.get(path).status_code == 200
    assert client.get("/api/projects?deleted=1").get_json()["projects"] == []
    # Its sprites were never touched.
    assert len(client.get(f"/api/sprites?project_id={project['id']}").get_json()["sprites"]) == 1


def test_recently_deleted_lists_only_your_own_projects(app, client):
    alice, bob = student(app, "alice"), student(app, "bob")
    mine = new_project(alice, "Alice Game")
    alice.delete(f"/api/projects/{mine['id']}")
    assert [p["id"] for p in alice.get("/api/projects?deleted=1").get_json()["projects"]] == [mine["id"]]
    assert bob.get("/api/projects?deleted=1").get_json()["projects"] == []
    # Bob cannot restore (or learn about) Alice's project.
    assert bob.post(f"/api/projects/{mine['id']}/restore").status_code == 404
    # Students cannot delete shared projects, so shared ones never show up as deleted for them.
    shared = next(p for p in bob.get("/api/projects").get_json()["projects"] if p["owner_id"] is None)
    assert bob.delete(f"/api/projects/{shared['id']}").status_code == 403
    # The teacher sees every deleted project.
    assert mine["id"] in [p["id"] for p in client.get("/api/projects?deleted=1").get_json()["projects"]]


def test_only_admins_purge(app, client):
    alice = student(app, "alice")
    project = new_project(alice)
    alice.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})
    alice.delete(f"/api/projects/{project['id']}")
    assert alice.delete(f"/api/projects/{project['id']}?purge=1").status_code == 403

    response = client.delete(f"/api/projects/{project['id']}?purge=1")
    assert response.status_code == 200 and response.get_json()["purged"] is True
    assert client.get("/api/projects?deleted=1").get_json()["projects"] == []
    assert client.post(f"/api/projects/{project['id']}/restore").status_code == 404
    assert client.delete(f"/api/projects/{project['id']}?purge=1").status_code == 404
    with app.app_context():
        from prg32_construction_kit.db import ProjectRevision, db
        assert db.session.query(ProjectRevision).filter_by(project_id=project["id"]).count() == 0


def test_old_database_without_deleted_at_gets_the_column(tmp_path: Path):
    database = tmp_path / "test.sqlite"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE projects (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            owner_id INTEGER, title TEXT NOT NULL, description TEXT NOT NULL, author TEXT NOT NULL,
            tags TEXT NOT NULL, blocks_json TEXT NOT NULL, game_json TEXT NOT NULL);
        INSERT INTO projects VALUES ('project_old', '2025-01-01T00:00:00+00:00', '2025-01-01T00:00:00+00:00',
            NULL, 'Old Game', '', '', '[]', '{}', '{}');
    """)
    connection.commit()
    connection.close()

    app = make_app(tmp_path)
    make_app(tmp_path)  # starting twice must not fail: the upgrade is idempotent
    client = app.test_client()
    old = client.get("/api/projects/project_old")
    assert old.status_code == 200 and old.get_json()["deleted_at"] is None
    assert client.delete("/api/projects/project_old").status_code == 200
    assert client.get("/api/projects?deleted=1").get_json()["projects"][0]["id"] == "project_old"
    columns = [row[1] for row in sqlite3.connect(database).execute("PRAGMA table_info(projects)")]
    assert columns.count("deleted_at") == 1
    tables = {row[0] for row in sqlite3.connect(database).execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "project_revisions" in tables


def test_put_payload_cannot_set_deleted_at(client):
    project = new_project(client)
    updated = client.put(f"/api/projects/{project['id']}", json={"deleted_at": "2020-01-01"}).get_json()
    assert updated["deleted_at"] is None
    assert json.dumps(updated)  # still plain JSON
