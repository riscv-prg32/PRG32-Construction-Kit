// Runs a .prg32 cartridge in the WebAssembly build of the PRG32 core under Node.
//
//   node tools/wasm_harness.mjs path/to/prg32-core.js cartridge.prg32 FRAMES EVERY
//
// Prints the same JSON lines as the native harness (wasm/harness_main.cpp), so
// tests/test_wasm_runtime.py can compare them.
//
//   node tools/wasm_harness.mjs path/to/prg32-core.js --debug cartridge.prg32 COMMAND...
//
// Runs a debugger script, with the same commands and output as `prg32-core-harness --debug`.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const args = process.argv.slice(2);
const debug = args[1] === '--debug';
if (debug) args.splice(1, 1);
const [modulePath, cartridgePath, framesText, everyText] = args;
if (!modulePath || !cartridgePath || (!debug && (!framesText || !everyText))) {
  console.error('usage: node tools/wasm_harness.mjs prg32-core.js cartridge.prg32 FRAMES EVERY');
  process.exit(2);
}

// Press each PRG32 button for 30 frames in turn (the same script as the native harness).
const SEQUENCE = [0, 1, 2, 4, 8, 16, 32, 64, 17, 34];
const scriptedInput = frame => SEQUENCE[Math.floor(frame / 30) % SEQUENCE.length];

const require = createRequire(import.meta.url);
const createPrg32Core = require(resolve(modulePath));
const core = await createPrg32Core();
const bytes = readFileSync(cartridgePath);
const pointer = core._malloc(bytes.length);
core.HEAPU8.set(bytes, pointer);
const loaded = core._prg32_load(pointer, bytes.length);
core._free(pointer);
if (!loaded) {
  console.error('load: ' + core.UTF8ToString(core._prg32_last_error()));
  process.exit(3);
}

// TARGET of a debugger command: init, update, draw, update+OFFSET or a number (0x... allowed).
function target(text) {
  const [name, offset] = text.split('+');
  const base = { init: 0, update: 1, draw: 2 }[name];
  return ((base === undefined ? Number(name) : core._prg32_entry(base) >>> 0) + Number(offset || 0)) >>> 0;
}

function runDebugScript(commands) {
  const out = [];
  for (const command of commands) {
    const colon = command.indexOf(':');
    const verb = colon < 0 ? command : command.slice(0, colon);
    const argument = colon < 0 ? '' : command.slice(colon + 1);
    let result = 0;
    if (verb === 'state') {
      out.push(`{"command":"state","state":${core.UTF8ToString(core._prg32_state_json())}}`);
      continue;
    }
    if (verb === 'slice') result = core._prg32_debug_run(0, Number(argument), 0, 1);
    else if (verb === 'break' || verb === 'unbreak') result = core._prg32_breakpoint(target(argument), verb === 'break' ? 1 : 0);
    else if (verb === 'disasm') {
      const [where, count] = argument.split(':');
      out.push(`{"command":"${command}","disassembly":${core.UTF8ToString(core._prg32_disassemble(target(where), Number(count)))}}`);
      continue;
    } else {
      const modes = { over: 1, out: 2, continue: 0, frame: 0 };
      const times = argument ? Number(argument) : 1;
      for (let time = 0; time < times; time += 1) {
        if (verb === 'step') result = core._prg32_debug_step(0);
        else if (verb === 'stepi') result = core._prg32_debug_step_instruction(0);
        else if (verb in modes) {
          if (verb === 'continue' || verb === 'frame') core._prg32_debug_resume(); // Resume / Step frame
          result = core._prg32_debug_run(0, 20000000, modes[verb], verb === 'frame' ? 1 : 0);
        } else {
          console.error('unknown command ' + command);
          process.exit(2);
        }
        if (result < 0 || (verb.startsWith('step') && result === 0)) break;
      }
    }
    out.push(`{"command":"${command}","result":${result},"state":${core.UTF8ToString(core._prg32_debug_state_json())}}`);
  }
  process.stdout.write(out.join('\n') + '\n');
}

if (debug) {
  runDebugScript(args.slice(2));
  process.exit(0);
}
const frames = Number(framesText);
const every = Number(everyText);
const lines = [core.UTF8ToString(core._prg32_state_json())];
for (let frame = 0; frame < frames; frame += 1) {
  if (!core._prg32_frame(scriptedInput(frame))) {
    console.error(`frame ${frame}: ` + core.UTF8ToString(core._prg32_last_error()));
    process.exit(4);
  }
  if ((frame + 1) % every === 0) lines.push(core.UTF8ToString(core._prg32_state_json()));
}
process.stdout.write(lines.join('\n') + '\n');
