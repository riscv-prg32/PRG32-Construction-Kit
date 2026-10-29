"""The email sending queue, the activity log and the statistics (docs/activity_and_statistics.md)."""

from __future__ import annotations

import csv
import io
import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

from conftest import make_app


def put(client, **settings):
    return client.put("/api/admin/settings", json={"settings": settings})


# --- the mail queue ----------------------------------------------------------------------------

def _fake_smtp(monkeypatch, *, delay=0.05, fail=0):
    """A pretend SMTP server that counts how many messages it holds at the same time."""
    state = {"now": 0, "most": 0, "sent": [], "fail": fail}
    lock = threading.Lock()

    def transport(message):
        with lock:
            state["now"] += 1
            state["most"] = max(state["most"], state["now"])
        try:
            time.sleep(delay)
            with lock:
                if state["fail"]:
                    state["fail"] -= 1
                    raise OSError("connection refused")
                state["sent"].append(message["To"])
        finally:
            with lock:
                state["now"] -= 1

    monkeypatch.setattr("prg32_construction_kit.mail_queue._transport", transport)
    return state


def test_the_smtp_server_never_gets_more_messages_than_the_queue_size(app, client, monkeypatch):
    from prg32_construction_kit import mail_queue

    state = _fake_smtp(monkeypatch)
    assert put(client, SMTP_HOST="smtp.school.example", SMTP_MAX_PARALLEL=3).status_code == 200
    with app.test_request_context():
        assert mail_queue.limit() == 3
        for number in range(12):
            mail_queue.enqueue("registration", f"student{number}@school.example", "Hello", "a link")
    status = client.get("/api/admin/mail").get_json()
    assert status["counts"] == {"queued": 12, "sending": 0, "sent": 0, "failed": 0}
    assert mail_queue.dispatch(app, wait=True) == 12
    assert state["most"] == 3 and len(state["sent"]) == 12
    status = client.get("/api/admin/mail?status=sent").get_json()
    assert status["counts"]["sent"] == 12 and len(status["messages"]) == 12
    assert status["messages"][0]["recipient"].startswith("st***@")          # shortened for the admin page
    with app.app_context():
        from prg32_construction_kit.db import db

        assert all(item.body == "" for item in db.session.scalars(db.select(mail_queue.MailMessage)))


def test_the_default_queue_size_is_five_and_the_admin_can_change_it(app, client):
    setting = next(item for item in client.get("/api/admin/settings").get_json()["settings"]
                   if item["key"] == "SMTP_MAX_PARALLEL")
    assert setting["value"] == 5 and setting["group"] == "email" and setting["minimum"] == 1
    assert put(client, SMTP_MAX_PARALLEL=0).status_code == 400
    assert put(client, SMTP_MAX_PARALLEL=8).status_code == 200
    assert client.get("/api/admin/mail").get_json()["limit"] == 8


def test_a_refused_message_is_tried_again_then_failed_and_can_be_retried(app, client, monkeypatch):
    from prg32_construction_kit import mail_queue
    from prg32_construction_kit.db import db

    monkeypatch.setattr(mail_queue, "RETRY_MINUTES", (0, 0))
    state = _fake_smtp(monkeypatch, delay=0, fail=3)
    assert put(client, SMTP_HOST="smtp.school.example").status_code == 200
    with app.test_request_context():
        item = mail_queue.enqueue("new_sign_in", "teacher@school.example", "New sign-in", "text")
        message_id = item.id
    mail_queue.dispatch(app, wait=True)
    failed = client.get("/api/admin/mail?status=failed").get_json()["messages"]
    assert [entry["id"] for entry in failed] == [message_id]
    assert failed[0]["attempts"] == mail_queue.MAX_ATTEMPTS and "refused" in failed[0]["last_error"]
    assert client.post(f"/api/admin/mail/{message_id}/retry").status_code == 200
    assert client.post(f"/api/admin/mail/{message_id}/retry").status_code == 409      # queued now, not failed
    mail_queue.dispatch(app, wait=True)
    assert state["sent"] == ["teacher@school.example"]
    with app.app_context():
        assert db.session.get(mail_queue.MailMessage, message_id).status == "sent"


def test_the_message_text_is_sealed_in_the_database(app, client):
    from prg32_construction_kit import mail_queue
    from prg32_construction_kit.db import db

    with app.test_request_context():
        item = mail_queue.enqueue("registration", "x@school.example", "Finish", "https://kit/register?token=SECRET")
        stored = db.session.get(mail_queue.MailMessage, item.id).body
    from prg32_construction_kit.secrets_at_rest import is_sealed

    assert "SECRET" not in stored and is_sealed(stored)


def test_registration_mail_goes_through_the_queue(tmp_path, monkeypatch):
    from prg32_construction_kit import mail_queue
    from prg32_construction_kit.db import db

    app = make_app(tmp_path, SMTP_HOST="smtp.school.example")
    state = _fake_smtp(monkeypatch, delay=0)
    app.test_client(login=None).post("/auth/register", data={"email": "new@school.example"})
    with app.app_context():
        assert [item.kind for item in db.session.scalars(db.select(mail_queue.MailMessage))] == ["registration"]
    mail_queue.dispatch(app, wait=True)
    assert state["sent"] == ["new@school.example"]


def test_only_admins_see_the_mail_queue(app):
    app.test_client()   # the admin exists
    with app.app_context():
        from prg32_construction_kit.auth import create_user

        create_user("pupil", "pupil@school.example", "pupil-password-1", role="user")
    pupil = app.test_client(login=("pupil", "pupil-password-1"))
    assert pupil.get("/api/admin/mail").status_code == 403
    assert pupil.get("/api/admin/activity").status_code == 403
    assert pupil.get("/api/admin/statistics").status_code == 403
    assert pupil.get("/api/admin/statistics/daily.csv").status_code == 403


# --- the activity log --------------------------------------------------------------------------

def test_every_request_is_logged_without_its_content(app, client):
    client.get("/")
    client.post("/api/projects", json={"title": "Secret title 42"})
    events = client.get("/api/admin/activity").get_json()["events"]
    created = next(event for event in events if event["category"] == "project_create")
    assert created["actor"] == "user" and created["username"] == "admin" and created["status"] in (200, 201)
    assert created["route"] == "/api/projects" and created["method"] == "POST"
    assert any(event["category"] == "page_view" and event["route"] == "/" for event in events)
    assert "Secret title" not in str(events)
    assert all(event["route"] != "/api/admin/activity" for event in events)        # the admin's own polling
    assert client.get("/static/js/app.js").status_code == 200
    assert not any(event["route"].startswith("/static/") for event in client.get("/api/admin/activity").get_json()["events"])


def test_visitors_without_an_account_get_a_daily_pseudonym_and_no_full_address(app, client):
    from prg32_construction_kit import activity
    from prg32_construction_kit.db import db

    visitor = app.test_client(login=None)
    for _ in range(2):
        visitor.get("/auth/login", environ_base={"REMOTE_ADDR": "192.0.2.77"}, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) Firefox/130.0"})
    visitor.get("/auth/login", environ_base={"REMOTE_ADDR": "192.0.2.78"}, headers={"Sec-GPC": "1"})
    guests = client.get("/api/admin/activity?actor=guest").get_json()["events"]
    named = [event for event in guests if event["visitor"]]
    assert len(named) == 2 and len({event["visitor"] for event in named}) == 1
    assert named[0]["visitor"].startswith("guest-") and named[0]["network"] == "192.0.2.0/24"
    assert named[0]["agent"] == "Firefox · Windows" and "192.0.2.77" not in str(guests)
    assert any(event["visitor"] == "" for event in guests)            # Global Privacy Control: no pseudonym
    with app.app_context():
        today = datetime.now(timezone.utc).date().isoformat()
        tomorrow = (datetime.now(timezone.utc).date() + timedelta(days=1)).isoformat()
        with app.test_request_context():
            assert activity.visitor_of("192.0.2.77", "x", today) != activity.visitor_of("192.0.2.77", "x", tomorrow)
            assert db.session.get(activity.ActivitySalt, today) is None              # yesterday's salt is gone
    people = client.get("/api/admin/activity/people").get_json()
    assert people["guests"][0]["visitor"] == named[0]["visitor"]
    assert people["guest_requests_without_pseudonym"] >= 1


@pytest.mark.parametrize("address,network", [("10.1.2.3", "10.1.2.0/24"), ("2001:db8:1:2::5", "2001:db8:1::/48"),
                                              ("::ffff:10.0.0.9", "10.0.0.0/24"), ("not an address", "")])
def test_addresses_are_shortened_to_their_network(address, network):
    from prg32_construction_kit.activity import network_of

    assert network_of(address) == network


def test_reading_one_persons_activity_is_audited_and_the_csv_is_pseudonymised(app, client):
    client.get("/")
    user_id = client.get("/auth/me").get_json()["user"]["id"]
    assert client.get(f"/api/admin/activity?user_id={user_id}").status_code == 200
    audit = client.get("/api/admin/audit?action=activity_view").get_json()["events"]
    assert audit and audit[0]["target_id"] == str(user_id)
    plain = client.get("/api/admin/activity.csv").get_data(as_text=True)
    assert plain.startswith("\ufeffid,created_at,actor")
    rows = list(csv.DictReader(io.StringIO(plain.lstrip("\ufeff"))))
    users = [row for row in rows if row["actor"] == "user"]
    assert users and all(row["username"].startswith("person-") and row["user_id"] == "" for row in users)
    named = client.get("/api/admin/activity.csv?names=1").get_data(as_text=True).lstrip("\ufeff")
    assert any(row["username"] == "admin" for row in csv.DictReader(io.StringIO(named)))
    assert client.get("/api/admin/audit?action=activity_export").get_json()["events"]


def test_the_activity_log_can_be_switched_off(app, client):
    assert put(client, PRG32_KIT_ACTIVITY_LOG=False).status_code == 200
    before = len(client.get("/api/admin/activity").get_json()["events"])
    client.get("/")
    client.get("/account")
    assert len(client.get("/api/admin/activity").get_json()["events"]) == before


def test_erasure_and_export_include_the_activity_log(app, client):
    from prg32_construction_kit import activity, privacy
    from prg32_construction_kit.auth import create_user
    from prg32_construction_kit.db import db

    with app.app_context():
        create_user("leaver", "leaver@school.example", "leaver-password-1", role="user")
    leaver = app.test_client(login=("leaver", "leaver-password-1"))
    leaver.get("/")
    with app.app_context():
        user_id = db.session.scalar(db.select(activity.ActivityEvent.user_id).where(
            activity.ActivityEvent.user_id.is_not(None), activity.ActivityEvent.user_id != 1).limit(1))
        assert privacy.export_personal_data(user_id)["tables"]["activity_events"]
    with app.test_request_context():
        privacy.erase_account(user_id, "admin")
        assert db.session.scalar(db.select(activity.ActivityEvent.id).where(
            activity.ActivityEvent.user_id == user_id)) is None


def test_retention_removes_old_activity_and_mail(app, client):
    from prg32_construction_kit import activity, mail_queue, retention
    from prg32_construction_kit import settings as site_settings
    from prg32_construction_kit.db import db

    client.get("/")
    with app.test_request_context():
        old = (datetime.now(timezone.utc) - timedelta(days=400)).date().isoformat()
        db.session.add(activity.ActivityEvent(created_at=old + "T10:00:00+00:00", day=old, actor="guest", visitor="",
                                              category="page_view", method="GET", route="/", status=200))
        db.session.add(mail_queue.MailMessage(kind="smtp_test", recipient="a@b.example", subject="s", status="sent",
                                              created_at=old + "T10:00:00+00:00", next_attempt_at=old))
        db.session.commit()
        report = retention.apply(site_settings.view(), dry_run=False)
        assert report["expired_activity_events"] == 1 and report["expired_mail"] == 1


# --- statistics ------------------------------------------------------------------------------

def test_statistics_count_accounts_visitors_and_actions(app, client):
    client.get("/")
    client.post("/api/projects", json={"title": "Game"})
    guest = app.test_client(login=None)
    guest.get("/auth/login", environ_base={"REMOTE_ADDR": "198.51.100.4"})
    data = client.get("/api/admin/statistics").get_json()
    assert set(data) >= {"summary", "daily", "hours", "categories", "per_user"}
    assert len(data["daily"]) == 30 and len(data["hours"]) == 24
    summary = data["summary"]
    assert summary["active_users"] == 1 and summary["guest_visitor_days"] == 1 and summary["accounts"] >= 1
    today = data["daily"][-1]
    assert today["active_users"] == 1 and today["guest_visitors"] == 1 and today["requests"] >= 3
    assert any(item["category"] == "project_create" for item in data["categories"])
    person = data["per_user"][0]
    assert person["user"].startswith("person-") and person["user_id"] is None        # pseudonymised by default
    named = client.get("/api/admin/statistics?names=1").get_json()["per_user"][0]
    assert named["user"] == "admin" and named["projects_owned"] >= 1
    assert client.get("/api/admin/audit?action=statistics_names").get_json()["events"]


@pytest.mark.parametrize("table", ["summary", "daily", "hours", "categories", "per_user"])
def test_every_statistics_table_downloads_as_csv(app, client, table):
    client.get("/")
    answer = client.get(f"/api/admin/statistics/{table}.csv?from=2026-01-01&to=2026-01-31")
    assert answer.status_code == 200 and answer.mimetype == "text/csv"
    assert "attachment" in answer.headers["Content-Disposition"]
    header = answer.get_data(as_text=True).lstrip("\ufeff").splitlines()[0]
    assert header.split(",")[0] in ("metric", "day", "hour", "category", "user")
    events = client.get("/api/admin/audit?action=statistics_export").get_json()["events"]
    assert events and events[0]["target_id"] == table


def test_statistics_refuse_bad_dates_and_unknown_tables(client):
    assert client.get("/api/admin/statistics?from=yesterday").status_code == 400
    assert client.get("/api/admin/statistics/secrets.csv").status_code == 404


def test_csv_cells_cannot_become_spreadsheet_formulas(app):
    from prg32_construction_kit.activity import csv_response

    with app.test_request_context():
        text = csv_response([{"a": "=HYPERLINK(1)", "b": 3}], ("a", "b"), "x.csv").get_data(as_text=True)
    assert "'=HYPERLINK" in text


def test_the_admin_pages_open(client):
    for path in ("/admin/activity", "/admin/statistics", "/admin/settings"):
        assert client.get(path).status_code == 200, path
