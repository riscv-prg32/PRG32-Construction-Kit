# ADR-0004: Handwritten assembly authoring mode

**Status:** Proposed — blocked on a decision by the project owner

## Context

The full-IDE brief asks for an `assembly` authoring mode with handwritten
RISC-V assembly. `AGENTS.md` currently says assembly is generated only from
the validated game IR, "never from user-typed assembly", and that Advanced C
projects compile their own C only.

Handwritten assembly is as safe to assemble as C is to compile (both run the
GNU toolchain on the server), but it can use `.incbin`, `.include` and
arbitrary directives that read host files, so it needs its own validator.

## Options

1. Keep the current rule: no handwritten assembly.
2. Allow it with a directive allow-list (no `.incbin`, `.include`, `.macro`
   with includes; only `.text`, `.data`, `.globl`, `.word`, …) and the same
   entry-point check as C; update `AGENTS.md`.
3. Allow it only for the browser toolchain (G3) where nothing runs on the
   server.

## Decision

None yet. The manifest reserves `authoring_mode: "assembly"`; the importer
refuses it with a clear message until this ADR is accepted.
