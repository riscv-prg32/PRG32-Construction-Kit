# PRG32 feature coverage

PRG32 cartridges call the firmware through the **portable ABI table**
(`prg32/abi/prg32_abi.json` in [riscv-prg32/PRG32](https://github.com/riscv-prg32/PRG32)).
The Construction Kit gives students three ways to reach it:

- **Blocks**: the visual language, with generated C;
- **Simulator**: the browser simulator that runs Blocks projects;
- **Advanced C**: hand-written C against the full portable ABI, compiled by
  the same PRG32 toolchain (see `cartridge_build.md`).

Every portable ABI function is reachable from **Advanced C**. The table shows
which ones also have blocks.

| PRG32 feature (ABI group) | Blocks | Simulator | Advanced C only |
| --- | --- | --- | --- |
| Lifecycle `init` / `update` / `draw` | three hat blocks | yes | - |
| Input, player 1 and 2 (`prg32_input_read`) | *is held*, *was just pressed*, P2 buttons | yes (keyboard, on-screen pad) | `input_read_player`, `input_read_menu`, `controller_read`, `input_wait_released` |
| Graphics (`gfx_clear/pixel/rect/text8`) | clear, rectangle, outline, pixel, line, circle, text, number, picture | yes, same font and RGB565 colours | `gfx_present`, `set_fullscreen`, `snapshot_row_rgb565` |
| Indexed palette (`palette_set`, `*_indexed`) | 4 palette blocks | yes | `palette_get` |
| Random (`prg32_random_number`) | *set to random*, `random()` | yes (different sequence) | - |
| Time | `frame()` (deterministic frame counter) | yes | `prg32_ticks_ms` |
| Sprites (`sprite_hitbox`, `sprite_draw_8x8`) | *touches*, *draw 8x8 sprite* | yes | 16x16/24x24 RGB565, animation, indexed and bitplane sprites (Sprite Lab produces the C arrays) |
| Tiles and playfields (`tilemap`) | define tile, fill, put, `tile()`, scroll, camera, draw | yes | text-tile screen (`tile_put`, `tile_present`), `scroll_by`, `parallax`, `draw_dual`, tile flags |
| Platformer helpers (`platformer`) | - | - | `platform_actor_*`, `platform_solid_at`, camera follow |
| Audio (`audio`) | beep, MIDI note, stop, master volume | yes (the firmware's 8-voice engine) | note on/off with pan, samples, tracks, tempo, channel volume/pan |
| Status bands | *show in status band* (game info) | shown in the debug line | band modes, colours, log |
| Splash | *show splash* | yes | `splash_draw`, `splash_show_default` |
| Scores | *save high score*, *show scoreboard*, *ask the player's name* | messages only | `score_player_get/set`, `score_count/get`, `score_sync_remote` |
| Multiplayer (`multiplayer`) | *join*, *share my position*, `peers()`, `peer_x/y/look()` | offline (0 peers) | `multiplayer_leave`, `set_input`, raw peer records |
| Keyboard (`keyboard`) | through *ask the player's name* | - | `keyboard_init/update/draw`, `text_input` |
| Wi-Fi (`wifi`) | - | - | `wifi_start_mode`, setup, status |
| Metrics and performance (`metrics`) | - | - | `perf_*` measurement API |
| Console and cartridge slots | - | - | `console_*`, `cart_*` slot services |

## Feature bits

A cartridge declares the optional firmware services it needs. For Blocks
projects the kit works them out from the blocks and passes them to
`python3 -m prg32 cartridge build --required-feature ...`; multiplayer
projects also get `--multiplayer`, which sets the cartridge header flag. For
Advanced C projects the student lists them in **Required PRG32 features**.

| Blocks used | Feature |
| --- | --- |
| sound blocks | `audio` |
| *touches*, *draw 8x8 sprite* | `sprites` |
| tile and playfield blocks, `tile()` | `tilemap` |
| multiplayer blocks, `peers()` | `multiplayer` |

## Runtimes

The same `.prg32` cartridge runs on three PRG32 runtimes. They agree on the
game logic; a few presentation details differ by design:

| Detail | ESP32-C6 firmware and QEMU | PRG32-QT | Kit simulator |
| --- | --- | --- | --- |
| Colours | RGB565 | nearest colour of a 256-colour palette | RGB565 |
| Text font | 8 x 8 firmware font | its own 5 x 7 font | 8 x 8 firmware font |
| Undefined tile | painted with black | skipped | painted with black |
| Status bands | 20-pixel bands above and below | optional, off by default | debug line |
| Audio | I2S (board), UART PCM stream (QEMU) | Qt Multimedia | the firmware's engine in WebAssembly, played as PCM |

`tools/runtime_check.py` builds every example and runs it in the simulator,
on QEMU and on PRG32-QT (see `runtime_check.md`).
