from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

COLOR_MAP = {
    "BLACK": "PRG32_COLOR_BLACK",
    "WHITE": "PRG32_COLOR_WHITE",
    "RED": "PRG32_COLOR_RED",
    "GREEN": "PRG32_COLOR_GREEN",
    "BLUE": "PRG32_COLOR_BLUE",
    "YELLOW": "PRG32_COLOR_YELLOW",
    "CYAN": "PRG32_COLOR_CYAN",
    "MAGENTA": "PRG32_COLOR_MAGENTA",
    "ORANGE": "PRG32_COLOR_ORANGE",
    "PINK": "PRG32_COLOR_PINK",
}

COLOR_DEFINES = {
    "PRG32_COLOR_BLACK": "0x0000",
    "PRG32_COLOR_WHITE": "0xFFFF",
    "PRG32_COLOR_RED": "0xF800",
    "PRG32_COLOR_GREEN": "0x07E0",
    "PRG32_COLOR_BLUE": "0x001F",
    "PRG32_COLOR_YELLOW": "0xFFE0",
    "PRG32_COLOR_CYAN": "0x07FF",
    "PRG32_COLOR_MAGENTA": "0xF81F",
    "PRG32_COLOR_ORANGE": "0xFD20",
    "PRG32_COLOR_PINK": "0xF81F",
}

BUTTON_MAP = {
    "LEFT": "PRG32_BTN_LEFT",
    "RIGHT": "PRG32_BTN_RIGHT",
    "UP": "PRG32_BTN_UP",
    "DOWN": "PRG32_BTN_DOWN",
    "A": "PRG32_BTN_A",
    "B": "PRG32_BTN_B",
    "START": "PRG32_BTN_START",
    "SELECT": "PRG32_BTN_SELECT",
}

_IDENTIFIER_RE = re.compile(r"[^A-Za-z0-9_]+")
_EXPR_RE = re.compile(r"^[A-Za-z0-9_\s+\-*/%()<>!=&|.,]+$")


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        if not value.strip():
            return {}
        return json.loads(value)
    if isinstance(value, dict):
        return value
    return {}


def c_identifier(value: str | None, fallback: str = "game") -> str:
    raw = (value or fallback).strip().lower()
    raw = _IDENTIFIER_RE.sub("_", raw).strip("_")
    if not raw:
        raw = fallback
    if raw[0].isdigit():
        raw = f"_{raw}"
    return raw[:48]


def c_string(value: Any) -> str:
    text = str(value if value is not None else "")
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def c_expr(value: Any, fallback: str = "0") -> str:
    text = str(value if value not in (None, "") else fallback).strip()
    if not _EXPR_RE.match(text):
        return fallback
    return text


def c_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return fallback


def color_macro(value: Any) -> str:
    key = str(value or "WHITE").upper().strip()
    if key.startswith("PRG32_COLOR_"):
        return key
    return COLOR_MAP.get(key, "PRG32_COLOR_WHITE")


def button_macro(value: Any) -> str:
    key = str(value or "A").upper().strip()
    if key.startswith("PRG32_BTN_"):
        return key
    return BUTTON_MAP.get(key, "PRG32_BTN_A")


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
    candidate = inputs.get(name) or inputs.get("DO") or inputs.get("STACK")
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


@dataclass
class ParseContext:
    variables: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def ensure_var(self, raw_name: str, initial: int = 0) -> str:
        name = c_identifier(raw_name, "state")
        self.variables.setdefault(name, initial)
        return name


def parse_statement(block: dict[str, Any], ctx: ParseContext) -> dict[str, Any] | None:
    btype = block.get("type")
    if btype == "prg32_set_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "score")), c_int(field_value(block, "VALUE", 0)))
        return {"op": "set", "var": name, "value": c_expr(field_value(block, "VALUE", 0))}
    if btype == "prg32_change_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "score")))
        return {"op": "change", "var": name, "delta": c_expr(field_value(block, "DELTA", 1))}
    if btype == "prg32_clamp_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "x")))
        return {
            "op": "clamp",
            "var": name,
            "low": c_expr(field_value(block, "LOW", 0)),
            "high": c_expr(field_value(block, "HIGH", 320)),
        }
    if btype == "prg32_if_button":
        child = input_block(block, "DO")
        return {
            "op": "if_button",
            "button": str(field_value(block, "BUTTON", "A")).upper(),
            "then": parse_stack(child, ctx),
        }
    if btype == "prg32_if_touching":
        child = input_block(block, "DO")
        return {
            "op": "if_touching",
            "ax": c_expr(field_value(block, "AX", "player_x")),
            "ay": c_expr(field_value(block, "AY", "player_y")),
            "aw": c_expr(field_value(block, "AW", 16)),
            "ah": c_expr(field_value(block, "AH", 16)),
            "bx": c_expr(field_value(block, "BX", "enemy_x")),
            "by": c_expr(field_value(block, "BY", "enemy_y")),
            "bw": c_expr(field_value(block, "BW", 16)),
            "bh": c_expr(field_value(block, "BH", 16)),
            "then": parse_stack(child, ctx),
        }
    if btype == "prg32_clear_screen":
        return {"op": "clear", "color": str(field_value(block, "COLOR", "BLACK")).upper()}
    if btype == "prg32_draw_rect":
        return {
            "op": "rect",
            "x": c_expr(field_value(block, "X", 0)),
            "y": c_expr(field_value(block, "Y", 0)),
            "w": c_expr(field_value(block, "W", 16)),
            "h": c_expr(field_value(block, "H", 16)),
            "color": str(field_value(block, "COLOR", "WHITE")).upper(),
        }
    if btype == "prg32_draw_text":
        return {
            "op": "text",
            "x": c_expr(field_value(block, "X", 0)),
            "y": c_expr(field_value(block, "Y", 0)),
            "text": str(field_value(block, "TEXT", "HELLO")),
            "fg": str(field_value(block, "FG", "WHITE")).upper(),
            "bg": str(field_value(block, "BG", "BLACK")).upper(),
        }
    if btype == "prg32_play_beep":
        return {"op": "beep", "freq": c_expr(field_value(block, "FREQ", 880)), "ms": c_expr(field_value(block, "MS", 80))}
    if btype == "prg32_comment":
        return {"op": "comment", "text": str(field_value(block, "TEXT", "comment"))}
    ctx.warnings.append(f"Skipped unsupported block type: {btype}")
    return {"op": "comment", "text": f"Unsupported block {btype}"}


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

    for top in workspace_blocks(blocks_json):
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

    if not ctx.variables:
        ctx.variables.update({"player_x": 150, "player_y": 180, "score": 0})
    if not draw:
        draw = [
            {"op": "clear", "color": "BLACK"},
            {"op": "rect", "x": "player_x", "y": "player_y", "w": "16", "h": "16", "color": "YELLOW"},
            {"op": "text", "x": "8", "y": "8", "text": "PRG32", "fg": "GREEN", "bg": "BLACK"},
        ]

    title = project.get("title") or "PRG32 Game"
    prefix = c_identifier(project.get("entry_prefix") or title, "prg32_game")
    return {
        "abi": "prg32-construction-kit-game-1.0",
        "title": title,
        "description": project.get("description", ""),
        "author": project.get("author", "Student"),
        "entry_prefix": prefix,
        "state": [{"name": name, "type": "int", "initial": initial} for name, initial in ctx.variables.items()],
        "init": init,
        "update": update,
        "draw": draw,
        "warnings": ctx.warnings,
    }


def _emit_statement(stmt: dict[str, Any], phase: str, indent: str = "    ") -> list[str]:
    op = stmt.get("op")
    lines: list[str] = []
    if op == "set":
        lines.append(f"{indent}{stmt['var']} = {stmt['value']};")
    elif op == "change":
        lines.append(f"{indent}{stmt['var']} += {stmt['delta']};")
    elif op == "clamp":
        var = stmt["var"]
        lines.append(f"{indent}if ({var} < {stmt['low']}) {{ {var} = {stmt['low']}; }}")
        lines.append(f"{indent}if ({var} > {stmt['high']}) {{ {var} = {stmt['high']}; }}")
    elif op == "if_button":
        lines.append(f"{indent}if (input & {button_macro(stmt.get('button'))}) {{")
        for child in stmt.get("then", []):
            lines.extend(_emit_statement(child, phase, indent + "    "))
        lines.append(f"{indent}}}")
    elif op == "if_touching":
        lines.append(
            f"{indent}if (prg32_sprite_hitbox({stmt['ax']}, {stmt['ay']}, {stmt['aw']}, {stmt['ah']}, "
            f"{stmt['bx']}, {stmt['by']}, {stmt['bw']}, {stmt['bh']})) {{"
        )
        for child in stmt.get("then", []):
            lines.extend(_emit_statement(child, phase, indent + "    "))
        lines.append(f"{indent}}}")
    elif op == "clear":
        lines.append(f"{indent}prg32_gfx_clear({color_macro(stmt.get('color'))});")
    elif op == "rect":
        lines.append(
            f"{indent}prg32_gfx_rect({stmt['x']}, {stmt['y']}, {stmt['w']}, {stmt['h']}, {color_macro(stmt.get('color'))});"
        )
    elif op == "text":
        lines.append(
            f"{indent}prg32_gfx_text8({stmt['x']}, {stmt['y']}, \"{c_string(stmt.get('text'))}\", "
            f"{color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg', 'BLACK'))});"
        )
    elif op == "beep":
        lines.append(f"{indent}prg32_audio_beep({stmt['freq']}, {stmt['ms']});")
    elif op == "comment":
        lines.append(f"{indent}/* {c_string(stmt.get('text'))} */")
    else:
        lines.append(f"{indent}/* Unsupported op: {c_string(op)} */")
    return lines


def ir_to_c(game_ir: dict[str, Any]) -> str:
    prefix = c_identifier(game_ir.get("entry_prefix"), "prg32_game")
    lines: list[str] = [
        "/*",
        " * Generated by PRG32-Construction-Kit.",
        " * Edit the blocks or project JSON, then regenerate this file.",
        " */",
        "#include <stdint.h>",
        "#include \"prg32.h\"",
        "",
    ]
    for macro, value in COLOR_DEFINES.items():
        lines.extend([f"#ifndef {macro}", f"#define {macro} {value}", "#endif"])
    lines.append("")
    for item in game_ir.get("state", []):
        name = c_identifier(item.get("name"), "state")
        initial = c_int(item.get("initial"), 0)
        lines.append(f"static int {name} = {initial};")
    lines.append("")
    lines.append(f"void {prefix}_init(void) {{")
    for item in game_ir.get("state", []):
        name = c_identifier(item.get("name"), "state")
        initial = c_int(item.get("initial"), 0)
        lines.append(f"    {name} = {initial};")
    for stmt in game_ir.get("init", []):
        lines.extend(_emit_statement(stmt, "init"))
    lines.append("}")
    lines.append("")
    lines.append(f"void {prefix}_update(void) {{")
    lines.append("    uint32_t input = prg32_input_read();")
    for stmt in game_ir.get("update", []):
        lines.extend(_emit_statement(stmt, "update"))
    lines.append("}")
    lines.append("")
    lines.append(f"void {prefix}_draw(void) {{")
    for stmt in game_ir.get("draw", []):
        lines.extend(_emit_statement(stmt, "draw"))
    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def blocks_to_c(blocks_json: Any, project: dict[str, Any] | None = None) -> tuple[dict[str, Any], str]:
    game_ir = blocks_to_ir(blocks_json, project)
    return game_ir, ir_to_c(game_ir)


def _rgb565(hex_color: str | None) -> int:
    if not hex_color or hex_color == "transparent":
        return 0
    text = hex_color.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        return 0
    r = int(text[0:2], 16)
    g = int(text[2:4], 16)
    b = int(text[4:6], 16)
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def sprite_to_c(sprite: dict[str, Any]) -> str:
    name = c_identifier(sprite.get("name"), "sprite")
    width = int(sprite.get("width") or 16)
    height = int(sprite.get("height") or 16)
    pixels = sprite.get("pixels") or []
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
