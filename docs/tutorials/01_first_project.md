# Tutorial 1: First Blocks Project

Goal: create a tiny PRG32 game that draws a player square.

## 1. Create the project

1. Open the home page.
2. Click **New Project**.
3. Keep **Blocks** selected. (The dialog also offers **C**, **Assembly (RISC-V)** and **Python
   (PRG32 Python)**: they start from a small working game, written as code and explained line by
   line.)
4. Title it `First Square`.
5. Click **Create**.

## 2. Build the start state

In the Blocks area:

1. Drag `when game starts`.
2. Add `set player_x to 150`.
3. Add `set player_y to 180`.

## 3. Draw the square

1. Drag `every frame draw`.
2. Add `clear screen BLACK`.
3. Add `draw rectangle x player_x y player_y w 16 h 16 color YELLOW`.

## 4. Run it

Click **Run** (Shift+F10). The kit builds your game and starts it in the simulator on the right:
you should see a yellow square on the PRG32 screen.

## 5. Save and export

1. Click **Save** (Ctrl+S).
2. Open the **Project** menu and choose **Export as JSON**.

The downloaded file is a Blocks PRG32 game stored as JSON.

## 6. Get a cartridge for your PRG32

Click **Compile** (it needs an account), then the **Download esp32c6 .prg32** link in the
**Build** tab. The kit compiles your blocks and your browser saves a file such as
`first-square-esp32c6.prg32`. That file is your PRG32 cartridge: copy it to a cartridge slot on
the board. The **Download qemu .prg32** link next to it is the same game for the QEMU emulator.
