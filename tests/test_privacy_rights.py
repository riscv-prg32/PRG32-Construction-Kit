"""Data-subject rights with synthetic students (ADR-0022, docs/privacy/rights_requests.md).

- every table is known to the rights workflows (or declared to hold nothing about a person);
- a student downloads everything about them as one structured document, without secrets,
  and cannot download anyone else's; other people's names are not in it;
- requests are registered with their deadline; only the controller's staff carry them out;
  an erasure needs an explicit confirmation naming the account;
- erasure reaches every table, folder and file, revokes cloud tokens, keeps the audit log
  under a pseudonym, and says what remains outside the kit;
- a restored backup holding an erased student is cleaned by re-applying the register;
- restriction lets the student read and download, nothing else;
- the notice version shown at each collection point is recorded;
- backups older than the retention period are deleted.
"""

from __future__ import annotations

import datetime
import json
import sys
import tarfile
from pathlib import Path

import pytest
from conftest import ADMIN_PASSWORD, make_app
from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import backup_restore  # noqa: E402

NAME, EMAIL, PASSWORD = "zq7student", "zq7student@school.test", "student-password-1"
OTHER = "kx4student"


def kit_at(data: Path):
    return make_app(data, DB_PATH=data / "construction_kit.sqlite", BUILD_ROOT=data / "builds",
                    ARTIFACT_ROOT=data / "artifacts",
                    SQLALCHEMY_DATABASE_URI=f"sqlite:///{data / 'construction_kit.sqlite'}")


@pytest.fixture()
def kit(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    return kit_at(data)


class FakeDrive:
    """Stands in for a cloud provider: records revocations."""
    revokes_at_provider = True
    revoked: list = []

    def revoke(self, tokens):
        FakeDrive.revoked.append(tokens.get("refresh_token"))
        return True


def give_a_life(app, admin, monkeypatch) -> dict:
    """A synthetic student with something in every place the kit keeps personal data."""
    from prg32_construction_kit import cloud_storage
    from prg32_construction_kit.auth import RegistrationToken
    from prg32_construction_kit.db import create_resource, db
    from prg32_construction_kit.identity import ExternalIdentity
    from prg32_construction_kit.publishing import PublishAttempt
    from prg32_construction_kit.sso import SsoOutbox

    for name in (NAME, OTHER):
        made = admin.post("/api/users", json={"username": name, "email": f"{name}@school.test", "password": PASSWORD})
        assert made.status_code == 201, made.get_json()
    student = app.test_client(login=(NAME, PASSWORD))
    me = student.get("/auth/me").get_json()["user"]
    project = student.post("/api/projects", json={"title": "Zq7 game", "author": NAME}).get_json()
    student.post("/api/sprites", json={"name": "hero", "project_id": project["id"]})
    student.post("/api/assets", json={"name": "song", "project_id": project["id"], "data": {"notes": [60]}})
    token = student.post("/auth/tokens", json={"label": "laptop", "scopes": ["read"]}).get_json()["token"]
    klass = admin.post("/api/classes", json={"name": "3B"}).get_json()
    assert admin.post(f"/api/classes/{klass['id']}/members", json={"username": NAME}).status_code in (200, 201)
    with app.app_context():
        artifact_file = Path(app.config["ARTIFACT_ROOT"]) / "zq7.prg32"
        artifact_file.write_bytes(b"PRG2" + bytes(60))
        create_resource("artifacts", {"kind": "cartridge", "name": "zq7.prg32", "path": str(artifact_file),
                                      "project_id": project["id"], "owner_id": me["id"]})
        build = create_resource("builds", {"project_id": project["id"], "status": "succeeded", "log": f"built by {NAME}",
                                           "owner_id": me["id"]})
        folder = Path(app.config["BUILD_ROOT"]) / build["id"]
        folder.mkdir(parents=True)
        (folder / "game.c").write_text("/* zq7 */")
        samples = Path(app.config["ARTIFACT_ROOT"]) / "audio" / str(me["id"])
        samples.mkdir(parents=True)
        (samples / "drum.wav").write_bytes(b"RIFF....")
        db.session.add(cloud_storage.CloudAccount(user_id=me["id"], provider="google", account_id="g-123",
                                                  account_name=EMAIL, scopes="drive.file",
                                                  tokens=cloud_storage.seal({"refresh_token": "refresh-zq7"})))
        db.session.add(cloud_storage.CloudLink(user_id=me["id"], provider="google", account_id="g-123",
                                               project_id=project["id"], file_id="file-1", remote_revision="1",
                                               content_sha256="0" * 64, local_version=1))
        db.session.add(ExternalIdentity(user_id=me["id"], provider="oidc", issuer="https://idp.school.test",
                                        subject="sub-zq7", email=EMAIL))
        db.session.add(PublishAttempt(id="pa-1", digest="d-1", user_id=me["id"], profile_id="p", artifact_id="a",
                                      state="submitted", store_host="store.school.test", cartridge_id="zq7.game",
                                      cartridge_version="1.0.0", created_at="2026-10-21T00:00:00",
                                      updated_at="2026-10-21T00:00:00"))
        db.session.add(SsoOutbox(email=EMAIL, payload="{}"))
        db.session.add(RegistrationToken(email=EMAIL, token_hash="h-zq7", expires_at="2026-11-01T00:00:00"))
        db.session.commit()
    monkeypatch.setattr("prg32_construction_kit.cloud_storage.provider_named", lambda _name: FakeDrive())
    return {"student": student, "id": me["id"], "project": project, "build": build, "token": token,
            "artifact_file": artifact_file, "samples": samples, "folder": folder}


def every_cell(app) -> list[tuple[str, str, str]]:
    from prg32_construction_kit.db import db

    found = []
    with app.app_context():
        for table in db.metadata.tables:
            for row in db.session.execute(text(f'SELECT * FROM "{table}"')).mappings():
                for column, value in row.items():
                    found.append((table, column, str(value)))
    return found


# --- the inventory -------------------------------------------------------------------------

def test_every_table_is_known_to_the_rights_workflows(kit):
    from prg32_construction_kit import privacy
    from prg32_construction_kit.db import db

    with kit.app_context():
        tables = set(db.metadata.tables)
    assert tables == set(privacy.PERSONAL_TABLES) | set(privacy.NOT_PERSONAL)
    assert not set(privacy.PERSONAL_TABLES) & set(privacy.NOT_PERSONAL)


# --- access and portability ------------------------------------------------------------------

def test_the_export_holds_everything_and_no_secret(kit, monkeypatch):
    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    response = life["student"].get("/api/me/privacy/export")
    assert response.status_code == 200 and "attachment" in response.headers["Content-Disposition"]
    document = response.get_json()
    assert document["format"] == "prg32-personal-data-export" and document["subject"]["username"] == NAME
    tables = document["tables"]
    for table in ("users", "projects", "sprites", "assets", "artifacts", "builds", "api_tokens", "cloud_accounts",
                  "cloud_links", "external_identities", "class_members", "publish_attempts", "sso_outbox",
                  "registration_tokens", "audit_events", "privacy_notice_records"):
        assert tables[table], table
    assert tables["users"][0]["password_hash"] == "(kept secret, not exported)"
    assert tables["cloud_accounts"][0]["tokens"] == "(kept secret, not exported)"
    raw = json.dumps(document)
    assert "refresh-zq7" not in raw and life["token"] not in raw and "h-zq7" not in raw
    assert ADMIN_PASSWORD not in raw and '"admin"' not in raw       # other people's names are not theirs
    assert {item.get("name") or item.get("audio_sample") for item in document["files"]} >= {"zq7.prg32", "drum.wav"}
    assert any(place["where"] == "backups" for place in document["not_in_this_export"])
    # A project archive is not this document: the export is per person, across every table.
    assert set(document["tables"]) == set(__import__("prg32_construction_kit.privacy").privacy.PERSONAL_TABLES)


def test_nobody_downloads_somebody_elses_data(kit, monkeypatch):
    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    other = kit.test_client(login=(OTHER, PASSWORD))
    assert other.get(f"/api/admin/privacy/users/{life['id']}/export").status_code == 403
    mine = other.get("/api/me/privacy/export").get_json()
    assert mine["subject"]["username"] == OTHER and NAME not in json.dumps(mine)
    # An API token, even with every scope the student has, never makes privacy requests.
    by_token = kit.test_client(login=None)
    refused = by_token.get("/api/me/privacy/export", headers={"Authorization": f"Bearer {life['token']}"})
    assert refused.status_code == 403
    assert admin.get(f"/api/admin/privacy/users/{life['id']}/export").get_json()["subject"]["id"] == life["id"]


# --- the request register --------------------------------------------------------------------

def test_requests_have_a_deadline_and_only_staff_decide(kit, monkeypatch):
    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    sent = life["student"].post("/api/me/privacy/requests", json={"kind": "rectification", "details": "my email changed"})
    assert sent.status_code == 201
    item = sent.get_json()
    received = datetime.datetime.fromisoformat(item["received_at"].replace("Z", "+00:00"))
    due = datetime.datetime.fromisoformat(item["due_at"])
    assert (due - received).days == 30 and item["verified_by"] == "signed in" and not item["overdue"]
    assert life["student"].post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "complete"}).status_code == 403
    assert life["student"].post("/api/me/privacy/requests", json={"kind": "nonsense"}).status_code == 400
    extended = admin.post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "extend", "days": 30,
                                                                             "reason": "waiting for the school office"})
    assert extended.get_json()["extension_reason"] and extended.get_json()["due_at"] > item["due_at"]
    assert admin.post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "complete"}).status_code == 400
    done = admin.post(f"/api/admin/privacy/requests/{item['id']}",
                      json={"action": "complete", "reason": "email corrected with the account editor"}).get_json()
    assert done["status"] == "completed" and done["handled_by"] == "admin"
    on_behalf = admin.post(f"/api/admin/privacy/users/{life['id']}/requests", json={"kind": "objection"})
    assert on_behalf.status_code == 400                        # say how the identity was checked
    letter = admin.post(f"/api/admin/privacy/users/{life['id']}/requests",
                        json={"kind": "objection", "verified_by": "parent, in person, school ID seen"})
    assert letter.status_code == 201
    refused = admin.post(f"/api/admin/privacy/requests/{letter.get_json()['id']}", json={"action": "refuse"})
    assert refused.status_code == 400                          # a refusal needs its reason
    mine = life["student"].get("/api/me/privacy/requests").get_json()["requests"]
    assert {item["kind"] for item in mine} == {"rectification", "objection"}


# --- erasure ---------------------------------------------------------------------------------

def test_erasure_reaches_everything_the_kit_holds(kit, monkeypatch):
    admin = kit.test_client()
    FakeDrive.revoked = []
    life = give_a_life(kit, admin, monkeypatch)
    item = life["student"].post("/api/me/privacy/requests", json={"kind": "erasure"}).get_json()
    unconfirmed = admin.post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "complete"})
    assert unconfirmed.status_code == 400 and unconfirmed.get_json()["code"] == "confirm_required"
    done = admin.post(f"/api/admin/privacy/requests/{item['id']}",
                      json={"action": "complete", "confirm_user_id": life["id"]}).get_json()
    assert done["status"] == "completed", done["outcome"]["failures"]
    outcome = done["outcome"]
    assert FakeDrive.revoked == ["refresh-zq7"]
    assert outcome["steps"]["cloud_tokens"] == [{"provider": "google", "revoked_at_provider": True}]
    store = [place for place in outcome["outside_the_kit"] if place["where"] == "Cartridge Store"]
    assert store and store[0]["items"][0]["cartridge"] == "zq7.game"
    assert outcome["backups_expire_by"] and done["user_id"] is None and done["subject"].startswith("person-")
    # Nothing in any table names the student any more...
    leftovers = [cell for cell in every_cell(kit) if NAME in cell[2] or EMAIL in cell[2] or "sub-zq7" in cell[2]]
    assert leftovers == []
    from prg32_construction_kit import privacy
    from prg32_construction_kit.db import db

    with kit.app_context():
        for table, (kind, column) in privacy.PERSONAL_TABLES.items():
            if kind == "user":
                count = db.session.execute(text(f'SELECT COUNT(*) FROM "{table}" WHERE "{column}" = :id'),
                                           {"id": life["id"]}).scalar()
                assert count == 0, table
    # ... no file or folder is left ...
    assert not life["artifact_file"].exists() and not life["samples"].exists() and not life["folder"].exists()
    # ... and the audit log still shows what happened, under the pseudonym.
    events = admin.get("/api/admin/audit?limit=500").get_json()
    events = events.get("events", events) if isinstance(events, dict) else events
    assert any(event.get("actor_name") == done["subject"] for event in events)
    assert kit.test_client(login=None).post("/auth/login", data={"username": NAME, "password": PASSWORD}).status_code != 302


def test_a_restored_backup_does_not_bring_an_erased_student_back(tmp_path, monkeypatch):
    data = tmp_path / "old"
    data.mkdir()
    kit = kit_at(data)
    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    archive = tmp_path / "before-erasure.tar"
    backup_restore.backup(data, archive, None, False)
    item = life["student"].post("/api/me/privacy/requests", json={"kind": "erasure"}).get_json()
    admin.post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "complete", "confirm_user_id": life["id"]})
    register = tmp_path / "erasures.json"
    assert kit.test_cli_runner().invoke(args=["prg32-privacy-erasures", "--out", str(register)]).exit_code == 0
    restored_data = tmp_path / "restored"
    backup_restore.restore(archive, restored_data)
    restored = kit_at(restored_data)
    assert NAME in json.dumps(restored.test_client().get("/api/users").get_json())      # back, from the backup
    result = restored.test_cli_runner().invoke(args=["prg32-privacy-reapply", "--register", str(register)])
    assert result.exit_code == 0 and '"completed"' in result.output
    assert NAME not in json.dumps(restored.test_client().get("/api/users").get_json())
    assert [cell for cell in every_cell(restored) if NAME in cell[2] or EMAIL in cell[2]] == []


def test_old_backups_are_deleted_after_the_retention_period(tmp_path):
    folder = tmp_path / "backups"
    folder.mkdir()
    data = tmp_path / "data"
    data.mkdir()
    kit_at(data)
    backup_restore.backup(data, folder / "new.tar", None, False)
    backup_restore.backup(data, folder / "old.tar", None, False)
    later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=20)
    assert backup_restore.prune(folder, 35, now=later) == []
    with tarfile.open(folder / "new.tar") as archive:
        assert json.loads(archive.extractfile("MANIFEST.json").read())["created"]
    much_later = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=36)
    assert backup_restore.prune(folder, 35, dry_run=True, now=much_later) == ["new.tar", "old.tar"]
    assert backup_restore.prune(folder, 35, now=much_later) == ["new.tar", "old.tar"]
    assert list(folder.iterdir()) == []


# --- restriction --------------------------------------------------------------------------------

def test_a_restricted_account_can_read_and_download_but_not_change(kit, monkeypatch):
    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    item = life["student"].post("/api/me/privacy/requests", json={"kind": "restriction"}).get_json()
    admin.post(f"/api/admin/privacy/requests/{item['id']}", json={"action": "complete", "reason": "while we check"})
    student = life["student"]
    assert student.get("/api/projects").status_code == 200
    assert student.get("/api/me/privacy/export").status_code == 200
    blocked = student.post("/api/projects", json={"title": "new"})
    assert blocked.status_code == 423 and blocked.get_json()["code"] == "restricted"
    assert student.put(f"/api/projects/{life['project']['id']}", json={"title": "x"}).status_code == 423
    assert student.post(f"/api/projects/{life['project']['id']}/package", json={}).status_code == 423
    assert student.post("/api/me/privacy/requests", json={"kind": "objection"}).status_code == 201
    lifted = student.post("/api/me/privacy/requests", json={"kind": "restriction", "details": "lift it"}).get_json()
    admin.post(f"/api/admin/privacy/requests/{lifted['id']}", json={"action": "complete", "restricted": False,
                                                                    "reason": "check finished"})
    assert student.post("/api/projects", json={"title": "new"}).status_code == 201


# --- notices ------------------------------------------------------------------------------------

def test_the_notice_version_shown_is_recorded_at_each_collection_point(kit, monkeypatch):
    from prg32_construction_kit import privacy
    from prg32_construction_kit.db import db
    from prg32_construction_kit.privacy import PrivacyNoticeRecord

    admin = kit.test_client()
    life = give_a_life(kit, admin, monkeypatch)
    kit.test_client(login=(NAME, PASSWORD))            # signs in again, now a class member
    with kit.app_context():
        rows = db.session.query(PrivacyNoticeRecord).filter_by(user_id=life["id"]).all()
        seen = {(row.notice, row.version) for row in rows}
        assert ("account", privacy.notices()["account"]["version"]) in seen
        assert ("classes", privacy.notices()["classes"]["version"]) in seen
        assert len([row for row in rows if row.notice == "account"]) == 1        # once per version
    for page, notice in (("/auth/login", "guest"), ("/auth/login", "account"), ("/auth/register", "account"),
                         ("/privacy", "publishing")):
        html = kit.test_client(login=None).get(page).get_data(as_text=True)
        assert f'data-privacy-notice="{notice}"' in html, (page, notice)
    account = life["student"].get("/account").get_data(as_text=True)
    assert 'data-privacy-notice="cloud"' in account and 'id="downloadMyData"' in account
    assert 'data-privacy-notice="publishing"' in admin.get("/publish").get_data(as_text=True)
    assert 'data-privacy-notice="classes"' in admin.get("/classes").get_data(as_text=True)
    listed = kit.test_client(login=None).get("/api/privacy/notices").get_json()["notices"]
    for item in listed:
        assert (ROOT / item["full"]).is_file(), item["full"]
        assert item["version"] in (ROOT / item["full"]).read_text(), item["id"]


def test_the_audit_log_and_old_signup_links_expire(kit):
    from prg32_construction_kit import retention, security
    from prg32_construction_kit.auth import RegistrationToken
    from prg32_construction_kit.db import db

    with kit.app_context():
        db.session.add(security.AuditEvent(created_at="2020-01-01T00:00:00", action="old"))
        db.session.add(RegistrationToken(email="old@school.test", token_hash="h-old", expires_at="2020-01-02T00:00:00"))
        db.session.commit()
        shown = retention.apply(kit.config, dry_run=True)
        assert shown["expired_audit_events"] == 1 and shown["expired_signup_links"] == 1
        retention.apply(kit.config, dry_run=False)
        assert db.session.query(security.AuditEvent).filter_by(action="old").count() == 0
        assert db.session.query(RegistrationToken).filter_by(email="old@school.test").count() == 0


def test_answered_requests_expire_only_when_the_controller_sets_a_period(kit):
    from prg32_construction_kit import retention
    from prg32_construction_kit.db import db
    from prg32_construction_kit.privacy import PrivacyRequest

    with kit.app_context():
        db.session.add(PrivacyRequest(subject_ref="person-old", kind="access", status="completed",
                                      received_at="2020-01-01T00:00:00", due_at="2020-01-31T00:00:00",
                                      completed_at="2020-01-02T00:00:00"))
        db.session.add(PrivacyRequest(subject_ref="person-open", kind="erasure", status="received",
                                      received_at="2020-01-01T00:00:00", due_at="2020-01-31T00:00:00"))
        db.session.commit()
        assert retention.apply(kit.config, dry_run=False)["expired_privacy_requests"] == 0   # default: keep
        kit.config["PRG32_KIT_PRIVACY_REQUEST_DAYS"] = 730
        assert retention.apply(kit.config, dry_run=False)["expired_privacy_requests"] == 1
        left = [item.subject_ref for item in db.session.query(PrivacyRequest).all()]
        assert left == ["person-open"]                       # an open request is never removed
