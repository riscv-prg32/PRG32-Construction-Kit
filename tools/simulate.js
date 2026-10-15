#!/usr/bin/env node
// Run a Construction Kit project in the browser simulator without a browser.
//
//   node tools/simulate.js examples/games/pong.json 200 out.ppm 20-60:UP 100:A
//
// Buttons are held for the given frame range (LEFT RIGHT UP DOWN A B START,
// joined with '+'). The last frame is written as a 320x200 PPM image and the
// game variables are printed as JSON, so tests and tutorials can check a game.
'use strict';
const fs = require('fs');
const path = require('path');

global.window = {};
eval(fs.readFileSync(path.join(__dirname, '..', 'static', 'js', 'simulator.js'), 'utf8'));
const { Simulator, compileBlocks } = window.PRG32Simulator;

const [file, framesText, out, ...script] = process.argv.slice(2);
if (!file) {
  console.error('usage: simulate.js project.json [frames] [out.ppm] [start-end:BUTTON+BUTTON ...]');
  process.exit(2);
}
const data = JSON.parse(fs.readFileSync(file, 'utf8'));
const project = data.project || data;
const frames = Number(framesText || 60);
const held = {};
script.forEach(item => {
  const [span, buttons] = item.split(':');
  const [first, last] = span.split('-').map(Number);
  for (let frame = first; frame <= (last === undefined ? first : last); frame++) {
    held[frame] = (held[frame] || []).concat(buttons.split('+'));
  }
});

// Math.random is replaced by a fixed sequence so runs are repeatable.
let seed = 12345;
Math.random = () => { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x80000000; };

const sim = new Simulator(null, null);
const ir = sim.loadBlocks(project.blocks_json);
for (let frame = 0; frame < frames; frame++) {
  sim.keys = {};
  (held[frame] || []).forEach(button => { sim.keys[button] = true; });
  sim.step(false);
}
if (out) {
  const header = Buffer.from('P6\n320 200\n255\n');
  const body = Buffer.alloc(320 * 200 * 3);
  for (let i = 0; i < 320 * 200; i++) {
    const [r, g, b] = window.PRG32Simulator.toRgb(sim.fb[i]);
    body[i * 3] = r; body[i * 3 + 1] = g; body[i * 3 + 2] = b;
  }
  fs.writeFileSync(out, Buffer.concat([header, body]));
}
console.log(JSON.stringify({ frames, warnings: ir.warnings, state: sim.state, band: sim.band }));
void compileBlocks;
