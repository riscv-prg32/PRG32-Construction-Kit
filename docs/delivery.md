# Getting a game onto a PRG32

Everything here works on the classroom network, with no internet connection.

## For students

1. In the editor or IDE, press **Download .prg32**. You get a **PRG32 cartridge**.
2. Give it to your teacher, or put it on the PRG32 yourself as below.

## On the PRG32 console (ESP32-C6)

The console makes its own Wi-Fi. Join it, then, from a computer with the PRG32 SDK:

```bash
python3 -m prg32 esp32c6 upload game-esp32c6.prg32 --url http://192.168.4.1 --slot cart1
```

```bash
python3 -m prg32 esp32c6 run --url http://192.168.4.1 --slot cart1
```

Use the `esp32c6` cartridge for the console. Each slot (`cart0` … `cart7`) holds one
game; uploading replaces what was in that slot. (PRG32-QT has four slots, `cart0` …
`cart3`.) A Cartridge Store set up for the
class works too: publish from the kit, install from the Store on the console.

## In PRG32-QT (desktop)

Use the `qemu` or `esp32c6` cartridge:

1. Open PRG32-QT and choose **Import PRG32 cartridge**.
2. Pick the `.prg32` file. The game starts in the player.

PRG32-QT also offers the console's web API on port 8080, so the upload command
above works with `--url http://127.0.0.1:8080`.

## In the browser

**Play in browser** in the kit, or open the `.prg32` on the **Player** page. This is
the only target the kit checks automatically.

## PRG32-iOS

Not supported by the kit for now (ADR-0020). The kit does not hand cartridges to
the iOS app, and makes no claim that a downloaded cartridge works there.

## For teachers: recording that it worked

`tools/delivery_check.py` uploads cartridges to a console or to PRG32-QT, starts each
one, takes a screenshot and writes a record: each cartridge's SHA-256, the device's
runtime answer, the slot, whether the screen shows anything, the outcome, and the kit
and PRG32 SDK commits.

```bash
python3 tools/delivery_check.py device --url http://192.168.4.1 --slot cart7 --target "PRG32 console" --out records/console.json c-game.prg32 generated-asm-game.prg32 handwritten-asm-game.prg32
```

- Choose a slot you do not need: its game is replaced.
- Try one cartridge of each kind: Blocks or C, generated assembly, handwritten
  assembly. `tools/check_build.py --save-cartridges DIR` builds all of them.
- PRG32-QT has four slots (`cart0` … `cart3`); the tool refuses a slot the device does
  not have before sending anything. `--screenshots DIR` keeps each screenshot.
- `launched` means the device stored and started the cartridge and drew something.
  Watch it too, and write what you saw in `--notes`.
- `record` (instead of `device`) writes the hashes only, for example before
  importing by hand in PRG32-QT.

**Status:**

- **PRG32-QT:** recorded on 2026-10-21 in `docs/evidence/delivery/2026-10-21-prg32qt/`.
  Canonical PRG32-QT `f6d80ad` (unpatched, macOS) stored, started and drew five kit
  cartridges through its own web API: Blocks as C, Blocks as assembly, Advanced C,
  handwritten assembly, and the console audio check. The screenshots are kept. Their
  SHA-256 are the ones the kit's Docker image builds (`docs/evidence/toolchain/`).
- **PRG32 console:** no delivery has been recorded yet. It needs a console on the
  network.
