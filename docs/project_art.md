# Project art in your game: sprites, backgrounds and sounds

A project's art is made in three tools of the IDE: **Sprite Lab** (sprites), **Backgrounds**
(tiles and maps) and **AudioStudio** (sound effects and soundtracks). Every kind of project uses
that art the same way: **by its name**. Change a sprite in Sprite Lab and the next Run shows the
new picture; nothing has to be copied into the code by hand. [ART-01]

| The art | Blocks | PRG32 Python | C | Assembly |
|---|---|---|---|---|
| a sprite `rocket` | `draw sprite rocket x 10 y 20` | `prg32.sprite("rocket", 10, 20)` | `rocket_draw(10, 20);` | `li a0, 10` / `li a1, 20` / `call rocket_draw` |
| a background `sky` | `load background sky`, `draw background sky` | `prg32.background_load("sky")`, `prg32.background_draw("sky")` | `sky_load();`, `sky_draw();` | `call sky_load`, `call sky_draw` |
| a sound effect `Coin` | `play sound effect Coin` | `prg32.sound_effect("Coin")` | `sfx_coin();` | `call sfx_coin` |
| a soundtrack `Theme` | `play soundtrack Theme` | `prg32.soundtrack_play("Theme")` | `prg32_audio_play_track(TRACK_THEME);` | `li a0, TRACK_THEME` / `call prg32_audio_play_track` |

Each tool shows these lines for the sprite, background or sounds you are editing, under **Use it
in your game**: choose Blocks, PRG32 Python, C or Assembly. The examples **Star Catcher (Blocks)**,
**(Python)**, **(C)** and **(Assembly)** on the Projects page are the same game written four times
with the same art (`examples/art/`); [tutorial 10](tutorials/10_project_art.md) walks through them.

## For students

- **Load a background once, draw it every frame.** `load background` (or `sky_load()`) defines its
  tiles and puts its map in the playfield: put it in *when game starts* / `init`. `draw background`
  (or `sky_draw()`) copies the playfield to the screen: put it first in *draw*, then draw sprites
  on top of it.
- **A sprite is drawn with its top-left corner at x, y.** Its see-through pixels (the eraser in
  Sprite Lab) are not drawn, so the background shows through.
- **Names.** A block or a Python call uses the name you gave the art in its tool. C and assembly
  use a *C name* made from it: lower case, spaces become `_` (`level 1` → `level_1`), and a name
  that is already taken gets `_2`. The IDE shows the C name in **Use it in your game** and in the
  read-only file `prg32_assets.h` / `prg32_assets.S` (project files → **Project art**).
- **Sizes.** C and assembly also get `ROCKET_WIDTH` and `ROCKET_HEIGHT`, the size of each sprite
  in pixels, for collision tests such as `prg32_sprite_hitbox`.
- **A missing name.** If a block names art that was renamed or deleted, the code generator warns
  you and leaves that block out; PRG32 Python stops with an error on that line. Neither ever
  guesses another picture.

## In C and assembly: one include line

A C game writes, below `#include "prg32.h"`:

```c
#include "prg32_assets.h"
```

and an assembly game writes, on a line of its own:

```text
#include "prg32_assets.S"
```

This is not a file on the server. When the game is built, the kit writes the project's art **in
place of that line, on that same line**: every other line keeps its number, so compiler messages
and the debugger point at the lines you wrote. The IDE shows what is written there, laid out and
explained, as the read-only file **prg32_assets.h** (or **prg32_assets.S**) under **Project art**
in the project files; it changes as soon as the art changes.

What the include gives a C game (the assembly has the same names, as labels and `.equ`):

```c
enum { ROCKET_WIDTH = 16, ROCKET_HEIGHT = 16 };
static const uint16_t rocket_pixels[256] = { ... };          /* direct colours, RGB565 */
void rocket_draw(int x, int y);                               /* prg32_sprite_draw_frame */
void star_draw(int x, int y);                                 /* an indexed sprite: prg32_sprite_draw_indexed */
void sky_load(void);                                          /* prg32_tile_define, prg32_playfield_put */
void sky_draw(void);                                          /* prg32_playfield_draw, layer 0 then 1 */
void sfx_coin(void);                                          /* prg32_audio_note(...) */
enum { TRACK_THEME = 0 };                                     /* for prg32_audio_play_track */
```

Rules, checked when the game is saved and built (and by the editor while you type):

- write the line exactly once, on a line of its own, without a comment after it;
- in C, below `#include "prg32.h"`;
- it is the only `#include` an assembly game may write: every other include, `.include` and
  `.incbin` is still refused, because they could read files on the server.

The game needs the PRG32 features its art uses (`sprites`, `tilemap`, `platformer` for tiles with
flags, `audio`); the kit adds them to the cartridge by itself.

## In Blocks and PRG32 Python

The **Sprites & Tiles** category has three blocks: **draw sprite**, **load background** and
**draw background**. Their lists show the project's sprites and backgrounds. PRG32 Python has
`prg32.sprite(name, x, y)`, `prg32.background_load(name)` and `prg32.background_draw(name)`
([PRG32 Python](python_language.md)).

The generated `game.c` and `game.S` contain only the art the game uses, in part 3 (*Pictures*),
with the same functions as above. **Convert to C** (or assembly) writes the include line instead,
so the converted game keeps following Sprite Lab and Backgrounds.

## For teachers

- The art stays data: sprites are sprite records, backgrounds are assets of kind `background`, the
  sound is the AudioStudio document. `project_assets.catalog` turns them into code; the same art
  always gives the same code, in a fixed order (by name), so builds stay deterministic and
  byte-identical.
- The include line names no file, so it cannot reach the server: the server blanks it before its
  checks (`source_project.validate_asm_source`) and writes the art in its place only in the text
  handed to the compiler (`routes._generated_sources`). The text written there has no comments and
  no `#` lines. The saved `game.c` / `game.S` is never changed.
- An indexed sprite's descriptor holds two addresses; it is filled in on the stack when the sprite
  is drawn, because a cartridge may be loaded anywhere and only code may compute an address.
- Examples with art bring their sprites, background and AudioStudio document when they are added,
  for guests too. Project archives, **Make my copy** and the move of guest games into an account
  carry the art as before.
- `tests/test_project_assets.py` builds Star Catcher in all four languages with the real toolchain,
  runs the cartridges in `prg32qt-headless` and checks that the four frames are identical, pixel
  for pixel. `tests/test_asm_generator.py` proves the generated assembly makes exactly the same
  firmware calls as the generated C for a game with sprites and a background.

## The API

```text
GET  /api/projects/<id>/art   {catalog, c_header, asm_include, usage, features, files}
POST /api/guest/art           {title?, sprites, backgrounds, audio_studio?} -> the same, stores nothing
```

`usage` has, for every sprite, background, sound effect and soundtrack, its line in `blocks`,
`python`, `c` and `asm`. The guest routes `/api/guest/convert`, `/convert_to` and `/run` also take
the guest's `sprites` and `backgrounds` (at most 64 of each). See also [ADR-0029](adr/0029-project-art-in-code.md).
