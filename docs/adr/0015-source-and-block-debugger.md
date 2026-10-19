# ADR-0015: Source and block debugging from saved maps and DWARF

**Status:** Accepted (2026-10-19, refinement phase 4)

## Context

The Player debugger (ADR-0006) works on machine addresses only. The release
gate (audit H-01, scenario D) needs C and assembly source breakpoints, the
active Blockly block, locals and globals, a call stack, watches, a CSR and a
stack view, a compressed-instruction stepping fixture and a safe fallback when
debug information is missing. It must not change generated code, cartridges or
guest results. The PRG32 builder (`python -m prg32 cartridge build`, in the
PRG32 repository) compiles with `-Os`, has no debug switch and deletes its ELF.

## Decision

One coordinate chain, every link a saved, deterministic artifact:

```text
Blockly block id --(source map)--> IR path --(source map)--> game.c / game.S lines
                 --(debug map: DWARF line table)--> guest addresses
```

1. **Source maps** (`source_maps.py`, artifact kind `source_map`): while
   parsing the blocks the kit notes which block made each IR statement
   (`update[2].then[0]`); while generating C or assembly it wraps each
   statement in marker lines, records the lines between them and removes the
   markers. The generated text is byte-identical to the normal output (a test
   checks every example), so the IR, the C and the assembly are unchanged.
2. **Debug builds without changing the cartridge** (`debug_build.py`): the
   kit gives the builder its own `--tool-prefix`: small per-build wrappers in
   `<build>/debugtools/` that call the real compiler with `-g` and
   `-fdebug-prefix-map`, and keep a copy of the linked ELF in `<build>/debug/`.
   `-g` does not change generated code; the kit checks it on every build: the
   loadable bytes of the ELF must equal the code in the cartridge, otherwise
   the ELF is thrown away. The wrappers run inside the same sandbox
   (ADR-0010) and only add flags. The cleaner fix (a `--debug-elf` option in
   the PRG32 builder) is proposed to the PRG32 maintainers.
3. **Debug maps** (`debug_info.py`, artifact kind `debug_map`): the server
   reads the ELF with pyelftools (pure Python, public domain) and writes a
   small JSON: line table, functions with parameters, locals and scopes,
   globals, types, call-frame rules (`.debug_frame`) and the link base. File
   names are reduced to their last part; the ELF itself is never served (its
   DWARF strings name server folders). Size and count limits apply; any error
   gives `{"status": "unavailable", "reason": ...}` and the Player stays an
   address-level debugger.
4. **The browser** (`static/js/source_debug.js`, plain functions tested in
   Node): PC → line → block, line/block → breakpoint addresses, call stack by
   unwinding with the call-frame rules, DWARF location expressions for
   variables (registers, frame-relative, absolute, constants; anything else
   is shown as "not available here"), values by type, watches (`name`,
   `a.b`, `a[3]`), and conditional breakpoints (`score > 10`) checked by the
   Player when the address breakpoint hits: if the condition is false it
   continues. Source and block breakpoints are address breakpoints in the
   core, so pausing and stepping are exactly the existing, differential-
   tested ones.
5. **CSRs and stack:** the core reports the counters a cartridge can read
   (`cycle`, `time`, `instret` and their high halves) in its debug state,
   computed by the same rule as its `csrr` (`wasm/prg32_core_api.cpp`); the
   stack view reads guest memory from `sp`.
6. **Compressed instructions:** `tests/fixtures/debug/compressed.S` and its
   committed cartridge step through 16- and 32-bit instructions in WebAssembly
   and natively, with identical state after each step.

## Consequences

- No database change: maps are artifacts linked to their cartridge
  (`metadata.cartridge_artifact_id`). `GET /api/artifacts/<id>/debug` (new,
  read-only, owner-checked) returns a cartridge's maps and source together.
- Optimised code (`-Os`) means some locals live only in registers for part of
  a function and some are optimised away; the debugger says so instead of
  guessing. Generated Blocks variables are globals and are always readable.
- When the PRG32 builder changes how it calls the compiler, the wrapper check
  fails safely (no debug map) and a test says so.
- Builds take slightly longer (pyelftools reads a ~50 KB ELF in well under a
  second); `PRG32_DEBUG_INFO=0` turns debug builds off.
