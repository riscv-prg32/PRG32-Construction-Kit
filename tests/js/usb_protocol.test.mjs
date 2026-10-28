// Behaviour of static/js/prg32_usb_protocol.js against a pretend PRG32.
// Run: node --test tests/js/   (tests/test_usb_protocol_js.py runs it under pytest)
import test from 'node:test';
import assert from 'node:assert/strict';
import './fake_prg32_serial.js';
import {
  ProtocolSession, FrameDecoder, MESSAGE, FLAG_RESTART, encodeFrame, crc32,
  cartridgeInfo, cartridgeProblems, choosePort, USB_FILTERS
} from '../../static/js/prg32_usb_protocol.js';

function cartridge(size = 9000, abiMajor = 1, name = 'Deploy Me') {
  const bytes = new Uint8Array(size);
  bytes.set([0x50, 0x52, 0x47, 0x32]);
  new DataView(bytes.buffer).setUint16(4, abiMajor, true);
  bytes.set(new TextEncoder().encode(name), 40);
  for (let i = 128; i < size; i += 1) bytes[i] = i & 0xff;
  return bytes;
}

async function session(options) {
  const port = globalThis.createFakePrg32Port(options);
  const s = new ProtocolSession(port);
  await s.open();
  return { s, device: port.device };
}

test('crc32 matches zlib for a known vector', () => {
  assert.equal(crc32(new TextEncoder().encode('123456789')), 0xcbf43926);
});

test('the decoder skips log text and corrupt frames', () => {
  const decoder = new FrameDecoder();
  const bad = encodeFrame(MESSAGE.STATUS, 1, new TextEncoder().encode('bad'));
  bad[bad.length - 1] ^= 0x80;
  decoder.push(new TextEncoder().encode('boot log\n'));
  decoder.push(bad);
  decoder.push(encodeFrame(MESSAGE.STATUS, 2, new TextEncoder().encode('{"ok":true}')));
  const frame = decoder.next();
  assert.equal(frame.requestId, 2);
  assert.equal(decoder.next(), null);
});

test('a store upload uses the negotiated chunk size and reports progress', async () => {
  const { s, device } = await session();
  const hello = await s.hello();
  assert.equal(s.chunkSize(), 4096);
  const bytes = cartridge();
  const info = cartridgeInfo(bytes);
  assert.deepEqual(cartridgeProblems(info, hello), []);
  const progress = [];
  const result = await s.upload(bytes, { name: info.name, slot: 'cart3', command: 'store' }, (r, t) => progress.push([r, t]));
  assert.equal(result.slot, 'cart3');
  assert.equal(result.running, false);
  assert.deepEqual([...device.slots.cart3], [...bytes]);
  assert.deepEqual(device.chunkSizes, [4096, 4096, 808]);
  assert.deepEqual(progress.at(-1), [9000, 9000]);
  await s.close();
  assert.equal(device.setSignalsCalls, 0);
});

test('an older firmware without max_chunk gets 1024-byte chunks', async () => {
  const { s, device } = await session({ hello: { max_chunk: undefined } });
  await s.hello();
  await s.upload(cartridge(3000), { name: 'x', slot: 'cart0', command: 'run' });
  assert.deepEqual(device.chunkSizes, [1024, 1024, 952]);
  await s.close();
});

test('a chunk whose reply was lost is sent once more and not written twice', async () => {
  const { s, device } = await session({ dropReplies: [1] });
  await s.hello();
  const bytes = cartridge(5000);
  const result = await s.upload(bytes, { name: 'x', slot: 'cart1', command: 'store' });
  assert.equal(result.ok, true);
  assert.equal(device.dataRequests, 3);
  assert.deepEqual([...device.slots.cart1], [...bytes]);
  await s.close();
});

test('refusals happen before anything is sent', async () => {
  const { s, device } = await session();
  const hello = await s.hello();
  const info = cartridgeInfo(cartridge());
  assert.match(cartridgeProblems({ ...info, abiMajor: 2 }, hello).join(), /ABI 2/);
  assert.match(cartridgeProblems(info, hello, 'debug').join(), /PRG32-QT/);
  assert.match(cartridgeProblems({ ...info, size: 70000 }, hello).join(), /at most 65536/);
  assert.match(cartridgeProblems(cartridgeInfo(new Uint8Array(100)), hello).join(), /not a PRG32 cartridge/);
  assert.match(cartridgeProblems(info, { protocol: 'other' }).join(), /prg32-io-1.0/);
  assert.deepEqual(device.requests, [MESSAGE.HELLO]);
  await s.close();
});

test('the device refusing a request becomes a readable error', async () => {
  const { s } = await session();
  await assert.rejects(s.upload(cartridge(), { name: 'x', slot: 'cart9', command: 'store' }), /cart0 to cart7/);
  await assert.rejects(s.json(MESSAGE.UPLOAD_BEGIN, { name: 'x', slot: 'cart2', size: 1, crc32: 0, command: 'debug' }), /PRG32-Qt only/);
  await s.close();
});

test('performance retrieval restarts the document then follows the chunks', async () => {
  const { s, device } = await session({ performanceChunks: ['{"cases":', '[1,', '2]}'] });
  assert.equal(await s.performance(), '{"cases":[1,2]}');
  assert.deepEqual(device.performanceFlags, [FLAG_RESTART, 0, 0]);
  await s.close();
});

test('a silent device times out instead of hanging', async () => {
  const { s } = await session({ silent: true });
  await assert.rejects(s.request(MESSAGE.HELLO, new Uint8Array(), 200), error => error.name === 'TimeoutError');
  await s.close();
});

test('the port chooser asks only for ESP32-C6 native USB and reuses an authorized one', async () => {
  const target = {};
  const serial = globalThis.installFakeSerial(target);
  const port = await choosePort(target.serial);
  assert.deepEqual(serial.requestPortFilters, USB_FILTERS);
  serial.requestPortFilters = null;
  assert.equal(await choosePort(target.serial), port);
  assert.equal(serial.requestPortFilters, null);
});
