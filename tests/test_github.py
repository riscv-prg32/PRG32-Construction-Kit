"""GitHub as a project remote (ADR-0025, docs/github.md), against an in-process GitHub (tests/fake_github.py)."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import make_app
from fake_github import APP_CLIENT, FakeGitHub
from test_auth import make_student, student_client

from prg32_construction_kit import cloud_storage
from prg32_construction_kit.cloud_storage import CloudAccount, CloudError, GitHub
from prg32_construction_kit.db import db

SETTINGS = {"CLOUD_GITHUB_CLIENT_ID": APP_CLIENT, "CLOUD_GITHUB_CLIENT_SECRET": "test-only",
            "CLOUD_GITHUB_APP_SLUG": "prg32-kit", "PUBLIC_URL": "https://kit.school.test"}


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def gh(tmp_path, monkeypatch):
    clock = Clock()
    monkeypatch.setattr(cloud_storage, "now_seconds", clock)
    monkeypatch.setattr(cloud_storage, "sleep", lambda _seconds: None)
    app = make_app(tmp_path, **SETTINGS)
    fake = FakeGitHub(clock)
    monkeypatch.setattr(cloud_storage, "transport", fake)
    admin = app.test_client()
    make_student(admin, "ada")
    return {"app": app, "fake": fake, "clock": clock, "student": student_client(app, "ada"), "admin": admin}


def connect(gh, repository="ada/games"):
    student = gh["student"]
    start = student.post("/api/cloud/github/connect", json={"consent": True}).get_json()["redirect"]
    query = parse_qs(urlsplit(start).query)
    assert start.startswith("https://github.com/login/oauth/authorize?")
    assert query["code_challenge_method"] == ["S256"] and query["client_id"] == [APP_CLIENT]
    answer = student.get(f"/cloud/github/callback?state={query['state'][0]}&code=good-code")
    assert answer.status_code == 302, answer.get_data(as_text=True)
    if repository:
        assert student.put("/api/cloud/github/repository", json={"repository": repository}).status_code == 200
    return student


def new_project(student, title="Rocket Race", **fields):
    return student.post("/api/projects", json={"title": title, "blocks_json": {"blocks": 1}, **fields}).get_json()


def push(gh, project, **body):
    return gh["student"].post(f"/api/projects/{project['id']}/cloud/github/push", json=body)


def folder_of(gh, project):
    return f"rocket-race-{project['id']}"


def test_connecting_uses_pkce_and_keeps_the_token_sealed(gh):
    student = connect(gh, repository=None)
    assert len(gh["fake"].verifiers) == 1 and len(gh["fake"].verifiers[0]) >= 43
    providers = student.get("/api/cloud").get_json()["providers"]
    github = next(item for item in providers if item["name"] == "github")
    assert github["connected"] and github["account_name"] == "ada-codes"
    assert github["install_url"] == "https://github.com/apps/prg32-kit/installations/new"
    assert "ghu_" not in json.dumps(providers)
    with gh["app"].app_context():
        row = db.session.query(CloudAccount).one()
        assert "ghu_" not in row.tokens and cloud_storage.unseal(row.tokens)["access_token"].startswith("ghu_")


def test_only_an_installed_repository_and_a_real_branch_can_be_chosen(gh):
    student = connect(gh, repository=None)
    listed = student.get("/api/cloud/github/repositories").get_json()
    assert [repo["full_name"] for repo in listed["repositories"]] == ["ada/games", "ada/notes"]
    assert student.put("/api/cloud/github/repository", json={"repository": "someone/else"}).status_code == 400
    assert student.put("/api/cloud/github/repository", json={"repository": "ada/games", "branch": "a b"}).status_code == 400
    project = new_project(student)
    refused = push(gh, project)
    assert refused.status_code == 400 and refused.get_json()["code"] == "no_repository"
    chosen = student.put("/api/cloud/github/repository", json={"repository": "ada/games"}).get_json()
    assert chosen == {"repository": "ada/games", "branch": "main"}


def test_commit_and_push_writes_readable_files_with_the_message(gh):
    student = connect(gh)
    project = new_project(student, game_json={"source_mode": "c",
                                              "source_c": "void rocket_race_init(void) {}\n"})
    answer = push(gh, project, message="My first game")
    assert answer.status_code == 200 and answer.get_json()["result"] == "created", answer.get_json()
    files = gh["fake"].folder_files("ada/games", folder_of(gh, project))
    assert files["src/game.c"] == b"void rocket_race_init(void) {}\n"
    assert "prg32.project.json" in files
    assert "README.md" in gh["fake"].files_of(gh["fake"].objects[gh["fake"].branches[("ada/games", "main")]]["tree"])
    # A change, a second commit; the Git tab lists both, newest first.
    current = student.get(f"/api/projects/{project['id']}").get_json()
    student.put(f"/api/projects/{project['id']}", json={
        "game_json": {"source_mode": "c", "source_c": "void rocket_race_init(void) { /* v2 */ }\n"},
        "expected_version": current["version"]})
    assert push(gh, project, message="Faster rockets").get_json()["result"] == "saved"
    history = student.get(f"/api/projects/{project['id']}/cloud/github/commits").get_json()
    assert history["linked"] and history["repository"] == "ada/games"
    assert [commit["message"] for commit in history["commits"]] == ["Faster rockets", "My first game"]


def test_both_sides_changed_is_a_conflict_with_choices(gh):
    student = connect(gh)
    project = new_project(student)
    push(gh, project)
    folder = folder_of(gh, project)
    gh["fake"].commit_files("ada/games", "main", {f"{folder}/notes.txt": b"from home"}, "edited at home")
    current = student.get(f"/api/projects/{project['id']}").get_json()
    student.put(f"/api/projects/{project['id']}", json={"title": "Rocket Race", "blocks_json": {"blocks": 2},
                                                        "expected_version": current["version"]})
    conflict = push(gh, project)
    assert conflict.status_code == 409 and conflict.get_json()["code"] == "cloud_conflict"
    assert set(conflict.get_json()["choices"]) == {"copy", "take_remote", "overwrite"}
    revision = conflict.get_json()["remote"]["revision"]
    overwritten = push(gh, project, choice="overwrite", expected_remote_revision=revision)
    assert overwritten.get_json()["result"] == "overwritten"
    assert "notes.txt" not in gh["fake"].folder_files("ada/games", folder)   # the folder is exactly the project


def test_pull_takes_the_repository_version(gh):
    student = connect(gh)
    project = new_project(student, game_json={"source_mode": "c", "source_c": "void rocket_race_init(void) {}\n"})
    push(gh, project)
    folder = folder_of(gh, project)
    gh["fake"].commit_files("ada/games", "main", {f"{folder}/src/game.c": b"void rocket_race_init(void) { /* home */ }\n"},
                            "edited on GitHub")
    taken = student.post(f"/api/projects/{project['id']}/cloud/github/pull", json={})
    assert taken.get_json()["result"] == "taken", taken.get_json()
    assert "/* home */" in taken.get_json()["project"]["game_json"]["source_c"]


def test_a_branch_moved_meanwhile_changes_nothing(gh):
    student = connect(gh)
    project = new_project(student)
    push(gh, project)
    before = dict(gh["fake"].branches)
    current = student.get(f"/api/projects/{project['id']}").get_json()
    student.put(f"/api/projects/{project['id']}", json={"blocks_json": {"blocks": 3}, "expected_version": current["version"]})
    gh["fake"].move_branch_before_update = True
    answer = push(gh, project)
    assert answer.status_code == 409 and answer.get_json()["code"] == "remote_changed"
    head = gh["fake"].branches[("ada/games", "main")]
    assert gh["fake"].objects[head]["message"] == "pushed elsewhere" and head != before[("ada/games", "main")]


def test_an_expired_token_is_refreshed_and_a_dead_one_asks_to_reconnect(gh):
    student = connect(gh)
    project = new_project(student)
    gh["clock"].now += 29_000                              # the 8-hour user token has expired
    seen = len(gh["fake"].requests)
    assert push(gh, project).status_code == 200
    assert any(url.endswith("/login/oauth/access_token") for _method, url in gh["fake"].requests[seen:])
    gh["fake"].refresh_tokens.clear()
    gh["clock"].now += 29_000
    ended = push(gh, project)
    assert ended.status_code == 401 and ended.get_json()["code"] == "reconnect"


def test_disconnecting_revokes_the_grant(gh):
    student = connect(gh)
    answer = student.post("/api/cloud/github/disconnect", json={}).get_json()
    assert answer["revoked_at_provider"] is True and gh["fake"].revoked
    with gh["app"].app_context():
        assert db.session.query(CloudAccount).count() == 0


def test_only_github_addresses_are_used():
    item = GitHub(APP_CLIENT)
    for url in ("https://api.github.com/user", "https://github.com/login/oauth/access_token"):
        cloud_storage._allowed(url, item.hosts)
    for url in ("http://api.github.com/user", "https://api.github.com.evil.test/user", "https://raw.githubusercontent.com/x"):
        with pytest.raises(CloudError):
            cloud_storage._allowed(url, item.hosts)


def test_github_is_off_without_its_settings_or_when_switched_off(tmp_path, gh):
    plain = make_app(tmp_path / "plain")
    with plain.test_request_context():
        assert "github" not in cloud_storage.configured()
    gh["app"].config["CLOUD_GITHUB_ENABLED"] = False
    with gh["app"].test_request_context():
        assert "github" not in cloud_storage.configured()
