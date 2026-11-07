"""ABI 1.8 input (buttons C D L R, the analog stick, game controllers) and multiplayer, in every language."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from prg32_construction_kit import expressions, python_project, source_project
from prg32_construction_kit.asm_generator import blocks_to_asm, ir_to_asm
from prg32_construction_kit.generator import BUTTON_MAP, EventBlockError, blocks_to_c, blocks_to_ir, ir_to_c, room_signature
from prg32_construction_kit.py_generator import ir_to_python

ROOT = Path(__file__).resolve().parent.parent
PROJECT = {"title": "Star Catcher", "entry_prefix": "sc"}


def stmt(kind, **fields):
    return {"type": kind, "id": kind, "fields": fields}


def chain(blocks):
    """Blockly's next links for a list of blocks."""
    for first, second in zip(blocks, blocks[1:]):
        first["next"] = {"block": second}
    return blocks[0] if blocks else None


def game(start=(), update=(), draw=()):
    tops = []
    for kind, blocks in (("prg32_on_start", start), ("prg32_update", update), ("prg32_draw", draw)):
        top = {"type": kind, "id": kind}
        if blocks:
            top["inputs"] = {"DO": {"block": chain([dict(b) for b in blocks])}}
        tops.append(top)
    return {"blocks": {"blocks": tops}}


def python_game(init="pass", update="pass", draw="prg32.clear(prg32.BLACK)"):
    return (f"import prg32\n\nx: int = 0\n\n\ndef init() -> None:\n    {init}\n\n\n"
            f"def update() -> None:\n    global x\n    {update}\n\n\ndef draw() -> None:\n    {draw}\n")


@pytest.mark.parametrize("title, room, expected", [
    ("Star Catcher", "", "Star-Catcher"),
    ("Pong", "", "Pong"),
    ("Pong", "class 3B:v1", "class-3B:v1"),
    ("Caffè è buono", "", "Caff-buono"),
    ("???", "", "prg32-game"),
    ("x" * 80, "", "x" * 47),
])
def test_a_room_name_is_one_the_firmware_accepts(title, room, expected):
    assert room_signature(room, title) == expected


def test_blocks_join_with_a_valid_room_once_and_tick_every_frame():
    ir, c = blocks_to_c(game(start=[stmt("prg32_mp_join")],
                             update=[stmt("prg32_mp_share", X="1", Y="2", LOOK="3", FLAGS="4")]), PROJECT)
    assert ir["required_features"] == ["multiplayer"] and ir["warnings"] == []
    assert 'prg32_kit_mp_join("Star-Catcher");' in c
    assert "if (prg32_kit_mp_joined) return;" in c
    assert "prg32_multiplayer_set_local_state(1, 2, 3, 4);" in c
    update = c[c.index("void sc_update(void)"):c.index("void sc_draw(void)")]
    assert update.count("prg32_multiplayer_tick();") == 1
    assembly = blocks_to_asm(game(start=[stmt("prg32_mp_join")]), PROJECT)[1]
    assert '.asciz "Star-Catcher"' in assembly and "call  prg32_multiplayer_tick" in assembly


def test_python_multiplayer_generates_the_same_as_blocks():
    source = python_game(init='prg32.mp_join("class3b")',
                         update="prg32.mp_share(1, 2, 3, 4)\n    prg32.mp_send_buttons()\n    prg32.mp_leave()",
                         draw="prg32.number(0, 0, prg32.my_id() + prg32.peer_id(0) + prg32.peer_flags(0) + prg32.peer_input(0))")
    ir = python_project.python_to_ir(source, PROJECT)
    assert ir["required_features"] == ["multiplayer"] and ir["warnings"] == []
    c, assembly = ir_to_c(ir), ir_to_asm(ir)
    for line in ('prg32_kit_mp_join("class3b");', "prg32_multiplayer_set_local_state(1, 2, 3, 4);",
                 "prg32_multiplayer_set_input(prg32_input_read());", "prg32_kit_mp_leave();", "prg32_multiplayer_tick();"):
        assert line in c
    for call in ("prg32_kit_mp_join", "prg32_multiplayer_set_input", "prg32_kit_mp_leave", "prg32_multiplayer_tick",
                 "prg32_multiplayer_local_player_id"):
        assert call in assembly
    assert "prg32.mp_join(" in ir_to_python(ir)


def test_a_python_join_without_a_name_uses_the_title():
    ir = python_project.python_to_ir(python_game(init="prg32.mp_join()"), PROJECT)
    assert 'prg32_kit_mp_join("Star-Catcher");' in ir_to_c(ir)


@pytest.mark.parametrize("make", [
    lambda: blocks_to_ir(game(update=[stmt("prg32_mp_share")]), PROJECT),
    lambda: python_project.python_to_ir(python_game(update="prg32.mp_share(1, 2)"), PROJECT),
])
def test_multiplayer_without_a_join_warns(make):
    assert any("never joins" in str(item) for item in make()["warnings"])


def test_only_a_join_that_ran_gets_the_generated_guard_cleared_by_leave():
    c = blocks_to_c(game(start=[stmt("prg32_mp_join")], update=[stmt("prg32_mp_leave")]), PROJECT)[1]
    assert "prg32_kit_mp_joined = 0;" in c


def test_the_firmware_buttons_and_no_player_2():
    for name, bit in (("C", 7), ("D", 8), ("L", 9), ("R", 10)):
        assert BUTTON_MAP[name] == f"PRG32_BTN_{name}" and expressions.CONSTANTS[f"PRG32_BTN_{name}"] == 1 << bit
    assert not [name for name in expressions.CONSTANTS if "P2_" in name]
    assert not [name for name in BUTTON_MAP if "P2_" in name]


def test_a_saved_player_2_button_is_refused_not_changed_to_a():
    block = dict(stmt("prg32_if_button", BUTTON="P2_LEFT"), id="old-block")
    with pytest.raises(EventBlockError) as caught:
        blocks_to_ir(game(update=[block]), PROJECT)
    assert "player 2" in str(caught.value) and caught.value.block_ids == ["old-block"]


def test_python_refuses_player_2_names():
    with pytest.raises(python_project.PythonError):
        python_project.python_to_ir(python_game(update="if prg32.held(prg32.P2_LEFT):\n        x = 1"), PROJECT)


def test_c_and_assembly_refuse_player_2_names():
    with pytest.raises(ValueError, match="player 2"):
        source_project.validate_c_source(
            '#include "prg32.h"\nvoid g_init(void) {}\nvoid g_update(void) { if (prg32_input_read() & PRG32_P2_BTN_A) return; }\nvoid g_draw(void) {}\n', "g")


def test_the_stick_in_blocks_and_python():
    ir, c = blocks_to_c(game(update=[stmt("prg32_change_state", VAR="x", DELTA="stick_x() / 32 + stick_y() + has_stick()")]), PROJECT)
    assert "prg32_input_axis_x()" in c and "prg32_input_axis_y()" in c and "prg32_input_has_analog()" in c
    assert ir["required_features"] == []     # the stick is core: no feature bit, so every console loads it
    ir = python_project.python_to_ir(python_game(update="x = x + prg32.stick_x() // 32"), PROJECT)
    assert "prg32_input_axis_x" in ir_to_asm(ir)


@pytest.mark.skipif(not shutil.which("node"), reason="needs Node")
def test_controllers_follow_the_firmware_rules():
    script = """
    globalThis.window = {};
    require(%s);
    const { Hub, axisValue, BITS } = window.PRG32Controllers;
    const out = {};
    out.rest = axisValue(0.05);                 // inside the deadzone
    out.full = [axisValue(1), axisValue(-1)];
    const pads = [{ id: 'one', mapping: 'standard', connected: true, axes: [0, 0],
      buttons: Array.from({ length: 16 }, (_, i) => ({ pressed: [0, 2, 5, 12].includes(i) })) },
      null, { id: 'two', mapping: '', connected: true, axes: [0, 0], buttons: [{ pressed: false }, { pressed: true }] }];
    let hub = new Hub(() => pads);
    const first = hub.poll();
    out.mask = first.mask === (BITS.A | BITS.C | BITS.R | BITS.UP | BITS.B);
    out.stick = first.stick;
    // A direction turns on at a tilt of 40 and off below 24.
    hub = new Hub(() => [{ id: 's', connected: true, mapping: 'standard', buttons: [], axes: [hub.tilt, 0] }]);
    const right = tilt => { hub.tilt = tilt; return Boolean(hub.poll().mask & BITS.RIGHT); };
    out.hysteresis = [0.2, 0.5, 0.3, 0.1].map(right);
    hub = new Hub(() => []);
    out.noPad = hub.poll();
    hub.setScreenStick(1, -1);
    out.screen = hub.poll();
    console.log(JSON.stringify(out));
    """ % json.dumps(str(ROOT / "static" / "js" / "prg32_controllers.js"))
    out = json.loads(subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout)
    assert out["rest"] == 0 and out["full"] == [127, -127]
    assert out["mask"] is True and out["stick"] is True
    assert out["hysteresis"] == [False, True, True, False]
    assert out["noPad"] == {"mask": 0, "x": 0, "y": 0, "stick": False}
    assert out["screen"]["x"] == 127 and out["screen"]["y"] == -127 and out["screen"]["stick"] is True


def test_every_page_with_a_game_loads_the_controllers_first():
    for page, script in (("templates/ide.html", "simulator.js"), ("templates/player.html", "prg32_runtime.js"),
                         ("static/offline.html", "simulator.js"), ("static/offline-player.html", "prg32_runtime.js")):
        text = (ROOT / page).read_text()
        assert text.index("prg32_controllers.js") < text.index(script), page
    assert "/static/js/prg32_controllers.js" in (ROOT / "static" / "service-worker.js").read_text()
