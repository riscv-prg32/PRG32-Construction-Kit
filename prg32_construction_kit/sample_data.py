from __future__ import annotations

from .db import count, create_resource


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
