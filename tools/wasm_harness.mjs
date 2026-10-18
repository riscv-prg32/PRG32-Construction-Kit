// Runs a .prg32 cartridge in the WebAssembly build of the PRG32 core under Node.
//
//   node tools/wasm_harness.mjs path/to/prg32-core.js cartridge.prg32 FRAMES EVERY
//
// Prints the same JSON lines as the native harness (wasm/harness_main.cpp), so
// tests/test_wasm_runtime.py can compare them.
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve } from 'node:path';

const [modulePath, cartridgePath, framesText, everyText] = process.argv.slice(2);
if (!modulePath || !cartridgePath || !framesText || !everyText) {
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
