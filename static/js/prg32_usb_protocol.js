// Browser client for PRG32's self-synchronising prg32-io-1.0 protocol.
export const MESSAGE = Object.freeze({
  HELLO: 0x01, UPLOAD_BEGIN: 0x02, UPLOAD_DATA: 0x03, UPLOAD_END: 0x04,
  RUN: 0x05, DEBUG: 0x06, PERFORMANCE_GET: 0x07, STATUS: 0x80, RESULT_DATA: 0x81
});
export const MAGIC = new Uint8Array([0x50, 0x52, 0x47, 0x33, 0x32, 0x49, 0x4f, 0x00]);
const HEADER_SIZE = 24;
const MAX_PAYLOAD = 16 * 1024;
const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let number = 0; number < 256; number += 1) {
    let value = number;
    for (let bit = 0; bit < 8; bit += 1) value = (value & 1) ? (0xedb88320 ^ (value >>> 1)) : (value >>> 1);
    table[number] = value >>> 0;
  }
  return table;
})();

export function crc32(bytes) {
  let value = 0xffffffff;
  for (const byte of bytes) value = CRC_TABLE[(value ^ byte) & 0xff] ^ (value >>> 8);
  return (value ^ 0xffffffff) >>> 0;
}

export function encodeFrame(type, requestId, payload = new Uint8Array(), flags = 0) {
  if (payload.length > MAX_PAYLOAD) throw new Error('USB protocol payload is too large.');
  const frame = new Uint8Array(HEADER_SIZE + payload.length);
  frame.set(MAGIC);
  const view = new DataView(frame.buffer);
  view.setUint8(8, 1);
  view.setUint8(9, type);
  view.setUint16(10, flags, true);
  view.setUint32(12, requestId, true);
  view.setUint32(16, payload.length, true);
  view.setUint32(20, crc32(payload), true);
  frame.set(payload, HEADER_SIZE);
  return frame;
}

export class ProtocolSession {
  constructor(port) {
    this.port = port;
    this.reader = null;
    this.writer = null;
    this.buffer = new Uint8Array();
    this.requestId = 0;
  }
  async open() {
    await this.port.open({ baudRate: 115200, bufferSize: 32768 });
    this.writer = this.port.writable.getWriter();
    this.reader = this.port.readable.getReader();
  }
  async close() {
    if (this.reader) this.reader.releaseLock();
    if (this.writer) this.writer.releaseLock();
    await this.port.close();
  }
  magicOffset() {
    for (let start = 0; start <= this.buffer.length - MAGIC.length; start += 1) {
      if (MAGIC.every((byte, index) => this.buffer[start + index] === byte)) return start;
    }
    return -1;
  }
  decode() {
    const start = this.magicOffset();
    if (start < 0) {
      this.buffer = this.buffer.slice(Math.max(0, this.buffer.length - MAGIC.length + 1));
      return null;
    }
    if (start) this.buffer = this.buffer.slice(start);
    if (this.buffer.length < HEADER_SIZE) return null;
    const view = new DataView(this.buffer.buffer, this.buffer.byteOffset, this.buffer.byteLength);
    const size = view.getUint32(16, true);
    if (view.getUint8(8) !== 1 || size > MAX_PAYLOAD) {
      this.buffer = this.buffer.slice(1);
      return null;
    }
    if (this.buffer.length < HEADER_SIZE + size) return null;
    const payload = this.buffer.slice(HEADER_SIZE, HEADER_SIZE + size);
    const frame = { type: view.getUint8(9), flags: view.getUint16(10, true), requestId: view.getUint32(12, true), payload };
    const expectedCrc = view.getUint32(20, true);
    this.buffer = this.buffer.slice(HEADER_SIZE + size);
    return crc32(payload) === expectedCrc ? frame : null;
  }
  async next(deadline) {
    while (Date.now() < deadline) {
      const frame = this.decode();
      if (frame) return frame;
      const wait = Math.max(1, deadline - Date.now());
      const answer = await Promise.race([
        this.reader.read(),
        new Promise(resolve => setTimeout(() => resolve({ timeout: true }), wait))
      ]);
      if (answer.timeout) throw new Error('The PRG32 device did not answer the USB protocol request.');
      if (answer.done) throw new Error('The PRG32 USB connection closed unexpectedly.');
      const joined = new Uint8Array(this.buffer.length + answer.value.length);
      joined.set(this.buffer);
      joined.set(answer.value, this.buffer.length);
      this.buffer = joined;
    }
    throw new Error('The PRG32 device did not answer the USB protocol request.');
  }
  async request(type, payload = new Uint8Array(), timeoutMs = 15000) {
    const requestId = ++this.requestId;
    await this.writer.write(encodeFrame(type, requestId, payload));
    const deadline = Date.now() + timeoutMs;
    while (true) {
      const frame = await this.next(deadline);
      if (frame.requestId === requestId) return frame;
    }
  }
  status(frame) {
    if (frame.type !== MESSAGE.STATUS) throw new Error('The PRG32 device returned an unexpected response.');
    let value;
    try { value = JSON.parse(new TextDecoder().decode(frame.payload)); } catch (_) { throw new Error('The PRG32 device returned invalid status data.'); }
    if (!value.ok) throw new Error(value.error || 'The PRG32 device rejected the request.');
    return value;
  }
  async json(type, value, timeoutMs = 15000) {
    return this.status(await this.request(type, new TextEncoder().encode(JSON.stringify(value)), timeoutMs));
  }
  async hello() { return this.status(await this.request(MESSAGE.HELLO)); }
  async upload(data, metadata, onProgress) {
    await this.json(MESSAGE.UPLOAD_BEGIN, { ...metadata, size: data.length, crc32: crc32(data) });
    for (let offset = 0; offset < data.length; offset += 1024) {
      const chunk = data.subarray(offset, Math.min(offset + 1024, data.length));
      const payload = new Uint8Array(4 + chunk.length);
      new DataView(payload.buffer).setUint32(0, offset, true);
      payload.set(chunk, 4);
      const progress = this.status(await this.request(MESSAGE.UPLOAD_DATA, payload));
      onProgress(progress.received, progress.total);
    }
    return this.json(MESSAGE.UPLOAD_END, { size: data.length }, 30000);
  }
  async performance() {
    const output = [];
    while (true) {
      const frame = await this.request(MESSAGE.PERFORMANCE_GET);
      if (frame.type === MESSAGE.STATUS) this.status(frame);
      if (frame.type !== MESSAGE.RESULT_DATA) throw new Error('The PRG32 device returned an unexpected performance response.');
      output.push(...frame.payload);
      if (frame.flags & 1) break;
    }
    const text = new TextDecoder().decode(new Uint8Array(output));
    JSON.parse(text);
    return text;
  }
}
