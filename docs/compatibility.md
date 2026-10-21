# Compatibility

## PRG32 cartridge ABI

| Item | Value | Source |
| --- | --- | --- |
| ABI | 1.6, hash `0x260f6136` | PRG32 `prg32/abi/abi_generated.py` |
| Also accepted by PRG32-QT | `0x006427c2`, `0x6be6e8d0` | PRG32-QT `src/core/Runtime.h` |
| Compiler target | `rv32imc_zicsr_zifencei` (SDK default) | PRG32 `prg32/prg32.py` |
| Runtime ISA | RV32IMAC interpreter | PRG32-QT `src/core/Rv32Cpu.h` |
| Kit-generated assembly | RV32IM `.S`, portable ABI table | `asm_generator.py` |

`project_format.SDK_ABI` copies the ABI values into every
`prg32.project.json`; `tests/test_project_format.py` fails if the installed
SDK disagrees.

## Project files

| Format | Read | Written |
| --- | --- | --- |
| `prg32-construction-kit-project-1.0` (single JSON export) | Yes, migrated to schema 1 | Yes (`/export`) |
| `prg32-project` schema 1 (archive) | Yes | Yes (`/archive`) |
| `prg32-project` schema > 1 | Refused with a "newer kit" message | — |

## Debugger parity with PRG32-QT

What PRG32-QT 0.4.1 offers (its `docs/DEBUGGING.md`, `/api/debug`), and what
the kit's **Player** debugger offers on the same machine code (G5). The
editor's Blocks preview is a separate thing: it runs the game IR, has
**Step** = one whole frame and shows the first 8 Blockly variables.

| Capability | PRG32-QT | Kit Player (browser) |
| --- | --- | --- |
| Debug mode on/off (bug button) | Yes | Yes (**Debug mode** switch); off = whole-frame execution |
| Pause / resume | Yes; resume ignores the current breakpoint once | Yes, same rule (`prg32_debug_resume`) |
| Single instruction step | Yes (stops inside an ABI call's host address) | Yes; **Step** also runs an ABI call the guest jumps into, so the PC stays in guest code. PRG32-QT's exact step is `prg32_debug_step` |
| Step over / step out | No | **Kit adds** (call/return recognition in the core) |
| Step frame | No (bug button off + run) | **Kit adds**: to the end of the frame, stopping at breakpoints |
| Speed 0.01×–4× | Yes, instrumented slices | Yes, same speeds and slicing |
| Address breakpoints (gutter) | Yes; no conditions; cleared when another cartridge loads | Yes; no conditions; **remembered per cartridge SHA-256** in the browser |
| Breakpoint hit count | No | **Kit adds** |
| x0–x31 with ABI names | Yes (hex) | Yes (hex + decimal tooltip; Advanced view); changed values highlighted (**kit adds**) |
| PC, update/draw phase | Yes | Yes |
| Disassembly following the PC; Init/Update/Draw/PC views | Yes (PRG32-QT's `RiscVDisassembler`) | Yes, same disassembler; also **go to any address** and machine words (Advanced) |
| Recently executed instructions in the listing | Yes (64-entry trace) | No: the core's trace is not exposed yet |
| Memory view, hex + ASCII, decimal or `0x` address | Yes (128 B in UI, ≤1024 B over HTTP) | Yes (128–1024 B) |
| Guest vs host time | FPS, host µs, instructions, cycles, late frames | Game (virtual) time vs real time, frames, instructions, cycles; no late-frame count or host µs |
| Input mask, audio waveform telemetry | Yes | No |
| Remote control | HTTP `/api/debug` | JavaScript `player.debug()` on the page (same commands and state names; no network endpoint) |
| Beginner / advanced views | No | **Kit adds**: beginner shows argument/return registers in decimal with explanations; both views share one state |
| CSRs | No | **Kit adds**: the counters a cartridge can read (`cycle`, `time`, `instret` and high halves), by the core's rule |
| C/assembly source breakpoints, line stepping | No | **Kit adds** for kit-compiled cartridges (DWARF line table, ADR-0015) |
| C locals, globals, call stack (DWARF CFI), watches, conditional breakpoints, stack view | No | **Kit adds** for kit-compiled cartridges; values optimised out at `-Os` are shown as such |
| Blockly block highlighting and block breakpoints | — | **Kit adds** (block → IR → source → address maps, ADR-0015) |

## Browser runtime parity with PRG32-QT

The browser runs PRG32-QT's own core (`docs/wasm_runtime.md`).

| Area | PRG32-QT | Browser (`/player`) |
| --- | --- | --- |
| RV32IMAC interpreter, ABI 1.6 (139 calls) | Yes | Same code; identical state in golden tests |
| Accurate ESP32-C6 timing (virtual clock) | Yes (default) | Yes (default) |
| 320 × 200 RGB565 framebuffer | Yes | Yes; identical frames to `prg32qt-headless` |
| Buttons (keyboard map, latch of quick taps) | Yes | Yes, same keys; on-screen buttons |
| Audio | Qt mixer (no ADSR, floating point) | The PRG32 firmware's own engine: 8 voices, ADSR, synth filter, samples, tracker, stereo mix (ADR-0021, `audio_engine.md`) |
| Multiplayer, Wi-Fi, score upload | Yes | No |
| Debugger UI | Yes | Yes (see the parity table above) |

## Hosts that run cartridges

| Host | How a kit cartridge gets there | Verified |
| --- | --- | --- |
| Browser (kit Player) | **Play in browser**, or open a `.prg32` on `/player` | Automated: golden and kit-cartridge tests |
| PRG32-QT | Download `.prg32`, **Import PRG32 cartridge**; or its web API on port 8080; or the Store (`delivery.md`) | Runtime headless (`runtime_check.md`); end-user import not yet recorded |
| PRG32-iOS | Not supported by the kit for now (ADR-0020) | Deferred |
| PRG32 console (ESP32-C6) | `python3 -m prg32 esp32c6 upload` over the console's Wi-Fi, or the Cartridge Store (`delivery.md`) | Not yet recorded (`tools/delivery_check.py`) |
