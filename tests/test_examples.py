"""The example projects and the whole Blocks vocabulary: JSON -> IR -> C, in Python and in the simulator."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit.generator import blocks_to_c, blocks_to_ir, check_expr

ROOT = Path(__file__).resolve().parent.parent
GAMES = ["pong", "breakout", "space_invaders", "asteroids", "snake"]
EXAMPLE_FILES = [ROOT / "examples" / "games" / f"{slug}.json" for slug in GAMES] + [ROOT / "examples" / "feature_tour.json"]
BLOCK_TYPES = sorted(set(re.findall(r"type: '(prg32_\w+)'", (ROOT / "static" / "js" / "blockly_blocks.js").read_text())))
SIMULATOR = ROOT / "static" / "js" / "simulator.js"
HAS_NODE = shutil.which("node") is not None
HOST_CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")


def load_project(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("project", data)


def every_block_project() -> dict:
    """One block of every toolbox type, with the default values a student starts from."""
    containers = {"prg32_on_start", "prg32_update", "prg32_draw"}
    statements = [{"type": "prg32_list_create", "id": "make-list"}]
    statements += [{"type": t, "id": t} for t in BLOCK_TYPES if t not in containers | {"prg32_list_create"}]
    for current, following in zip(statements, statements[1:]):
        current["next"] = {"block": following}
    return {"blocks": {"languageVersion": 0, "blocks": [
        {"type": "prg32_on_start", "id": "start", "inputs": {"DO": {"block": statements[0]}}},
        {"type": "prg32_update", "id": "update"},
        {"type": "prg32_draw", "id": "draw"},
    ]}}


def run_node(script: str) -> str:
    prelude = f"global.window = {{}}; eval(require('fs').readFileSync({json.dumps(str(SIMULATOR))}, 'utf8'));"
    return subprocess.run(["node", "-e", prelude + script], check=True, capture_output=True, text=True).stdout


@pytest.mark.parametrize("path", EXAMPLE_FILES, ids=lambda p: p.stem)
def test_example_projects_generate_clean_deterministic_c(path):
    project = load_project(path)
    ir, source = blocks_to_c(project["blocks_json"], project)
    assert ir["warnings"] == []
    prefix = ir["entry_prefix"]
    for phase in ("init", "update", "draw"):
        assert f"void {prefix}_{phase}(void) {{" in source
    assert blocks_to_c(project["blocks_json"], project)[1] == source  # same JSON, same C
    for banned in ("malloc(", "printf(", "float ", "double ", "#include <stdio"):
        assert banned not in source


def test_games_declare_the_prg32_features_they_use():
    features = {path.stem: blocks_to_ir(load_project(path)["blocks_json"], load_project(path))["required_features"]
                for path in EXAMPLE_FILES}
    assert features["snake"] == ["audio", "tilemap"]
    assert features["asteroids"] == ["audio"]
    assert "sprites" in features["space_invaders"]
    assert features["feature_tour"] == ["audio", "multiplayer", "sprites", "tilemap"]


def test_example_json_is_up_to_date_with_the_generator_script(tmp_path, monkeypatch):
    import importlib.util
    spec = importlib.util.spec_from_file_location("build_example_games", ROOT / "tools" / "build_example_games.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "OUT_DIR", tmp_path / "examples" / "games")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    for written in module.build():
        committed = ROOT / written.relative_to(tmp_path)
        assert written.read_text() == committed.read_text(), f"run python3 tools/build_example_games.py ({committed.name})"


def test_every_toolbox_block_is_understood_by_the_generator():
    assert len(BLOCK_TYPES) >= 45
    ir, source = blocks_to_c(every_block_project(), {"title": "Every Block"})
    assert not [w for w in ir["warnings"] if "unsupported" in w.lower()], ir["warnings"]
    assert "Unsupported" not in source


@pytest.mark.skipif(HOST_CC is None, reason="no host C compiler")
@pytest.mark.parametrize("name", [p.stem for p in EXAMPLE_FILES] + ["every_block"])
def test_generated_c_compiles_without_warnings(tmp_path, name):
    if name == "every_block":
        project = {"title": "Every Block", "blocks_json": every_block_project()}
    else:
        project = next(load_project(p) for p in EXAMPLE_FILES if p.stem == name)
    _, source = blocks_to_c(project["blocks_json"], project)
    c_file = tmp_path / "game.c"
    c_file.write_text(source)
    result = subprocess.run([HOST_CC, "-std=c99", "-Wall", "-Wextra", "-Werror", "-fsyntax-only",
                             "-I", str(ROOT / "tests" / "fixtures"), str(c_file)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")
@pytest.mark.parametrize("path", EXAMPLE_FILES + [None], ids=lambda p: p.stem if p else "every_block")
def test_simulator_reads_blocks_into_the_same_ir(path):
    if path is None:
        project = {"title": "Every Block", "blocks_json": every_block_project()}
    else:
        project = load_project(path)
    ir = blocks_to_ir(project["blocks_json"], project)
    output = run_node(
        f"const ir = window.PRG32Simulator.compileBlocks({json.dumps(project['blocks_json'])});"
        "console.log(JSON.stringify({state: ir.state, lists: ir.lists, features: ir.required_features,"
        " init: ir.init, update: ir.update, draw: ir.draw, warnings: ir.warnings}));"
    )
    js = json.loads(output)
    assert js["state"] == ir["state"]
    assert js["lists"] == ir["lists"]
    assert js["features"] == ir["required_features"]
    for phase in ("init", "update", "draw"):
        assert js[phase] == ir[phase], phase
    assert not [w for w in js["warnings"] if "unsupported" in w.lower()]


@pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")
@pytest.mark.parametrize("slug", GAMES)
def test_games_run_in_the_simulator(slug):
    path = ROOT / "examples" / "games" / f"{slug}.json"
    result = subprocess.run(["node", str(ROOT / "tools" / "simulate.js"), str(path), "400", "", "5:START", "8:A",
                             "20-80:LEFT", "90:A", "120-200:RIGHT", "210:A"], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert report["warnings"] == []
    assert report["state"]


@pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")
def test_expression_normalization_matches_python():
    cases = ["x--3", "Player_X + 2", "bricks[i * 10 + col]", "abs(dx) < 4", "min(a, max(b, 3))", "sin(angle) * 9 / 256",
             "rgb(255, 0, 0)", "random(-2, 2)", "frame() % 8 < 5", "tile(0, x, y) == 4", "peers()", "-(-a)",
             "PRG32_GAME_W - 16", "PRG32_NOT_A_THING", "exit(0)", "bricks", "a[1]", "abs(1, 2)", "1.5", "0x7FFFFFFF",
             "99999999999", "x = 1", "a; b", "{", "#define", "(1", "x[1]]"]
    lists = {"bricks": 60}
    expected = [check_expr(case, lists) for case in cases]
    output = run_node(f"console.log(JSON.stringify({json.dumps(cases)}.map(c => window.PRG32Simulator.checkExpr(c, {json.dumps(lists)}))));")
    assert json.loads(output) == expected
    assert expected[0] == "x - -3"
    assert expected[2] == "bricks[i * 10 + col]"
    assert expected[13:] == [None] * (len(cases) - 13) or expected[13] is None
