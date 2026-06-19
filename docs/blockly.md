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
| `play beep freq 880 ms 80` | `prg32_audio_beep(880, 80);` |

## Expression rules

Text fields for coordinates and values accept simple integer expressions such as:

```text
150
player_x
player_x + 8
score * 2
```

The generator sanitizes expressions and rejects syntax that would inject arbitrary C.
