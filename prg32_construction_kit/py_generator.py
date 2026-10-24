"""The Blocks program written in PRG32 Python: a read-only game.py made from the game IR.

    Blockly JSON -> validated game IR (generator.blocks_to_ir) -> this file's game.py

It sits beside the generated game.c and game.S in the IDE, so a student can see the same game
as Blocks, PRG32 Python, C and assembly. It is only read, never built: the cartridge is still
made from the C (or assembly) of the same IR. The PRG32 Python compiler (python_project.py)
accepts it and gives a game that does the same (tests/test_py_generator.py proves both).

The same IR always gives the same text. Two things differ from the Blocks' C:

* Python's operators bind differently from C's (in C ``a & b == c`` is ``a & (b == c)``), so
  every expression is rebuilt from its tree with the brackets Python needs.
* PRG32 Python keeps whole numbers and True/False apart. A number used as a test becomes
  ``n != 0``; a test used as a number cannot be written yet, and that one line says so.
"""

from __future__ import annotations

import json
import keyword
from typing import Any, Callable

from .expressions import ExpressionError, parse_expr, state_name

SOURCE_FILE = "game.py"
LIFECYCLE = ("init", "update", "draw")

# Python's operator precedence, loosest first (a bigger number binds tighter).
_OR, _AND, _NOT, _COMPARE, _BITOR, _BITXOR, _BITAND, _SHIFT, _SUM, _PRODUCT, _UNARY, _ATOM = range(1, 13)
_BINARY = {"|": _BITOR, "^": _BITXOR, "&": _BITAND, "<<": _SHIFT, ">>": _SHIFT, "+": _SUM, "-": _SUM,
           "*": _PRODUCT, "/": _PRODUCT, "%": _PRODUCT}
_COMPARISONS = {"==", "!=", "<", ">", "<=", ">="}
_BUILTINS = {"abs", "min", "max"}   # written abs(x), not prg32.abs(x), as in Python
# Names PRG32 Python cannot give a variable (python_project.py refuses them).
_TAKEN = {"abs", "min", "max", "range", "print", "len", "int", "bool", "list", "str", "float", "input",
          "prg32", "global", "pass", *LIFECYCLE}


class NotPython(ValueError):
    """This part of the Blocks program has no PRG32 Python form yet."""


def _wrap(part: tuple[str, str, int], at_least: int) -> str:
    text, _kind, prec = part
    return text if prec >= at_least else f"({text})"


def _as_bool(part: tuple[str, str, int]) -> tuple[str, str, int]:
    """A test: a number counts as true when it is not 0, as in the Blocks and C."""
    if part[1] == "bool":
        return part
    return (f"{_wrap(part, _COMPARE + 1)} != 0", "bool", _COMPARE)


Lift = Callable[[str], str] | None


def _as_int(part: tuple[str, str, int], lift: Lift = None) -> tuple[str, str, int]:
    """A number. A test used as a number (1 when true, 0 when false in C) needs ``lift``: it stores
    the test in a variable first and gives back that variable's name."""
    if part[1] == "bool":
        if lift is None:
            raise NotPython(f"the test {part[0]} is used as a number")
        return (lift(part[0]), "int", _ATOM)
    return part


def constant(name: str) -> str:
    """PRG32_COLOR_RED -> prg32.RED, PRG32_BTN_LEFT -> prg32.LEFT, PRG32_SCREEN_W -> prg32.SCREEN_W."""
    for start in ("PRG32_COLOR_", "PRG32_BTN_", "PRG32_"):
        if name.startswith(start):
            return "prg32." + name[len(start):]
    return name


def expression(tree: tuple, lift: Lift = None) -> tuple[str, str, int]:
    """One expression tree (expressions.py) as PRG32 Python: (text, "int" or "bool", precedence)."""
    kind = tree[0]
    sub = lambda part: expression(part, lift)  # noqa: E731
    if kind == "num":
        return (tree[1], "int", _ATOM)
    if kind == "name":
        return (tree[1], "int", _ATOM)
    if kind == "const":
        return (constant(tree[1]), "int", _ATOM)
    if kind == "paren":   # the brackets are put back where Python needs them
        return sub(tree[1])
    if kind == "index":
        index = _as_int(sub(tree[2]), lift)
        return (f"{tree[1]}[{index[0]}]", "int", _ATOM)
    if kind == "call":
        args = ", ".join(_as_int(sub(arg), lift)[0] for arg in tree[2])
        name = tree[1] if tree[1] in _BUILTINS else "prg32." + tree[1]
        return (f"{name}({args})", "int", _ATOM)
    if kind == "unary":
        op, inner = tree[1], sub(tree[2])
        if op == "!":
            if inner[1] == "bool":
                return (f"not {_wrap(inner, _NOT)}", "bool", _NOT)
            return (f"{_wrap(inner, _COMPARE + 1)} == 0", "bool", _COMPARE)
        return (f"{op}{_wrap(_as_int(inner, lift), _UNARY)}", "int", _UNARY)
    if kind == "bin":
        op, left, right = tree[1], sub(tree[2]), sub(tree[3])
        if op in ("&&", "||"):
            prec, word = (_AND, "and") if op == "&&" else (_OR, "or")
            return (f"{_wrap(_as_bool(left), prec)} {word} {_wrap(_as_bool(right), prec + 1)}", "bool", prec)
        left, right = _as_int(left, lift), _as_int(right, lift)
        if op in _COMPARISONS:   # one comparison at a time: never a Python chain like a < b < c
            return (f"{_wrap(left, _COMPARE + 1)} {op} {_wrap(right, _COMPARE + 1)}", "bool", _COMPARE)
        prec = _BINARY[op]
        word = "//" if op == "/" else op   # PRG32 Python's // rounds toward zero, like C's /
        return (f"{_wrap(left, prec)} {word} {_wrap(right, prec + 1)}", "int", prec)
    raise NotPython(f"unknown expression part {kind}")


class _Writer:
    def __init__(self, game_ir: dict[str, Any]):
        self.lists = {item["name"]: int(item["size"]) for item in game_ir.get("lists", [])}
        self.names = {item["name"] for item in game_ir.get("state", [])} | set(self.lists)
        self.skipped: list[str] = []
        self.function = ""
        self.assigned: list[str] = []
        self.helpers: dict[str, str] = {}
        self.declared: set[str] = set()   # helper variables already declared in this function
        self.pending: list[str] = []
        self.pad = ""
        self.lifted = 0
        self.has_random = False

    # --- values -------------------------------------------------------------------------------
    def tree(self, text: Any) -> tuple:
        try:
            return parse_expr(text if str(text).strip() else "0", self.lists).tree
        except (ExpressionError, RecursionError):
            raise NotPython(f"the expression {str(text)[:40]!r} was not checked") from None

    def int(self, text: Any) -> str:
        return _as_int(self.value(self.tree(text)), self.lift)[0]

    def int_at(self, text: Any, at_least: int) -> str:
        return _wrap(_as_int(self.value(self.tree(text)), self.lift), at_least)

    def test(self, text: Any) -> str:
        """The test of an if: a bool, or a number (true when not 0) as it is."""
        return self.value(self.tree(text))[0]

    def value(self, tree: tuple) -> tuple[str, str, int]:
        return expression(tree, self.lift)

    def lift(self, test: str) -> str:
        """Store a test as 1 or 0 before the line that uses it as a number (C does the same)."""
        if self.has_random:   # the test would be worked out before the random numbers, not among them
            raise NotPython(f"the test {test} is used as a number in a line with random(...)")
        self.lifted += 1
        name = self.helper("as_number" if self.lifted == 1 else f"as_number_{self.lifted}")
        if name not in self.declared:
            self.declared.add(name)
            self.pending.append(f"{self.pad}{name}: int = 0")
        self.pending += [f"{self.pad}if {test}:", f"{self.pad}    {name} = 1", f"{self.pad}else:",
                         f"{self.pad}    {name} = 0"]
        return name

    def impure(self, text: Any) -> bool:
        return any(word in str(text) for word in ("random", "frame", "peer", "tile"))

    @staticmethod
    def color(value: Any) -> str:
        return "prg32." + str(value or "WHITE")

    @staticmethod
    def rows(values: Any) -> str:
        rows = ['"' + "".join("X" if int(row) & (0x80 >> col) else "." for col in range(8)) + '"'
                for row in list(values or [])[:8]]
        return "[" + ", ".join(rows) + "]"

    def variable(self, name: str) -> str:
        if name not in self.assigned:
            self.assigned.append(name)
        return name

    def helper(self, base: str) -> str:
        """A variable of this function the Blocks do not have (its C name is <function>_<name>)."""
        if base not in self.helpers:
            name = base
            while state_name(f"{self.function}_{name}") in self.names:
                name += "_"
            self.helpers[base] = name
        return self.helpers[base]

    # --- statements ---------------------------------------------------------------------------
    def block(self, statements: Any, depth: int) -> list[str]:
        lines: list[str] = []
        for stmt in statements or []:
            lines.extend(self.statement(stmt, depth))
        return lines or ["    " * depth + "pass"]

    def statement(self, stmt: dict[str, Any], depth: int) -> list[str]:
        # The lines a test-as-number needs go just before this statement (lift).
        saved = (self.pending, self.pad, self.lifted, self.has_random)
        self.pending, self.pad, self.lifted = [], "    " * depth, 0
        self.has_random = "random(" in json.dumps(stmt)
        try:
            lines = self.write(stmt, self.pad, depth)
            return self.pending + lines
        except NotPython as reason:
            note = f"Not written in PRG32 Python yet ({stmt.get('op')}): {reason}"
            self.skipped.append(note)
            return [self.pad + json.dumps(note)]
        finally:
            self.pending, self.pad, self.lifted, self.has_random = saved

    def write(self, stmt: dict[str, Any], pad: str, depth: int) -> list[str]:  # noqa: C901 - one table of ops
        op = stmt.get("op")
        call = lambda name, *args: [f"{pad}prg32.{name}({', '.join(a for a in args if a)})"]  # noqa: E731
        if op == "comment":
            return [pad + json.dumps(str(stmt.get("text", "")))]
        if op == "set":
            var, value = self.variable(stmt["var"]), self.value(self.tree(stmt.get("value")))
            if value[1] == "bool":   # a test stored as a number: 1 when true, 0 when false, as in C
                return [f"{pad}if {value[0]}:", f"{pad}    {var} = 1", f"{pad}else:", f"{pad}    {var} = 0"]
            return [f"{pad}{var} = {value[0]}"]
        if op == "change":
            tree = self.tree(stmt.get("delta"))
            if tree[0] == "unary" and tree[1] == "-":   # change by -3 reads better as  -= 3
                return [f"{pad}{self.variable(stmt['var'])} -= {_as_int(self.value(tree[2]), self.lift)[0]}"]
            return [f"{pad}{self.variable(stmt['var'])} += {_as_int(self.value(tree), self.lift)[0]}"]
        if op == "clamp":
            var = self.variable(stmt["var"])
            return [f"{pad}{var} = prg32.clamp({var}, {self.int(stmt.get('low'))}, {self.int(stmt.get('high'))})"]
        if op == "random":
            return [f"{pad}{self.variable(stmt['var'])} = prg32.random({self.int(stmt.get('low'))}, "
                    f"{self.int(stmt.get('high'))})"]
        if op == "wrap":
            var = self.variable(stmt["var"])
            span = f"{self.int_at(stmt.get('high'), _SUM + 1)} - {self.int_at(stmt.get('low'), _SUM + 1)} + 1"
            return [f"{pad}if {var} < {self.int_at(stmt.get('low'), _COMPARE + 1)}:", f"{pad}    {var} += {span}",
                    f"{pad}elif {var} > {self.int_at(stmt.get('high'), _COMPARE + 1)}:", f"{pad}    {var} -= {span}"]
        if op == "if":
            lines = [f"{pad}if {self.test(stmt.get('cond'))}:", *self.block(stmt.get("then"), depth + 1)]
            otherwise = stmt.get("else")
            while otherwise and len(otherwise) == 1 and otherwise[0].get("op") == "if":   # else + if = elif
                inner = otherwise[0]
                lines += [f"{pad}elif {self.test(inner.get('cond'))}:", *self.block(inner.get("then"), depth + 1)]
                otherwise = inner.get("else")
            if otherwise:
                lines += [f"{pad}else:", *self.block(otherwise, depth + 1)]
            return lines
        if op == "repeat":
            # The Blocks count from 'from' to 'to', both included: range stops before its end.
            high = self.tree(stmt.get("to"))
            stop = str(int(high[1], 0) + 1) if high[0] == "num" else f"{self.int_at(stmt.get('to'), _SUM)} + 1"
            start = self.int(stmt.get("from"))
            bounds = stop if start == "0" else f"{start}, {stop}"
            return [f"{pad}for {self.variable(stmt['var'])} in range({bounds}):", *self.block(stmt.get("body"), depth + 1)]
        if op == "list_fill":
            lst, size = stmt["list"], self.lists.get(stmt["list"], 1)
            index = self.helper("fill_i")
            value = self.int(stmt.get("value"))
            lines = []
            if self.impure(stmt.get("value")):   # the Blocks pick one value for every item
                hold = self.helper("fill_value")
                lines.append(f"{pad}{hold}: int = {value}" if hold not in self.declared else f"{pad}{hold} = {value}")
                self.declared.add(hold)
                value = hold
            return lines + [f"{pad}for {index} in range({size}):", f"{pad}    {lst}[{index}] = {value}"]
        if op == "list_set":
            item, value = f"{stmt['list']}[{self.int(stmt.get('index'))}]", self.value(self.tree(stmt.get("value")))
            if value[1] == "bool":
                return [f"{pad}if {value[0]}:", f"{pad}    {item} = 1", f"{pad}else:", f"{pad}    {item} = 0"]
            return [f"{pad}{item} = {value[0]}"]
        if op == "list_change":
            return [f"{pad}{stmt['list']}[{self.int(stmt.get('index'))}] += {self.int(stmt.get('delta'))}"]
        if op in ("if_button", "if_button_once"):
            test = "held" if op == "if_button" else "pressed"
            return [f"{pad}if prg32.{test}(prg32.{stmt.get('button', 'A')}):", *self.block(stmt.get("then"), depth + 1)]
        if op == "if_touching":
            args = ", ".join(self.int(stmt.get(key)) for key in ("ax", "ay", "aw", "ah", "bx", "by", "bw", "bh"))
            return [f"{pad}if prg32.touching({args}):", *self.block(stmt.get("then"), depth + 1)]
        i, c = self.int, self.color
        if op == "clear":
            return call("clear", c(stmt.get("color", "BLACK")))
        if op in ("rect", "frame"):
            return call(op, i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("w")), i(stmt.get("h")), c(stmt.get("color")))
        if op == "rect_rgb":
            return call("rect_rgb", i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("w")), i(stmt.get("h")),
                        i(stmt.get("rgb")))
        if op == "pixel":
            return call("pixel", i(stmt.get("x")), i(stmt.get("y")), c(stmt.get("color")))
        if op == "line":
            return call("line", i(stmt.get("x1")), i(stmt.get("y1")), i(stmt.get("x2")), i(stmt.get("y2")),
                        c(stmt.get("color")))
        if op == "circle":
            return call("circle", i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("r")), c(stmt.get("color")),
                        "filled=True" if stmt.get("fill") else "")
        if op == "bitmap":
            return call("bitmap", self.rows(stmt.get("rows")), i(stmt.get("x")), i(stmt.get("y")),
                        c(stmt.get("color")), i(stmt.get("scale")))
        if op == "sprite8":
            return call("sprite8", self.rows(stmt.get("rows")), i(stmt.get("x")), i(stmt.get("y")),
                        c(stmt.get("fg")), c(stmt.get("bg")))
        if op == "pixel_indexed":
            return call("pixel_indexed", i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("index")))
        if op == "rect_indexed":
            return call("rect_indexed", i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("w")), i(stmt.get("h")),
                        i(stmt.get("index")))
        if op == "palette_set":
            return call("palette_set", i(stmt.get("index")), c(stmt.get("color")))
        if op == "clear_indexed":
            return call("clear_indexed", i(stmt.get("index")))
        if op == "text":
            return call("text", i(stmt.get("x")), i(stmt.get("y")), json.dumps(str(stmt.get("text", ""))),
                        c(stmt.get("fg")), c(stmt.get("bg")))
        if op == "number":
            return call("number", i(stmt.get("value")), i(stmt.get("x")), i(stmt.get("y")), c(stmt.get("fg")),
                        c(stmt.get("bg")))
        if op == "tile_define":
            return call("tile_define", i(stmt.get("id")), self.rows(stmt.get("rows")), c(stmt.get("fg")),
                        c(stmt.get("bg")))
        if op == "playfield_clear":
            return call("playfield_clear", i(stmt.get("layer")), i(stmt.get("id")))
        if op == "playfield_put":
            return call("playfield_put", i(stmt.get("layer")), i(stmt.get("tx")), i(stmt.get("ty")), i(stmt.get("id")))
        if op == "playfield_scroll":
            return call("playfield_scroll", i(stmt.get("layer")), i(stmt.get("x")), i(stmt.get("y")))
        if op == "playfield_camera":
            return call("playfield_camera", i(stmt.get("x")), i(stmt.get("y")))
        if op == "playfield_draw":
            return call("playfield_draw", i(stmt.get("layer")), "transparent=True" if stmt.get("transparent") else "")
        if op == "beep":
            return call("beep", i(stmt.get("freq")), i(stmt.get("ms")))
        if op == "note":
            return call("note", i(stmt.get("note")), i(stmt.get("channel")), i(stmt.get("ms")))
        if op == "note_off":
            return call("note_off", i(stmt.get("channel")))
        if op == "volume":
            return call("volume", i(stmt.get("volume")))
        if op == "sfx":
            return call("sound_effect", json.dumps(str(stmt.get("name", ""))))
        if op == "track_play":
            return call("soundtrack_play", json.dumps(str(stmt.get("name", ""))))
        if op in ("track_stop", "sound_stop_all", "player_name", "mp_join"):
            return call({"track_stop": "soundtrack_stop"}.get(op, op))
        if op == "band":
            value = i(stmt["value"]) if str(stmt.get("value", "")).strip() else ""
            return call("band", json.dumps(str(stmt.get("text", ""))), value)
        if op == "score_submit":
            return call("score_submit", i(stmt.get("value")))
        if op == "scoreboard":
            return call("scoreboard", json.dumps(str(stmt.get("title", ""))))
        if op == "splash":
            return call("splash", json.dumps(str(stmt.get("title", ""))), json.dumps(str(stmt.get("subtitle", ""))),
                        i(stmt.get("ms")), c(stmt.get("bg")), c(stmt.get("fg")), c(stmt.get("accent")))
        if op == "mp_share":
            return call("mp_share", i(stmt.get("x")), i(stmt.get("y")), i(stmt.get("look")))
        raise NotPython(f"no PRG32 Python statement for {op}")

    def function_lines(self, name: str, statements: Any, doc: str) -> list[str]:
        self.function, self.assigned, self.helpers, self.declared = name, [], {}, set()
        body = self.block(statements, 1)
        lines = [f"def {name}() -> None:", f'    """{doc}"""']
        changed = [var for var in self.assigned if var not in self.helpers.values()]
        if changed:
            lines.append("    global " + ", ".join(changed))
        return lines + body


def from_blocks(game_ir: dict[str, Any]) -> bool:
    """True for the IR of a Blocks program (C, assembly and Python projects have their own source)."""
    return game_ir.get("source_mode") in (None, "", "blocks")


def name_problems(game_ir: dict[str, Any]) -> list[str]:
    """Block variable names PRG32 Python cannot use (they are fine in C)."""
    names = [item["name"] for item in game_ir.get("state", [])] + [item["name"] for item in game_ir.get("lists", [])]
    return [name for name in names
            if keyword.iskeyword(name) or name in _TAKEN or name.startswith("_") or name.startswith("prg32")]


def ir_to_python(game_ir: dict[str, Any]) -> str:
    """game.py for the IR of a Blocks program (read-only: the cartridge is built from the C)."""
    writer = _Writer(game_ir)
    title = str(game_ir.get("title") or "PRG32 Game").replace('"""', "'''").replace("\\", "/")
    out = [f'"""{title}: the Blocks program written in PRG32 Python.', "",
           "Made by the kit from the blocks, read-only: change the blocks, then Generate again.",
           "The cartridge is built from game.c; this is the same game in PRG32 Python.", '"""', "import prg32", ""]
    for item in game_ir.get("state", []):
        out.append(f"{item['name']}: int = {int(item.get('initial', 0))}")
    for item in game_ir.get("lists", []):
        out.append(f"{item['name']}: list[int] = [0] * {int(item['size'])}")
    docs = {"init": "Runs once, when the game starts (the 'when game starts' blocks).",
            "update": "Runs every frame: the 'every frame' blocks.",
            "draw": "Runs every frame after update: the 'draw' blocks."}
    for name in LIFECYCLE:
        out += ["", ""] + writer.function_lines(name, game_ir.get(name), docs[name])
    problems = [f"{name} cannot be a PRG32 Python name: rename the variable in the blocks"
                for name in name_problems(game_ir)] + writer.skipped
    if problems:
        notes = ["# Not yet the same game in PRG32 Python:"] + [f"#   {note}" for note in problems]
        out[6:6] = notes   # just after  import prg32
    return "\n".join(out) + "\n"
