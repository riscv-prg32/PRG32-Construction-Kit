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
Blocks and simulator behavior. The kit does not claim complete PRG32 feature
parity. Use the [PRG32 framework manual](https://github.com/riscv-prg32/PRG32/blob/main/docs/software/framework_manual.md)
and PRG32 cartridge toolchain for those lessons until dedicated kit support is
implemented and tested.

## Expression rules

Text fields for coordinates and values accept simple integer expressions such as:

```text
150
player_x
player_x + 8
score * 2
```

The generator sanitizes expressions and rejects syntax that would inject arbitrary C.
