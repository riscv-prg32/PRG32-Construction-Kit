"""The kit and a real PRG32 Cartridge Store sharing users.

Runs only when the CartridgeStore repository sits next to this one (or
PRG32_CARTRIDGE_STORE_SOURCE points at it) and its requirements are installed. Until the
shared-identity contract is merged upstream, the Store next to the kit is used through a
patched clean clone (tools/pinned_store.py, docs/upstream/README.md §6.1).
"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from conftest import make_app
from prg32_construction_kit import sso_protocol

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
# The Store with the shared-identity contract: a patched clean clone, never the Store itself (tools/pinned_store.py).
from pinned_store import store_source  # noqa: E402
STORE_SOURCE = store_source()
SECRET = "a-shared-classroom-secret-that-is-long-enough"
PASSWORD = "student-password-1"

if not (STORE_SOURCE / "cartridge_store").is_dir():
    pytest.skip("CartridgeStore repository not found", allow_module_level=True)
sys.path.append(str(STORE_SOURCE))
try:
    from cartridge_store.app import create_app as create_store
except ImportError as exc:
    pytest.skip(f"CartridgeStore requirements are not installed: {exc}", allow_module_level=True)


def kit_emails(kit) -> set[str]:
    from prg32_construction_kit.auth import User

    with kit.app_context():
        return {user.email for user in User.query.all()}


def _route_to(app):
    client = app.test_client()

    def transport(method, url, headers, body):
        response = client.open(urlsplit(url).path, method=method, headers=headers, data=body)
        return response.status_code, response.data

    return transport


@pytest.fixture()
def kit_and_store(tmp_path):
    store = create_store({"TESTING": True, "DATA_DIR": str(tmp_path / "store"),
                              "SSO_SECRET": SECRET, "SSO_PEER_URL": "http://kit.test"})
    kit = make_app(tmp_path / "kit", SSO_SECRET=SECRET, SSO_PEER_URL="http://store.test")
    kit.config["SSO_TRANSPORT"] = _route_to(store)
    store.config["SSO_TRANSPORT"] = _route_to(kit)
    return kit, store


def store_admin(store):
    client = store.test_client()
    assert client.post("/auth/login", data={"username": "admin", "password": "password"}).status_code == 302
    return client


def test_protocol_file_is_the_same_in_both_repositories(kit_and_store):
    store_copy = STORE_SOURCE / "cartridge_store" / "sso_protocol.py"
    assert store_copy.read_text() == Path(sso_protocol.__file__).read_text()


def test_kit_user_can_sign_in_to_the_store(kit_and_store):
    kit, store = kit_and_store
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    browser = store.test_client()
    assert browser.post("/auth/login", data={"username": "ada@school.test", "password": PASSWORD}).status_code == 302
    assert browser.get("/api/me").get_json()["user"]["username"] == "ada"


def test_the_username_is_shared_and_the_store_handle_stays_public_only(kit_and_store):
    """Identity contract (docs/accounts_and_sso.md): the username is shared; the Store's public
    handle is a separate, pseudonymous display name that never replaces it on either side."""
    kit, store = kit_and_store
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    me = store.test_client()
    me.post("/auth/login", data={"username": "ada", "password": PASSWORD})
    user = me.get("/api/me").get_json()["user"]
    assert user["username"] == "ada"
    if "public_handle" in user:            # Stores from 4a3138b on (with docs/upstream §6's patch)
        assert user["public_handle"] not in ("ada", "ada@school.test")
    ada = kit.test_client(login=("ada", PASSWORD))
    assert ada.get("/auth/me").get_json()["user"]["username"] == "ada"


def test_a_store_only_account_with_the_same_username_is_never_joined(kit_and_store):
    """Collision: the Store already has another "ada". Accounts are matched by email, so the kit's
    ada gets her own Store account (named by her email there) and the other one is untouched."""
    kit, store = kit_and_store
    store.test_client().get("/")
    with store.app_context():
        from cartridge_store.database import get_db
        from werkzeug.security import generate_password_hash

        get_db().execute("INSERT INTO users(username, email, password_hash, role) VALUES ('ada', 'ada@elsewhere.test', ?, 'user')",
                         (generate_password_hash("another-password-1"),))
        get_db().commit()
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    kit_ada = store.test_client()
    assert kit_ada.post("/auth/login", data={"username": "ada@school.test", "password": PASSWORD}).status_code == 302
    mine = kit_ada.get("/api/me").get_json()["user"]
    assert mine["email"] == "ada@school.test" and mine["username"] == "ada@school.test"
    other = store.test_client()
    assert other.post("/auth/login", data={"username": "ada", "password": PASSWORD}).status_code == 401
    assert other.post("/auth/login", data={"username": "ada", "password": "another-password-1"}).status_code == 302
    assert other.get("/api/me").get_json()["user"]["email"] == "ada@elsewhere.test"
    ada = kit.test_client(login=("ada", PASSWORD))
    assert ada.get("/auth/me").get_json()["user"]["email"] == "ada@school.test"


def test_store_registration_reaches_the_kit(kit_and_store):
    kit, store = kit_and_store
    browser = store.test_client()
    browser.post("/auth/register", data={"email": "bob@school.test"})
    token = store.extensions["prg32_last_registration"]["token"]
    browser.post("/auth/register/complete", data={"token": token, "password": PASSWORD, "password_confirm": PASSWORD})
    kit_browser = kit.test_client(login=None)
    assert kit_browser.post("/auth/login", data={"username": "bob@school.test", "password": PASSWORD}).status_code == 302


def test_store_admin_changes_and_deletes_reach_the_kit(kit_and_store):
    kit, store = kit_and_store
    admin = store_admin(store)
    admin.post("/admin/users", data={"username": "cy", "email": "cy@school.test", "password": PASSWORD, "role": "user",
                                     "groups": ["editors"]})
    kit_users = {user["email"]: user for user in kit.test_client().get("/api/users").get_json()["users"]}
    assert kit_users["cy@school.test"]["groups"] == ["editors"]
    with store.app_context():
        from cartridge_store.database import get_db

        user_id = get_db().execute("SELECT id FROM users WHERE email = 'cy@school.test'").fetchone()["id"]
    admin.post(f"/admin/users/{user_id}/role", data={"role": "publisher"})
    kit_users = {user["email"]: user for user in kit.test_client().get("/api/users").get_json()["users"]}
    assert kit_users["cy@school.test"]["role"] == "publisher"
    admin.post(f"/admin/users/{user_id}/delete")
    kit_users = {user["email"]: user for user in kit.test_client().get("/api/users").get_json()["users"]}
    assert "cy@school.test" not in kit_users


def test_single_sign_on_both_ways(kit_and_store):
    kit, store = kit_and_store
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    kit_browser = kit.test_client(login=("ada", PASSWORD))
    page = kit_browser.get("/auth/sso/peer?next=/publish").get_data(as_text=True)
    ticket = page.split('name="ticket" value="', 1)[1].split('"', 1)[0]
    store_browser = store.test_client()
    response = store_browser.post("/auth/sso/accept", data={"ticket": ticket, "next": "/publish"})
    assert response.status_code == 302 and response.headers["Location"] == "/publish"
    assert store_browser.get("/api/me").get_json()["user"]["email"] == "ada@school.test"

    page = store_browser.get("/auth/sso/peer").get_data(as_text=True)
    ticket = page.split('name="ticket" value="', 1)[1].split('"', 1)[0]
    fresh_kit_browser = kit.test_client(login=None)
    assert fresh_kit_browser.post("/auth/sso/accept", data={"ticket": ticket}).status_code == 302
    assert fresh_kit_browser.get("/auth/me").get_json()["user"]["email"] == "ada@school.test"


def test_kit_publishes_to_the_store_as_the_student(kit_and_store, monkeypatch):
    kit, store = kit_and_store
    kit.config["STORE_TRUSTED_LOCAL"] = True  # the peer here is plain http, as on a classroom LAN (ADR-0008)
    # Publishing needs the publisher role (ADR-0009); the role is synced with the Store too.
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD,
                                               "role": "publisher"})
    ada = kit.test_client(login=("ada", PASSWORD))
    seen = {}

    def publish_through_store(store_url, token, path):
        response = store.test_client().get("/api/me", headers={"Authorization": f"Bearer {token}"})
        seen["user"] = response.get_json()["user"]
        again = store.test_client().get("/api/me", headers={"Authorization": f"Bearer {token}"})
        seen["reused"] = again.get_json()["user"]["authenticated"]
        return {"ok": True}

    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", publish_through_store)
    profile = ada.post("/api/publish_profiles", json={"name": "School", "store_url": "http://store.test"}).get_json()
    from conftest import make_store_bundle, review_and_publish

    artifact = make_store_bundle(ada, monkeypatch)
    review_and_publish(ada, profile["id"], artifact["id"])
    assert seen["user"]["email"] == "ada@school.test" and seen["user"]["authenticated"] is True
    assert seen["reused"] is False  # an API ticket works only once


def test_sync_now_from_the_store_admin_page(tmp_path):
    store = create_store({"TESTING": True, "DATA_DIR": str(tmp_path / "store")})
    kit = make_app(tmp_path / "kit")
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    store_admin(store).post("/admin/users", data={"username": "bob", "email": "bob@school.test", "password": PASSWORD})
    store.config.update(SSO_SECRET=SECRET, SSO_PEER_URL="http://kit.test", SSO_TRANSPORT=_route_to(kit))
    kit.config.update(SSO_SECRET=SECRET, SSO_PEER_URL="http://store.test", SSO_TRANSPORT=_route_to(store))
    assert store_admin(store).post("/admin/sso/sync").status_code == 302
    # Both sides started with admin@localhost; they are now one account with the
    # newest password, so look at the kit's database instead of signing in.
    assert {"ada@school.test", "bob@school.test", "admin@localhost"} <= kit_emails(kit)
    assert store.test_client().post("/auth/login", data={"username": "ada@school.test", "password": PASSWORD}).status_code == 302
