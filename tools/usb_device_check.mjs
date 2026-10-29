#!/usr/bin/env node
// Hardware check for static/js/prg32_usb_protocol.js on a real PRG32.
//
//   node tools/usb_device_check.mjs /dev/cu.usbmodem101 game.prg32 [slot] [store|run]
//
// Browsers need a person to choose the port, so this tool runs the exact
// module the Deploy page loads under Node, with a small adapter that gives a
// serial device the Web Serial port shape (open, readable, writable, close).
// Like a browser, the adapter never changes DTR or RTS. It writes the slot it
// is given; choose one nobody needs.
import fs from 'node:fs';
import tty from 'node:tty';
import { ReadableStream, WritableStream } from 'node:stream/web';
import {
  ProtocolSession, cartridgeInfo, cartridgeProblems, CLIENT_VERSION
} from '../static/js/prg32_usb_protocol.js';

class NodeSerialPort {
  constructor(path) {
    this.path = path;
    this.fd = null;
  }

  async open() {
    this.fd = fs.openSync(this.path, fs.constants.O_RDWR | fs.constants.O_NOCTTY);
    this.input = new tty.ReadStream(this.fd);
    this.input.setRawMode(true);
    const input = this.input;
    this.readable = new ReadableStream({
      start(controller) {
        input.on('data', chunk => controller.enqueue(new Uint8Array(chunk)));
        input.on('end', () => controller.close());
      },
      cancel() { input.pause(); }
    });
    const fd = this.fd;
    this.writable = new WritableStream({
      // A tty accepts part of a large write; keep writing until all is sent.
      write(chunk) {
        let sent = 0;
        while (sent < chunk.length) {
          try {
            sent += fs.writeSync(fd, chunk, sent, chunk.length - sent);
          } catch (error) {
            if (error.code !== 'EAGAIN') throw error;
          }
        }
      }
    });
  }

  async close() {
    this.input.destroy();
  }
}

const [path, file, slot = 'cart7', command = 'store'] = process.argv.slice(2);
if (!path || !file) {
  console.error('usage: node tools/usb_device_check.mjs PORT CARTRIDGE.prg32 [slot] [store|run]');
  process.exit(2);
}
const bytes = new Uint8Array(fs.readFileSync(file));
const info = cartridgeInfo(bytes);
const session = new ProtocolSession(new NodeSerialPort(path));
const results = [];
const check = (name, ok, detail = '') => {
  results.push(ok);
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ': ' + detail : ''}`);
};

await session.open();
try {
  console.log(`client ${CLIENT_VERSION}, cartridge ${info.name} (${info.size} bytes, ABI ${info.abiMajor}.${info.abiMinor})`);
  const hello = await session.hello();
  check('HELLO', hello.protocol === 'prg32-io-1.0', `firmware ${hello.firmware}, target ${hello.target}, chunk ${session.chunkSize()}`);
  check('cartridge accepted by the browser checks', cartridgeProblems(info, hello, command).length === 0,
    cartridgeProblems(info, hello, command).join(' '));
  check('wrong ABI refused before sending', cartridgeProblems({ ...info, abiMajor: 99 }, hello).length === 1);
  check('debug refused before sending', cartridgeProblems(info, hello, 'debug').length === 1);
  const steps = [];
  const started = Date.now();
  const result = await session.upload(bytes, { name: info.name, slot, command }, (received, total) => steps.push([received, total]));
  const seconds = (Date.now() - started) / 1000;
  check(`${command} upload to ${slot}`, result.ok && result.slot === slot && result.running === (command === 'run'),
    `${JSON.stringify(result)} in ${seconds.toFixed(2)} s, ${steps.length} progress reports`);
  check('progress reached the full size', steps.length > 0 && steps[steps.length - 1][0] === bytes.length);
  const again = await session.hello();
  check('device still answers after the upload', again.protocol === 'prg32-io-1.0');
  const text = await session.performance();
  check('performance retrieval returns JSON', JSON.parse(text) !== null, text.slice(0, 80));
} finally {
  await session.close();
}
const failed = results.filter(ok => !ok).length;
console.log(`${results.length - failed}/${results.length} checks passed`);
process.exit(failed ? 1 : 0);
