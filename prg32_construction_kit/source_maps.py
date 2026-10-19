"""Block -> IR -> source maps for the debugger (ADR-0015).

A source map says, for every Blockly block, which IR statement it became and which
lines of the generated game.c (or game.S) hold that statement:

    {"schema": "prg32-source-map/1", "language": "c", "file": "game.c",
     "source_sha256": "...",
     "entries": [{"block": "a1b2", "ir": "update[0].then[1]", "op": "set", "lines": [41, 42]}, ...]}

How it is made, without changing the generated code: blocks_to_ir_traced notes which block
made each IR statement; the generators, given that note, wrap each statement's lines in
marker lines; strip_markers removes the markers and records where they were. The text
left over is exactly the normal output, which build_source_map checks every time.
Nested blocks (inside "if" or "repeat") have their own, smaller line ranges.
"""

from __future__ import annotations

import hashlib
from typing import Any

from .asm_generator import ir_to_asm
from .generator import MAP_BEGIN, MAP_END, blocks_to_ir_traced, ir_to_c

SCHEMA = "prg32-source-map/1"
PHASES = ("init", "update", "draw")
# The IR keys that hold nested statement lists.
NESTED = ("then", "else", "body", "do")


def ir_paths(game_ir: dict[str, Any]) -> dict[int, tuple[str, str]]:
    """id(statement) -> (IR path like "update[2].then[0]", op) for every IR statement."""
    paths: dict[int, tuple[str, str]] = {}

    def walk(statements: Any, prefix: str) -> None:
        for index, stmt in enumerate(statements if isinstance(statements, list) else []):
            if not isinstance(stmt, dict):
                continue
            path = f"{prefix}[{index}]"
            paths[id(stmt)] = (path, str(stmt.get("op", "")))
            for key in NESTED:
                if isinstance(stmt.get(key), list):
                    walk(stmt[key], f"{path}.{key}")

    for phase in PHASES:
        walk(game_ir.get(phase), phase)
    return paths


def strip_markers(text: str) -> tuple[str, list[tuple[str, int, int]]]:
    """Remove marker lines; return the clean text and (block id, first line, last line) spans."""
    clean: list[str] = []
    open_spans: list[tuple[str, int]] = []
    spans: list[tuple[str, int, int]] = []
    for line in text.split("\n"):
        if line.startswith(MAP_BEGIN):
            open_spans.append((line[len(MAP_BEGIN):], len(clean) + 1))
        elif line.startswith(MAP_END):
            block, first = open_spans.pop()
            if len(clean) >= first:  # a statement that wrote no line has no span
                spans.append((block, first, len(clean)))
        else:
            clean.append(line)
    if open_spans:
        raise ValueError("unbalanced source-map markers")
    return "\n".join(clean), spans


def build_source_map(blocks_json: Any, project: dict[str, Any], language: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    """(game IR, generated source, source map) for a Blocks project, in "c" or "asm"."""
    game_ir, origins = blocks_to_ir_traced(blocks_json, project)
    if language == "asm":
        marked, plain, name = ir_to_asm(game_ir, trace=origins), ir_to_asm(game_ir), "game.S"
    else:
        marked, plain, name = ir_to_c(game_ir, trace=origins), ir_to_c(game_ir), "game.c"
    source, spans = strip_markers(marked)
    if source != plain:  # the markers must never change what students and the compiler see
        raise RuntimeError("source-map markers changed the generated code")
    by_block = {block: id_ for id_, block in origins.items()}
    paths = ir_paths(game_ir)
    entries = []
    for block, first, last in sorted(spans, key=lambda span: (span[1], -span[2], span[0])):
        path, op = paths.get(by_block.get(block, -1), ("", ""))
        entries.append({"block": block, "ir": path, "op": op, "lines": [first, last]})
    source_map = {"schema": SCHEMA, "language": language, "file": name,
                  "source_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(), "entries": entries}
    return game_ir, source, source_map
