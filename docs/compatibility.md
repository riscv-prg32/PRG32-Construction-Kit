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

What PRG32-QT 0.4.1 offers (`docs/DEBUGGING.md`), and what the kit offers.
The kit's current debugger works on the game IR, not machine code.

| Capability | PRG32-QT | Kit (browser) |
| --- | --- | --- |
| Pause / resume | Yes | Yes, on the game IR |
| Single instruction step | Yes | No: **Step** runs one whole frame (update + draw) of the IR |
| Step over / into / out | No | No |
| Speed 0.01×–4× | Yes | No |
| Address breakpoints | Yes (no conditions, cleared on load) | No |
| x0–x31 registers (hex) | Yes | No |
| CSRs | No | No |
| Memory view | Yes (≤128 B in UI, ≤1024 B over HTTP) | No |
| Disassembly, Init/Update/Draw/PC views | Yes | No |
| C locals / DWARF / call stack / watches | No | No |
| Blockly variable view | — | Partial: the first 8 variables as text under the screen |

Closing these gaps is G4/G5 (ADR-0003, ADR-0006).

## Browser runtime parity with PRG32-QT

The browser runs PRG32-QT's own core (`docs/wasm_runtime.md`).

| Area | PRG32-QT | Browser (`/player`) |
| --- | --- | --- |
| RV32IMAC interpreter, ABI 1.6 (139 calls) | Yes | Same code; identical state in golden tests |
| Accurate ESP32-C6 timing (virtual clock) | Yes (default) | Yes (default) |
| 320 × 200 RGB565 framebuffer | Yes | Yes; identical frames to `prg32qt-headless` |
| Buttons (keyboard map, latch of quick taps) | Yes | Yes, same keys; on-screen buttons |
| Audio | Qt mixer | Approximate: oscillators for tones/notes, PCM as recorded |
| Multiplayer, Wi-Fi, score upload | Yes | No |
| Debugger UI | Yes | Not yet (C API ready, G5) |

## Hosts that run cartridges

| Host | How a kit cartridge gets there | Verified |
| --- | --- | --- |
| Browser (kit Player) | **Play in browser**, or open a `.prg32` on `/player` | Automated: golden and kit-cartridge tests |
| PRG32-QT | Download `.prg32`, import in PRG32-QT; or publish to the Store and install from it | Manual, per `runtime_check.md` |
| PRG32-iOS | Download `.prg32`, share to the device, import with the app's file picker | Not verified here (no device) |
| PRG32 console (ESP32-C6) | Through the Cartridge Store | Not verified here (no hardware) |
