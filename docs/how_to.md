# How-To Recipes

## How to use the simulator gamepad

Below the simulator screen, the classic-style gamepad lets students test games with a mouse or touch screen. Its direction pad sends `UP`, `DOWN`, `LEFT`, and `RIGHT`; the red buttons send `A` and `B`; and the middle buttons send `SELECT` and `START`. These are the same names used by the **if button pressed** blocks. Keyboard controls remain available: arrow keys, `Z`/`X`, `Enter`, and `Shift`.

## How to make a moving player

1. Add `when game starts`.
2. Add `set player_x to 150` and `set player_y to 180`.
3. Add `every frame update`.
4. Add `if button LEFT pressed`, then `change player_x by -3`.
5. Add `if button RIGHT pressed`, then `change player_x by 3`.
6. Add `keep player_x between 0 and 304`.
7. Add `every frame draw`.
8. Add `clear screen BLACK` and `draw rectangle x player_x y player_y w 16 h 16 color YELLOW`.

## How to inspect generated C

1. Open the project editor.
2. Click **Save**.
3. Click **Generate C**.
4. Read the C panel. Match each block to one generated C statement.

## How to download a PRG32 cartridge

1. Open the project editor.
2. Click **Download .prg32**. The browser saves a file such as `my-game-esp32c6.prg32`.
3. To test in the emulator instead, open the arrow next to the button and choose **QEMU emulator**.
4. Upload the PRG32 cartridge to a cartridge slot on the board.

The server needs the PRG32 toolchain for this step. Without it, nothing is
downloaded and the **Debug Log** tab explains what is missing.

## How to create an artifact

Artifacts are created by:

- generating C from a project;
- preparing a cartridge bundle;
- downloading a `.prg32` cartridge (the cartridge is also kept as an artifact);
- converting a sprite to C;
- uploading a file on the Artifacts page.

## How to move data to another machine

1. Stop the app.
2. Copy the `data/` directory.
3. Start the app on the new machine with `PRG32_KIT_DATA` pointing at that copy.

## How to use with a separate Cartridge Store

1. Start Cartridge Store.
2. Start PRG32-Construction-Kit.
3. Open **Publish**.
4. Create a profile pointing at the store URL.
5. Prepare a cartridge bundle from a project.
6. Publish the bundle.
