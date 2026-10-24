// Runs a PRG32 cartridge in the browser core (static/wasm) and records its sound, for tests
// and evidence (ADR-0021, docs/audio_engine.md).
//
//   node tools/audio_capture.mjs [--module path/prg32-core.js] cartridge.prg32 FRAMES [out.wav]
//
// Prints one JSON object: per frame the 8 voices (active, synth, envelope state, level,
// volume, pan) after that frame, how many stereo frames it produced, and the left/right
// peak and energy of those frames; then the whole run's sample count, FNV-1a hash and
// counters. With out.wav the 22050 Hz signed 16-bit stereo PCM is written as a WAV file.
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const require = createRequire(import.meta.url);
const args = process.argv.slice(2);
let modulePath = resolve(root, 'static/wasm/prg32-core.js');
if (args[0] === '--module') { modulePath = resolve(args[1]); args.splice(0, 2); }
const [cartridgePath, framesText, wavPath] = args;
const createPrg32Core = require(modulePath);
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

const voiceBuffer = core._malloc(6 * 4);
const all = [];
let hash = 0xcbf29ce484222325n;
const fnvPrime = 0x100000001b3n;
const mask = (1n << 64n) - 1n;

function drain() {
  const count = core._prg32_audio_frames();
  const at = core._prg32_audio_samples() >> 1;
  const samples = core.HEAP16.slice(at, at + count * 2);
  core._prg32_audio_take();
  for (const value of samples) {
    hash ^= BigInt(value & 0xffff);
    hash = (hash * fnvPrime) & mask;
    all.push(value);
  }
  let peakLeft = 0, peakRight = 0, energyLeft = 0, energyRight = 0;
  for (let i = 0; i < samples.length; i += 2) {
    peakLeft = Math.max(peakLeft, Math.abs(samples[i]));
    peakRight = Math.max(peakRight, Math.abs(samples[i + 1]));
    energyLeft += samples[i] * samples[i];
    energyRight += samples[i + 1] * samples[i + 1];
  }
  return { count, peakLeft, peakRight, energyLeft, energyRight,
    clipped: samples.some(value => value === 32767 || value === -32768) };
}

function voices() {
  const out = [];
  for (let voice = 0; voice < 8; voice += 1) {
    core._prg32_audio_voice(voice, voiceBuffer);
    const v = core.HEAP32.slice(voiceBuffer >> 2, (voiceBuffer >> 2) + 6);
    out.push({ active: v[0], synth: v[1], state: v[2], level: v[3], volume: v[4], pan: v[5] });
  }
  return out;
}

const frames = [];
frames.push({ frame: 0, voices: voices(), ...drain() });   // after init
for (let frame = 1; frame <= Number(framesText); frame += 1) {
  if (!core._prg32_frame(0)) {
    console.error('frame: ' + core.UTF8ToString(core._prg32_last_error()));
    process.exit(4);
  }
  frames.push({ frame, voices: voices(), ...drain() });
}

if (wavPath) {
  const data = Buffer.alloc(all.length * 2);
  all.forEach((value, index) => data.writeInt16LE(value, index * 2));
  const header = Buffer.alloc(44);
  header.write('RIFF', 0); header.writeUInt32LE(36 + data.length, 4); header.write('WAVE', 8);
  header.write('fmt ', 12); header.writeUInt32LE(16, 16); header.writeUInt16LE(1, 20); header.writeUInt16LE(2, 22);
  header.writeUInt32LE(22050, 24); header.writeUInt32LE(22050 * 4, 28); header.writeUInt16LE(4, 32);
  header.writeUInt16LE(16, 34); header.write('data', 36); header.writeUInt32LE(data.length, 40);
  writeFileSync(wavPath, Buffer.concat([header, data]));
}

process.stdout.write(JSON.stringify({
  frames, samples: all.length, pcm_fnv1a: hash.toString(16).padStart(16, '0'),
  buzzer_calls: core._prg32_audio_buzzer_calls(), dropped: core._prg32_audio_dropped(),
  state: JSON.parse(core.UTF8ToString(core._prg32_state_json())),
}));
