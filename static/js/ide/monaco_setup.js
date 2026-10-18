// Loads the Monaco code editor for the IDE (ADR-0013) and teaches it PRG32 RISC-V assembly.
//
// - Monaco comes from static/vendor (no CDN); its web worker is a same-origin file, because the
//   Content Security Policy does not allow blob: workers.
// - "prg32-asm" is a small Monarch grammar for the RV32IMC assembly the kit accepts: the
//   instructions and pseudo-instructions, x0-x31 and their ABI names, the directives that
//   source_project.validate_asm_source allows, /* */ and # comments, labels, numbers, strings.
//   Directives outside the allow-list are shown as errors (the server refuses them anyway).
window.PRG32Monaco = (function () {
  'use strict';
  const BASE = '/static/vendor/monaco-editor/0.52.2/min/vs';
  let ready = null;

  // The kit's allowed directives (prg32_construction_kit/source_project.py, ALLOWED_ASM_DIRECTIVES).
  const DIRECTIVES = ['.2byte', '.4byte', '.align', '.ascii', '.asciz', '.balign', '.bss', '.byte', '.data', '.equ',
    '.equiv', '.global', '.globl', '.half', '.local', '.option', '.p2align', '.rodata', '.section', '.set', '.short',
    '.size', '.skip', '.space', '.string', '.text', '.type', '.word', '.zero'];
  // RV32I + M + C (compressed) instructions and the common pseudo-instructions.
  const INSTRUCTIONS = ('lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu sb sh sw addi slti sltiu xori ori '
    + 'andi slli srli srai add sub sll slt sltu xor srl sra or and fence ecall ebreak csrrw csrrs csrrc csrrwi csrrsi '
    + 'csrrci mul mulh mulhsu mulhu div divu rem remu c.addi4spn c.lw c.sw c.nop c.addi c.jal c.li c.addi16sp c.lui '
    + 'c.srli c.srai c.andi c.sub c.xor c.or c.and c.j c.beqz c.bnez c.slli c.lwsp c.jr c.mv c.ebreak c.jalr c.add '
    + 'c.swsp nop li la mv not neg seqz snez sltz sgtz beqz bnez blez bgez bltz bgtz bgt ble bgtu bleu j jr ret call '
    + 'tail csrr csrw csrs csrc').split(' ');
  const REGISTERS = ['zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 'fp', 's1', 'a0', 'a1', 'a2', 'a3', 'a4',
    'a5', 'a6', 'a7', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4', 't5', 't6']
    .concat(Array.from({ length: 32 }, (_, index) => 'x' + index));

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
