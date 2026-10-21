"""The admin Settings page (prg32_construction_kit/settings.py, docs/admin_settings.md)."""
from __future__ import annotations

import json

import pytest
from conftest import make_app
from sqlalchemy import select


def put(client, **changes):
    return client.put("/api/admin/settings", json={"settings": changes})


def setting(client, key):
    return next(item for item in client.get("/api/admin/settings").get_json()["settings"] if item["key"] == key)


def test_only_admins_see_or_change_settings(app, client, anon):
    assert anon.get("/api/admin/settings").status_code == 401
    assert client.post("/api/users", json={"username": "kid", "email": "kid@example.org",
                                           "password": "kid-password-123", "role": "user"}).status_code in (200, 201)
    kid = app.test_client(login=("kid", "kid-password-123"))
    assert kid.get("/api/admin/settings").status_code == 403
    assert put(kid, SITE_NAME="Hacked").status_code == 403
    assert kid.get("/admin/settings").status_code == 403
    assert client.get("/admin/settings").status_code == 200
    assert 'href="/admin/settings"' in client.get("/").get_data(as_text=True)
    assert 'href="/admin/settings"' not in kid.get("/").get_data(as_text=True)


def test_a_change_applies_at_once_and_can_go_back_to_the_default(client):
    assert put(client, SITE_NAME="Room 12 Game Lab").status_code == 200
    page = client.get("/").get_data(as_text=True)
    assert "Room 12 Game Lab" in page
    item = setting(client, "SITE_NAME")
    assert item["changed"] and item["value"] == "Room 12 Game Lab" and item["default"] == "PRG32-Construction-Kit"
    assert put(client, SITE_NAME=None).status_code == 200
    assert setting(client, "SITE_NAME")["value"] == "PRG32-Construction-Kit"


@pytest.mark.parametrize("changes", [
    {"PRG32_KIT_QUOTA_MB": -1}, {"PRG32_KIT_QUOTA_MB": "lots"}, {"PRG32_KIT_QUOTA_MB": True},
    {"SKIN": "neon"}, {"ALLOW_REGISTRATION": "yes"}, {"PRG32_PRIVACY_CONTACT": "two\nlines"},
    {"DEFAULT_STORE_URL": "ftp://store"}, {"NOT_A_SETTING": 1}, {"SECRET_KEY": "x"},
    {"SSO_SECRET": "short"}, {"DEFAULT_ROLE": "admin"}, {"WELCOME_TEXT": "x" * 2001},
])
def test_wrong_values_are_refused_and_nothing_is_saved(client, changes):
    response = put(client, **{"SITE_NAME": "Saved?", **changes})
    assert response.status_code == 400, response.get_json()
    assert setting(client, "SITE_NAME")["value"] == "PRG32-Construction-Kit"


def test_the_environment_wins_and_locks_the_setting(client, monkeypatch):
    monkeypatch.setenv("PRG32_KIT_SITE_NAME", "From the server")
    item = setting(client, "SITE_NAME")
    assert item["locked"] is True
    response = put(client, SITE_NAME="From the page")
    assert response.status_code == 400 and "PRG32_KIT_SITE_NAME" in response.get_json()["error"]


def test_a_locked_setting_ignores_an_older_saved_value(app, client, monkeypatch):
    assert put(client, PRG32_KIT_QUOTA_PROJECTS=3).status_code == 200
    monkeypatch.setenv("PRG32_KIT_QUOTA_PROJECTS", "7")
    app.config["PRG32_KIT_QUOTA_PROJECTS"] = 7          # what Config read from that variable
    with app.app_context():
        from prg32_construction_kit import settings

        assert settings.get("PRG32_KIT_QUOTA_PROJECTS") == 7


def test_secrets_are_sealed_and_never_sent_back(app, client):
    assert put(client, SMTP_PASSWORD="mail-password-42").status_code == 200
    answer = client.get("/api/admin/settings").get_data(as_text=True)
    assert "mail-password-42" not in answer
    assert setting(client, "SMTP_PASSWORD") == {**setting(client, "SMTP_PASSWORD"), "set": True}
    assert "value" not in setting(client, "SMTP_PASSWORD")
    with app.app_context():
        from prg32_construction_kit import settings
        from prg32_construction_kit.db import db

        row = db.session.get(settings.SiteSetting, "SMTP_PASSWORD")
        assert "mail-password-42" not in row.value and json.loads(row.value).startswith("enc1:")
        assert settings.get("SMTP_PASSWORD") == "mail-password-42"


def test_the_audit_log_names_the_settings_but_not_their_values(app, client):
    assert put(client, PRG32_PRIVACY_CONTACT="dpo@school.example", SMTP_PASSWORD="mail-password-42").status_code == 200
    with app.app_context():
        from prg32_construction_kit.db import db
        from prg32_construction_kit.security import AuditEvent

        event = db.session.scalars(select(AuditEvent).where(AuditEvent.action == "settings_update")).one()
        assert "PRG32_PRIVACY_CONTACT" in event.metadata_json and "SMTP_PASSWORD" in event.metadata_json
        assert "dpo@school.example" not in event.metadata_json and "mail-password-42" not in event.metadata_json


def test_settings_drive_the_kit(app, client, anon):
    assert put(client, ALLOW_REGISTRATION=False).status_code == 200
    assert anon.post("/auth/register", data={"email": "new@example.org"}).status_code in (400, 403)
    assert put(client, PRG32_PRIVACY_CONTROLLER="Scuola Media Rossi").status_code == 200
    assert "Scuola Media Rossi" in anon.get("/privacy").get_data(as_text=True)
    assert put(client, PRG32_KIT_QUOTA_PROJECTS=1).status_code == 200
    with app.test_request_context():
        from prg32_construction_kit import settings, storage_policy

        assert storage_policy.usage(1, settings.view())["quota_projects"] == 1
    assert put(client, COLOR_SCHEME="dark", SKIN="ocean").status_code == 200
    page = client.get("/").get_data(as_text=True)
    assert 'data-bs-theme="dark"' in page and "css/themes/ocean.css" in page
    assert put(client, WELCOME_TEXT="Make a game about your town!").status_code == 200
    assert "Make a game about your town!" in client.get("/").get_data(as_text=True)


def test_every_skin_has_a_stylesheet(anon):
    from prg32_construction_kit.settings import SKINS

    for skin in SKINS:
        assert anon.get(f"/static/css/themes/{skin}.css").status_code == 200


def test_maintenance_lets_admins_in_and_tells_everybody_else(app, client):
    assert client.post("/api/users", json={"username": "kid", "email": "kid@example.org",
                                           "password": "kid-password-123", "role": "user"}).status_code in (200, 201)
    kid = app.test_client(login=("kid", "kid-password-123"))
    assert put(client, MAINTENANCE_MODE=True, MAINTENANCE_MESSAGE="Back at 10:30").status_code == 200
    page = kid.get("/")
    assert page.status_code == 503 and "Back at 10:30" in page.get_data(as_text=True)
    assert kid.get("/api/projects").get_json()["code"] == "maintenance"
    for open_path in ("/privacy", "/auth/login", "/documentation"):
        assert kid.get(open_path).status_code in (200, 302), open_path
    assert client.get("/").status_code == 200 and "Maintenance mode is on" in client.get("/").get_data(as_text=True)
    assert put(client, MAINTENANCE_MODE=False).status_code == 200
    assert kid.get("/").status_code == 200


def test_a_test_mail_goes_to_the_admin(app, client):
    assert client.post("/api/admin/settings/smtp_test", json={}).status_code == 400     # no SMTP server yet
    assert put(client, SMTP_HOST="smtp.school.example").status_code == 200
    answer = client.post("/api/admin/settings/smtp_test", json={})
    assert answer.status_code == 200
    assert app.extensions["prg32_last_smtp_test"]["email"] == answer.get_json()["sent_to"]


def test_cloud_providers_can_be_switched_off(app, client):
    app.config["CLOUD_GOOGLE_CLIENT_ID"] = "client-id"
    with app.test_request_context():
        from prg32_construction_kit import cloud_storage

        assert "google" in cloud_storage.configured()
    assert put(client, CLOUD_GOOGLE_ENABLED=False).status_code == 200
    with app.test_request_context():
        assert "google" not in cloud_storage.configured()


def test_another_process_sees_a_change(tmp_path):
    first = make_app(tmp_path)
    second = make_app(tmp_path)                 # a second worker on the same database
    with second.app_context():
        from prg32_construction_kit import settings

        assert settings.get("SITE_NAME") == "PRG32-Construction-Kit"
    assert put(first.test_client(), SITE_NAME="Shared Lab").status_code == 200
    with second.app_context():
        assert settings.get("SITE_NAME") == "Shared Lab"


def test_api_tokens_need_the_admin_scope(app, client):
    token = client.post("/auth/tokens", json={"name": "read", "scopes": ["read"]}).get_json()
    secret = token.get("token") or token.get("secret")
    assert secret
    reader = app.test_client(login=None)
    answer = reader.get("/api/admin/settings", headers={"Authorization": f"Bearer {secret}"})
    assert answer.status_code == 403
