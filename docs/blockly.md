# Blockly Game Blocks

## Stored format

Projects save the Blockly workspace serialization in JSON:

```json
{
  "blocks": {
    "languageVersion": 0,
    "blocks": []
  }
}
```

This is stored in:

```text
projects.blocks_json
```

## Top-level blocks

| Block | Purpose |
| --- | --- |
| `when game starts` | Runs once in generated `<prefix>_init`. |
| `every frame update` | Runs every frame in generated `<prefix>_update`. |
| `every frame draw` | Runs every frame in generated `<prefix>_draw`. |

## State blocks

| Block | C behavior |
| --- | --- |
| `set score to 0` | `score = 0;` |
| `change player_x by -3` | `player_x += -3;` |
| `keep player_x between 0 and 304` | emits two boundary checks. |

## Input and logic blocks

| Block | C behavior |
| --- | --- |
| `if button LEFT pressed` | `if (input & PRG32_BTN_LEFT) { ... }` |
| `if rect touches rect` | `prg32_sprite_hitbox(...)` |

## Drawing blocks

| Block | C behavior |
| --- | --- |
| `clear screen black` | `prg32_gfx_clear(PRG32_COLOR_BLACK);` |
| `draw rectangle ...` | `prg32_gfx_rect(...);` |
| `draw text ...` | `prg32_gfx_text8(...);` |

## Audio block

| Block | C behavior |
| --- | --- |
| `play beep freq 880 ms 80` | Converts 880 Hz to the nearest MIDI note and calls `prg32_audio_note` for 80 ms. Frequencies are clamped to the C3–C6 range. |
| `play MIDI note 60 on channel 0 for 250 ms` | Calls the asynchronous `prg32_audio_note` mixer API with default instrument 0. |

## Current PRG32 main coverage

The Blocks editor supports the cartridge lifecycle, one local controller,
integer state, rectangle collision, RGB565 clear/rectangle/pixel/text,
palette and indexed clear/rectangle/pixel, inclusive random numbers, and
simple mixer notes. The JavaScript simulator approximates these operations;
physical audio and random-number sequences may differ.

The current PRG32 cartridge ABI also includes tiles and scrolling playfields,
platform actors, sprite assets and animation, samples and tracker audio,
on-screen keyboard, scores, multiplayer, status bands, RGB LED, performance
measurement, and other runtime services. These do **not** yet have equivalent
Blocks and simulator behavior. The **Advanced C** editor can build cartridges
using the full portable cartridge ABI with the current PRG32 toolchain. Some
`prg32.h` functions are resident-only and cannot be called by a cartridge. Use the
[PRG32 framework manual](https://github.com/riscv-prg32/PRG32/blob/main/docs/software/framework_manual.md)
for those lessons. Blocks and simulator parity remains a separate future task.

## Expression rules

Text fields for coordinates and values accept simple integer expressions such as:

```text
150
player_x
player_x + 8
score * 2
```

An expression may use:

- whole numbers (`16`, `-3`, `0x1F`)
- state variable names (`player_x`) and PRG32 constants (`PRG32_SCREEN_W`)
- parentheses and the operators `+ - * / % < > <= >= == != && || ! & | ^ ~ << >>`

Anything else is replaced by the block's default value, and the replacement is
listed under **Warnings** after **Convert**. That includes function calls
(`rand()`), decimals (`1.5`), quotes, semicolons, braces, comments and `#`
lines, so a text field can never add hidden C code.

Some details students may notice:

- Names are not case-sensitive: `Player_X` and `player_x` are the same variable.
- Division works like C integers: `7 / 2` is `3`, and the simulator does the same.
- Names that C already uses get `_var` added: a variable called `input` or `int`
  becomes `input_var` or `int_var` in the generated C.
- Text in **draw text** and **comment** blocks is escaped, so quotes and `*/`
  stay inside the string or comment.
