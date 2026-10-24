# Checking games on PRG32 runtimes

`tools/runtime_check.py` repeats, outside the web app, everything a student's
click on **Compile** (and a download link in the IDE's Build tab) does, and then runs the result on real PRG32
runtimes:

```text
examples/*.json -> game IR -> C -> .prg32 (qemu, esp32c6)
    -> browser simulator (Node.js)
    -> PRG32-QT headless runner
    -> PRG32 firmware in Espressif QEMU
```

Each run presses the game's buttons with a fixed script and saves the last
frame from every runtime, so teachers can compare them side by side.

## Requirements

| Needed for | What |
| --- | --- |
| building | a PRG32 checkout where `python3 -m prg32 cartridge build --help` works, and `riscv32-esp-elf-gcc` on `PATH` (ESP-IDF 5.4) |
| simulator | Node.js |
| PRG32-QT | `prg32qt-headless` from a PRG32-QT build (`cmake -S . -B build-core -DPRG32QT_BUILD_APP=OFF`) |
| QEMU | Espressif `qemu-system-riscv32` and `riscv32-esp-elf-gdb` on `PATH`, and a QEMU firmware built with the CI profile so the staged cartridge boots directly |
| PNG figures | Pillow (`pip install pillow`) |

Build the QEMU firmware once in the PRG32 checkout (the `cicd` profile boots
the staged cartridge instead of the setup menu):

```bash
. $HOME/esp-idf/export.sh
DEFAULTS="profiles/sdkconfig.defaults;profiles/sdkconfig.defaults.qemu;profiles/sdkconfig.defaults.cicd"
idf.py -B build-qemu -D SDKCONFIG=build-qemu/sdkconfig -D "SDKCONFIG_DEFAULTS=$DEFAULTS" set-target esp32c3
idf.py -B build-qemu -D SDKCONFIG=build-qemu/sdkconfig -D "SDKCONFIG_DEFAULTS=$DEFAULTS" build
(cd build-qemu && python -m esptool --chip=esp32c3 merge_bin --output=qemu_flash.bin --fill-flash-size=4MB @flash_args)
python -c "from prg32.utilities.environment_check import ensure_qemu_efuse; ensure_qemu_efuse()"
```

Run the tool from the same shell. If `qemu-system-riscv32` or
`riscv32-esp-elf-gdb` is not found, add their folders under
`~/.espressif/tools/` to `PATH`. `--figures` needs Pillow in the Python that
runs the tool; without it the frames stay as `.ppm` files in `--out`.

## Run it

```bash
python3 tools/runtime_check.py --prg32 ../PRG32 \
  --qt-runner ../PRG32-QT/build-core/prg32qt-headless --qemu \
  --out /tmp/prg32-check --figures docs/figures/games
```

Example output:

```text
asteroids       PASS  code=9308 bytes  features=audio  simulator=ok  prg32qt=ok  qemu_run=ok
breakout        PASS  code=4784 bytes  features=audio,sprites  simulator=ok  prg32qt=ok  qemu_run=ok
pong            PASS  code=4644 bytes  features=audio,sprites  simulator=ok  prg32qt=ok  qemu_run=ok
snake           PASS  code=5120 bytes  features=audio,tilemap  simulator=ok  prg32qt=ok  qemu_run=ok
space_invaders  PASS  code=6420 bytes  features=audio,sprites  simulator=ok  prg32qt=ok  qemu_run=ok
feature_tour    PASS  code=5352 bytes  features=audio,multiplayer,sprites,tilemap  simulator=ok  prg32qt=ok  qemu_run=ok
```

`report.json` in the output folder has the details. Leave out `--qt-runner`
or `--qemu` to skip a runtime.

## How the QEMU screenshot is taken

The Espressif QEMU build has no `screendump` command. The tool connects
`riscv32-esp-elf-gdb` to QEMU's GDB stub, stops at the next
`prg32_gfx_present`, and copies the firmware framebuffer `g_fb` (320 x 240
RGB565) out of guest memory. That is the exact image the firmware sends to
the display. QEMU opens its SDL window while it runs; console keys (`w a s d`,
`z` = A, space = START) reach the firmware through the console UART.

## Browser simulator only

```bash
node tools/simulate.js examples/games/pong.json 200 pong.ppm 20-60:UP 100:A
```

prints the game variables as JSON and writes the last frame. The test suite
uses it to play every game for a few hundred frames.
