"""Single sign-on and user sync.

The protocol is the same on both sides, so two Construction Kits linked to
each other behave like a kit linked to a Cartridge Store. The real kit-to-store
pairing is tested in test_sso_with_cartridge_store.py when that repository is
next to this one.
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

import pytest

from conftest import make_app
from prg32_construction_kit import sso_protocol as protocol

SECRET = "a-shared-classroom-secret-that-is-long-enough"
PASSWORD = "student-password-1"


def link(app_a, app_b, *, online=lambda: True):
    """Route app_a's sync requests to app_b, like a network would."""
    peer = app_b.test_client(login=None)

    def transport(method, url, headers, body):
        if not online():
            raise ConnectionError("peer is offline")
        response = peer.open(urlsplit(url).path, method=method, headers=headers, data=body)
        return response.status_code, response.data

    app_a.config["SSO_TRANSPORT"] = transport


@pytest.fixture()
def pair(tmp_path):
    kit = make_app(tmp_path / "kit", SSO_SECRET=SECRET, SSO_PEER_URL="http://other.test")
    other = make_app(tmp_path / "other", SSO_SECRET=SECRET, SSO_PEER_URL="http://kit.test")
    link(kit, other)
    link(other, kit)
    return kit, other


def users(app):
    return {user["email"]: user for user in app.test_client().get("/api/users").get_json()["users"]}


def test_signed_requests_and_tickets():
    body = b'{"users":[]}'
    headers = protocol.sign_request(SECRET, "POST", "/api/sso/users", body)
    assert protocol.verify_request(SECRET, "POST", "/api/sso/users", body, headers)
    assert not protocol.verify_request(SECRET, "POST", "/api/sso/users", b'{"users":[1]}', headers)
    assert not protocol.verify_request("x" * 40, "POST", "/api/sso/users", body, headers)
    old = protocol.sign_request(SECRET, "POST", "/api/sso/users", body, timestamp=int(time.time()) - 3600)
    assert not protocol.verify_request(SECRET, "POST", "/api/sso/users", body, old)

    ticket = protocol.make_ticket(SECRET, email="Ada@School.test", audience="cartridge-store", purpose="login", ttl=60)
    claims = protocol.read_ticket(SECRET, ticket, audience="cartridge-store", purpose="login")
    assert claims and claims["email"] == "ada@school.test"
    assert protocol.read_ticket(SECRET, ticket, audience="construction-kit", purpose="login") is None
    assert protocol.read_ticket(SECRET, ticket, audience="cartridge-store", purpose="api") is None
    assert protocol.read_ticket(SECRET, ticket[:-2] + "xx", audience="cartridge-store", purpose="login") is None
    assert protocol.read_ticket(SECRET, ticket, audience="cartridge-store", purpose="login", now=time.time() + 120) is None


def test_short_secrets_keep_sso_off(tmp_path):
    app = make_app(tmp_path, SSO_SECRET="too-short", SSO_PEER_URL="http://store.test")
    assert app.test_client().get("/auth/me").get_json()["sso"]["enabled"] is False


def test_unsigned_sync_requests_are_refused(pair):
    kit, _ = pair
    anon = kit.test_client(login=None)
    evil = {"users": [{"email": "evil@x.test", "role": "admin", "password_hash": "x"}]}
    assert anon.post("/api/sso/users", json=evil).status_code == 403
    assert anon.get("/api/sso/users").status_code == 403
    assert "evil@x.test" not in users(kit)


def test_new_changed_and_deleted_users_reach_the_other_side(pair):
    kit, other = pair
    created = kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test",
                                                         "password": PASSWORD, "groups": ["class-3b"]}).get_json()
    copy = users(other)["ada@school.test"]
    assert copy["username"] == "ada" and copy["groups"] == ["class-3b"] and copy["has_password"]
    # The same password works on the other side.
    assert other.test_client(login=None).post("/auth/login", data={"username": "ada", "password": PASSWORD}).status_code == 302

    # A change made on the other side comes back.
    other.test_client().put(f"/api/users/{copy['id']}", json={"role": "publisher", "email": "ada@new.test"})
    assert users(kit)["ada@new.test"]["role"] == "publisher"
    assert "ada@school.test" not in users(kit)

    kit.test_client().delete(f"/api/users/{created['id']}")
    assert "ada@new.test" not in users(other)


def test_changes_wait_while_the_other_side_is_offline(tmp_path):
    kit = make_app(tmp_path / "kit", SSO_SECRET=SECRET, SSO_PEER_URL="http://other.test")
    other = make_app(tmp_path / "other", SSO_SECRET=SECRET, SSO_PEER_URL="http://kit.test")
    up = {"value": False}
    link(kit, other, online=lambda: up["value"])
    link(other, kit)
    admin = kit.test_client()
    admin.post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    assert "ada@school.test" not in users(other)
    assert admin.get("/auth/me").get_json()["sso"]["pending"] == 1
    up["value"] = True
    result = admin.post("/api/sso/sync", json={}).get_json()
    assert result["ok"] is True
    assert "ada@school.test" in users(other)
    assert admin.get("/auth/me").get_json()["sso"]["pending"] == 0


def test_full_sync_merges_users_made_before_sync_was_turned_on(tmp_path):
    kit = make_app(tmp_path / "kit")
    other = make_app(tmp_path / "other")
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    other.test_client().post("/api/users", json={"username": "bob", "email": "bob@school.test", "password": PASSWORD})
    for app, peer in ((kit, "http://other.test"), (other, "http://kit.test")):
        app.config.update(SSO_SECRET=SECRET, SSO_PEER_URL=peer)
    link(kit, other)
    link(other, kit)
    kit.test_client().post("/api/sso/sync", json={})
    assert {"ada@school.test", "bob@school.test"} <= set(users(kit)) & set(users(other))


def test_older_changes_never_overwrite_newer_ones(pair):
    kit, _ = pair
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    stale = {"email": "ada@school.test", "username": "ada", "role": "admin", "updated_at": "2000-01-01T00:00:00Z"}
    body = json.dumps({"users": [stale]}).encode()
    headers = protocol.sign_request(SECRET, "POST", "/api/sso/users", body)
    headers["Content-Type"] = "application/json"
    result = kit.test_client(login=None).post("/api/sso/users", data=body, headers=headers).get_json()
    assert result["results"] == ["stale"]
    assert users(kit)["ada@school.test"]["role"] == "user"


def test_the_last_admin_is_never_removed_by_sync(pair):
    kit, _ = pair
    record = {"email": "admin@localhost", "deleted": True, "updated_at": protocol.timestamp_now()}
    body = json.dumps({"users": [record]}).encode()
    headers = {**protocol.sign_request(SECRET, "POST", "/api/sso/users", body), "Content-Type": "application/json"}
    result = kit.test_client(login=None).post("/api/sso/users", data=body, headers=headers).get_json()
    assert result["results"] == ["kept-last-admin"]


def test_login_ticket_signs_in_once(pair):
    kit, _ = pair
    kit.test_client().post("/api/users", json={"username": "ada", "email": "ada@school.test", "password": PASSWORD})
    ticket = protocol.make_ticket(SECRET, email="ada@school.test", audience="construction-kit", purpose="login", ttl=60)
    browser = kit.test_client(login=None)
    response = browser.post("/auth/sso/accept", data={"ticket": ticket, "next": "/sprites"})
    assert response.status_code == 302 and response.headers["Location"] == "/sprites"
    assert browser.get("/auth/me").get_json()["user"]["email"] == "ada@school.test"
    assert kit.test_client(login=None).post("/auth/sso/accept", data={"ticket": ticket}).status_code == 400
    wrong = protocol.make_ticket(SECRET, email="ada@school.test", audience="cartridge-store", purpose="login", ttl=60)
    assert kit.test_client(login=None).post("/auth/sso/accept", data={"ticket": wrong}).status_code == 400


def test_open_cartridge_store_button_makes_a_ticket_for_the_store(pair):
    kit, _ = pair
    page = kit.test_client().get("/auth/sso/peer?next=/publish").get_data(as_text=True)
    assert 'action="http://other.test/auth/sso/accept"' in page and 'value="/publish"' in page
    ticket = page.split('name="ticket" value="', 1)[1].split('"', 1)[0]
    claims = protocol.read_ticket(SECRET, ticket, audience="cartridge-store", purpose="login")
    assert claims["email"] == "admin@localhost"


def test_publishing_to_the_synced_store_uses_a_one_time_ticket(pair, monkeypatch):
    kit, _ = pair
    kit.config["STORE_TRUSTED_LOCAL"] = True  # the peer here is plain http, as on a classroom LAN (ADR-0008)
    client = kit.test_client()
    profile = client.post("/api/publish_profiles", json={"name": "School store", "store_url": "http://other.test/"}).get_json()
    assert profile["uses_sso"] is True
    from conftest import make_store_bundle, review_and_publish

    artifact = make_store_bundle(client, monkeypatch)
    sent = {}

    def fake_publish(store_url, token, path):
        sent["token"] = token
        return {"ok": True}

    monkeypatch.setattr("prg32_construction_kit.routes.publish_bundle", fake_publish)
    review_and_publish(client, profile["id"], artifact["id"])
    claims = protocol.read_ticket(SECRET, sent["token"], audience="cartridge-store", purpose="api")
    assert claims and claims["email"] == "admin@localhost"


def test_discovery_says_whether_sso_is_on(pair, tmp_path):
    kit, _ = pair
    assert kit.test_client(login=None).get("/.well-known/prg32-construction-kit.json").get_json()["sso"]["enabled"] is True
    plain = make_app(tmp_path / "plain")
    assert plain.test_client(login=None).get("/.well-known/prg32-construction-kit.json").get_json()["sso"]["enabled"] is False
