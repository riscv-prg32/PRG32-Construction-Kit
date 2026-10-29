"""Indexed-colour sprites: a palette and one palette index per pixel (docs/sprite_editor.md).

A sprite is either **direct** (each pixel is its own colour, ``pixels`` as ``#rrggbb``) or
**indexed**: a palette of up to 256 colours and, for each pixel, the number of its palette entry.
An indexed sprite is what the PRG32 draws with ``prg32_sprite_draw_indexed``
(``prg32_indexed_sprite_t``, prg32.h): it needs 1, 2, 4 or 8 bits per pixel instead of 16, and
changing one palette entry recolours every pixel that uses it.

The ``palette`` field of a sprite is ``{}`` for a direct sprite, or::

    {"mode": "indexed", "colors": ["#000000", "#ffd800", ...], "transparent_index": 0 or -1,
     "indices": [[0, 1, 1, ...], ...]}

``indices`` is the source of truth of an indexed sprite. ``pixels`` stays the colour of every pixel
(``"transparent"`` for the transparent entry), so every reader of direct sprites (previews, PNG
export, the RGB565 C array) keeps working.
"""

from __future__ import annotations

import re
from typing import Any

from .messages import text as say

MAX_COLORS = 256
_HEX = re.compile(r"^#[0-9a-f]{6}$")


class PaletteError(ValueError):
    pass


def bits_per_pixel(color_count: int) -> int:
    """The smallest PRG32 packing (1, 2, 4 or 8 bits) that holds ``color_count`` palette entries."""
    for bits in (1, 2, 4, 8):
        if color_count <= 1 << bits:
            return bits
    raise PaletteError(say("sprite", "A palette has at most 256 colours."))


def checked(palette: Any, width: int, height: int) -> dict[str, Any]:
    """The palette field, normalised, or PaletteError saying what is wrong."""
    if palette in (None, {}):
        return {}
    if not isinstance(palette, dict) or palette.get("mode") != "indexed":
        raise PaletteError(say("sprite", "The palette must be empty (direct colours) or an indexed palette."))
    colors = palette.get("colors")
    if not isinstance(colors, list) or not 1 <= len(colors) <= MAX_COLORS:
        raise PaletteError(say("sprite", "An indexed sprite needs 1 to 256 palette colours."))
    colors = [str(color).lower() for color in colors]
    if not all(_HEX.match(color) for color in colors):
        raise PaletteError(say("sprite", "Palette colours must look like #rrggbb."))
    transparent = palette.get("transparent_index", -1)
    if not isinstance(transparent, int) or isinstance(transparent, bool) or not -1 <= transparent < len(colors):
        raise PaletteError(say("sprite", "The transparent colour must be none (-1) or a palette entry."))
    indices = palette.get("indices")
    if not isinstance(indices, list) or len(indices) != height or any(
            not isinstance(row, list) or len(row) != width for row in indices):
        raise PaletteError(say("sprite", "The pixels must be {height} rows of {width} palette entries.", height=height, width=width))
    for row in indices:
        for value in row:
            if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < len(colors):
                raise PaletteError(say("sprite", "Every pixel must use a palette entry (0 to the number of colours - 1)."))
    return {"mode": "indexed", "colors": colors, "transparent_index": transparent, "indices": indices}


def pixels_of(palette: dict[str, Any]) -> list[list[str]]:
    """The colour of every pixel of an indexed sprite, as direct sprites store them."""
    colors, transparent = palette["colors"], palette["transparent_index"]
    return [["transparent" if value == transparent else colors[value] for value in row] for row in palette["indices"]]


def packed(palette: dict[str, Any]) -> bytes:
    """The indices as the PRG32 reads them: densely packed across the frame, most significant first
    (``(pixels x bits + 7) / 8`` bytes; prg32.h, PRG32_SPRITE_BPP_*)."""
    bits = bits_per_pixel(len(palette["colors"]))
    out, current, filled = bytearray(), 0, 0
    for row in palette["indices"]:
        for value in row:
            current = (current << bits) | value
            filled += bits
            if filled == 8:
                out.append(current)
                current, filled = 0, 0
    if filled:
        out.append(current << (8 - filled))
    return bytes(out)
