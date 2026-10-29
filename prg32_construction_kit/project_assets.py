"""Project art in code: a project's sprites, backgrounds and sounds, for every kind of project.

Sprite Lab, Backgrounds and AudioStudio keep a project's art as data (sprites, assets of kind
``background``, the AudioStudio document). This module turns that data into code, the same way
for every kind of project (docs/project_art.md):

* **Blocks** and **PRG32 Python** name a sprite or a background ("draw sprite ship", "load
  background level"); the game IR then carries the picture itself (``game_ir["assets"]``), so
  the generated C and assembly stay deterministic from the saved project.
* **C** and **assembly** projects write one line, ``#include "prg32_assets.h"`` (C) or
  ``#include "prg32_assets.S"`` (assembly). When the kit builds the game, that line is replaced
  by the project's art written as code, *on that same line*, so every other line keeps its
  number (compiler messages and the debugger point at the line the student wrote). The IDE
  shows the same code, laid out and explained, as a read-only file.

What each picture becomes, in C (the assembly does exactly the same calls):

    enum { SHIP_WIDTH = 16, SHIP_HEIGHT = 16 };
    static const uint16_t ship_pixels[256] = { ... };          /* direct colours, RGB565 */
    void ship_draw(int x, int y) { prg32_sprite_draw_frame(x, y, 16, 16, ship_pixels, 0, 0xF81F); }

    void level_load(void) { ... prg32_tile_define ... prg32_playfield_put ... }
    void level_draw(void) { prg32_playfield_draw(0, 0); prg32_playfield_draw(1, 1); }

    void sfx_jump(void) { prg32_audio_note(0, 8, 72, 200, 120); }
    enum { TRACK_THEME = 0 };

An indexed sprite keeps its packed indices and palette and is drawn with
``prg32_sprite_draw_indexed``. The descriptor it needs holds two addresses, so it is filled in
on the stack when the sprite is drawn: a cartridge can be loaded anywhere, and only code
(never data) may compute an address.

The replacement text has no comments, no ``#`` lines and no ``//``, so even an include line
inside a ``/* ... */`` comment cannot change what the compiler reads.
"""

from __future__ import annotations

import re
from typing import Any

from .expressions import c_identifier
from .messages import text as say

C_INCLUDE = "prg32_assets.h"
ASM_INCLUDE = "prg32_assets.S"
# The include line, exactly on a line of its own ("..." or <...>, # or the %: digraph).
_INCLUDE = r'^[ \t]*(?:#|%:)[ \t]*include[ \t]*["<]{name}[">][ \t]*$'
C_INCLUDE_LINE = re.compile(_INCLUDE.format(name=re.escape(C_INCLUDE)), re.MULTILINE)
ASM_INCLUDE_LINE = re.compile(_INCLUDE.format(name=re.escape(ASM_INCLUDE)), re.MULTILINE)
# The same directive once comments are gone (what source_project's checks see).
_DIRECTIVE = r'^\s*#\s*include\s*["<]{name}[">]\s*$'
C_DIRECTIVE = re.compile(_DIRECTIVE.format(name=re.escape(C_INCLUDE)))
ASM_DIRECTIVE = re.compile(_DIRECTIVE.format(name=re.escape(ASM_INCLUDE)))

MAX_SPRITE_SIDE = 128
TRANSPARENT_KEY = 0xF81F   # magenta: a pixel of this colour is not drawn (prg32_sprite_draw_frame)
FLAGS = {"solid": 1, "platform": 2, "hazard": 4, "collect": 8}   # PRG32_TILE_FLAG_*


class AssetsError(ValueError):
    pass


# ---------------------------------------------------------------------------
# The catalog: every sprite, background and sound of a project, with its C name
# ---------------------------------------------------------------------------

def _rgb565(color: Any) -> int:
    from .generator import _rgb565 as rgb565
    return rgb565(color)


def _names(taken: set[str], prefix: str):
    """Give each piece of art its own C name: no two alike, never the game's own entry names."""
    reserved = {prefix, f"{prefix}_init", f"{prefix}_update", f"{prefix}_draw"}

    def name(raw: Any, fallback: str) -> str:
        base = c_identifier(str(raw) if raw is not None else None, fallback)
        if base.startswith("prg32") or base in reserved:
            base = f"my_{base}"[:48]
        candidate, number = base, 2
        while candidate in taken or candidate in reserved:
            candidate = f"{base[:44]}_{number}"
            number += 1
        taken.add(candidate)
        return candidate
    return name


def _sprite(row: dict[str, Any], name: str) -> dict[str, Any]:
    from .sprite_palette import checked, pixels_of

    width = max(1, min(MAX_SPRITE_SIDE, _whole(row.get("width"), 16)))
    height = max(1, min(MAX_SPRITE_SIDE, _whole(row.get("height"), 16)))
    entry: dict[str, Any] = {"name": name, "title": str(row.get("name") or name)[:64], "width": width, "height": height}
    palette = checked(row.get("palette") or {}, width, height)
    if palette:
        entry["palette"] = palette
        entry["pixels"] = pixels_of(palette)
        return entry
    source = row.get("pixels") if isinstance(row.get("pixels"), list) else []
    pixels = []
    for y in range(height):
        line = source[y] if y < len(source) and isinstance(source[y], list) else []
        pixels.append([_color(line[x]) if x < len(line) else "transparent" for x in range(width)])
    entry["pixels"] = pixels
    return entry


def _color(value: Any) -> str:
    text = str(value or "").strip().lower()
    if re.fullmatch(r"#[0-9a-f]{6}", text):
        return text
    if re.fullmatch(r"#[0-9a-f]{3}", text):
        return "#" + "".join(ch * 2 for ch in text[1:])
    return "transparent"


def _whole(value: Any, fallback: int) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError, OverflowError):
        return fallback


def catalog(sprites: list[dict[str, Any]] | None, assets: list[dict[str, Any]] | None,
            audio: dict[str, Any] | None = None, title: str | None = None) -> dict[str, Any]:
    """Every piece of a project's art, with the C name its code uses.

    ``sprites`` are sprite rows, ``assets`` asset rows (only kind ``background`` is art here),
    ``audio`` the AudioStudio document. The order is fixed (by name, then id), so the same
    project always gives the same code. A sprite or background that does not pass its checks
    is left out and named in ``skipped``.
    """
    from . import backgrounds as background_rules
    from .sprite_palette import PaletteError

    prefix = c_identifier(title or "PRG32 Game", "prg32_game")
    name = _names(set(), prefix)
    order = lambda row: (str(row.get("name") or ""), str(row.get("id") or ""))  # noqa: E731
    out: dict[str, Any] = {"sprites": [], "backgrounds": [], "effects": [], "soundtracks": [], "skipped": []}
    for row in sorted((row for row in sprites or [] if isinstance(row, dict)), key=order):
        try:
            out["sprites"].append(_sprite(row, name(row.get("name"), "sprite")))
        except PaletteError:
            out["skipped"].append(str(row.get("name") or "sprite")[:64])
    rows = [row for row in assets or [] if isinstance(row, dict) and row.get("kind") == "background"]
    for row in sorted(rows, key=order):
        try:
            data = background_rules.checked(row.get("data"))
        except background_rules.BackgroundError:
            out["skipped"].append(str(row.get("name") or "background")[:64])
            continue
        out["backgrounds"].append({"name": name(row.get("name"), "background"),
                                   "title": str(row.get("name") or "background")[:64], **data})
    document = audio if isinstance(audio, dict) else {}
    for index, effect in enumerate(document.get("effects") or []):
        out["effects"].append({"name": name("sfx_" + str(effect.get("name") or index), "sfx"),
                               "title": str(effect.get("name") or ""), "voice": int(effect.get("voice", 0)),
                               "instrument": 8 + index, "note": int(effect.get("note", 60)),
                               "volume": int(effect.get("volume", 200)), "ms": int(effect.get("duration_ms", 200))})
    for index, track in enumerate(document.get("soundtracks") or []):
        out["soundtracks"].append({"name": name("track_" + str(track.get("name") or index), "track").upper(),
                                   "title": str(track.get("name") or ""), "track": index})
    return out


def find(entries: list[dict[str, Any]], wanted: Any) -> dict[str, Any] | None:
    """The sprite or background a block or a Python call names: by its name in the tool, else its C name."""
    text = str(wanted if wanted is not None else "")
    return next((entry for entry in entries if entry["title"] == text), None) \
        or next((entry for entry in entries if entry["name"] == text), None)


def features(assets: dict[str, Any] | None) -> set[str]:
    """The PRG32 features the art needs: sprites, tilemap, platformer (tile flags), audio."""
    assets = assets or {}
    needed = set()
    if assets.get("sprites"):
        needed.add("sprites")
    if assets.get("backgrounds"):
        needed.add("tilemap")
        if any(tile["flags"] for background in assets["backgrounds"] for tile in background["tiles"]):
            needed.add("platformer")
    if assets.get("effects") or assets.get("soundtracks"):
        needed.add("audio")
    return needed


# ---------------------------------------------------------------------------
# The art as C
# ---------------------------------------------------------------------------

def _transparent_key(sprite: dict[str, Any]) -> int:
    """The colour that marks a see-through pixel: magenta, unless the sprite paints with magenta."""
    used = {_rgb565(color) for row in sprite["pixels"] for color in row if color != "transparent"}
    key = TRANSPARENT_KEY
    while key in used:
        key -= 1
    return key


def _numbers(values: list[int], digits: int, per_line: int) -> list[str]:
    fmt = f"0x{{:0{digits}X}}"
    rows = [", ".join(fmt.format(value) for value in values[start:start + per_line])
            for start in range(0, len(values), per_line)] or ["0"]
    return [f"    {row}," if index < len(rows) - 1 else f"    {row}" for index, row in enumerate(rows)]


def _sprite_c(sprite: dict[str, Any]) -> tuple[list[str], list[str]]:
    """(comment lines, code lines) of one sprite."""
    from .sprite_palette import bits_per_pixel, packed

    name, width, height, title = sprite["name"], sprite["width"], sprite["height"], sprite["title"]
    upper = name.upper()
    if sprite.get("palette"):
        palette = sprite["palette"]
        colors, bits = palette["colors"], bits_per_pixel(len(palette["colors"]))
        data = packed(palette)
        transparent = palette["transparent_index"]
        comment = [f"Sprite {title!r}: {width}x{height} pixels, a palette of {len(colors)} colours, "
                   f"{bits} bit(s) per pixel ({len(data)} bytes)"
                   + (f"; palette entry {transparent} is see-through." if transparent >= 0 else "."),
                   f"{name}_draw(x, y) draws it with its top-left corner at x, y (prg32_sprite_draw_indexed).",
                   "The descriptor holds two addresses, so it is filled in, field by field, when the sprite is drawn."]
        code = [f"enum {{ {upper}_WIDTH = {width}, {upper}_HEIGHT = {height} }};",
                f"static const uint16_t {name}_palette[{len(colors)}] = {{",
                *_numbers([_rgb565(color) for color in colors], 4, 8), "};",
                f"static const uint8_t {name}_indices[{len(data)}] = {{",
                *_numbers(list(data), 2, 16), "};",
                f"void {name}_draw(int x, int y) {{",
                "    prg32_indexed_sprite_t sprite;",
                f"    sprite.pixels = {name}_indices; sprite.palette = {name}_palette;",
                f"    sprite.width = {width}; sprite.height = {height}; sprite.frame_count = 1;",
                f"    sprite.palette_count = {len(colors)}; sprite.bits_per_pixel = {bits}; "
                f"sprite.transparent_index = {transparent};",
                "    prg32_sprite_draw_indexed(x, y, &sprite, 0);",
                "}"]
        return comment, code
    key = _transparent_key(sprite)
    flat = [key if color == "transparent" else _rgb565(color) for row in sprite["pixels"] for color in row]
    comment = [f"Sprite {title!r}: {width}x{height} pixels, direct colours (RGB565, 2 bytes per pixel, "
               f"{2 * width * height} bytes); 0x{key:04X} marks the see-through pixels.",
               f"{name}_draw(x, y) draws it with its top-left corner at x, y (prg32_sprite_draw_frame)."]
    code = [f"enum {{ {upper}_WIDTH = {width}, {upper}_HEIGHT = {height} }};",
            f"static const uint16_t {name}_pixels[{width * height}] = {{", *_numbers(flat, 4, max(1, min(width, 16))), "};",
            f"void {name}_draw(int x, int y) {{",
            f"    prg32_sprite_draw_frame(x, y, {width}, {height}, {name}_pixels, 0, 0x{key:04X});",
            "}"]
    return comment, code


def _background_c(background: dict[str, Any]) -> tuple[list[str], list[str]]:
    name, tiles = background["name"], background["tiles"]
    width, height, layers = background["width"], background["height"], background["layers"]
    count = len(tiles)
    flagged = any(tile["flags"] for tile in tiles)
    comment = [f"Background {background['title']!r}: {count} tile(s) of 8x8 pixels, a {width}x{height} map, "
               f"{len(layers)} layer(s).",
               f"{name}_load() defines the tiles and fills the playfield (call it once, in init); "
               f"{name}_draw() draws the layers (every frame, in draw)."
               + (" Its tiles have flags for the platform helpers." if flagged else "")]
    code: list[str] = []
    if count:
        code += [f"static const uint8_t {name}_tile_ids[{count}] = {{ {', '.join(str(t['id']) for t in tiles)} }};",
                 f"static const uint8_t {name}_tiles[{count}][8] = {{"]
        code += [f"    {{ {', '.join(f'0x{row:02X}' for row in tile['rows'])} }}" + ("," if i < count - 1 else "")
                 for i, tile in enumerate(tiles)]
        code += ["};", f"static const uint16_t {name}_tile_colors[{count}][2] = {{"]
        code += [f"    {{ 0x{_rgb565(tile['fg']):04X}, 0x{_rgb565(tile['bg']):04X} }}" + ("," if i < count - 1 else "")
                 for i, tile in enumerate(tiles)]
        code.append("};")
        if flagged:
            code.append(f"static const uint8_t {name}_tile_flags[{count}] = {{ "
                        + ", ".join(str(sum(FLAGS[flag] for flag in tile["flags"])) for tile in tiles) + " };")
    for number, layer in enumerate(layers):
        code.append(f"static const uint8_t {name}_layer{number}[{height}][{width}] = {{")
        code += [f"    {{ {', '.join(str(cell) for cell in row)} }}" + ("," if y < height - 1 else "")
                 for y, row in enumerate(layer)]
        code.append("};")
    code.append(f"void {name}_load(void) {{")
    if count:
        code += [f"    for (int i = 0; i < {count}; i++) {{",
                 f"        prg32_tile_define({name}_tile_ids[i], {name}_tiles[i], {name}_tile_colors[i][0], "
                 f"{name}_tile_colors[i][1]);"]
        if flagged:
            code.append(f"        prg32_platform_tile_flags({name}_tile_ids[i], {name}_tile_flags[i]);")
        code.append("    }")
    for number in range(len(layers)):
        code += [f"    prg32_playfield_clear({number}, 0);",
                 f"    for (int y = 0; y < {height}; y++) {{",
                 f"        for (int x = 0; x < {width}; x++) {{",
                 f"            prg32_playfield_put({number}, (uint8_t)x, (uint8_t)y, {name}_layer{number}[y][x]);",
                 "        }", "    }"]
    code += ["}", f"void {name}_draw(void) {{", "    prg32_playfield_draw(0, 0);"]
    if len(layers) > 1:
        code.append("    prg32_playfield_draw(1, 1);")
    code.append("}")
    return comment, code


def _sounds_c(assets: dict[str, Any]) -> list[tuple[list[str], list[str]]]:
    parts = []
    for effect in assets.get("effects") or []:
        parts.append(([f"Sound effect {effect['title']!r}: instrument {effect['instrument']} on voice "
                       f"{effect['voice']}, note {effect['note']}, volume {effect['volume']}, {effect['ms']} ms."],
                      [f"void {effect['name']}(void) {{ prg32_audio_note({effect['voice']}, {effect['instrument']}, "
                       f"{effect['note']}, {effect['volume']}, {effect['ms']}); }}"]))
    tracks = assets.get("soundtracks") or []
    if tracks:
        parts.append((["Soundtracks: start one with prg32_audio_play_track(TRACK_...), stop it with "
                       "prg32_audio_stop_track()."],
                      ["enum { " + ", ".join(f"{track['name']} = {track['track']}" for track in tracks) + " };"]))
    return parts


def c_parts(assets: dict[str, Any] | None, sounds: bool = True) -> list[tuple[list[str], list[str]]]:
    """Every piece of art as (comment lines, C lines), in catalog order."""
    assets = assets or {}
    parts = [_sprite_c(sprite) for sprite in assets.get("sprites") or []]
    parts += [_background_c(background) for background in assets.get("backgrounds") or []]
    if sounds:
        parts += _sounds_c(assets)
    return parts


def c_lines(assets: dict[str, Any] | None, sounds: bool = True) -> list[str]:
    """The art as readable C: each piece under its comment (the generated game.c, prg32_assets.h)."""
    from .generator import c_comment_block

    lines: list[str] = []
    for comment, code in c_parts(assets, sounds):
        lines += [*c_comment_block(" ".join(comment)), *code, ""]
    return lines


def c_header(assets: dict[str, Any] | None) -> str:
    """prg32_assets.h as the IDE shows it: what replaces the include line, laid out and explained."""
    body = c_lines(assets)
    return "\n".join([
        "/*",
        " * prg32_assets.h: this project's art as C, made by PRG32-Construction-Kit.",
        " * Read-only. Change the art in Sprite Lab, Backgrounds and AudioStudio.",
        " *",
        " * Write  #include \"prg32_assets.h\"  in game.c, below  #include \"prg32.h\".",
        " * When the game is built, that line is replaced by the code below, written on that",
        " * same line, so every other line of game.c keeps its number.",
        " */",
        "",
        *(body or ["/* This project has no sprites, backgrounds or sounds yet. */", ""]),
    ]).rstrip() + "\n"


def _one_line(code: list[str]) -> str:
    return " ".join(line.strip() for line in code if line.strip())


def expand_c(source: str, assets: dict[str, Any] | None) -> str:
    """game.c as the compiler reads it: the include line replaced by the art, on that line."""
    if not C_INCLUDE_LINE.search(source):
        return source
    text = _one_line([line for _comment, code in c_parts(assets) for line in code])
    return C_INCLUDE_LINE.sub(lambda _match: text, source)


# ---------------------------------------------------------------------------
# The art as RISC-V assembly: the same calls, in the same order, as the C
# ---------------------------------------------------------------------------

def _half(values: list[int], per_line: int, note: str) -> list[tuple[str, str]]:
    rows = [values[start:start + per_line] for start in range(0, len(values), per_line)]
    return [(".half " + ", ".join(f"0x{value:04X}" for value in row), note if index == 0 else "")
            for index, row in enumerate(rows)]


def _byte(values: list[int], per_line: int, note: str, hexadecimal: bool = True) -> list[tuple[str, str]]:
    rows = [values[start:start + per_line] for start in range(0, len(values), per_line)]
    show = (lambda value: f"0x{value:02X}") if hexadecimal else str
    return [(".byte " + ", ".join(show(value) for value in row), note if index == 0 else "")
            for index, row in enumerate(rows)]


def _sprite_asm(sprite: dict[str, Any]) -> tuple[list[str], list[Any], list[Any]]:
    """(comment, read-only data rows, code rows) of one sprite."""
    from .sprite_palette import bits_per_pixel, packed

    comment, _code = _sprite_c(sprite)
    name, width, height = sprite["name"], sprite["width"], sprite["height"]
    upper = name.upper()
    consts = [(f".equ {upper}_WIDTH, {width}", "pixels across"), (f".equ {upper}_HEIGHT, {height}", "pixels down")]
    if sprite.get("palette"):
        palette = sprite["palette"]
        colors, bits = palette["colors"], bits_per_pixel(len(palette["colors"]))
        data = list(packed(palette))
        data_rows = [*consts, (".balign 2", "halfwords start at even addresses"), f"{name}_palette:",
                     *_half([_rgb565(color) for color in colors], 8, "the palette, RGB565"),
                     f"{name}_indices:", *_byte(data, 16, f"{bits} bit(s) per pixel, packed")]
        code = [f"{name}_draw:",
                ("addi sp, sp, -32", "room for the 20-byte descriptor and ra"),
                ("sw ra, 28(sp)", "save the return address: we call the firmware"),
                (f"la t0, {name}_indices", "the packed pixels"), ("sw t0, 0(sp)", "descriptor.pixels"),
                (f"la t0, {name}_palette", "the palette"), ("sw t0, 4(sp)", "descriptor.palette"),
                (f"li t0, {width}", "width"), ("sh t0, 8(sp)", "descriptor.width"),
                (f"li t0, {height}", "height"), ("sh t0, 10(sp)", "descriptor.height"),
                ("li t0, 1", "one frame"), ("sh t0, 12(sp)", "descriptor.frame_count"),
                (f"li t0, {len(colors)}", "palette entries"), ("sh t0, 14(sp)", "descriptor.palette_count"),
                (f"li t0, {bits}", "bits per pixel"), ("sb t0, 16(sp)", "descriptor.bits_per_pixel"),
                (f"li t0, {palette['transparent_index']}", "see-through entry (-1: none)"),
                ("sh t0, 18(sp)", "descriptor.transparent_index"),
                ("mv a2, sp", "a2 = &descriptor (a0 = x, a1 = y are already set)"),
                ("li a3, 0", "frame 0"),
                ("call prg32_sprite_draw_indexed", "the firmware draws it"),
                ("lw ra, 28(sp)", "restore the return address"), ("addi sp, sp, 32", "free the frame"),
                ("ret", "back to the caller")]
        return comment, data_rows, code
    key = _transparent_key(sprite)
    flat = [key if color == "transparent" else _rgb565(color) for row in sprite["pixels"] for color in row]
    data_rows = [*consts, (".balign 2", "halfwords start at even addresses"), f"{name}_pixels:",
                 *_half(flat, max(1, min(width, 16)), "one RGB565 colour per pixel, row after row")]
    code = [f"{name}_draw:",
            (f"li a2, {width}", "a2 = width (a0 = x, a1 = y are already set)"),
            (f"li a3, {height}", "a3 = height"),
            (f"la a4, {name}_pixels", "a4 = the pixels"),
            ("li a5, 0", "a5 = frame 0"),
            (f"li a6, 0x{key:04X}", "a6 = the see-through colour"),
            ("tail prg32_sprite_draw_frame", "the firmware draws it and returns to our caller")]
    return comment, data_rows, code


def _background_asm(background: dict[str, Any]) -> tuple[list[str], list[Any], list[Any]]:
    comment, _code = _background_c(background)
    name, tiles = background["name"], background["tiles"]
    width, height, layers = background["width"], background["height"], background["layers"]
    count = len(tiles)
    flagged = any(tile["flags"] for tile in tiles)
    data: list[Any] = []
    if count:
        data += [f"{name}_tile_ids:", *_byte([tile["id"] for tile in tiles], 16, "tile numbers", False),
                 f"{name}_tiles:", *[(".byte " + ", ".join(f"0x{row:02X}" for row in tile["rows"]),
                                      f"tile {tile['id']}: 8 rows") for tile in tiles],
                 (".balign 2", ""), f"{name}_tile_colors:",
                 *[(f".half 0x{_rgb565(tile['fg']):04X}, 0x{_rgb565(tile['bg']):04X}",
                    f"tile {tile['id']}: foreground, background") for tile in tiles]]
        if flagged:
            data += [f"{name}_tile_flags:",
                     *_byte([sum(FLAGS[flag] for flag in tile["flags"]) for tile in tiles], 16, "flags", False)]
    for number, layer in enumerate(layers):
        data.append(f"{name}_layer{number}:")
        data += [(".byte " + ", ".join(str(cell) for cell in row), f"row {y}" if y == 0 else "")
                 for y, row in enumerate(layer)]
    code: list[Any] = [f"{name}_load:",
                       ("addi sp, sp, -16", "a stack frame"), ("sw ra, 12(sp)", "save the return address"),
                       ("sw s0, 8(sp)", "s0..s2 count; the caller expects them unchanged"),
                       ("sw s1, 4(sp)", ""), ("sw s2, 0(sp)", "")]
    if count:
        code += [("li s0, 0", "s0 = i, the tile"), f"{name}_load_tile:",
                 (f"la t0, {name}_tile_ids", ""), ("add t0, t0, s0", ""), ("lbu a0, 0(t0)", "a0 = tile number"),
                 (f"la a1, {name}_tiles", ""), ("slli t1, s0, 3", "8 bytes per tile"),
                 ("add a1, a1, t1", "a1 = its 8 rows"),
                 (f"la t0, {name}_tile_colors", ""), ("slli t1, s0, 2", "4 bytes per tile"), ("add t0, t0, t1", ""),
                 ("lhu a2, 0(t0)", "a2 = foreground"), ("lhu a3, 2(t0)", "a3 = background"),
                 ("call prg32_tile_define", "store the tile")]
        if flagged:
            code += [(f"la t0, {name}_tile_ids", ""), ("add t0, t0, s0", ""), ("lbu a0, 0(t0)", "a0 = tile number"),
                     (f"la t0, {name}_tile_flags", ""), ("add t0, t0, s0", ""), ("lbu a1, 0(t0)", "a1 = its flags"),
                     ("call prg32_platform_tile_flags", "for the platform helpers")]
        code += [("addi s0, s0, 1", "next tile"), (f"li t0, {count}", ""),
                 (f"blt s0, t0, {name}_load_tile", "until every tile is defined")]
    for number in range(len(layers)):
        rows, cells = f"{name}_load_rows{number}", f"{name}_load_cells{number}"
        code += [(f"li a0, {number}", f"layer {number}"), ("li a1, 0", "tile 0: empty"),
                 ("call prg32_playfield_clear", "empty the layer"),
                 ("li s1, 0", "s1 = y"), f"{rows}:", ("li s2, 0", "s2 = x"), f"{cells}:",
                 (f"li t0, {width}", "tiles per row"), ("mul t0, s1, t0", "y * width"), ("add t0, t0, s2", "+ x"),
                 (f"la t1, {name}_layer{number}", ""), ("add t1, t1, t0", ""), ("lbu a3, 0(t1)", "a3 = the tile there"),
                 (f"li a0, {number}", "a0 = layer"), ("mv a1, s2", "a1 = x"), ("mv a2, s1", "a2 = y"),
                 ("call prg32_playfield_put", "place it"),
                 ("addi s2, s2, 1", "next column"), (f"li t0, {width}", ""), (f"blt s2, t0, {cells}", ""),
                 ("addi s1, s1, 1", "next row"), (f"li t0, {height}", ""), (f"blt s1, t0, {rows}", "")]
    code += [("lw s2, 0(sp)", "restore s2"), ("lw s1, 4(sp)", "restore s1"), ("lw s0, 8(sp)", "restore s0"),
             ("lw ra, 12(sp)", "restore the return address"), ("addi sp, sp, 16", "free the frame"),
             ("ret", "back to the caller"),
             f"{name}_draw:", ("addi sp, sp, -16", "a stack frame"), ("sw ra, 12(sp)", "save the return address"),
             ("li a0, 0", "layer 0"), ("li a1, 0", "every tile drawn"), ("call prg32_playfield_draw", "")]
    if len(layers) > 1:
        code += [("li a0, 1", "layer 1, in front"), ("li a1, 1", "tile 0 lets layer 0 show through"),
                 ("call prg32_playfield_draw", "")]
    code += [("lw ra, 12(sp)", "restore the return address"), ("addi sp, sp, 16", "free the frame"),
             ("ret", "back to the caller")]
    return comment, data, code


def _sounds_asm(assets: dict[str, Any]) -> list[tuple[list[str], list[Any], list[Any]]]:
    parts = []
    for comment, _code in _sounds_c(assets):
        parts.append((comment, [], []))
    for index, effect in enumerate(assets.get("effects") or []):
        parts[index] = (parts[index][0], [], [
            f"{effect['name']}:",
            (f"li a0, {effect['voice']}", "a0 = voice"), (f"li a1, {effect['instrument']}", "a1 = instrument"),
            (f"li a2, {effect['note']}", "a2 = note"), (f"li a3, {effect['volume']}", "a3 = volume"),
            (f"li a4, {effect['ms']}", "a4 = milliseconds"),
            ("tail prg32_audio_note", "the firmware plays it and returns to our caller")])
    tracks = assets.get("soundtracks") or []
    if tracks:
        parts[-1] = (parts[-1][0], [(f".equ {track['name']}, {track['track']}", f"soundtrack {track['title']}")
                                    for track in tracks], [])
    return parts


def asm_parts(assets: dict[str, Any] | None, sounds: bool = True) -> list[tuple[list[str], list[Any], list[Any]]]:
    """Every piece of art as (comment lines, read-only data rows, code rows), in catalog order."""
    assets = assets or {}
    parts = [_sprite_asm(sprite) for sprite in assets.get("sprites") or []]
    parts += [_background_asm(background) for background in assets.get("backgrounds") or []]
    if sounds:
        parts += _sounds_asm(assets)
    return parts


def asm_lines(assets: dict[str, Any] | None, sounds: bool = True) -> tuple[list[str], list[str]]:
    """The art as readable assembly: (read-only data lines, code lines), each piece under its comment."""
    from .asm_generator import asm_rows, comment_block

    data: list[str] = []
    code: list[str] = []
    for comment, data_rows, code_rows in asm_parts(assets, sounds):
        if data_rows:
            data += [*comment_block([" ".join(comment)]), *asm_rows(data_rows)]
        if code_rows:
            code += [*comment_block([" ".join(comment)]), *asm_rows(code_rows), ""]
    return data, code


def asm_include(assets: dict[str, Any] | None) -> str:
    """prg32_assets.S as the IDE shows it: what replaces the include line, laid out and explained."""
    from .asm_generator import asm_line

    data, code = asm_lines(assets)
    lines = ["/*",
             " * prg32_assets.S: this project's art as RISC-V assembly, made by PRG32-Construction-Kit.",
             " * Read-only. Change the art in Sprite Lab, Backgrounds and AudioStudio.",
             " *",
             " * Write  #include \"prg32_assets.S\"  in game.S, on a line of its own. When the game is",
             " * built, that line is replaced by the code below, written on that same line, so every",
             " * other line of game.S keeps its number. .pushsection and .popsection put the art in",
             " * its own sections and then go back to the section the line was in.",
             " * Every function follows the calling convention: inputs in a0.., ra, s-registers kept.",
             " */"]
    if not data and not code:
        return "\n".join(lines + ["/* This project has no sprites, backgrounds or sounds yet. */"]) + "\n"
    if data:
        lines += [asm_line(".pushsection .rodata", "read-only data: pictures, maps, numbers"), *data,
                  asm_line(".popsection", "back to the section we were in")]
    if code:
        lines += [asm_line(".pushsection .text", "code"), asm_line(".balign 4", ""), *code,
                  asm_line(".popsection", "back to the section we were in")]
    return "\n".join(lines).rstrip() + "\n"


def expand_asm(source: str, assets: dict[str, Any] | None) -> str:
    """game.S as the assembler reads it: the include line replaced by the art, on that line."""
    if not ASM_INCLUDE_LINE.search(source):
        return source
    statements: list[str] = []
    data_rows: list[Any] = []
    code_rows: list[Any] = []
    for _comment, data, code in asm_parts(assets):
        data_rows += data
        code_rows += code
    plain = lambda rows: [row if isinstance(row, str) else row[0] for row in rows]  # noqa: E731
    if data_rows:
        statements += [".pushsection .rodata", *plain(data_rows), ".popsection"]
    if code_rows:
        statements += [".pushsection .text", ".balign 4", *plain(code_rows), ".popsection"]
    text = " ; ".join(statements)
    return ASM_INCLUDE_LINE.sub(lambda _match: text, source)


# ---------------------------------------------------------------------------
# Checking the include line in student code
# ---------------------------------------------------------------------------

def check_include(source: str, language: str) -> bool:
    """Whether a C or assembly source includes the art; ValueError when the line is written wrongly.

    The include must be a line of its own (no comment or line continuation on it), at most
    once, and in C below ``#include "prg32.h"``.
    """
    from .source_project import _without_comments

    directive, raw = (C_DIRECTIVE, C_INCLUDE_LINE) if language == "c" else (ASM_DIRECTIVE, ASM_INCLUDE_LINE)
    header = C_INCLUDE if language == "c" else ASM_INCLUDE
    code_lines = [re.sub(r"^\s*%:", "#", line) for line in _without_comments(source).splitlines()]
    found = [index for index, line in enumerate(code_lines) if directive.match(line)]
    if not found:
        return False
    if len(found) > 1:
        raise AssetsError(say("assets", "Include {header} only once", header=header))
    if len(raw.findall(source)) != 1:
        raise AssetsError(say("assets", "Write #include \"{header}\" on a line of its own, without a comment", header=header))
    if language == "c":
        prg32 = next((index for index, line in enumerate(code_lines)
                      if re.match(r'^\s*#\s*include\s*[<"]prg32\.h[>"]\s*$', line)), None)
        if prg32 is None or prg32 > found[0]:
            raise AssetsError(say("assets", "Write #include \"prg32.h\" above #include \"prg32_assets.h\""))
    return True


def blank_include(source: str) -> str:
    """Assembly with its art include line emptied, for the checks that refuse every other include."""
    return ASM_INCLUDE_LINE.sub("", source)


# ---------------------------------------------------------------------------
# How to use each piece of art, in each kind of project (Sprite Lab, Backgrounds, AudioStudio)
# ---------------------------------------------------------------------------

def usage(assets: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    """For every piece of art, the line that uses it: Blocks, PRG32 Python, C and assembly."""
    def quoted(title: str) -> str:
        return '"' + title.replace("\\", "\\\\").replace('"', '\\"') + '"'

    out: dict[str, list[dict[str, str]]] = {"sprites": [], "backgrounds": [], "effects": [], "soundtracks": []}
    for sprite in assets.get("sprites") or []:
        name, title = sprite["name"], sprite["title"]
        out["sprites"].append({"title": title, "name": name,
                               "blocks": f"draw sprite {title} x 10 y 20",
                               "python": f"prg32.sprite({quoted(title)}, 10, 20)",
                               "c": f"{name}_draw(10, 20);",
                               "asm": f"li a0, 10\nli a1, 20\ncall {name}_draw"})
    for background in assets.get("backgrounds") or []:
        name, title = background["name"], background["title"]
        out["backgrounds"].append({"title": title, "name": name,
                                   "blocks": f"load background {title}  /  draw background {title}",
                                   "python": f"prg32.background_load({quoted(title)})\n"
                                             f"prg32.background_draw({quoted(title)})",
                                   "c": f"{name}_load();   /* in init */\n{name}_draw();   /* in draw */",
                                   "asm": f"call {name}_load   # in init\ncall {name}_draw   # in draw"})
    for effect in assets.get("effects") or []:
        out["effects"].append({"title": effect["title"], "name": effect["name"],
                               "blocks": f"play sound effect {effect['title']}",
                               "python": f"prg32.sound_effect({quoted(effect['title'])})",
                               "c": f"{effect['name']}();", "asm": f"call {effect['name']}"})
    for track in assets.get("soundtracks") or []:
        out["soundtracks"].append({"title": track["title"], "name": track["name"],
                                   "blocks": f"play soundtrack {track['title']}",
                                   "python": f"prg32.soundtrack_play({quoted(track['title'])})",
                                   "c": f"prg32_audio_play_track({track['name']});",
                                   "asm": f"li a0, {track['name']}\ncall prg32_audio_play_track"})
    return out


def public(assets: dict[str, Any]) -> dict[str, Any]:
    """What the IDE gets: the catalog, the two read-only files and how to use each piece."""
    return {"catalog": assets, "c_header": c_header(assets), "asm_include": asm_include(assets),
            "usage": usage(assets), "features": sorted(features(assets)), "files": {"c": C_INCLUDE, "asm": ASM_INCLUDE}}
