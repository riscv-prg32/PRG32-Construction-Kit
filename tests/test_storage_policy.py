"""Registered storage policy (ADR-0017): conflict-safe saves, autosave, quotas, retention.

Guest storage lives in the browser and is tested in tests/test_storage_browser.py.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest
from test_auth import make_student, student_client
from test_source_languages import fake_builder

from prg32_construction_kit import retention
from prg32_construction_kit.db import ProjectRevision, db
from prg32_construction_kit.sample_data import default_blocks


def new_project(browser, **fields):
    response = browser.post("/api/projects", json={"title": "Game", "blocks_json": default_blocks(), **fields})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


# --- conflict-safe saves ------------------------------------------------------------------

def test_every_save_increments_the_version(client):
    project = new_project(client)
    assert project["version"] == 0
    saved = client.put(f"/api/projects/{project['id']}", json={"title": "A", "expected_version": 0}).get_json()
    assert saved["version"] == 1
    assert client.put(f"/api/projects/{project['id']}", json={"title": "B"}).get_json()["version"] == 2


def test_a_save_from_an_older_version_changes_nothing(client):
    project = new_project(client)
    window_a = window_b = project["version"]
    assert client.put(f"/api/projects/{project['id']}", json={"title": "from A", "expected_version": window_a}).status_code == 200
    refused = client.put(f"/api/projects/{project['id']}", json={"title": "from B", "expected_version": window_b})
    body = refused.get_json()
    assert refused.status_code == 409 and body["code"] == "version_conflict"
    assert body["current"]["title"] == "from A" and body["current"]["version"] == 1
    assert client.get(f"/api/projects/{project['id']}").get_json()["title"] == "from A"
    # The student chose "save mine over it": the save names the newer version on purpose.
    assert client.put(f"/api/projects/{project['id']}", json={"title": "from B", "expected_version": 1}).status_code == 200


def test_the_version_check_is_atomic(app, client):
    """Even if a save passes the first check, the conditional UPDATE refuses a stale version."""
    from prg32_construction_kit.db import VersionConflict, update_resource

    project = new_project(client)
    with app.app_context():
        update_resource("projects", project["id"], {"title": "first"}, expected_version=0)
        with pytest.raises(VersionConflict):
            update_resource("projects", project["id"], {"title": "second"}, expected_version=0)


def test_a_restore_is_a_new_version_so_an_old_window_cannot_save_over_it(client):
    project = new_project(client)
    path = f"/api/projects/{project['id']}"
    client.put(path, json={"title": "first", "blocks_json": {"n": 1}, "expected_version": 0})
    client.put(path, json={"title": "second", "blocks_json": {"n": 2}, "expected_version": 1})
    revision = client.get(path + "/revisions").get_json()["revisions"][-1]
    restored = client.post(f"{path}/revisions/{revision['id']}/restore").get_json()["project"]
    assert restored["version"] == 3
    stale = client.put(path, json={"title": "from an old window", "expected_version": 2})
    assert stale.status_code == 409 and stale.get_json()["code"] == "version_conflict"
    assert client.get(path).get_json()["title"] == restored["title"]


def test_expected_version_must_be_a_number(client):
    project = new_project(client)
    assert client.put(f"/api/projects/{project['id']}", json={"title": "x", "expected_version": "0"}).status_code == 400


def revisions(app, project_id):
    with app.app_context():
        return db.session.query(ProjectRevision).filter_by(project_id=project_id).count()


def test_autosaves_do_not_fill_the_history(app, client):
    project = new_project(client)
    url = f"/api/projects/{project['id']}"
    for step in range(3):
        version = client.get(url).get_json()["version"]
        client.put(url, json={"blocks_json": {"step": step}, "expected_version": version, "autosave": True})
    assert revisions(app, project["id"]) == 1          # the first autosave keeps the original once
    version = client.get(url).get_json()["version"]
    client.put(url, json={"blocks_json": {"step": "saved"}, "expected_version": version})
    assert revisions(app, project["id"]) == 2          # an explicit save always does
    app.config["PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES"] = 0
    version = client.get(url).get_json()["version"]
    client.put(url, json={"blocks_json": {"step": "later"}, "expected_version": version, "autosave": True})
    assert revisions(app, project["id"]) == 3          # ... and autosaves do once the newest is old enough


# --- quotas ---------------------------------------------------------------------------------

def test_project_count_quota(app, client):
    app.config["PRG32_KIT_QUOTA_PROJECTS"] = 2
    make_student(client, "ada")
    ada = student_client(app, "ada")
    first = new_project(ada)
    new_project(ada)
    refused = ada.post("/api/projects", json={"title": "third"})
    assert refused.status_code == 413 and refused.get_json()["code"] == "quota_exceeded"
    assert ada.post(f"/api/projects/{first['id']}/duplicate", json={}).status_code == 413
    assert ada.post("/api/examples/pong/import").status_code == 413
    assert new_project(client)["title"] == "Game"   # administrators have no limit
    usage = ada.get("/api/storage").get_json()
    assert usage["projects"] == 2 and usage["quota_projects"] == 2


def test_space_quota_refuses_growth_but_allows_shrinking(app, client):
    app.config["PRG32_KIT_QUOTA_MB"] = 1
    make_student(client, "ada")
    ada = student_client(app, "ada")
    project = new_project(ada, description="x" * 900_000)
    refused = ada.put(f"/api/projects/{project['id']}", json={"description": "y" * 1_200_000})
    assert refused.status_code == 413 and refused.get_json()["usage"]["quota_bytes"] == 1024 * 1024
    assert ada.post("/api/projects", json={"title": "big", "description": "z" * 300_000}).status_code == 413
    assert ada.put(f"/api/projects/{project['id']}", json={"description": "small"}).status_code == 200
    assert ada.get("/api/storage").get_json()["bytes"] < 10_000


def test_a_full_account_cannot_compile(app, client, monkeypatch):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder([]))
    project = new_project(ada, description="x" * 200_000)
    app.config["PRG32_KIT_QUOTA_MB"] = 1
    assert ada.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).status_code == 200
    app.config["PRG32_KIT_QUOTA_MB"] = 0
    big = new_project(ada, description="y" * 700_000)   # made while there was no limit
    app.config["PRG32_KIT_QUOTA_MB"] = 1
    refused = ada.post(f"/api/projects/{big['id']}/package", json={"architectures": ["qemu"]})
    assert refused.status_code == 413 and refused.get_json()["code"] == "quota_exceeded"


def test_quota_refusals_are_audited(app, client):
    app.config["PRG32_KIT_QUOTA_PROJECTS"] = 1
    make_student(client, "ada")
    ada = student_client(app, "ada")
    new_project(ada)
    ada.post("/api/projects", json={"title": "again"})
    actions = [event["action"] for event in client.get("/api/admin/audit").get_json()["events"]]
    assert "quota_exceeded" in actions


# --- retention --------------------------------------------------------------------------------

def package(browser, project_id):
    response = browser.post(f"/api/projects/{project_id}/package", json={"architectures": ["qemu"]})
    assert response.status_code == 200, response.get_json()
    return response.get_json()


def test_each_project_keeps_its_newest_builds_with_their_files(app, client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder([]))
    app.config["PRG32_KIT_KEEP_BUILDS"] = 2
    project = new_project(client)
    results = [package(client, project["id"]) for _ in range(4)]
    builds = client.get("/api/builds", query_string={"project_id": project["id"]}).get_json()["builds"]
    assert sorted(build["id"] for build in builds) == sorted(r["build"]["id"] for r in results[-2:])
    root = Path(app.config["BUILD_ROOT"])
    assert not (root / results[0]["build"]["id"]).exists() and (root / results[-1]["build"]["id"]).exists()
    old_cartridge = results[0]["cartridge_artifacts"][0]["id"]
    assert client.get(f"/api/artifacts/{old_cartridge}").status_code == 404
    assert client.get(f"/api/artifacts/{results[-1]['cartridge_artifacts'][0]['id']}").status_code == 200


def test_trash_is_emptied_after_its_days_and_dry_runs_change_nothing(app, client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder([]))
    old, recent = new_project(client, title="old"), new_project(client, title="recent")
    built = package(client, old["id"])
    for project in (old, recent):
        client.delete(f"/api/projects/{project['id']}")
    with app.app_context():
        from prg32_construction_kit.db import Project

        db.session.get(Project, old["id"]).deleted_at = "2000-01-01T00:00:00+00:00"
        db.session.commit()
    report = client.post("/api/admin/retention", json={}).get_json()
    assert report["dry_run"] is True and [item["project"] for item in report["purged_projects"]] == [old["id"]]
    assert client.get("/api/projects", query_string={"deleted": 1}).get_json()["projects"]
    report = client.post("/api/admin/retention", json={"dry_run": False}).get_json()
    deleted = [item["id"] for item in client.get("/api/projects", query_string={"deleted": 1}).get_json()["projects"]]
    assert deleted == [recent["id"]]
    assert not (Path(app.config["BUILD_ROOT"]) / built["build"]["id"]).exists()
    assert client.get(f"/api/artifacts/{built['bundle_artifact']['id']}").status_code == 404


def test_only_old_unknown_build_folders_are_removed(app, client):
    root = Path(app.config["BUILD_ROOT"])
    stale, fresh, other = root / "build_0123456789ab", root / "build_ba9876543210", root / "my-notes"
    for folder in (stale, fresh, other):
        folder.mkdir(parents=True)
    hour_ago = time.time() - 2 * retention.ORPHAN_AGE_SECONDS
    os.utime(stale, (hour_ago, hour_ago))
    report = client.post("/api/admin/retention", json={"dry_run": False}).get_json()
    assert report["removed_folders"] == ["build_0123456789ab"]
    assert not stale.exists() and fresh.exists() and other.exists()


def test_switched_off_accounts_are_listed_never_deleted(app, client):
    student = make_student(client, "ada")
    project = new_project(student_client(app, "ada"))
    client.post(f"/api/users/{student['id']}/deactivate", json={})
    report = client.post("/api/admin/retention", json={"dry_run": False}).get_json()
    assert [item["username"] for item in report["switched_off_accounts"]] == ["ada"]
    assert client.get(f"/api/projects/{project['id']}").status_code == 200


def test_retention_is_for_administrators(app, client):
    make_student(client, "ada")
    assert student_client(app, "ada").post("/api/admin/retention", json={}).status_code == 403


def test_retention_command_line(app):
    result = app.test_cli_runner().invoke(args=["prg32-retention"])
    assert result.exit_code == 0 and '"dry_run": true' in result.output


def test_deleting_an_account_with_its_items(app, client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder([]))
    student = make_student(client, "ada")
    ada = student_client(app, "ada")
    project = new_project(ada)
    built = package(ada, project["id"])
    answer = client.delete(f"/api/users/{student['id']}", query_string={"with_items": 1}).get_json()
    assert answer["deleted"] is True and answer["items_removed"]["projects"] == 1
    assert client.get(f"/api/projects/{project['id']}").status_code == 404
    assert not (Path(app.config["BUILD_ROOT"]) / built["build"]["id"]).exists()


# --- guests ------------------------------------------------------------------------------------

def test_guest_mode_is_offered_or_not(app, anon):
    assert b"Try without an account" in anon.get("/auth/login").data
    assert anon.get("/.well-known/prg32-construction-kit.json").get_json()["guest_mode"] == "local"
    app.config["PRG32_GUEST_MODE"] = "off"
    assert b"Try without an account" not in anon.get("/auth/login").data


def test_the_guest_workspace_is_static_and_stores_nothing_on_the_server(anon):
    page = anon.get("/static/offline.html")
    assert page.status_code == 200 and b"guest_store.js" in page.data
    assert b"fetch(" not in anon.get("/static/js/guest_store.js").data   # IndexedDB only, never the network
