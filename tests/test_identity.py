"""School sign-in: OpenID Connect with PKCE and accounts by issuer + subject (ADR-0016).

An in-process identity provider (tests/fake_idp.py) signs real ID tokens. Proven here:
PKCE, state and nonce are required and single use; the ID token's signature, issuer,
audience, expiry and nonce are checked; key rotation works and unknown keys do not;
accounts are found by issuer + subject, several providers never collide, and an
account is never joined to another because the emails match (linking is a deliberate
act from the Account page); provider claims grant academic roles, never global ones;
redirects cannot be steered from the callback.
"""

from __future__ import annotations

import time
from urllib.parse import urlsplit

import pytest
from fake_idp import FakeIdP

from prg32_construction_kit import identity

PROVIDER = {"slug": "school", "name": "Our school", "issuer": "https://idp.school.test", "client_id": "kit",
            "client_secret_ref": "env:TEST_SCHOOL_SECRET", "role_claim": "roles",
            "role_map": {"faculty": "teacher", "staff": "facilitator", "pupil": "student"}}


@pytest.fixture()
def idp(app, client, monkeypatch):
    fake = FakeIdP()
    monkeypatch.setenv("TEST_SCHOOL_SECRET", fake.secret)
    monkeypatch.setattr(identity, "http", fake.http)
    identity.forget_caches()
    assert client.post("/api/admin/identity_providers", json=PROVIDER).status_code == 201
    yield fake
    identity.forget_caches()


def start(browser, slug="school", next_page="/projects"):
    response = browser.get(f"/auth/oidc/{slug}/login", query_string={"next": next_page})
    assert response.status_code == 302, response.get_data(as_text=True)
    return response.headers["Location"]


def finish(browser, grant, slug="school", **extra):
    return browser.get(f"/auth/oidc/{slug}/callback", query_string={"code": grant["code"], "state": grant["state"],
                                                                     **extra})


def school_sign_in(browser, fake, subject, email="", slug="school", **claims):
    return finish(browser, fake.authorize(start(browser, slug), subject, email, **claims), slug)


def me(browser):
    return browser.get("/auth/me").get_json()["user"]


def audit(client, action):
    return client.get("/api/admin/audit", query_string={"action": action}).get_json()["events"]


# --- the flow -----------------------------------------------------------------------

def test_sign_in_uses_pkce_state_and_nonce(app, idp):
    browser = app.test_client(login=None)
    location = start(browser)
    query = dict(part.split("=", 1) for part in urlsplit(location).query.split("&"))
    assert location.startswith("https://idp.school.test/authorize?")
    assert query["code_challenge_method"] == "S256" and len(query["code_challenge"]) >= 43
    assert len(query["state"]) >= 32 and len(query["nonce"]) >= 32 and query["response_type"] == "code"
    grant = idp.authorize(location, "pupil-1", "ada@school.test", roles=["pupil"])
    response = finish(browser, grant)
    assert response.status_code == 302 and response.headers["Location"] == "/projects"
    assert me(browser)["email"] == "ada@school.test" and me(browser)["kit_role"] == "student"


def test_a_tampered_pkce_verifier_is_refused(app, idp):
    browser = app.test_client(login=None)
    grant = idp.authorize(start(browser), "pupil-1", "ada@school.test")
    idp.codes[grant["code"]]["challenge"] = "x" * 43     # the verifier the kit sends no longer matches
    response = finish(browser, grant)
    assert response.status_code == 401 and b"did not accept" in response.data
    assert me(browser)["authenticated"] is False


@pytest.mark.parametrize("problem", ["missing", "reused", "other_provider", "expired"])
def test_state_must_be_this_browsers_fresh_single_use_state(app, client, idp, monkeypatch, problem):
    browser = app.test_client(login=None)
    grant = idp.authorize(start(browser), "pupil-1", "ada@school.test")
    if problem == "missing":
        response = browser.get("/auth/oidc/school/callback", query_string={"code": grant["code"]})
    elif problem == "reused":
        assert finish(browser, grant).status_code == 302
        browser.post("/auth/logout")
        response = finish(browser, grant)
    elif problem == "other_provider":
        second = dict(PROVIDER, slug="other", issuer="https://idp2.school.test")
        assert client.post("/api/admin/identity_providers", json=second).status_code == 201
        response = finish(browser, grant, slug="other")
    else:
        real = time.time
        monkeypatch.setattr(identity.time, "time", lambda: real() + identity.FLOW_SECONDS + 5)
        response = finish(browser, grant)
    assert response.status_code == 400
    assert me(browser)["authenticated"] is False or problem == "reused"


def test_state_from_another_browser_is_refused(app, idp):
    attacker, victim = app.test_client(login=None), app.test_client(login=None)
    grant = idp.authorize(start(attacker), "attacker", "eve@school.test")
    assert finish(victim, grant).status_code == 400   # login CSRF: the victim's session has no such state
    assert me(victim)["authenticated"] is False


def test_the_return_page_cannot_be_steered(app, idp):
    browser = app.test_client(login=None)
    grant = idp.authorize(start(browser, next_page="https://evil.example/"), "pupil-1", "ada@school.test")
    assert finish(browser, grant, next="https://evil.example/").headers["Location"] == "/"


def test_provider_errors_and_unknown_providers(app, idp):
    browser = app.test_client(login=None)
    grant = idp.authorize(start(browser), "pupil-1", "ada@school.test")
    assert finish(browser, grant, error="access_denied").status_code == 401
    assert browser.get("/auth/oidc/nobody/login").status_code == 404


# --- the ID token -------------------------------------------------------------------

@pytest.mark.parametrize("patch, header", [
    ({"iss": "https://evil.example"}, {}),
    ({"aud": "someone-else"}, {}),
    ({"aud": ["kit", "someone-else"]}, {}),                 # several audiences without azp
    ({"exp": int(time.time()) - 3600}, {}),
    ({"iat": int(time.time()) + 3600}, {}),
    ({"nonce": "not-this-sign-in"}, {}),
    ({"sub": None}, {}),
    ({}, {"alg": "none"}),
    ({}, {"alg": "HS256"}),
])
def test_bad_id_tokens_are_refused(app, client, idp, patch, header):
    browser = app.test_client(login=None)
    idp.claims_patch, idp.header_patch = patch, header
    response = school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    assert response.status_code == 401, response.get_data(as_text=True)
    assert me(browser)["authenticated"] is False
    assert audit(client, "oidc_sign_in")[0]["metadata"]["reason"] == "invalid_token"


def test_several_audiences_with_the_right_azp_are_accepted(app, idp):
    browser = app.test_client(login=None)
    idp.claims_patch = {"aud": ["kit", "another"], "azp": "kit"}
    assert school_sign_in(browser, idp, "pupil-1", "ada@school.test").status_code == 302


def test_a_forged_signature_is_refused(app, idp, monkeypatch):
    browser = app.test_client(login=None)
    real_sign = idp.sign
    monkeypatch.setattr(idp, "sign", lambda claims, header=None, **kw: real_sign(claims, header)[:-8] + "AAAAAAAA")
    response = school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    assert response.status_code == 401 and b"signature" in response.data


def test_key_rotation_is_followed_but_unknown_keys_are_not(app, idp, monkeypatch):
    browser = app.test_client(login=None)
    assert school_sign_in(browser, idp, "pupil-1", "ada@school.test").status_code == 302
    browser.post("/auth/logout")
    idp.rotate()                                   # a new key the kit has not seen yet
    real = time.time                               # (the cache may be refreshed once a minute)
    monkeypatch.setattr(identity.time, "time", lambda: real() + identity.JWKS_REFRESH_SECONDS + 1)
    assert school_sign_in(browser, idp, "pupil-1", "ada@school.test").status_code == 302
    browser.post("/auth/logout")
    idp.sign_with = "never-published"
    response = school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    assert response.status_code == 401 and b"unknown key" in response.data


def test_es256_providers_work(app, client, monkeypatch):
    fake = FakeIdP(issuer="https://ec.school.test", algorithm="ES256")
    monkeypatch.setenv("TEST_SCHOOL_SECRET", fake.secret)
    monkeypatch.setattr(identity, "http", fake.http)
    identity.forget_caches()
    client.post("/api/admin/identity_providers", json=dict(PROVIDER, slug="ec", issuer=fake.issuer))
    browser = app.test_client(login=None)
    assert school_sign_in(browser, fake, "p-1", "ec@school.test", slug="ec").status_code == 302


# --- accounts ---------------------------------------------------------------------------

def test_accounts_are_found_by_issuer_and_subject(app, idp):
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    first = me(browser)["id"]
    browser.post("/auth/logout")
    school_sign_in(browser, idp, "pupil-1", "ada.lovelace@school.test")   # the school changed her email
    assert me(browser)["id"] == first


def test_two_providers_never_collide(app, client, idp, monkeypatch):
    other = FakeIdP(issuer="https://idp2.school.test")
    monkeypatch.setenv("TEST_OTHER_SECRET", other.secret)
    client.post("/api/admin/identity_providers", json=dict(PROVIDER, slug="other", issuer=other.issuer,
                                                           client_secret_ref="env:TEST_OTHER_SECRET"))
    route = {idp.issuer: idp.http, other.issuer: other.http}
    monkeypatch.setattr(identity, "http", lambda method, url, **kw: route[url.split("/", 3)[0] + "//"
                                                                        + url.split("/", 3)[2]](method, url, **kw))
    a, b = app.test_client(login=None), app.test_client(login=None)
    school_sign_in(a, idp, "42", "one@school.test")
    school_sign_in(b, other, "42", "two@school.test", slug="other")      # same subject, other issuer
    assert me(a)["id"] != me(b)["id"]


def test_matching_email_never_joins_accounts(app, client, idp):
    from test_auth import make_student

    student = make_student(client, "ada")
    browser = app.test_client(login=None)
    response = school_sign_in(browser, idp, "pupil-1", student["email"])
    assert response.status_code == 403 and b"already exists" in response.data
    assert me(browser)["authenticated"] is False
    assert client.get(f"/api/users/{student['id']}").get_json()["identities"] == []
    assert audit(client, "oidc_sign_in")[0]["metadata"]["reason"] == "email_in_use"


def test_linking_is_a_deliberate_act_of_the_signed_in_owner(app, client, idp):
    from test_auth import make_student, student_client

    student = make_student(client, "ada")
    ada = student_client(app, "ada")
    redirect = ada.post("/auth/identities/school/link", json={}).get_json()["redirect"]
    response = finish(ada, idp.authorize(redirect, "pupil-1", student["email"]))
    assert response.status_code == 302 and response.headers["Location"] == "/account"
    assert [item["provider"] for item in ada.get("/auth/identities").get_json()["identities"]] == ["school"]
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "pupil-1", student["email"])
    assert me(browser)["id"] == student["id"]
    # The same school account cannot be linked to a second kit account.
    make_student(client, "bob")
    bob = student_client(app, "bob")
    redirect = bob.post("/auth/identities/school/link", json={}).get_json()["redirect"]
    assert finish(bob, idp.authorize(redirect, "pupil-1", "x@school.test")).status_code == 409


def test_a_link_started_by_someone_else_is_refused(app, client, idp):
    from test_auth import make_student, student_client

    make_student(client, "ada")
    ada = student_client(app, "ada")
    redirect = ada.post("/auth/identities/school/link", json={}).get_json()["redirect"]
    ada.post("/auth/logout")
    response = finish(ada, idp.authorize(redirect, "pupil-1", "a@school.test"))
    assert response.status_code in (400, 403)


def test_unlinking_keeps_a_way_to_sign_in(app, idp):
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    only = browser.get("/auth/identities").get_json()["identities"][0]
    assert browser.delete(f"/auth/identities/{only['id']}").status_code == 400   # no password: keep it


def test_provider_claims_grant_academic_roles_only(app, client, idp):
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "prof-1", "prof@school.test", roles=["faculty"])
    assert me(browser)["kit_role"] == "teacher" and me(browser)["role"] == "user"
    bad = dict(PROVIDER, slug="bad", role_map={"faculty": "admin"})
    assert client.post("/api/admin/identity_providers", json=bad).status_code == 400


def test_switched_off_accounts_cannot_use_school_sign_in(app, client, idp):
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    user_id = me(browser)["id"]
    client.post(f"/api/users/{user_id}/deactivate")
    assert me(browser)["authenticated"] is False
    assert school_sign_in(browser, idp, "pupil-1", "ada@school.test").status_code == 403


def test_allowed_domains_limit_new_accounts(app, client, idp):
    client.put("/api/admin/identity_providers/school", json={"allowed_domains": ["school.test"]})
    browser = app.test_client(login=None)
    assert school_sign_in(browser, idp, "x", "someone@elsewhere.test").status_code == 403


# --- administrators -------------------------------------------------------------------

def test_only_administrators_manage_providers_and_secrets_stay_references(app, client, idp):
    from test_auth import make_student, student_client

    make_student(client, "ada")
    ada = student_client(app, "ada")
    assert ada.get("/api/admin/identity_providers").status_code == 403
    assert ada.post("/api/admin/identity_providers", json=dict(PROVIDER, slug="mine")).status_code == 403
    listed = client.get("/api/admin/identity_providers").get_json()["providers"]
    assert listed[0]["client_secret_ref"] == "env:TEST_SCHOOL_SECRET" and idp.secret not in str(listed)
    plain = dict(PROVIDER, slug="plain", client_secret_ref="my-real-secret")
    assert client.post("/api/admin/identity_providers", json=plain).status_code == 400
    insecure = dict(PROVIDER, slug="insecure", issuer="http://idp.example.org")
    assert client.post("/api/admin/identity_providers", json=insecure).status_code == 400
    assert audit(client, "identity_provider_create")[0]["target_id"] == "school"


def test_no_secret_code_or_token_reaches_the_audit_log(app, client, idp):
    browser = app.test_client(login=None)
    school_sign_in(browser, idp, "pupil-1", "ada@school.test")
    events = str(client.get("/api/admin/audit", query_string={"limit": 200}).get_json())
    assert idp.secret not in events and "id_token" not in events and "code_verifier" not in events


def test_endpoints_must_be_https_except_on_this_computer():
    assert identity.check_endpoint("https://idp.school.test/x")
    assert identity.check_endpoint("http://127.0.0.1:8080/x")
    for url in ("http://idp.school.test/x", "ftp://idp/x", "https:///x", ""):
        with pytest.raises(ValueError):
            identity.check_endpoint(url)
