# ADR-0003: Browser runtime is the PRG32-QT core compiled to WebAssembly

**Status:** Proposed (needs a G4 spike with Emscripten; not installed here)

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
