// Connects the PRG32 language services (language.js) to Monaco (ADR-0014).
//
// - Completion, hover, signature help and "go to declaration" (F12) for Advanced C ('c')
//   and RISC-V assembly ('prg32-asm'), from the committed language index only.
// - "Go to declaration" on a PRG32 function opens "prg32.h (portable API)": a read-only,
//   generated list of what a cartridge can call (the real SDK headers stay on the server).
// - attach(model, ...) checks a student's source while they type and shows the problems as
//   markers (owner 'prg32-live'); the server still checks every build.
window.PRG32MonacoLanguage = (function () {
  'use strict';
  const SDK_URI = 'prg32-sdk:/prg32.h';
  let sdkModel = null;

  function kind(monaco, name) {
    const kinds = monaco.languages.CompletionItemKind;
    return { function: kinds.Function, constant: kinds.Constant, struct: kinds.Struct, file: kinds.File,
      keyword: kinds.Keyword, operator: kinds.Operator, variable: kinds.Variable, reference: kinds.Reference,
      module: kinds.Module }[name] || kinds.Text;
  }

  function markdown(text) {
    return text ? { value: text, isTrusted: false, supportHtml: false } : undefined;
  }

  function position(pos) { return { line: pos.lineNumber, column: pos.column }; }

  function register(monaco, options) {
    PRG32Language.useIndex(window.PRG32LanguageIndex);
    sdkModel = monaco.editor.createModel(window.PRG32LanguageIndex.header.text, 'c', monaco.Uri.parse(SDK_URI));
    for (const [id, language, triggers] of [['c', 'c', ['"', '<', '#', '_']], ['prg32-asm', 'asm', ['.', '#', '_']]]) {
      monaco.languages.registerCompletionItemProvider(id, {
        triggerCharacters: triggers,
        provideCompletionItems(model, pos) {
          if (model.uri.toString() === SDK_URI) return { suggestions: [] };
          const found = PRG32Language.completions(language, model.getValue(), position(pos));
          const range = new monaco.Range(pos.lineNumber, found.range.column, pos.lineNumber, found.range.endColumn);
          return { suggestions: found.items.map((item, order) => ({
            label: item.label, kind: kind(monaco, item.kind), detail: item.detail,
            documentation: markdown(item.documentation), insertText: item.insertText, range,
            sortText: String(order).padStart(4, '0'),
            insertTextRules: item.snippet ? monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet : undefined,
          })) };
        },
      });
      monaco.languages.registerHoverProvider(id, {
        provideHover(model, pos) {
          const found = PRG32Language.hover(language, model.getValue(), position(pos));
          if (!found) return null;
          return { range: new monaco.Range(found.range.line, found.range.column, found.range.line, found.range.endColumn),
            contents: [markdown(found.contents)] };
        },
      });
      monaco.languages.registerDefinitionProvider(id, {
        provideDefinition(model, pos) {
          const found = PRG32Language.definition(language, model.getValue(), position(pos));
          if (!found) return null;
          const uri = found.target === 'sdk' ? sdkModel.uri : model.uri;
          return { uri, range: new monaco.Range(found.line, found.column, found.line, found.column) };
        },
      });
    }
    monaco.languages.registerSignatureHelpProvider('c', {
      signatureHelpTriggerCharacters: ['(', ','],
      signatureHelpRetriggerCharacters: [','],
      provideSignatureHelp(model, pos) {
        const found = PRG32Language.signatureHelp('c', model.getValue(), position(pos));
        if (!found) return null;
        return { value: { signatures: [{ label: found.label, documentation: markdown(found.documentation),
          parameters: found.parameters.map(label => ({ label })) }], activeSignature: 0,
          activeParameter: found.activeParameter }, dispose() {} };
      },
    });
    // "Go to declaration" into prg32.h: the IDE opens it as a read-only tab.
    monaco.editor.registerEditorOpener({
      openCodeEditor(source, resource, selectionOrPosition) {
        if (resource.toString() !== SDK_URI) return false;
        const line = selectionOrPosition ? (selectionOrPosition.startLineNumber || selectionOrPosition.lineNumber) : 1;
        options.openSdk(line);
        return true;
      },
    });
  }

  // Live checks for one editable model. onProblems receives the problems after every check.
  function attach(monaco, model, language, getTitle, onProblems) {
    let timer = null;
    const check = () => {
      const problems = PRG32Language.diagnostics(language, model.getValue(), { title: getTitle() });
      monaco.editor.setModelMarkers(model, 'prg32-live', problems.map(problem => ({
        startLineNumber: problem.line, startColumn: problem.column, endLineNumber: problem.endLine,
        endColumn: problem.endColumn, code: problem.code,
        message: problem.explanation ? `${problem.message}\n${problem.explanation}` : problem.message,
        severity: problem.severity === 'warning' ? monaco.MarkerSeverity.Warning : monaco.MarkerSeverity.Error,
      })));
      onProblems(problems);
    };
    const listener = model.onDidChangeContent(() => { clearTimeout(timer); timer = setTimeout(check, 250); });
    check();
    return { check, dispose() { clearTimeout(timer); listener.dispose(); } };
  }

  return { register, attach, get sdkModel() { return sdkModel; }, SDK_URI };
})();
