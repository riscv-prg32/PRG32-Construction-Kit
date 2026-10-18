# ADR-0006: One debug protocol shared with PRG32-QT

**Status:** Proposed

## Context

PRG32-QT exposes `GET/POST /api/debug` with commands `enable`, `pause`,
`resume`, `step`, `breakpoint`, `speed` and bounded memory reads. The brief
requires more (step over/into/out, watches, conditional breakpoints, DWARF).

## Decision

Use PRG32-QT's command vocabulary and state JSON as the protocol for the
browser debugger, carried over `postMessage` to the WASM worker instead of
HTTP. New commands are added to the Qt-free core first (so both hosts gain
them) and listed in a parity table in `docs/compatibility.md`.
