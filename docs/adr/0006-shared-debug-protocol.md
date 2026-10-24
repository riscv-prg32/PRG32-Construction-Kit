# ADR-0006: One debug protocol shared with PRG32-QT

**Status:** Accepted — first slice implemented in G5 (2026-10-18)

## Context

PRG32-QT exposes `GET/POST /api/debug` with commands `enable`, `pause`,
`resume`, `step`, `breakpoint`, `speed` and bounded memory reads. The brief
requires more (step over/into/out, watches, conditional breakpoints, DWARF).

## Decision

Use PRG32-QT's command vocabulary and state JSON as the protocol for the
browser debugger, carried over `postMessage` to the WASM worker instead of
HTTP. New commands are added to the Qt-free core first (so both hosts gain
them) and listed in a parity table in `docs/compatibility.md`.

## Implementation notes (G5, first slice)

- `PRG32CartridgePlayer.debug({command, ...})` (`static/js/prg32_runtime.js`)
  takes PRG32-QT's commands with PRG32-QT's error words and returns its state
  names (`enabled`, `running`, `paused`, `phase`, `speed`, `pc`,
  `breakpoints`, `registers`, `memory_address`, `memory_hex`);
  `debugState({address, length})` is the `GET`. Kit additions: commands
  `step_over`, `step_out`, `step_frame`, `clear_breakpoints`; fields
  `entries`, `breakpoint_hits`, `last_breakpoint`, `reason`, `frames`,
  `retired`, `cycles`, `guest_ns`, `wall_ms`, `sha256`. PRG32-QT's
  `assembly_html` is replaced by `player.disassemble(address, count)` rows.
- **Transport deviation:** the core still runs on the page's main thread
  (as in G4), so the commands are direct method calls, not `postMessage`.
  The request and answer are plain JSON objects, so moving the core into a
  worker later changes the transport only.
- **Core-first deviation:** the new commands (breakpoint set, run with an
  instruction budget, resume-ignores-once, step over/out, disassembly) live
  in the kit's C interface `wasm/prg32_core_api.cpp` over PRG32-QT's
  unchanged `src/core` (`Runtime::debugStep`, `RiscVDisassembler`), not in
  PRG32-QT itself. Native and WebAssembly builds of that file are proven
  identical by `tests/test_wasm_runtime.py`. Moving step over/out into
  PRG32-QT's `Runtime` (so its desktop debugger gains them) is a PRG32-QT
  change for its maintainers.
