#!/usr/bin/env python3
"""Write the art of the Star Catcher examples, and the Blocks version of the game.

Star Catcher is one small game written four times, once per kind of project, to show how a
game uses the art made in Sprite Lab, Backgrounds and AudioStudio (docs/project_art.md):

    examples/art/star_catcher.art.json      the sprites, the background and the sound (this script)
    examples/art/star_catcher.blocks.json   the Blocks version (this script)
    examples/art/star_catcher.py            the PRG32 Python version (written by hand)
    examples/art/star_catcher.c             the C version (written by hand)
    examples/art/star_catcher.S             the assembly version (written by hand)

Every version catches the same falling star with the same rocket in front of the same sky,
and plays the same sounds. Regenerate the two JSON files after changing this script:

    python3 tools/build_art_examples.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit.audio_studio import default_document, instrument, validate_document  # noqa: E402

OUT_DIR = ROOT / "examples" / "art"

# The rocket: direct colours, '.' is see-through.
ROCKET_COLORS = {"W": "#ffffff", "R": "#e03030", "B": "#3080ff", "G": "#909090", "Y": "#ffd800"}
ROCKET = [
    ".......WW.......",
    "......WWWW......",
    "......WBBW......",
    ".....WWBBWW.....",
    ".....WWWWWW.....",
    "....RWWWWWWR....",
    "....RWWWWWWR....",
    "...RRWWWWWWRR...",
    "...RRWWWWWWRR...",
    "..RRRWWWWWWRRR..",
    "..RR.WWWWWW.RR..",
    "..R..GGGGGG..R..",
    ".....YY..YY.....",
    ".....Y....Y.....",
    "......Y..Y......",
    "................",
]
# The star: an indexed sprite, 4 palette entries (2 bits per pixel), entry 0 see-through.
STAR_PALETTE = ["#000000", "#ffd800", "#fff4a0", "#ff8000"]
STAR = [
    "...1....",
    "...1....",
    ".11211..",
    "1122211.",
    ".12221..",
    ".11211..",
    ".1.3.1..",
    "1..3..1.",
]


def rocket() -> dict:
    pixels = [["transparent" if ch == "." else ROCKET_COLORS[ch] for ch in row] for row in ROCKET]
    return {"name": "rocket", "width": 16, "height": 16, "pixels": pixels, "palette": {}}


def star() -> dict:
    indices = [[0 if ch == "." else int(ch) for ch in row] for row in STAR]
    pixels = [["transparent" if value == 0 else STAR_PALETTE[value] for value in row] for row in indices]
    return {"name": "star", "width": 8, "height": 8, "pixels": pixels,
            "palette": {"mode": "indexed", "colors": STAR_PALETTE, "transparent_index": 0, "indices": indices}}


def sky() -> dict:
    """40 x 25 tiles: a night sky with a few stars, grass, then two rows of solid ground."""
    tiles = [
        {"id": 1, "name": "sky", "rows": [0] * 8, "fg": "#ffffff", "bg": "#101848", "flags": []},
        {"id": 2, "name": "twinkle", "rows": [0, 0, 0, 0x10, 0, 0, 0, 0], "fg": "#ffffff", "bg": "#101848", "flags": []},
        {"id": 3, "name": "grass", "rows": [0xFF, 0xDB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00], "fg": "#30c040",
         "bg": "#6b3a1a", "flags": ["platform"]},
        {"id": 4, "name": "ground", "rows": [0xFF, 0x80, 0x80, 0x80, 0xFF, 0x08, 0x08, 0x08], "fg": "#8b4a22",
         "bg": "#5a2a10", "flags": ["solid"]},
    ]
    layer = []
    for y in range(25):
        if y == 22:
            layer.append([3] * 40)
        elif y > 22:
            layer.append([4] * 40)
        else:
            layer.append([2 if (x * x * 7 + x * y * 3 + y * 31) % 37 == 0 else 1 for x in range(40)])
    return {"name": "sky", "kind": "background", "content_type": "application/json",
            "data": {"width": 40, "height": 25, "tiles": tiles, "layers": [layer]}}


def sound() -> dict:
    document = default_document()
    document["effects"] = [{"name": "Coin", "instrument": instrument("Coin", "pulse", pulse_width=4, attack=0, decay=30,
                                                                     sustain=120, release=40),
                            "note": 84, "duration_ms": 120, "volume": 220, "voice": 7}]
    melody = [72, None, 76, None, 79, None, 76, None, 74, None, 77, None, 81, None, "off", None]
    bass = [48, None, None, None, 55, None, None, None, 50, None, None, None, 57, None, "off", None]
    rows = [melody, bass] + [[None] * 16 for _ in range(6)]
    document["soundtracks"] = [{"name": "Theme", "tempo": 120, "steps": 16, "loop": True, "rows": rows}]
    return validate_document(document)


# --- the Blocks version ------------------------------------------------------------------------
def chain(blocks: list[dict]) -> dict | None:
    for current, following in zip(blocks, blocks[1:]):
        current["next"] = {"block": following}
    return blocks[0] if blocks else None


class Workspace:
    def __init__(self, slug: str):
        self.slug, self.count = slug, 0

    def block(self, block_type: str, inputs: dict | None = None, **fields) -> dict:
        self.count += 1
        block: dict = {"type": block_type, "id": f"{self.slug}-{self.count}"}
        if fields:
            block["fields"] = {key: str(value) for key, value in fields.items()}
        if inputs:
            block["inputs"] = {name: {"block": chain(body)} for name, body in inputs.items() if body}
        return block


def blocks() -> dict:
    w = Workspace("star-catcher")
    b = w.block
    respawn = [b("prg32_set_state", VAR="star_y", VALUE="0"), b("prg32_random_state", VAR="star_x", LOW="8", HIGH="304")]
    start = [b("prg32_set_state", VAR="rocket_x", VALUE="152"), b("prg32_set_state", VAR="star_x", VALUE="100"),
             b("prg32_set_state", VAR="star_y", VALUE="0"), b("prg32_set_state", VAR="score", VALUE="0"),
             b("prg32_background_load", BACKGROUND="sky"), b("prg32_soundtrack_play", TRACK="Theme")]
    update = [
        b("prg32_if_button", {"DO": [b("prg32_change_state", VAR="rocket_x", DELTA="-3")]}, BUTTON="LEFT"),
        b("prg32_if_button", {"DO": [b("prg32_change_state", VAR="rocket_x", DELTA="3")]}, BUTTON="RIGHT"),
        b("prg32_clamp_state", VAR="rocket_x", LOW="0", HIGH="304"),
        b("prg32_change_state", VAR="star_y", DELTA="2"),
        b("prg32_if_touching", {"DO": [b("prg32_change_state", VAR="score", DELTA="1"),
                                       b("prg32_sound_effect", EFFECT="Coin"), *respawn]},
          AX="rocket_x", AY="160", AW="16", AH="16", BX="star_x", BY="star_y", BW="8", BH="8"),
        b("prg32_if", {"DO": [b("prg32_set_state", VAR="star_y", VALUE="0"),
                              b("prg32_random_state", VAR="star_x", LOW="8", HIGH="304")]}, COND="star_y > 176"),
    ]
    draw = [b("prg32_background_draw", BACKGROUND="sky"),
            b("prg32_draw_project_sprite", SPRITE="rocket", X="rocket_x", Y="160"),
            b("prg32_draw_project_sprite", SPRITE="star", X="star_x", Y="star_y"),
            b("prg32_draw_number", VALUE="score", X="8", Y="8", FG="YELLOW", BG="NAVY")]
    tops = []
    for kind, body, x in (("prg32_on_start", start, 20), ("prg32_update", update, 360), ("prg32_draw", draw, 760)):
        top = w.block(kind, {"DO": body})
        top.update({"x": x, "y": 20})
        tops.append(top)
    return {"blocks": {"languageVersion": 0, "blocks": tops}}


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    art = {"sprites": [rocket(), star()], "assets": [sky()], "audio_studio": sound()}
    (OUT_DIR / "star_catcher.art.json").write_text(json.dumps(art, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (OUT_DIR / "star_catcher.blocks.json").write_text(json.dumps(blocks(), indent=1, sort_keys=True) + "\n",
                                                      encoding="utf-8")
    print(f"Wrote {OUT_DIR.relative_to(ROOT)}/star_catcher.art.json and star_catcher.blocks.json")


if __name__ == "__main__":
    main()
