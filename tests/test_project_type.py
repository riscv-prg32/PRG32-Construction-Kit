"""A project's type is fixed; Blocks convert to C or assembly once, and never back (ADR-0024)."""
from __future__ import annotations

import io
import zipfile

import pytest

from prg32_construction_kit.sample_data import default_blocks, starter_project
from prg32_construction_kit.source_project import validate_asm_source, validate_c_source


def make(client, kind, title="Fixed Type"):
    start = starter_project(kind, title)
    return client.post("/api/projects", json={"title": title, **start}).get_json()


@pytest.mark.parametrize("kind,other", [("blocks", "c"), ("blocks", "asm"), ("c", "asm"), ("asm", "c"),
                                        ("c", "blocks"), ("asm", "blocks")])
def test_a_save_never_changes_the_type(client, kind, other):
    project = make(client, kind)
    other_game = starter_project(other, "Fixed Type")["game_json"] if other != "blocks" else {"abi": "ir"}
    answer = client.put(f"/api/projects/{project['id']}", json={"game_json": other_game})
    assert answer.status_code == 409 and answer.get_json()["code"] == "type_locked"
    assert answer.get_json()["project_type"] == kind
    # A save of the same type is fine.
    same = starter_project(kind, "Fixed Type")["game_json"] if kind != "blocks" else {"abi": "ir"}
    assert client.put(f"/api/projects/{project['id']}", json={"game_json": same}).status_code == 200


@pytest.mark.parametrize("language,check", [("c", validate_c_source), ("asm", validate_asm_source)])
def test_blocks_convert_once_and_the_blocks_stay_in_history(client, language, check):
    project = make(client, "blocks", "Space Race")
    answer = client.post(f"/api/projects/{project['id']}/convert_to", json={"language": language})
    assert answer.status_code == 200, answer.get_json()
    game = answer.get_json()["game_json"]
    assert game["source_mode"] == language
    source = game["source_c" if language == "c" else "source_asm"]
    check(source, "Space Race")
    assert "this is your own" in source
    # Never back, and not again.
    assert client.post(f"/api/projects/{project['id']}/convert_to", json={"language": "c"}).status_code == 409
    back = client.put(f"/api/projects/{project['id']}", json={"game_json": {"abi": "ir"}})
    assert back.get_json()["code"] == "type_locked"
    # The Blocks version is in History: it can be downloaded, not restored over the converted project.
    history = client.get(f"/api/projects/{project['id']}/revisions").get_json()["revisions"]
    blocks_version = next(rev for rev in history if rev["reason"] == "convert")
    archive = zipfile.ZipFile(io.BytesIO(client.get(
        f"/api/projects/{project['id']}/revisions/{blocks_version['id']}/archive").data))
    assert "src/blocks.json" in archive.namelist()
    restore = client.post(f"/api/projects/{project['id']}/revisions/{blocks_version['id']}/restore")
    assert restore.status_code == 409 and restore.get_json()["code"] == "type_locked"


def test_conversion_checks_its_input(app, client):
    project = make(client, "blocks")
    assert client.post(f"/api/projects/{project['id']}/convert_to", json={"language": "python"}).status_code == 400
    assert client.post("/api/projects/nope/convert_to", json={"language": "c"}).status_code == 404
    stale = client.post(f"/api/projects/{project['id']}/convert_to", json={"language": "c", "expected_version": 99})
    assert stale.status_code == 409 and stale.get_json()["code"] == "version_conflict"


def test_guests_convert_in_their_browser(anon):
    answer = anon.post("/api/guest/convert_to", json={"project": {"title": "Guest Race", "blocks_json": default_blocks()},
                                                       "language": "asm"})
    assert answer.status_code == 200
    validate_asm_source(answer.get_json()["game_json"]["source_asm"], "Guest Race")
