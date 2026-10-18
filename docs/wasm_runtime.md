# Running real cartridges in the browser

The **Player** page (`/player`) runs a real `.prg32` cartridge in the
browser. It is not the Blocks preview: the cartridge's RISC-V machine code
runs in the same PRG32 core as PRG32-QT, compiled to WebAssembly. Blocks,
Advanced C and handwritten assembly cartridges all run there.

## For students

1. Compile your game (**Compile Cartridge**) and press **Play in browser**, or
   open **Player** and choose **Open a .prg32 file**.
2. Press **Play**. Buttons: arrows or W A S D, **Z**/**J** = A, **X**/**K** = B,
   **Enter**/**Space** = Select. On a tablet, use the on-screen buttons.
3. **Frame** runs exactly one frame (update + draw) and stops.
4. **Speed** (0.1× to 4×) changes how fast frames come. The game always
   thinks 33 ms passed per frame, so it behaves the same at every speed:
   under the screen, *Game time* is what the cartridge sees, *Real time* is
   your clock.

The Blocks **Play** button in the editor still shows the quick Blocks
preview, which runs your blocks directly (no RISC-V). The Player is how the
console really runs it.

## For teachers

- The cartridge runs only in the student's browser; nothing is sent to the
  server. A local `.prg32` file never leaves the computer.
- It works offline once the page has been opened (the service worker keeps
  `static/wasm/` and the runtime script).
- Timing is PRG32-QT's accurate ESP32-C6 profile (160 MHz virtual clock, one
  frame = 33 ms), so a game that is too slow on the console is late here too.
- Sound is an approximation (see `compatibility.md`).

## How it is built

```text
PRG32-QT src/core (C++, Qt-free)  ──┐
wasm/prg32_core_api.cpp (C API)  ───┼─ Emscripten ─► static/wasm/prg32-core.{js,wasm}  (≈ 125 KB)
                                    └─ C++ compiler ► prg32-core-harness (golden tests)
static/js/prg32_runtime.js: canvas, buttons, timing, Web Audio  ─► templates/player.html
```

- The core is **not copied** into this repository: `wasm/CMakeLists.txt`
  compiles PRG32-QT's `src/core` from a checkout (MIT licensed).
- `python3 tools/build_wasm.py --prg32qt ../PRG32-QT` rebuilds the module and
  writes `static/wasm/BUILD.json`: the PRG32-QT commit, the Emscripten version
  and the SHA-256 of both files. `--check` only compares.
- The C API (`prg32_load`, `prg32_frame`, `prg32_debug_step`, `prg32_pc`,
  `prg32_register`, `prg32_read_memory`, `prg32_state_json`, audio queue, …)
  is what the debugger (G5) will build on.

## How we know it is the same machine

`tests/test_wasm_runtime.py`:

| Check | Evidence |
| --- | --- |
| WebAssembly = native build of the same core | PC, x0–x31, retired instructions, virtual cycles, framebuffer FNV-1a and audio-call count after every 100 frames for 600 frames, on PRG32-QT's golden cartridges `Asteroids`, `Bach`, `PerformanceTest`, with scripted button presses. |
| Native build = PRG32-QT's `prg32qt-headless` | The last frame after 450 frames is byte-identical (PPM) for `Asteroids` and `Bach`. |
| Kit cartridges | Blocks (Pong), generated assembly, Advanced C and handwritten assembly cartridges built with the real toolchain give the same states in both builds and draw pixels. |
| Reproducible module | A fresh build from the recorded PRG32-QT commit with the recorded Emscripten gives the same bytes. |
| Audio | Calls made by `Bach` reach the browser host with valid kinds. |

These run when Node, CMake, a C++ compiler and a PRG32-QT checkout
(`PRG32QT_DIR`) are present, and skip otherwise. CI's `wasm-runtime` job runs
them against the committed module and against a fresh build.

## Limits

- Not done: multiplayer (no transport in the browser), Wi-Fi, score upload,
  the PRG32-QT performance overlay. Scores stay in memory.
- Sound: tones and notes are simple oscillators, PCM is played as recorded;
  PRG32-QT's mixer, envelopes and filters are not reproduced exactly.
- One cartridge per page at a time.
- Instruction stepping, registers and breakpoints exist in the C API but have
  no user interface yet (G5).
