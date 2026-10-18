# ADR-0014: Offline language services from a generated PRG32 index

**Status:** Accepted (2026-10-19, refinement phase 3)

## Context

The IDE (ADR-0013) had Monaco with colours and problems after a server round
trip, but no completion, hover, navigation or live diagnostics (audit IDE-03,
IDE-04). The briefs forbid host language servers, arbitrary includes, file reads
and remote requests, and require the editor never to suggest an API or a
directive that the validators reject. Students also need to know which SDK
functions a *portable* cartridge may call: `prg32.h` declares the whole resident
firmware API, but a portable cartridge links only against the ABI table
(`prg32/abi`), so calling anything else fails with "undefined reference".

## Decision

1. **One generated index**, `static/js/ide/prg32_language_index.js`, built by
   `tools/build_language_index.py` from fixed inputs: the SDK headers a
   cartridge may include, the SDK's ABI table, the kit's own validators
   (`source_project._ALLOWED_HEADERS`, `ALLOWED_ASM_DIRECTIVES`) and
   student-written tables (RV32IMC + Zicsr instructions, registers, the ilp32
   calling convention). It records the ABI (1.6, `0x260f6136`, checked against
   `project_format.SDK_ABI`), the SDK revision and the SHA-256 of every input.
   Same inputs, same file; `--check` and a test compare it byte for byte.
2. **Portable vs resident:** functions in the ABI table are *portable* and are
   the only ones suggested; functions declared in the headers but missing from
   the table are *resident-only*, never suggested, and marked as an error when
   used. The index also carries a generated, read-only `prg32.h (portable API)`
   text that "go to declaration" opens; the real SDK headers stay on the server.
3. **Plain functions, no Monaco:** `static/js/ide/language.js` computes
   completion, hover, signature help, definitions, diagnostics and compiler-
   message normalization from text + index. `static/js/ide/monaco_language.js`
   only adapts them to Monaco providers, markers and an editor opener. Node
   runs the same file in tests (`tools/language_fixtures.mjs`).
4. **Live checks mirror the server, rule for rule,** with a map from every
   character back to the student's source, so a problem is marked at its exact
   line and columns. The server's `validate_c_source` / `validate_asm_source`
   are unchanged in what they accept; `validate_asm_source` now reports the
   line the student sees (multi-line comments and line continuations used to
   shift it). Extra editor-only checks (unknown instruction, wrong register,
   resident-only or unknown `prg32_` call) only add problems, never remove one.
5. **Compiler output** becomes problems with exact ranges; absolute paths are
   cut to the file name; link errors point at the call; common messages get a
   one-line explanation. Every problem code has a fixed, student-readable
   explanation.

## Consequences

- Works with the network off: nothing is fetched after the page loads (a browser
  test runs the services offline and checks the requests).
- `tests/test_language_services.py` holds exact fixtures
  (`tests/fixtures/language/cases.json`) for completion, hover, signature help,
  navigation, diagnostics and normalization in both languages, checks
  agreement with the validators on a corpus of unsafe sources and on 3 000
  generated ones, and checks that kit-generated C/assembly is clean.
- When the PRG32 SDK changes its ABI or headers, or the validators change,
  regenerate the index (`python3 tools/build_language_index.py`); the tests say
  so. The builder refuses an SDK whose ABI differs from the kit's.
- Not semantic analysis: there are no types, scopes or C parsing beyond the
  kit's rules; deeper errors still come from the compiler after Compile.
- The index (about 170 KB) loads with the IDE page only.
