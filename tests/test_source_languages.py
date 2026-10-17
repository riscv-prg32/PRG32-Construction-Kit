"""Generate and compile C, RISC-V assembly, or both, through the API."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from prg32_construction_kit.sample_data import default_blocks


def make_project(client, title="Two Languages"):
    return client.post("/api/projects", json={"title": title, "blocks_json": default_blocks()}).get_json()


def fake_builder(commands):
    def fake_run(command, **_kwargs):
        commands.append(command)
        with open(command[command.index("--out") + 1], "wb") as cartridge:
            cartridge.write(b"PRG32-test")
        return SimpleNamespace(returncode=0, stdout="built\n", stderr="")
    return fake_run


def built_source(command: list[str]) -> str:
    """The name of the source file handed to the PRG32 builder."""
    return next(Path(arg).name for arg in command if arg.endswith(("game.c", "game.S")))


def test_convert_defaults_to_c_only(client):
    project = make_project(client)
    data = client.post(f"/api/projects/{project['id']}/convert", json={}).get_json()
    assert data["source_language"] == "c"
    assert "c_source" in data and "asm_source" not in data
    assert [artifact["kind"] for artifact in data["artifacts"]] == ["c_source"]


def test_convert_can_make_assembly_only(client):
    project = make_project(client)
    data = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "asm"}).get_json()
    assert "c_source" not in data
    assert "    .globl two_languages_init" in data["asm_source"]
    assert data["artifact"]["kind"] == "asm_source"
    assert data["artifact"]["content_type"] == "text/x-asm"
    assert data["artifact"]["name"] == "Two Languages generated assembly"
    stored = client.get(f"/api/artifacts/{data['artifact']['id']}").get_json()
    assert stored["text_content"] == data["asm_source"]


def test_convert_can_make_both_sources(client):
    project = make_project(client)
    data = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"}).get_json()
    assert "void two_languages_init(void)" in data["c_source"]
    assert "two_languages_init:" in data["asm_source"]
    assert [artifact["kind"] for artifact in data["artifacts"]] == ["c_source", "asm_source"]
    assert data["asm_artifact"]["id"] == data["artifacts"][1]["id"]
    listed = client.get("/api/artifacts?kind=asm_source").get_json()
    assert any(item["id"] == data["asm_artifact"]["id"] for item in listed["artifacts"])


@pytest.mark.parametrize("language", ["python", "", None, ["c"]])
def test_unknown_source_languages_are_rejected(client, language):
    project = make_project(client)
    response = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": language})
    assert response.status_code == 400
    assert "source_language" in response.get_json()["error"]


def test_advanced_c_projects_have_no_generated_assembly(client):
    source = ('#include "prg32.h"\nvoid own_c_init(void) {}\n'
              'void own_c_update(void) {}\nvoid own_c_draw(void) {}\n')
    project = client.post("/api/projects", json={
        "title": "Own C", "game_json": {"source_mode": "c", "source_c": source}}).get_json()
    for route in ("convert", "package"):
        response = client.post(f"/api/projects/{project['id']}/{route}", json={"source_language": "asm"})
        assert response.status_code == 400
        assert "Assembly is generated from Blocks" in response.get_json()["error"]


def test_package_compiles_the_assembly_when_asked(client, monkeypatch):
    commands = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    project = make_project(client)
    response = client.post(f"/api/projects/{project['id']}/package", json={"source_language": "asm"})
    assert response.status_code == 200
    result = response.get_json()
    assert result["c_artifact"] is None
    assert result["asm_artifact"]["kind"] == "asm_source"
    assert result["build"]["c_artifact_id"] is None
    assert result["build"]["metadata"]["built_from"] == "asm"
    assert result["build"]["metadata"]["asm_artifact_id"] == result["asm_artifact"]["id"]
    assert {built_source(command) for command in commands} == {"game.S"}
    with zipfile.ZipFile(io.BytesIO(client.get(
            f"/api/artifacts/{result['bundle_artifact']['id']}/download").data)) as bundle:
        assert "source/game.S" in bundle.namelist() and "source/game.c" not in bundle.namelist()
        assert bundle.read("source/game.S").decode() == result["asm_artifact"]["text_content"]


def test_package_with_both_compiles_c_and_bundles_both(client, monkeypatch):
    commands = []
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder(commands))
    project = make_project(client)
    result = client.post(f"/api/projects/{project['id']}/package", json={"source_language": "both"}).get_json()
    assert result["build"]["metadata"]["built_from"] == "c"
    assert result["c_artifact"]["kind"] == "c_source" and result["asm_artifact"]["kind"] == "asm_source"
    assert {built_source(command) for command in commands} == {"game.c"}
    with zipfile.ZipFile(io.BytesIO(client.get(
            f"/api/artifacts/{result['bundle_artifact']['id']}/download").data)) as bundle:
        assert {"source/game.c", "source/game.S"} <= set(bundle.namelist())
