"""Restoring a revision keeps sprite/asset identity and the links to them."""

from __future__ import annotations

import io
import sqlite3
import zipfile

import pytest
from conftest import make_app

import importlib

# The package also exports the SQLAlchemy object as "db", so import the module by name.
kit_db = importlib.import_module("prg32_construction_kit.db")
from prg32_construction_kit.auth import create_user
from prg32_construction_kit.db import get_resource
from prg32_construction_kit.sample_data import default_blocks


def blocks(label: str) -> dict:
    workspace = default_blocks()
    workspace["label"] = label
    return workspace


def sprite(client, project_id, name, colour="#ffffff"):
    return client.post("/api/sprites", json={"project_id": project_id, "name": name, "width": 1, "height": 1,
                                             "pixels": [[colour]]}).get_json()


def children(client, project_id):
    sprites = client.get(f"/api/sprites?project_id={project_id}").get_json()["sprites"]
    assets = client.get(f"/api/assets?project_id={project_id}").get_json()["assets"]
    return {s["name"]: s for s in sprites}, {a["name"]: a for a in assets}


def setup_history(client):
    """Revision 1 holds sprites Ship and Rock and asset Level; then everything changes."""
    project = client.post("/api/projects", json={"title": "Keep Links", "blocks_json": blocks("v1")}).get_json()
    ship = sprite(client, project["id"], "Ship")
    rock = sprite(client, project["id"], "Rock", "#00ff00")
    level = client.post("/api/assets", json={"project_id": project["id"], "name": "Level", "data": {"n": 1}}).get_json()
    # An artifact made from the Ship sprite: it must keep pointing at Ship after a restore.
    artifact = client.post(f"/api/sprites/{ship['id']}/convert", json={}).get_json()["artifact"]
    client.put(f"/api/projects/{project['id']}", json={"blocks_json": blocks("v2")})  # keeps revision 1
    revision = client.get(f"/api/projects/{project['id']}/revisions").get_json()["revisions"][0]
    archive_v1 = client.get(f"/api/projects/{project['id']}/revisions/{revision['id']}/archive").data
    # Change everything: edit Ship, delete Rock, add Star, edit Level.
    client.put(f"/api/sprites/{ship['id']}", json={"pixels": [["#ff0000"]]})
    client.delete(f"/api/sprites/{rock['id']}")
    star = sprite(client, project["id"], "Star", "#ffff00")
    client.put(f"/api/assets/{level['id']}", json={"data": {"n": 2}})
    return project, revision, archive_v1, {"ship": ship, "rock": rock, "star": star, "level": level,
                                           "artifact": artifact}


def restore(client, project, revision):
    return client.post(f"/api/projects/{project['id']}/revisions/{revision['id']}/restore", json={})


def test_restore_updates_in_place_adds_and_removes(app, client):
    project, revision, archive_v1, rows = setup_history(client)
    response = restore(client, project, revision)
    assert response.status_code == 200, response.get_data(as_text=True)
    sprites, assets = children(client, project["id"])
    assert set(sprites) == {"Ship", "Rock"}  # Star removed, Rock back
    assert sprites["Ship"]["id"] == rows["ship"]["id"]  # same row, same id
    assert sprites["Ship"]["pixels"] == [["#ffffff"]]  # with the old picture
    assert sprites["Rock"]["pixels"] == [["#00ff00"]]
    assert assets["Level"]["id"] == rows["level"]["id"] and assets["Level"]["data"] == {"n": 1}
    with app.app_context():
        assert get_resource("sprites", rows["star"]["id"]) is None
        # The artifact made from Ship still knows its sprite.
        assert get_resource("artifacts", rows["artifact"]["id"])["sprite_id"] == rows["ship"]["id"]
    # The restored project is exactly revision 1 again: same files, same order, same bytes.
    assert client.get(f"/api/projects/{project['id']}/archive").data == archive_v1


def test_restore_twice_keeps_ids_stable(client):
    project, revision, _archive, rows = setup_history(client)
    restore(client, project, revision)
    first = {name: row["id"] for name, row in children(client, project["id"])[0].items()}
    restore(client, project, revision)
    second = {name: row["id"] for name, row in children(client, project["id"])[0].items()}
    assert first == second and first["Ship"] == rows["ship"]["id"]


def test_reordering_follows_the_revision(client):
    """Order in a project is by name and content; renaming changes it, restoring brings it back."""
    project, revision, archive_v1, rows = setup_history(client)
    client.put(f"/api/sprites/{rows['ship']['id']}", json={"name": "AAA first"})
    restore(client, project, revision)
    assert client.get(f"/api/projects/{project['id']}/archive").data == archive_v1
    assert children(client, project["id"])[0]["Ship"]["id"] == rows["ship"]["id"]


def test_older_revisions_without_ids_match_by_name(app, client):
    project, revision, archive_v1, rows = setup_history(client)
    with app.app_context():
        kit_db.db.session.execute(kit_db.text("UPDATE project_revisions SET child_ids = '{}'"))
        kit_db.db.session.commit()
    assert restore(client, project, revision).status_code == 200
    sprites, _assets = children(client, project["id"])
    assert sprites["Ship"]["id"] == rows["ship"]["id"]
    assert client.get(f"/api/projects/{project['id']}/archive").data == archive_v1


@pytest.mark.parametrize("child_ids", ["not json", "[1, 2]", '{"assets/sprites/01-rock.json": "../x"}'])
def test_malformed_recorded_ids_fall_back_safely(app, client, child_ids):
    project, revision, archive_v1, _rows = setup_history(client)
    with app.app_context():
        kit_db.db.session.execute(kit_db.text("UPDATE project_revisions SET child_ids = :v"), {"v": child_ids})
        kit_db.db.session.commit()
    assert restore(client, project, revision).status_code == 200
    assert client.get(f"/api/projects/{project['id']}/archive").data == archive_v1


def test_damaged_revision_is_refused_without_changes(app, client):
    project, revision, _archive, _rows = setup_history(client)
    before = client.get(f"/api/projects/{project['id']}/archive").data
    with app.app_context():
        kit_db.db.session.execute(kit_db.text("UPDATE project_revisions SET manifest = 'broken'"))
        kit_db.db.session.commit()
    assert client.get(f"/api/projects/{project['id']}/revisions").status_code == 200  # still listed
    response = restore(client, project, revision)
    assert response.status_code == 422
    assert client.get(f"/api/projects/{project['id']}/archive").data == before


def test_recorded_ids_of_another_project_are_never_used(app, client):
    project, revision, archive_v1, _rows = setup_history(client)
    other = client.post("/api/projects", json={"title": "Other", "blocks_json": blocks("o")}).get_json()
    foreign = sprite(client, other["id"], "Ship", "#123456")
    with app.app_context():
        kit_db.db.session.execute(kit_db.text("UPDATE project_revisions SET child_ids = :v"),
                                  {"v": '{"assets/sprites/02-ship.json": "%s"}' % foreign["id"]})
        kit_db.db.session.commit()
    assert restore(client, project, revision).status_code == 200
    with app.app_context():
        untouched = get_resource("sprites", foreign["id"])
    assert untouched["project_id"] == other["id"] and untouched["pixels"] == [["#123456"]]
    assert client.get(f"/api/projects/{project['id']}/archive").data == archive_v1


def test_failure_half_way_changes_nothing(app, client, monkeypatch):
    project, revision, _archive, rows = setup_history(client)
    before = client.get(f"/api/projects/{project['id']}/archive").data
    before_ids = {name: row["id"] for name, row in children(client, project["id"])[0].items()}

    real_new_id = kit_db.new_id
    staged = []

    def broken_new_id(prefix):
        if prefix == "sprite":  # the safety snapshot (prefix "rev") still works
            staged.append(prefix)
            raise RuntimeError("database is full")
        return real_new_id(prefix)
    # Updates and deletes are staged first; creating Rock again then fails.
    monkeypatch.setattr(kit_db, "new_id", broken_new_id)
    with pytest.raises(RuntimeError):
        restore(client, project, revision)
    monkeypatch.undo()
    assert staged == ["sprite"]  # it really failed half way, after updates and deletes were staged
    assert client.get(f"/api/projects/{project['id']}/archive").data == before
    assert {name: row["id"] for name, row in children(client, project["id"])[0].items()} == before_ids
    with app.app_context():
        assert get_resource("artifacts", rows["artifact"]["id"])["sprite_id"] == rows["ship"]["id"]


def test_new_children_belong_to_the_project_owner_not_the_teacher(app, client):
    with app.app_context():
        create_user("ana", "ana@example.org", "ana-password-123")
    ana = app.test_client(login=("ana", "ana-password-123"))
    project, revision, _archive, rows = setup_history(ana)
    owner = ana.get("/auth/me").get_json()["user"]["id"]
    # The teacher (admin) restores the student's project.
    assert restore(client, project, revision).status_code == 200
    sprites, _assets = children(ana, project["id"])
    assert sprites["Rock"]["owner_id"] == owner and sprites["Ship"]["owner_id"] == owner


def test_other_students_cannot_restore_or_read_history(app, client):
    project, revision, _archive, _rows = setup_history(client)
    with app.app_context():
        create_user("eve", "eve@example.org", "eve-password-123")
    eve = app.test_client(login=("eve", "eve-password-123"))
    assert restore(eve, project, revision).status_code == 404
    assert eve.get(f"/api/projects/{project['id']}/revisions/{revision['id']}/archive").status_code == 404
    mine = eve.post("/api/projects", json={"title": "Eve", "blocks_json": blocks("e")}).get_json()
    # A revision id of someone else's project does not work through Eve's own project either.
    assert eve.post(f"/api/projects/{mine['id']}/revisions/{revision['id']}/restore", json={}).status_code == 404


def test_child_ids_column_is_added_to_old_databases(tmp_path):
    app = make_app(tmp_path)
    database = tmp_path / "test.sqlite"
    with app.app_context():
        kit_db.db.session.remove()
        kit_db.db.engine.dispose()
    connection = sqlite3.connect(database)
    connection.execute("ALTER TABLE project_revisions DROP COLUMN child_ids")
    connection.commit()
    connection.close()
    again = make_app(tmp_path)  # initialisation adds it back, and running it twice is harmless
    make_app(tmp_path)
    with again.app_context():
        columns = {row[1] for row in kit_db.db.session.execute(kit_db.text("PRAGMA table_info(project_revisions)"))}
    assert "child_ids" in columns
    client = again.test_client()
    project, revision, archive_v1, _rows = setup_history(client)
    assert restore(client, project, revision).status_code == 200


def test_revision_archives_do_not_contain_row_ids(client):
    project, revision, archive_v1, rows = setup_history(client)
    with zipfile.ZipFile(io.BytesIO(archive_v1)) as archive:
        everything = b"".join(archive.read(name) for name in archive.namelist())
    assert rows["ship"]["id"].encode() not in everything
