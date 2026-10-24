# PRG32 Python (language version 1)

PRG32 Python is a small, typed part of Python for writing PRG32 games. The kit never runs your
Python: it reads `game.py`, checks it, and translates it into the same game description the
Blocks make. From there it writes C and RISC-V assembly that you can read, line by line, and
builds a PRG32 cartridge. Design: [ADR-0026](adr/0026-prg32-python-projects.md).

```text
game.py -> checked by the kit -> game IR -> game.c and game.S (with explanations) -> cartridge
```

A program that runs in PRG32 Python is also valid Python 3 syntax, but a few things work like
the PRG32's processor instead of desktop Python. They are marked **Cartridge rule** below.

## A whole game

```python
"""My PRG32 game."""
import prg32

player_x: int = 150
score: int = 0


def init() -> None:
    """Runs once, when the game starts."""
    global score
    score = 0


def update() -> None:
    """Runs every frame: read the buttons, move things."""
    global player_x
    if prg32.held(prg32.LEFT):
        player_x -= 3
    if prg32.held(prg32.RIGHT):
        player_x += 3
    player_x = prg32.clamp(player_x, 0, 304)


def draw() -> None:
    """Runs every frame after update: draw the screen."""
    prg32.clear(prg32.BLACK)
    prg32.rect(player_x, 180, 16, 16, prg32.YELLOW)
    prg32.number(score, 8, 8)
```

Every game has `import prg32` and the three functions `init`, `update` and `draw`, each written
`def name() -> None:`. The text in `"""..."""` under a `def` becomes a comment in the C.

## Variables and types

| Type | Meaning | Example |
| --- | --- | --- |
| `int` | a whole number from -2147483648 to 2147483647 | `lives: int = 3` |
| `bool` | `True` or `False` | `playing: bool = True` |
| `list[int]` | a fixed number of `int`s, counted from 0 | `bricks: list[int] = [0] * 10` or `[3, 1, 4]` |

- Every variable has a type and a starting value the first time it is written.
- Starting values outside functions are fixed numbers, `True`/`False`, `prg32` constants or
  earlier variables: `HALF: int = WIDTH // 2`.
- To change a variable from outside the functions inside a function, write `global name` at the
  start of the function (as in Python). List items can be changed without `global`.
- A variable declared inside a function (`n: int = 0`) becomes `<function>_n` in the C, so its
  name does not clash with other functions.
- Names use English letters, digits and `_`, start with a letter, and are not words that C uses
  (`int`, `double`, `input`, ...). `WIDTH` and `width` are the same name in the C, so only one may
  exist.
- **Cartridge rule:** numbers wrap around at 32 bits: `2147483647 + 1` is `-2147483648`.
- **Cartridge rule:** a list has 1 to 1024 items. Reading outside it gives 0; writing outside it
  does nothing (no crash, no hidden memory change).

## Statements

| PRG32 Python | Notes |
| --- | --- |
| `x = expression` | `x += e` and `x -= e` add; `x *= e`, `//=`, `%=`, `<<=`, `>>=`, `&=`, `|=`, `^=` work too |
| `items[i] = expression` | `items[i] += e` and friends work too |
| `if ...:` / `elif ...:` / `else:` | the test is a `bool`, or an `int` (true when not 0) |
| `for i in range(stop):` / `for i in range(start, stop):` | **Cartridge rule:** at most 1024 rounds; no step |
| `my_helper(a, b)` | calls one of your own functions |
| `prg32.something(...)` | see the `prg32` module below |
| `pass` | does nothing |
| `return` | only as the last line of a function that gives back nothing |

Not part of PRG32 Python (the kit says so, with the line): `while`, `break`, `continue`,
`try`, `with`, `class`, `lambda`, `del`, `yield`, `async`, `match`, `import` of other modules,
`print`, `eval`, `exec`, `open`, slices, `a if c else b`, tuples, dictionaries, sets, f-strings,
floating-point numbers.

## Expressions

| Operators | Meaning |
| --- | --- |
| `+ - *` | add, subtract, multiply (whole numbers) |
| `//` `%` | divide and remainder |
| `<< >> & \| ^ ~` | bit operations |
| `== != < <= > >=` | compare (gives a `bool`) |
| `and or not` | combine `bool`s |

- **Cartridge rule:** `//` and `%` round toward zero, like C and the RISC-V processor:
  `-7 // 2` is `-3` (desktop Python says `-4`) and `-7 % 2` is `-1`. Dividing by 0 gives `-1`
  and `x % 0` gives `x`, as the RISC-V `div` and `rem` instructions do.
- `/` (a fraction) and `**` are refused: write `//`, or multiply.
- `and`, `or` and `not` need `bool` values. Write `if lives > 0 and playing:`, not `if lives and
  playing:`. They stop early, as in Python.
- Compare two values at a time: `0 < x and x < 10`, not `0 < x < 10`.
- `True` and `False` are not numbers: `True + 1` is refused.
- Shifts use only the lowest 5 bits of the count, like the processor.
- `abs(x)`, `min(a, b)` and `max(a, b)` are built in.

## Your own functions

```python
def move(dx: int, dy: int) -> None:
    global x, y
    x += dx
    y += dy


def double(v: int) -> int:
    return v * 2
```

- Every parameter has a type, and the function says what it gives back: `-> None` (nothing),
  `-> int` or `-> bool`.
- A function that gives back a value has exactly one line: `return expression`.
- The kit copies a function's lines where it is called (the C has no extra functions), so a
  function cannot call itself, directly or through others (no recursion), and calls go at
  most 8 deep.
- A value that changes every time it is asked for (`prg32.random(...)`, `prg32.frame()`) cannot be
  given to a parameter that is used twice: store it in a variable first.

## The `prg32` module

Colours: `prg32.BLACK, WHITE, RED, GREEN, BLUE, YELLOW, CYAN, MAGENTA, ORANGE, PINK, GRAY,
DARK_GRAY, BROWN, PURPLE, NAVY, LIME`. Buttons: `prg32.LEFT, RIGHT, UP, DOWN, A, B, START,
SELECT`. Numbers: `prg32.SCREEN_W` (320), `prg32.SCREEN_H` (200) and the other PRG32 constants
without the `PRG32_` start (`prg32.TILE_W`, ...).

**Drawing:** `clear(color=BLACK)`, `rect(x, y, w, h, color=WHITE)`, `frame(x, y, w, h, color)`,
`rect_rgb(x, y, w, h, rgb)`, `pixel(x, y, color)`, `line(x1, y1, x2, y2, color)`,
`circle(x, y, r, color, filled=False)`, `bitmap(rows, x, y, color, scale=1)`,
`sprite8(rows, x, y, fg, bg)`, `text(x, y, "TEXT", fg=WHITE, bg=BLACK)`,
`number(value, x, y, fg, bg)`, `palette_set(index, color)`, `pixel_indexed(x, y, index)`,
`rect_indexed(x, y, w, h, index)`, `clear_indexed(index)`.
A picture (`rows`) is 8 texts of up to 8 characters, `.` for an empty pixel:
`["..XX....", ".XXXX...", ...]`.

**Tiles and playfields:** `tile_define(id, rows, fg, bg)`, `playfield_clear(layer, id)`,
`playfield_put(layer, tx, ty, id)`, `playfield_scroll(layer, x, y)`, `playfield_camera(x, y)`,
`playfield_draw(layer, transparent=False)`, and the value `tile(layer, tx, ty)`.

**Sound (the eight-voice audio engine):** `note(note, voice=0, ms=250)` (60 is middle C, voices
0-7), `note_off(voice)`, `volume(0..255)`, `beep(freq, ms)`, `sound_effect("name")` and
`soundtrack_play("name")` (made in AudioStudio, by name), `soundtrack_stop()`,
`sound_stop_all()`. The old buzzer does not exist.

**Tests for `if`:** `held(button)` (every frame while held), `pressed(button)` (only the
frame it goes down; player 2's buttons are `prg32.P2_LEFT`, `prg32.P2_A`, ...), `touching(ax, ay, aw, ah, bx, by, bw, bh)` (two rectangles overlap). They
are used as the whole test, or joined with `and`: `if prg32.pressed(prg32.A) and playing:`.
**Cartridge rule:** such an `if` cannot have `elif`/`else` yet; write a second `if`.

**Values:** `clamp(v, low, high)`, `sign(x)`, `sin(degrees)` and `cos(degrees)` (times 256),
`rgb(r, g, b)`, `random(low, high)` (both included), `frame()` (the frame count; `frame(x, y, w, h)`
still draws an outline), and for multiplayer `peers()`,
`peer_x(n)`, `peer_y(n)`, `peer_look(n)`.

**Game services:** `band("TEXT", value)`, `score_submit(value)`, `scoreboard("TITLE")`,
`splash("TITLE", "SUBTITLE", ms, bg, fg, accent)`, `player_name()`, `mp_join()`,
`mp_share(x, y, look)`.

Text given to `text`, `band`, `scoreboard` and `splash` uses the PRG32 8x8 font: English letters,
digits and the usual signs, up to 64 characters (`band` 24, titles 32).

## Limits

| Limit | Value |
| --- | --- |
| size of game.py | 64 KiB, 4000 lines |
| brackets inside each other | 32 |
| blocks (if/for) inside each other | 12 |
| functions / variables | 64 / 256 |
| helper calls inside each other | 8 |
| one expression after helpers are copied in | 200 characters |
| statements after helpers are copied in | 4000 |

## Problems and where they show

The IDE checks game.py while you type (red underlines) and the server checks it again when you
save, run or compile. Every message names the line, for example
`Line 12: 'while' loops could run forever; use  for i in range(n):  (at most 1024 rounds)`.
The Problems list jumps to the line with Enter.

## Debugging

Run (Shift+F10) builds the game with debug information. In the Debug tab, the **game.py** tab
shows your program with the running line highlighted; press a line number to put a breakpoint
on that Python line, and **Next Python line** to step. The game.c and game.S tabs show the
same place in the generated code. The Variables list shows your variables by their C names
(`update_i` for `i` inside `update`).

## How it is checked (for teachers)

The kit parses game.py with Python's own parser (`ast.parse`), which only builds a syntax tree:
nothing is imported or executed. Each part of the tree is accepted only if PRG32 Python allows
it (an allow-list), and every value is type-checked. The result is the kit's game IR, the same
one the Blocks make, so the C and assembly generators, the build sandbox and the cartridge are
exactly the ones Blocks projects use. The same game.py always gives byte-identical C, assembly
and cartridge (the build provenance records the language version, the parser grammar and the
SHA-256 of game.py and of the IR).
