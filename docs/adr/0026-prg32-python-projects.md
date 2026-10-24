# ADR-0026: PRG32 Python projects, compiled ahead of time to the game IR

**Status:** Accepted (2026-10-23). Amends ADR-0001 (project manifest: schema version 2) and
ADR-0024 (fixed project types: a fourth type).

## Context

Students who have outgrown Blocks often want a "real" text language before C. Python is the
language most of them meet first. A PRG32 cartridge, though, is a small RV32 program with no
operating system and no room for a Python interpreter, and the kit must never run student
code on the server. The audit brief (I18N-01 and PY-01 rows, `docs/briefs/`) asks for a Python
project mode that is a versioned, validated authoring language with deterministic C and
assembly output, editor support, debugging and packaging parity, and no Python execution.

## Decision

1. **Python is an authoring language, not a runtime.** No CPython or MicroPython is embedded in
   the cartridge or run during validation or builds. The pipeline is:

   ```text
   saved game.py
     -> ast.parse (CPython's parser, with size and nesting limits; never imported or run)
     -> allow-listed, statically typed PRG32 Python checks (python_project.py)
     -> the game IR (generator.IR_ABI): the same contract as the Blocks
     -> commented C (generator.ir_to_c) and, on request, RISC-V assembly (asm_generator)
     -> the sandboxed PRG32 toolchain -> PRG32 cartridge
   ```

2. **PRG32 Python, language version 1**, is defined in `docs/python_language.md`: `import prg32`;
   lifecycle functions `init`, `update` and `draw`; typed variables (`int` is a signed 32-bit
   number, `bool`, `list[int]` of fixed size); `if`/`elif`/`else`; `for name in range(...)`
   (at most 1024 rounds); assignments and augmented assignments; helper functions with typed
   parameters (copied in where they are called, no recursion); and the `prg32` module, whose
   functions are exactly the IR's statements and the kit's expression functions. Everything
   else is refused with a stable code and the line and column in game.py.
3. **Cartridge semantics are explicit, not inherited:** 32-bit wrap-around, `//` and `%`
   round toward zero like C and the RISC-V CPU (`-7 // 2` is `-3`), `x // 0` is `-1` and
   `x % 0` is `x`, `and`/`or`/`not` need `bool` values, comparisons cannot be chained, and
   C precedence is produced from Python's tree (brackets are added where they differ).
4. **Limits** stop denial of service in the compiler: 64 KiB and 4000 lines of source, 32
   nested brackets, 20 000 syntax nodes, tree depth 64, 12 nested blocks, 64 functions, 256
   variables, helper calls 8 deep, 4000 IR statements, 200 characters per IR expression.
5. **Project representation:** `game_json = {"source_mode": "python", "source_python": "...",
   "python_language_version": 1}`. The Python source is authoritative; IR, C, assembly and
   maps are artifacts made again on every build and never stored over the source. The type is
   fixed (ADR-0024): no save path turns a project into or out of Python, and there is no
   conversion to or from Python in version 1. A version the kit does not know is refused.
6. **Archives:** `prg32.project.json` schema version 2 adds `authoring_mode: "python"`, the file
   `src/game.py` and `python_language_version`. A version-1 document upgrades unchanged.
7. **Provenance and maps:** builds record the language, its version, the parser grammar, the
   SHA-256 of game.py and of the IR (`provenance.build_provenance`). Source maps carry
   `"python": [line, column, end line, end column]` per IR statement, so the debugger shows
   game.py, puts breakpoints on Python lines and steps "next Python line"; the markers never
   change the generated files (`source_maps.project_source_map`).
8. **Editor services** run in the browser from the committed language index
   (`tools/build_language_index.py` writes `python_project.api_reference()`): Monarch
   highlighting, completion, hover, signature help, go to definition and quick live checks.
   The live checks may add problems; only the server's compiler decides what is valid.

## Consequences

- Python, Blocks, C and assembly share one IR and one pair of generators, so one fix reaches
  every mode and the C/assembly parity tests cover Python too (`tests/test_python_project.py`).
- Some ordinary Python is refused (`while`, `break`, recursion, floats, classes, strings as
  values); the messages say what to write instead. A later language version may add more,
  each with its own tests.
- Generated comments call statements "steps" in Python projects ("Block" in Blocks projects).
- A Blocks -> Python conversion is not offered: the IR's integer conditions do not always
  type-check as PRG32 Python. It may come later as its own decision.
