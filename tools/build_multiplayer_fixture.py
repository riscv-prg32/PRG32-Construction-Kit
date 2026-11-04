#!/usr/bin/env python3
"""Build the Blocks multiplayer test game used by tests/test_multiplayer_browser.py.

    PYTHONPATH=../PRG32 python3 tools/build_multiplayer_fixture.py

The game is made of blocks (tests/fixtures/multiplayer/two_windows.blocks.json). Its C comes from the
kit's own generator, and the PRG32 SDK compiles it into two_windows.prg32 for the browser core, so the
test plays exactly what a student's Blocks project would. Needs the PRG32 SDK and the RISC-V GCC.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit.generator import blocks_to_c  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "multiplayer"
PROJECT = {"title": "Two Windows", "entry_prefix": "tw"}


def stmt(kind, **fields):
    return {"type": kind, "fields": fields}


def chain(blocks):
    for first, second in zip(blocks, blocks[1:]):
        first["next"] = {"block": second}
    return blocks[0]


def when(condition, *blocks):
    return {"type": "prg32_if", "fields": {"COND": condition}, "inputs": {"DO": {"block": chain(list(blocks))}}}


def rect(x, y, color):
    return stmt("prg32_draw_rect", X=x, Y=y, W="8", H="8", COLOR=color)


def game() -> dict:
    """Each window: a yellow square that follows its stick; the first other player as a cyan square
    40 pixels lower; markers along the top for what arrived from that player."""
    start = [stmt("prg32_mp_join", ROOM="kit-two-windows")]
    update = [
        stmt("prg32_set_state", VAR="player_x", VALUE="150 + stick_x()"),
        stmt("prg32_set_state", VAR="player_y", VALUE="60"),
        stmt("prg32_mp_share", X="player_x", Y="player_y", LOOK="7", FLAGS="3"),
        stmt("prg32_mp_send_buttons"),
    ]
    draw = [
        stmt("prg32_clear_screen", COLOR="BLACK"),
        rect("player_x", "player_y", "YELLOW"),
        when("peers() > 0", rect("peer_x(0)", "peer_y(0) + 40", "CYAN")),
        when("peer_look(0) == 7 && peer_flags(0) == 3", rect("0", "0", "GREEN")),
        when("peer_input(0) & 16", rect("16", "0", "RED")),
        when("my_id() != 0", rect("32", "0", "BLUE")),
        when("peer_id(0) != 0 && peer_id(0) != my_id()", rect("48", "0", "MAGENTA")),
    ]
    tops = []
    for kind, blocks in (("prg32_on_start", start), ("prg32_update", update), ("prg32_draw", draw)):
        tops.append({"type": kind, "inputs": {"DO": {"block": chain(blocks)}}})
    return {"blocks": {"languageVersion": 0, "blocks": tops}}


def main() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    blocks = game()
    (FIXTURES / "two_windows.blocks.json").write_text(json.dumps(blocks, indent=1) + "\n", encoding="utf-8")
    ir, c_source = blocks_to_c(blocks, PROJECT)
    assert ir["required_features"] == ["multiplayer"] and not ir["warnings"], ir["warnings"]
    (FIXTURES / "two_windows.c").write_text(c_source, encoding="utf-8")
    with tempfile.TemporaryDirectory() as folder:
        source = Path(folder) / "two_windows.c"
        source.write_text(c_source, encoding="utf-8")
        subprocess.run([sys.executable, "-m", "prg32", "cartridge", "build", str(source), "--portable",
                        "--architecture", "qemu", "--entry-prefix", "tw", "--name", "two_windows",
                        "--out", str(FIXTURES / "two_windows.prg32")], check=True)
    print("Wrote", FIXTURES / "two_windows.prg32")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
