"""Scenario L (tools/python_reference.py): the parts that need no PRG32 toolchain, and the CI wiring.

The tool's build phase runs in the toolchain container in CI and its run phase beside canonical
PRG32-QT (python-reference job); these tests keep its inputs honest everywhere: the reference game
compiles, every hostile program and diagnostic is refused at the place the tool expects, the
debug-map lookup finds a game.py line, and the server's answers carry the problem's code and range.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from prg32_construction_kit import python_project

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("python_reference", ROOT / "tools" / "python_reference.py")
reference = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reference)
AUDIO = json.loads(reference.SCENARIO_AUDIO.read_text())


def test_the_reference_game_uses_every_part_of_prg32_python():
    source = reference.SCENARIO.read_text()
    assert python_project.check(source, {"audio_studio": AUDIO}) == []
    for word in ("//", "%", "elif", "else:", "for ", "def double", "def bump", "prg32.held", "prg32.pressed",
                 "prg32.rect", "prg32.circle", "prg32.bitmap", "prg32.text", "prg32.note", "prg32.sound_effect",
                 "prg32.soundtrack_play", "2147483647"):
        assert word in source, word
    pans = [voice["pan"] for voice in AUDIO["voices"]]
    assert len(pans) == 8 and pans == sorted(pans) and pans[0] < 0 < pans[-1]   # stereo, left to right
    assert reference.BREAK_ON in source.splitlines()


@pytest.mark.parametrize("name", sorted(reference.hostile_programs(Path("/nonexistent/sentinel"))))
def test_every_hostile_program_is_refused_without_running(name, tmp_path):
    sentinel = tmp_path / reference.SENTINEL
    program = reference.hostile_programs(sentinel)[name]
    problems = python_project.check(program)
    assert problems and problems[0]["code"], name
    assert problems[0]["line"] >= 1 or problems[0]["code"] == "too_big", name   # a whole-file problem has no line
    assert not sentinel.exists()


@pytest.mark.parametrize("case", reference.diagnostics(), ids=lambda case: case[0])
def test_diagnostics_are_at_the_places_the_tool_expects(case):
    _name, program, code, line, column = case
    problem = python_project.check(program, {"audio_studio": AUDIO})[0]
    assert (problem["code"], problem["line"], problem["column"]) == (code, line, column)


def test_the_server_answers_with_the_problem_code_and_range(client, anon):
    program = reference.diagnostics()[0][1]
    project = client.post("/api/projects", json={"title": "Range", "game_json": {
        "source_mode": "python", "source_python": program, "python_language_version": 1}}).get_json()
    for path in (f"/api/projects/{project['id']}/convert", f"/api/projects/{project['id']}/package"):
        answer = client.post(path, json={})
        body = answer.get_json()
        assert answer.status_code == 400 and body["code"] == "unknown_name", path
        problem = body["problems"][0]
        assert (problem["line"], problem["column"], problem["end_line"]) == (7, 9, 7) and problem["end_column"] > 9
        assert body["error"].startswith("Line 7: ")
    guest = anon.post("/api/guest/convert", json={"project": {"title": "Range", "game_json": {
        "source_mode": "python", "source_python": program}}}).get_json()
    assert guest["code"] == "unknown_name" and guest["problems"][0]["column"] == 9


def test_a_game_py_line_is_found_in_the_debug_maps():
    debug = {"python_source": {"text": "a\n    tick += 1\nb\n"},
             "source_map": {"entries": [{"python": [2, 5, 2, 14], "lines": [40, 41]}, {"python": [3, 1], "lines": [50, 50]}]},
             "debug_map": {"files": ["game.c", "portable_stubs.S"], "link_base": 0x1000,
                           "lines": [[0x1010, 0, 39, 1], [0x1024, 0, 41, 1], [0x1020, 0, 40, 1], [0x1018, 1, 40, 1]],
                           "symbols": [{"name": "g_init", "kind": "function", "address": 0x1000, "size": 0x10},
                                       {"name": "g_update", "kind": "function", "address": 0x1010, "size": 0x40}]}}
    assert reference.python_line_target(debug, "    tick += 1") == (2, "update+16", 16)


def test_ci_runs_both_phases_of_scenario_l():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text()
    assert "tools/python_reference.py build --out /evidence/python-reference" in workflow
    job = workflow.split("\n  python-reference:\n", 1)[1].split("\n  dependency-review:\n", 1)[0]
    assert "needs: container-smoke-test" in job and "repository: riscv-prg32/PRG32-QT" in job
    assert "tools/python_reference.py run" in job and "python-reference-${{ github.sha }}" in job
