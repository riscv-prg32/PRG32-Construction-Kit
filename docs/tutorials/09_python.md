# Tutorial 9: your first game in PRG32 Python

Time: about 40 minutes. You need nothing but the kit (a guest can do it too). The language is
described in [PRG32 Python](../python_language.md).

## 1. Make a Python project

1. On **Projects**, press **New project**.
2. Choose **Python (PRG32 Python)**, call it `Catcher` and press **Create**.
3. The IDE opens `game.py`: a small game that already works. Press **Run** (Shift+F10). Click
   the screen and move the yellow square with the arrow keys.

## 2. Read the three functions

- `init()` runs once, when the game starts.
- `update()` runs every frame: it reads the buttons and moves things.
- `draw()` runs every frame after `update()`: it paints the screen.

Hover over `prg32.rect` to read what it does. Type `prg32.` on a new line and press
**Ctrl+Space** to see everything the PRG32 offers.

## 3. Add a falling star

Add two variables at the top, under `score`:

```python
star_x: int = 100
star_y: int = 0
```

In `update()`, the `global` line names every outside variable that `update()` changes. Make it
name the star too, then move the star down:

```python
    global player_x, star_x, star_y, score
    star_y += 2
    if star_y > prg32.SCREEN_H:
        star_y = 0
        star_x = prg32.random(0, 304)
```

In `draw()`, draw it: `prg32.rect(star_x, star_y, 8, 8, prg32.WHITE)`. Press **Run**.

## 4. Catch it

Still in `update()`:

```python
    if prg32.touching(star_x, star_y, 8, 8, player_x, player_y, 16, 16):
        score += 1
        star_y = 0
        prg32.note(72, voice=1, ms=80)
```

In `draw()`, show the score: `prg32.number(score, 8, 24, prg32.YELLOW)`.

## 5. Make a mistake on purpose

Write `star_y = star_y / 2` and wait a moment: the editor underlines `/` and says that PRG32
numbers are whole numbers. Change it to `//`. Now write `while True:` on a new line: the
editor explains why loops must use `for i in range(...)`. Delete it again.

## 6. Look at the C and the assembly

Press **Generate** (Ctrl+Shift+G). In **Generated (read-only)**, open `game.c` and `game.S`.
Find your `star_y += 2`: the comment above it says `Step "change star_y by 2"`, and the C line is
`star_y += 2;`. In the assembly, the same step is a load, an `addi` and a store, each explained.

## 7. Debug a line

Open the **Debug** tab and press **Run**. In **game.py**, press the line number of
`score += 1`. Catch a star: the game stops on that line. Look at **Variables**, then press
**Next Python line**. Press **Continue** to play on.

## For teachers

- The kit never runs the student's Python: it is parsed, checked against the PRG32 Python rules
  and translated to the same IR as the Blocks, then to C and assembly with explanations.
- The same game.py always gives byte-identical C, assembly and cartridge, in every language of
  the interface.
- A Python project stays a Python project: it cannot be turned into Blocks, C or assembly by a
  save. To compare languages, make a C project from the same idea, or open the generated C.
