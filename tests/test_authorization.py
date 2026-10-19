"""Who may do what (ADR-0016): negative tests first.

Cross-owner reads and writes, shared read-only items, role escalation, classes (teachers
and facilitators read their students' work, never change or publish it), scoped and
expiring API tokens, stale and revoked sessions, deactivated and service accounts, and
the 409 user_changed refusal.
"""

from __future__ import annotations

import pytest
from test_auth import STUDENT_PASSWORD, make_student, student_client


def kit_user(client, app, name, kit_role="student", role="user"):
    user = make_student(client, name, role)
    if kit_role != "student":
        assert client.put(f"/api/users/{user['id']}", json={"kit_role": kit_role}).status_code == 200
    return user, student_client(app, name)


def shared(app, resource, payload):
    """An item without an owner (a shared classroom item); the API never makes these."""
    from prg32_construction_kit.db import create_resource

    with app.app_context():
        return create_resource(resource, {**payload, "owner_id": None})


def project(browser, title="Mine"):
    response = browser.post("/api/projects", json={"title": title})
    assert response.status_code == 201
    return response.get_json()


# --- owners ---------------------------------------------------------------------------

@pytest.mark.parametrize("resource, body", [
    ("projects", {"title": "A"}), ("sprites", {"name": "s", "width": 8, "height": 8}),
    ("assets", {"name": "a"}), ("builds", {"status": "created"}),
    ("artifacts", {"kind": "note", "name": "n"}), ("publish_profiles", {"name": "p"})])
def test_nobody_reads_or_changes_another_students_items(app, client, resource, body):
    _, ada = kit_user(client, app, "ada")
    _, bob = kit_user(client, app, "bob")
    item = ada.post(f"/api/{resource}", json=body).get_json()
    assert bob.get(f"/api/{resource}/{item['id']}").status_code == 404
    assert bob.put(f"/api/{resource}/{item['id']}", json={"name": "taken"}).status_code == 404
    assert bob.delete(f"/api/{resource}/{item['id']}").status_code == 404
    assert item["id"] not in [row["id"] for row in bob.get(f"/api/{resource}").get_json()[resource]]


def test_shared_items_are_read_only_for_students(app, client):
    template = shared(app, "projects", {"title": "Class template"})
    _, ada = kit_user(client, app, "ada")
    assert ada.get(f"/api/projects/{template['id']}").status_code == 200
    assert ada.put(f"/api/projects/{template['id']}", json={"title": "mine now"}).status_code == 403
    assert ada.delete(f"/api/projects/{template['id']}").status_code == 403


def test_owner_cannot_be_reassigned_by_a_student(app, client):
    ada_user, ada = kit_user(client, app, "ada")
    bob_user, bob = kit_user(client, app, "bob")
    item = ada.post("/api/projects", json={"title": "A", "owner_id": bob_user["id"]}).get_json()
    assert item["owner_id"] == ada_user["id"]
    ada.put(f"/api/projects/{item['id']}", json={"owner_id": bob_user["id"]})
    assert bob.get(f"/api/projects/{item['id']}").status_code == 404


# --- escalation -----------------------------------------------------------------------

def test_students_cannot_raise_their_own_roles(app, client):
    ada_user, ada = kit_user(client, app, "ada")
    assert ada.put(f"/api/users/{ada_user['id']}", json={"role": "admin"}).status_code == 403
    assert ada.put(f"/api/users/{ada_user['id']}", json={"kit_role": "teacher"}).status_code == 403
    assert ada.post("/api/classes", json={"name": "my class"}).status_code == 403
    assert ada.post("/auth/tokens", json={"scopes": ["admin"]}).status_code == 400
    assert ada.post("/auth/tokens", json={"scopes": ["publish"]}).status_code == 400
    assert ada.get("/auth/me").get_json()["user"]["role"] == "user"


def test_admins_cannot_change_their_own_academic_role(client):
    me = client.get("/auth/me").get_json()["user"]
    assert client.put(f"/api/users/{me['id']}", json={"kit_role": "teacher"}).status_code == 400


def test_unknown_academic_roles_are_refused(app, client):
    ada_user, _ = kit_user(client, app, "ada")
    assert client.put(f"/api/users/{ada_user['id']}", json={"kit_role": "principal"}).status_code == 400


# --- classes --------------------------------------------------------------------------

@pytest.fixture()
def school(app, client):
    teacher_user, teacher = kit_user(client, app, "ms_t", "teacher")
    facilitator_user, facilitator = kit_user(client, app, "mr_f", "facilitator")
    ada_user, ada = kit_user(client, app, "ada")
    bob_user, bob = kit_user(client, app, "bob")
    other_user, other_teacher = kit_user(client, app, "mx_o", "teacher")
    room = teacher.post("/api/classes", json={"name": "3B"}).get_json()
    assert teacher.post(f"/api/classes/{room['id']}/members", json={"username": "ada"}).status_code == 201
    assert client.post(f"/api/classes/{room['id']}/members",
                       json={"username": "mr_f", "role": "facilitator"}).status_code == 201
    return {"class": room, "teacher": teacher, "facilitator": facilitator, "ada": ada, "bob": bob,
            "other_teacher": other_teacher, "ada_user": ada_user, "bob_user": bob_user,
            "facilitator_user": facilitator_user, "teacher_user": teacher_user, "other_user": other_user}


def test_teachers_and_facilitators_read_their_students_work_only(school):
    mine = project(school["ada"], "Ada's game")
    outside = project(school["bob"], "Bob's game")   # bob is not in the class
    for reader in ("teacher", "facilitator"):
        assert school[reader].get(f"/api/projects/{mine['id']}").status_code == 200
        assert school[reader].get(f"/api/projects/{outside['id']}").status_code == 404
        listed = school[reader].get(f"/api/classes/{school['class']['id']}/projects").get_json()["projects"]
        assert [item["title"] for item in listed] == ["Ada's game"]
    assert school["other_teacher"].get(f"/api/projects/{mine['id']}").status_code == 404
    assert school["ada"].get(f"/api/classes/{school['class']['id']}/projects").status_code == 404


def test_supervision_is_read_only(school):
    mine = project(school["ada"], "Ada's game")
    for reader in ("teacher", "facilitator"):
        assert school[reader].put(f"/api/projects/{mine['id']}", json={"title": "changed"}).status_code == 403
        assert school[reader].delete(f"/api/projects/{mine['id']}").status_code == 403
        assert school[reader].post(f"/api/projects/{mine['id']}/package", json={}).status_code == 403
    assert school["ada"].get(f"/api/projects/{mine['id']}").get_json()["title"] == "Ada's game"


def test_teachers_cannot_publish_their_students_bundles(app, school, client):
    mine = project(school["ada"], "Ada's game")
    bundle = school["ada"].post("/api/artifacts", json={"project_id": mine["id"], "kind": "store_bundle",
                                                        "name": "b", "metadata": {"publishable": True}}).get_json()
    client.put(f"/api/users/{school['teacher_user']['id']}", json={"role": "publisher"})
    teacher = student_client(app, "ms_t")
    profile = shared(app, "publish_profiles", {"name": "class store", "store_url": "https://store.school.test"})
    answer = teacher.post("/api/publish/review", json={"profile_id": profile["id"], "bundle_artifact_id": bundle["id"]})
    assert answer.status_code == 404 and answer.get_json()["reason"] == "bundle_not_found"


def test_only_administrators_add_teachers_and_facilitators(school):
    room = school["class"]["id"]
    assert school["teacher"].post(f"/api/classes/{room}/members",
                                  json={"username": "mx_o", "role": "teacher"}).status_code == 403
    assert school["teacher"].post(f"/api/classes/{room}/members",
                                  json={"username": "bob", "role": "facilitator"}).status_code == 403
    # a teacher-account cannot be slipped in as a "student" to gain read access either
    assert school["teacher"].post(f"/api/classes/{room}/members", json={"username": "mx_o"}).status_code == 403
    assert school["facilitator"].post(f"/api/classes/{room}/members", json={"username": "bob"}).status_code == 403
    assert school["ada"].post(f"/api/classes/{room}/members", json={"username": "bob"}).status_code == 403
    assert school["facilitator"].delete(f"/api/classes/{room}").status_code == 403
    assert school["other_teacher"].get(f"/api/classes/{room}").status_code == 404


def test_removing_a_student_ends_the_teachers_view(school):
    mine = project(school["ada"], "Ada's game")
    room = school["class"]["id"]
    assert school["teacher"].delete(f"/api/classes/{room}/members/{school['ada_user']['id']}").status_code == 200
    assert school["teacher"].get(f"/api/projects/{mine['id']}").status_code == 404
    assert school["teacher"].delete(
        f"/api/classes/{room}/members/{school['facilitator_user']['id']}").status_code == 403


def test_students_see_their_class_but_not_its_members(school):
    shown = school["ada"].get("/api/classes").get_json()["classes"]
    assert [item["name"] for item in shown] == ["3B"] and "members" not in shown[0]


# --- API tokens ---------------------------------------------------------------------

def token_for(browser, **body):
    response = browser.post("/auth/tokens", json=body)
    assert response.status_code == 201, response.get_json()
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


def test_token_scopes_are_enforced(app, client, anon):
    _, ada = kit_user(client, app, "ada")
    item = project(ada)
    read = token_for(ada, scopes=["read"])
    assert anon.get(f"/api/projects/{item['id']}", headers=read).status_code == 200
    denied = anon.put(f"/api/projects/{item['id']}", json={"title": "x"}, headers=read)
    assert denied.status_code == 403 and denied.get_json()["code"] == "insufficient_scope"
    assert anon.post(f"/api/projects/{item['id']}/package", json={}, headers=read).status_code == 403
    write = token_for(ada, scopes=["read", "write"])
    assert anon.put(f"/api/projects/{item['id']}", json={"title": "y"}, headers=write).status_code == 200
    assert anon.post(f"/api/projects/{item['id']}/package", json={}, headers=write).status_code == 403
    assert anon.post("/auth/tokens", json={"scopes": ["read", "write", "build"]}, headers=write).status_code == 400
    assert anon.post("/auth/password", json={"new_password": "x" * 12}, headers=write).status_code == 403
    admin_read = token_for(client, scopes=["read"])
    assert anon.get("/api/users", headers=admin_read).status_code == 403   # an admin's read token is not admin


def test_old_tokens_keep_full_access_and_expired_tokens_stop(app, client, anon):
    from prg32_construction_kit.auth import ApiToken
    from prg32_construction_kit.db import db

    headers = token_for(client, scopes=["read"], expires_in_days=1)
    assert anon.get("/api/projects", headers=headers).status_code == 200
    with app.app_context():
        row = db.session.scalars(db.select(ApiToken)).all()[-1]
        row.expires_at = "2000-01-01T00:00:00+00:00"
        legacy = token_for(client)
        db.session.commit()
    assert anon.get("/api/projects", headers=headers).status_code == 401
    with app.app_context():
        newest = db.session.scalars(db.select(ApiToken)).all()[-1]
        newest.scopes = None    # a token made before scopes existed
        db.session.commit()
    assert anon.get("/api/users", headers=legacy).status_code == 200


# --- sessions --------------------------------------------------------------------------

def test_password_change_ends_other_sessions_but_not_this_one(app, client):
    kit_user(client, app, "ada")
    laptop, phone = student_client(app, "ada"), student_client(app, "ada")
    assert laptop.post("/auth/password", json={"current_password": STUDENT_PASSWORD,
                                               "new_password": "a-new-password-1"}).status_code == 200
    assert laptop.get("/api/projects").status_code == 200
    assert phone.get("/api/projects").status_code == 401


def test_sign_out_everywhere(app, client):
    kit_user(client, app, "ada")
    laptop, phone = student_client(app, "ada"), student_client(app, "ada")
    assert phone.post("/auth/sessions/revoke", json={}).status_code == 200
    assert laptop.get("/api/projects").status_code == 401 and phone.get("/api/projects").status_code == 401


def test_administrators_end_a_users_sessions(app, client):
    ada_user, ada = kit_user(client, app, "ada")
    assert client.post(f"/api/users/{ada_user['id']}/sessions/revoke", json={}).status_code == 200
    assert ada.get("/api/projects").status_code == 401


def test_sessions_end_after_their_lifetime_however_active(app, client):
    _, ada = kit_user(client, app, "ada")
    with ada.session_transaction() as saved:
        saved["signed_in_at"] -= app.config["PERMANENT_SESSION_LIFETIME"] + 1
    assert ada.get("/api/projects").status_code == 401


def test_a_session_with_a_forged_epoch_is_rejected(app, client):
    _, ada = kit_user(client, app, "ada")
    with ada.session_transaction() as saved:
        saved["epoch"] = 99
    assert ada.get("/api/projects").status_code == 401


# --- deprovisioning ---------------------------------------------------------------------

def test_deactivation_ends_sessions_tokens_and_sign_in_and_keeps_items(app, client, anon):
    ada_user, ada = kit_user(client, app, "ada")
    item = project(ada, "Kept")
    headers = token_for(ada)
    assert client.post(f"/api/users/{ada_user['id']}/deactivate", json={}).get_json()["disabled"] is True
    assert ada.get("/api/projects").status_code == 401
    assert anon.get("/api/projects", headers=headers).status_code == 401
    assert anon.post("/auth/login", data={"username": "ada", "password": STUDENT_PASSWORD},
                     headers={"Accept": "application/json"}).status_code == 401
    assert client.get(f"/api/projects/{item['id']}").get_json()["title"] == "Kept"
    client.post(f"/api/users/{ada_user['id']}/reactivate", json={})
    assert student_client(app, "ada").get("/api/projects").status_code == 200
    assert anon.get("/api/projects", headers=headers).status_code == 401   # revoked tokens stay revoked
    actions = [event["action"] for event in client.get("/api/admin/audit").get_json()["events"]]
    assert "user_deactivate" in actions and "user_reactivate" in actions


def test_administrators_cannot_deactivate_themselves(client):
    me = client.get("/auth/me").get_json()["user"]
    assert client.post(f"/api/users/{me['id']}/deactivate", json={}).status_code == 400


def test_service_accounts_use_tokens_only(app, client, anon):
    service = make_student(client, "robot")
    client.put(f"/api/users/{service['id']}", json={"kit_role": "service"})
    response = anon.post("/auth/login", data={"username": "robot", "password": STUDENT_PASSWORD},
                         headers={"Accept": "application/json"})
    assert response.status_code == 401


# --- one browser, two accounts ------------------------------------------------------------

def test_a_window_opened_as_another_user_is_refused(app, client):
    ada_user, ada = kit_user(client, app, "ada")
    bob_user, _ = kit_user(client, app, "bob")
    response = ada.post("/api/projects", json={"title": "x"}, headers={"X-PRG32-User": str(bob_user["id"])})
    assert response.status_code == 409 and response.get_json()["code"] == "user_changed"
    assert ada.post("/api/projects", json={"title": "x"}, headers={"X-PRG32-User": str(ada_user["id"])}).status_code == 201


def test_account_classes_and_identity_pages(app, client):
    _, ada = kit_user(client, app, "ada")
    for page in ("/account", "/classes"):
        assert ada.get(page).status_code == 200
    assert ada.get("/admin/identity").status_code == 403
    page = client.get("/admin/identity").get_data(as_text=True)
    assert "/auth/oidc/SLUG/callback" in page
    assert "Sign out everywhere" in ada.get("/account").get_data(as_text=True)
