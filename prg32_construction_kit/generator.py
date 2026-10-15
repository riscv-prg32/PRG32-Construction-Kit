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
# One expression token: an integer, a name, or an allowed C operator.
_EXPR_TOKEN_RE = re.compile(
    r"\s*(?:(?P<number>(?:0[xX][0-9A-Fa-f]+|[0-9]+)(?![A-Za-z0-9_]))"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
    r"|(?P<op><<|>>|<=|>=|==|!=|&&|\|\||[-+*/%()<>!&|^~]))"
)
_COLOR_MACROS = set(COLOR_MAP.values())
_BUTTON_MACROS = set(BUTTON_MAP.values())
# Names students cannot use for state variables because C already uses them.
# `input` is the local button mask inside the generated update function.
RESERVED_NAMES = {
    "auto", "break", "case", "char", "const", "continue", "default", "do", "double", "else", "enum",
    "extern", "float", "for", "goto", "if", "inline", "int", "long", "register", "restrict", "return",
    "short", "signed", "sizeof", "static", "struct", "switch", "typedef", "union", "unsigned", "void",
    "volatile", "while", "bool", "true", "false", "asm", "input",
}


def as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, str):
        if not value.strip():
            return {}
        value = json.loads(value)
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


def state_name(value: Any) -> str:
    """Return the C name for a student state variable."""
    name = c_identifier(str(value) if value is not None else None, "state")
    if name in RESERVED_NAMES or name.startswith("prg32_"):
        name = f"{name}_var"
    return name


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


def check_expr(value: Any) -> str | None:
    """Return a safe C integer expression, or None when the text is not allowed.

    Allowed: whole numbers, state variable names, PRG32_ constants, parentheses,
    and arithmetic/comparison/logic operators. Not allowed: function calls,
    decimals, strings, semicolons, braces, comments, or preprocessor text.
    """
    text = str(value).strip()
    if not text or len(text) > 200 or "/*" in text or "*/" in text or "//" in text:
        return None
    out: list[str] = []
    pos = 0
    depth = 0
    want_value = True  # the grammar alternates: value, operator, value, ...
    while pos < len(text):
        match = _EXPR_TOKEN_RE.match(text, pos)
        if not match or match.end() == pos:
            return None
        out.append(text[pos:match.start(match.lastgroup)])
        kind = match.lastgroup
        token = match.group(kind)
        if kind in {"name", "number"}:
            if not want_value:
                return None
            if kind == "name":
                token = token if token.startswith("PRG32_") else state_name(token)
            want_value = False
        elif token == "(":
            if not want_value:
                return None  # function calls are not part of the Blocks language
            depth += 1
        elif token == ")":
            depth -= 1
            if depth < 0 or want_value:
                return None
        elif want_value:
            if token not in {"-", "+", "!", "~"}:
                return None
        else:
            want_value = True
        if token in {"+", "-"} and out and "".join(out).endswith(token):
            out.append(" ")  # keep "x - -3" from turning into the C operator --
        out.append(token)
        pos = match.end()
    if depth != 0 or want_value:
        return None
    return "".join(out)


def c_expr(value: Any, fallback: str = "0") -> str:
    text = str(value if value not in (None, "") else fallback)
    return check_expr(text) or check_expr(fallback) or "0"


def c_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(str(value).strip()))
    except Exception:
        return fallback


def color_macro(value: Any) -> str:
    key = str(value or "WHITE").upper().strip()
    if key in _COLOR_MACROS:
        return key
    return COLOR_MAP.get(key, "PRG32_COLOR_WHITE")


def button_macro(value: Any) -> str:
    key = str(value or "A").upper().strip()
    if key in _BUTTON_MACROS:
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
        name = state_name(raw_name)
        self.variables.setdefault(name, initial)
        return name

    def expr(self, value: Any, fallback: Any = 0) -> str:
        """Validate one block field as a C expression, warning when it is replaced."""
        if value in (None, ""):
            value = fallback
        checked = check_expr(value)
        if checked is None:
            self.warnings.append(f"Replaced unsupported expression {str(value)[:40]!r} with {fallback}")
            return c_expr(fallback)
        return checked


def parse_statement(block: dict[str, Any], ctx: ParseContext) -> dict[str, Any] | None:
    btype = block.get("type")
    if btype == "prg32_set_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "score")), c_int(field_value(block, "VALUE", 0)))
        return {"op": "set", "var": name, "value": ctx.expr(field_value(block, "VALUE", 0), 0)}
    if btype == "prg32_change_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "score")))
        return {"op": "change", "var": name, "delta": ctx.expr(field_value(block, "DELTA", 1), 1)}
    if btype == "prg32_clamp_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "x")))
        return {
            "op": "clamp",
            "var": name,
            "low": ctx.expr(field_value(block, "LOW", 0), 0),
            "high": ctx.expr(field_value(block, "HIGH", 320), 320),
        }
    if btype == "prg32_random_state":
        name = ctx.ensure_var(str(field_value(block, "VAR", "target_x")))
        return {"op": "random", "var": name, "low": ctx.expr(field_value(block, "LOW", 0), 0), "high": ctx.expr(field_value(block, "HIGH", 304), 304)}
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
            "ax": ctx.expr(field_value(block, "AX", "player_x"), "player_x"),
            "ay": ctx.expr(field_value(block, "AY", "player_y"), "player_y"),
            "aw": ctx.expr(field_value(block, "AW", 16), 16),
            "ah": ctx.expr(field_value(block, "AH", 16), 16),
            "bx": ctx.expr(field_value(block, "BX", "enemy_x"), "enemy_x"),
            "by": ctx.expr(field_value(block, "BY", "enemy_y"), "enemy_y"),
            "bw": ctx.expr(field_value(block, "BW", 16), 16),
            "bh": ctx.expr(field_value(block, "BH", 16), 16),
            "then": parse_stack(child, ctx),
        }
    if btype == "prg32_clear_screen":
        return {"op": "clear", "color": str(field_value(block, "COLOR", "BLACK")).upper()}
    if btype == "prg32_draw_rect":
        return {
            "op": "rect",
            "x": ctx.expr(field_value(block, "X", 0), 0),
            "y": ctx.expr(field_value(block, "Y", 0), 0),
            "w": ctx.expr(field_value(block, "W", 16), 16),
            "h": ctx.expr(field_value(block, "H", 16), 16),
            "color": str(field_value(block, "COLOR", "WHITE")).upper(),
        }
    if btype in {"prg32_draw_pixel", "prg32_draw_pixel_indexed", "prg32_draw_rect_indexed"}:
        result = {"op": {"prg32_draw_pixel": "pixel", "prg32_draw_pixel_indexed": "pixel_indexed", "prg32_draw_rect_indexed": "rect_indexed"}[btype],
                  "x": ctx.expr(field_value(block, "X", 0), 0), "y": ctx.expr(field_value(block, "Y", 0), 0)}
        if btype == "prg32_draw_pixel":
            result["color"] = str(field_value(block, "COLOR", "WHITE")).upper()
        else:
            result["index"] = ctx.expr(field_value(block, "INDEX", 1), 1)
        if btype == "prg32_draw_rect_indexed":
            result["w"] = ctx.expr(field_value(block, "W", 16), 16)
            result["h"] = ctx.expr(field_value(block, "H", 16), 16)
        return result
    if btype == "prg32_palette_set":
        return {"op": "palette_set", "index": ctx.expr(field_value(block, "INDEX", 1), 1), "color": str(field_value(block, "COLOR", "WHITE")).upper()}
    if btype == "prg32_clear_indexed":
        return {"op": "clear_indexed", "index": ctx.expr(field_value(block, "INDEX", 0), 0)}
    if btype == "prg32_draw_text":
        return {
            "op": "text",
            "x": ctx.expr(field_value(block, "X", 0), 0),
            "y": ctx.expr(field_value(block, "Y", 0), 0),
            "text": str(field_value(block, "TEXT", "HELLO")),
            "fg": str(field_value(block, "FG", "WHITE")).upper(),
            "bg": str(field_value(block, "BG", "BLACK")).upper(),
        }
    if btype == "prg32_play_beep":
        return {"op": "beep", "freq": ctx.expr(field_value(block, "FREQ", 880), 880), "ms": ctx.expr(field_value(block, "MS", 80), 80)}
    if btype == "prg32_audio_note":
        return {"op": "note", "note": ctx.expr(field_value(block, "NOTE", 60), 60), "channel": ctx.expr(field_value(block, "CHANNEL", 0), 0), "ms": ctx.expr(field_value(block, "MS", 250), 250)}
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
    elif op == "random":
        lines.append(f"{indent}{stmt['var']} = (int)prg32_random_number({stmt['low']}, {stmt['high']});")
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
    elif op == "pixel":
        lines.append(f"{indent}prg32_gfx_pixel({stmt['x']}, {stmt['y']}, {color_macro(stmt.get('color'))});")
    elif op == "palette_set":
        lines.append(f"{indent}prg32_palette_set({stmt['index']}, {color_macro(stmt.get('color'))});")
    elif op == "clear_indexed":
        lines.append(f"{indent}prg32_gfx_clear_indexed({stmt['index']});")
    elif op == "rect_indexed":
        lines.append(f"{indent}prg32_gfx_rect_indexed({stmt['x']}, {stmt['y']}, {stmt['w']}, {stmt['h']}, {stmt['index']});")
    elif op == "pixel_indexed":
        lines.append(f"{indent}prg32_gfx_pixel_indexed({stmt['x']}, {stmt['y']}, {stmt['index']});")
    elif op == "text":
        lines.append(
            f"{indent}prg32_gfx_text8({stmt['x']}, {stmt['y']}, \"{c_string(stmt.get('text'))}\", "
            f"{color_macro(stmt.get('fg'))}, {color_macro(stmt.get('bg', 'BLACK'))});"
        )
    elif op == "beep":
        lines.append(f"{indent}prg32_audio_note(0, 0, prg32_kit_note_from_hz({stmt['freq']}), 255, {stmt['ms']});")
    elif op == "note":
        lines.append(f"{indent}prg32_audio_note({stmt['channel']}, 0, {stmt['note']}, 255, {stmt['ms']});")
    elif op == "comment":
        lines.append(f"{indent}/* {c_comment(stmt.get('text'))} */")
    else:
        lines.append(f"{indent}/* Unsupported op: {c_comment(op)} */")
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
    lines.extend([
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
        "",
    ])
    for item in game_ir.get("state", []):
        name = state_name(item.get("name"))
        initial = c_int(item.get("initial"), 0)
        lines.append(f"static int {name} = {initial};")
    lines.append("")
    lines.append(f"void {prefix}_init(void) {{")
    for item in game_ir.get("state", []):
        name = state_name(item.get("name"))
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
