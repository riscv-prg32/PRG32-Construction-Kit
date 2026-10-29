// PRG32 language services for the IDE (refinement phase 3, ADR-0014): completion, hover,
// signature help, "go to declaration", live diagnostics and compiler-message normalization,
// for Advanced C and handwritten RISC-V assembly.
//
// - Everything here is a plain function of the text and the PRG32 language index
//   (prg32_language_index.js, generated from the pinned PRG32 SDK by
//   tools/build_language_index.py). Nothing is fetched and nothing is sent anywhere,
//   so it works offline and gives the same answer every time.
// - The live checks repeat, rule for rule, the server's validators
//   (prg32_construction_kit/source_project.py: validate_c_source, validate_asm_source)
//   so a student sees a problem while typing, at the exact place. The server still
//   checks every build: these checks only explain, they never allow anything.
// - Suggestions come from the index only: the headers, functions and directives the
//   server accepts. Resident-firmware functions are never suggested.
// - Positions are 1-based lines and columns, like Monaco; endColumn is exclusive.
//
// No DOM and no Monaco here: tests run this file in Node (tools/language_fixtures.mjs).
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PRG32Language = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  // Messages in the reader's language when the page loaded the kit's i18n.js (ADR-0027);
  // English, from the text below, where it did not (Node.js tests and tools).
  const tr = typeof globalThis.tr === 'function' ? globalThis.tr
    : (key, english, values) => String(english).replace(/\{([a-z_][a-z0-9_]*)\}/g,
      (all, name) => (values && name in values ? String(values[name]) : all));

  const MAX_BYTES = 256 * 1024;
  // Mirrors of source_project.py, kept in the same order as the server checks them.
  const DIRECTIVE_START = /^\s*(?:#|%:)/;
  const C_INCLUDE = /^\s*#\s*include\s*[<"]([^>"]+)[>"]\s*$/;
  const C_ALLOWED_DIRECTIVE = /^\s*#\s*(?:define|ifndef|ifdef|if|elif|else|endif|undef)\b/;
  const C_FORBIDDEN_WORDS = /\b(?:asm|__asm|__asm__|_Pragma|__has_include|__has_include_next|__has_embed)\b/g;
  const ASM_SECTION = /^\.(?:text|data|bss|rodata)(?:\.[A-Za-z0-9_.]+)?$/;
  const ASM_LABEL = /^\s*(?:[A-Za-z_.$][\w.$]*|\d+)\s*:/;
  const ASM_DEFINE = /^\s*#\s*define\s+[A-Za-z_]\w*(?:\s+[\w\s+\-*/%()<>&|^~]*)?$/;
  const ASM_CONDITIONAL = /^\s*#\s*(?:ifndef|ifdef|if|elif|else|endif|undef)\b/;
  const CPP_DIRECTIVES = new Set(['define', 'undef', 'if', 'ifdef', 'ifndef', 'elif', 'elifdef', 'elifndef', 'else',
    'endif', 'include', 'include_next', 'import', 'embed', 'line', 'pragma', 'error', 'warning', 'ident', 'sccs',
    'assert', 'unassert']);
  const ASM_FILE_WORDS = /incbin|include|__has_include|_Pragma/i;
  // The one include an assembly game may write, exactly on a line of its own: the kit puts the
  // project's art in its place (project_assets.py, docs/project_art.md). It reads no file.
  const ASM_ASSETS_INCLUDE = /^[ \t]*(?:#|%:)[ \t]*include[ \t]*["<]prg32_assets\.S[">][ \t]*$/;
  const STRING = /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g;

  // Student-readable explanations for every problem code. They never contain server details.
  const EXPLAIN = {
    'python-too-big': tr('js.language.a_game_py_can_be_at', 'A game.py can be at most 64 KiB and 4000 lines.'),
    'python-loop': tr('js.language.a_while_loop_could_run_forever', 'A while loop could run forever and freeze the console. Count with  for i in range(n):  (at most 1024 rounds).'),
    'python-unsupported': tr('js.language.prg32_python_is_a_small_part', 'PRG32 Python is a small part of Python that can become a cartridge: typed variables, if/elif/else, for ... in range(...), your own functions and the prg32 module.'),
    'python-import': tr('js.language.a_prg32_python_game_imports_only', 'A PRG32 Python game imports only the prg32 module:  import prg32. Other modules need a computer with Python; a cartridge has none.'),
    'python-unsafe': tr('js.language.functions_that_run_text_as_code', 'Functions that run text as code or open files are not part of PRG32 Python: the game is translated into C, never run as Python.'),
    'python-print': tr('js.language.the_prg32_has_no_console_window', 'The PRG32 has no console window. Write on the screen with prg32.text(x, y, "TEXT") or prg32.number(value, x, y).'),
    'python-division': tr('js.language.prg32_numbers_are_whole_numbers_use', 'PRG32 numbers are whole numbers. Use // to divide (7 // 2 is 3); the remainder is %.'),
    'python-power': tr('js.language.write_the_multiplication_out_x_x', 'Write the multiplication out (x * x), or use a fixed number.'),
    'python-float': tr('js.language.prg32_numbers_are_whole_numbers_for', 'PRG32 numbers are whole numbers. For fractions, scale them: 256 can mean 1.0.'),
    'python-unknown-prg32': tr('js.language.this_name_is_not_part_of', 'This name is not part of the prg32 module. Check the spelling; Ctrl+Space lists what prg32 offers.'),
    'python-import-missing': tr('js.language.write_import_prg32_at_the_top', 'Write  import prg32  at the top of game.py before using prg32.'),
    'python-lifecycle': tr('js.language.python_three_functions', 'A PRG32 Python game has three functions: def init() -> None: runs once, def update() -> None: and def draw() -> None: run every frame.'),
    'empty': tr('js.language.write_the_game_before_checking_it', 'Write the game before checking it.'),
    'too-big': tr('js.language.a_cartridge_source_can_be_at', 'A cartridge source can be at most 256 KiB, without NUL bytes.'),
    'trigraph': tr('js.language.trigraphs_and_are_an_old_c', 'Trigraphs (??= and ??/) are an old C feature the kit does not accept.'),
    'comment': tr('js.language.a_comment_needs_a_matching_to', 'A /* comment needs a matching */ to end it.'),
    'c-include': tr('js.language.a_prg32_cartridge_can_include_only_art', 'A PRG32 cartridge can include only prg32.h, prg32_audio.h, prg32_assets.h (your project\'s art), stdint.h, stddef.h and stdbool.h. Other headers would need a C library or files on the server.'),
    'c-directive': tr('js.language.allowed_preprocessor_lines_include_appro', 'Allowed preprocessor lines: #include (approved headers), #define, #undef, #if, #ifdef, #ifndef, #elif, #else and #endif.'),
    'c-token-paste': tr('js.language.the_operator_can_build_hidden_words', 'The ## operator can build hidden words, so the kit does not accept it.'),
    'c-forbidden': tr('js.language.inline_assembly_and_pragma_could_read', 'Inline assembly and _Pragma could read files on the server while compiling. Write assembly in an Assembly project instead.'),
    'c-entry': tr('js.language.the_console_calls_three_functions_named', 'The console calls three functions named after your project title: init once, then update and draw for every frame. Each must be written exactly as  void NAME(void) { ... }.'),
    'c-resident-only': tr('js.language.this_function_exists_only_inside_the', 'This function exists only inside the PRG32 firmware. A portable cartridge can call only the functions in the PRG32 ABI, so the build would stop with "undefined reference".'),
    'c-unknown-api': tr('js.language.this_name_starts_with_prg32_but', 'This name starts with prg32_ but is not part of the PRG32 API. Check the spelling.'),
    'obsolete-buzzer': tr('js.language.the_buzzer_is_obsolete_prg32_games', 'The buzzer is obsolete: PRG32 games use the eight-voice audio engine (instruments with ADSR envelopes, stereo pan, sound effects and soundtracks made in AudioStudio). The server refuses this name.'),
    'asm-file-access': tr('js.language.include_incbin_and_pragma_could_read', 'include, incbin and _Pragma could read files on the server, so they are not allowed.'),
    'asm-preprocessor': tr('js.language.in_assembly_only_define_name_value', 'In assembly only  #define NAME value  and #if / #ifdef / #ifndef / #elif / #else / #endif / #undef are allowed as preprocessor lines.'),
    'asm-directive': tr('js.language.only_the_directives_the_kit_lists', 'Only the directives the kit lists are allowed; others could read files or change how the cartridge is built.'),
    'asm-section': tr('js.language.put_code_in_text_and_data', 'Put code in .text and data in .rodata, .data or .bss (or sub-sections such as .text.game).'),
    'asm-entry': tr('js.language.the_console_calls_three_labels_named', 'The console calls three labels named after your project title: init, update and draw. Each needs a label (NAME:) and .globl NAME so the console can find it.'),
    'asm-instruction': tr('js.language.this_is_not_an_rv32imc_instruction', 'This is not an RV32IMC instruction or pseudo-instruction the assembler knows.'),
    'asm-register': tr('js.language.risc_v_has_32_registers_x0', 'RISC-V has 32 registers: x0-x31, or by their ABI names zero, ra, sp, gp, tp, t0-t6, s0-s11 (fp = s0) and a0-a7.'),
    'compiler': tr('js.language.the_compiler_found_this_problem', 'The compiler found this problem.'),
  };
  // Common compiler messages, said in simpler words.
  const COMPILER_HINTS = [
    [/implicit declaration of function '?(prg32_\w+)'?/, name => tr('js.language.name_not_declared_check', '{name} is not declared: check the spelling. ', { name }) +
      tr('js.language.only_the_functions_in_prg32_h', 'Only the functions in prg32.h (portable API) can be used.')],
    [/implicit declaration of function/, () => tr('js.language.this_function_is_used_before_it', 'This function is used before it is declared. Declare or define it above, or check the spelling.')],
    [/expected ';'/, () => tr('js.language.a_statement_must_end_with_look', 'A statement must end with ; (look at the end of the line before, too).')],
    [/undeclared/, () => tr('js.language.this_name_is_not_declared_check', 'This name is not declared: check the spelling, or declare the variable first.')],
    [/undefined reference to/, () => tr('js.language.the_program_calls_something_that_does', 'The program calls something that does not exist in a PRG32 cartridge.')],
    [/conflicting types/, () => tr('js.language.this_name_is_declared_twice_with', 'This name is declared twice with different types.')],
    [/expected '\}'|expected declaration or statement at end of input/, () => tr('js.language.a_has_no_matching', 'A { has no matching }.')],
    [/unrecognized opcode|unknown opcode|illegal operands/, () => tr('js.language.the_assembler_does_not_understand_this', 'The assembler does not understand this instruction or its operands.')],
  ];

  let INDEX = null;
  let tables = null;

  function useIndex(index) {
    INDEX = index;
    tables = null;
  }

  function idx() {
    if (!INDEX) INDEX = (typeof window !== 'undefined' ? window : globalThis).PRG32LanguageIndex;
    if (!tables) {
      const c = INDEX.c;
      const asm = INDEX.asm;
      tables = {
        functions: new Map(c.functions.map(f => [f.name, f])),
        resident: new Map(c.resident_only.map(f => [f.name, f])),
        obsolete: new Map((c.obsolete || []).map(o => [o.name, o])),
        constants: new Map(c.constants.map(k => [k.name, k])),
        types: new Map(c.types.map(t => [t.name, t])),
        headers: new Set(c.headers),
        directives: new Map(asm.directives.map(d => [d.name, d])),
        instructions: new Map(asm.instructions.map(i => [i.name, i])),
        registers: new Map(),
      };
      for (const reg of asm.registers) {
        tables.registers.set(reg.name, reg);
        tables.registers.set(reg.abi, reg);
      }
      for (const [alias, target] of Object.entries(asm.register_aliases)) {
        tables.registers.set(alias, tables.registers.get(target));
      }
    }
    return tables;
  }

  // --- the project title -> entry names (generator.c_identifier) ---
  function entryPrefix(title) {
    let raw = (title || 'prg32_game').trim().toLowerCase();
    raw = raw.replace(/[^A-Za-z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!raw) raw = 'prg32_game';
    if (/^[0-9]/.test(raw)) raw = '_' + raw;
    return raw.slice(0, 48);
  }

  // --- text with a map back to the student's source ---

  // Comments removed like source_project._without_comments_mapped: continuations joined,
  // each comment one space. origin[i] is the source offset of output character i.
  function withoutComments(source) {
    const chars = [];
    const from = [];
    for (let i = 0; i < source.length; i++) {
      if (source[i] === '\\' && source[i + 1] === '\n') { i += 1; continue; }
      if (source[i] === '\\' && source[i + 1] === '\r' && source[i + 2] === '\n') { i += 2; continue; }
      chars.push(source[i]);
      from.push(i);
    }
    const text = chars.join('');
    const out = [];
    const origin = [];
    let quote = '';
    let i = 0;
    while (i < text.length) {
      const ch = text[i];
      if (quote) {
        out.push(ch); origin.push(from[i]);
        if (ch === '\\' && i + 1 < text.length) { out.push(text[i + 1]); origin.push(from[i + 1]); i += 2; continue; }
        if (ch === quote || ch === '\n') quote = '';
        i += 1;
      } else if (ch === '"' || ch === "'") {
        quote = ch; out.push(ch); origin.push(from[i]); i += 1;
      } else if (text.startsWith('/*', i)) {
        const end = text.indexOf('*/', i + 2);
        if (end < 0) return { text: null, origin: null, unterminated: from[i] };
        out.push(' '); origin.push(from[i]); i = end + 2;
      } else if (text.startsWith('//', i)) {
        const end = text.indexOf('\n', i);
        out.push(' '); origin.push(from[i]); i = end < 0 ? text.length : end;
      } else {
        out.push(ch); origin.push(from[i]); i += 1;
      }
    }
    return { text: out.join(''), origin };
  }

  function withoutStrings(mapped) {
    const out = [];
    const origin = [];
    const keep = (from, to) => {  // a loop, not push(...array): sources can be long
      out.push(mapped.text.slice(from, to));
      for (let i = from; i < to; i++) origin.push(mapped.origin[i]);
    };
    let last = 0;
    for (const match of mapped.text.matchAll(STRING)) {
      keep(last, match.index);
      out.push('""');
      origin.push(mapped.origin[match.index], mapped.origin[match.index + match[0].length - 1]);
      last = match.index + match[0].length;
    }
    keep(last, mapped.text.length);
    return { text: out.join(''), origin };
  }

  // Python's str.splitlines() boundaries (it also splits on \r, \v, \f, \x1c-\x1e, \x85, \u2028/9).
  function splitLines(text) {
    const lines = [];
    const re = /\r\n|[\n\r\v\f\x1c\x1d\x1e\x85\u2028\u2029]/g;
    let start = 0;
    let match;
    while ((match = re.exec(text))) {
      lines.push({ text: text.slice(start, match.index), start });
      start = match.index + match[0].length;
    }
    if (start < text.length) lines.push({ text: text.slice(start), start });
    return lines;
  }

  function positionAt(source, offset) {
    const before = source.slice(0, Math.max(0, offset));
    const line = before.split('\n').length;
    const column = offset - (before.lastIndexOf('\n') + 1) + 1;
    return { line, column };
  }

  function lineEnd(source, line) {
    return (source.split('\n')[line - 1] || '').replace(/\r$/, '').length + 1;
  }

  // A problem from offsets into mapped text (start inclusive, end exclusive).
  function problem(source, mapped, start, end, severity, code, message) {
    const first = mapped.origin[Math.min(start, mapped.origin.length - 1)] ?? source.length;
    const last = end > start ? mapped.origin[Math.min(end - 1, mapped.origin.length - 1)] + 1 : first + 1;
    return problemAt(source, first, last, severity, code, message);
  }

  function problemAt(source, first, last, severity, code, message) {
    const from = positionAt(source, first);
    let to = positionAt(source, Math.max(last, first + 1));
    if (to.line !== from.line) to = { line: from.line, column: lineEnd(source, from.line) };
    if (to.column <= from.column) to = { line: from.line, column: from.column + 1 };
    return { severity, code, message, explanation: EXPLAIN[code] || '', line: from.line, column: from.column,
      endLine: to.line, endColumn: to.column };
  }

  function wholeLine(source, line, severity, code, message) {
    const text = (source.split('\n')[line - 1] || '').replace(/\r$/, '');
    const indent = text.length - text.trimStart().length;
    return { severity, code, message, explanation: EXPLAIN[code] || '', line, column: indent + 1, endLine: line,
      endColumn: Math.max(indent + 2, text.trimEnd().length + 1) };
  }

  function basicChecks(source, kind) {
    if (typeof source !== 'string' || !source.trim()) {
      return [{ severity: 'error', code: 'empty', message: tr('js.language.kind_source_is_empty', '{kind} source is empty', { kind }), explanation: EXPLAIN.empty,
        line: 1, column: 1, endLine: 1, endColumn: 2 }];
    }
    const problems = [];
    if (new TextEncoder().encode(source).length > MAX_BYTES || source.includes('\0')) {
      problems.push(wholeLine(source, 1, 'error', 'too-big', tr('js.language.kind_source_too_big', '{kind} source exceeds 256 KiB or contains NUL bytes', { kind })));
    }
    for (const match of source.matchAll(/\?\?[=/]/g)) {
      problems.push(problemAt(source, match.index, match.index + 3, 'error', 'trigraph',
        tr('js.language.trigraphs_and_are_not_supported', 'Trigraphs (??= and ??/) are not supported')));
    }
    return problems;
  }

  // --- C ---

  function cDiagnostics(source, title) {
    const problems = basicChecks(source, 'C');
    if (problems.some(p => p.code === 'empty')) return problems;
    const code = withoutComments(source);
    if (code.text === null) {
      problems.push(problemAt(source, code.unterminated, code.unterminated + 2, 'error', 'comment',
        tr('js.language.c_source_has_a_comment_that', 'C source has a comment that never ends')));
      return problems;
    }
    for (const line of codeLines(code)) {
      if (!DIRECTIVE_START.test(line.text)) continue;
      const directive = line.text.replace(/^\s*%:/, '#');
      const include = directive.match(C_INCLUDE);
      if (include && idx().headers.has(include[1])) continue;
      if (C_ALLOWED_DIRECTIVE.test(directive)) continue;
      if (include) {
        const at = line.text.indexOf(include[1], line.text.indexOf('include') + 7);
        problems.push(problem(source, code, line.start + at, line.start + at + include[1].length, 'error', 'c-include',
          tr('js.language.header_not_available', 'The header {header} is not available in a PRG32 cartridge', { header: include[1] })));
      } else {
        const lead = line.text.length - line.text.trimStart().length;
        problems.push(problem(source, code, line.start + lead, line.start + line.text.trimEnd().length, 'error',
          'c-directive', tr('js.language.only_approved_prg32_standard_headers_and', 'Only approved PRG32/standard headers and basic conditional or define directives are supported')));
      }
    }
    const bare = withoutStrings(code);
    for (const match of bare.text.matchAll(/##|%:%:/g)) {
      problems.push(problem(source, bare, match.index, match.index + match[0].length, 'error', 'c-token-paste',
        tr('js.language.the_token_pasting_operator_is_not', 'The ## token-pasting operator is not supported')));
    }
    for (const match of bare.text.matchAll(C_FORBIDDEN_WORDS)) {
      problems.push(problem(source, bare, match.index, match.index + match[0].length, 'error', 'c-forbidden',
        tr('js.language.word_not_supported_in_c', '\'{word}\' is not supported in PRG32 cartridge C', { word: match[0] })));
    }
    const prefix = entryPrefix(title);
    const escaped = prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const lifecycle = new RegExp(`\\bvoid\\s+(${escaped}_(?:init|update|draw))\\s*\\(\\s*void\\s*\\)\\s*\\{`, 'g');
    const found = new Set([...bare.text.matchAll(lifecycle)].map(match => match[1]));
    for (const phase of ['init', 'update', 'draw']) {
      const name = `${prefix}_${phase}`;
      if (found.has(name)) continue;
      const near = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).exec(bare.text);
      const message = tr('js.language.c_must_define_lifecycle', 'C source must define void {prefix}_init/update/draw(void): ', { prefix }) +
        (near ? tr('js.language.write_name_as', 'write {name} as  void {name}(void) { ... }', { name }) : tr('js.language.name_is_missing', 'void {name}(void) is missing', { name }));
      problems.push(near ? problem(source, bare, near.index, near.index + name.length, 'error', 'c-entry', message)
        : wholeLine(source, 1, 'error', 'c-entry', message));
    }
    // Beyond the server's checks: calls the portable ABI cannot make.
    const defined = new Set([...bare.text.matchAll(/\b([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{/g)].map(match => match[1]));
    obsoleteChecks(source, bare, problems);
    for (const match of bare.text.matchAll(/\bprg32_\w+\b/g)) {
      const name = match[0];
      if (idx().obsolete.has(name)) continue;
      if (idx().resident.has(name)) {
        problems.push(problem(source, bare, match.index, match.index + name.length, 'error', 'c-resident-only',
          tr('js.language.resident_not_portable', '{name} belongs to the resident PRG32 firmware, not to the portable cartridge ABI {abi}: the cartridge would not link', { name, abi: `${INDEX.abi.major}.${INDEX.abi.minor}` })));
      } else if (!idx().functions.has(name) && !idx().types.has(name) && !defined.has(name)
                 && /^\s*\(/.test(bare.text.slice(match.index + name.length))) {
        problems.push(problem(source, bare, match.index, match.index + name.length, 'warning', 'c-unknown-api',
          tr('js.language.not_a_prg32_function', '{name} is not a PRG32 function', { name })));
      }
    }
    return sortProblems(problems);
  }

  function codeLines(mapped) {
    return splitLines(mapped.text);
  }

  // --- assembly ---

  function asmStatements(text) {
    // source_project._asm_statements, with the offset of each statement in the line
    const body = text.split('#', 1)[0];
    const out = [];
    let offset = 0;
    for (const part of body.split(';')) {
      const lead = part.length - part.trimStart().length;
      if (part.trim()) out.push({ text: part.trim(), at: offset + lead });
      offset += part.length + 1;
    }
    return out;
  }

  function asmSymbols(bare) {
    const labels = new Map();
    const names = new Set();
    for (const line of splitLines(bare.text)) {
      let rest = line.text;
      let at = 0;
      let match;
      while ((match = rest.match(ASM_LABEL))) {
        const name = match[0].replace(/:$/, '').trim();
        if (!labels.has(name)) labels.set(name, bare.origin[line.start + at + match[0].indexOf(name)]);
        at += match[0].length;
        rest = rest.slice(match[0].length);
      }
      const define = line.text.match(/^\s*#\s*define\s+([A-Za-z_]\w*)/);
      if (define) names.add(define[1]);
      for (const equ of line.text.matchAll(/\.(?:equ|set|equiv)\s+([A-Za-z_.$][\w.$]*)/gi)) names.add(equ[1]);
    }
    return { labels, names };
  }

  function asmDiagnostics(source, title) {
    const problems = basicChecks(source, tr('js.language.assembly', 'Assembly'));
    if (problems.some(p => p.code === 'empty')) return problems;
    const noComments = withoutComments(source);
    if (noComments.text === null) {
      problems.push(problemAt(source, noComments.unterminated, noComments.unterminated + 2, 'error', 'comment',
        tr('js.language.c_source_has_a_comment_that', 'C source has a comment that never ends')));
      return problems;
    }
    const bare = withoutStrings(noComments);
    const sourceLines = source.split('\n');
    const lines = splitLines(bare.text).filter(line => {
      const number = positionAt(source, bare.origin[line.start] ?? source.length).line;
      return !ASM_ASSETS_INCLUDE.test((sourceLines[number - 1] || '').replace(/\r$/, ''));
    });
    // Words that read files: in preprocessor lines anywhere, elsewhere before a '#' comment.
    for (const line of lines) {
      const code = DIRECTIVE_START.test(line.text) ? line.text : line.text.split('#', 1)[0];
      const found = ASM_FILE_WORDS.exec(code);
      if (found) {
        problems.push(problem(source, bare, line.start + found.index, line.start + found.index + found[0].length,
          'error', 'asm-file-access',
          tr('js.language.asm_word_reads_files', '\'{word}\' is not allowed in PRG32 cartridge assembly: it could read files on the server', { word: found[0] })));
      }
    }
    const symbols = asmSymbols(bare);
    for (const line of lines) {
      const number = positionAt(source, bare.origin[line.start] ?? source.length).line;
      if (DIRECTIVE_START.test(line.text)) {
        const directive = line.text.replace(/^\s*%:/, '#');
        const word = directive.match(/^\s*#\s*(\w*)/)[1];
        if (ASM_CONDITIONAL.test(directive) || ASM_DEFINE.test(directive) || !CPP_DIRECTIVES.has(word)) continue;
        const lead = line.text.length - line.text.trimStart().length;
        problems.push(problem(source, bare, line.start + lead, line.start + line.text.trimEnd().length, 'error',
          'asm-preprocessor', tr('js.language.asm_preprocessor_only', 'Line {line}: only \'#define NAME value\' and #if/#ifdef/#else/#endif are allowed as preprocessor lines', { line: number })));
        continue;
      }
      for (const statement of asmStatements(line.text)) {
        let text = statement.text;
        let at = statement.at;
        let label;
        while ((label = text.match(ASM_LABEL))) {
          const rest = text.slice(label[0].length);
          at += label[0].length + (rest.length - rest.trimStart().length);
          text = rest.trim();
        }
        if (!text) continue;
        const start = line.start + at;
        if (text.startsWith('.')) {
          const name = text.split(' ')[0].split('\t')[0].toLowerCase();
          if (!idx().directives.has(name)) {
            problems.push(problem(source, bare, start, start + name.length, 'error', 'asm-directive',
              tr('js.language.asm_directive_not_allowed', 'Line {line}: the directive {name} is not allowed. Allowed: {allowed}', { line: number, name, allowed: [...idx().directives.keys()].sort().join(', ') })));
          } else if (name === '.section') {
            const rest = text.slice(text.indexOf(' ') + 1);
            const section = text.indexOf(' ') < 0 ? '' : rest.split(',')[0].trim();
            if (!ASM_SECTION.test(section)) {
              const offset = section ? text.indexOf(section, name.length) : 0;
              const length = section ? section.length : name.length;
              problems.push(problem(source, bare, start + offset, start + offset + length, 'error', 'asm-section',
                tr('js.language.asm_section_not_allowed', 'Line {line}: use .text, .rodata, .data or .bss sections, not \'{section}\'', { line: number, section })));
            }
          }
          continue;
        }
        problems.push(...asmInstructionChecks(source, bare, start, text, symbols));
      }
    }
    const prefix = entryPrefix(title);
    for (const phase of ['init', 'update', 'draw']) {
      const name = `${prefix}_${phase}`;
      const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const labelAt = new RegExp(`^\\s*${escaped}\\s*:`, 'm').exec(bare.text);
      if (!labelAt) {
        problems.push(wholeLine(source, 1, 'error', 'asm-entry', tr('js.language.asm_must_define_label', 'Assembly source must define the label {name}:', { name })));
        continue;
      }
      if (!new RegExp(`^\\s*\\.glob(?:a)?l\\s+${escaped}\\s*(?:[#;]|$)`, 'mi').test(bare.text)) {
        const offset = labelAt.index + labelAt[0].indexOf(name);
        problems.push(problem(source, bare, offset, offset + name.length, 'error', 'asm-entry',
          tr('js.language.asm_must_make_visible', 'Assembly source must make {name} visible with .globl {name}', { name })));
      }
    }
    obsoleteChecks(source, bare, problems);
    return sortProblems(problems);
  }

  // The old buzzer (prg32_buzzer_*, prg32_note_t): refused by the server, so an error here too, saying what to use.
  function obsoleteChecks(source, bare, problems) {
    for (const match of bare.text.matchAll(/\b(?:prg32_buzzer_\w*|prg32_note_t|PRG32_PIN_BUZZER)\b/g)) {
      const entry = idx().obsolete.get(match[0]);
      problems.push(problem(source, bare, match.index, match.index + match[0].length, 'error', 'obsolete-buzzer',
        tr('js.language.obsolete_buzzer_use', '{name} belongs to the old PRG32 buzzer, which is no longer supported. Use {instead}.', { name: match[0], instead: entry ? entry.instead : tr('js.language.the_prg32_audio_engine_prg32_audio', 'the PRG32 audio engine (prg32_audio_*)') })));
    }
  }

  const REGISTER_LIKE = /^(?:x\d+|a\d+|s\d+|t\d+)$/i;

  // Beyond the server's checks (the assembler would refuse these): unknown instructions, wrong registers.
  function asmInstructionChecks(source, bare, start, text, symbols) {
    const out = [];
    const mnemonic = text.match(/^[A-Za-z_][\w.]*/);
    if (!mnemonic) return out;
    const name = mnemonic[0];
    if (!idx().instructions.has(name.toLowerCase()) && !symbols.names.has(name)) {
      out.push(problem(source, bare, start, start + name.length, 'error', 'asm-instruction',
        tr('js.language.not_an_rv32imc_instruction', '{name} is not an RV32IMC instruction', { name })));
      return out;
    }
    const operands = text.slice(name.length);
    for (const token of operands.matchAll(/(?<![\w.$%])[A-Za-z_][\w]*/g)) {
      const word = token[0];
      if (!REGISTER_LIKE.test(word) || idx().registers.has(word.toLowerCase())) continue;
      if (symbols.labels.has(word) || symbols.names.has(word)) continue;
      const offset = start + name.length + token.index;
      out.push(problem(source, bare, offset, offset + word.length, 'error', 'asm-register',
        `${word} is not a RISC-V register`));
    }
    return out;
  }

  function sortProblems(problems) {
    return problems.sort((a, b) => a.line - b.line || a.column - b.column || a.code.localeCompare(b.code));
  }

  function diagnostics(language, source, options) {
    const title = (options || {}).title;
    if (language === 'python') return pythonDiagnostics(source);
    return language === 'asm' ? asmDiagnostics(source, title) : cDiagnostics(source, title);
  }

  // --- PRG32 Python (ADR-0026) ---
  // Quick checks while typing. The server's compiler (python_project.py) decides what is valid:
  // these checks only point at the most common problems earlier, never accept more.

  // game.py with the inside of strings and comments blanked out, so offsets stay the same.
  function pythonBare(source) {
    let out = '';
    let i = 0;
    let quote = '';
    while (i < source.length) {
      const ch = source[i];
      if (quote) {
        if (ch === '\\' && i + 1 < source.length) { out += '  '; i += 2; continue; }
        if (source.startsWith(quote, i)) { out += quote; i += quote.length; quote = ''; continue; }
        out += ch === '\n' ? '\n' : ' ';
        i += 1;
      } else if (ch === '#') {
        while (i < source.length && source[i] !== '\n') { out += ' '; i += 1; }
      } else if (ch === '"' || ch === "'") {
        quote = source.startsWith(ch.repeat(3), i) ? ch.repeat(3) : ch;
        out += quote;
        i += quote.length;
      } else {
        out += ch;
        i += 1;
      }
    }
    return out;
  }

  function pythonNames() {
    const py = INDEX.python;
    return { functions: new Map(py.functions.map(fn => [fn.name, fn])), constants: new Set(py.constants), py };
  }

  function pythonDiagnostics(source) {
    if (typeof source !== 'string' || !source.trim()) {
      return [{ severity: 'error', code: 'empty', message: tr('js.language.game_py_is_empty', 'game.py is empty'), explanation: EXPLAIN.empty,
        line: 1, column: 1, endLine: 1, endColumn: 2 }];
    }
    const problems = [];
    const limits = INDEX.python.limits;
    if (new TextEncoder().encode(source).length > limits.source_bytes || source.split('\n').length > limits.lines
        || source.includes('\0')) {
      problems.push(wholeLine(source, 1, 'error', 'python-too-big', tr('js.language.game_py_is_too_big', 'game.py is too big')));
    }
    const bare = pythonBare(source);
    const names = pythonNames();
    const add = (re, code, message) => {
      for (const match of bare.matchAll(re)) {
        const start = match.index + (match[1] ? match[0].indexOf(match[1]) : 0);
        const word = match[1] || match[0];
        problems.push(problemAt(source, start, start + word.length, 'error', code,
          typeof message === 'function' ? message(word) : message));
      }
    };
    add(/^[ \t]*(while)\b/gm, 'python-loop', tr('js.language.python_while', '\'while\' is not part of PRG32 Python: use for ... in range(...)'));
    add(/^[ \t]*(class|try|except|finally|with|async|nonlocal|del|raise|assert|match)\b/gm, 'python-unsupported',
      word => tr('js.language.python_word_unsupported', '\'{word}\' is not part of PRG32 Python', { word }));
    add(/\b(lambda|yield|await)\b/g, 'python-unsupported', word => tr('js.language.python_word_unsupported', "'{word}' is not part of PRG32 Python", { word }));
    add(/^[ \t]*(import[ \t]+(?!prg32[ \t]*$)[^\n]*)/gm, 'python-import', tr('js.language.prg32_python_imports_only_one_module', 'PRG32 Python imports only one module: import prg32'));
    add(/^[ \t]*(from[ \t]+\w[^\n]*)/gm, 'python-import', tr('js.language.python_from_import', 'Write \'import prg32\', then prg32.name(...)'));
    add(/\b(eval|exec|open|compile|__import__|getattr|setattr|delattr|globals|locals|vars|input|breakpoint)[ \t]*\(/g,
      'python-unsafe', word => tr('js.language.python_call_unsupported', '{word}(...) is not part of PRG32 Python', { word }));
    add(/\b(print)[ \t]*\(/g, 'python-print', tr('js.language.the_prg32_has_no_console_use', 'The PRG32 has no console: use prg32.text or prg32.number'));
    add(/(?<![/])\/(?![/])/g, 'python-division', tr('js.language.python_slash', '\'/\' makes a fraction: use // for whole numbers'));
    add(/\*\*/g, 'python-power', tr('js.language.python_power', '\'**\' is not part of PRG32 Python yet'));
    add(/(?<![\w.])(\d+\.\d*|\.\d+)(?![\w.])/g, 'python-float', tr('js.language.prg32_numbers_are_whole_numbers', 'PRG32 numbers are whole numbers'));
    add(/\bprg32\.([A-Za-z_]\w*)/g, 'python-unknown-prg32', word => (names.functions.has(word) || names.constants.has(word))
      ? null : tr('js.language.prg32_has_no', 'prg32 has no {word}', { word }));
    if (/\bprg32\./.test(bare) && !/^import[ \t]+prg32[ \t]*$/m.test(bare)) {
      const at = bare.search(/\bprg32\./);
      problems.push(problemAt(source, at, at + 5, 'error', 'python-import-missing', tr('js.language.write_import_prg32_at_the_top_2', 'Write import prg32 at the top first')));
    }
    for (const phase of INDEX.python.lifecycle) {
      if (!new RegExp(`^def[ \\t]+${phase}[ \\t]*\\(`, 'm').test(bare)) {
        problems.push(wholeLine(source, 1, 'error', 'python-lifecycle', tr('js.language.python_define_lifecycle', 'Define the function  def {phase}() -> None:', { phase })));
      }
    }
    return sortProblems(problems.filter(problem => problem.message));
  }

  function pythonDoc(fn) {
    const kinds = { statement: tr('js.language.does_something', 'does something'), condition: tr('js.language.a_test_for_an_if', 'a test for an if'), value: tr('js.language.gives_a_whole_number', 'gives a whole number') };
    return ['```python', fn.signature, '```', fn.help, '', `prg32 module, PRG32 Python ${INDEX.python.version}: ` +
      kinds[fn.kind] + '.'].join('\n');
  }

  function pythonCompletions(source, position) {
    const before = lineText(source, position.line).slice(0, position.column - 1);
    const names = pythonNames();
    const member = before.match(/\bprg32\.([A-Za-z_]\w*)?$/);
    if (member) {
      const typed = member[1] || '';
      const items = names.py.functions.filter(fn => startsWith(fn.name, typed)).map(fn => ({
        label: fn.name, kind: 'function', detail: fn.signature, documentation: pythonDoc(fn),
        insertText: fn.params.length ? `${fn.name}(${fn.params.map((p, i) => '${' + (i + 1) + ':' + p + '}').join(', ')})`
          : `${fn.name}()`, snippet: true }));
      for (const name of names.py.constants.filter(c => startsWith(c, typed))) {
        items.push({ label: name, kind: 'constant', detail: `prg32.${name}`, insertText: name });
      }
      return result(position, typed, items);
    }
    const typed = (before.match(/[A-Za-z_]\w*$/) || [''])[0];
    const words = new Map();
    const bare = pythonBare(source);
    for (const match of bare.matchAll(/^[ \t]*def[ \t]+([A-Za-z_]\w*)/gm)) words.set(match[1], 'function');
    for (const match of bare.matchAll(/^[ \t]*([A-Za-z_]\w*)[ \t]*:[ \t]*(?:int|bool|list)/gm)) words.set(match[1], 'variable');
    const items = [...words].filter(([name]) => startsWith(name, typed) && name !== typed)
      .map(([name, kind]) => ({ label: name, kind, insertText: name }));
    for (const word of ['prg32', ...names.py.builtins, ...names.py.types, 'list[int]', 'def', 'if', 'elif', 'else',
      'for', 'in', 'range', 'return', 'global', 'pass', 'and', 'or', 'not', 'True', 'False', 'None', 'import']) {
      if (startsWith(word, typed) && word !== typed) items.push({ label: word, kind: word === 'prg32' ? 'module' : 'keyword', insertText: word });
    }
    return result(position, typed, items);
  }

  function pythonCallAt(source, position) {
    const lines = source.split('\n');
    const upto = pythonBare(lines.slice(0, position.line - 1).concat([(lines[position.line - 1] || '')
      .slice(0, position.column - 1)]).join('\n'));
    let depth = 0;
    let commas = 0;
    for (let i = upto.length - 1; i >= 0; i--) {
      const ch = upto[i];
      if (ch === ')' || ch === ']') depth += 1;
      else if ((ch === '(' || ch === '[') && depth > 0) depth -= 1;
      else if (ch === ',' && depth === 0) commas += 1;
      else if (ch === '\n' && depth === 0) return null;
      else if (ch === '(' && depth === 0) {
        const name = (upto.slice(0, i).match(/\bprg32\.([A-Za-z_]\w*)\s*$/) || [])[1];
        const fn = name && pythonNames().functions.get(name);
        return fn ? { fn, commas } : null;
      }
    }
    return null;
  }

  // --- words and contexts ---

  function lineText(source, line) {
    return (source.split('\n')[line - 1] || '').replace(/\r$/, '');
  }

  function wordAt(source, position, pattern) {
    const text = lineText(source, position.line);
    const re = pattern || /[A-Za-z_.$][\w.$]*/g;
    for (const match of text.matchAll(re)) {
      const start = match.index + 1;
      const end = start + match[0].length;
      if (position.column >= start && position.column <= end) {
        return { word: match[0], line: position.line, column: start, endColumn: end };
      }
    }
    return null;
  }

  function wordBefore(source, position, pattern) {
    const before = lineText(source, position.line).slice(0, position.column - 1);
    const match = before.match(pattern || /[A-Za-z_.$][\w.$]*$/);
    const word = match ? match[0] : '';
    return { word, line: position.line, column: position.column - word.length, endColumn: position.column };
  }

  function startsWith(label, prefix) {
    return label.toLowerCase().startsWith(prefix.toLowerCase());
  }

  function functionDoc(fn) {
    const lines = ['```c', fn.signature + ';', '```', fn.summary];
    const group = INDEX.c.groups[fn.group];
    if (group) lines.push('', `*${fn.group}:* ${group}`);
    lines.push('', `Portable PRG32 ABI ${INDEX.abi.major}.${INDEX.abi.minor} · feature: ${fn.feature}`);
    return lines.join('\n');
  }

  function snippet(fn) {
    if (!fn.params.length) return `${fn.name}()`;
    return `${fn.name}(${fn.params.map((p, i) => '${' + (i + 1) + ':' + p.name + '}').join(', ')})`;
  }

  // --- completion ---

  function completions(language, source, position) {
    if (language === 'python') return pythonCompletions(source, position);
    return language === 'asm' ? asmCompletions(source, position) : cCompletions(source, position);
  }

  function cCompletions(source, position) {
    const before = lineText(source, position.line).slice(0, position.column - 1);
    const include = before.match(/^\s*#\s*include\s*([<"])([\w.]*)$/);
    if (include) {
      const close = include[1] === '<' ? '>' : '"';
      return result(position, include[2], INDEX.c.headers.filter(h => startsWith(h, include[2])).map(h => ({
        label: h, kind: 'file', detail: 'header', insertText: h + close,
        documentation: h === 'prg32_assets.h' ? tr('js.language.your_project_art_as_c', 'your project\'s sprites, backgrounds and sounds as C')
          : h.startsWith('prg32') ? tr('js.language.prg32_sdk_header', 'PRG32 SDK header') : tr('js.language.freestanding_c_header', 'freestanding C header') })));
    }
    const hash = before.match(/^\s*#\s*(\w*)$/);
    if (hash) {
      return result(position, hash[1], INDEX.c.preprocessor.filter(word => startsWith(word, hash[1])).map(word => ({
        label: word, kind: 'keyword', detail: 'preprocessor', insertText: word })));
    }
    const typed = wordBefore(source, position, /[A-Za-z_]\w*$/).word;
    if (!typed) return result(position, '', []);
    const items = [];
    for (const fn of INDEX.c.functions) {
      if (startsWith(fn.name, typed)) {
        items.push({ label: fn.name, kind: 'function', detail: fn.signature, documentation: functionDoc(fn),
          insertText: snippet(fn), snippet: true });
      }
    }
    for (const constant of INDEX.c.constants) {
      if (startsWith(constant.name, typed)) {
        items.push({ label: constant.name, kind: 'constant', detail: `#define ${constant.name} ${constant.value}`,
          documentation: constant.doc, insertText: constant.name });
      }
    }
    for (const type of INDEX.c.types) {
      if (startsWith(type.name, typed)) {
        items.push({ label: type.name, kind: 'struct', detail: tr('js.language.prg32_type', 'PRG32 type'), documentation: '', insertText: type.name });
      }
    }
    return result(position, typed, items);
  }

  function asmCompletions(source, position) {
    const line = lineText(source, position.line);
    const before = line.slice(0, position.column - 1);
    if (/^\s*#\s*\w*$/.test(before)) {
      const typed = before.match(/(\w*)$/)[1];
      return result(position, typed, INDEX.asm.preprocessor.filter(word => startsWith(word, typed)).map(word => ({
        label: word, kind: 'keyword', detail: 'preprocessor', insertText: word })));
    }
    const code = before.replace(/^\s*(?:(?:[A-Za-z_.$][\w.$]*|\d+)\s*:\s*)*/, '');
    const head = code.match(/^(\.?[A-Za-z_][\w.]*|\.)?$/);
    if (head) {
      const typed = head[1] || '';
      const items = [];
      for (const directive of INDEX.asm.directives) {
        if (startsWith(directive.name, typed)) {
          items.push({ label: directive.name, kind: 'keyword', detail: directive.syntax, documentation: directive.help,
            insertText: directive.name });
        }
      }
      if (!typed.startsWith('.')) {
        for (const instruction of INDEX.asm.instructions) {
          if (startsWith(instruction.name, typed)) {
            items.push({ label: instruction.name, kind: 'operator', detail: instruction.syntax,
              documentation: `${instruction.help} (${instruction.extension})`, insertText: instruction.name });
          }
        }
      }
      return result(position, typed, items);
    }
    const mnemonic = code.match(/^(\.?[A-Za-z_][\w.]*)\s+/)[1].toLowerCase();
    const typed = (before.match(/[A-Za-z_.$][\w.$]*$/) || [''])[0];
    if (mnemonic === '.section') {
      return result(position, typed, INDEX.asm.sections.filter(s => startsWith(s, typed)).map(s => ({
        label: s, kind: 'module', detail: 'section', insertText: s })));
    }
    const symbols = asmSymbols(withoutStrings(withoutComments(source).text === null
      ? { text: '', origin: [] } : withoutComments(source)));
    const items = [];
    if (['call', 'tail', 'la', 'lla', 'jal', 'j'].includes(mnemonic)) {
      for (const fn of INDEX.c.functions) {
        if (startsWith(fn.name, typed)) {
          items.push({ label: fn.name, kind: 'function', detail: fn.signature, documentation: asmCallDoc(fn),
            insertText: fn.name });
        }
      }
    }
    for (const label of symbols.labels.keys()) {
      if (startsWith(label, typed) && !/^\d+$/.test(label)) {
        items.push({ label, kind: 'reference', detail: tr('js.language.label_in_this_file', 'label in this file'), insertText: label });
      }
    }
    if (!['call', 'tail', 'j'].includes(mnemonic)) {
      for (const reg of INDEX.asm.registers) {
        for (const name of [reg.abi, reg.name]) {
          if (startsWith(name, typed)) {
            items.push({ label: name, kind: 'variable', detail: `${reg.name} / ${reg.abi}`,
              documentation: registerDoc(reg), insertText: name });
          }
        }
      }
    }
    return result(position, typed, items);
  }

  function result(position, typed, items) {
    return { range: { line: position.line, column: position.column - typed.length, endColumn: position.column },
      items };
  }

  function registerDoc(reg) {
    const saved = reg.saved_by === 'callee' ? tr('js.language.kept_across_calls_save_it_before', 'kept across calls (save it before you change it)')
      : reg.saved_by === 'caller' ? tr('js.language.may_change_in_any_call', 'may change in any call') : 'special';
    return `**${reg.abi}** (${reg.name}): ${reg.role}. ${saved}.`;
  }

  function asmCallDoc(fn) {
    const args = fn.params.map((p, i) => `a${i} = ${p.name} (${p.type})`).join(', ');
    const lines = ['```c', fn.signature + ';', '```', fn.summary, ''];
    lines.push(args ? tr('js.language.asm_call_before', 'Before `call {name}`: {args}.', { name: fn.name, args }) : tr('js.language.asm_call_no_args', 'No arguments: just `call {name}`.', { name: fn.name }));
    if (fn.returns !== 'void') lines.push(tr('js.language.asm_call_result', 'The result ({type}) is in a0 afterwards.', { type: fn.returns }));
    lines.push('', INDEX.asm.calling_convention);
    return lines.join('\n');
  }

  // --- hover ---

  function hover(language, source, position) {
    if (language === 'python') {
      const word = wordAt(source, position, /\bprg32\.[A-Za-z_]\w*/g);
      if (!word) return null;
      const name = word.word.slice(6);
      const names = pythonNames();
      if (names.functions.has(name)) return { range: word, contents: pythonDoc(names.functions.get(name)) };
      if (names.constants.has(name)) return { range: word, contents: '```python\nprg32.' + name + '\n```\nA prg32 constant.' };
      return null;
    }
    if (language === 'asm') {
      const word = wordAt(source, position, /[A-Za-z_.$][\w.$]*/g);
      if (!word) return null;
      const lower = word.word.toLowerCase();
      const t = idx();
      let text = null;
      if (t.directives.has(lower)) {
        const d = t.directives.get(lower);
        text = '```\n' + d.syntax + '\n```\n' + d.help;
      } else if (t.instructions.has(lower) && isMnemonic(source, word)) {
        const i = t.instructions.get(lower);
        text = '```\n' + i.syntax + '\n```\n' + `${i.help} (${i.extension})`;
      } else if (t.registers.has(lower)) {
        text = registerDoc(t.registers.get(lower));
      } else if (t.functions.has(word.word)) {
        text = asmCallDoc(t.functions.get(word.word));
      } else if (t.resident.has(word.word)) {
        text = residentDoc(t.resident.get(word.word));
      } else if (t.obsolete.has(word.word)) {
        text = obsoleteDoc(t.obsolete.get(word.word));
      }
      return text ? { range: word, contents: text } : null;
    }
    const word = wordAt(source, position, /[A-Za-z_]\w*/g);
    if (!word) return null;
    const t = idx();
    let text = null;
    if (t.functions.has(word.word)) text = functionDoc(t.functions.get(word.word));
    else if (t.resident.has(word.word)) text = residentDoc(t.resident.get(word.word));
    else if (t.obsolete.has(word.word)) text = obsoleteDoc(t.obsolete.get(word.word));
    else if (t.constants.has(word.word)) {
      const k = t.constants.get(word.word);
      text = '```c\n#define ' + k.name + ' ' + k.value + '\n```\n' + (k.doc || '');
    } else if (t.types.has(word.word)) text = '```c\n' + word.word + '\n```\nA PRG32 SDK type.';
    return text ? { range: word, contents: text } : null;
  }

  function isMnemonic(source, word) {
    const before = lineText(source, word.line).slice(0, word.column - 1);
    return /^\s*(?:(?:[A-Za-z_.$][\w.$]*|\d+)\s*:\s*)*$/.test(before) || /;\s*$/.test(before);
  }

  function obsoleteDoc(entry) {
    return tr('js.language.obsolete_the_old_buzzer_use', '**Obsolete: the old buzzer.** Use {instead}.', { instead: entry.instead }) + '\n\n' + EXPLAIN['obsolete-buzzer'];
  }

  function residentDoc(fn) {
    return '```c\n' + fn.signature + ';\n```\n' + tr('js.language.resident_firmware_only', 'Resident firmware only: {only}', { only: EXPLAIN['c-resident-only'] });
  }

  // --- signature help (C) ---

  function signatureHelp(language, source, position) {
    if (language === 'asm') return null;
    if (language === 'python') {
      const call = pythonCallAt(source, position);
      if (!call) return null;
      return { label: call.fn.signature, documentation: call.fn.help, parameters: call.fn.params,
        activeParameter: Math.min(call.commas, Math.max(0, call.fn.params.length - 1)) };
    }
    const lines = source.split('\n');
    const upto = lines.slice(0, position.line - 1).concat([(lines[position.line - 1] || '')
      .slice(0, position.column - 1)]).join('\n');
    let depth = 0;
    let commas = 0;
    for (let i = upto.length - 1; i >= 0; i--) {
      const ch = upto[i];
      if (ch === ')') depth += 1;
      else if (ch === '(' && depth > 0) depth -= 1;
      else if (ch === ',' && depth === 0) commas += 1;
      else if (ch === ';' || ch === '{' || ch === '}') return null;
      else if (ch === '(' && depth === 0) {
        const name = (upto.slice(0, i).match(/([A-Za-z_]\w*)\s*$/) || [])[1];
        const fn = name && idx().functions.get(name);
        if (!fn) return null;
        return { label: fn.signature, documentation: fn.summary,
          parameters: fn.params.map(p => `${p.type} ${p.name}`.replace('* ', '*')),
          activeParameter: Math.min(commas, Math.max(0, fn.params.length - 1)) };
      }
    }
    return null;
  }

  // --- go to declaration ---

  function definition(language, source, position) {
    if (language === 'python') {
      const word = wordAt(source, position, /[A-Za-z_]\w*/g);
      if (!word) return null;
      const found = new RegExp(`^([ \\t]*def[ \\t]+)${word.word}[ \\t]*\\(`, 'm').exec(pythonBare(source));
      if (!found) return null;
      const at = positionAt(source, found.index + found[1].length);
      return { target: 'self', line: at.line, column: at.column };
    }
    const word = wordAt(source, position, language === 'asm' ? /[A-Za-z_.$][\w.$]*/g : /[A-Za-z_]\w*/g);
    if (!word) return null;
    const t = idx();
    const sdk = t.functions.get(word.word) || t.constants.get(word.word) || t.types.get(word.word);
    if (sdk) return { target: 'sdk', line: sdk.line, column: 1 };
    if (language === 'asm') {
      const noComments = withoutComments(source);
      if (noComments.text === null) return null;
      const symbols = asmSymbols(withoutStrings(noComments));
      if (symbols.labels.has(word.word)) {
        const at = positionAt(source, symbols.labels.get(word.word));
        return { target: 'self', line: at.line, column: at.column };
      }
      return null;
    }
    const noComments = withoutComments(source);
    if (noComments.text === null) return null;
    const bare = withoutStrings(noComments);
    const escaped = word.word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const found = new RegExp(`\\b${escaped}\\s*\\([^;{}]*\\)\\s*\\{`).exec(bare.text);
    if (!found) return null;
    const at = positionAt(source, bare.origin[found.index]);
    return { target: 'self', line: at.line, column: at.column };
  }

  // --- compiler and server messages -> problems, without server paths ---

  // An absolute path (Unix or Windows) becomes its last part: /srv/kit/builds/7/tmp/game.c -> game.c
  function withoutPaths(text) {
    // Build logs already show the build folder as "<build>/" (packager.redact_build_path).
    return text.replace(/<build>[\\/]/g, '')
      .replace(/(?:[A-Za-z]:)?(?:[\\/][^\s\\/:'"`()]+)+[\\/]([^\s\\/:'"`()]+)/g, '$1');
  }

  function normalizeCompilerOutput(output, options) {
    const opts = options || {};
    const source = opts.source || '';
    const ownFile = opts.language === 'asm' ? /^game\.[sS]$/ : /^game\.c$/;
    const problems = [];
    const seen = new Set();
    const add = item => {
      const key = [item.line, item.column, item.severity, item.message].join('|');
      if (!seen.has(key)) { seen.add(key); problems.push(item); }
    };
    for (const raw of String(output || '').split(/\r?\n/)) {
      const line = withoutPaths(raw).trim();
      if (!line) continue;
      // gcc: "game.c:12:5: error: ..."; GNU as: "game.S:12: Error: ..." (no column, capital E)
      const compiler = line.match(/^([\w.\-]+):(\d+):(?:(\d+):)?\s*(?:fatal )?(error|warning|note):\s*(.*)$/i);
      if (compiler) {
        const message = compiler[5];
        compiler[4] = compiler[4].toLowerCase();
        if (compiler[4] === 'note') continue;
        const hint = COMPILER_HINTS.find(([re]) => re.test(message));
        const explanation = hint ? hint[1]((message.match(hint[0]) || [])[1]) : EXPLAIN.compiler;
        if (ownFile.test(compiler[1])) {
          const lineNo = Number(compiler[2]);
          const text = lineText(source, lineNo);
          if (!compiler[3]) {  // no column: the whole line
            const indent = text.length - text.trimStart().length;
            add({ severity: compiler[4], code: 'compiler', message, explanation, line: lineNo, column: indent + 1,
              endLine: lineNo, endColumn: Math.max(indent + 2, text.trimEnd().length + 1) });
            continue;
          }
          const column = Number(compiler[3]);
          const word = wordAt(source, { line: lineNo, column }, /[A-Za-z_.$][\w.$]*/g);
          add({ severity: compiler[4], code: 'compiler', message, explanation, line: lineNo, column,
            endLine: lineNo, endColumn: word && word.column === column ? word.endColumn : column + 1 });
        } else {
          add({ severity: compiler[4], code: 'compiler', message: `${compiler[1]}: ${message}`, explanation,
            line: 0, column: 0, endLine: 0, endColumn: 0 });
        }
        continue;
      }
      const undefinedRef = line.match(/undefined reference to [`'"]?([A-Za-z_]\w*)/);
      if (undefinedRef) {
        const name = undefinedRef[1];
        const resident = idx().resident.has(name);
        const at = new RegExp(`\\b${name}\\b`).exec(source);
        const pos = at ? positionAt(source, at.index) : { line: 0, column: 0 };
        add({ severity: 'error', code: resident ? 'c-resident-only' : 'compiler',
          message: resident ? tr('js.language.resident_cannot_call', '{name} belongs to the resident PRG32 firmware: a portable cartridge cannot call it', { name })
            : tr('js.language.undefined_reference', 'undefined reference to {name}', { name }),
          explanation: resident ? EXPLAIN['c-resident-only'] : COMPILER_HINTS[4][1](),
          line: pos.line, column: pos.column, endLine: pos.line, endColumn: at ? pos.column + name.length : 0 });
        continue;
      }
      const server = line.match(/^Line (\d+): (.*)$/);
      if (server) {
        const lineNo = Number(server[1]);
        add({ severity: 'error', code: 'server', message: server[2], explanation: '', line: lineNo, column: 1,
          endLine: lineNo, endColumn: lineEnd(source, lineNo) });
      }
    }
    return problems;
  }

  return { useIndex, entryPrefix, diagnostics, completions, hover, signatureHelp, definition,
    normalizeCompilerOutput, withoutPaths, EXPLAIN };
});
