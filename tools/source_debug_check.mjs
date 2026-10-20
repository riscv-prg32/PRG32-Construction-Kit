// Drives the browser PRG32 core with the source debugger (static/js/source_debug.js), for tests.
//
//   node tools/source_debug_check.mjs cartridge.prg32 debug-map.json [source-map.json|-] COMMAND...
//
// Commands (each prints one JSON line):
//   line:N          put a breakpoint on source line N (it moves to the next line with code)
//   block:ID        put a breakpoint on a Blockly block
//   if:N:COND       breakpoint on line N that only stops when COND holds (e.g. if:20:row == 2)
//   continue        run until a breakpoint (resume ignores the current one once, like PRG32-QT)
//   stepi[:N]       step N instructions
//   where           the line, block, call stack, variables, globals and CSRs where the core is
//   watch:EXPR      the value of a watch expression in the innermost frame
// Conditional breakpoints are checked here exactly as the Player checks them: when the
// address breakpoint hits and the condition is false, run on.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const SourceDebug = require(resolve(root, 'static/js/source_debug.js'));
const createPrg32Core = require(resolve(root, 'static/wasm/prg32-core.js'));

const [cartridgePath, mapPath, sourceMapPath, ...commands] = process.argv.slice(2);
const core = await createPrg32Core();
const bytes = readFileSync(cartridgePath);
const pointer = core._malloc(bytes.length);
core.HEAPU8.set(bytes, pointer);
if (!core._prg32_load(pointer, bytes.length)) {
  console.error('load: ' + core.UTF8ToString(core._prg32_last_error()));
  process.exit(3);
}
core._free(pointer);

const buffer = core._malloc(4096);
const memory = {
  read(address, length) {
    const count = core._prg32_read_memory(address >>> 0, buffer, Math.min(length, 4096));
    return count === length ? core.HEAPU8.slice(buffer, buffer + count) : null;
  },
};
const state = () => JSON.parse(core.UTF8ToString(core._prg32_debug_state_json()));
const debug = SourceDebug.create({
  debugMap: JSON.parse(readFileSync(mapPath, 'utf8')),
  sourceMap: sourceMapPath && sourceMapPath !== '-' ? JSON.parse(readFileSync(sourceMapPath, 'utf8')) : null,
  guestBase: core._prg32_guest_base() >>> 0,
});
const conditions = new Map();   // address -> condition text

function place(found, condition) {
  if (!found) return { placed: null };
  for (const address of found.addresses) {
    core._prg32_breakpoint(address, 1);
    if (condition) conditions.set(address, condition);
  }
  return { placed: found };
}

function where() {
  const now = state();
  const stack = debug.callStack(now, memory);
  const top = stack[0];
  return {
    pc: now.pc, phase: now.phase, line: debug.lineAt(now.pc), block: debug.blockAt(now.pc),
    stack: stack.map(frame => ({ function: frame.function, file: frame.file, line: frame.line, guessed: !!frame.guessed,
      inlined: !!frame.inlined, inlinedInto: frame.inlinedInto || null })),
    variables: stack.map(frame => debug.variables(frame, memory).map(v => ({ name: v.name, text: v.text }))),
    globals: debug.globals(memory).map(g => ({ name: g.name, text: g.text })),
    csr: SourceDebug.csrRows(now).map(row => [row.name, row.value]),
    retired: now.retired, top: top ? top.function : null,
  };
}

const out = [];
for (const command of commands) {
  const [verb, ...rest] = command.split(':');
  if (verb === 'line') out.push({ command, ...place(debug.breakpointForLine(Number(rest[0]))) });
  else if (verb === 'block') out.push({ command, ...place(debug.breakpointForBlock(rest.join(':'))) });
  else if (verb === 'if') out.push({ command, ...place(debug.breakpointForLine(Number(rest[0])), rest.slice(1).join(':')) });
  else if (verb === 'continue') {
    let result = 0;
    let skipped = 0;
    for (;;) {
      core._prg32_debug_resume();
      result = core._prg32_debug_run(0, 20000000, 0, 0);
      const now = state();
      const text = result === 2 ? conditions.get(now.pc >>> 0) : null;
      if (!text) break;
      const verdict = debug.condition(text, debug.callStack(now, memory)[0], memory);
      if (!verdict.ok || verdict.value) break;
      skipped += 1;
      if (skipped > 10000) break;
    }
    out.push({ command, result, skipped, ...where() });
  } else if (verb === 'stepi') {
    const times = Number(rest[0] || 1);
    const widths = [];
    for (let i = 0; i < times; i++) {
      const before = state().pc >>> 0;
      core._prg32_debug_step_instruction(0);
      widths.push(((state().pc >>> 0) - before) | 0);
    }
    out.push({ command, widths, ...where() });
  } else if (verb === 'where') out.push({ command, ...where() });
  else if (verb === 'watch') {
    const frame = debug.callStack(state(), memory)[0];
    const value = debug.watch(rest.join(':'), frame, memory);
    out.push({ command, text: value.text, value: value.value, error: !!value.error });
  } else {
    console.error('unknown command ' + command);
    process.exit(2);
  }
}
process.stdout.write(JSON.stringify(out) + '\n');
