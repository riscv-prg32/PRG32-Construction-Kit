from __future__ import annotations

from .db import count, create_resource


# These match the public examples in riscv-prg32/PRG32.  They are deliberately
# small Block-language lessons: students can open every project, run it in the
# simulator, and inspect its generated C without needing hidden C source.
UPSTREAM_EXAMPLES = (
    ("pong", "Pong", "Move the lower paddle in a two-paddle court.", "BLUE", "paddle_x", "paddle_y"),
    ("breakout", "Breakout", "Move a paddle below a colourful brick wall.", "ORANGE", "paddle_x", "paddle_y"),
    ("space_invaders", "Space Invaders", "Pilot a ship beneath a row of invaders.", "GREEN", "ship_x", "ship_y"),
    ("pacman", "Pacman", "Guide a yellow maze runner around a simple arena.", "YELLOW", "hero_x", "hero_y"),
    ("asteroids", "Asteroids", "Steer a small ship among drifting rocks.", "CYAN", "ship_x", "ship_y"),
    ("tetris", "Tetris", "Slide a falling block into the playfield.", "MAGENTA", "piece_x", "piece_y"),
    ("platformer", "Platformer", "Explore a side-view platform scene.", "GREEN", "hero_x", "hero_y"),
    ("raycaster", "Raycaster", "Explore a first-person-style corridor sketch.", "CYAN", "viewer_x", "viewer_y"),
    ("wing_commander", "Wing Commander", "Fly a cockpit ship through a star field.", "BLUE", "ship_x", "ship_y"),
    ("frogger", "Frogger", "Help a frog cross a busy road.", "GREEN", "frog_x", "frog_y"),
    ("scrolling_parallax", "Scrolling Parallax", "Move through two differently moving background bands.", "BLUE", "camera_x", "camera_y"),
    ("animated_sprites", "Animated Sprites", "Move a character while its colour-frame marker changes.", "ORANGE", "sprite_x", "sprite_y"),
    ("dual_playfield", "Dual Playfield", "Compare a background playfield with a moving foreground ship.", "MAGENTA", "ship_x", "ship_y"),
    ("splash_screen", "Splash Screen", "Make a game title screen with a start button.", "BLUE", "cursor_x", "cursor_y"),
    ("keyboard_input", "Keyboard Input", "Use the directional controls to move a text cursor.", "WHITE", "cursor_x", "cursor_y"),
    ("wifi_setup", "Wi-Fi Setup", "Prototype a friendly setup choice screen.", "CYAN", "choice_x", "choice_y"),
    ("audio_synth", "Audio Synth", "Play a note with the A button.", "MAGENTA", "note_x", "note_y"),
    ("audio_mono_beep", "Audio Mono Beep", "Play a short beep with the A button.", "YELLOW", "beep_x", "beep_y"),
    ("audio_mono_sample", "Audio Mono Sample", "Make a sample-pad sketch using a beep block.", "ORANGE", "pad_x", "pad_y"),
    ("audio_mono_tracker", "Audio Mono Tracker", "Build a tiny mono music-step sketch.", "GREEN", "step_x", "step_y"),
    ("audio_stereo_music", "Audio Stereo Music", "Sketch music lanes in a Blocks-friendly form.", "CYAN", "track_x", "track_y"),
    ("audio_stereo_pan_test", "Audio Stereo Pan Test", "Explore left and right music lanes with a control marker.", "PINK", "pan_x", "pan_y"),
)


def upstream_example_blocks(slug: str, title: str, color: str, x_name: str, y_name: str) -> dict:
    """Return a compact, editable Blockly project for one upstream example."""
    def block(block_type: str, block_id: str, fields: dict, next_block: dict | None = None, inputs: dict | None = None) -> dict:
        value = {"type": block_type, "id": f"{slug}-{block_id}", "fields": fields}
        if next_block:
            value["next"] = {"block": next_block}
        if inputs:
            value["inputs"] = inputs
        return value

    draw = block("prg32_clear_screen", "clear", {"COLOR": "BLACK"}, block(
        "prg32_draw_rect", "arena", {"X": "8", "Y": "24", "W": "304", "H": "168", "COLOR": "BLUE"}, block(
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
        for project in upstream_example_projects():
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
