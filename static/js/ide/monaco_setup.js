// Loads the Monaco code editor for the IDE (ADR-0013) and teaches it PRG32 RISC-V assembly.
//
// - Monaco comes from static/vendor (no CDN); its web worker is a same-origin file, because the
//   Content Security Policy does not allow blob: workers.
// - "prg32-asm" is a small Monarch grammar for the RV32IMC assembly the kit accepts: the
//   instructions and pseudo-instructions, x0-x31 and their ABI names, the directives that
//   source_project.validate_asm_source allows (all from the language index), /* */ and #
//   comments, labels, numbers, strings.
//   Directives outside the allow-list are shown as errors (the server refuses them anyway).
window.PRG32Monaco = (function () {
  'use strict';
  const BASE = '/static/vendor/monaco-editor/0.52.2/min/vs';
  let ready = null;

  // The word lists come from the PRG32 language index (prg32_language_index.js, made by
  // tools/build_language_index.py): the directives are exactly the ones
  // source_project.validate_asm_source allows; the instructions are RV32IMC + Zicsr + pseudo.
  const ASM = window.PRG32LanguageIndex.asm;
  const DIRECTIVES = ASM.directives.map(directive => directive.name);
  const INSTRUCTIONS = ASM.instructions.map(instruction => instruction.name);
  const REGISTERS = ASM.registers.map(register => register.abi)
    .concat(Object.keys(ASM.register_aliases), ASM.registers.map(register => register.name));

  function registerAssembly(monaco) {
    monaco.languages.register({ id: 'prg32-asm', extensions: ['.S', '.s'], aliases: ['PRG32 RISC-V assembly'] });
    monaco.languages.setMonarchTokensProvider('prg32-asm', {
      ignoreCase: true,
      directives: DIRECTIVES,
      instructions: INSTRUCTIONS,
      registers: REGISTERS,
      tokenizer: {
        root: [
          [/\/\*/, 'comment', '@comment'],
          [/#\s*(?:define|undef|if|ifdef|ifndef|elif|else|endif)\b/, 'keyword.directive'],
          [/#.*$/, 'comment'],
          [/^\s*[A-Za-z_.$][\w.$]*:/, 'type.identifier'],     // a label
          [/^\s*\d+:/, 'type.identifier'],                   // a numeric local label
          [/\.[A-Za-z0-9_]+/, { cases: { '@directives': 'keyword', '@default': 'invalid' } }],
          [/[A-Za-z_][\w.]*/, { cases: { '@instructions': 'keyword.instruction', '@registers': 'variable.predefined',
            '@default': 'identifier' } }],
          [/0[xX][0-9a-fA-F]+|0[bB][01]+|-?\d+/, 'number'],
          [/"([^"\\]|\\.)*"/, 'string'],
          [/'([^'\\]|\\.)'/, 'string'],
          [/[(),:+\-*/%<>&|^~]/, 'delimiter'],
        ],
        comment: [[/\*\//, 'comment', '@pop'], [/./, 'comment']],
      },
    });
    monaco.languages.setLanguageConfiguration('prg32-asm', {
      comments: { blockComment: ['/*', '*/'], lineComment: '#' },
      brackets: [['(', ')']],
      autoClosingPairs: [{ open: '(', close: ')' }, { open: '"', close: '"' }, { open: '/*', close: ' */' }],
    });
  }

  function load() {
    if (ready) return ready;
    window.MonacoEnvironment = {
      // The worker file is in static/vendor; it finds the rest of Monaco next to itself.
      getWorkerUrl: () => BASE + '/base/worker/workerMain.js',
    };
    ready = new Promise((resolve, reject) => {
      window.require.config({ paths: { vs: BASE } });
      window.require(['vs/editor/editor.main'], () => {
        registerAssembly(window.monaco);
        resolve(window.monaco);
      }, reject);
    });
    return ready;
  }

  return { load, DIRECTIVES, INSTRUCTIONS, REGISTERS };
})();
