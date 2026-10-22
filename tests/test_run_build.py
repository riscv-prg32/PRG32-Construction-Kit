"""Run builds (run_build.py, ADR-0024): a cartridge for the IDE's simulator, nothing kept."""
from __future__ import annotations

import base64

import pytest
from sqlalchemy import func, select
from test_source_languages import fake_builder

from prg32_construction_kit.sample_data import default_blocks, starter_project

C_GAME = starter_project("c", "Run C")["game_json"]
ASM_GAME = starter_project("asm", "Run Asm")["game_json"]


def rows(app) -> dict[str, int]:
    from prg32_construction_kit.db import db

    with app.app_context():
        return {name: db.session.scalar(select(func.count()).select_from(table))
                for name, table in db.metadata.tables.items() if name not in ("auth_throttle", "audit_events")}


@pytest.fixture()
def builder(app, monkeypatch):
    """The PRG32 builder replaced by one that writes a small file as the cartridge."""
    commands: list[list[str]] = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    monkeypatch.setattr("prg32_construction_kit.run_build.toolchain_present", lambda _command: True)
    return commands


@pytest.mark.parametrize("payload", [
    {"title": "Run Blocks", "blocks_json": default_blocks()},
    {"title": "Run C", "game_json": C_GAME},
    {"title": "Run Asm", "game_json": ASM_GAME},
])
def test_every_project_type_runs_and_nothing_is_kept(app, client, builder, payload):
    project = client.post("/api/projects", json=payload).get_json()
    before = rows(app)
    answer = client.post(f"/api/projects/{project['id']}/run", json={})
    assert answer.status_code == 200, answer.get_json()
    body = answer.get_json()
    assert body["ok"] and base64.b64decode(body["cartridge"]) == b"PRG32-test"
    assert len(builder) == 1 and "qemu" in builder[0]          # one build, for the browser core's target
    assert body["debug"]["source"]["language"] == ("asm" if "Asm" in payload["title"] else "c")
    assert body["debug"]["cartridge"]["project_id"] == project["id"]
    assert rows(app) == before, "a run build stored something"
    leftovers = [path for path in app.config["BUILD_ROOT"].iterdir() if path.name.startswith("build_")]
    assert leftovers == []


def test_guests_run_their_own_game_and_nothing_is_kept(app, anon, builder):
    before = rows(app)
    for game in ({"title": "Guest Blocks", "blocks_json": default_blocks()}, {"title": "Run C", "game_json": C_GAME},
                 {"title": "Run Asm", "game_json": ASM_GAME}):
        answer = anon.post("/api/guest/run", json={"project": game})
        assert answer.status_code == 200, answer.get_json()
        assert answer.get_json()["cartridge"]
    assert rows(app) == before


def test_guest_runs_are_limited_per_address(app, anon, builder):
    app.config["THROTTLE_LIMITS"] = {"guest_run": (2, 3600)}
    game = {"project": {"title": "Again", "blocks_json": default_blocks()}}
    answers = [anon.post("/api/guest/run", json=game).status_code for _ in range(3)]
    assert answers == [200, 200, 429]


def test_unsafe_source_is_refused_before_any_build(app, anon, builder):
    bad = {"source_mode": "c", "source_c": "#include <stdio.h>\nvoid x_init(void){}\n"}
    assert anon.post("/api/guest/run", json={"project": {"title": "x", "game_json": bad}}).status_code == 400
    assert builder == []


def test_without_a_toolchain_the_answer_says_so(app, client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.run_build.toolchain_present", lambda _command: False)
    project = client.post("/api/projects", json={"title": "No Tools", "blocks_json": default_blocks()}).get_json()
    answer = client.post(f"/api/projects/{project['id']}/run", json={})
    assert answer.status_code == 503 and answer.get_json()["code"] == "no_toolchain"


def test_runs_need_a_readable_project_and_a_sign_in(client, anon):
    assert client.post("/api/projects/nope/run", json={}).status_code == 404
    assert anon.post("/api/projects/nope/run", json={}).status_code == 401


def test_the_run_cartridge_is_the_compiled_one(app, client):
    """With the real PRG32 toolchain: Run builds exactly the qemu cartridge Compile makes."""
    from prg32_construction_kit.build_check import toolchain_present

    if not toolchain_present(app.config["PRG32_BUILD_COMMAND"]):
        pytest.skip("the PRG32 toolchain is not installed")
    for payload in ({"title": "Same Blocks", "blocks_json": default_blocks()}, {"title": "Run C", "game_json": C_GAME}):
        project = client.post("/api/projects", json=payload).get_json()
        run = client.post(f"/api/projects/{project['id']}/run", json={}).get_json()
        assert run["ok"], run["log"]
        built = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
        cartridge = client.get(f"/api/artifacts/{built['cartridge_artifacts'][0]['id']}/download").data
        assert base64.b64decode(run["cartridge"]) == cartridge
