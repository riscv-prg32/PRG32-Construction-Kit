# Tutorial 10: your own art in Blocks, Python, C and assembly

Time: about 40 minutes. You need nothing but the kit (a guest can do it too). The rules are in
[Project art in your game](../project_art.md).

## 1. Add Star Catcher

1. On **Projects**, find **Star Catcher (Blocks)** in the examples (badge *sprites & sound*) and
   press **Add**.
2. Open it and press **Run** (Shift+F10). Move the rocket with the arrow keys and catch the
   falling star.
3. In the project files, open **Sprites → rocket**. Sprite Lab opens as a tab.

## 2. Change the art, not the code

1. In Sprite Lab, paint the rocket's nose another colour and press **Save**.
2. Press **Run** again: the game draws the new rocket. You changed no block.
3. Look under **Use it in your game** in Sprite Lab. Choose **Blocks**, then **PRG32 Python**,
   **C** and **Assembly**: the same sprite, used in four languages.

## 3. Read the blocks

The **Sprites & Tiles** category has three blocks for your art:

```text
when game starts:  load background sky
every frame draw:  draw background sky
                   draw sprite rocket x rocket_x y 160
                   draw sprite star x star_x y star_y
```

Load a background once, draw it first in every frame, then draw the sprites on top of it.
Press **Generate** and open `game.c`: part 3 holds `rocket_draw`, `star_draw`, `sky_load` and
`sky_draw`, made from the art.

## 4. The same game in PRG32 Python

Add **Star Catcher (Python)** and open `game.py`. The art is named in quotes:

```python
def draw() -> None:
    prg32.background_draw("sky")
    prg32.sprite("rocket", rocket_x, ROCKET_Y)
    prg32.sprite("star", star_x, star_y)
```

Change `"star"` to `"stars"` and save. The Problems panel says the project has no sprite with
that name, on that line. Put it back.

## 5. The same game in C

Add **Star Catcher (C)**. Near the top of `game.c` there is one line for all the art:

```c
#include "prg32_assets.h"
```

Open **Project art → prg32_assets.h** in the project files: it is read-only, and it shows the
code the kit writes in place of that line when the game is built. Find `rocket_draw`,
`ROCKET_WIDTH`, `sky_load`, `sfx_coin` and `TRACK_THEME`, then find where `game.c` uses them.

## 6. The same game in assembly

Add **Star Catcher (Assembly)**. Its line is `#include "prg32_assets.S"`, and its art is called
like a firmware function:

```text
la t0, rocket_x
lw a0, 0(t0)
li a1, ROCKET_Y
call rocket_draw
```

Run all four games: they draw exactly the same picture.

## 7. Try it yourself

- Draw a new sprite called `comet` in Sprite Lab and save it. Draw it in each game: a block, a
  `prg32.sprite("comet", ...)` line, `comet_draw(x, y);` in C, `call comet_draw` in assembly.
- In **Backgrounds**, add a second layer to `sky` with clouds. `draw background sky` draws it in
  front, with tile 0 see-through.
- In AudioStudio, change the **Coin** sound. Every game plays the new sound.
