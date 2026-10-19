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

## Debug your blocks, your C or your assembly

When you compile a project in the kit and press **Run & debug**, the Player
also knows your program, not only its instructions. Under the machine code
you see:

- **Blocks** (Blocks projects): your blocks. While the game is stopped, the
  block that is running has a blue outline. Click a block (or choose it in
  the list) and press **● Breakpoint on block**: the game stops every time
  that block starts.
- **game.c** or **game.S**: your source. The running line is blue. Press a
  line number to put a **●** breakpoint on that line. If a line has no code of
  its own (the compiler moved its work), the breakpoint goes to the next line
  that has some, and the Player tells you.
- **Next block** / **Next line**: run until the next block (or line) of your
  program. Function calls run whole.
- **Variables**: your Blocks variables (`score`, `ball_x`, ...) with their
  values. In Advanced view also the variables of the function that is running.
- **Watches**: type a name and press **Watch**: `score`, `player.x`,
  `heights[2]`, or a register such as `a0`.
- **Call stack**: which function called which. Press one to see its variables.
- **Stop only if...**: give a breakpoint a condition such as `score > 10`
  and the game stops there only when it is true.

Try it: put a breakpoint on the block that moves the ball, watch `ball_x`,
then press **Continue** a few times. Give the breakpoint the condition
`ball_x < 50`: now it stops only when the ball is near the left wall.

Sometimes a variable says *optimised out*: the compiler made your program
faster and did not keep that value at this point. The debugger says so
instead of guessing.

## Advanced view

**Advanced** shows all 32 registers in hexadecimal, the machine words of each
instruction, a memory viewer, and two more buttons:

- **Step over**: on a call (`jal`, `jalr`), runs the whole called function
  and stops on the next line.
- **Step out**: runs until the current function returns to its caller.

The memory viewer takes an address in decimal (`1082130432`) or hexadecimal
(`0x40800000`) and shows up to 1024 bytes as hex and as text. With a kit
cartridge, Advanced also shows the **counter CSRs** (`cycle`, `time`,
`instret`: what `csrr` would read) and the **stack**: the words around `sp`.

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
- Source and block debugging needs a cartridge compiled by the kit: the kit
  compiles with debug information on the side (the cartridge itself is
  exactly the same, `../adr/0015-source-and-block-debugger.md`). A `.prg32`
  opened from a file gets the machine-code debugger only.
- Good exercise with blocks: find which block changes `score`, using a
  breakpoint with the condition `score > 0`.
