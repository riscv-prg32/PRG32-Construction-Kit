"""Sign-in throttling and the administrator audit log."""

from __future__ import annotations

import importlib
import json

import pytest
from conftest import ADMIN_PASSWORD, make_app

from prg32_construction_kit import security
from prg32_construction_kit.auth import RegistrationToken, create_user

kit_db = importlib.import_module("prg32_construction_kit.db")
PASSWORD = "student-password-1"


@pytest.fixture()
def clock(monkeypatch):
    """A controllable clock for the throttle windows."""
    now = {"t": 1_000_000}
    monkeypatch.setattr(security, "_now", lambda: now["t"])
    return now


def login(browser, username, password, address="10.0.0.1", **headers):
    return browser.post("/auth/login", data={"username": username, "password": password},
                        environ_base={"REMOTE_ADDR": address}, headers=headers)


def everything_stored(app) -> str:
    """All audit rows as one text, to search for secrets."""
    with app.app_context():
        rows = kit_db.db.session.execute(kit_db.text("SELECT * FROM audit_events")).all()
    return json.dumps([list(map(str, row)) for row in rows])


def events(client, **params):
    response = client.get("/api/admin/audit", query_string=params)
    assert response.status_code == 200
    return response.get_json()["events"]


# --- sign-in throttling -------------------------------------------------------------

def test_five_wrong_passwords_lock_that_name_from_that_address(app, anon, clock):
    for _ in range(5):
        assert login(anon, "admin", "wrong").status_code == 401
    locked = login(anon, "admin", ADMIN_PASSWORD)  # even the right password waits
    assert locked.status_code == 429
    assert int(locked.headers["Retry-After"]) == 15 * 60
    assert b"Too many attempts" in locked.data
    # A classmate behind the same address is not affected, nor is the same name elsewhere.
    with app.app_context():
        create_user("ada", "ada@school.test", PASSWORD)
    assert login(anon, "ada", PASSWORD).status_code == 302
    assert login(app.test_client(login=None), "admin", ADMIN_PASSWORD, address="10.0.0.2").status_code == 302


def test_the_lock_ends_when_the_window_ends(anon, clock):
    for _ in range(5):
        login(anon, "admin", "wrong")
    assert login(anon, "admin", ADMIN_PASSWORD).status_code == 429
    clock["t"] += 15 * 60
    assert login(anon, "admin", ADMIN_PASSWORD).status_code == 302


def test_a_successful_sign_in_resets_the_count(app, clock):
    browser = app.test_client(login=None)
    for _ in range(4):
        login(browser, "admin", "wrong")
    assert login(browser, "admin", ADMIN_PASSWORD).status_code == 302
    browser.post("/auth/logout", headers={"X-PRG32-Kit": "1"})
    for _ in range(4):
        assert login(browser, "admin", "wrong").status_code == 401
    assert login(browser, "admin", ADMIN_PASSWORD).status_code == 302


def test_unknown_and_known_names_are_treated_the_same(anon, clock):
    answers = []
    for name in ("admin", "nobody-here"):
        for _ in range(5):
            answers.append(login(anon, name, "wrong").status_code)
        locked = login(anon, name, "wrong", Accept="application/json")
        answers.append(locked.status_code)
    assert answers == [401] * 5 + [429] + [401] * 5 + [429]


def test_many_names_from_one_address_hit_the_address_limit(tmp_path, clock):
    app = make_app(tmp_path, THROTTLE_LIMITS={"login_address": (3, 900)})
    browser = app.test_client(login=None)
    for index in range(3):
        login(browser, f"guess{index}", "wrong")
    assert login(browser, "admin", ADMIN_PASSWORD).status_code == 429


def test_forwarded_addresses_are_ignored_unless_a_proxy_is_configured(tmp_path, clock):
    app = make_app(tmp_path)
    browser = app.test_client(login=None)
    for index in range(5):
        login(browser, "admin", "wrong", **{"X-Forwarded-For": f"192.0.2.{index}"})
    assert login(browser, "admin", ADMIN_PASSWORD, **{"X-Forwarded-For": "192.0.2.99"}).status_code == 429

    behind_proxy = make_app(tmp_path / "proxy", PROXY_COUNT=1)
    browser = behind_proxy.test_client(login=None)
    for _ in range(5):
        login(browser, "admin", "wrong", **{"X-Forwarded-For": "198.51.100.7"})
    assert login(browser, "admin", ADMIN_PASSWORD, **{"X-Forwarded-For": "198.51.100.7"}).status_code == 429
    # Another student behind the same proxy is a different address.
    assert login(browser, "admin", ADMIN_PASSWORD, **{"X-Forwarded-For": "198.51.100.8"}).status_code == 302
    # Only the entry the trusted proxy added counts: a forged first entry does not help.
    forged = login(browser, "admin", ADMIN_PASSWORD, **{"X-Forwarded-For": "1.2.3.4, 198.51.100.7"})
    assert forged.status_code == 429


def test_registration_requests_are_limited_per_email(anon, clock):
    for _ in range(3):
        assert anon.post("/auth/register", data={"email": "kid@school.test"}).status_code == 200
    response = anon.post("/auth/register", data={"email": "kid@school.test"})
    assert response.status_code == 429 and "Retry-After" in response.headers
    assert anon.post("/auth/register", data={"email": "other@school.test"}).status_code == 200


def test_bad_registration_links_are_limited_per_address(tmp_path, clock):
    app = make_app(tmp_path, THROTTLE_LIMITS={"register_complete": (2, 3600)})
    browser = app.test_client(login=None)
    for _ in range(2):
        assert browser.post("/auth/register/complete", data={"token": "guess", "password": PASSWORD}).status_code == 400
    assert browser.post("/auth/register/complete", data={"token": "guess", "password": PASSWORD}).status_code == 429
    # A real link still works from another address.
    browser.post("/auth/register", data={"email": "new@school.test"})
    with app.app_context():
        assert kit_db.db.session.scalar(kit_db.select(RegistrationToken)) is not None


def test_api_tokens_are_limited_per_user(tmp_path, clock):
    app = make_app(tmp_path, THROTTLE_LIMITS={"token_create": (2, 3600)})
    admin = app.test_client()
    assert admin.post("/auth/tokens", json={"label": "a"}).status_code == 201
    assert admin.post("/auth/tokens", json={"label": "b"}).status_code == 201
    assert admin.post("/auth/tokens", json={"label": "c"}).status_code == 429
    with app.app_context():
        create_user("ada", "ada@school.test", PASSWORD)
    assert app.test_client(login=("ada", PASSWORD)).post("/auth/tokens", json={"label": "x"}).status_code == 201


def test_a_teacher_can_unlock_everybody(app, client, anon, clock):
    for _ in range(5):
        login(anon, "admin", "wrong")
    with app.app_context():
        create_user("ada", "ada@school.test", PASSWORD)
    student = app.test_client(login=("ada", PASSWORD))
    assert student.delete("/api/admin/throttles").status_code == 403
    assert client.delete("/api/admin/throttles").get_json()["cleared"] >= 1
    assert login(anon, "admin", ADMIN_PASSWORD).status_code == 302
    assert events(client, action="throttles_clear")[0]["outcome"] == "success"


def test_throttle_table_holds_no_names_or_addresses(app, anon, clock):
    login(anon, "secret-name@school.test", "wrong", address="203.0.113.5")
    with app.app_context():
        keys = [row[0] for row in kit_db.db.session.execute(kit_db.text("SELECT key FROM auth_throttle"))]
    assert keys and not any("secret-name" in key or "203.0.113.5" in key for key in keys)


# --- audit log ---------------------------------------------------------------------

def test_user_management_is_audited_without_passwords(app, client):
    user = client.post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD,
                                           "groups": ["class-3b"]}).get_json()
    client.put(f"/api/users/{user['id']}", json={"role": "admin"})
    client.put(f"/api/users/{user['id']}", json={"groups": ["class-4a"]})
    client.put(f"/api/users/{user['id']}", json={"password": "a-new-password-22"})
    client.delete(f"/api/users/{user['id']}")
    log = {event["action"]: event for event in events(client)}
    assert log["user_create"]["metadata"] == {"groups": ["class-3b"], "role": "user", "username": "ada"}
    assert log["user_role_change"]["metadata"]["role_before"] == "user"
    assert log["user_role_change"]["metadata"]["role_after"] == "admin"
    assert log["user_groups_change"]["metadata"]["groups_after"] == ["class-4a"]
    assert log["user_update"]["metadata"] == {"credentials_changed": True}
    assert log["user_delete"]["target_id"] == str(user["id"])
    assert log["admin_bootstrap"]["actor_name"] == "system"  # made at the first start, by nobody
    assert all(event["actor_name"] == "admin" and event["created_at"]
               for action, event in log.items() if action.startswith("user_"))
    stored = everything_stored(app)
    assert PASSWORD not in stored and "a-new-password-22" not in stored


def test_api_tokens_are_audited_but_never_stored(app, client):
    created = client.post("/auth/tokens", json={"label": "board"}).get_json()
    client.delete(f"/auth/tokens/{created['id']}")
    client.delete("/auth/tokens/999999")
    actions = [(event["action"], event["outcome"]) for event in events(client)]
    assert ("api_token_create", "success") in actions
    assert ("api_token_revoke", "success") in actions and ("api_token_revoke", "not_found") in actions
    assert created["token"] not in everything_stored(app)


def test_publish_attempts_and_results_are_audited(app, client, monkeypatch):
    from conftest import make_store_bundle, review_and_publish

    bundle = make_store_bundle(client, monkeypatch, "Pub")
    app.config["STORE_ALLOWED_ORIGINS"] = ["https://store.school.test"]
    profile = client.post("/api/publish_profiles", json={"name": "Store", "store_url": "https://store.school.test",
                                                         "bearer_token": "prg32_secret_value"}).get_json()
    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle",
                        lambda url, token, path: {"ok": True, "status_code": 201, "response": {}})
    review_and_publish(client, profile["id"], bundle["id"])
    client.post("/api/publish", json={"profile_id": "nope", "bundle_artifact_id": bundle["id"]})
    published = events(client, action="publish")
    assert [(event["outcome"], event["metadata"]["stage"]) for event in published] == [
        ("refused", "refused"), ("success", "submitted"), ("success", "upload")]
    assert published[1]["metadata"]["store_host"] == "store.school.test"
    assert published[1]["metadata"]["status_code"] == 201
    assert "prg32_secret_value" not in everything_stored(app)


def test_the_audit_log_is_for_admins_only(app, client, anon):
    with app.app_context():
        create_user("ada", "ada@school.test", PASSWORD)
    student = app.test_client(login=("ada", PASSWORD))
    assert student.get("/api/admin/audit").status_code == 403
    assert anon.get("/api/admin/audit").status_code == 401
    assert client.get("/api/admin/audit?limit=abc").status_code == 400
    assert len(events(client, limit=1)) == 1


def test_safe_metadata_drops_secrets_and_trims():
    cleaned = security.safe_metadata({"password": "x", "api_token": "y", "Session_Cookie": "z", "ticket": "t",
                                      "label": "a" * 500, "groups": list(range(100)), "n": 3})
    assert set(cleaned) == {"label", "groups", "n"}
    assert len(cleaned["label"]) == 200 and len(cleaned["groups"]) == 50
