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
  const STRING = /"(?:\\.|[^"\\\n])*"|'(?:\\.|[^'\\\n])*'/g;

  // Student-readable explanations for every problem code. They never contain server details.
  const EXPLAIN = {
    'empty': 'Write the game before checking it.',
    'too-big': 'A cartridge source can be at most 256 KiB, without NUL bytes.',
    'trigraph': 'Trigraphs (??= and ??/) are an old C feature the kit does not accept.',
    'comment': 'A /* comment needs a matching */ to end it.',
    'c-include': 'A PRG32 cartridge can include only prg32.h, prg32_audio.h, stdint.h, stddef.h and stdbool.h. ' +
      'Other headers would need a C library or files on the server.',
    'c-directive': 'Allowed preprocessor lines: #include (approved headers), #define, #undef, #if, #ifdef, ' +
      '#ifndef, #elif, #else and #endif.',
    'c-token-paste': 'The ## operator can build hidden words, so the kit does not accept it.',
    'c-forbidden': 'Inline assembly and _Pragma could read files on the server while compiling. ' +
      'Write assembly in an Assembly project instead.',
    'c-entry': 'The console calls three functions named after your project title: init once, then update ' +
      'and draw for every frame. Each must be written exactly as  void NAME(void) { ... }.',
    'c-resident-only': 'This function exists only inside the PRG32 firmware. A portable cartridge can call ' +
      'only the functions in the PRG32 ABI, so the build would stop with "undefined reference".',
    'c-unknown-api': 'This name starts with prg32_ but is not part of the PRG32 API. Check the spelling.',
    'obsolete-buzzer': 'The buzzer is obsolete: PRG32 games use the eight-voice audio engine (instruments with ' +
      'ADSR envelopes, stereo pan, sound effects and soundtracks made in AudioStudio). The server refuses this name.',
    'asm-file-access': 'include, incbin and _Pragma could read files on the server, so they are not allowed.',
    'asm-preprocessor': 'In assembly only  #define NAME value  and #if / #ifdef / #ifndef / #elif / #else / ' +
      '#endif / #undef are allowed as preprocessor lines.',
    'asm-directive': 'Only the directives the kit lists are allowed; others could read files or change how ' +
      'the cartridge is built.',
    'asm-section': 'Put code in .text and data in .rodata, .data or .bss (or sub-sections such as .text.game).',
    'asm-entry': 'The console calls three labels named after your project title: init, update and draw. ' +
      'Each needs a label (NAME:) and .globl NAME so the console can find it.',
    'asm-instruction': 'This is not an RV32IMC instruction or pseudo-instruction the assembler knows.',
    'asm-register': 'RISC-V has 32 registers: x0-x31, or by their ABI names zero, ra, sp, gp, tp, t0-t6, ' +
      's0-s11 (fp = s0) and a0-a7.',
    'compiler': 'The compiler found this problem.',
  };
  // Common compiler messages, said in simpler words.
  const COMPILER_HINTS = [
    [/implicit declaration of function '?(prg32_\w+)'?/, name => `${name} is not declared: check the spelling. ` +
      'Only the functions in prg32.h (portable API) can be used.'],
    [/implicit declaration of function/, () => 'This function is used before it is declared. Declare or define it above, or check the spelling.'],
    [/expected ';'/, () => 'A statement must end with ; (look at the end of the line before, too).'],
    [/undeclared/, () => 'This name is not declared: check the spelling, or declare the variable first.'],
    [/undefined reference to/, () => 'The program calls something that does not exist in a PRG32 cartridge.'],
    [/conflicting types/, () => 'This name is declared twice with different types.'],
    [/expected '\}'|expected declaration or statement at end of input/, () => 'A { has no matching }.'],
    [/unrecognized opcode|unknown opcode|illegal operands/, () => 'The assembler does not understand this instruction or its operands.'],
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
      return [{ severity: 'error', code: 'empty', message: `${kind} source is empty`, explanation: EXPLAIN.empty,
        line: 1, column: 1, endLine: 1, endColumn: 2 }];
    }
    const problems = [];
    if (new TextEncoder().encode(source).length > MAX_BYTES || source.includes('\0')) {
      problems.push(wholeLine(source, 1, 'error', 'too-big', `${kind} source exceeds 256 KiB or contains NUL bytes`));
    }
    for (const match of source.matchAll(/\?\?[=/]/g)) {
      problems.push(problemAt(source, match.index, match.index + 3, 'error', 'trigraph',
        'Trigraphs (??= and ??/) are not supported'));
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
        'C source has a comment that never ends'));
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
          `The header ${include[1]} is not available in a PRG32 cartridge`));
      } else {
        const lead = line.text.length - line.text.trimStart().length;
        problems.push(problem(source, code, line.start + lead, line.start + line.text.trimEnd().length, 'error',
          'c-directive', 'Only approved PRG32/standard headers and basic conditional or define directives are supported'));
      }
    }
    const bare = withoutStrings(code);
    for (const match of bare.text.matchAll(/##|%:%:/g)) {
      problems.push(problem(source, bare, match.index, match.index + match[0].length, 'error', 'c-token-paste',
        'The ## token-pasting operator is not supported'));
    }
    for (const match of bare.text.matchAll(C_FORBIDDEN_WORDS)) {
      problems.push(problem(source, bare, match.index, match.index + match[0].length, 'error', 'c-forbidden',
        `'${match[0]}' is not supported in PRG32 cartridge C`));
    }
    const prefix = entryPrefix(title);
    const escaped = prefix.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const lifecycle = new RegExp(`\\bvoid\\s+(${escaped}_(?:init|update|draw))\\s*\\(\\s*void\\s*\\)\\s*\\{`, 'g');
    const found = new Set([...bare.text.matchAll(lifecycle)].map(match => match[1]));
    for (const phase of ['init', 'update', 'draw']) {
      const name = `${prefix}_${phase}`;
      if (found.has(name)) continue;
      const near = new RegExp(`\\b${name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`).exec(bare.text);
      const message = `C source must define void ${prefix}_init/update/draw(void): ` +
        (near ? `write ${name} as  void ${name}(void) { ... }` : `void ${name}(void) is missing`);
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
          `${name} belongs to the resident PRG32 firmware, not to the portable cartridge ABI ` +
          `${INDEX.abi.major}.${INDEX.abi.minor}: the cartridge would not link`));
      } else if (!idx().functions.has(name) && !idx().types.has(name) && !defined.has(name)
                 && /^\s*\(/.test(bare.text.slice(match.index + name.length))) {
        problems.push(problem(source, bare, match.index, match.index + name.length, 'warning', 'c-unknown-api',
          `${name} is not a PRG32 function`));
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
    const problems = basicChecks(source, 'Assembly');
    if (problems.some(p => p.code === 'empty')) return problems;
    const noComments = withoutComments(source);
    if (noComments.text === null) {
      problems.push(problemAt(source, noComments.unterminated, noComments.unterminated + 2, 'error', 'comment',
        'C source has a comment that never ends'));
      return problems;
    }
    const bare = withoutStrings(noComments);
    const lines = splitLines(bare.text);
    // Words that read files: in preprocessor lines anywhere, elsewhere before a '#' comment.
    for (const line of lines) {
      const code = DIRECTIVE_START.test(line.text) ? line.text : line.text.split('#', 1)[0];
      const found = ASM_FILE_WORDS.exec(code);
      if (found) {
        problems.push(problem(source, bare, line.start + found.index, line.start + found.index + found[0].length,
          'error', 'asm-file-access',
          `'${found[0]}' is not allowed in PRG32 cartridge assembly: it could read files on the server`));
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
          'asm-preprocessor', `Line ${number}: only '#define NAME value' and #if/#ifdef/#else/#endif are allowed ` +
          'as preprocessor lines'));
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
              `Line ${number}: the directive ${name} is not allowed. Allowed: ` +
              [...idx().directives.keys()].sort().join(', ')));
          } else if (name === '.section') {
            const rest = text.slice(text.indexOf(' ') + 1);
            const section = text.indexOf(' ') < 0 ? '' : rest.split(',')[0].trim();
            if (!ASM_SECTION.test(section)) {
              const offset = section ? text.indexOf(section, name.length) : 0;
              const length = section ? section.length : name.length;
              problems.push(problem(source, bare, start + offset, start + offset + length, 'error', 'asm-section',
                `Line ${number}: use .text, .rodata, .data or .bss sections, not '${section}'`));
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
        problems.push(wholeLine(source, 1, 'error', 'asm-entry', `Assembly source must define the label ${name}:`));
        continue;
      }
      if (!new RegExp(`^\\s*\\.glob(?:a)?l\\s+${escaped}\\s*(?:[#;]|$)`, 'mi').test(bare.text)) {
        const offset = labelAt.index + labelAt[0].indexOf(name);
        problems.push(problem(source, bare, offset, offset + name.length, 'error', 'asm-entry',
          `Assembly source must make ${name} visible with .globl ${name}`));
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
        `${match[0]} belongs to the old PRG32 buzzer, which is no longer supported. Use ` +
        `${entry ? entry.instead : 'the PRG32 audio engine (prg32_audio_*)'}.`));
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
        `${name} is not an RV32IMC instruction`));
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
    return language === 'asm' ? asmDiagnostics(source, title) : cDiagnostics(source, title);
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
    return language === 'asm' ? asmCompletions(source, position) : cCompletions(source, position);
  }

  function cCompletions(source, position) {
    const before = lineText(source, position.line).slice(0, position.column - 1);
    const include = before.match(/^\s*#\s*include\s*([<"])([\w.]*)$/);
    if (include) {
      const close = include[1] === '<' ? '>' : '"';
      return result(position, include[2], INDEX.c.headers.filter(h => startsWith(h, include[2])).map(h => ({
        label: h, kind: 'file', detail: 'header', insertText: h + close,
        documentation: h.startsWith('prg32') ? 'PRG32 SDK header' : 'freestanding C header' })));
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
        items.push({ label: type.name, kind: 'struct', detail: 'PRG32 type', documentation: '', insertText: type.name });
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
        items.push({ label, kind: 'reference', detail: 'label in this file', insertText: label });
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
    const saved = reg.saved_by === 'callee' ? 'kept across calls (save it before you change it)'
      : reg.saved_by === 'caller' ? 'may change in any call' : 'special';
    return `**${reg.abi}** (${reg.name}): ${reg.role}. ${saved}.`;
  }

  function asmCallDoc(fn) {
    const args = fn.params.map((p, i) => `a${i} = ${p.name} (${p.type})`).join(', ');
    const lines = ['```c', fn.signature + ';', '```', fn.summary, ''];
    lines.push(args ? `Before \`call ${fn.name}\`: ${args}.` : `No arguments: just \`call ${fn.name}\`.`);
    if (fn.returns !== 'void') lines.push(`The result (${fn.returns}) is in a0 afterwards.`);
    lines.push('', INDEX.asm.calling_convention);
    return lines.join('\n');
  }

  // --- hover ---

  function hover(language, source, position) {
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
    return '**Obsolete: the old buzzer.** Use ' + entry.instead + '.\n\n' + EXPLAIN['obsolete-buzzer'];
  }

  function residentDoc(fn) {
    return '```c\n' + fn.signature + ';\n```\n' + 'Resident firmware only: ' + EXPLAIN['c-resident-only'];
  }

  // --- signature help (C) ---

  function signatureHelp(language, source, position) {
    if (language === 'asm') return null;
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
          message: resident ? `${name} belongs to the resident PRG32 firmware: a portable cartridge cannot call it`
            : `undefined reference to ${name}`,
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
