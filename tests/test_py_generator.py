"""The Blocks program written in PRG32 Python (py_generator.py), shown read-only as game.py.

- The PRG32 Python compiler accepts the game.py of every example and of every block type.
- It is the same game: the Blocks' IR and the IR compiled back from game.py run in the browser
  simulator with the same buttons and random numbers, and every variable, list item, pixel and
  band text is the same in every frame.
- Expressions get Python's brackets (C and Python bind & | ^ and comparisons differently) and
  numbers used as tests (and tests used as numbers) keep their C meaning.
- The text is deterministic; what cannot be written yet says so in game.py itself.
"""
from __future__ import annotations

import copy
import json
import subprocess

import pytest
from test_examples import EXAMPLE_FILES, HAS_NODE, SIMULATOR, every_block_project, load_project

from prg32_construction_kit import python_project, sample_data
from prg32_construction_kit.generator import blocks_to_ir
from prg32_construction_kit.py_generator import ir_to_python

# Runs two IRs side by side in the simulator: Math.random repeats the same numbers for both.
TWIN = """
global.window = {};
eval(require('fs').readFileSync(%s, 'utf8'));
const { Simulator } = window.PRG32Simulator;
const [a, b, frames] = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const script = {5: ['START'], 8: ['A'], 90: ['A'], 150: ['B'], 210: ['A']};
for (let f = 20; f <= 80; f++) script[f] = ['LEFT', 'UP'];
for (let f = 120; f <= 200; f++) script[f] = ['RIGHT'];
function run(ir) {
  let seed = 12345;
  Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x80000000; };
  const sim = new Simulator(null, null);
  sim.ir = ir; sim.reset();
  const out = [];
  for (let f = 0; f < frames; f++) {
    sim.keys = {}; (script[f] || []).forEach(k => { sim.keys[k] = true; });
    sim.step(false);
    const state = {}; (a.state || []).forEach(s => { state[s.name] = sim.state[s.name]; });
    const lists = {}; (a.lists || []).forEach(l => { lists[l.name] = Array.from(sim.lists[l.name]); });
    let h = 0; for (let i = 0; i < sim.fb.length; i++) h = (h * 31 + sim.fb[i]) | 0;
    out.push(JSON.stringify([state, lists, h, sim.band]));
  }
  return out;
}
const x = run(a), y = run(b);
const bad = x.findIndex((v, i) => v !== y[i]);
console.log(JSON.stringify(bad < 0 ? {same: true, last: x[x.length - 1]} : {frame: bad, blocks: x[bad], python: y[bad]}));
""" % json.dumps(str(SIMULATOR))


def blocks_projects() -> list[tuple[str, dict]]:
    found = [(path.stem, load_project(path)) for path in EXAMPLE_FILES]
    found += [(example["slug"], example["project"]) for example in sample_data.example_catalog()
              if (example["project"].get("game_json") or {}).get("source_mode") in (None, "blocks")]
    return found


def back_to_ir(game_ir: dict, project: dict) -> tuple[str, dict]:
    source = ir_to_python(game_ir)
    assert python_project.check(source, project) == [], source
    return source, python_project.python_to_ir(source, project)


def same_game(blocks_ir: dict, python_ir: dict, frames: int = 240) -> dict:
    result = subprocess.run(["node", "-e", TWIN], input=json.dumps([blocks_ir, python_ir, frames]),
                            capture_output=True, text=True, check=True)
    answer = json.loads(result.stdout)
    assert answer.get("same"), answer
    return answer


@pytest.mark.parametrize("name,project", blocks_projects(), ids=[name for name, _ in blocks_projects()])
def test_every_example_is_written_in_prg32_python(name, project):
    game_ir = blocks_to_ir(project["blocks_json"], project)
    source, _ = back_to_ir(game_ir, project)
    assert "Not yet the same game" not in source, name
    assert source.startswith('"""') and "\nimport prg32\n" in source
    assert ir_to_python(copy.deepcopy(game_ir)) == source        # the same IR gives the same text


@pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")
@pytest.mark.parametrize("name,project", blocks_projects(), ids=[name for name, _ in blocks_projects()])
def test_every_example_is_the_same_game_in_python(name, project):
    game_ir = blocks_to_ir(project["blocks_json"], project)
    _, python_ir = back_to_ir(game_ir, project)
    answer = same_game(game_ir, python_ir)
    assert answer["last"] != "[{},{},0,\"\"]", "nothing happened: the comparison would prove nothing"


AUDIO = {"effects": [{"name": "zap", "voice": 2, "note": 72, "volume": 200, "duration_ms": 120}],
         "soundtracks": [{"name": "theme"}]}
PICTURE = [0x18, 0x3C, 0x7E, 0xFF, 0xFF, 0x7E, 0x3C, 0x18]


def test_every_block_type_is_written_in_prg32_python():
    project = {"title": "Every Block", "blocks_json": every_block_project(), "audio_studio": AUDIO}
    game_ir = blocks_to_ir(project["blocks_json"], project)
    # The picture and sound statements need data the toolbox defaults leave out.
    game_ir["draw"] += [
        {"op": "bitmap", "rows": PICTURE, "x": "10", "y": "20", "color": "RED", "scale": "2"},
        {"op": "sprite8", "rows": PICTURE, "x": "30", "y": "40", "fg": "LIME", "bg": "NAVY"},
        {"op": "tile_define", "id": "3", "rows": PICTURE, "fg": "WHITE", "bg": "BLACK"},
        {"op": "sfx", "name": "zap", "voice": 2, "instrument": 8, "note": 72, "volume": 200, "ms": 120},
        {"op": "track_play", "name": "theme", "track": 0},
    ]
    source, python_ir = back_to_ir(game_ir, project)
    assert "Not yet the same game" not in source
    assert 'prg32.bitmap(["...XX...", "..XXXX..", ".XXXXXX.", "XXXXXXXX", "XXXXXXXX", ".XXXXXX.", "..XXXX..", ' \
           '"...XX..."], 10, 20, prg32.RED, 2)' in source
    assert 'prg32.sound_effect("zap")' in source and 'prg32.soundtrack_play("theme")' in source
    assert python_ir["draw"][-1] == {"op": "track_play", "name": "theme", "track": 0}
    if HAS_NODE:
        same_game(game_ir, python_ir, frames=30)


# Expressions whose meaning depends on how C binds them, or on numbers used as tests.
EXPRESSIONS = [
    "a & b == c", "a | b < 3", "a ^ b != 0", "a << 2 + 1", "a + b * c - -3", "a - (b - c)", "a - b - c",
    "7 / -2", "-7 % 3", "a / 0", "a % 0", "!a", "!!a", "!(a < b)", "a && b", "a || !b", "a && b || c && !a",
    "(a < b) + 1", "-(a == b)", "(a > 0) * 10 + (b > 0)", "~a & 255", "abs(a - b) < 4", "min(a, max(b, 3))",
    "clamp(a * 9, -5, 5)", "sin(a) * 9 / 256", "a < b == (c < 2)", "items[(a + 1) & 3] + items[b & 3]",
    "PRG32_SCREEN_W - 16 | 1", "frame() % 8 < 5", "a > 2 && items[1] == 0",
]


@pytest.mark.skipif(not HAS_NODE, reason="Node.js is not installed")
@pytest.mark.parametrize("start", [(0, 0, 0), (3, -2, 7), (-9, 4, 1), (12, 12, -3)])
def test_expressions_keep_their_c_meaning(start):
    a, b, c = start
    update = [{"op": "set", "var": f"r{i}", "value": text} for i, text in enumerate(EXPRESSIONS)]
    update += [{"op": "if", "cond": text, "then": [{"op": "change", "var": f"t{i}", "delta": "1"}],
                "else": [{"op": "change", "var": f"t{i}", "delta": "-1"}]} for i, text in enumerate(EXPRESSIONS)]
    update += [{"op": "change", "var": "a", "delta": "1"}, {"op": "change", "var": "b", "delta": "-2"},
               {"op": "list_set", "list": "items", "index": "a & 3", "value": "a * 3"}]
    state = [{"name": "a", "type": "int", "initial": a}, {"name": "b", "type": "int", "initial": b},
             {"name": "c", "type": "int", "initial": c}]
    state += [{"name": f"{kind}{i}", "type": "int", "initial": 0} for kind in "rt" for i in range(len(EXPRESSIONS))]
    game_ir = {"title": "Expressions", "state": state, "lists": [{"name": "items", "size": 4}],
               "init": [], "update": update, "draw": [{"op": "clear", "color": "BLACK"}]}
    source, python_ir = back_to_ir(game_ir, {"title": "Expressions"})
    assert "Not yet the same game" not in source
    # C reads  a & b == c  as  a & (b == c), a number and a test: the test is stored as 1 or 0 first
    # (Python would read the same text as  (a & b) == c).
    assert "    if b == c:\n        as_number = 1\n    else:\n        as_number = 0\n    r0 = a & as_number\n" in source
    assert "r3 = a << 2 + 1" in source and "r7 = 7 // -2" in source and "r26 = items[a + 1 & 3]" in source
    assert "    if not a < b:\n        r13 = 1\n" in source
    same_game(game_ir, python_ir, frames=20)


def test_the_text_is_easy_to_read_and_always_the_same():
    game_ir = {"title": "Tiny", "state": [{"name": "x", "type": "int", "initial": 150},
                                         {"name": "lives", "type": "int", "initial": 3}],
               "lists": [{"name": "bricks", "size": 10}],
               "init": [{"op": "list_fill", "list": "bricks", "value": "1"}],
               "update": [{"op": "if_button", "button": "LEFT", "then": [{"op": "change", "var": "x", "delta": "-3"}]},
                          {"op": "clamp", "var": "x", "low": "0", "high": "304"},
                          {"op": "if", "cond": "lives < 1", "then": [{"op": "set", "var": "x", "value": "150"}],
                           "else": [{"op": "if", "cond": "lives > 5", "then": [{"op": "set", "var": "lives", "value": "5"}]}]}],
               "draw": [{"op": "clear", "color": "BLACK"},
                        {"op": "rect", "x": "x", "y": "180", "w": "16", "h": "16", "color": "YELLOW"},
                        {"op": "text", "x": "8", "y": "8", "text": "SAY \"HI\"", "fg": "WHITE", "bg": "BLACK"}]}
    source = ir_to_python(game_ir)
    assert source == '''"""Tiny: the Blocks program written in PRG32 Python.

Made by the kit from the blocks, read-only: change the blocks, then Generate again.
The cartridge is built from game.c; this is the same game in PRG32 Python.
"""
import prg32

x: int = 150
lives: int = 3
bricks: list[int] = [0] * 10


def init() -> None:
    """Runs once, when the game starts (the 'when game starts' blocks)."""
    for fill_i in range(10):
        bricks[fill_i] = 1


def update() -> None:
    """Runs every frame: the 'every frame' blocks."""
    global x, lives
    if prg32.held(prg32.LEFT):
        x -= 3
    x = prg32.clamp(x, 0, 304)
    if lives < 1:
        x = 150
    elif lives > 5:
        lives = 5


def draw() -> None:
    """Runs every frame after update: the 'draw' blocks."""
    prg32.clear(prg32.BLACK)
    prg32.rect(x, 180, 16, 16, prg32.YELLOW)
    prg32.text(8, 8, "SAY \\"HI\\"", prg32.WHITE, prg32.BLACK)
'''
    assert python_project.check(source) == []


def test_what_cannot_be_written_yet_says_so_in_game_py():
    game_ir = {"title": "Odd", "state": [{"name": "lambda", "type": "int", "initial": 0},
                                        {"name": "x", "type": "int", "initial": 0}], "lists": [],
               "init": [], "draw": [],
               "update": [{"op": "set", "var": "x", "value": "random(0, 9) + (x > 3)"}]}
    source = ir_to_python(game_ir)
    notes = source.split("import prg32\n")[1].split("\n\n")[0]
    assert "# Not yet the same game in PRG32 Python:" in notes
    assert "lambda cannot be a PRG32 Python name" in notes
    assert "the test x > 3 is used as a number in a line with random(...)" in notes
    assert '    "Not written in PRG32 Python yet (set)' in source   # the line itself, where it would be


def test_prg32_frame_is_both_the_outline_and_the_frame_count():
    """docs/python_language.md lists frame() among the values; frame(x, y, w, h) still draws."""
    source = ("import prg32\nt: int = 0\n\n\ndef init() -> None:\n    pass\n\n\ndef update() -> None:\n"
              "    global t\n    t = prg32.frame() % 8\n\n\ndef draw() -> None:\n    prg32.frame(1, 2, 3, 4, prg32.RED)\n")
    game_ir = python_project.python_to_ir(source)
    assert game_ir["update"][-1] == {"op": "set", "var": "t", "value": "frame() % 8"}
    assert game_ir["draw"][-1]["op"] == "frame"


def test_generate_sends_game_py_for_blocks_projects_only(client, anon):
    blocks = client.post("/api/projects", json={"title": "Py View", "blocks_json": sample_data.default_blocks()}).get_json()
    answer = client.post(f"/api/projects/{blocks['id']}/convert", json={"source_language": "both"}).get_json()
    assert answer["python_source"] == ir_to_python(answer["game_ir"])
    assert not any(artifact["kind"] == "py_source" for artifact in answer["artifacts"])   # shown, never stored
    c_project = client.post("/api/projects", json={"title": "C View", **sample_data.starter_project("c", "C View")}).get_json()
    assert "python_source" not in client.post(f"/api/projects/{c_project['id']}/convert", json={}).get_json()
    guest = anon.post("/api/guest/convert", json={"source_language": "both", "project": {
        "title": "Guest View", "blocks_json": sample_data.default_blocks()}}).get_json()
    assert guest["python_source"].startswith('"""Guest View: the Blocks program written in PRG32 Python.')
