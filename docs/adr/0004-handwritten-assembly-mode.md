# ADR-0004: Handwritten assembly authoring mode

**Status:** Accepted — option 2, decided by the project owner on 2026-10-18

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

Option 2. A project may be written in RISC-V assembly
(`game_json.source_mode: "asm"`, manifest `authoring_mode: "assembly"`,
archive file `src/game.S`). Before the PRG32 builder runs,
`source_project.validate_asm_source` checks:

- only allow-listed directives (`ALLOWED_ASM_DIRECTIVES`: sections, symbol
  visibility, alignment, data, text and `.equ`-style constants); sections are
  limited to `.text`, `.rodata`, `.data`, `.bss` and their sub-sections;
- no `include`, `incbin`, `__has_include` or `_Pragma` anywhere in code,
  whatever the case, so a macro cannot rebuild a file-reading directive;
- preprocessor lines are only `#define NAME number-expression` (no macro
  arguments, no `#`/`##`) and `#if`/`#ifdef`/`#ifndef`/`#elif`/`#else`/
  `#endif`/`#undef`; other `# text` lines are comments;
- labels `<prefix>_init`, `<prefix>_update`, `<prefix>_draw` exist and are
  `.globl`; size ≤ 256 KiB, no NUL bytes, no trigraphs.

Like the C check, this is a guard, not an OS sandbox (ADR-0005 still applies).
`AGENTS.md` was updated. Evidence: `tests/test_handwritten_assembly.py`,
including a real cartridge build when the toolchain is installed.
