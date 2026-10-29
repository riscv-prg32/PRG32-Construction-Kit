from __future__ import annotations

import json
from pathlib import Path

from .db import count, create_resource

# Complete, playable Blocks games. Each file is a normal exported project
# (examples/games/<slug>.json); tools/build_example_games.py regenerates them.
GAMES_DIR = Path(__file__).resolve().parent.parent / "examples" / "games"
# PRG32 Python examples (ADR-0026): one game.py each; slug -> (title, description).
PYTHON_DIR = Path(__file__).resolve().parent.parent / "examples" / "python"
PYTHON_EXAMPLES = {"brick_catch": ("Brick Catch (Python)", "Catch falling bricks with a paddle: a game written in PRG32 Python.")}
CLASSIC_GAMES = ("pong", "breakout", "space_invaders", "asteroids", "snake")
# Star Catcher (docs/project_art.md): one game, four kinds of project, all using the same
# Sprite Lab sprites, background and AudioStudio sound (examples/art/, tools/build_art_examples.py).
ART_DIR = Path(__file__).resolve().parent.parent / "examples" / "art"
ART_EXAMPLES = (
    ("star_catcher_blocks", "Star Catcher (Blocks)", "blocks", "star_catcher.blocks.json"),
    ("star_catcher_python", "Star Catcher (Python)", "python", "star_catcher.py"),
    ("star_catcher_c", "Star Catcher (C)", "c", "star_catcher.c"),
    ("star_catcher_asm", "Star Catcher (Assembly)", "asm", "star_catcher.S"),
)
_ART_DESCRIPTION = ("Catch the falling star with the rocket. Its sprites, background and sounds are made in "
                    "Sprite Lab, Backgrounds and AudioStudio; the {language} uses them by name.")
_ART_LANGUAGE = {"blocks": "blocks", "python": "Python code", "c": "C code", "asm": "assembly code"}


def art_example_projects() -> list[dict]:
    """The Star Catcher examples: each project with its art (``sprites``, ``assets``, ``audio_studio``)."""
    art = json.loads((ART_DIR / "star_catcher.art.json").read_text(encoding="utf-8"))
    out = []
    for slug, title, kind, file in ART_EXAMPLES:
        text = (ART_DIR / file).read_text(encoding="utf-8")
        game_json: dict = {}
        blocks_json: dict = {}
        if kind == "blocks":
            blocks_json = json.loads(text)
        elif kind == "python":
            game_json = {"source_mode": "python", "source_python": text, "python_language_version": 1}
        else:
            # The art include adds the features its art needs; these are the ones the code itself uses.
            game_json = {"source_mode": kind, f"source_{kind}": text, "required_features": ["audio", "sprites", "tilemap"]}
        project = {"title": title, "description": _ART_DESCRIPTION.format(language=_ART_LANGUAGE[kind]),
                   "author": "PRG32-Construction-Kit", "tags": [kind, "art", "example"],
                   "blocks_json": blocks_json, "game_json": game_json}
        out.append({"slug": slug, "title": title, "description": project["description"], "kind": "art",
                    "language": kind, "project": project, "sprites": art["sprites"], "assets": art["assets"],
                    "audio_studio": art["audio_studio"]})
    return out


def classic_game_project(slug: str) -> dict:
    """Load one complete example game as a project payload."""
    data = json.loads((GAMES_DIR / f"{slug}.json").read_text(encoding="utf-8"))
    project = data.get("project", data)
    return {
        "title": project["title"],
        "description": project.get("description", ""),
        "author": project.get("author", "PRG32 Kit"),
        "tags": project.get("tags", []),
        "blocks_json": project["blocks_json"],
        "game_json": {},
    }


def classic_game_projects() -> list[dict]:
    return [classic_game_project(slug) for slug in CLASSIC_GAMES if (GAMES_DIR / f"{slug}.json").exists()]


def example_catalog() -> list[dict]:
    """Every example offered by the dashboard: complete games first, then short sketches.

    A sketch whose game now exists as a complete game is replaced by it.
    """
    catalog = []
    for slug in CLASSIC_GAMES:
        if (GAMES_DIR / f"{slug}.json").exists():
            project = classic_game_project(slug)
            catalog.append({"slug": slug, "title": project["title"], "description": project["description"],
                            "kind": "game", "project": project})
    for slug, (title, description) in PYTHON_EXAMPLES.items():
        source = (PYTHON_DIR / f"{slug}.py").read_text(encoding="utf-8")
        catalog.append({"slug": f"{slug}_python", "title": title, "description": description, "kind": "python",
                        "project": {"title": title, "description": description, "author": "PRG32-Construction-Kit",
                                    "tags": ["python", "example"], "blocks_json": {},
                                    "game_json": {"source_mode": "python", "source_python": source,
                                                  "python_language_version": 1}}})
    catalog.extend(art_example_projects())
    complete = {item["slug"] for item in catalog}
    for example, project in zip(UPSTREAM_EXAMPLES, upstream_example_projects()):
        if example[0] not in complete:
            catalog.append({"slug": example[0], "title": example[1], "description": example[2],
                            "kind": "sketch", "project": project})
    return catalog


# These match the public examples in riscv-prg32/PRG32.  They are deliberately
# small Block-language lessons: students can open every project, run it in the
# simulator, and inspect its generated C without needing hidden C source.
UPSTREAM_EXAMPLES = (
    ("pong", "Pong", "Move the lower paddle in a two-paddle court.", "WHITE", "paddle_x", "paddle_y"),
    ("breakout", "Breakout", "Move a paddle below a colourful brick wall.", "ORANGE", "paddle_x", "paddle_y"),
    ("space_invaders", "Space Invaders", "Pilot a ship beneath a row of invaders.", "GREEN", "ship_x", "ship_y"),
    ("pacman", "Pacman", "Guide a yellow maze runner around a simple arena.", "YELLOW", "hero_x", "hero_y"),
    ("asteroids", "Asteroids", "Steer a small ship among drifting rocks.", "CYAN", "ship_x", "ship_y"),
    ("tetris", "Tetris", "Slide a falling block into the playfield.", "MAGENTA", "piece_x", "piece_y"),
    ("platformer", "Platformer", "Explore a side-view platform scene.", "GREEN", "hero_x", "hero_y"),
    ("raycaster", "Raycaster", "Explore a first-person-style corridor sketch.", "CYAN", "viewer_x", "viewer_y"),
    ("wing_commander", "Wing Commander", "Fly a cockpit ship through a star field.", "YELLOW", "ship_x", "ship_y"),
    ("frogger", "Frogger", "Help a frog cross a busy road.", "GREEN", "frog_x", "frog_y"),
    ("scrolling_parallax", "Scrolling Parallax", "Move through two differently moving background bands.", "LIME", "camera_x", "camera_y"),
    ("animated_sprites", "Animated Sprites", "Move a character while its colour-frame marker changes.", "ORANGE", "sprite_x", "sprite_y"),
    ("dual_playfield", "Dual Playfield", "Compare a background playfield with a moving foreground ship.", "MAGENTA", "ship_x", "ship_y"),
    ("splash_screen", "Splash Screen", "Make a game title screen with a start button.", "WHITE", "cursor_x", "cursor_y"),
    ("keyboard_input", "Keyboard Input", "Use the directional controls to move a text cursor.", "WHITE", "cursor_x", "cursor_y"),
    ("wifi_setup", "Wi-Fi Setup", "Prototype a friendly setup choice screen.", "CYAN", "choice_x", "choice_y"),
    ("audio_synth", "Audio Synth", "Play a note with the A button.", "MAGENTA", "note_x", "note_y"),
    ("audio_mono_beep", "Audio Mono Beep", "Play a short beep with the A button.", "YELLOW", "beep_x", "beep_y"),
    ("audio_mono_sample", "Audio Mono Sample", "Make a sample-pad sketch using a beep block.", "ORANGE", "pad_x", "pad_y"),
    ("audio_mono_tracker", "Audio Mono Tracker", "Build a tiny mono music-step sketch.", "GREEN", "step_x", "step_y"),
    ("audio_stereo_music", "Audio Stereo Music", "Sketch music lanes in a Blocks-friendly form.", "CYAN", "track_x", "track_y"),
    ("audio_stereo_pan_test", "Audio Stereo Pan Test", "Explore left and right music lanes with a control marker.", "PINK", "pan_x", "pan_y"),
)


ARENA_COLOR = "BLUE"


def upstream_example_blocks(slug: str, title: str, color: str, x_name: str, y_name: str) -> dict:
    """Return a compact, editable Blockly project for one upstream example."""
    def block(block_type: str, block_id: str, fields: dict, next_block: dict | None = None, inputs: dict | None = None) -> dict:
        value = {"type": block_type, "id": f"{slug}-{block_id}", "fields": fields}
        if next_block:
            value["next"] = {"block": next_block}
        if inputs:
            value["inputs"] = inputs
        return value

    # The player is drawn on top of the arena, so it needs a colour of its own to be seen.
    draw = block("prg32_clear_screen", "clear", {"COLOR": "BLACK"}, block(
        "prg32_draw_rect", "arena", {"X": "8", "Y": "24", "W": "304", "H": "168", "COLOR": ARENA_COLOR}, block(
            "prg32_draw_rect", "player", {"X": x_name, "Y": y_name, "W": "16", "H": "16", "COLOR": color}, block(
                "prg32_draw_text", "title", {"TEXT": title.upper(), "X": "12", "Y": "6", "FG": "WHITE", "BG": "BLACK"}
            )
        )
    ))
    clamp_y = block("prg32_clamp_state", "clamp-y", {"VAR": y_name, "LOW": "24", "HIGH": "176"})
    clamp_x = block("prg32_clamp_state", "clamp-x", {"VAR": x_name, "LOW": "8", "HIGH": "296"}, clamp_y)
    down = block("prg32_if_button", "down", {"BUTTON": "DOWN"}, clamp_x, {"DO": {"block": block("prg32_change_state", "down-move", {"VAR": y_name, "DELTA": "3"})}})
    up = block("prg32_if_button", "up", {"BUTTON": "UP"}, down, {"DO": {"block": block("prg32_change_state", "up-move", {"VAR": y_name, "DELTA": "-3"})}})
    right = block("prg32_if_button", "right", {"BUTTON": "RIGHT"}, up, {"DO": {"block": block("prg32_change_state", "right-move", {"VAR": x_name, "DELTA": "3"})}})
    update = block("prg32_if_button", "left", {"BUTTON": "LEFT"}, right, {"DO": {"block": block("prg32_change_state", "left-move", {"VAR": x_name, "DELTA": "-3"})}})
    if slug.startswith("audio_"):
        clamp_y["next"] = {
            "block": block("prg32_if_button", "play", {"BUTTON": "A"}, inputs={"DO": {"block": block("prg32_play_beep", "beep", {"FREQ": "880", "MS": "80"})}})
        }
    return {"blocks": {"languageVersion": 0, "blocks": [
        {"type": "prg32_on_start", "id": f"{slug}-start", "x": 20, "y": 20, "inputs": {"DO": {"block": block("prg32_set_state", "set-x", {"VAR": x_name, "VALUE": "152"}, block("prg32_set_state", "set-y", {"VAR": y_name, "VALUE": "100"}))}}},
        {"type": "prg32_update", "id": f"{slug}-update", "x": 330, "y": 20, "inputs": {"DO": {"block": update}}},
        {"type": "prg32_draw", "id": f"{slug}-draw", "x": 650, "y": 20, "inputs": {"DO": {"block": draw}}},
    ]}}


def upstream_example_projects() -> list[dict]:
    return [
        {
            "title": title,
            "description": f"Blocks adaptation of the PRG32 {title} example. {description}",
            "author": "PRG32 Kit",
            "tags": ["upstream-example", "blocks", slug],
            "blocks_json": upstream_example_blocks(slug, title, color, x_name, y_name),
            "game_json": {},
        }
        for slug, title, description, color, x_name, y_name in UPSTREAM_EXAMPLES
    ]


def default_blocks() -> dict:
    return {
        "blocks": {
            "languageVersion": 0,
            "blocks": [
                {
                    "type": "prg32_on_start",
                    "id": "start",
                    "x": 20,
                    "y": 20,
                    "inputs": {
                        "DO": {
                            "block": {
                                "type": "prg32_set_state",
                                "id": "set-player-x",
                                "fields": {"VAR": "player_x", "VALUE": "150"},
                                "next": {
                                    "block": {
                                        "type": "prg32_set_state",
                                        "id": "set-player-y",
                                        "fields": {"VAR": "player_y", "VALUE": "180"},
                                        "next": {
                                            "block": {
                                                "type": "prg32_set_state",
                                                "id": "set-score",
                                                "fields": {"VAR": "score", "VALUE": "0"},
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    },
                },
                {
                    "type": "prg32_update",
                    "id": "update",
                    "x": 330,
                    "y": 20,
                    "inputs": {
                        "DO": {
                            "block": {
                                "type": "prg32_if_button",
                                "id": "left",
                                "fields": {"BUTTON": "LEFT"},
                                "inputs": {"DO": {"block": {"type": "prg32_change_state", "id": "move-left", "fields": {"VAR": "player_x", "DELTA": "-3"}}}},
                                "next": {
                                    "block": {
                                        "type": "prg32_if_button",
                                        "id": "right",
                                        "fields": {"BUTTON": "RIGHT"},
                                        "inputs": {"DO": {"block": {"type": "prg32_change_state", "id": "move-right", "fields": {"VAR": "player_x", "DELTA": "3"}}}},
                                        "next": {
                                            "block": {
                                                "type": "prg32_clamp_state",
                                                "id": "clamp-x",
                                                "fields": {"VAR": "player_x", "LOW": "0", "HIGH": "304"},
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    },
                },
                {
                    "type": "prg32_draw",
                    "id": "draw",
                    "x": 650,
                    "y": 20,
                    "inputs": {
                        "DO": {
                            "block": {
                                "type": "prg32_clear_screen",
                                "id": "clear",
                                "fields": {"COLOR": "BLACK"},
                                "next": {
                                    "block": {
                                        "type": "prg32_draw_rect",
                                        "id": "player",
                                        "fields": {"X": "player_x", "Y": "player_y", "W": "16", "H": "16", "COLOR": "YELLOW"},
                                        "next": {
                                            "block": {
                                                "type": "prg32_draw_text",
                                                "id": "title",
                                                "fields": {"TEXT": "PRG32 BLOCKS", "X": "8", "Y": "8", "FG": "GREEN", "BG": "BLACK"},
                                            }
                                        },
                                    }
                                },
                            }
                        }
                    },
                },
            ],
        }
    }


def seed_if_empty(default_store_url: str = "http://127.0.0.1:5080") -> None:
    if count("projects") == 0:
        create_resource(
            "projects",
            {
                "title": "Hello Blocks",
                "description": "Move the yellow square left and right, then convert the blocks to PRG32 C.",
                "author": "PRG32 Kit",
                "tags": ["starter", "blocks", "classroom"],
                "blocks_json": default_blocks(),
                "game_json": {},
            },
        )
        for project in classic_game_projects():
            create_resource("projects", project)
        complete = set(CLASSIC_GAMES)
        for example, project in zip(UPSTREAM_EXAMPLES, upstream_example_projects()):
            if example[0] not in complete:
                create_resource("projects", project)
    if count("sprites") == 0:
        pixels = []
        for y in range(16):
            row = []
            for x in range(16):
                if x in (0, 15) or y in (0, 15):
                    row.append("#000000")
                elif 4 <= x <= 11 and 4 <= y <= 11:
                    row.append("#ffd800")
                else:
                    row.append("transparent")
            pixels.append(row)
        create_resource("sprites", {"name": "smile", "width": 16, "height": 16, "pixels": pixels})
    if count("publish_profiles") == 0:
        create_resource("publish_profiles", {"name": "Local Cartridge Store", "store_url": default_store_url, "bearer_token": ""})


# --- New Project: a starting point in Blocks, C, assembly or PRG32 Python -----------------

STARTER_KINDS = ("blocks", "c", "asm", "python")

_C_GENERATED = (" * Generated by PRG32-Construction-Kit from the saved Blocks JSON.\n"
                " * Edit the blocks, then regenerate this file.\n")
_C_STARTER = (" * Made by PRG32-Construction-Kit from Blocks:\n"
              " * this is your own C now. Change it freely; the explanations below stay true until you do.\n")
_ASM_GENERATED = (" * RISC-V assembly generated by PRG32-Construction-Kit from the saved Blocks JSON.\n"
                  " * Edit the blocks, then regenerate this file. The C file made from the same blocks\n"
                  " * does exactly the same work: read the two side by side.\n")
_ASM_STARTER = (" * Made by PRG32-Construction-Kit from Blocks:\n"
                " * this is your own RISC-V assembly now. Change it freely; the explanations below\n"
                " * stay true until you do.\n")


def starter_project(kind: str, title: str) -> dict:
    """The blocks_json and game_json of a new project of one kind (the New Project dialog).

    The C and assembly starters are the starter Blocks game turned into code by the kit's own
    generators, so they pass the same checks as handwritten code and keep the per-line
    explanations; their entry names come from the title, as the checks require.
    """
    if kind not in STARTER_KINDS:
        raise ValueError("kind must be one of: " + ", ".join(STARTER_KINDS))
    if kind == "python":
        # PRG32 Python (ADR-0026): the same small game, written as game.py.
        from .python_project import LANGUAGE_VERSION, STARTER
        return {"blocks_json": {}, "game_json": {"source_mode": "python", "source_python": STARTER,
                                                 "python_language_version": LANGUAGE_VERSION}}
    blocks = default_blocks()
    if kind == "blocks":
        return {"blocks_json": blocks, "game_json": {}}
    return {"blocks_json": blocks, "game_json": blocks_as_code({"title": title, "blocks_json": blocks}, kind)}


def blocks_as_code(project: dict, language: str) -> dict:
    """A Blocks project's game as the ``game_json`` of a C or assembly project (one-way conversion, ADR-0024).

    The code is what the kit's generators make from the blocks (``project["audio_studio"]``, when
    given, fixes the sound numbers), with its explanations, and a header saying it is the
    student's own code now. Raises ValueError when the blocks do not generate.
    """
    from .asm_generator import ir_to_asm
    from .generator import blocks_to_c

    if language not in ("c", "asm"):
        raise ValueError("language must be c or asm")
    # Sprites and backgrounds stay in Sprite Lab and Backgrounds: the code includes them
    # (#include "prg32_assets.h" / ".S", project_assets.py) instead of keeping a copy.
    game_ir, c_source = blocks_to_c(project.get("blocks_json") or {}, project, art_include=True)
    features = list(game_ir.get("required_features") or [])
    if language == "c":
        return {"source_mode": "c", "source_c": c_source.replace(_C_GENERATED, _C_STARTER), "required_features": features}
    return {"source_mode": "asm", "source_asm": ir_to_asm(game_ir, art_include=True).replace(_ASM_GENERATED, _ASM_STARTER),
            "required_features": features}
