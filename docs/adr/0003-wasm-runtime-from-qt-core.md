# ADR-0003: Browser runtime is the PRG32-QT core compiled to WebAssembly

**Status:** Accepted — implemented in G4 (2026-10-18)

## Context

The kit's simulator interprets the kit's *game IR*, so it cannot run Advanced
C or any real `.prg32`. PRG32-QT's `src/core` is a Qt-free RV32IMAC
interpreter that implements all 139 entries of ABI 1.6 and already has
headless golden tests (`Asteroids.prg32`, `Bach.prg32`). PRG32-iOS shows the
cost of a second implementation: a Swift copy that must be kept in step.

## Decision

Compile `prg32qt_core` with Emscripten into a WASM module with a small C API
(load, init, frame, debugStep, registers, memory, framebuffer). Browser host
adapters supply input, audio (Web Audio), timing and storage. The guest stays
*interpreted inside WASM*. Additions needed by the browser (for example a
framebuffer export or step-over) are proposed **upstream** to PRG32-QT.

The IR simulator remains as the beginner "preview" and is labelled as such.

## Acceptance

Golden cartridges give the same framebuffer hashes, retired-instruction
counts and register state after N frames in `prg32qt-headless` and in the
WASM build under Node.

## Outcome

- `wasm/prg32_core_api.cpp` is a C interface over `prg32::Cartridge` and
  `prg32::Runtime`; `wasm/CMakeLists.txt` compiles it with PRG32-QT's
  `src/core` (commit recorded in `static/wasm/BUILD.json`) both with
  Emscripten and natively. No PRG32-QT source was changed or copied, so no
  upstream PR was needed yet.
- Size: `prg32-core.wasm` 108,535 bytes, `prg32-core.js` 14,895 bytes
  (Emscripten 6.0.12, `-O2`).
- Evidence: identical machine state native vs WebAssembly on the golden
  cartridges, identical frames native vs `prg32qt-headless`, and identical
  runs of kit-built cartridges (`docs/wasm_runtime.md`).
- The C API lives in the kit for now; if PRG32-QT wants a browser target,
  it can move upstream unchanged.
