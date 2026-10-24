"""New Project: a starting point in Blocks, C, assembly or PRG32 Python (sample_data.starter_project, GET /api/starters)."""
from __future__ import annotations

import pytest

from prg32_construction_kit.sample_data import STARTER_KINDS, default_blocks, starter_project
from prg32_construction_kit.source_project import validate_asm_source, validate_c_source


@pytest.mark.parametrize("title", ["My PRG32 Game", "Space Race 2", "3D!"])
def test_c_and_assembly_starters_pass_the_handwritten_checks(title):
    c = starter_project("c", title)["game_json"]
    asm = starter_project("asm", title)["game_json"]
    assert c["source_mode"] == "c" and asm["source_mode"] == "asm"
    assert validate_c_source(c["source_c"], title) == validate_asm_source(asm["source_asm"], title)
    for source in (c["source_c"], asm["source_asm"]):
        assert "this is your own" in source and "regenerate this file" not in source
        assert "HOW TO READ THIS FILE" in source        # the teaching comments stay


def test_a_blocks_starter_is_the_starter_game():
    assert starter_project("blocks", "x") == {"blocks_json": default_blocks(), "game_json": {}}


def test_the_starters_api_answers_everyone_the_same(client, anon):
    for kind in STARTER_KINDS:
        mine = client.get(f"/api/starters/{kind}?title=Rocket").get_json()
        assert anon.get(f"/api/starters/{kind}?title=Rocket").get_json() == mine
    assert client.get("/api/starters/cobol").status_code == 404
    assert anon.post("/api/starters/c").status_code in (401, 405)


@pytest.mark.parametrize("kind", ["c", "asm"])
def test_a_starter_project_saves_and_generates(client, kind):
    start = client.get(f"/api/starters/{kind}?title=Rocket").get_json()
    project = client.post("/api/projects", json={"title": "Rocket", **start}).get_json()
    answer = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": kind})
    assert answer.status_code == 200, answer.get_json()


def test_a_python_starter_is_prg32_python_that_compiles():
    from prg32_construction_kit.python_project import LANGUAGE_VERSION, python_to_ir

    game = starter_project("python", "Rocket")["game_json"]
    assert game["source_mode"] == "python" and game["python_language_version"] == LANGUAGE_VERSION
    assert python_to_ir(game["source_python"], {"title": "Rocket"})["entry_prefix"] == "rocket"


def test_a_python_starter_saves_and_generates_c_and_assembly(client):
    start = client.get("/api/starters/python?title=Rocket").get_json()
    project = client.post("/api/projects", json={"title": "Rocket", **start}).get_json()
    answer = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"})
    assert answer.status_code == 200, answer.get_json()
    body = answer.get_json()
    assert "void rocket_update(void)" in body["c_source"] and "rocket_update:" in body["asm_source"]
    # The IR is shown, never stored over the Python source.
    assert client.get(f"/api/projects/{project['id']}").get_json()["game_json"]["source_python"] == start["game_json"]["source_python"]
