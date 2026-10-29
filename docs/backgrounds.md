# Backgrounds: tiles and maps

**Backgrounds** makes the scenery of a game the way the PRG32 draws it: small square **tiles**
and **maps** made of them. It opens like Sprite Lab and AudioStudio, as a tab of the project's
IDE: from **Backgrounds** in the menu bar, from **Backgrounds** in the project files (each
background, or **New background…**), or from the Projects page. It has the same layout: the
toolbar on top (**New**, **Save**, **Delete**, **Convert to C**), the project's backgrounds on
the left, the map in the centre with the tiles under it, and the tile editor and properties on
the right. Without an account, backgrounds are kept in your browser with the project.

## For students

- A **tile** is 8 × 8 pixels. Each pixel is on or off: on is drawn in the tile's
  **foreground** colour, off in its **background** colour. Click a pixel in the big tile on the
  right to switch it; drag to switch several. **Add tile** makes a new one, **Remove tile**
  deletes the chosen one (map cells that used it become empty).
- Choose a tile under the map, then click or drag on the **map** to place it. Tile **0** is
  empty.
- The map is up to 64 × 32 tiles (the screen shows 40 × 25). It has two **layers**: 0 is
  behind, 1 is in front. **Show the other layer** shows the one you are not painting, faded.
- **For the platform helpers** marks what a tile is in a platform game: **solid** (walls),
  **platform** (stand on it from above), **hazard** (it hurts), **collect** (pick it up).

## In your game

**Use it in your game** (under the properties) shows the lines for the saved background:

| Kind of project | Once, when the game starts | Every frame, before the sprites |
|---|---|---|
| Blocks | `load background level` | `draw background level` |
| PRG32 Python | `prg32.background_load("level")` | `prg32.background_draw("level")` |
| C (after `#include "prg32_assets.h"`) | `level_load();` | `level_draw();` |
| Assembly (after `#include "prg32_assets.S"`) | `call level_load` | `call level_draw` |

`level_draw()` draws layer 0, then layer 1 with tile 0 see-through. Scroll with
`prg32_playfield_scroll` or the camera as before. See [project_art.md](project_art.md).

## In code

**Convert to C** saves the background and writes, for a background called `level`:

```c
static const uint8_t level_tiles[2][8] = { ... };      /* 8 rows of 8 bits, bit 7 is the leftmost pixel */
static const uint8_t level_layer0[25][40] = { ... };   /* one tile number per cell, 0 is empty */
void level_load(void);   /* defines the tiles (prg32_tile_define) and fills the map (prg32_playfield_put) */
```

Call `level_load();` once, in `init`. Then, in `draw`, draw the layers with
`prg32_playfield_draw(0, 0);` and `prg32_playfield_draw(1, 1);` (the 1 lets tile 0 show what is
behind it). Scroll with `prg32_playfield_scroll` or the camera, exactly as in the PRG32
documentation. The game needs the `tilemap` feature, and `platformer` if a tile has flags.
`tests/test_backgrounds.py` compiles such a background with the real toolchain and checks the
pixels PRG32-QT draws.

## For teachers

- A background is a project asset of kind `background` (`backgrounds.py` checks it: tile numbers
  1 to 255, 8 rows each, `#rrggbb` colours, known flags, the map's size and cells). It travels with
  the project archive, **Make my copy** and the guest workspace's move into an account.
- **Convert to C** also keeps the C as an artifact (`background_c_source`), like Sprite Lab's.
