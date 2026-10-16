"""Blocks JSON -> validated game IR -> deterministic PRG32 C.

The pipeline has two small steps that students can inspect:

1. ``blocks_to_ir`` reads the saved Blockly workspace and produces a game IR:
   variables, lists, and three statement lists (init, update, draw). Every
   text field is checked by ``expressions.py`` before it enters the IR.
2. ``ir_to_c`` writes freestanding C for the PRG32 portable cartridge ABI.
   Kit helpers (lists, numbers on screen, lines, circles, bitmaps, math) are
   written into the same C file, and only when the game uses them.

``static/js/simulator.js`` reads the same blocks into the same IR so the
browser simulator and the generated C behave alike.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from .expressions import (
    CONSTANTS,
    RESERVED_NAMES,  # noqa: F401  (re-exported for older imports)
    ExpressionError,
    c_identifier,
    check_expr,  # noqa: F401  (re-exported for tests and docs)
    expr_to_c,
    parse_expr,
    render,
    state_name,
)

IR_ABI = "prg32-construction-kit-game-1.1"

COLOR_NAMES = ["BLACK", "WHITE", "RED", "GREEN", "BLUE", "YELLOW", "CYAN", "MAGENTA", "ORANGE", "PINK",
               "GRAY", "DARK_GRAY", "BROWN", "PURPLE", "NAVY", "LIME"]
COLOR_MAP = {name: f"PRG32_COLOR_{name}" for name in COLOR_NAMES}
COLOR_DEFINES = {macro: f"0x{CONSTANTS[macro]:04X}" for macro in COLOR_MAP.values()}

BUTTON_NAMES = ["LEFT", "RIGHT", "UP", "DOWN", "A", "B", "START", "SELECT"]
BUTTON_MAP = {name: f"PRG32_BTN_{name}" for name in BUTTON_NAMES}
BUTTON_MAP.update({f"P2_{name}": f"PRG32_P2_BTN_{name}" for name in BUTTON_NAMES})

MAX_LIST_SIZE = 1024
MAX_REPEAT = 1024
SINE_TABLE = [0, 4, 9, 13, 18, 22, 27, 31, 36, 40, 44, 49, 53, 58, 62, 66, 71, 75, 79, 83, 88, 92, 96, 100,
              104, 108, 112, 116, 120, 124, 128, 132, 136, 139, 143, 147, 150, 154, 158, 161, 165, 168, 171,
              175, 178, 181, 184, 187, 190, 193, 196, 199, 202, 204, 207, 210, 212, 215, 217, 219, 222, 224,
              226, 228, 230, 232, 234, 236, 237, 239, 241, 242, 243, 245, 246, 247, 248, 249, 250, 251, 252,
              253, 254, 254, 255, 255, 255, 256, 256, 256, 256]
_ON_PIXEL = re.compile(r"[^.\s0_-]")


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        if not value.strip():
            return {}
        value = json.loads(value)
    if isinstance(value, dict):
        return value
    return {}


def c_string(value: Any) -> str:
    """Escape text for a C string literal (quotes, backslashes, control characters, trigraphs)."""
    out = []
    for ch in str(value if value is not None else ""):
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ord(ch) < 32 or ord(ch) == 127:
            out.append(f"\\{ord(ch):03o}")
        else:
            out.append(ch)
    text = "".join(out)
    while "??" in text:  # keep C trigraphs such as ??/ from changing the string
        text = text.replace("??", "?\\?")
    return text


def c_comment(value: Any) -> str:
    """Make text safe inside a /* ... */ comment: it can never close the comment early."""
    text = "".join(ch if 32 <= ord(ch) != 127 else " " for ch in str(value if value is not None else ""))
    while "*/" in text or "/*" in text:
        text = text.replace("*/", "* /").replace("/*", "/ *")
    return text.replace("??", "? ?")


def c_expr(value: Any, fallback: str = "0") -> str:
    text = str(value if value not in (None, "") else fallback)
    return check_expr(text) or check_expr(fallback) or "0"


_DECIMAL_RE = re.compile(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")
_WHOLE_NUMBER_RE = re.compile(r"(-?)\s*(0[xX][0-9A-Fa-f]+|[0-9]+)")


def c_int(value: Any, fallback: int = 0) -> int:
    """Read a plain decimal number such as 10 or 2.5 (cut to 10 and 2); anything else gives the fallback.

    simulator.js ``cInt`` accepts exactly the same text.
    """
    text = str(value).strip()
    if not _DECIMAL_RE.fullmatch(text):
        return fallback
    try:
        return int(float(text))
    except (OverflowError, ValueError):
        return fallback


def int32(value: int) -> int:
    """Wrap a whole number to a 32-bit C int, like `value | 0` in JavaScript."""
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


def initial_value(value: Any) -> int:
    """The starting value of a variable: a plain whole number (like -3 or 0x10), otherwise 0."""
    match = _WHOLE_NUMBER_RE.fullmatch(str(value if value is not None else "").strip())
    if not match:
        return 0
    digits = match.group(2)
    number = int(digits, 16) if digits[:2].lower() == "0x" else int(digits, 10)
    if number > 0x7FFFFFFF:
        return 0
    return -number if match.group(1) else number


def color_name(value: Any, fallback: str = "WHITE") -> str:
    key = str(value or fallback).upper().strip()
    if key.startswith("PRG32_COLOR_"):
        key = key[len("PRG32_COLOR_"):]
    return key if key in COLOR_MAP else fallback


def color_macro(value: Any) -> str:
    return COLOR_MAP[color_name(value)]


def button_macro(value: Any) -> str:
    key = str(value or "A").upper().strip()
    if key in BUTTON_MAP.values():
        return key
    return BUTTON_MAP.get(key, "PRG32_BTN_A")


def bitmap_rows(block: dict[str, Any]) -> list[int]:
    """Read the eight ROW0..ROW7 fields: '.' is an empty pixel, anything else is lit."""
    rows = []
    for index in range(8):
        text = str(field_value(block, f"ROW{index}", "........"))[:8].ljust(8, ".")
        value = 0
        for col, ch in enumerate(text):
            if _ON_PIXEL.match(ch):
                value |= 0x80 >> col
        rows.append(value)
    return rows


def workspace_blocks(blocks_json: Any) -> list[dict[str, Any]]:
    data = as_dict(blocks_json)
    if "blocks" in data and isinstance(data["blocks"], dict):
        blocks = data["blocks"].get("blocks", [])
        return blocks if isinstance(blocks, list) else []
    if "blocks" in data and isinstance(data["blocks"], list):
        return data["blocks"]
    if "type" in data:
        return [data]
    return []


def field_value(block: dict[str, Any], name: str, fallback: Any = "") -> Any:
    fields = block.get("fields") or {}
    value = fields.get(name, fallback)
    if isinstance(value, dict):
        return value.get("value", fallback)
    return value


def input_block(block: dict[str, Any], name: str) -> dict[str, Any] | None:
    inputs = block.get("inputs") or {}
    candidate = inputs.get(name)
    if candidate is None and name == "DO":
        candidate = inputs.get("STACK")
    if isinstance(candidate, dict):
        child = candidate.get("block") or candidate.get("shadow")
        return child if isinstance(child, dict) else None
    return None


def next_block(block: dict[str, Any]) -> dict[str, Any] | None:
    nxt = block.get("next") or {}
    if isinstance(nxt, dict):
        child = nxt.get("block")
        return child if isinstance(child, dict) else None
    return None


def walk_stack(block: dict[str, Any] | None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    while isinstance(block, dict) and id(block) not in seen:
        seen.add(id(block))
        out.append(block)
        block = next_block(block)
    return out


def all_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every block in the workspace, including blocks nested in inputs."""
    out: list[dict[str, Any]] = []
    todo = list(blocks)
    seen: set[int] = set()
    while todo:
        block = todo.pop()
        if not isinstance(block, dict) or id(block) in seen:
            continue
        seen.add(id(block))
        out.append(block)
        nxt = next_block(block)
        if nxt:
            todo.append(nxt)
        for value in (block.get("inputs") or {}).values():
            if isinstance(value, dict):
                todo.extend(child for child in (value.get("block"), value.get("shadow")) if isinstance(child, dict))
    return out


@dataclass
class ParseContext:
    variables: dict[str, int] = field(default_factory=dict)
    lists: dict[str, int] = field(default_factory=dict)
    features: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)

    def ensure_var(self, raw_name: Any, initial: int = 0) -> str | None:
        name = state_name(raw_name)
        if name in self.lists:
            self.warnings.append(f"{name} is a list; use the list blocks to change it")
            return None
        self.variables.setdefault(name, initial)
        return name

    def ensure_list(self, raw_name: Any) -> str | None:
        name = state_name(raw_name)
        if name not in self.lists:
            self.warnings.append(f"List {name} is used but never made with a 'make list' block")
            return None
        return name

    def expr(self, value: Any, fallback: Any = 0) -> str:
        """Validate one block field as an expression, warning when it is replaced."""
        if value in (None, ""):
            value = fallback
        try:
            parsed = parse_expr(value, self.lists)
        except (ExpressionError, RecursionError):
            self.warnings.append(f"Replaced unsupported expression {str(value)[:40]!r} with {fallback}")
            parsed = parse_expr(c_expr(fallback), self.lists)
        for name in sorted(parsed.names):
            self.variables.setdefault(name, 0)
        self.features |= parsed.features
        return render(parsed.tree)


def _field_expr(ctx: ParseContext, block: dict[str, Any], name: str, fallback: Any) -> str:
    return ctx.expr(field_value(block, name, fallback), fallback)


def _text(block: dict[str, Any], name: str, fallback: str, limit: int = 64) -> str:
    """Text for the PRG32 8x8 font, which only has printable ASCII: other characters become '?'."""
    raw = str(field_value(block, name, fallback))[:limit]
    return "".join(ch if 32 <= ord(ch) <= 126 else "?" for ch in raw)


def parse_statement(block: dict[str, Any], ctx: ParseContext) -> dict[str, Any] | None:
    btype = block.get("type")
    f = lambda name, fallback: _field_expr(ctx, block, name, fallback)  # noqa: E731
    if btype in {"prg32_set_state", "prg32_change_state", "prg32_clamp_state", "prg32_random_state", "prg32_wrap_state"}:
        initial = initial_value(field_value(block, "VALUE", 0)) if btype == "prg32_set_state" else 0
        name = ctx.ensure_var(field_value(block, "VAR", "score"), initial)
        if name is None:
            return {"op": "comment", "text": f"skipped: {btype} cannot change a list"}
        if btype == "prg32_set_state":
            return {"op": "set", "var": name, "value": f("VALUE", 0)}
        if btype == "prg32_change_state":
            return {"op": "change", "var": name, "delta": f("DELTA", 1)}
        op = {"prg32_clamp_state": "clamp", "prg32_random_state": "random", "prg32_wrap_state": "wrap"}[btype]
        high = 304 if op == "random" else 319 if op == "wrap" else 320
        return {"op": op, "var": name, "low": f("LOW", 0), "high": f("HIGH", high)}
    if btype in {"prg32_if", "prg32_if_else"}:
        stmt = {"op": "if", "cond": f("COND", 0), "then": parse_stack(input_block(block, "DO"), ctx)}
        if btype == "prg32_if_else":
            stmt["else"] = parse_stack(input_block(block, "ELSE"), ctx)
        return stmt
    if btype == "prg32_repeat":
        name = ctx.ensure_var(field_value(block, "VAR", "i"))
        if name is None:
            return {"op": "comment", "text": "skipped: a repeat block cannot count with a list"}
        return {"op": "repeat", "var": name, "from": f("FROM", 0), "to": f("TO", 9),
                "body": parse_stack(input_block(block, "DO"), ctx)}
    if btype == "prg32_list_create":
        name = state_name(field_value(block, "LIST", "items"))
        return {"op": "list_fill", "list": name, "value": f("VALUE", 0)}
    if btype in {"prg32_list_set", "prg32_list_change"}:
        name = ctx.ensure_list(field_value(block, "LIST", "items"))
        if name is None:
            return {"op": "comment", "text": "skipped: unknown list"}
        if btype == "prg32_list_set":
            return {"op": "list_set", "list": name, "index": f("INDEX", 0), "value": f("VALUE", 0)}
        return {"op": "list_change", "list": name, "index": f("INDEX", 0), "delta": f("DELTA", 1)}
    if btype in {"prg32_if_button", "prg32_if_button_once"}:
        button = str(field_value(block, "BUTTON", "A")).upper()
        if button not in BUTTON_MAP:
            button = "A"
        return {"op": "if_button" if btype == "prg32_if_button" else "if_button_once", "button": button,
                "then": parse_stack(input_block(block, "DO"), ctx)}
    if btype == "prg32_if_touching":
        ctx.features.add("sprites")
        stmt = {"op": "if_touching"}
        for key, fallback in (("AX", "player_x"), ("AY", "player_y"), ("AW", 16), ("AH", 16),
                              ("BX", "enemy_x"), ("BY", "enemy_y"), ("BW", 16), ("BH", 16)):
            stmt[key.lower()] = f(key, fallback)
        stmt["then"] = parse_stack(input_block(block, "DO"), ctx)
        return stmt
    if btype == "prg32_clear_screen":
        return {"op": "clear", "color": color_name(field_value(block, "COLOR", "BLACK"), "BLACK")}
    if btype in {"prg32_draw_rect", "prg32_draw_frame"}:
        return {"op": "rect" if btype == "prg32_draw_rect" else "frame", "x": f("X", 0), "y": f("Y", 0),
                "w": f("W", 16), "h": f("H", 16), "color": color_name(field_value(block, "COLOR", "WHITE"))}
    if btype == "prg32_draw_rect_rgb":
        return {"op": "rect_rgb", "x": f("X", 0), "y": f("Y", 0), "w": f("W", 16), "h": f("H", 16),
                "rgb": f("RGB", "0xFFFF")}
    if btype == "prg32_draw_pixel":
        return {"op": "pixel", "x": f("X", 0), "y": f("Y", 0), "color": color_name(field_value(block, "COLOR", "WHITE"))}
    if btype == "prg32_draw_line":
        return {"op": "line", "x1": f("X1", 0), "y1": f("Y1", 0), "x2": f("X2", 16), "y2": f("Y2", 16),
                "color": color_name(field_value(block, "COLOR", "WHITE"))}
    if btype == "prg32_draw_circle":
        return {"op": "circle", "x": f("X", 160), "y": f("Y", 100), "r": f("R", 8),
                "color": color_name(field_value(block, "COLOR", "WHITE")),
                "fill": str(field_value(block, "FILL", "OUTLINE")).upper() == "FILLED"}
    if btype == "prg32_draw_bitmap":
        return {"op": "bitmap", "rows": bitmap_rows(block), "x": f("X", 0), "y": f("Y", 0),
                "color": color_name(field_value(block, "COLOR", "WHITE")), "scale": f("SCALE", 1)}
    if btype == "prg32_draw_sprite8":
        ctx.features.add("sprites")
        return {"op": "sprite8", "rows": bitmap_rows(block), "x": f("X", 0), "y": f("Y", 0),
                "fg": color_name(field_value(block, "FG", "WHITE")), "bg": color_name(field_value(block, "BG", "BLACK"), "BLACK")}
    if btype in {"prg32_draw_pixel_indexed", "prg32_draw_rect_indexed"}:
        result = {"op": "pixel_indexed" if btype == "prg32_draw_pixel_indexed" else "rect_indexed",
                  "x": f("X", 0), "y": f("Y", 0), "index": f("INDEX", 1)}
        if btype == "prg32_draw_rect_indexed":
            result["w"] = f("W", 16)
            result["h"] = f("H", 16)
        return result
    if btype == "prg32_palette_set":
        return {"op": "palette_set", "index": f("INDEX", 1), "color": color_name(field_value(block, "COLOR", "WHITE"))}
    if btype == "prg32_clear_indexed":
        return {"op": "clear_indexed", "index": f("INDEX", 0)}
    if btype == "prg32_draw_text":
        return {"op": "text", "x": f("X", 0), "y": f("Y", 0), "text": _text(block, "TEXT", "HELLO"),
                "fg": color_name(field_value(block, "FG", "WHITE")), "bg": color_name(field_value(block, "BG", "BLACK"), "BLACK")}
    if btype == "prg32_draw_number":
        return {"op": "number", "value": f("VALUE", "score"), "x": f("X", 0), "y": f("Y", 0),
                "fg": color_name(field_value(block, "FG", "WHITE")), "bg": color_name(field_value(block, "BG", "BLACK"), "BLACK")}
    if btype == "prg32_tile_define":
        ctx.features.add("tilemap")
        return {"op": "tile_define", "id": f("ID", 1), "rows": bitmap_rows(block),
                "fg": color_name(field_value(block, "FG", "WHITE")), "bg": color_name(field_value(block, "BG", "BLACK"), "BLACK")}
    if btype == "prg32_playfield_clear":
        ctx.features.add("tilemap")
        return {"op": "playfield_clear", "layer": f("LAYER", 0), "id": f("ID", 0)}
    if btype == "prg32_playfield_put":
        ctx.features.add("tilemap")
        return {"op": "playfield_put", "layer": f("LAYER", 0), "tx": f("TX", 0), "ty": f("TY", 0), "id": f("ID", 1)}
    if btype == "prg32_playfield_scroll":
        ctx.features.add("tilemap")
        return {"op": "playfield_scroll", "layer": f("LAYER", 0), "x": f("X", 0), "y": f("Y", 0)}
    if btype == "prg32_playfield_camera":
        ctx.features.add("tilemap")
        return {"op": "playfield_camera", "x": f("X", 0), "y": f("Y", 0)}
    if btype == "prg32_playfield_draw":
        ctx.features.add("tilemap")
        return {"op": "playfield_draw", "layer": f("LAYER", 0),
                "transparent": str(field_value(block, "TRANSPARENT", "OPAQUE")).upper() == "TRANSPARENT"}
    if btype == "prg32_play_beep":
        ctx.features.add("audio")
        return {"op": "beep", "freq": f("FREQ", 880), "ms": f("MS", 80)}
    if btype == "prg32_audio_note":
        ctx.features.add("audio")
        return {"op": "note", "note": f("NOTE", 60), "channel": f("CHANNEL", 0), "ms": f("MS", 250)}
    if btype == "prg32_audio_stop":
        ctx.features.add("audio")
        return {"op": "note_off", "channel": f("CHANNEL", 0)}
    if btype == "prg32_audio_volume":
        ctx.features.add("audio")
        return {"op": "volume", "volume": f("VOLUME", 200)}
    if btype == "prg32_band_text":
        value = field_value(block, "VALUE", "")
        stmt = {"op": "band", "text": _text(block, "TEXT", "SCORE", 24)}
        if str(value).strip():
            stmt["value"] = ctx.expr(value, 0)
        return stmt
    if btype == "prg32_score_submit":
        return {"op": "score_submit", "value": f("VALUE", "score")}
    if btype == "prg32_scoreboard_show":
        return {"op": "scoreboard", "title": _text(block, "TITLE", "HIGH SCORES", 32)}
    if btype == "prg32_splash":
        return {"op": "splash", "title": _text(block, "TITLE", "MY GAME", 32), "subtitle": _text(block, "SUBTITLE", "PRESS START", 32),
                "ms": f("MS", 1500), "bg": color_name(field_value(block, "BG", "BLACK"), "BLACK"),
                "fg": color_name(field_value(block, "FG", "WHITE")), "accent": color_name(field_value(block, "ACCENT", "YELLOW"))}
    if btype == "prg32_player_name":
        return {"op": "player_name"}
    if btype == "prg32_mp_join":
        ctx.features.add("multiplayer")
        return {"op": "mp_join"}
    if btype == "prg32_mp_share":
        ctx.features.add("multiplayer")
        return {"op": "mp_share", "x": f("X", "player_x"), "y": f("Y", "player_y"), "look": f("LOOK", 0)}
    if btype == "prg32_comment":
        return {"op": "comment", "text": str(field_value(block, "TEXT", "comment"))}
    ctx.warnings.append(f"Skipped unsupported block type: {str(btype)[:40]}")
    return {"op": "comment", "text": f"Unsupported block {str(btype)[:40]}"}


def parse_stack(first_block: dict[str, Any] | None, ctx: ParseContext) -> list[dict[str, Any]]:
    statements: list[dict[str, Any]] = []
    for block in walk_stack(first_block):
        stmt = parse_statement(block, ctx)
        if stmt:
            statements.append(stmt)
    return statements


def blocks_to_ir(blocks_json: Any, project: dict[str, Any] | None = None) -> dict[str, Any]:
    project = project or {}
    ctx = ParseContext()
    init: list[dict[str, Any]] = []
    update: list[dict[str, Any]] = []
    draw: list[dict[str, Any]] = []
    top_blocks = workspace_blocks(blocks_json)

    # Lists are found first, so any block may read a list made in 'when game starts'.
    for block in all_blocks(top_blocks):
        if block.get("type") == "prg32_list_create":
            name = state_name(field_value(block, "LIST", "items"))
            size = max(1, min(MAX_LIST_SIZE, c_int(field_value(block, "SIZE", 10), 10)))
            if name in ctx.lists and ctx.lists[name] != size:
                ctx.warnings.append(f"List {name} is made twice with different sizes; using the larger one")
            ctx.lists[name] = max(size, ctx.lists.get(name, 0))

    for top in top_blocks:
        btype = top.get("type")
        if btype == "prg32_on_start":
            init.extend(parse_stack(input_block(top, "DO"), ctx))
        elif btype == "prg32_update":
            update.extend(parse_stack(input_block(top, "DO"), ctx))
        elif btype == "prg32_draw":
            draw.extend(parse_stack(input_block(top, "DO"), ctx))
        elif btype:
            # Loose blocks are treated as update logic so student work is not lost.
            stmt = parse_statement(top, ctx)
            if stmt:
                update.append(stmt)

    if not ctx.variables and not ctx.lists:
        ctx.variables.update({"player_x": 150, "player_y": 180, "score": 0})
    if not draw:
        ctx.variables.setdefault("player_x", 150)
        ctx.variables.setdefault("player_y", 180)
        draw = [
            {"op": "clear", "color": "BLACK"},
            {"op": "rect", "x": "player_x", "y": "player_y", "w": "16", "h": "16", "color": "YELLOW"},
            {"op": "text", "x": "8", "y": "8", "text": "PRG32", "fg": "GREEN", "bg": "BLACK"},
        ]

    title = project.get("title") or "PRG32 Game"
    prefix = c_identifier(project.get("entry_prefix") or title, "prg32_game")
    return {
        "abi": IR_ABI,
        "title": title,
        "description": project.get("description", ""),
        "author": project.get("author", "Student"),
        "entry_prefix": prefix,
        "state": [{"name": name, "type": "int", "initial": initial} for name, initial in ctx.variables.items()],
        "lists": [{"name": name, "size": size} for name, size in ctx.lists.items()],
        "required_features": sorted(ctx.features),
        "init": init,
        "update": update,
        "draw": draw,
        "warnings": ctx.warnings,
    }


# ---------------------------------------------------------------------------
# C generation
# ---------------------------------------------------------------------------

# Helper C functions, written into the game file only when the game needs them.
HELPERS: dict[str, list[str]] = {
    "list_get": [
        "/* Lists: reading outside a list gives 0. */",
        "static int prg32_kit_get(const int *list, int size, int index) {",
        "    return (index >= 0 && index < size) ? list[index] : 0;",
        "}",
    ],
    "list_set": [
        "/* Lists: writing outside a list does nothing. */",
        "static void prg32_kit_set(int *list, int size, int index, int value) {",
        "    if (index >= 0 && index < size) list[index] = value;",
        "}",
    ],
    "list_fill": [
        "/* Lists: give every item the same value. */",
        "static void prg32_kit_fill(int *list, int size, int value) {",
        "    int index;",
        "    for (index = 0; index < size; ++index) list[index] = value;",
        "}",
    ],
    "div": [
        "/* Division like the RISC-V DIV instruction: x / 0 is -1 (no crash). */",
        "static int prg32_kit_div(int a, int b) {",
        "    if (b == 0) return -1;",
        "    if (b == -1) return (int)(0u - (unsigned int)a);",
        "    return a / b;",
        "}",
    ],
    "mod": [
        "/* Remainder like the RISC-V REM instruction: x % 0 is x (no crash). */",
        "static int prg32_kit_mod(int a, int b) {",
        "    if (b == 0) return a;",
        "    if (b == -1) return 0;",
        "    return a % b;",
        "}",
    ],
    "abs": ["static int prg32_kit_abs(int value) { return value < 0 ? -value : value; }"],
    "sign": ["static int prg32_kit_sign(int value) { return (value > 0) - (value < 0); }"],
    "min": ["static int prg32_kit_min(int a, int b) { return a < b ? a : b; }"],
    "max": ["static int prg32_kit_max(int a, int b) { return a > b ? a : b; }"],
    "clamp": ["static int prg32_kit_clamp(int value, int low, int high) { return value < low ? low : value > high ? high : value; }"],
    "sin": [
        "/* sin(degrees) and cos(degrees) return a value from -256 to 256 (256 means 1.0). */",
        "static const int16_t prg32_kit_sine_table[91] = {",
        *("    " + ", ".join(str(v) for v in SINE_TABLE[i:i + 16]) + ("," if i + 16 < len(SINE_TABLE) else "")
          for i in range(0, len(SINE_TABLE), 16)),
        "};",
        "static int prg32_kit_sin(int degrees) {",
        "    int a = degrees % 360;",
        "    if (a < 0) a += 360;",
        "    if (a <= 90) return prg32_kit_sine_table[a];",
        "    if (a <= 180) return prg32_kit_sine_table[180 - a];",
        "    if (a <= 270) return -prg32_kit_sine_table[a - 180];",
        "    return -prg32_kit_sine_table[360 - a];",
        "}",
    ],
    "cos": ["static int prg32_kit_cos(int degrees) { return prg32_kit_sin(degrees % 360 + 90); }"],
    "rgb": [
        "/* rgb(red, green, blue) packs 0..255 values into one RGB565 colour. */",
        "static int prg32_kit_rgb(int r, int g, int b) {",
        "    r = r < 0 ? 0 : r > 255 ? 255 : r;",
        "    g = g < 0 ? 0 : g > 255 ? 255 : g;",
        "    b = b < 0 ? 0 : b > 255 ? 255 : b;",
        "    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3);",
        "}",
    ],
    "random": [
        "/* A whole random number from low to high, both included. */",
        "static int prg32_kit_random(int low, int high) {",
        "    if (high <= low) return low;",
        "    return low + (int)prg32_random_number(0u, (uint32_t)(high - low));",
        "}",
    ],
    "frame": [
        "/* frame() counts finished frames since the game started. */",
        "static int prg32_kit_frame_count;",
        "static int prg32_kit_frame(void) { return prg32_kit_frame_count; }",
    ],
    "tile": [
        "/* tile(layer, column, row) reads the tile number stored in a playfield. */",
        "static int prg32_kit_tile(int layer, int tx, int ty) {",
        "    if (layer < 0 || tx < 0 || ty < 0 || layer > 255 || tx > 255 || ty > 255) return 0;",
        "    return (int)prg32_playfield_get((uint8_t)layer, (uint8_t)tx, (uint8_t)ty);",
        "}",
    ],
    "peer_value": [
        "/* Other players on the Cartridge Store relay (0 when playing alone). */",
        "static int prg32_kit_peer_value(int index, int what) {",
        "    prg32_player_state_t peer;",
        "    if (prg32_multiplayer_get_peer(index, &peer) != 0) return 0;",
        "    return what == 0 ? peer.x : what == 1 ? peer.y : peer.sprite;",
        "}",
    ],
    "peers": ["static int prg32_kit_peers(void) { return prg32_multiplayer_get_peer_count(); }"],
    "peer_x": ["static int prg32_kit_peer_x(int index) { return prg32_kit_peer_value(index, 0); }"],
    "peer_y": ["static int prg32_kit_peer_y(int index) { return prg32_kit_peer_value(index, 1); }"],
    "peer_look": ["static int prg32_kit_peer_look(int index) { return prg32_kit_peer_value(index, 2); }"],
    "once": [
        "/* Buttons held during the previous frame, for 'just pressed' blocks. */",
        "static uint32_t prg32_kit_previous_input;",
    ],
    "beep": [
        "/* Convert a classroom frequency to the nearest supported MIDI note. */",
        "static uint8_t prg32_kit_note_from_hz(int hz) {",
        "    static const uint16_t frequencies[] = {",
        "        131, 139, 147, 156, 165, 175, 185, 196, 208, 220, 233, 247,",
        "        262, 277, 294, 311, 330, 349, 370, 392, 415, 440, 466, 494,",
        "        523, 554, 587, 622, 659, 698, 740, 784, 831, 880, 932, 988, 1047",
        "    };",
        "    unsigned int index;",
        "    if (hz <= frequencies[0]) return 48;",
        "    for (index = 0; index < 36; ++index) {",
        "        if (hz < (frequencies[index] + frequencies[index + 1]) / 2) return (uint8_t)(48 + index);",
        "    }",
        "    return 84;",
        "}",
    ],
    "number": [
        "/* Write a whole number with the 8x8 PRG32 font (no printf on a cartridge). */",
        "static int prg32_kit_format_number(char *out, int value) {",
        "    char digits[11];",
        "    unsigned int magnitude = value < 0 ? 0u - (unsigned int)value : (unsigned int)value;",
        "    int count = 0;",
        "    int length = 0;",
        "    do {",
        "        digits[count++] = (char)('0' + magnitude % 10u);",
        "        magnitude /= 10u;",
        "    } while (magnitude != 0u && count < 10);",
        "    if (value < 0) out[length++] = '-';",
        "    while (count > 0) out[length++] = digits[--count];",
        "    out[length] = '\\0';",
        "    return length;",
        "}",
        "static void prg32_kit_draw_number(int x, int y, int value, uint16_t fg, uint16_t bg) {",
        "    char text[12];",
        "    prg32_kit_format_number(text, value);",
        "    prg32_gfx_text8(x, y, text, fg, bg);",
        "}",
    ],
    "band": [
        "/* Show text (and a number) in the firmware status band; only redraw when it changes. */",
        "static char prg32_kit_band_now[48];",
        "static char prg32_kit_band_shown[48];",
        "static void prg32_kit_band(const char *text, int has_value, int value) {",
        "    int length = 0;",
        "    int index;",
        "    while (text[length] != '\\0' && length < 32) {",
        "        prg32_kit_band_now[length] = text[length];",
        "        ++length;",
        "    }",
        "    if (has_value) {",
        "        prg32_kit_band_now[length++] = ' ';",
        "        length += prg32_kit_format_number(prg32_kit_band_now + length, value);",
        "    }",
        "    prg32_kit_band_now[length] = '\\0';",
        "    for (index = 0; index <= length; ++index) {",
        "        if (prg32_kit_band_now[index] != prg32_kit_band_shown[index]) break;",
        "    }",
        "    if (index > length) return;",
        "    for (index = 0; index <= length; ++index) prg32_kit_band_shown[index] = prg32_kit_band_now[index];",
        "    prg32_band_set_game_info(prg32_kit_band_now);",
        "}",
    ],
    "frame_rect": [
        "static void prg32_kit_draw_frame(int x, int y, int w, int h, uint16_t color) {",
        "    if (w <= 0 || h <= 0) return;",
        "    prg32_gfx_rect(x, y, w, 1, color);",
        "    prg32_gfx_rect(x, y + h - 1, w, 1, color);",
        "    prg32_gfx_rect(x, y, 1, h, color);",
        "    prg32_gfx_rect(x + w - 1, y, 1, h, color);",
        "}",
    ],
    "line": [
        "/* Bresenham's line algorithm: only whole-number steps, no division. */",
        "static void prg32_kit_draw_line(int x1, int y1, int x2, int y2, uint16_t color) {",
        "    int dx = x2 > x1 ? x2 - x1 : x1 - x2;",
        "    int dy = y2 > y1 ? y1 - y2 : y2 - y1;",
        "    int sx = x1 < x2 ? 1 : -1;",
        "    int sy = y1 < y2 ? 1 : -1;",
        "    int error = dx + dy;",
        "    int steps = 0;",
        "    while (steps++ < 2048) {",
        "        int twice;",
        "        prg32_gfx_pixel(x1, y1, color);",
        "        if (x1 == x2 && y1 == y2) break;",
        "        twice = 2 * error;",
        "        if (twice >= dy) { error += dy; x1 += sx; }",
        "        if (twice <= dx) { error += dx; y1 += sy; }",
        "    }",
        "}",
    ],
    "circle": [
        "/* Midpoint circle algorithm: eight mirrored points per step. */",
        "static void prg32_kit_draw_circle(int cx, int cy, int r, uint16_t color, int filled) {",
        "    int x;",
        "    int y = 0;",
        "    int error;",
        "    if (r < 0) return;",
        "    if (r > 200) r = 200;",
        "    x = r;",
        "    error = 1 - r;",
        "    while (x >= y) {",
        "        if (filled) {",
        "            prg32_gfx_rect(cx - x, cy + y, 2 * x + 1, 1, color);",
        "            prg32_gfx_rect(cx - x, cy - y, 2 * x + 1, 1, color);",
        "            prg32_gfx_rect(cx - y, cy + x, 2 * y + 1, 1, color);",
        "            prg32_gfx_rect(cx - y, cy - x, 2 * y + 1, 1, color);",
        "        } else {",
        "            prg32_gfx_pixel(cx + x, cy + y, color);",
        "            prg32_gfx_pixel(cx - x, cy + y, color);",
        "            prg32_gfx_pixel(cx + x, cy - y, color);",
        "            prg32_gfx_pixel(cx - x, cy - y, color);",
        "            prg32_gfx_pixel(cx + y, cy + x, color);",
        "            prg32_gfx_pixel(cx - y, cy + x, color);",
        "            prg32_gfx_pixel(cx + y, cy - x, color);",
        "            prg32_gfx_pixel(cx - y, cy - x, color);",
        "        }",
        "        ++y;",
        "        if (error < 0) {",
        "            error += 2 * y + 1;",
        "        } else {",
        "            --x;",
        "            error += 2 * (y - x) + 1;",
        "        }",
        "    }",
        "}",
    ],
    "bitmap": [
        "/* Draw an 8x8 picture: each row is one byte, the left pixel is the high bit. */",
        "static void prg32_kit_draw_bitmap(int x, int y, const uint8_t *rows, uint16_t color, int scale) {",
        "    int row;",
        "    int col;",
        "    if (scale < 1) scale = 1;",
        "    if (scale > 8) scale = 8;",
        "    for (row = 0; row < 8; ++row) {",
        "        for (col = 0; col < 8; ++col) {",
        "            if (rows[row] & (0x80u >> col)) prg32_gfx_rect(x + col * scale, y + row * scale, scale, scale, color);",
        "        }",
        "    }",
        "}",
    ],
}
# Helpers that call other helpers.
_HELPER_NEEDS = {"cos": {"sin"}, "band": {"number"}, "peer_x": {"peer_value"}, "peer_y": {"peer_value"},
                 "peer_look": {"peer_value"}}
_HELPER_ORDER = ["list_get", "list_set", "list_fill", "div", "mod", "abs", "sign", "min", "max", "clamp", "sin", "cos", "rgb", "random", "frame", "tile",
                 "peer_value", "peers", "peer_x", "peer_y", "peer_look", "once", "beep", "number", "band", "frame_rect", "line", "circle", "bitmap"]


class _Emitter:
    def __init__(self, game_ir: dict[str, Any]):
        self.lists = {state_name(item.get("name")): max(1, min(MAX_LIST_SIZE, c_int(item.get("size"), 1)))
                      for item in game_ir.get("lists", []) if isinstance(item, dict)}
        self.needs: set[str] = set()
        self.bitmaps: dict[tuple[int, ...], str] = {}
        self.title = str(game_ir.get("title") or "PRG32 Game")

    def x(self, text: Any) -> str:
        """Translate one IR expression to C."""
        checked = check_expr(text, self.lists) if text not in (None, "") else None
        return expr_to_c(checked, self.lists, self.needs) if checked else "0"

    def bitmap(self, rows: Any) -> str:
        values = tuple((c_int(v) & 0xFF) for v in (rows if isinstance(rows, list) else [])[:8])
        values = values + (0,) * (8 - len(values))
        if values not in self.bitmaps:
            self.bitmaps[values] = f"prg32_kit_bitmap_{len(self.bitmaps)}"
        return self.bitmaps[values]

    def block(self, statements: Any, indent: str, depth: int) -> list[str]:
        lines: list[str] = []
        for stmt in statements if isinstance(statements, list) else []:
            if isinstance(stmt, dict):
                lines.extend(self.statement(stmt, indent, depth))
        return lines

    def statement(self, stmt: dict[str, Any], indent: str, depth: int) -> list[str]:
        op = stmt.get("op")
        x = self.x
        var = state_name(stmt.get("var")) if "var" in stmt else ""
        lst = state_name(stmt.get("list")) if "list" in stmt else ""
        inner = indent + "    "
        if op == "set":
            return [f"{indent}{var} = {x(stmt.get('value'))};"]
        if op == "change":
            return [f"{indent}{var} += {x(stmt.get('delta'))};"]
        if op == "clamp":
            low, high = x(stmt.get("low")), x(stmt.get("high"))
            return [f"{indent}if ({var} < {low}) {{ {var} = {low}; }}",
                    f"{indent}if ({var} > {high}) {{ {var} = {high}; }}"]
        if op == "wrap":
            low, high = x(stmt.get("low")), x(stmt.get("high"))
            return [f"{indent}if ({var} < {low}) {{ {var} += ({high}) - ({low}) + 1; }}",
                    f"{indent}else if ({var} > {high}) {{ {var} -= ({high}) - ({low}) + 1; }}"]
        if op == "random":
            self.needs.add("random")
            return [f"{indent}{var} = prg32_kit_random({x(stmt.get('low'))}, {x(stmt.get('high'))});"]
        if op == "if":
            lines = [f"{indent}if ({x(stmt.get('cond'))}) {{", *self.block(stmt.get("then"), inner, depth)]
            if "else" in stmt:
                lines += [f"{indent}}} else {{", *self.block(stmt.get("else"), inner, depth)]
            return lines + [f"{indent}}}"]
        if op == "repeat":
            k, end, n = f"prg32_kit_step{depth}", f"prg32_kit_last{depth}", f"prg32_kit_count{depth}"
            return [
                f"{indent}{{",
                f"{inner}/* repeat {var} from {c_comment(stmt.get('from'))} to {c_comment(stmt.get('to'))} (at most {MAX_REPEAT} times) */",
                f"{inner}int {k};",
                f"{inner}int {end} = {x(stmt.get('to'))};",
                f"{inner}int {n} = 0;",
                f"{inner}for ({k} = {x(stmt.get('from'))}; {k} <= {end} && {n} < {MAX_REPEAT}; ++{k}, ++{n}) {{",
                f"{inner}    {var} = {k};",
                *self.block(stmt.get("body"), inner + "    ", depth + 1),
                f"{inner}}}",
                f"{indent}}}",
            ]
        if op in {"list_fill", "list_set", "list_change"}:
            if lst not in self.lists:
                return [f"{indent}/* unknown list {c_comment(lst)} */"]
            size = self.lists[lst]
            if op == "list_fill":
                self.needs.add("list_fill")
                return [f"{indent}prg32_kit_fill({lst}, {size}, {x(stmt.get('value'))});"]
            index = x(stmt.get("index"))
            self.needs.add("list_set")
            if op == "list_set":
                return [f"{indent}prg32_kit_set({lst}, {size}, {index}, {x(stmt.get('value'))});"]
            self.needs.add("list_get")
            return [f"{indent}prg32_kit_set({lst}, {size}, {index}, prg32_kit_get({lst}, {size}, {index}) + {x(stmt.get('delta'))});"]
        if op == "if_button":
            return [f"{indent}if (input & {button_macro(stmt.get('button'))}) {{",
                    *self.block(stmt.get("then"), inner, depth), f"{indent}}}"]
        if op == "if_button_once":
            self.needs.add("once")
            button = button_macro(stmt.get("button"))
            return [f"{indent}if ((input & {button}) && !(prg32_kit_previous_input & {button})) {{",
                    *self.block(stmt.get("then"), inner, depth), f"{indent}}}"]
        if op == "if_touching":
            args = ", ".join(x(stmt.get(k)) for k in ("ax", "ay", "aw", "ah", "bx", "by", "bw", "bh"))
            return [f"{indent}if (prg32_sprite_hitbox({args})) {{", *self.block(stmt.get("then"), inner, depth), f"{indent}}}"]
        if op == "clear":
            return [f"{indent}prg32_gfx_clear({color_macro(stmt.get('color'))});"]
        if op == "rect":
            return [f"{indent}prg32_gfx_rect({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('w'))}, {x(stmt.get('h'))}, {color_macro(stmt.get('color'))});"]
        if op == "rect_rgb":
            return [f"{indent}prg32_gfx_rect({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('w'))}, {x(stmt.get('h'))}, {x(stmt.get('rgb'))});"]
        if op == "frame":
            self.needs.add("frame_rect")
            return [f"{indent}prg32_kit_draw_frame({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('w'))}, {x(stmt.get('h'))}, {color_macro(stmt.get('color'))});"]
        if op == "pixel":
            return [f"{indent}prg32_gfx_pixel({x(stmt.get('x'))}, {x(stmt.get('y'))}, {color_macro(stmt.get('color'))});"]
        if op == "line":
            self.needs.add("line")
            return [f"{indent}prg32_kit_draw_line({x(stmt.get('x1'))}, {x(stmt.get('y1'))}, {x(stmt.get('x2'))}, {x(stmt.get('y2'))}, {color_macro(stmt.get('color'))});"]
        if op == "circle":
            self.needs.add("circle")
            return [f"{indent}prg32_kit_draw_circle({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('r'))}, {color_macro(stmt.get('color'))}, {1 if stmt.get('fill') else 0});"]
        if op == "bitmap":
            self.needs.add("bitmap")
            return [f"{indent}prg32_kit_draw_bitmap({x(stmt.get('x'))}, {x(stmt.get('y'))}, {self.bitmap(stmt.get('rows'))}, {color_macro(stmt.get('color'))}, {x(stmt.get('scale'))});"]
        if op == "sprite8":
            return [f"{indent}prg32_sprite_draw_8x8({x(stmt.get('x'))}, {x(stmt.get('y'))}, {self.bitmap(stmt.get('rows'))}, {color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg'))});"]
        if op == "palette_set":
            return [f"{indent}prg32_palette_set({x(stmt.get('index'))}, {color_macro(stmt.get('color'))});"]
        if op == "clear_indexed":
            return [f"{indent}prg32_gfx_clear_indexed({x(stmt.get('index'))});"]
        if op == "rect_indexed":
            return [f"{indent}prg32_gfx_rect_indexed({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('w'))}, {x(stmt.get('h'))}, {x(stmt.get('index'))});"]
        if op == "pixel_indexed":
            return [f"{indent}prg32_gfx_pixel_indexed({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('index'))});"]
        if op == "text":
            return [f"{indent}prg32_gfx_text8({x(stmt.get('x'))}, {x(stmt.get('y'))}, \"{c_string(stmt.get('text'))}\", "
                    f"{color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg', 'BLACK'))});"]
        if op == "number":
            self.needs.add("number")
            return [f"{indent}prg32_kit_draw_number({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('value'))}, "
                    f"{color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg', 'BLACK'))});"]
        if op == "tile_define":
            return [f"{indent}prg32_tile_define({x(stmt.get('id'))}, {self.bitmap(stmt.get('rows'))}, "
                    f"{color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg', 'BLACK'))});"]
        if op == "playfield_clear":
            return [f"{indent}prg32_playfield_clear({x(stmt.get('layer'))}, {x(stmt.get('id'))});"]
        if op == "playfield_put":
            return [f"{indent}prg32_playfield_put({x(stmt.get('layer'))}, {x(stmt.get('tx'))}, "
                    f"{x(stmt.get('ty'))}, {x(stmt.get('id'))});"]
        if op == "playfield_scroll":
            return [f"{indent}prg32_playfield_scroll({x(stmt.get('layer'))}, {x(stmt.get('x'))}, {x(stmt.get('y'))});"]
        if op == "playfield_camera":
            return [f"{indent}prg32_playfield_camera({x(stmt.get('x'))}, {x(stmt.get('y'))});"]
        if op == "playfield_draw":
            return [f"{indent}prg32_playfield_draw({x(stmt.get('layer'))}, {1 if stmt.get('transparent') else 0});"]
        if op == "beep":
            self.needs.add("beep")
            return [f"{indent}prg32_audio_note(0, 0, prg32_kit_note_from_hz({x(stmt.get('freq'))}), 255, {x(stmt.get('ms'))});"]
        if op == "note":
            return [f"{indent}prg32_audio_note({x(stmt.get('channel'))}, 0, {x(stmt.get('note'))}, 255, {x(stmt.get('ms'))});"]
        if op == "note_off":
            return [f"{indent}prg32_audio_note_off({x(stmt.get('channel'))});"]
        if op == "volume":
            return [f"{indent}prg32_audio_set_master_volume({x(stmt.get('volume'))});"]
        if op == "band":
            self.needs.add("band")
            has_value = "value" in stmt
            value = x(stmt.get("value")) if has_value else "0"
            return [f"{indent}prg32_kit_band(\"{c_string(stmt.get('text'))}\", {1 if has_value else 0}, {value});"]
        if op == "score_submit":
            return [f"{indent}prg32_score_submit_current_player(\"{c_string(self.title[:23])}\", {x(stmt.get('value'))});"]
        if op == "scoreboard":
            return [f"{indent}prg32_scoreboard_show(\"{c_string(self.title[:23])}\", \"{c_string(stmt.get('title'))}\");"]
        if op == "splash":
            return [f"{indent}prg32_splash_show_game(\"{c_string(stmt.get('title'))}\", \"{c_string(stmt.get('subtitle'))}\", "
                    f"{x(stmt.get('ms'))}, {color_macro(stmt.get('bg'))}, {color_macro(stmt.get('fg'))}, "
                    f"{color_macro(stmt.get('accent'))});"]
        if op == "player_name":
            return [f"{indent}prg32_score_player_prompt();"]
        if op == "mp_join":
            return [f"{indent}prg32_multiplayer_join(\"{c_string(self.title[:31])}\", PRG32_MP_FLAG_ENABLE);"]
        if op == "mp_share":
            return [f"{indent}prg32_multiplayer_set_local_state({x(stmt.get('x'))}, {x(stmt.get('y'))}, {x(stmt.get('look'))}, 0);",
                    f"{indent}prg32_multiplayer_tick();"]
        if op == "comment":
            return [f"{indent}/* {c_comment(stmt.get('text'))} */"]
        return [f"{indent}/* Unsupported op: {c_comment(op)} */"]


def _helper_lines(needs: set[str]) -> list[str]:
    wanted = set(needs)
    for name in list(wanted):
        wanted |= _HELPER_NEEDS.get(name, set())
    lines: list[str] = []
    for name in _HELPER_ORDER:
        if name in wanted:
            lines.extend(HELPERS[name])
            lines.append("")
    return lines


def _reads_input(body: list[str]) -> bool:
    """Button blocks read the local `input` mask; a function declares it only when it is used."""
    return any("(input & " in line or "((input & " in line for line in body)


def ir_to_c(game_ir: dict[str, Any]) -> str:
    prefix = c_identifier(game_ir.get("entry_prefix"), "prg32_game")
    emitter = _Emitter(game_ir)
    state = [(state_name(item.get("name")), int32(c_int(item.get("initial"), 0)))
             for item in game_ir.get("state", []) if isinstance(item, dict)]
    init_body = emitter.block(game_ir.get("init", []), "    ", 0)
    update_body = emitter.block(game_ir.get("update", []), "    ", 0)
    draw_body = emitter.block(game_ir.get("draw", []), "    ", 0)
    needs = emitter.needs
    if emitter.lists:
        needs.add("list_fill")  # init clears every list with prg32_kit_fill

    lines: list[str] = [
        "/*",
        f" * {c_comment(emitter.title)}",
        " * Generated by PRG32-Construction-Kit from the saved Blocks JSON.",
        " * Edit the blocks, then regenerate this file.",
        " */",
        "#include <stdint.h>",
        "#include \"prg32.h\"",
        "",
    ]
    for macro, value in COLOR_DEFINES.items():
        lines.extend([f"#ifndef {macro}", f"#define {macro} {value}", "#endif"])
    lines.extend(["#ifndef PRG32_SCREEN_W", "#define PRG32_SCREEN_W PRG32_GAME_W", "#endif",
                  "#ifndef PRG32_SCREEN_H", "#define PRG32_SCREEN_H PRG32_GAME_H", "#endif", ""])
    lines.extend(_helper_lines(needs))
    for rows, name in emitter.bitmaps.items():
        pattern = "  ".join("".join("#" if row & (0x80 >> col) else "." for col in range(8)) for row in rows)
        lines.append(f"/* {pattern} */")
        lines.append(f"static const uint8_t {name}[8] = {{{', '.join(f'0x{row:02X}' for row in rows)}}};")
    if emitter.bitmaps:
        lines.append("")
    lines.append("/* Game state: every variable is a whole number (int). */")
    for name, initial in state:
        lines.append(f"static int {name} = {initial};")
    for name, size in emitter.lists.items():
        lines.append(f"static int {name}[{size}];")
    lines.append("")

    lines.append(f"void {prefix}_init(void) {{")
    if _reads_input(init_body):
        lines.append("    uint32_t input = prg32_input_read();")
    for name, initial in state:
        lines.append(f"    {name} = {initial};")
    for name, size in emitter.lists.items():
        lines.append(f"    prg32_kit_fill({name}, {size}, 0);")
    if "frame" in needs:
        lines.append("    prg32_kit_frame_count = 0;")
    if "once" in needs:
        lines.append("    prg32_kit_previous_input = prg32_input_read();")
    lines.extend(init_body)
    lines.append("}")
    lines.append("")
    lines.append(f"void {prefix}_update(void) {{")
    if _reads_input(update_body) or "once" in needs:
        lines.append("    uint32_t input = prg32_input_read();")
    lines.extend(update_body)
    if "once" in needs:
        lines.append("    prg32_kit_previous_input = input;")
    if "frame" in needs:
        lines.append("    prg32_kit_frame_count++;")
    lines.append("}")
    lines.append("")
    lines.append(f"void {prefix}_draw(void) {{")
    if _reads_input(draw_body):
        lines.append("    uint32_t input = prg32_input_read();")
    lines.extend(draw_body)
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def blocks_to_c(blocks_json: Any, project: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    game_ir = blocks_to_ir(blocks_json, project)
    return game_ir, ir_to_c(game_ir)


_HEX_COLOR_RE = re.compile(r"^#?([0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")
MAX_SPRITE_SIDE = 128


def _rgb565(hex_color: Any) -> int:
    if not isinstance(hex_color, str) or hex_color == "transparent":
        return 0
    match = _HEX_COLOR_RE.match(hex_color.strip())
    if not match:
        return 0
    text = match.group(1)
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def sprite_to_c(sprite: dict[str, Any]) -> str:
    name = c_identifier(sprite.get("name"), "sprite")
    width = max(1, min(MAX_SPRITE_SIDE, c_int(sprite.get("width"), 16) or 16))
    height = max(1, min(MAX_SPRITE_SIDE, c_int(sprite.get("height"), 16) or 16))
    pixels = sprite.get("pixels") if isinstance(sprite.get("pixels"), list) else []
    flat: list[int] = []
    for y in range(height):
        row = pixels[y] if y < len(pixels) and isinstance(pixels[y], list) else []
        for x in range(width):
            flat.append(_rgb565(row[x] if x < len(row) else None))
    lines = [
        "/* Sprite generated by PRG32-Construction-Kit. */",
        "#include <stdint.h>",
        f"#define {name.upper()}_WIDTH {width}",
        f"#define {name.upper()}_HEIGHT {height}",
        f"static const uint16_t {name}_pixels[{width * height}] = {{",
    ]
    for y in range(height):
        part = flat[y * width : (y + 1) * width]
        lines.append("    " + ", ".join(f"0x{value:04X}" for value in part) + ("," if y < height - 1 else ""))
    lines.append("};")
    lines.append("")
    return "\n".join(lines)
