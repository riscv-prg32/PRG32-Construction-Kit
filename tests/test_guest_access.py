"""The guest workspace on the server (ADR-0023): which pages open without an account, and the
guest API that generates code and previews sound without storing anything."""
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from prg32_construction_kit.sample_data import default_blocks

GUEST_PAGES = ("/", "/sprites", "/player", "/audio-studio", "/ide/guest-abc")
CLOSED = [("GET", "/api/projects"), ("POST", "/api/projects"), ("GET", "/api/sprites"), ("GET", "/api/artifacts"),
          ("POST", "/api/projects/x/package"), ("POST", "/api/projects/x/check"), ("POST", "/api/publish"),
          ("GET", "/api/classes"), ("GET", "/api/cloud"), ("GET", "/artifacts"), ("GET", "/publish"),
          ("GET", "/classes"), ("GET", "/account"), ("GET", "/admin/settings")]


def rows(app) -> dict[str, int]:
    from prg32_construction_kit.db import db

    with app.app_context():
        return {name: db.session.scalar(select(func.count()).select_from(table))
                # Logs, not the guest's work: the activity log notes only that a request happened
                # (route pattern and outcome, under a one-day pseudonym; tests/test_mail_activity_statistics.py).
                for name, table in db.metadata.tables.items()
                if name not in ("auth_throttle", "audit_events", "activity_events", "activity_salts")}


def test_the_kit_opens_without_an_account(anon):
    for path in GUEST_PAGES:
        page = anon.get(path)
        assert page.status_code == 200, path
        html = page.get_data(as_text=True)
        assert '<meta name="prg32-guest" content="1">' in html and "guest_api.js" in html, path
    discovery = anon.get("/.well-known/prg32-construction-kit.json").get_json()
    assert discovery["guest_workspace"] is True


@pytest.mark.parametrize("method,path", CLOSED)
def test_everything_else_still_needs_a_sign_in(anon, method, path):
    answer = anon.open(path, method=method, json={} if method == "POST" else None)
    assert answer.status_code in (302, 401), (method, path, answer.status_code)


def test_the_classic_editor_address_opens_the_ide(client, anon):
    for browser in (client, anon):
        answer = browser.get("/projects/guest-abc")
        assert answer.status_code == 302 and answer.headers["Location"].endswith("/ide/guest-abc")
        answer = browser.get("/audio-studio/guest-abc")
        assert answer.status_code == 302 and answer.headers["Location"].endswith("/ide/guest-abc#sound")


def test_signed_in_pages_do_not_use_the_guest_workspace(client):
    html = client.get("/").get_data(as_text=True)
    assert '<meta name="prg32-guest" content="">' in html and "guest_api.js" not in html


@pytest.mark.parametrize("setting,value", [("LOGIN_REQUIRED", True), ("PRG32_GUEST_MODE", "off")])
def test_the_settings_close_the_guest_workspace(app, anon, setting, value):
    app.config[setting] = value
    for path in GUEST_PAGES:
        assert anon.get(path).status_code == 302, path
    assert anon.post("/api/guest/convert", json={"project": {"blocks_json": default_blocks()}}).status_code == 401


def test_guest_code_is_the_same_as_an_accounts_and_nothing_is_kept(app, client, anon):
    project = client.post("/api/projects", json={"title": "Same Game", "blocks_json": default_blocks()}).get_json()
    mine = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"}).get_json()
    before = rows(app)
    guest = anon.post("/api/guest/convert", json={"project": {"title": "Same Game", "blocks_json": default_blocks()},
                                                  "source_language": "both"})
    assert guest.status_code == 200, guest.get_json()
    body = guest.get_json()
    assert body["c_source"] == mine["c_source"] and body["asm_source"] == mine["asm_source"]
    assert body["game_ir"] == mine["game_ir"]
    assert rows(app) == before, "the guest API stored something"


def test_guest_c_and_assembly_are_validated(anon):
    unsafe = {"source_mode": "c", "source_c": "#include <stdio.h>\nint main(void){return 0;}\n"}
    answer = anon.post("/api/guest/convert", json={"project": {"title": "Bad", "game_json": unsafe}})
    assert answer.status_code == 400
    answer = anon.post("/api/guest/convert", json={"project": {"title": "Bad", "game_json": {
        "source_mode": "asm", "source_asm": '.incbin "/etc/passwd"\n'}}})
    assert answer.status_code == 400


def test_guest_sound_and_sprites(app, anon):
    before = rows(app)
    audio = anon.post("/api/guest/audio", json={})
    assert audio.status_code == 200 and audio.get_json()["document"]["voices"]
    document = audio.get_json()["document"]
    preview = anon.post("/api/guest/audio/preview", json={"document": document, "muted": [1]})
    assert preview.status_code == 200 and preview.data[:4] == b"AUD0"
    with_sample = dict(document, samples=[{"name": "drum", "artifact_id": "x"}])
    assert anon.post("/api/guest/audio", json={"document": with_sample}).status_code == 400
    sprite = anon.post("/api/guest/sprites/convert", json={"sprite": {"name": "hero", "width": 2, "height": 1,
                                                                       "pixels": [["#ff0000", "#00ff00"]]}})
    assert sprite.status_code == 200 and "hero_pixels" in sprite.get_json()["c_source"]
    assert rows(app) == before


def test_guests_can_copy_an_example(app, anon):
    slug = anon.get("/api/examples").get_json()["examples"][0]["slug"]
    before = rows(app)
    example = anon.get(f"/api/guest/examples/{slug}")
    assert example.status_code == 200 and example.get_json()["project"]["blocks_json"]
    assert rows(app) == before


def test_the_guest_api_is_limited_per_address(app, anon):
    app.config["THROTTLE_LIMITS"] = {"guest_api": (3, 3600)}
    answers = [anon.post("/api/guest/audio", json={}).status_code for _ in range(5)]
    assert answers[:3] == [200, 200, 200] and answers[3:] == [429, 429]
