# Lesson 7: Look inside the processor with the debugger

Your game is a list of RISC-V instructions. The processor runs them one by
one, very fast: tens of thousands every frame. The **debugger** lets you
stop it and run one instruction at a time, to see what really happens.

You need a compiled cartridge: compile any project and press **Play in
browser**, or open a `.prg32` file on the **Player** page. The debugger is
the card under the screen.

## For students

1. Switch on **Debug mode**. Now the processor checks, before every
   instruction, whether you asked it to stop there.
2. Press **Step**. The blue row is the next instruction; after each step it
   moves down. Watch the **Registers**: the one that just changed turns
   yellow.
3. Click the grey space left of an address. A red **●** appears: that is a
   **breakpoint**. Press **Continue**: the game runs and stops just before
   that instruction. Press **Continue** again: it runs one more frame and
   stops there again.
4. **Step frame** runs to the end of the frame (update + draw) and stops,
   unless a breakpoint comes first.
5. Set the speed to **0.01×** and press **Continue**: you can watch the blue
   row walk through the code.

Things to look for:

- The **Update** and **Draw** buttons show where your `update` and `draw`
  functions start. Every frame the processor runs update, then draw.
- `a0` holds the first number a function receives, and the number it gives
  back. Put a breakpoint after a `jalr` (a function call) and look at `a0`.
- `sp` (the stack pointer) goes *down* when a function starts (`addi sp, sp,
  -16`) and back *up* when it ends.
- **Game time** is the time the game thinks has passed (33 ms per frame).
  **Real time** is your clock. At 0.01× they are very different, but the game
  behaves the same.

## Advanced view

**Advanced** shows all 32 registers in hexadecimal, the machine words of each
instruction, a memory viewer, and two more buttons:

- **Step over**: on a call (`jal`, `jalr`), runs the whole called function
  and stops on the next line.
- **Step out**: runs until the current function returns to its caller.

The memory viewer takes an address in decimal (`1082130432`) or hexadecimal
(`0x40800000`) and shows up to 1024 bytes as hex and as text.

Beginner and Advanced are two ways of looking at the same thing: switching
does not change the game, and the breakpoints stay.

## For teachers

- It is the same debugger as PRG32-QT's (same instructions, same rules:
  breakpoints are checked before an instruction runs; **Continue** leaves
  the current breakpoint once). Step over, step out, step frame and the
  beginner view are additions; see `../compatibility.md`.
- Breakpoints are remembered in the browser for that exact cartridge. A
  recompiled cartridge is a different one and starts with none.
- Everything runs in the student's browser; nothing is sent to the server.
- Good first exercises: count how many instructions one frame needs (watch
  the instruction counter between two stops at the same breakpoint); find
  the instruction that changes the x position of a sprite; compare a Blocks
  game with its generated assembly (**Generate Assembly** in the editor).
- Not yet: C variable names, the call stack, watches and conditional
  breakpoints, and highlighting the Blockly block that is running.
