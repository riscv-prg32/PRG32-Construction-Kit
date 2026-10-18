"""The first administrator: no well-known password, ever, and never re-created."""

from __future__ import annotations

import importlib
import json
import logging
import stat

import pytest
from conftest import make_app

from prg32_construction_kit.auth import BOOTSTRAP_PASSWORD_FILE, BootstrapError, User
from prg32_construction_kit.config import Config

kit_db = importlib.import_module("prg32_construction_kit.db")
STRONG = "a-long-classroom-admin-pass"


def admins(app) -> list[str]:
    with app.app_context():
        return [user.username for user in kit_db.db.session.scalars(kit_db.select(User).where(User.role == "admin"))]


def audit_rows(app) -> list[dict]:
    with app.app_context():
        rows = kit_db.db.session.execute(kit_db.text("SELECT action, outcome, metadata FROM audit_events")).all()
    return [{"action": a, "outcome": o, "metadata": json.loads(m)} for a, o, m in rows]


def test_there_is_no_built_in_default_password():
    import os

    if not os.environ.get("PRG32_ADMIN_PASSWORD"):
        assert Config.ADMIN_PASSWORD is None


def test_fresh_production_start_makes_a_random_password_file(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    app = make_app(tmp_path, ADMIN_PASSWORD=None, KIT_ENV="production")
    secret_file = tmp_path / BOOTSTRAP_PASSWORD_FILE
    password = secret_file.read_text().strip()
    assert len(password) >= 20 and password != "password"
    assert stat.S_IMODE(secret_file.stat().st_mode) == 0o600
    assert admins(app) == ["admin"]
    assert password not in caplog.text and BOOTSTRAP_PASSWORD_FILE in caplog.text
    client = app.test_client(login=("admin", password))
    assert client.get("/auth/me").get_json()["user"]["role"] == "admin"
    assert {"action": "admin_bootstrap", "outcome": "success",
            "metadata": {"environment": "production", "source": "generated", "weak": False}} in audit_rows(app)


def test_changing_the_admin_password_deletes_the_file(tmp_path):
    app = make_app(tmp_path, ADMIN_PASSWORD=None, KIT_ENV="production")
    password = (tmp_path / BOOTSTRAP_PASSWORD_FILE).read_text().strip()
    client = app.test_client(login=("admin", password))
    response = client.post("/auth/password", json={"current_password": password, "new_password": STRONG})
    assert response.status_code == 200
    assert not (tmp_path / BOOTSTRAP_PASSWORD_FILE).exists()


@pytest.mark.parametrize("weak", ["password", "change-me-before-class", "short", "PASSWORD"])
def test_production_refuses_weak_passwords_and_creates_no_admin(tmp_path, weak):
    with pytest.raises(BootstrapError, match="production server") as error:
        make_app(tmp_path, ADMIN_PASSWORD=weak, KIT_ENV="production")
    assert f"'{weak}'" not in str(error.value) and f"={weak}" not in str(error.value)  # never echoed
    assert not (tmp_path / BOOTSTRAP_PASSWORD_FILE).exists()
    app = make_app(tmp_path, ADMIN_PASSWORD=STRONG, KIT_ENV="production")  # fixing the setting works
    assert admins(app) == ["admin"]


def test_explicit_strong_password_is_used_and_no_file_is_written(tmp_path):
    app = make_app(tmp_path, ADMIN_PASSWORD=STRONG, KIT_ENV="production")
    assert not (tmp_path / BOOTSTRAP_PASSWORD_FILE).exists()
    assert app.test_client(login=("admin", STRONG)).get("/auth/me").get_json()["user"]["role"] == "admin"
    assert audit_rows(app)[0]["metadata"]["source"] == "environment"


def test_development_allows_a_weak_password_with_a_warning(tmp_path, caplog):
    caplog.set_level(logging.WARNING)
    app = make_app(tmp_path, ADMIN_PASSWORD="password", KIT_ENV="development")
    assert "INSECURE" in caplog.text and "'password'" not in caplog.text
    assert app.test_client(login=("admin", "password")).get("/auth/me").get_json()["user"]["role"] == "admin"
    assert audit_rows(app)[0]["metadata"]["weak"] is True


def test_existing_installation_keeps_its_admin(tmp_path):
    make_app(tmp_path, ADMIN_PASSWORD=STRONG, KIT_ENV="production")
    # Restart with another (even unset) setting: the existing admin and password stay.
    app = make_app(tmp_path, ADMIN_PASSWORD=None, KIT_ENV="production")
    assert admins(app) == ["admin"]
    assert not (tmp_path / BOOTSTRAP_PASSWORD_FILE).exists()
    assert app.test_client(login=("admin", STRONG)).get("/auth/me").status_code == 200


def test_renamed_or_deleted_admin_is_never_recreated(tmp_path):
    app = make_app(tmp_path, ADMIN_PASSWORD=STRONG, KIT_ENV="production")
    client = app.test_client(login=("admin", STRONG))
    admin_id = client.get("/auth/me").get_json()["user"]["id"]
    client.put(f"/api/users/{admin_id}", json={"username": "teacher"})
    teacher = client.post("/api/users", json={"username": "second", "email": "second@school.test",
                                              "password": STRONG, "role": "admin"}).get_json()
    second = app.test_client(login=("second", STRONG))
    assert second.delete(f"/api/users/{admin_id}").status_code == 200
    again = make_app(tmp_path, ADMIN_PASSWORD=None, KIT_ENV="production")
    assert admins(again) == ["second"] and teacher["username"] == "second"
    assert not (tmp_path / BOOTSTRAP_PASSWORD_FILE).exists()


def test_the_password_file_is_never_served_as_an_artifact(tmp_path):
    app = make_app(tmp_path, ADMIN_PASSWORD=None, KIT_ENV="production", BUILD_ROOT=tmp_path, ARTIFACT_ROOT=tmp_path)
    password = (tmp_path / BOOTSTRAP_PASSWORD_FILE).read_text().strip()
    client = app.test_client(login=("admin", password))
    artifact = client.post("/api/artifacts", json={"name": "x", "path": str(tmp_path / BOOTSTRAP_PASSWORD_FILE)}).get_json()
    response = client.get(f"/api/artifacts/{artifact['id']}/download")
    assert response.status_code == 404 and password.encode() not in response.data


def test_docker_and_examples_have_no_well_known_password():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    compose = (root / "docker-compose.yml").read_text()
    assert "PRG32_ADMIN_PASSWORD:-password" not in compose
    assert "PRG32_KIT_ENV=production" in (root / "Dockerfile").read_text()
    env_example = (root / "examples" / "deploy" / "classroom.env").read_text()
    assert "\nPRG32_ADMIN_PASSWORD=change-me-before-class" not in env_example
