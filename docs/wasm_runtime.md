# Running real cartridges in the browser

The simulator on the right of the IDE, and the **Player** page (`/player`), run a real
`.prg32` cartridge in the browser: its RISC-V machine code runs in the same PRG32 core as
PRG32-QT, compiled to WebAssembly. Blocks, C and handwritten assembly cartridges all run
there.

## For students

1. In the IDE press **Run**: the kit builds the game and plays it on the right (also
   without an account; nothing is kept). Or open **Player** and choose **Open a .prg32 file**.
2. Press **Play**. Buttons: arrows or W A S D, **Z**/**J** = A, **X**/**K** = B,
   **Enter**/**Space** = Select. On a tablet, use the on-screen buttons.
3. **Frame** runs exactly one frame (update + draw) and stops.
4. **Speed** (0.01× to 4×) changes how fast frames come. The game always
   thinks 33 ms passed per frame, so it behaves the same at every speed:
   under the screen, *Game time* is what the cartridge sees, *Real time* is
   your clock.
5. The **Debugger** under the screen pauses the game on any RISC-V
   instruction: see `tutorials/07_debugger.md`.

Only when the kit's server cannot compile does the IDE fall back to the quick Blocks
preview, which runs your blocks directly (no RISC-V). The simulator is how the console
really runs it.

## For teachers

- The cartridge runs only in the student's browser; nothing is sent to the
  server. A local `.prg32` file never leaves the computer.
- It works offline once the page has been opened (the service worker keeps
  `static/wasm/` and the runtime script).
- Timing is PRG32-QT's accurate ESP32-C6 profile (160 MHz virtual clock, one
  frame = 33 ms), so a game that is too slow on the console is late here too.
- Sound is the PRG32 firmware's audio engine, compiled in (ADR-0021, `audio_engine.md`).

## How it is built

```text
PRG32-QT src/core (C++, Qt-free)  ──┐
wasm/prg32_core_api.cpp (C API)  ───┼─ Emscripten ─► static/wasm/prg32-core.{js,wasm}  (≈ 145 KB)
                                    └─ C++ compiler ► prg32-core-harness (golden tests)
static/js/prg32_runtime.js: canvas, buttons, timing, plays the engine's PCM  ─► templates/player.html
```

- The core is **not copied** into this repository: `wasm/CMakeLists.txt`
  compiles PRG32-QT's `src/core` from a checkout (MIT licensed).
- `python3 tools/build_wasm.py --prg32qt ../PRG32-QT` rebuilds the module and
  writes `static/wasm/BUILD.json`: the PRG32-QT commit, the Emscripten version
  and the SHA-256 of both files. `--check` only compares.
- The C API: `prg32_load`, `prg32_frame`, `prg32_state_json`, the audio
  queue, and the debugger calls below.

## The debugger (G5)

`static/js/prg32_debugger.js` is the panel; `PRG32CartridgePlayer.debug()`
in `prg32_runtime.js` is the protocol (ADR-0006): PRG32-QT's `/api/debug`
commands `enable`, `pause`, `resume`, `step`, `breakpoint`, `speed`, plus
the kit's `step_over`, `step_out`, `step_frame`, `clear_breakpoints`. It
returns PRG32-QT's state object (`phase`, `pc`, `paused`, `speed`,
`breakpoints`, `registers`, `memory_address`, `memory_hex`, …) with the
kit's additions (`entries`, `breakpoint_hits`, `guest_ns`, `wall_ms`,
`sha256`, `reason`). Errors are `{ok: false, error}` with PRG32-QT's words.

The work is done in the C++ core (`wasm/prg32_core_api.cpp`), so the native
harness and the browser run the very same code:

| C function | What it does |
| --- | --- |
| `prg32_debug_step(input)` | Exactly one `Runtime::debugStep`: PRG32-QT's step (a jump into an ABI call stops on the host address). |
| `prg32_debug_step_instruction(input)` | The panel's **Step**: one guest instruction; an ABI call the guest jumps into runs to its return. |
| `prg32_debug_run(input, budget, mode, stop_at_frame_end)` | Instrumented run, breakpoints checked before every instruction. Mode 0 continue, 1 step over, 2 step out. Returns −1 trap, 0 budget used, 1 frame end, 2 breakpoint, 3 done. |
| `prg32_debug_resume()` | PRG32-QT's resume rule: the next run ignores the breakpoint at the current address once. |
| `prg32_breakpoint(address, enabled)`, `prg32_breakpoints_clear()` | Breakpoints on any readable guest address. |
| `prg32_debug_pc()`, `prg32_debug_phase()`, `prg32_entry(0/1/2)` | Execution address (PC in a call, else the update entry, as PRG32-QT), idle/update/draw, init/update/draw entries. |
| `prg32_disassemble(address, count)` | PRG32-QT's `RiscVDisassembler`, as JSON rows. |
| `prg32_debug_state_json()` | Registers, PC, phase, breakpoints, hits, frames, retired, cycles, guest ns. |

How the panel plays in debug mode: one **resume**, then small slices of
`prg32_debug_run` each animation frame. The slice size follows the speed and
the instructions the last frame needed (PRG32-QT's "slices"), so at 0.01×
the PC walks visibly through the code. A slice that stops on a breakpoint
leaves the cartridge there; only **Continue** (resume) moves past it.

Step over and step out are not in PRG32-QT. The core recognises calls
(`jal`/`jalr`/`c.jal`/`c.jalr` that write `ra` or `t0`) and returns
(`jalr x0` through `ra`/`t0`, `c.jr ra`, or the end of an ABI call):

- **step over** a call runs until the PC is the next instruction with the
  stack pointer back at least where it was (so recursion works), or the
  update/draw function returns; on anything else it is a plain step;
- **step out** counts calls and returns until the current function returns;
  between frames it is a plain step.
Both stop at breakpoints and after 20 million instructions.

Breakpoints are remembered per cartridge in the browser's `localStorage`
(key `prg32-kit-breakpoints:<SHA-256 of the cartridge>`); PRG32-QT clears
them when another cartridge is loaded. The Beginner/Advanced choice is
remembered too (`prg32-kit-debugger-view`).

## How we know it is the same machine

`tests/test_wasm_runtime.py`:

| Check | Evidence |
| --- | --- |
| WebAssembly = native build of the same core | PC, x0–x31, retired instructions, virtual cycles, framebuffer FNV-1a and audio-call count after every 100 frames for 600 frames, on PRG32-QT's golden cartridges `Asteroids`, `Bach`, `PerformanceTest`, with scripted button presses. |
| Native build = PRG32-QT's `prg32qt-headless` | The last frame after 450 frames is byte-identical (PPM) for `Asteroids` and `Bach`. |
| Kit cartridges | Blocks (Pong), generated assembly, Advanced C and handwritten assembly cartridges built with the real toolchain give the same states in both builds and draw pixels. |
| Reproducible module | A fresh build from the recorded PRG32-QT commit with the recorded Emscripten gives the same bytes. |
| Audio | Calls made by `Bach` reach the browser host with valid kinds; the PCM hash is part of every compared state, so the WebAssembly and native builds render identical samples (`audio_engine.md`). |
| Debugger = native | A script of single steps, step over/out, breakpoints, continue, frames and playback slices gives identical PC, x0–x31, phase, breakpoints, hit counts, retired instructions and cycles after every command, on the golden cartridges and on kit cartridges (`--debug` mode of both harnesses). |
| Debugger semantics | N single steps = one `step:N`; a breakpoint on update stops once per frame and resume leaves it once; a stop without moving is not a new hit; playback slices stay on a breakpoint; step over runs a whole call; step out of update lands on draw; 29 instrumented frames = 29 normal frames (same registers, cycles and framebuffer). |
| Player protocol | `PRG32CartridgePlayer.debug()` in Node: PRG32-QT's error words, speed list, breakpoint validation, state fields, breakpoints remembered per SHA-256. |

These run when Node, CMake, a C++ compiler and a PRG32-QT checkout
(`PRG32QT_DIR`) are present, and skip otherwise. CI's `wasm-runtime` job runs
them against the committed module and against a fresh build.

## Limits

- Not done: multiplayer (no transport in the browser), Wi-Fi, score upload,
  the PRG32-QT performance overlay. Scores stay in memory.
- Sound follows the PRG32 firmware, not PRG32-QT's desktop mixer (which has no ADSR);
  `prg32_audio_notes` plays its notes in engine time while the game keeps running
  (on the console the game waits).
- One cartridge per page at a time.
- Debugger: source, block, variable, call-stack, watch and condition
  features need a cartridge compiled by the kit (debug map and block map,
  ADR-0015); a `.prg32` file opened from disk is debugged at address level.
- In debug mode music tracks do not advance: like PRG32-QT, the track player
  runs only in whole normal frames (`Runtime::frame`). Notes and sounds the
  cartridge plays itself still work.
- The disassembler is PRG32-QT's: a few compressed instructions it does not
  decode show as `.2byte` (for example `c.beqz`). They still run correctly.
