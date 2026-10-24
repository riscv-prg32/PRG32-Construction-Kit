"""Cloud storage (ADR-0019): one contract, run against fake Google Drive and OneDrive.

Every test runs for both providers (tests/fake_cloud.py). Real tenants: opt-in
tests/test_cloud_live.py.
"""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from conftest import make_app
from fake_cloud import FakeCloud
from test_auth import make_student, student_client

from prg32_construction_kit import cloud_storage
from prg32_construction_kit.cloud_storage import CloudAccount, CloudError, CloudLink
from prg32_construction_kit.db import ProjectRevision, db

PROVIDERS = ("google", "onedrive")
CLOUD_SETTINGS = {"CLOUD_GOOGLE_CLIENT_ID": "kit-google-client", "CLOUD_GOOGLE_CLIENT_SECRET": "test-only",
                  "CLOUD_ONEDRIVE_CLIENT_ID": "kit-onedrive-client", "PUBLIC_URL": "https://kit.school.test"}


class Clock:
    def __init__(self):
        self.now = 1_800_000_000.0

    def __call__(self):
        return self.now


@pytest.fixture()
def clock(monkeypatch):
    item = Clock()
    monkeypatch.setattr(cloud_storage, "now_seconds", item)
    return item


@pytest.fixture()
def sleeps(monkeypatch):
    waited: list[float] = []
    monkeypatch.setattr(cloud_storage, "sleep", waited.append)
    return waited


@pytest.fixture(params=PROVIDERS)
def cloud(request, tmp_path, clock, sleeps, monkeypatch):
    """A kit with both providers set up, a student, and a fake of the provider under test."""
    app = make_app(tmp_path, **CLOUD_SETTINGS)
    fake = FakeCloud(request.param, clock)
    monkeypatch.setattr(cloud_storage, "transport", fake)
    admin = app.test_client()
    make_student(admin, "ada")
    student = student_client(app, "ada")
    return {"app": app, "fake": fake, "name": request.param, "student": student, "admin": admin, "sleeps": sleeps}


def connect(cloud, browser=None, code="good-code"):
    browser = browser or cloud["student"]
    start = browser.post(f"/api/cloud/{cloud['name']}/connect", json={"consent": True})
    assert start.status_code == 200, start.get_json()
    state = parse_qs(urlsplit(start.get_json()["redirect"]).query)["state"][0]
    return browser.get(f"/cloud/{cloud['name']}/callback?state={state}&code={code}")


def new_project(browser, title="Cloud Game", **fields):
    return browser.post("/api/projects", json={"title": title, "blocks_json": {"blocks": 1}, **fields}).get_json()


def push(cloud, project, **body):
    return cloud["student"].post(f"/api/projects/{project['id']}/cloud/{cloud['name']}/push", json=body)


def pull(cloud, project, **body):
    return cloud["student"].post(f"/api/projects/{project['id']}/cloud/{cloud['name']}/pull", json=body)


def save(browser, project, **fields):
    current = browser.get(f"/api/projects/{project['id']}").get_json()
    answer = browser.put(f"/api/projects/{project['id']}", json={**fields, "expected_version": current["version"]})
    assert answer.status_code == 200, answer.get_json()
    return answer.get_json()


def other_archive(cloud, title="Changed in the cloud"):
    """The bytes of a different project archive, as another computer would save it."""
    other = new_project(cloud["admin"], title=title, blocks_json={"blocks": 99})
    return cloud["admin"].get(f"/api/projects/{other['id']}/archive").data


def only_file(cloud) -> dict:
    files = cloud["fake"].live_files()
    assert len(files) == 1, files
    return files[0]


# --- without cloud settings ----------------------------------------------------------

def test_without_settings_there_is_no_cloud_and_nothing_else_changes(client):
    assert client.get("/api/cloud").get_json() == {"providers": []}
    project = new_project(client)
    refused = client.post(f"/api/projects/{project['id']}/cloud/google/push", json={})
    assert refused.status_code == 404 and refused.get_json()["code"] == "not_configured"
    assert client.put(f"/api/projects/{project['id']}", json={"title": "still saves"}).status_code == 200


def test_guests_never_reach_cloud_storage(anon):
    assert anon.get("/api/cloud").status_code == 401
    assert anon.get("/cloud/google/callback?state=x&code=y").status_code in (302, 401)


# --- consent and tokens --------------------------------------------------------------

def test_connecting_needs_consent_and_uses_pkce_and_least_privilege(cloud):
    student = cloud["student"]
    refused = student.post(f"/api/cloud/{cloud['name']}/connect", json={})
    assert refused.status_code == 400 and refused.get_json()["code"] == "consent_required"
    start = student.post(f"/api/cloud/{cloud['name']}/connect", json={"consent": True}).get_json()["redirect"]
    query = {key: values[0] for key, values in parse_qs(urlsplit(start).query).items()}
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) >= 43
    assert query["redirect_uri"] == f"https://kit.school.test/cloud/{cloud['name']}/callback"
    granted = query["scope"].split()
    assert granted == (["https://www.googleapis.com/auth/drive.file"] if cloud["name"] == "google"
                       else ["Files.ReadWrite.AppFolder", "User.Read", "offline_access"])
    assert not any(scope in granted for scope in ("https://www.googleapis.com/auth/drive", "Files.ReadWrite.All"))


def test_a_callback_works_once_and_only_for_who_started_it(cloud):
    student = cloud["student"]
    start = student.post(f"/api/cloud/{cloud['name']}/connect", json={"consent": True}).get_json()["redirect"]
    state = parse_qs(urlsplit(start).query)["state"][0]
    assert student.get(f"/cloud/{cloud['name']}/callback?state=wrong&code=good-code").status_code == 400
    # The wrong state used the flow up: the right one no longer works either.
    assert student.get(f"/cloud/{cloud['name']}/callback?state={state}&code=good-code").status_code == 400
    assert connect(cloud).status_code == 302
    assert student.get(f"/cloud/{cloud['name']}/callback?state={state}&code=good-code").status_code == 400


def test_refusing_permission_connects_nothing(cloud):
    start = cloud["student"].post(f"/api/cloud/{cloud['name']}/connect", json={"consent": True}).get_json()["redirect"]
    state = parse_qs(urlsplit(start).query)["state"][0]
    answer = cloud["student"].get(f"/cloud/{cloud['name']}/callback?state={state}&error=access_denied")
    assert answer.status_code == 400
    assert not [p for p in cloud["student"].get("/api/cloud").get_json()["providers"] if p["connected"]]


def test_tokens_are_encrypted_and_never_shown_or_logged(cloud):
    assert connect(cloud).status_code == 302
    token = next(iter(cloud["fake"].access))
    status = cloud["student"].get("/api/cloud").get_json()
    mine = next(p for p in status["providers"] if p["name"] == cloud["name"])
    assert mine["connected"] and mine["account_name"] == "ada@school.test"
    assert token not in json.dumps(status)
    with cloud["app"].app_context():
        row = db.session.query(CloudAccount).one()
        assert token not in row.tokens and cloud_storage.unseal(row.tokens)["access_token"] == token
        events = json.dumps([dict(event) for event in db.session.execute(db.text("SELECT * FROM audit_events")).mappings()],
                            default=str)
        assert "cloud_consent" in events and "cloud_connect" in events
        assert token not in events
    project = new_project(cloud["student"])
    assert push(cloud, project).status_code == 200
    assert token not in json.dumps(cloud["student"].get(f"/api/projects/{project['id']}/cloud").get_json())


def test_a_connection_needs_a_browser_not_an_api_token(cloud):
    token = cloud["student"].post("/auth/tokens", json={"label": "script", "scopes": ["read", "write"]}).get_json()
    script = cloud["app"].test_client(login=None)
    answer = script.post(f"/api/cloud/{cloud['name']}/connect", json={"consent": True},
                         headers={"Authorization": "Bearer " + token["token"]})
    assert answer.status_code == 403 and answer.get_json()["code"] == "browser_only"


# --- saving and taking back ----------------------------------------------------------------

def test_push_creates_then_updates_and_an_unchanged_project_sends_nothing(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    first = push(cloud, project).get_json()
    assert first["result"] == "created"
    stored = only_file(cloud)
    assert stored["name"].endswith(".prg32project.zip") and project["id"] in stored["name"]
    writes = len([entry for entry in cloud["fake"].log if entry[0] in ("POST", "PUT", "PATCH")])
    assert push(cloud, project).get_json()["result"] == "in_sync"
    assert len([entry for entry in cloud["fake"].log if entry[0] in ("POST", "PUT", "PATCH")]) == writes
    save(cloud["student"], project, blocks_json={"blocks": 2})
    assert push(cloud, project).get_json()["result"] == "saved"
    assert len(cloud["fake"].live_files()) == 1 and stored["version"] == 2


def test_the_cloud_file_is_the_projects_archive(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    assert only_file(cloud)["data"] == cloud["student"].get(f"/api/projects/{project['id']}/archive").data


def test_pull_takes_a_cloud_change_when_nothing_changed_here(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], other_archive(cloud))
    taken = pull(cloud, project)
    assert taken.status_code == 200 and taken.get_json()["result"] == "taken"
    updated = taken.get_json()["project"]
    assert updated["title"] == "Changed in the cloud" and updated["version"] == project["version"] + 1
    assert updated["id"] == project["id"]
    assert pull(cloud, project).get_json()["result"] == "nothing_new"
    with cloud["app"].app_context():
        reasons = [row.reason for row in db.session.query(ProjectRevision).filter_by(project_id=project["id"])]
    assert "cloud" in reasons      # what was here before is in the project's history


def test_a_rename_in_the_cloud_is_not_a_change(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], rename="renamed.prg32project.zip")
    assert pull(cloud, project).get_json()["result"] == "nothing_new"
    save(cloud["student"], project, blocks_json={"blocks": 5})
    assert push(cloud, project).get_json()["result"] == "saved"


# --- conflicts: never overwrite silently -------------------------------------------------------

def test_push_over_a_cloud_change_is_a_conflict_with_choices(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    remote = only_file(cloud)
    cloud["fake"].edit_elsewhere(remote["id"], other_archive(cloud))
    before = remote["data"]
    save(cloud["student"], project, blocks_json={"blocks": 3})
    refused = push(cloud, project)
    body = refused.get_json()
    assert refused.status_code == 409 and body["code"] == "cloud_conflict"
    assert body["choices"] == ["copy", "take_remote", "overwrite"] and body["remote"]["revision"]
    assert remote["data"] == before         # nothing was written
    # "overwrite" must name the cloud version the student looked at.
    stale = push(cloud, project, choice="overwrite", expected_remote_revision="an older one")
    assert stale.status_code == 409 and remote["data"] == before
    done = push(cloud, project, choice="overwrite", expected_remote_revision=body["remote"]["revision"])
    assert done.status_code == 200 and done.get_json()["result"] == "overwritten"
    assert remote["data"] == cloud["student"].get(f"/api/projects/{project['id']}/archive").data


def test_pull_over_local_changes_is_a_conflict_and_take_remote_names_the_version(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], other_archive(cloud))
    mine = save(cloud["student"], project, title="My local work", blocks_json={"blocks": 4})
    refused = pull(cloud, project)
    assert refused.status_code == 409 and refused.get_json()["code"] == "cloud_conflict"
    assert cloud["student"].get(f"/api/projects/{project['id']}").get_json()["title"] == "My local work"
    assert pull(cloud, project, choice="take_remote").status_code == 409             # no version named
    assert pull(cloud, project, choice="take_remote", expected_version=mine["version"] - 1).status_code == 409
    taken = pull(cloud, project, choice="take_remote", expected_version=mine["version"])
    assert taken.status_code == 200 and taken.get_json()["project"]["title"] == "Changed in the cloud"
    history = cloud["student"].get(f"/api/projects/{project['id']}/revisions").get_json()["revisions"]
    assert any(item["title"] == "My local work" for item in history)     # the local work is kept


def test_copy_keeps_both(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], other_archive(cloud))
    save(cloud["student"], project, title="Mine", blocks_json={"blocks": 6})
    copied = pull(cloud, project, choice="copy")
    assert copied.status_code == 201
    assert copied.get_json()["project"]["id"] != project["id"]
    assert cloud["student"].get(f"/api/projects/{project['id']}").get_json()["title"] == "Mine"
    # ... or the local version as a new cloud file next to the changed one.
    assert push(cloud, project, choice="copy").get_json()["result"] == "created"
    assert len(cloud["fake"].live_files()) == 2


def test_a_save_here_while_taking_the_cloud_version_changes_nothing(cloud, monkeypatch):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], other_archive(cloud))
    import importlib

    kit_db = importlib.import_module("prg32_construction_kit.db")

    real = kit_db.restore_project_state

    def save_in_between(*args, **kwargs):
        kit_db.update_resource("projects", project["id"], {"title": "saved meanwhile"})
        return real(*args, **kwargs)

    monkeypatch.setattr(kit_db, "restore_project_state", save_in_between)
    answer = pull(cloud, project)
    assert answer.status_code == 409
    assert cloud["student"].get(f"/api/projects/{project['id']}").get_json()["title"] == "saved meanwhile"


def test_a_cloud_file_deleted_elsewhere_is_never_silently_recreated(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    only_file(cloud)["trashed"] = True
    save(cloud["student"], project, blocks_json={"blocks": 8})
    refused = push(cloud, project)
    assert refused.status_code == 409 and refused.get_json()["code"] == "remote_missing"
    assert refused.get_json()["choices"] == ["copy"]
    assert push(cloud, project, choice="copy").get_json()["result"] == "created"


# --- expiry, revocation, disconnect, account switching ------------------------------------------

def test_an_expired_token_is_refreshed_without_the_student_noticing(cloud, clock):
    connect(cloud)
    project = new_project(cloud["student"])
    clock.now += 7200
    assert push(cloud, project).status_code == 200
    with cloud["app"].app_context():
        assert cloud_storage.unseal(db.session.query(CloudAccount).one().tokens)["expires_at"] > clock.now


def test_a_token_refused_by_the_provider_is_refreshed_once(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    cloud["fake"].expire_tokens()           # the provider ended it early
    assert push(cloud, project).status_code == 200


def test_a_revoked_connection_asks_to_reconnect_and_changes_nothing(cloud, clock):
    connect(cloud)
    project = new_project(cloud["student"])
    cloud["fake"].revoke_refresh_tokens()
    cloud["fake"].expire_tokens()
    refused = push(cloud, project)
    assert refused.status_code == 401 and refused.get_json()["code"] == "reconnect"
    assert cloud["fake"].live_files() == []
    status = next(p for p in cloud["student"].get("/api/cloud").get_json()["providers"] if p["name"] == cloud["name"])
    assert status["needs_reconnect"] is True
    assert connect(cloud).status_code == 302
    assert push(cloud, project).status_code == 200


def test_disconnect_forgets_the_tokens_and_revokes_where_the_provider_can(cloud):
    connect(cloud)
    refresh = next(iter(cloud["fake"].refresh))
    answer = cloud["student"].post(f"/api/cloud/{cloud['name']}/disconnect").get_json()
    with cloud["app"].app_context():
        assert db.session.query(CloudAccount).count() == 0
    if cloud["name"] == "google":
        assert answer["revoked_at_provider"] is True and refresh in cloud["fake"].revoked
    else:   # Microsoft has no per-app refresh-token revocation: say so
        assert answer["revoked_at_provider"] is False and "account settings" in answer["note"]
    project = new_project(cloud["student"])
    assert push(cloud, project).get_json()["code"] == "not_connected"


def test_switching_cloud_accounts_never_writes_to_the_other_accounts_file(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    first = only_file(cloud)
    cloud["fake"].account = {"id": "acct-2", "name": "ada.home@example.test"}
    connect(cloud)
    save(cloud["student"], project, blocks_json={"blocks": 7})
    refused = push(cloud, project)
    assert refused.status_code == 409 and refused.get_json()["code"] == "other_account"
    assert pull(cloud, project).get_json()["code"] == "other_account"
    assert first["version"] == 1
    assert push(cloud, project, choice="copy").get_json()["result"] == "created"
    with cloud["app"].app_context():
        assert db.session.query(CloudLink).one().account_id == "acct-2"


# --- outages and retries ---------------------------------------------------------------------

def test_a_short_outage_is_retried_with_bounded_backoff(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    save(cloud["student"], project, blocks_json={"blocks": 9})
    cloud["fake"].outage = 2
    assert push(cloud, project).status_code == 200
    assert cloud["sleeps"] and max(cloud["sleeps"]) <= cloud_storage.MAX_RETRY_AFTER


def test_a_long_outage_is_a_retryable_refusal_after_three_attempts(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    save(cloud["student"], project, blocks_json={"blocks": 10})
    cloud["fake"].outage = 100
    before = len(cloud["fake"].log)
    refused = push(cloud, project)
    assert refused.status_code == 503 and refused.get_json()["retryable"] is True
    assert len(cloud["fake"].log) - before == 3
    cloud["fake"].outage = 0
    assert push(cloud, project).get_json()["result"] == "saved"


def test_a_dropped_connection_is_retryable_and_nothing_is_half_done(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    cloud["fake"].drop = 10
    refused = push(cloud, project)
    assert refused.status_code == 503 and refused.get_json()["retryable"] is True
    assert cloud["fake"].live_files() == []
    cloud["fake"].drop = 0
    assert push(cloud, project).get_json()["result"] == "created"


def test_one_dropped_connection_is_retried(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    cloud["fake"].drop = 1
    assert push(cloud, project).get_json()["result"] == "created"
    assert cloud["sleeps"] == [cloud_storage.RETRY_DELAYS[0]]


def test_a_save_checks_the_cloud_version_itself(cloud):
    """Between the kit's look at the file and its write, somebody else saved: the write is refused."""
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    remote = only_file(cloud)
    stale = cloud["fake"].revision(remote)
    cloud["fake"].edit_elsewhere(remote["id"], b"newer")
    with cloud["app"].app_context(), cloud["app"].test_request_context():
        account = db.session.query(CloudAccount).one()
        item = cloud_storage.configured()[cloud["name"]]
        with pytest.raises(cloud_storage.RemoteChanged):
            item.save(cloud_storage.Api(item, account), remote["id"], b"mine", "digest", stale)
    assert remote["data"] == b"newer"


def test_a_create_stored_but_not_confirmed_is_found_again_not_duplicated(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    cloud["fake"].store_then_fail = True
    refused = push(cloud, project)
    assert refused.status_code == 503 and len(cloud["fake"].live_files()) == 1   # stored, but not confirmed
    assert push(cloud, project).status_code == 200
    assert len(cloud["fake"].live_files()) == 1


# --- files, ownership, boundaries ---------------------------------------------------------------

def test_open_makes_a_linked_project_from_a_cloud_file(cloud):
    connect(cloud)
    project = new_project(cloud["student"], title="From another computer")
    push(cloud, project)
    files = cloud["student"].get(f"/api/cloud/{cloud['name']}/files").get_json()["files"]
    assert [item["project_id"] for item in files] == [project["id"]]
    opened = cloud["student"].post(f"/api/cloud/{cloud['name']}/files/{files[0]['file_id']}/open").get_json()
    assert opened["project"]["title"] == "From another computer" and opened["linked"] is False


def test_deleting_a_cloud_file_names_its_version_and_goes_to_the_trash(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    remote = only_file(cloud)
    path = f"/api/cloud/{cloud['name']}/files/{remote['id']}"
    assert cloud["student"].delete(path).status_code == 400
    revision = cloud["fake"].revision(remote)
    cloud["fake"].edit_elsewhere(remote["id"], b"changed")
    assert cloud["student"].delete(f"{path}?revision={revision}").status_code == 409
    assert remote["trashed"] is False
    assert cloud["student"].delete(f"{path}?revision={cloud['fake'].revision(remote)}").status_code == 200
    assert remote["trashed"] is True and remote["id"] in cloud["fake"].files     # recoverable
    with cloud["app"].app_context():
        assert db.session.query(CloudLink).count() == 0


def test_only_the_owner_syncs_a_project(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    make_student(cloud["admin"], "bob")
    bob = student_client(cloud["app"], "bob")
    connect(cloud, bob)
    assert bob.post(f"/api/projects/{project['id']}/cloud/{cloud['name']}/push", json={}).status_code == 404
    assert bob.post(f"/api/projects/{project['id']}/cloud/{cloud['name']}/pull", json={}).status_code == 404


def test_a_window_opened_as_another_user_is_refused(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    answer = cloud["student"].post(f"/api/projects/{project['id']}/cloud/{cloud['name']}/push", json={},
                                   headers={"X-PRG32-User": "99999"})
    assert answer.status_code == 409 and answer.get_json()["code"] == "user_changed"


def test_a_cloud_file_that_is_not_a_project_is_refused(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    cloud["fake"].edit_elsewhere(only_file(cloud)["id"], b"PK\x03\x04 not really a zip")
    answer = pull(cloud, project)
    assert answer.status_code == 422 and answer.get_json()["code"] == "bad_file"


def test_files_the_kit_did_not_make_stay_invisible_and_untouched(cloud):
    """Least privilege, as drive.file and the OneDrive app folder enforce it."""
    connect(cloud)
    mine = cloud["fake"].add_foreign("holiday-photos.prg32project.zip", b"the student's own file")
    project = new_project(cloud["student"])
    push(cloud, project)
    files = cloud["student"].get(f"/api/cloud/{cloud['name']}/files").get_json()["files"]
    assert mine["id"] not in [item["file_id"] for item in files]
    assert cloud["student"].post(f"/api/cloud/{cloud['name']}/files/{mine['id']}/open").status_code == 404
    assert cloud["student"].delete(f"/api/cloud/{cloud['name']}/files/{mine['id']}?revision=1").status_code in (200, 404)
    assert (mine["data"], mine["version"], mine["trashed"]) == (b"the student's own file", 1, False)


def test_an_outage_while_taking_the_cloud_version_changes_nothing_anywhere(cloud):
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    remote = only_file(cloud)
    cloud["fake"].edit_elsewhere(remote["id"], other_archive(cloud))
    before_remote = bytes(remote["data"])
    before_local = cloud["student"].get(f"/api/projects/{project['id']}").get_json()
    cloud["fake"].outage = 100
    refused = pull(cloud, project)
    assert refused.status_code == 503 and refused.get_json()["retryable"] is True
    after_local = cloud["student"].get(f"/api/projects/{project['id']}").get_json()
    assert (after_local["version"], after_local["title"]) == (before_local["version"], before_local["title"])
    assert remote["data"] == before_remote


def test_the_check_then_write_window_differs_by_provider(cloud):
    """Recorded honestly (ADR-0019): Drive cannot refuse a change made between the kit's check
    and its write; OneDrive's If-Match does."""
    connect(cloud)
    project = new_project(cloud["student"])
    push(cloud, project)
    remote = only_file(cloud)
    save(cloud["student"], project, blocks_json={"blocks": 11})
    cloud["fake"].before_write = lambda: cloud["fake"].edit_elsewhere(remote["id"], b"written in the window")
    answer = push(cloud, project)
    if cloud["name"] == "google":
        assert answer.status_code == 200          # the known gap: the change in the window is replaced
    else:
        assert answer.status_code == 409 and remote["data"] == b"written in the window"


def test_the_kit_only_talks_to_the_providers_addresses():
    drive = cloud_storage.GoogleDrive("id")
    for url in ("http://www.googleapis.com/drive/v3/files", "https://evil.test/drive", "https://www.googleapis.com:8443/x",
                "https://user:pw@www.googleapis.com/x", "https://www.googleapis.com.evil.test/x"):
        with pytest.raises(CloudError):
            cloud_storage._allowed(url, drive.hosts)
    onedrive = cloud_storage.OneDrive("id")
    cloud_storage._allowed("https://public.files.1drv.com/dl/1", (), onedrive.download_suffixes)
    with pytest.raises(CloudError):
        cloud_storage._allowed("https://169.254.169.254/latest", (), onedrive.download_suffixes)


def test_onedrive_refuses_projects_over_its_simple_upload_limit(tmp_path, clock, monkeypatch):
    app = make_app(tmp_path, **CLOUD_SETTINGS)
    fake = FakeCloud("onedrive", clock)
    monkeypatch.setattr(cloud_storage, "transport", fake)
    monkeypatch.setattr(cloud_storage.OneDrive, "max_upload", 100)
    client = app.test_client()
    connect({"name": "onedrive", "student": client})
    project = new_project(client)
    answer = client.post(f"/api/projects/{project['id']}/cloud/onedrive/push", json={})
    assert answer.status_code == 413 and answer.get_json()["code"] == "too_large"
