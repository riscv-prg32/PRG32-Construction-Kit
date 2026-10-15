#!/usr/bin/env python3
"""Refresh the game tutorials and build them into HTML slide decks.

Each tutorial is one Markdown file in ``docs/tutorials/games/``. Slides are
separated by ``---`` lines (the Marp convention), so the same file reads as a
handout on GitHub and presents as slides.

Block listings and C excerpts are never typed by hand. A tutorial asks for
them with marker comments, and this tool fills the space between the markers
from the example game's Blocks JSON and its generated C:

    <!-- blocks: pong update "The player moves" -->
    <!-- /blocks -->

    <!-- c: pong "The player moves" -->
    <!-- /c -->

The anchor text is the start of a comment block in the game: the excerpt is
that comment and the blocks after it, up to the next comment block. Run

    python3 tools/build_presentations.py

after changing a game or a tutorial. It rewrites the Markdown in place and
writes ``docs/presentations/<name>.html``; the test suite checks both are up
to date.
"""

from __future__ import annotations

import colorsys
import html
import json
import re
import sys
import types
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent.parent
TUTORIALS = ROOT / "docs" / "tutorials" / "games"
DECKS = ROOT / "docs" / "presentations"
_package = types.ModuleType("prg32_construction_kit")
_package.__path__ = [str(ROOT / "prg32_construction_kit")]
sys.modules.setdefault("prg32_construction_kit", _package)

from prg32_construction_kit.generator import blocks_to_c  # noqa: E402

REGION = re.compile(r"<!-- (blocks|c): (\w+)(?: (\w+))?(?: \"([^\"]*)\")?(?: depth (\d+))?(?: lines (\d+))? -->\n(.*?)<!-- /\1 -->", re.S)

LABELS = {
    "prg32_on_start": "when game starts", "prg32_update": "every frame update", "prg32_draw": "every frame draw",
    "prg32_comment": "comment {TEXT}",
    "prg32_splash": "show splash title {TITLE} subtitle {SUBTITLE} for {MS} ms",
    "prg32_set_state": "set {VAR} to {VALUE}", "prg32_change_state": "change {VAR} by {DELTA}",
    "prg32_clamp_state": "keep {VAR} between {LOW} and {HIGH}", "prg32_wrap_state": "wrap {VAR} around {LOW} to {HIGH}",
    "prg32_random_state": "set {VAR} to random from {LOW} to {HIGH}",
    "prg32_list_create": "make list {LIST} with {SIZE} items, all {VALUE}",
    "prg32_list_set": "set item {INDEX} of {LIST} to {VALUE}", "prg32_list_change": "change item {INDEX} of {LIST} by {DELTA}",
    "prg32_if": "if {COND}", "prg32_if_else": "if {COND}", "prg32_repeat": "repeat with {VAR} from {FROM} to {TO}",
    "prg32_if_touching": "if rect {AX} {AY} {AW} {AH} touches rect {BX} {BY} {BW} {BH}",
    "prg32_if_button": "if button {BUTTON} is held", "prg32_if_button_once": "if button {BUTTON} was just pressed",
    "prg32_clear_screen": "clear screen {COLOR}",
    "prg32_draw_rect": "draw rectangle x {X} y {Y} w {W} h {H} color {COLOR}",
    "prg32_draw_frame": "draw outline x {X} y {Y} w {W} h {H} color {COLOR}",
    "prg32_draw_rect_rgb": "draw rectangle x {X} y {Y} w {W} h {H} color value {RGB}",
    "prg32_draw_pixel": "draw pixel x {X} y {Y} color {COLOR}",
    "prg32_draw_line": "draw line from x {X1} y {Y1} to x {X2} y {Y2} color {COLOR}",
    "prg32_draw_circle": "draw {FILL} circle x {X} y {Y} radius {R} color {COLOR}",
    "prg32_draw_text": "draw text {TEXT} at x {X} y {Y} fg {FG} bg {BG}",
    "prg32_draw_number": "draw number {VALUE} at x {X} y {Y} fg {FG} bg {BG}",
    "prg32_draw_bitmap": "draw picture x {X} y {Y} color {COLOR} size {SCALE}",
    "prg32_draw_sprite8": "draw 8x8 sprite x {X} y {Y} fg {FG} bg {BG}",
    "prg32_tile_define": "define tile {ID} fg {FG} bg {BG}",
    "prg32_playfield_clear": "fill playfield layer {LAYER} with tile {ID}",
    "prg32_playfield_put": "put tile {ID} on layer {LAYER} at column {TX} row {TY}",
    "prg32_playfield_scroll": "scroll playfield layer {LAYER} to x {X} y {Y}",
    "prg32_playfield_camera": "move playfield camera to x {X} y {Y}",
    "prg32_playfield_draw": "draw playfield layer {LAYER} {TRANSPARENT}",
    "prg32_palette_set": "palette index {INDEX} color {COLOR}",
    "prg32_clear_indexed": "clear screen with palette index {INDEX}",
    "prg32_draw_rect_indexed": "draw indexed rectangle x {X} y {Y} w {W} h {H} index {INDEX}",
    "prg32_draw_pixel_indexed": "draw indexed pixel x {X} y {Y} index {INDEX}",
    "prg32_play_beep": "play beep freq {FREQ} ms {MS}",
    "prg32_audio_note": "play MIDI note {NOTE} on channel {CHANNEL} for {MS} ms",
    "prg32_audio_stop": "stop sound on channel {CHANNEL}", "prg32_audio_volume": "set master volume to {VOLUME}",
    "prg32_band_text": "show in status band {TEXT} number {VALUE}", "prg32_score_submit": "save high score {VALUE}",
    "prg32_scoreboard_show": "show scoreboard titled {TITLE}", "prg32_player_name": "ask the player's name",
    "prg32_mp_join": "join multiplayer game", "prg32_mp_share": "share my position x {X} y {Y} look {LOOK}",
}
DROPDOWN_FIELDS = {"BUTTON", "COLOR", "FG", "BG", "ACCENT", "FILL", "TRANSPARENT"}
DROPDOWN_WORDS = {"OPAQUE": "opaque", "TRANSPARENT": "tile 0 see-through", "OUTLINE": "outline", "FILLED": "filled"}
# Blockly hues of the toolbox categories (static/js/blockly_blocks.js).
HUES = {
    "prg32_on_start": 40, "prg32_splash": 40, "prg32_update": 210, "prg32_draw": 160, "prg32_comment": 90,
    "state": 260, "list": 290, "logic": 15, "input": 20, "draw": 160, "sprite": 330, "palette": 180, "sound": 300,
    "score": 60, "mp": 230,
}


def hue(block_type: str) -> int:
    if block_type in HUES:
        return HUES[block_type]
    for key, words in (("state", ("_state",)), ("list", ("_list_",)), ("input", ("if_button",)),
                       ("logic", ("prg32_if", "prg32_repeat")), ("sprite", ("sprite8", "tile_", "playfield")),
                       ("palette", ("palette", "indexed")), ("sound", ("beep", "audio")),
                       ("score", ("band", "score", "player_name")), ("mp", ("_mp_",))):
        if any(word in block_type for word in words):
            return HUES[key]
    return HUES["draw"]


def block_color(block_type: str) -> str:
    r, g, b = colorsys.hsv_to_rgb(hue(block_type) / 360, 0.45, 0.65)
    return f"#{int(r * 255):02x}{int(g * 255):02x}{int(b * 255):02x}"


def fields(block: dict) -> dict:
    out = {}
    for key, value in (block.get("fields") or {}).items():
        text = str(value)
        if key in DROPDOWN_FIELDS:
            text = DROPDOWN_WORDS.get(text, text.lower().replace("_", " "))
        out[key] = text
    return out


def label_parts(block: dict) -> list[tuple[str, str]]:
    """Split a block label into ('text', ...) and ('field', ...) parts."""
    template = LABELS.get(block["type"], block["type"])
    values = fields(block)
    if block["type"] == "prg32_band_text" and not values.get("VALUE"):
        template = "show in status band {TEXT}"
    parts: list[tuple[str, str]] = []
    for piece in re.split(r"(\{\w+\})", template):
        if piece.startswith("{") and piece.endswith("}"):
            parts.append(("field", values.get(piece[1:-1], "")))
        elif piece:
            parts.append(("text", piece))
    return parts


def picture_rows(block: dict) -> list[str] | None:
    if not any(f"ROW{i}" in (block.get("fields") or {}) for i in range(8)):
        return None
    return [str(block["fields"].get(f"ROW{i}", "........")) for i in range(8)]


def child(block: dict, name: str) -> dict | None:
    value = (block.get("inputs") or {}).get(name) or {}
    return value.get("block")


def chain_from(block: dict | None, stop_at_comment: bool) -> list[dict]:
    out = []
    first = True
    while block:
        if stop_at_comment and not first and block["type"] == "prg32_comment":
            break
        out.append(block)
        first = False
        block = (block.get("next") or {}).get("block")
    return out


def find_comment(block: dict | None, anchor: str) -> dict | None:
    while block:
        if block["type"] == "prg32_comment" and str(block["fields"].get("TEXT", "")).startswith(anchor):
            return block
        for value in (block.get("inputs") or {}).values():
            found = find_comment(value.get("block"), anchor)
            if found:
                return found
        block = (block.get("next") or {}).get("block")
    return None


# ---- plain text (Markdown) -------------------------------------------------
def block_text(block: dict, depth: int, max_depth: int = 99) -> list[str]:
    pad = "    " * depth
    label = "".join(text for _kind, text in label_parts(block))
    lines = [pad + label]
    rows = picture_rows(block)
    if rows:
        lines += [pad + "    " + row for row in rows]
    for name, title in (("DO", None), ("ELSE", "else")):
        body = child(block, name)
        if title and block["type"] == "prg32_if_else":
            lines.append(pad + title)
        if body and depth + 1 >= max_depth:
            lines.append(pad + "    ...")
        elif body:
            for inner in chain_from(body, False):
                lines += block_text(inner, depth + 1, max_depth)
    return lines


# ---- HTML (slides) ---------------------------------------------------------
def block_html(block: dict, depth: int = 0, max_depth: int = 99) -> str:
    color = block_color(block["type"])
    label = "".join(f'<span class="f">{html.escape(text)}</span>' if kind == "field" and text != "" else html.escape(text)
                    for kind, text in label_parts(block))
    rows = picture_rows(block)
    picture = ""
    if rows:
        cells = "".join(f'<i class="{"on" if ch not in ".-_ 0" else ""}"></i>' for row in rows for ch in row[:8].ljust(8, "."))
        picture = f'<span class="pic">{cells}</span>'
    inner = ""
    for name, title in (("DO", None), ("ELSE", "else")):
        body = child(block, name)
        if block["type"] in {"prg32_if_else"} and title:
            inner += f'<div class="blk-label" style="background:{color}">else</div>'
        if body or (name == "DO" and block["type"] in {"prg32_if", "prg32_if_else", "prg32_repeat", "prg32_if_button",
                                                       "prg32_if_button_once", "prg32_if_touching"}):
            if body and depth + 1 >= max_depth:
                content = '<div class="blk more">&hellip;</div>'
            else:
                content = "".join(block_html(b, depth + 1, max_depth) for b in chain_from(body, False))
            inner += f'<div class="blk-body" style="border-color:{color}">{content}</div>'
    kind = "blk comment" if block["type"] == "prg32_comment" else "blk"
    return f'<div class="{kind}"><div class="blk-label" style="background:{color}">{label}{picture}</div>{inner}</div>'


# ---- excerpts --------------------------------------------------------------
_GAMES: dict[str, tuple[dict, str]] = {}


def game(name: str) -> tuple[dict, str]:
    if name not in _GAMES:
        path = ROOT / "examples" / "games" / f"{name}.json"
        if not path.exists():
            path = ROOT / "examples" / f"{name}.json"
        project = json.loads(path.read_text(encoding="utf-8"))["project"]
        _ir, source = blocks_to_c(project["blocks_json"], project)
        stacks = {top["type"].removeprefix("prg32_"): top for top in project["blocks_json"]["blocks"]["blocks"]}
        stacks["start"] = stacks.pop("on_start")
        _GAMES[name] = (stacks, source)
    return _GAMES[name]


def blocks_excerpt(name: str, stack: str, anchor: str | None) -> list[dict]:
    stacks, _source = game(name)
    top = stacks[stack]
    if not anchor:
        return [top]
    found = find_comment(child(top, "DO"), anchor)
    if not found:
        raise SystemExit(f"{name}: no comment block starting with {anchor!r} in {stack}")
    return chain_from(found, True)


def c_excerpt(name: str, anchor: str | None, function: str | None, max_lines: int | None = None) -> str:
    _stacks, source = game(name)
    lines = source.splitlines()
    if function == "bitmaps":
        keep = [i for i, line in enumerate(lines) if line.startswith("static const uint8_t prg32_kit_bitmap_")]
        return "\n".join(lines[j] for i in keep for j in (i - 1, i))
    if function:
        start = next(i for i, line in enumerate(lines) if line.startswith(f"void {name}_{function}(void)"))
        end = next(i for i in range(start, len(lines)) if lines[i] == "}")
        return "\n".join(lines[start:end + 1])
    start = next((i for i, line in enumerate(lines) if line.strip().startswith(f"/* {anchor}")), None)
    if start is None:
        raise SystemExit(f"{name}: no C comment starting with {anchor!r}")
    indent = len(lines[start]) - len(lines[start].lstrip())
    out = [lines[start]]
    for line in lines[start + 1:]:
        level = len(line) - len(line.lstrip())
        if not line.strip():
            break
        if level < indent or (level == indent and line.strip().startswith("/*")):
            break
        out.append(line)
    if max_lines and len(out) > max_lines:
        out = out[:max_lines] + [" " * (len(out[max_lines]) - len(out[max_lines].lstrip())) + "..."]
    return "\n".join(line[indent:] for line in out)


def fill_region(match: re.Match) -> str:
    kind, name, extra, anchor, depth, lines, _old = match.groups()
    head = match.group(0).split("\n", 1)[0]
    if kind == "blocks":
        limit = int(depth) if depth else 99
        text = "\n".join(line for block in blocks_excerpt(name, extra, anchor) for line in block_text(block, 0, limit))
        return f"{head}\n```text\n{text}\n```\n<!-- /blocks -->"
    code = c_excerpt(name, anchor, extra, int(lines) if lines else None)
    return f"{head}\n```c\n{code}\n```\n<!-- /c -->"


def refresh_markdown(text: str) -> str:
    return REGION.sub(fill_region, text)


# ---- slides ----------------------------------------------------------------
def split_front_matter(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---\n"):
        end = text.index("\n---\n", 4)
        for line in text[4:end].splitlines():
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()
        text = text[end + 5:]
    return meta, text


def slide_html(source: str) -> str:
    placeholders: dict[str, str] = {}

    def keep(match: re.Match) -> str:
        kind, name, extra, anchor, depth, lines, _old = match.groups()
        key = f"REGION{len(placeholders)}X"
        if kind == "blocks":
            limit = int(depth) if depth else 99
            placeholders[key] = '<div class="blocks">' + "".join(
                block_html(b, 0, limit) for b in blocks_excerpt(name, extra, anchor)) + "</div>"
        else:
            code = c_excerpt(name, anchor, extra, int(lines) if lines else None)
            placeholders[key] = f'<pre class="c"><code>{html.escape(code)}</code></pre>'
        return f"\n{key}\n"

    css_class = ""
    class_match = re.search(r"<!-- class: ([\w -]+) -->", source)
    if class_match:
        css_class = " " + class_match.group(1)
    body = REGION.sub(keep, source)
    columns = body.split("<!-- column -->")
    rendered = [markdown.markdown(part, extensions=["tables", "fenced_code"]) for part in columns]
    # Text before the first column marker spans the slide; each marker starts a column.
    content = rendered[0]
    if len(rendered) > 1:
        content += '<div class="cols">' + "".join(f'<div class="col">{part}</div>' for part in rendered[1:]) + "</div>"
    for key, value in placeholders.items():
        content = content.replace(f"<p>{key}</p>", value).replace(key, value)
    content = content.replace('src="../../figures/', 'src="../figures/').replace('href="../../', 'href="../')
    return f'<section class="slide{css_class}">\n{content}\n</section>'


def build_deck(path: Path, text: str | None = None) -> str:
    meta, body = split_front_matter(path.read_text(encoding="utf-8") if text is None else text)
    slides = [part for part in re.split(r"\n---\n", "\n" + body + "\n") if part.strip()]
    title = meta.get("title", path.stem)
    sections = "\n".join(slide_html(slide) for slide in slides)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="deck.css">
</head>
<body>
<!-- Built by tools/build_presentations.py from docs/tutorials/games/{path.name}; edit that file, not this one. -->
<main class="deck" data-title="{html.escape(title)}">
{sections}
</main>
<nav class="deck-bar" aria-label="Slide navigation">
  <button type="button" data-go="prev" aria-label="Previous slide">&#8592;</button>
  <span class="deck-title">{html.escape(title)}</span>
  <span class="deck-count"></span>
  <button type="button" data-go="next" aria-label="Next slide">&#8594;</button>
</nav>
<script src="deck.js"></script>
</body>
</html>
"""


def main(check: bool = False) -> int:
    changed = []
    for path in sorted(TUTORIALS.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        refreshed = refresh_markdown(text)
        if refreshed != text:
            changed.append(path)
            if not check:
                path.write_text(refreshed, encoding="utf-8")
        deck = DECKS / f"{path.stem}.html"
        built = build_deck(path, refreshed)
        if not deck.exists() or deck.read_text(encoding="utf-8") != built:
            changed.append(deck)
            if not check:
                DECKS.mkdir(parents=True, exist_ok=True)
                deck.write_text(built, encoding="utf-8")
    for path in changed:
        print(("out of date: " if check else "wrote ") + str(path.relative_to(ROOT)))
    return 1 if (check and changed) else 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
