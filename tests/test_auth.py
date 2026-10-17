from __future__ import annotations

import io
import sqlite3

from conftest import ADMIN_PASSWORD, make_app
from prg32_construction_kit.sample_data import default_blocks

STUDENT_PASSWORD = "student-password-1"


def make_student(client, name: str, role: str = "user") -> dict:
    response = client.post("/api/users", json={"username": name, "email": f"{name}@school.test",
                                               "password": STUDENT_PASSWORD, "role": role})
    assert response.status_code == 201, response.get_json()
    return response.get_json()


def student_client(app, name: str):
    return app.test_client(login=(name, STUDENT_PASSWORD))


def test_signing_in_is_required(anon):
    assert anon.get("/api/projects").status_code == 401
    page = anon.get("/sprites")
    assert page.status_code == 302 and "/auth/login?next=/sprites" in page.headers["Location"]
    # Sign-in pages, static files, docs and discovery stay open.
    assert anon.get("/auth/login").status_code == 200
    assert anon.get("/static/js/app.js").status_code == 200
    assert anon.get("/.well-known/prg32-construction-kit.json").get_json()["auth"]["required"] is True


def test_login_logout_and_cookie(app, anon):
    bad = anon.post("/auth/login", data={"username": "admin", "password": "wrong"})
    assert bad.status_code == 401
    good = anon.post("/auth/login", data={"username": "admin@localhost", "password": ADMIN_PASSWORD, "next": "/sprites"})
    assert good.status_code == 302 and good.headers["Location"] == "/sprites"
    cookie = good.headers["Set-Cookie"]
    assert cookie.startswith("prg32_kit_session=") and "HttpOnly" in cookie and "SameSite=Lax" in cookie
    assert anon.get("/auth/me").get_json()["user"]["role"] == "admin"
    anon.post("/auth/logout")
    assert anon.get("/api/projects").status_code == 401


def test_login_never_redirects_to_another_site(anon):
    response = anon.post("/auth/login", data={"username": "admin", "password": ADMIN_PASSWORD, "next": "//evil.test/"})
    assert response.headers["Location"] == "/"


def test_secret_key_is_generated_once_and_kept(tmp_path):
    first = make_app(tmp_path).config["SECRET_KEY"]
    assert len(first) == 64 and (tmp_path / "secret_key").read_text() == first
    assert make_app(tmp_path).config["SECRET_KEY"] == first


def test_email_registration_creates_a_user(app, anon):
    assert anon.post("/auth/register", data={"email": "new@school.test"}).status_code == 200
    token = app.extensions["prg32_last_registration"]["token"]
    short = anon.post("/auth/register/complete", data={"token": token, "password": "short", "password_confirm": "short"})
    assert short.status_code == 400
    done = anon.post("/auth/register/complete", data={"token": token, "password": STUDENT_PASSWORD,
                                                      "password_confirm": STUDENT_PASSWORD})
    assert done.status_code == 302
    me = anon.get("/auth/me").get_json()["user"]
    assert me["email"] == "new@school.test" and me["role"] == "user"
    # The link works only once.
    again = anon.post("/auth/register/complete", data={"token": token, "password": STUDENT_PASSWORD})
    assert again.status_code == 400


def test_registration_can_be_closed(tmp_path):
    app = make_app(tmp_path, ALLOW_REGISTRATION=False)
    response = app.test_client(login=None).post("/auth/register", data={"email": "x@school.test"})
    assert response.status_code == 400


def test_students_only_see_their_own_projects(app, client):
    make_student(client, "ada")
    make_student(client, "bob")
    ada, bob = student_client(app, "ada"), student_client(app, "bob")
    project = ada.post("/api/projects", json={"title": "Ada's game", "blocks_json": default_blocks()}).get_json()
    assert project["can_edit"] is True

    assert project["id"] in [item["id"] for item in ada.get("/api/projects").get_json()["projects"]]
    assert project["id"] not in [item["id"] for item in bob.get("/api/projects").get_json()["projects"]]
    for method in ("get", "put", "delete"):
        assert getattr(bob, method)(f"/api/projects/{project['id']}", json={}).status_code == 404
    assert bob.post(f"/api/projects/{project['id']}/convert", json={}).status_code == 404
    assert bob.get(f"/api/projects/{project['id']}/export").status_code == 404
    # Teachers (admins) see and change everything.
    assert client.put(f"/api/projects/{project['id']}", json={"description": "checked"}).status_code == 200


def test_students_cannot_take_or_give_away_ownership(app, client):
    bob_id = make_student(client, "bob")["id"]
    make_student(client, "ada")
    ada = student_client(app, "ada")
    project = ada.post("/api/projects", json={"title": "Mine", "owner_id": bob_id}).get_json()
    assert project["owner_id"] != bob_id
    changed = ada.put(f"/api/projects/{project['id']}", json={"owner_id": bob_id}).get_json()
    assert changed["owner_id"] == project["owner_id"]


def test_shared_classroom_projects_are_read_only_for_students(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    shared = [item for item in ada.get("/api/projects").get_json()["projects"] if item["owner_id"] is None]
    assert shared, "the starter games are shared with everyone"
    assert shared[0]["can_edit"] is False
    assert ada.put(f"/api/projects/{shared[0]['id']}", json={"title": "mine now"}).status_code == 403
    assert ada.post(f"/api/projects/{shared[0]['id']}/convert", json={}).status_code == 403
    copy = ada.post("/api/examples/pong/import", json={}).get_json()
    assert copy["can_edit"] is True and copy["owner_id"] is not None


def test_students_cannot_point_artifacts_at_files(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    target = app.config["BUILD_ROOT"] / "someone-elses-build.prg32"
    target.write_bytes(b"secret cartridge")
    artifact = ada.post("/api/artifacts", json={"name": "x", "path": str(target)}).get_json()
    assert "path" not in artifact
    assert ada.get(f"/api/artifacts/{artifact['id']}/download").data == b""


def test_students_cannot_download_other_students_files(app, client):
    make_student(client, "ada")
    make_student(client, "bob")
    ada, bob = student_client(app, "ada"), student_client(app, "bob")
    uploaded = ada.post("/api/artifacts/upload", data={"file": (io.BytesIO(b"mine"), "game.prg32")},
                        content_type="multipart/form-data").get_json()
    assert ada.get(f"/api/artifacts/{uploaded['id']}/download").data == b"mine"
    assert bob.get(f"/api/artifacts/{uploaded['id']}/download").status_code == 404


def test_cross_site_form_posts_are_blocked(app, client):
    browser = app.test_client()
    browser.environ_base.pop("HTTP_X_PRG32_KIT")
    # A plain form post from another web site: no JSON, no X-PRG32-Kit header.
    assert browser.post("/api/projects", data={"title": "csrf"}).status_code == 403
    assert browser.post("/api/projects", json={"title": "json is fine"}).status_code == 201


def test_api_tokens_work_and_can_be_revoked(app, client, anon):
    created = client.post("/auth/tokens", json={"label": "script"}).get_json()
    assert created["token"].startswith("prg32_")
    headers = {"Authorization": f"Bearer {created['token']}"}
    assert anon.get("/api/projects", headers=headers).status_code == 200
    # Scripts using a token do not need the browser-only header.
    assert anon.post("/api/projects", data={"title": "from script"}, headers=headers).status_code == 201
    listed = client.get("/auth/tokens").get_json()["tokens"]
    assert [token["label"] for token in listed] == ["script"] and "token" not in listed[0]
    assert client.delete(f"/auth/tokens/{created['id']}").get_json()["ok"] is True
    assert anon.get("/api/projects", headers=headers).status_code == 401


def test_only_admins_manage_users(app, client):
    student = make_student(client, "ada")
    ada = student_client(app, "ada")
    assert ada.get("/api/users").status_code == 403
    assert ada.get("/admin/users").status_code == 403
    assert client.put(f"/api/users/{student['id']}", json={"role": "publisher", "groups": ["class-3b"]}).get_json()["groups"] == ["class-3b"]
    assert ada.get("/auth/me").get_json()["user"]["role"] == "publisher"
    assert client.delete(f"/api/users/{student['id']}").get_json()["deleted"] is True
    assert ada.get("/api/projects").status_code == 401  # a deleted account is signed out


def test_admins_cannot_lock_themselves_out(client):
    me = client.get("/auth/me").get_json()["user"]
    assert client.put(f"/api/users/{me['id']}", json={"role": "user"}).status_code == 400
    assert client.delete(f"/api/users/{me['id']}").status_code == 400
    assert client.post("/api/users", json={"username": "x", "email": "bad", "password": STUDENT_PASSWORD}).status_code == 400
    assert client.post("/api/users", json={"username": "admin", "email": "a@b.test"}).status_code == 400


def test_password_change(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    assert ada.post("/auth/password", json={"current_password": "wrong", "new_password": "another-pass-9"}).status_code == 400
    assert ada.post("/auth/password", json={"current_password": STUDENT_PASSWORD, "new_password": "another-pass-9"}).status_code == 200
    fresh = app.test_client(login=None)
    assert fresh.post("/auth/login", data={"username": "ada", "password": "another-pass-9"}).status_code == 302


def test_old_databases_get_an_owner_column(tmp_path):
    db_path = tmp_path / "test.sqlite"
    with sqlite3.connect(db_path) as connection:
        connection.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,"
                           " title TEXT NOT NULL, description TEXT NOT NULL, author TEXT NOT NULL, tags TEXT NOT NULL,"
                           " blocks_json TEXT NOT NULL, game_json TEXT NOT NULL)")
        connection.execute("INSERT INTO projects VALUES ('project_old', 'a', 'a', 'Old game', '', 'Me', '[]', '{}', '{}')")
    app = make_app(tmp_path)
    old = app.test_client().get("/api/projects/project_old").get_json()
    assert old["title"] == "Old game" and old["owner_id"] is None


def test_a_window_opened_as_another_user_is_stopped(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    ada_id = ada.get("/auth/me").get_json()["user"]["id"]
    admin_id = client.get("/auth/me").get_json()["user"]["id"]
    # This window was opened as the admin, but the browser now holds Ada's sign-in.
    stale = ada.post("/api/projects", json={"title": "Wrong account"}, headers={"X-PRG32-User": str(admin_id)})
    assert stale.status_code == 409
    assert stale.get_json()["code"] == "user_changed"
    assert ada.get("/api/projects", headers={"X-PRG32-User": str(admin_id)}).status_code == 409
    assert ada.post("/api/projects", json={"title": "Mine"}, headers={"X-PRG32-User": str(ada_id)}).status_code == 201
    assert ada.post("/api/projects", json={"title": "Script"}).status_code == 201  # scripts send no header


def test_pages_tell_the_browser_which_account_they_were_opened_as(app, client):
    me = client.get("/auth/me").get_json()["user"]
    assert f'<meta name="prg32-user" content="{me["id"]}">' in client.get("/").get_data(as_text=True)


def test_service_worker_never_caches_signed_in_pages(client):
    worker = client.get("/static/service-worker.js").get_data(as_text=True)
    shell = worker.split("const APP_SHELL = [", 1)[1].split("];", 1)[0]
    assert all(line.strip().startswith("'/static/") for line in shell.strip().splitlines())
    assert "startsWith('/static/')" in worker
