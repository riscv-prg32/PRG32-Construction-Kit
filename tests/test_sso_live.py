"""Shared accounts and single sign-on with a real Cartridge Store, over real HTTP (opt-in).

Off unless ``PRG32_LIVE_STORE=local``, like tests/test_store_live.py. The kit runs as an HTTP
server on 127.0.0.1 and a throwaway CartridgeStore (the checkout next to the kit, temporary
data, a test admin password) as a separate process on 127.0.0.1:5161; both get the same
test-only secret and each other's address. Nothing else can be reached.

What it proves, with real HTTP both ways (tests/test_sso_with_cartridge_store.py proves the
same in-process):

- a user made in the kit reaches the Store, and a role changed by the Store's admin reaches
  the kit (sync);
- a kit sign-in ticket signs the student in to the Store, and a Store ticket signs them in to
  the kit (single sign-on), each ticket only once;
- publishing as the student: the kit sends a one-time API ticket and the Store accepts the
  bundle as a pending submission; the same ticket again, a forged one, or a sign-in ticket
  used as an API ticket is refused by the Store;
- a student without the publisher role cannot publish: the kit refuses before anything is
  sent (the Store itself only asks for a signed-in user - recorded below).
"""

from __future__ import annotations

import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
import requests

from conftest import ADMIN_PASSWORD, make_app
from test_store_live import STORE_SOURCE, acknowledge_notice, form_token, store_sign_in

pytestmark = pytest.mark.skipif(os.environ.get("PRG32_LIVE_STORE") != "local",
                                reason="live Store tests are opt-in: set PRG32_LIVE_STORE=local")

PORT = 5161
STORE = f"http://127.0.0.1:{PORT}"
STORE_ADMIN = ("admin", "store-admin-test-only")
SECRET = secrets.token_hex(24)                       # test-only, new every run
PASSWORD = "student-password-1"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    from werkzeug.serving import make_server

    if not (STORE_SOURCE / "cartridge_store" / "app.py").is_file():
        pytest.fail(f"PRG32_LIVE_STORE=local needs a CartridgeStore checkout at {STORE_SOURCE}", pytrace=False)
    kit_port = free_port()
    kit_url = f"http://127.0.0.1:{kit_port}"
    kit = make_app(tmp_path_factory.mktemp("live-sso-kit"), SSO_SECRET=SECRET, SSO_PEER_URL=STORE,
                   STORE_ALLOWED_ORIGINS=[STORE], STORE_TRUSTED_LOCAL=True)
    server = make_server("127.0.0.1", kit_port, kit, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    data = tmp_path_factory.mktemp("live-sso-store")
    env = {**os.environ, "PRG32_STORE_DATA": str(data), "PRG32_STORE_DB": str(data / "store.sqlite"),
           "PRG32_ADMIN_PASSWORD": STORE_ADMIN[1], "SECRET_KEY": secrets.token_hex(16), "PYTHONPATH": str(STORE_SOURCE),
           "PRG32_SSO_SECRET": SECRET, "PRG32_SSO_PEER_URL": kit_url}
    code = f"from cartridge_store import create_app; create_app().run(host='127.0.0.1', port={PORT}, debug=False, use_reloader=False)"
    log = data / "store.log"
    process = subprocess.Popen([sys.executable, "-c", code], env=env, cwd=STORE_SOURCE, stdout=subprocess.DEVNULL,
                               stderr=log.open("a"))
    for _ in range(100):
        try:
            if requests.get(STORE + "/api/games", timeout=1).status_code < 500:
                break
        except requests.RequestException:
            time.sleep(0.2)
    else:
        process.terminate()
        raise AssertionError("the Cartridge Store did not start: " + log.read_text()[-800:])
    yield {"kit": kit, "kit_url": kit_url, "store_db": data / "store.sqlite"}
    process.terminate()
    process.wait(timeout=10)
    server.shutdown()


def browser(base: str, login: tuple[str, str] | None = None) -> requests.Session:
    session = requests.Session()
    session.headers["X-PRG32-Kit"] = "1"
    if login:
        if base == STORE:
            store_sign_in(session, STORE, *login)
        else:
            signed_in = session.post(base + "/auth/login", data={"username": login[0], "password": login[1]},
                                     allow_redirects=False, timeout=10)
            assert signed_in.status_code in (200, 302), signed_in.text[:300]
    return session


def kit_user(pair, name: str, role: str = "user") -> requests.Session:
    admin = browser(pair["kit_url"], ("admin", ADMIN_PASSWORD))
    made = admin.post(pair["kit_url"] + "/api/users", json={"username": name, "email": f"{name}@school.test",
                                                            "password": PASSWORD, "role": role}, timeout=10)
    assert made.status_code == 201, made.text[:300]
    return browser(pair["kit_url"], (name, PASSWORD))


def ticket_from(page: str) -> str:
    found = re.search(r'name="ticket" value="([^"]+)"', page)
    assert found, page[:400]
    return found.group(1)


def test_a_kit_user_reaches_the_store_and_a_store_role_change_reaches_the_kit(pair):
    kit_user(pair, "ada")
    store_ada = browser(STORE, ("ada@school.test", PASSWORD))            # the same password works at the Store
    assert store_ada.get(STORE + "/api/me", timeout=10).json()["user"]["username"] == "ada"
    import sqlite3

    store_admin = browser(STORE, STORE_ADMIN)
    with sqlite3.connect(f"file:{pair['store_db']}?mode=ro", uri=True) as database:   # read only
        ada_id = database.execute("SELECT id FROM users WHERE email = 'ada@school.test'").fetchone()[0]
    token = form_token(store_admin.get(STORE + "/admin/users", timeout=10).text)
    assert store_admin.post(f"{STORE}/admin/users/{ada_id}/role", data={"role": "publisher", **token},
                            allow_redirects=False, timeout=10).status_code in (200, 302)
    kit_admin = browser(pair["kit_url"], ("admin", ADMIN_PASSWORD))
    kit_users = {user["email"]: user for user in kit_admin.get(pair["kit_url"] + "/api/users", timeout=10).json()["users"]}
    assert kit_users["ada@school.test"]["role"] == "publisher"


def test_single_sign_on_both_ways_and_each_ticket_once(pair):
    bob = kit_user(pair, "bob")
    ticket = ticket_from(bob.get(pair["kit_url"] + "/auth/sso/peer?next=/", timeout=10).text)
    store_bob = requests.Session()
    accepted = store_bob.post(STORE + "/auth/sso/accept", data={"ticket": ticket, "next": "/"}, allow_redirects=False,
                              timeout=10)
    assert accepted.status_code == 302
    me = store_bob.get(STORE + "/api/me", timeout=10).json()
    assert me["user"]["email"] == "bob@school.test" and me["user"]["username"] == "bob"
    acknowledge_notice(store_bob, STORE, accepted)
    again = requests.Session()
    again.post(STORE + "/auth/sso/accept", data={"ticket": ticket}, allow_redirects=False, timeout=10)
    assert again.get(STORE + "/api/me", timeout=10).json()["user"]["authenticated"] is False
    back = ticket_from(store_bob.get(STORE + "/auth/sso/peer", timeout=10).text)
    kit_bob = requests.Session()
    assert kit_bob.post(pair["kit_url"] + "/auth/sso/accept", data={"ticket": back}, allow_redirects=False,
                        timeout=10).status_code == 302
    assert kit_bob.get(pair["kit_url"] + "/auth/me", timeout=10).json()["user"]["email"] == "bob@school.test"


def test_publishing_as_the_student_with_a_one_time_api_ticket(pair, monkeypatch):
    from conftest import review_and_publish
    from prg32_construction_kit import sso

    kit = pair["kit"]
    kit.test_client().post("/api/users", json={"username": "cy", "email": "cy@school.test", "password": PASSWORD,
                                               "role": "publisher"})
    cy = kit.test_client(login=("cy", PASSWORD))
    sent = {}
    from prg32_construction_kit import routes

    real_publish = routes.publish_bundle

    def remember(store_url, token, path):
        sent["token"], sent["path"] = token, path
        return real_publish(store_url, token, path)

    monkeypatch.setattr(routes, "publish_bundle", remember)
    profile = cy.post("/api/publish_profiles", json={"name": "Live Store", "store_url": STORE}).get_json()
    # The contract's valid bundle (real PRG32 cartridges), as cy's own artifact.
    from prg32_construction_kit.db import create_resource
    from test_store_live import with_version

    path = Path(kit.config["BUILD_ROOT"]) / "live-sso" / "bundle.zip"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(with_version("0.3.1"))
    cy_id = cy.get("/auth/me").get_json()["user"]["id"]
    with kit.app_context():
        bundle = create_resource("artifacts", {"kind": "store_bundle", "name": "bundle.zip", "path": str(path),
                                               "owner_id": cy_id, "metadata": {"publishable": True}})
    published = review_and_publish(cy, profile["id"], bundle["id"])
    assert published.status_code == 200 and published.get_json()["state"] == "submitted", published.get_json()["result"]
    answer = published.get_json()["result"]["response"]
    assert answer["status"] == "pending" and answer["review_required"] is True       # reached the real Store
    store_admin = browser(STORE, STORE_ADMIN)
    pending = store_admin.get(STORE + "/api/submissions", params={"status": "all"}, timeout=10).json()["submissions"]
    assert any(item.get("id") == answer["submission_id"] for item in pending)

    def upload(token):
        with open(sent["path"], "rb") as bundle_file:
            return requests.post(STORE + "/api/publish/bundle", headers={"Authorization": f"Bearer {token}"},
                                 files={"bundle": ("bundle.zip", bundle_file, "application/zip")}, timeout=20)

    assert upload(sent["token"]).status_code == 401                 # the same ticket only once
    assert upload(sent["token"][:-4] + "AAAA").status_code == 401   # forged
    with kit.app_context():
        login_ticket = sso.make_ticket("cy@school.test", "login")
    assert upload(login_ticket).status_code == 401                  # a sign-in ticket is not an API ticket


def test_a_student_without_the_publisher_role_sends_nothing(pair, monkeypatch):
    from conftest import make_store_bundle

    kit = pair["kit"]
    kit.test_client().post("/api/users", json={"username": "dee", "email": "dee@school.test", "password": PASSWORD})
    dee = kit.test_client(login=("dee", PASSWORD))
    store_admin = browser(STORE, STORE_ADMIN)
    before = len(store_admin.get(STORE + "/api/submissions", params={"status": "all"}, timeout=10).json()["submissions"])
    profile = dee.post("/api/publish_profiles", json={"name": "Live Store", "store_url": STORE})
    bundle = make_store_bundle(dee, monkeypatch, title="Not Allowed")
    review = dee.post("/api/publish/review", json={"profile_id": (profile.get_json() or {}).get("id"),
                                                    "artifact_id": bundle["id"]})
    assert review.status_code == 403
    after = len(store_admin.get(STORE + "/api/submissions", params={"status": "all"}, timeout=10).json()["submissions"])
    assert after == before


def test_store_bundle_upload_checks_sign_in_only(pair):
    """Recorded Store behaviour (docs/upstream/README.md §6.2): the Store accepts a bundle from any
    signed-in user and does not record who sent it; the kit's publisher check is what stops a
    student. This test fails, on purpose, if the Store starts checking roles: update the record."""
    plain = requests.Session()
    assert plain.post(STORE + "/api/publish/bundle", timeout=10).status_code == 401   # not signed in
    source = (STORE_SOURCE / "cartridge_store" / "app.py").read_text()
    handler = source.split('@app.post("/api/publish/bundle")', 1)[1].split("def ", 2)
    assert "@login_required" in handler[0] and "role_at_least" not in handler[1].split("\n    @app.")[0]
