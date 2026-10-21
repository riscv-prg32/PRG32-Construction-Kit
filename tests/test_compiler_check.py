"""The IDE's compiler check (ADR-0014): POST /api/projects/<id>/check.

The saved, validated source is compiled and linked exactly as a build does, in the build
sandbox, in a private build_<id>/ folder that is removed afterwards; the compiler's messages
come back for the Problems panel. It never compiles text the browser sends.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from test_auth import make_student, student_client

BROKEN_C = ("#include \"prg32.h\"\nvoid broken_init(void) {}\n"
            "void broken_update(void) { int score = 0; score = score + missing_value; }\nvoid broken_draw(void) {}\n")
FINE_ASM = """    .section .text
    .globl fine_init
    .globl fine_update
    .globl fine_draw
fine_init:
    ret
fine_update:
    ret
fine_draw:
    ret
"""


def c_project(client, title="Broken", source=BROKEN_C):
    game = {"source_mode": "c", "source_c": source, "required_features": []}
    return client.post("/api/projects", json={"title": title, "game_json": game}).get_json()


class Compiler:
    """Stands in for the PRG32 builder: records the source it was given, answers like gcc."""

    def __init__(self, fails=True):
        self.fails, self.sources, self.folders = fails, [], []

    def __call__(self, command, **_kwargs):
        source = next(Path(arg) for arg in command if arg.endswith(("game.c", "game.S")))
        self.sources.append((source.name, source.read_text()))
        self.folders.append(source.parent)
        if self.fails:
            return SimpleNamespace(returncode=1, stdout="",
                                   stderr=f"{source}:3:59: error: 'missing_value' undeclared (first use in this function)\n")
        Path(command[command.index("--out") + 1]).write_bytes(b"PRG2" + bytes(60))
        return SimpleNamespace(returncode=0, stdout="", stderr="")


@pytest.fixture()
def compiler(monkeypatch):
    fake = Compiler()
    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    return fake


def test_the_saved_source_is_compiled_and_nothing_is_kept(app, client, compiler):
    project = c_project(client)
    answer = client.post(f"/api/projects/{project['id']}/check", json={"source_language": "c"}).get_json()
    assert answer["available"] and answer["ok"] is False and answer["source_language"] == "c"
    assert "<build>/game.c:3:59: error: 'missing_value' undeclared" in answer["log"]
    assert str(compiler.folders[0]) not in answer["log"]                     # no server paths
    assert compiler.sources == [("game.c", BROKEN_C)]
    assert compiler.folders[0].name.startswith("build_") and not compiler.folders[0].exists()
    assert client.get("/api/artifacts").get_json()["artifacts"] == []         # nothing stored
    assert client.get("/api/builds").get_json()["builds"] == []


def test_assembly_and_generated_sources_are_checked_too(app, client, compiler):
    from prg32_construction_kit.sample_data import default_blocks

    compiler.fails = False
    asm = client.post("/api/projects", json={"title": "Fine", "game_json": {"source_mode": "asm", "source_asm": FINE_ASM,
                                                                             "required_features": []}}).get_json()
    assert client.post(f"/api/projects/{asm['id']}/check", json={}).get_json()["ok"] is True
    blocks = client.post("/api/projects", json={"title": "Blocks", "blocks_json": default_blocks()}).get_json()
    for language in ("c", "asm"):
        assert client.post(f"/api/projects/{blocks['id']}/check", json={"source_language": language}).get_json()["ok"]
    assert [name for name, _ in compiler.sources] == ["game.S", "game.c", "game.S"]
    assert client.post(f"/api/projects/{blocks['id']}/check", json={"source_language": "both"}).status_code == 400


def test_source_the_kit_refuses_is_never_compiled(app, client, compiler):
    game = {"source_mode": "c", "source_c": "#include <stdio.h>\nvoid x_init(void){}\n", "required_features": []}
    project = client.post("/api/projects", json={"title": "X", "game_json": game}).get_json()
    response = client.post(f"/api/projects/{project['id']}/check", json={})
    assert response.status_code == 400 and compiler.sources == []


def test_without_the_toolchain_the_check_says_so(app, client, monkeypatch):
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: False)
    project = c_project(client)
    assert client.post(f"/api/projects/{project['id']}/check", json={}).get_json() == {"available": False,
                                                                                         "source_language": "c"}


def test_only_the_owner_checks_and_a_token_needs_the_build_scope(app, client, compiler):
    make_student(client, "ada")
    make_student(client, "bob")
    ada, bob = student_client(app, "ada"), student_client(app, "bob")
    project = c_project(ada)
    assert bob.post(f"/api/projects/{project['id']}/check", json={}).status_code == 404
    write = ada.post("/auth/tokens", json={"scopes": ["read", "write"]}).get_json()["token"]
    build = ada.post("/auth/tokens", json={"scopes": ["read", "build"]}).get_json()["token"]
    anon = app.test_client(login=None)
    denied = anon.post(f"/api/projects/{project['id']}/check", json={}, headers={"Authorization": f"Bearer {write}"})
    assert denied.status_code == 403 and denied.get_json()["code"] == "insufficient_scope"
    allowed = anon.post(f"/api/projects/{project['id']}/check", json={}, headers={"Authorization": f"Bearer {build}"})
    assert allowed.status_code == 200


def test_a_full_account_cannot_run_the_compiler(app, client, compiler):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    project = c_project(ada)
    ada.post("/api/projects", json={"title": "Big", "description": "y" * 1_200_000})   # over 1 MB once limited
    app.config["PRG32_KIT_QUOTA_MB"] = 1
    refused = ada.post(f"/api/projects/{project['id']}/check", json={})
    assert refused.status_code == 413 and refused.get_json()["code"] == "quota_exceeded"
    assert compiler.sources == []


def test_the_real_compiler_reports_the_exact_place(app, client):
    """With the PRG32 toolchain installed (skipped otherwise)."""
    from prg32_construction_kit.build_check import check_command

    if not all(ok for ok, _ in check_command(app.config["PRG32_BUILD_COMMAND"])):
        pytest.skip("PRG32 build toolchain is not installed")
    project = c_project(client)
    answer = client.post(f"/api/projects/{project['id']}/check", json={}).get_json()
    assert answer["available"] and answer["ok"] is False
    assert "<build>/game.c:3:59" in answer["log"] and "missing_value" in answer["log"]
    fine = c_project(client, "Fine", '#include "prg32.h"\nvoid fine_init(void) {}\nvoid fine_update(void) {}\n'
                                     'void fine_draw(void) { prg32_gfx_clear(0); }\n')
    assert client.post(f"/api/projects/{fine['id']}/check", json={}).get_json()["ok"] is True
    assert not [path for path in Path(app.config["BUILD_ROOT"]).glob("build_*")]
