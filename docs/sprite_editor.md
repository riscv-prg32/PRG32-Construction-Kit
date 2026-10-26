# Sprite Lab

Sprite Lab is a small pixel editor for a game's pictures. It opens as a tab of the IDE, for
the project that is open: **Sprites** in the project files (each sprite, or **New sprite…**),
the **Sprite Lab** item of the top menu while the project is open, or **Sprite Lab** on a
project card on the Projects page. It has the same layout as
AudioStudio: the toolbar on top (**New**, **Save**, **Import**, **Export PNG**, **Delete**,
**Convert to C**), the project's sprites on the left, the canvas in the centre, the
properties and the generated C on the right.

## Features

- Create, load, update and delete the project's sprites (`/api/sprites?project_id=...`).
- Paint pixels on a grid.
- Use an eraser for transparent pixels.
- Import an image and downsample it to the sprite grid.
- Export a PNG from the browser.
- Convert sprite JSON to a C `uint16_t` RGB565 array.

## Indexed colours and palettes

**Colours** in the properties chooses how the sprite stores its colours:

- **Direct**: each pixel has its own colour (RGB565 on the PRG32, 16 bits per pixel).
- **Indexed (a palette)**: the sprite has a palette of up to 256 colours, and each pixel stores
  only the number of its palette entry. With 2 colours that is 1 bit per pixel, up to 4 colours
  2 bits, up to 16 colours 4 bits, up to 256 colours 8 bits. The line next to **Palette** shows
  the size, for example `4 colours · 2 bits per pixel · 64 bytes (direct: 512)`.

Switching a sprite to indexed makes its palette from the colours it uses. Transparent pixels get
entry 0, marked transparent. With a palette:

1. Click an entry (or use the arrow keys) to paint with it.
2. **Colour of the chosen entry** changes that entry, and every pixel using it changes at once.
   That is how games recolour a sprite, for a second player or a flash when hit.
3. **This entry is transparent** makes that entry not drawn. The eraser paints with it.
4. **Add colour** and **Remove last** change the palette; pixels of a removed entry take entry 0.
5. **Use a ready palette** (PRG32 named colours, 4 greys, black and white) gives every pixel the
   nearest colour of that palette.

Importing an image into an indexed sprite gives each pixel the nearest palette colour.
**Convert to C** then makes what `prg32_sprite_draw_indexed` draws (`prg32.h`):

```c
static const uint16_t ship_palette[3] = { 0x0000, 0xFEC0, 0xF800 };   /* RGB565 */
static const uint8_t ship_indices[2] = { 0x19, 0x55 };               /* 2 bits per pixel, packed */
static const prg32_indexed_sprite_t ship_sprite = {
    ship_indices, ship_palette, 4, 2, 1, 3, PRG32_SPRITE_BPP_2, 0     /* entry 0 is transparent */
};
/* prg32_sprite_draw_indexed(x, y, &ship_sprite, 0); */
```

The indices are packed most significant first, row after row, as the PRG32 reads them.
`tests/test_sprite_palette.py` compiles such a sprite with the real toolchain and checks the
colours PRG32-QT draws.

## Sprite JSON shape

```json
{
  "name": "player",
  "width": 16,
  "height": 16,
  "pixels": [
    ["transparent", "#ffd800"]
  ],
  "data_url": "data:image/png;base64,..."
}
```

For a direct sprite the `pixels` field is the source of truth for conversion. An indexed sprite
also has `"palette": {"mode": "indexed", "colors": [...], "transparent_index": 0, "indices": [[...]]}`.
Its `indices` are the truth, and its `pixels` are made from them, so every reader of direct
sprites keeps working. `data_url` is a convenience preview/export image.

## Convert to C

Click **Convert to C** in Sprite Lab. The backend creates a `sprite_c_source` artifact.

Example output:

```c
#define PLAYER_WIDTH 16
#define PLAYER_HEIGHT 16
static const uint16_t player_pixels[256] = {
    0x0000, 0xFFE0, ...
};
```
