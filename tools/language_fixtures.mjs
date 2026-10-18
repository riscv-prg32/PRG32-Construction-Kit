// Runs the IDE's language services (static/js/ide/language.js) under Node, for the tests.
//
//   node tools/language_fixtures.mjs < requests.json
//
// The input is a JSON list of requests:
//   {"op": "diagnostics", "language": "c" | "asm", "source": "...", "title": "..."}
//   {"op": "completions" | "hover" | "signatureHelp" | "definition", "language": ..., "source": ...,
//    "position": {"line": 1, "column": 1}}
//   {"op": "normalize", "language": ..., "source": ..., "output": "compiler output"}
//   {"op": "entryPrefix", "title": "..."}
// and the output is the JSON list of answers, in the same order. Nothing is fetched:
// the answers depend only on the request and the committed language index.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
require(resolve(root, 'static/js/ide/prg32_language_index.js'));  // sets globalThis.PRG32LanguageIndex
const language = require(resolve(root, 'static/js/ide/language.js'));
language.useIndex(globalThis.PRG32LanguageIndex);

const requests = JSON.parse(readFileSync(0, 'utf8'));
const answers = requests.map(request => {
  switch (request.op) {
    case 'diagnostics': return language.diagnostics(request.language, request.source, { title: request.title });
    case 'completions': return language.completions(request.language, request.source, request.position);
    case 'hover': return language.hover(request.language, request.source, request.position);
    case 'signatureHelp': return language.signatureHelp(request.language, request.source, request.position);
    case 'definition': return language.definition(request.language, request.source, request.position);
    case 'normalize': return language.normalizeCompilerOutput(request.output,
      { language: request.language, source: request.source });
    case 'entryPrefix': return language.entryPrefix(request.title);
    default: throw new Error(`unknown op ${request.op}`);
  }
});
process.stdout.write(JSON.stringify(answers));
