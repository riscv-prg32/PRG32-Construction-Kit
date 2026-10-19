"""School sign-in against a real OpenID Connect provider (opt-in; ADR-0016).

Off unless ``PRG32_LIVE_OIDC`` is set:

- ``PRG32_LIVE_OIDC=keycloak`` starts Keycloak (quay.io/keycloak/keycloak:26.0.7) in Docker
  on 127.0.0.1:8080 with the test realm tests/fixtures/oidc/school-realm.json (test users
  and a test client secret only; nothing real), runs everything below and removes it.
- ``PRG32_LIVE_OIDC=external`` uses an institution's tenant. Nothing is committed: set
  PRG32_LIVE_OIDC_ISSUER, PRG32_LIVE_OIDC_CLIENT_ID, PRG32_LIVE_OIDC_SECRET (the client
  secret, read from the environment only), PRG32_LIVE_OIDC_USER / _PASSWORD / _EMAIL
  (a test pupil). Register http://127.0.0.1:5155/auth/oidc/school/callback with the
  provider. Tests that need provider administration (key rotation, disabling a user,
  role claims) run only with Keycloak. The tenant's login page must have fields named
  ``username`` and ``password`` (override with PRG32_LIVE_OIDC_FORM="user-css;pass-css;submit-css").

What a real provider proves beyond tests/test_identity.py: discovery and JWKS from a real
server, PKCE enforced by the provider, a real browser login, state handling across real
redirects, issuer/audience/expiry checks on real tokens, key rotation, account collision
and explicit linking, deactivation on both sides, and recovery.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import requests

from prg32_construction_kit import identity

MODE = os.environ.get("PRG32_LIVE_OIDC", "")
pytestmark = pytest.mark.skipif(MODE not in ("keycloak", "external"),
                                reason="live identity provider tests are opt-in: set PRG32_LIVE_OIDC=keycloak or external")
ROOT = Path(__file__).resolve().parent.parent
REALM = ROOT / "tests" / "fixtures" / "oidc" / "school-realm.json"
KEYCLOAK_IMAGE = "quay.io/keycloak/keycloak:26.0.7"
KEYCLOAK = "http://localhost:8080"
KEYCLOAK_ADMIN = ("admin", "kc-admin-test-only")      # the throwaway container's admin, test only
KIT_PORT = int(os.environ.get("PRG32_LIVE_KIT_PORT", "5155"))
KIT = f"http://127.0.0.1:{KIT_PORT}"


def realm_users() -> dict[str, dict[str, str]]:
    data = json.loads(REALM.read_text())
    return {user["username"]: {"email": user["email"], "password": user["credentials"][0]["value"]}
            for user in data["users"]}


@pytest.fixture(scope="module")
def provider():
    if MODE == "external":
        needed = ("PRG32_LIVE_OIDC_ISSUER", "PRG32_LIVE_OIDC_CLIENT_ID", "PRG32_LIVE_OIDC_SECRET",
                  "PRG32_LIVE_OIDC_USER", "PRG32_LIVE_OIDC_PASSWORD", "PRG32_LIVE_OIDC_EMAIL")
        missing = [name for name in needed if not os.environ.get(name)]
        if missing:
            pytest.fail("PRG32_LIVE_OIDC=external needs " + ", ".join(missing), pytrace=False)
        yield {"issuer": os.environ["PRG32_LIVE_OIDC_ISSUER"], "client_id": os.environ["PRG32_LIVE_OIDC_CLIENT_ID"],
               "secret_env": "PRG32_LIVE_OIDC_SECRET", "admin": False,
               "users": {"ada": {"username": os.environ["PRG32_LIVE_OIDC_USER"],
                                 "password": os.environ["PRG32_LIVE_OIDC_PASSWORD"],
                                 "email": os.environ["PRG32_LIVE_OIDC_EMAIL"]}}}
        return
    if shutil.which("docker") is None:
        pytest.fail("PRG32_LIVE_OIDC=keycloak needs Docker", pytrace=False)
    subprocess.run(["docker", "rm", "-f", "prg32-live-kc"], capture_output=True)
    started = subprocess.run(
        ["docker", "run", "-d", "--name", "prg32-live-kc", "-p", "127.0.0.1:8080:8080",
         "-e", f"KC_BOOTSTRAP_ADMIN_USERNAME={KEYCLOAK_ADMIN[0]}", "-e", f"KC_BOOTSTRAP_ADMIN_PASSWORD={KEYCLOAK_ADMIN[1]}",
         "-v", f"{REALM.parent}:/opt/keycloak/data/import:ro", KEYCLOAK_IMAGE,
         "start-dev", "--import-realm", f"--hostname={KEYCLOAK}"], capture_output=True, text=True)
    assert started.returncode == 0, started.stderr
    try:
        for _ in range(90):
            try:
                if requests.get(f"{KEYCLOAK}/realms/school/.well-known/openid-configuration", timeout=2).ok:
                    break
            except requests.RequestException:
                pass
            time.sleep(2)
        users = {name: {"username": name, **values} for name, values in realm_users().items()}
        os.environ["PRG32_LIVE_OIDC_SECRET"] = json.loads(REALM.read_text())["clients"][0]["secret"]
        yield {"issuer": f"{KEYCLOAK}/realms/school", "client_id": "prg32-kit", "secret_env": "PRG32_LIVE_OIDC_SECRET",
               "admin": True, "users": users}
    finally:
        subprocess.run(["docker", "rm", "-f", "prg32-live-kc"], capture_output=True)


class KeycloakAdmin:
    def __init__(self):
        token = requests.post(f"{KEYCLOAK}/realms/master/protocol/openid-connect/token", timeout=10,
                              data={"grant_type": "password", "client_id": "admin-cli",
                                    "username": KEYCLOAK_ADMIN[0], "password": KEYCLOAK_ADMIN[1]}).json()["access_token"]
        self.headers = {"Authorization": f"Bearer {token}"}

    def user_id(self, username):
        return requests.get(f"{KEYCLOAK}/admin/realms/school/users", params={"username": username, "exact": "true"},
                            headers=self.headers, timeout=10).json()[0]["id"]

    def set_enabled(self, username, enabled):
        response = requests.put(f"{KEYCLOAK}/admin/realms/school/users/{self.user_id(username)}",
                                json={"enabled": enabled}, headers=self.headers, timeout=10)
        assert response.status_code == 204, response.text

    def rotate_keys(self):
        realm_id = requests.get(f"{KEYCLOAK}/admin/realms/school", headers=self.headers, timeout=10).json()["id"]
        response = requests.post(f"{KEYCLOAK}/admin/realms/school/components", headers=self.headers, timeout=10, json={
            "name": "rotated-" + str(int(time.time())), "providerId": "rsa-generated",
            "providerType": "org.keycloak.keys.KeyProvider", "parentId": realm_id,
            "config": {"priority": ["500"], "keySize": ["2048"], "active": ["true"], "enabled": ["true"],
                       "algorithm": ["RS256"]}})
        assert response.status_code == 201, response.text


@pytest.fixture(scope="module")
def kit(provider, tmp_path_factory):
    from werkzeug.serving import make_server

    from conftest import make_app

    app = make_app(tmp_path_factory.mktemp("live-oidc-kit"), PUBLIC_URL=KIT)
    admin = app.test_client()
    created = admin.post("/api/admin/identity_providers", json={
        "slug": "school", "name": "School (live)", "issuer": provider["issuer"], "client_id": provider["client_id"],
        "client_secret_ref": "env:" + provider["secret_env"], "role_claim": "roles",
        "role_map": {"faculty": "teacher", "pupil": "student", "staff": "facilitator"}})
    assert created.status_code == 201, created.get_json()
    server = make_server("127.0.0.1", KIT_PORT, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    identity.forget_caches()
    yield {"app": app, "admin": admin}
    server.shutdown()


@pytest.fixture()
def browser():
    from test_browser_offline import playwright_api

    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({"channel": "chrome"}, {}):
            try:
                launched = playwright.chromium.launch(headless=True, **options)
                break
            except Exception:  # noqa: BLE001, S112 - try Playwright's Chromium next
                continue
        if launched is None:
            pytest.fail("the live identity tests need Chrome or Playwright's Chromium", pytrace=False)
        yield launched
        launched.close()


FORM = os.environ.get("PRG32_LIVE_OIDC_FORM", "#username;#password;#kc-login").split(";")


def on_kit(url: str) -> bool:
    return urlsplit(url).netloc == urlsplit(KIT).netloc


def provider_form(page, user):
    """On the provider's sign-in page: type the test user's name and password."""
    page.fill(FORM[0], user["username"])
    page.fill(FORM[1], user["password"])
    page.click(FORM[2])


def school_login(page, user, expect_kit=True, before_submit=None):
    """Press the school button in the kit; sign in at the provider unless it remembers us; come back.

    The provider keeps its own session: signing out of the kit does not end it (ADR-0016),
    so a second school sign-in in the same browser may skip the provider's form.
    """
    page.goto(f"{KIT}/auth/oidc/school/login")
    deadline = time.time() + 20
    while time.time() < deadline and not on_kit(page.url) and not page.query_selector(FORM[0]):
        page.wait_for_timeout(100)
    if not on_kit(page.url):
        if before_submit:
            before_submit()
        provider_form(page, user)
    if expect_kit:
        page.wait_for_url(on_kit, timeout=20000)


def who(page):
    return page.evaluate("fetch('/auth/me').then(r => r.json()).then(d => d.user)")


def audit_reasons(kit):
    events = kit["admin"].get("/api/admin/audit", query_string={"action": "oidc_sign_in", "limit": 50}).get_json()
    assert "events" in events, events
    return [event["metadata"].get("reason", event["outcome"]) for event in events["events"]]


def test_real_sign_in_with_discovery_jwks_and_pkce(kit, provider, browser):
    document = requests.get(provider["issuer"] + "/.well-known/openid-configuration", timeout=10).json()
    assert document["issuer"] == provider["issuer"] and "S256" in document.get("code_challenge_methods_supported", ["S256"])
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["ada"])
    me = who(page)
    assert me["authenticated"] and me["email"] == provider["users"]["ada"]["email"]
    with kit["app"].app_context():
        row = identity.db.session.scalar(identity.select(identity.ExternalIdentity)
                                         .where(identity.ExternalIdentity.user_id == me["id"]))
        assert row.issuer == provider["issuer"] and row.subject      # keyed by issuer + subject
    context.close()


def test_the_provider_enforces_pkce(kit, provider, browser, monkeypatch):
    real = identity._token_request

    def without_verifier(item, document, code, verifier):
        return real(item, document, code, "not-the-verifier-" + "x" * 40)

    monkeypatch.setattr(identity, "_token_request", without_verifier)
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["ada"])
    assert who(page)["authenticated"] is False
    assert audit_reasons(kit)[0] == "invalid_token"     # the provider refused the code exchange
    context.close()


def test_a_tampered_state_is_refused(kit, provider, browser):
    context = browser.new_context()
    page = context.new_page()
    # The provider sends the browser back with a state this browser's kit session never made
    # (a sign-in started elsewhere, e.g. a link from an attacker): the kit cookie is gone.
    school_login(page, provider["users"]["ada"],
                 before_submit=lambda: context.clear_cookies(name="prg32_kit_session"))
    assert who(page)["authenticated"] is False and audit_reasons(kit)[0] == "bad_state"
    context.close()


def test_expired_tokens_are_refused(kit, provider, browser, monkeypatch):
    real = time.time
    monkeypatch.setattr(identity, "now_seconds", lambda: real() + 3600)   # the kit's clock is an hour ahead
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["ada"])
    assert who(page)["authenticated"] is False
    assert audit_reasons(kit)[0] in ("invalid_token", "expired_flow")
    context.close()


def test_a_wrong_audience_is_refused(kit, provider, browser, monkeypatch):
    real = identity.verify_id_token

    def other_client(token, item, jwks_uri, nonce, now=None):
        import dataclasses

        return real(token, dataclasses.replace(item, client_id="another-application"), jwks_uri, nonce, now)

    monkeypatch.setattr(identity, "verify_id_token", other_client)
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["ada"])
    assert who(page)["authenticated"] is False and audit_reasons(kit)[0] == "invalid_token"
    context.close()


def test_collision_then_explicit_linking_then_recovery(kit, provider, browser):
    user = provider["users"].get("eve") or provider["users"]["ada"]
    kit["admin"].post("/api/users", json={"username": "eve-local", "email": user["email"],
                                          "password": "eve-local-password-1"})
    context = browser.new_context()
    page = context.new_page()
    school_login(page, user)
    assert who(page)["authenticated"] is False and audit_reasons(kit)[0] == "email_in_use"
    # The owner signs in the usual way and links the school account deliberately.
    page.goto(f"{KIT}/auth/login")
    page.fill("#username", "eve-local")
    page.fill("#password", "eve-local-password-1")
    page.click("button[type=submit]")
    page.wait_for_url(f"{KIT}/")
    redirect = page.evaluate("fetch('/auth/identities/school/link', {method: 'POST', headers: {'X-PRG32-Kit': '1',"
                             " 'Content-Type': 'application/json'}, body: '{}'}).then(r => r.json()).then(d => d.redirect)")
    page.goto(redirect)
    if "/auth/oidc/school/callback" not in page.url and urlsplit(page.url).netloc != urlsplit(KIT).netloc:
        page.fill("#username", user["username"])
        page.fill("#password", user["password"])
        page.click("#kc-login")
    page.wait_for_url(f"{KIT}/account", timeout=20000)
    identities = page.evaluate("fetch('/auth/identities').then(r => r.json()).then(d => d.identities)")
    assert [item["provider"] for item in identities] == ["school"]
    # Recovery: unlink (a password remains), then school sign-in no longer finds the account.
    page.evaluate(f"fetch('/auth/identities/{identities[0]['id']}', {{method: 'DELETE', headers: {{'X-PRG32-Kit': '1'}}}})")
    page.evaluate("fetch('/auth/logout', {method: 'POST', headers: {'X-PRG32-Kit': '1'}})")
    school_login(page, user)
    assert who(page)["authenticated"] is False and audit_reasons(kit)[0] == "email_in_use"
    context.close()


def test_deactivation_on_both_sides(kit, provider, browser):
    user = provider["users"]["ada"]

    def fresh():
        """A new browser context: no kit session and no provider session (another day, another computer)."""
        return browser.new_context().new_page()

    page = fresh()
    school_login(page, user)
    me = who(page)
    assert me["authenticated"]
    kit["admin"].post(f"/api/users/{me['id']}/deactivate", json={})
    assert who(page)["authenticated"] is False                    # the kit session ended at once
    page = fresh()
    school_login(page, user)
    assert who(page)["authenticated"] is False and audit_reasons(kit)[0] == "account_disabled"
    kit["admin"].post(f"/api/users/{me['id']}/reactivate", json={})
    page = fresh()
    school_login(page, user)
    assert who(page)["id"] == me["id"]                             # recovery: the same account
    if provider["admin"]:
        # Switched off at the school: the provider itself refuses the sign-in.
        keycloak = KeycloakAdmin()
        keycloak.set_enabled(user["username"], False)
        try:
            page = fresh()
            school_login(page, user, expect_kit=False)
            page.wait_for_timeout(1000)
            assert not on_kit(page.url)
        finally:
            keycloak.set_enabled(user["username"], True)


def test_key_rotation_and_role_claims(kit, provider, browser, monkeypatch):
    if not provider["admin"]:
        pytest.skip("needs provider administration (Keycloak mode)")
    monkeypatch.setattr(identity, "JWKS_REFRESH_SECONDS", 0)
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["prof"])
    assert who(page)["kit_role"] == "teacher" and who(page)["role"] == "user"   # a claim never grants a global role
    before = {key["kid"] for key in requests.get(f"{provider['issuer']}/protocol/openid-connect/certs", timeout=10).json()["keys"]}
    KeycloakAdmin().rotate_keys()
    after = {key["kid"] for key in requests.get(f"{provider['issuer']}/protocol/openid-connect/certs", timeout=10).json()["keys"]}
    assert after - before                                           # a new signing key exists
    page = browser.new_context().new_page()
    school_login(page, provider["users"]["prof"])
    assert who(page)["authenticated"] is True                       # signed with the new key: fetched and verified
    context.close()


def test_signing_out_says_the_school_session_may_remain(kit, provider, browser):
    context = browser.new_context()
    page = context.new_page()
    school_login(page, provider["users"]["ada"])
    page.goto(f"{KIT}/account")
    answer = page.evaluate("fetch('/auth/logout', {method: 'POST', headers: {'X-PRG32-Kit': '1', 'Accept': 'application/json'}})"
                           ".then(r => r.json())")
    assert answer == {"ok": True, "school_session_ended": False}
    context.close()
