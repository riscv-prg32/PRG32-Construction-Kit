// Source and block debugging for the Cartridge Player (ADR-0015).
//
// PRG32SourceDebug.create({debugMap, sourceMap}) reads the two maps the kit saved with a
// cartridge and answers, for the paused core:
//   lineAt(pc)                 which line of game.c / game.S is running
//   blockAt(pc), blockOfLine   which Blockly block made that line (Blocks projects)
//   breakpointFor(line|block)  the guest addresses to stop at
//   callStack(state, memory)   the chain of calls, unwound with the DWARF call-frame rules
//   variables(frame, memory)   parameters and locals in scope, with their values
//   globals(memory)            global variables (and assembly data labels)
//   watch(text, frame, memory) the value of  name,  a.b,  a[3]  or a register
//   condition(text, ...)       a breakpoint condition such as  score > 10
// Plain functions only (no DOM, no core): tests run them in Node on committed fixtures.
// When the map is missing or damaged, ok is false and the Player stays address-level.
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.PRG32SourceDebug = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const REGISTER_NAMES = ['zero', 'ra', 'sp', 'gp', 'tp', 't0', 't1', 't2', 's0', 's1', 'a0', 'a1', 'a2', 'a3', 'a4',
    'a5', 'a6', 'a7', 's2', 's3', 's4', 's5', 's6', 's7', 's8', 's9', 's10', 's11', 't3', 't4', 't5', 't6'];
  const MAX_FRAMES = 16;
  const MAX_CHILDREN = 16;
  const NEAREST_LINES = 20;   // a breakpoint on a line without code moves to the next line with code

  const hex = value => '0x' + (value >>> 0).toString(16).padStart(8, '0');

  function registerNumber(name) {
    const text = String(name).toLowerCase();
    if (text === 'fp') return 8;
    const index = REGISTER_NAMES.indexOf(text);
    if (index >= 0) return index;
    const x = text.match(/^x(\d{1,2})$/);
    return x && Number(x[1]) < 32 ? Number(x[1]) : -1;
  }

  // --- memory -----------------------------------------------------------------------
  // memory.read(address, length) -> Uint8Array | null (the core's bounded guest reads).
  function readUnsigned(memory, address, size) {
    const bytes = memory.read(address >>> 0, size);
    if (!bytes || bytes.length < size) return null;
    let value = 0;
    for (let i = size - 1; i >= 0; i--) value = value * 256 + bytes[i];
    return value;
  }

  function create(options) {
    const map = options.debugMap || {};
    const sourceMap = options.sourceMap || null;
    if (map.status !== 'ok') {
      return { ok: false, reason: map.reason || 'no debug information', hasBlocks: false };
    }
    const delta = (options.guestBase === undefined ? map.link_base : options.guestBase) - map.link_base;
    const at = address => (address + delta) >>> 0;     // link address -> guest address
    const back = address => (address - delta) >>> 0;   // guest address -> link address
    const files = map.files;
    const userFile = sourceMap ? sourceMap.file : (files.includes('game.c') ? 'game.c' : files.includes('game.S') ? 'game.S' : files[0]);
    const userIndex = files.indexOf(userFile);
    const rows = map.lines;                             // [address, file, line, is_stmt], sorted by address
    const types = map.types || {};
    const functions = map.functions || [];
    const cfi = map.cfi || [];
    const symbols = (map.symbols || []).filter(s => !s.name.startsWith('__') || s.name === '__cart_start');
    const codeEnd = rows.length ? Math.max(...rows.filter(r => r[1] === userIndex).map(r => r[0])) : 0;

    // --- lines ----------------------------------------------------------------------
    function rowAt(address) {
      let low = 0;
      let high = rows.length - 1;
      let found = -1;
      while (low <= high) {
        const mid = (low + high) >> 1;
        if (rows[mid][0] <= address) { found = mid; low = mid + 1; } else high = mid - 1;
      }
      // Rows are sorted by address with ends of sequences first, so the last row at or before
      // the address describes it; if that row ends a sequence, the address has no line.
      if (found < 0 || rows[found][1] < 0) return null;
      return rows[found];
    }

    function lineAt(pc) {
      const row = rowAt(back(pc));
      return row ? { file: files[row[1]], line: row[2] } : null;
    }

    // Statement starts of one line: rows with is_stmt whose previous row is another line.
    // A row followed, at the same address, by a row of another line covers no instruction
    // (the optimiser moved that line's work elsewhere): the line has no code there.
    function lineStarts(fileIndex, line) {
      const out = [];
      for (let i = 0; i < rows.length; i++) {
        const row = rows[i];
        if (row[1] !== fileIndex || row[2] !== line || !row[3]) continue;
        if (rows[i + 1] && rows[i + 1][0] === row[0] && (rows[i + 1][1] !== fileIndex || rows[i + 1][2] !== line)) continue;
        const previous = rows[i - 1];
        if (previous && previous[1] === fileIndex && previous[2] === line && previous[0] !== row[0]) continue;
        if (!out.includes(row[0])) out.push(row[0]);
      }
      return out;
    }

    function breakpointForLine(line, file) {
      const fileIndex = files.indexOf(file || userFile);
      for (let candidate = line; candidate < line + NEAREST_LINES; candidate++) {
        const addresses = lineStarts(fileIndex, candidate);
        if (addresses.length) return { line: candidate, addresses: addresses.map(at) };
      }
      return null;
    }

    // --- blocks ---------------------------------------------------------------------
    const entries = sourceMap ? sourceMap.entries : [];
    function blockOfLine(line) {
      let best = null;
      for (const entry of entries) {
        const [first, last] = entry.lines;
        if (line >= first && line <= last && (!best || last - first < best.lines[1] - best.lines[0])) best = entry;
      }
      return best;
    }

    function blockAt(pc) {
      const where = lineAt(pc);
      return where && where.file === userFile ? blockOfLine(where.line) : null;
    }

    function breakpointForBlock(blockId) {
      const entry = entries.find(item => item.block === blockId);
      if (!entry) return null;
      for (let line = entry.lines[0]; line <= entry.lines[1]; line++) {
        const addresses = lineStarts(userIndex, line);
        if (addresses.length) return { line, addresses: addresses.map(at), block: blockId };
      }
      return null;
    }

    // --- functions and the call stack ---------------------------------------------------
    function functionAt(pc) {
      const address = back(pc);
      const fn = functions.find(item => address >= item.low && address < item.high);
      if (fn) return { name: fn.name, low: fn.low, info: fn };
      let best = null;
      for (const symbol of symbols) {
        if ((symbol.kind === 'function' || symbol.kind === 'label') && symbol.address <= address
            && (!best || symbol.address >= best.address) && symbol.name !== '__cart_start') best = symbol;
      }
      return best ? { name: best.name, low: best.address, info: null } : null;
    }

    function cfiRow(pc) {
      const address = back(pc);
      const entry = cfi.find(item => address >= item.low && address < item.high);
      if (!entry) return null;
      let row = null;
      for (const candidate of entry.rows) if (candidate[0] <= address) row = candidate;
      return row;
    }

    // frames[0] is where the core stopped; each next frame is its caller.
    function callStack(state, memory) {
      const imageEnd = map.link_base + map.image_size;
      const inImage = pc => back(pc) >= map.link_base && back(pc) < imageEnd;
      const frames = [];
      let registers = state.registers.slice();
      let pc = state.pc >>> 0;
      for (let depth = 0; depth < MAX_FRAMES && inImage(pc); depth++) {
        // A caller's line is the call instruction's, just before the return address.
        const lookup = depth === 0 ? pc : pc - 2;
        const fn = functionAt(lookup);
        const where = lineAt(lookup);
        const row = cfiRow(lookup);
        const cfa = row ? (registers[row[1]] + row[2]) >>> 0 : null;
        frames.push({ depth, pc, lookup, function: fn ? fn.name : hex(pc), file: where && where.file,
          line: where && where.line, cfa, registers, info: fn && fn.info });
        if (!row) {
          // Assembly without call-frame rules: if this is where the core stopped, ra is the way back.
          if (depth === 0 && inImage(registers[1] >>> 0)) {
            const back2 = (registers[1] >>> 0) - 2;
            const caller = functionAt(back2);
            const line = lineAt(back2);
            frames.push({ depth: 1, pc: registers[1] >>> 0, lookup: back2, function: caller ? caller.name : hex(registers[1]),
              file: line && line.file, line: line && line.line, cfa: null, registers: null, info: null, guessed: true });
          }
          break;
        }
        const next = registers.slice();
        for (const [reg, offset] of Object.entries(row[3])) {
          const saved = readUnsigned(memory, cfa + offset, 4);
          if (saved === null) return frames;
          next[Number(reg)] = saved;
        }
        if (row[3]['1'] === undefined && depth > 0) break;  // a caller always saved ra: anything else is not a call
        const returnAddress = (row[3]['1'] !== undefined ? next[1] : registers[1]) >>> 0;
        next[2] = cfa;
        if (!returnAddress || returnAddress === pc) break;
        registers = next;
        pc = returnAddress;
      }
      return frames;
    }

    // --- locations ------------------------------------------------------------------
    // One DWARF location: ops like [["fbreg", -20]], or ranges [[low, high, ops], ...].
    function locationAt(location, frame) {
      if (!location || !location.length) return null;
      if (typeof location[0][0] === 'number') {
        const address = back(frame.lookup);
        const range = location.find(item => address >= item[0] && address < item[1]);
        return range ? range[2] : null;
      }
      return location;
    }

    function evaluate(ops, frame, memory) {
      if (!ops) return { unavailable: 'not available here (optimised out at this point)' };
      const stack = [];
      const reg = number => (frame.registers ? frame.registers[number] >>> 0 : null);
      for (const op of ops) {
        const [name, a] = op;
        let match;
        if (name === 'addr') stack.push(at(a));
        else if ((match = name.match(/^reg(\d+)$/))) {
          if (ops.length !== 1) return { unavailable: 'kept in pieces' };
          return reg(Number(match[1])) === null ? { unavailable: 'register not known in this frame' }
            : { register: Number(match[1]), value: reg(Number(match[1])) };
        } else if ((match = name.match(/^breg(\d+)$/))) {
          if (reg(Number(match[1])) === null) return { unavailable: 'register not known in this frame' };
          stack.push((reg(Number(match[1])) + a) >>> 0);
        } else if (name === 'fbreg') {
          const base = (frame.info && frame.info.frame_base) || [];
          if (base.length !== 1 || base[0][0] !== 'call_frame_cfa' || frame.cfa === null) {
            return { unavailable: 'frame base not supported' };
          }
          stack.push((frame.cfa + a) >>> 0);
        } else if (name === 'call_frame_cfa') {
          if (frame.cfa === null) return { unavailable: 'no call-frame information' };
          stack.push(frame.cfa);
        } else if ((match = name.match(/^lit(\d+)$/))) stack.push(Number(match[1]));
        else if (/^const(\d[us]|u|s)$/.test(name)) stack.push(a);
        else if (name === 'plus_uconst') stack.push((stack.pop() + a) >>> 0);
        else if (['plus', 'minus', 'mul', 'and', 'or', 'xor', 'shl', 'shr'].includes(name)) {
          const right = stack.pop();
          const left = stack.pop();
          if (left === undefined || right === undefined) return { unavailable: 'unsupported location' };
          stack.push({ plus: left + right, minus: left - right, mul: Math.imul(left, right), and: left & right,
            or: left | right, xor: left ^ right, shl: left << right, shr: left >>> right }[name] >>> 0);
        } else if (name === 'neg') stack.push((-stack.pop()) >>> 0);
        else if (name === 'not') stack.push((~stack.pop()) >>> 0);
        else if (name === 'stack_value') return { value: stack.pop() >>> 0 };
        else if (name === 'entry_value' || name === 'GNU_entry_value') {
          return { unavailable: 'optimised out (only its value at the start of the function is known)' };
        } else return { unavailable: `location "${name}" not supported` };
      }
      return stack.length ? { address: stack.pop() >>> 0 } : { unavailable: 'unsupported location' };
    }

    // --- values -----------------------------------------------------------------------
    function resolve(typeId) {
      let type = types[typeId];
      let guard = 0;
      while (type && type.kind === 'alias' && guard++ < 12) type = types[type.target];
      return type || { kind: 'unknown' };
    }

    function typeName(typeId) {
      const type = types[typeId];
      if (!type) return 'int';
      if (type.kind === 'alias') return type.name || typeName(type.target);
      if (type.kind === 'pointer') return typeName(type.target) + ' *';
      if (type.kind === 'array') return `${typeName(type.target)}[${type.count ?? ''}]`;
      return type.name || type.kind;
    }

    function sizeOf(typeId) {
      const type = resolve(typeId);
      if (type.kind === 'array') return (type.count || 0) * sizeOf(type.target);
      return type.size || 4;
    }

    function scalarText(type, raw) {
      const size = type.size || 4;
      const bits = size * 8;
      if (type.kind === 'pointer') return hex(raw);
      if (type.kind === 'enum') return type.values[String(raw)] || String(raw);
      if (type.encoding === 'bool') return raw ? 'true' : 'false';
      let value = raw;
      if (type.encoding === 'signed' || (type.encoding === 'char' && /^(signed )?char$/.test(type.name || ''))) {
        if (bits < 32 && value >= 2 ** (bits - 1)) value -= 2 ** bits;
        else if (bits === 32) value |= 0;
      }
      if (type.encoding === 'char' && size === 1) {
        const code = raw & 0xff;
        return code >= 32 && code < 127 ? `${value} '${String.fromCharCode(code)}'` : String(value);
      }
      return String(value);
    }

    // A value: {text, children?, address?}
    function valueOf(typeId, where, memory, depth) {
      const type = resolve(typeId);
      if (where.unavailable) return { text: where.unavailable, unavailable: true };
      if (where.value !== undefined && where.address === undefined) {
        const masked = type.size && type.size < 4 ? where.value & (2 ** (type.size * 8) - 1) : where.value;
        return { text: scalarText(type, masked >>> 0), register: where.register };
      }
      const address = where.address;
      if (type.kind === 'array' || type.kind === 'struct') {
        if ((depth || 0) > 3) return { text: '…', address };
        const children = [];
        if (type.kind === 'array') {
          const step = sizeOf(type.target);
          for (let i = 0; i < Math.min(type.count || 0, MAX_CHILDREN); i++) {
            children.push({ name: `[${i}]`, ...valueOf(type.target, { address: address + i * step }, memory, (depth || 0) + 1) });
          }
          if ((type.count || 0) > MAX_CHILDREN) children.push({ name: '…', text: `${type.count - MAX_CHILDREN} more` });
          return { text: `${typeName(typeId)} at ${hex(address)}`, children, address };
        }
        for (const member of type.members) {
          children.push({ name: member.name, ...valueOf(member.type, { address: address + member.offset }, memory, (depth || 0) + 1) });
        }
        return { text: `{${children.map(child => `${child.name}: ${child.text}`).join(', ')}}`, children, address };
      }
      const size = type.size || 4;
      const raw = readUnsigned(memory, address, Math.min(size, 4));
      if (raw === null) return { text: 'not readable', unavailable: true, address };
      return { text: scalarText(type, raw), address };
    }

    function inScope(variable, frame) {
      if (!variable.scope) return true;
      const address = back(frame.lookup);
      return address >= variable.scope[0] && address < variable.scope[1];
    }

    function variables(frame, memory) {
      if (!frame || !frame.info) return [];
      return frame.info.variables
        .filter(variable => inScope(variable, frame) && !(variable.location && variable.location[0] && variable.location[0][0] === 'addr'))
        .map(variable => ({ name: variable.name, kind: variable.kind, type: typeName(variable.type),
          ...valueOf(variable.type, evaluate(locationAt(variable.location, frame), frame, memory), memory, 0) }));
    }

    function globals(memory) {
      const out = (map.globals || []).map(item => ({ name: item.function ? `${item.function}::${item.name}` : item.name,
        type: typeName(item.type), ...valueOf(item.type, { address: at(item.address) }, memory, 0) }));
      if (!out.length) {
        // Handwritten assembly: data labels after the code, read as 32-bit words.
        for (const symbol of symbols) {
          if (symbol.address > codeEnd && symbol.kind !== 'function' && !symbol.name.startsWith('prg32_')) {
            const raw = readUnsigned(memory, at(symbol.address), 4);
            out.push({ name: symbol.name, type: 'word', address: at(symbol.address),
              text: raw === null ? 'not readable' : `${raw | 0} (${hex(raw)})`, unavailable: raw === null });
          }
        }
      }
      return out;
    }

    // --- watches and conditions ---------------------------------------------------------
    function findVariable(name, frame) {
      if (frame && frame.info) {
        const local = frame.info.variables.filter(v => v.name === name && inScope(v, frame)).pop();
        if (local) return { type: local.type, where: evaluate(locationAt(local.location, frame), frame, null) };
      }
      const global = (map.globals || []).find(item => item.name === name);
      if (global) return { type: global.type, where: { address: at(global.address) } };
      const symbol = symbols.find(item => item.name === name && item.address > codeEnd);
      if (symbol) return { type: null, where: { address: at(symbol.address) }, word: true };
      return null;
    }

    function watch(text, frame, memory) {
      const expression = String(text || '').trim();
      const parts = expression.match(/^([A-Za-z_]\w*)((?:\.[A-Za-z_]\w*|\[\s*-?\w+\s*\])*)$/);
      if (!parts) return { text: 'write a name, name.part or name[number]', error: true };
      const reg = registerNumber(parts[1]);
      if (!parts[2] && reg >= 0 && !findVariable(parts[1], frame)) {
        const value = frame && frame.registers ? frame.registers[reg] >>> 0 : null;
        return value === null ? { text: 'not known in this frame', error: true } : { text: `${value | 0} (${hex(value)})`, value };
      }
      const found = findVariable(parts[1], frame);
      if (!found) return { text: `no variable called ${parts[1]} here`, error: true };
      if (found.word) {
        const raw = readUnsigned(memory, found.where.address, 4);
        return raw === null ? { text: 'not readable', error: true } : { text: `${raw | 0} (${hex(raw)})`, value: raw | 0 };
      }
      let typeId = found.type;
      let where = found.where;
      if (where.register !== undefined && frame && frame.registers) where = { value: frame.registers[where.register], register: where.register };
      for (const step of parts[2].match(/\.[A-Za-z_]\w*|\[\s*-?\w+\s*\]/g) || []) {
        if (where.address === undefined) return { text: 'only variables in memory have parts', error: true };
        const type = resolve(typeId);
        if (step.startsWith('.')) {
          const member = type.kind === 'struct' && type.members.find(item => item.name === step.slice(1));
          if (!member) return { text: `no part called ${step.slice(1)}`, error: true };
          typeId = member.type;
          where = { address: where.address + member.offset };
        } else {
          const indexText = step.slice(1, -1).trim();
          const index = /^-?\d+$/.test(indexText) ? Number(indexText) : Number(watch(indexText, frame, memory).value);
          if (type.kind !== 'array' || !Number.isInteger(index) || index < 0 || (type.count && index >= type.count)) {
            return { text: `index ${indexText} is outside the list`, error: true };
          }
          typeId = type.target;
          where = { address: where.address + index * sizeOf(type.target) };
        }
      }
      const shown = valueOf(typeId, where, memory, 0);
      const number = shown.children ? NaN : parseInt(shown.text, 10);
      return { ...shown, value: Number.isNaN(number) ? undefined : number, error: !!shown.unavailable };
    }

    // "score > 10", "x == y", "lives <= 0". Returns {ok, value} or {ok: false, error}.
    function condition(text, frame, memory) {
      const match = String(text || '').match(/^\s*(.+?)\s*(==|!=|<=|>=|<|>)\s*(.+?)\s*$/);
      if (!match) return { ok: false, error: 'write a condition like  score > 10' };
      const side = part => (/^-?(?:0x[0-9a-f]+|\d+)$/i.test(part) ? Number(part) : watch(part, frame, memory).value);
      const left = side(match[1]);
      const right = side(match[3]);
      if (left === undefined || right === undefined || Number.isNaN(left) || Number.isNaN(right)) {
        return { ok: false, error: `cannot read ${left === undefined ? match[1] : match[3]}` };
      }
      const value = { '==': left === right, '!=': left !== right, '<': left < right, '<=': left <= right,
        '>': left > right, '>=': left >= right }[match[2]];
      return { ok: true, value };
    }

    return { ok: true, userFile, hasBlocks: entries.length > 0, lineAt, blockAt, blockOfLine, functionAt,
      breakpointForLine, breakpointForBlock, callStack, variables, globals, watch, condition, typeName };
  }

  // The counter CSRs from the core's debug state (ADR-0015), 64-bit values as numbers.
  function csrRows(state) {
    const csr = state && state.csr;
    if (!csr) return [];
    const join = (low, high) => high * 4294967296 + low;
    return [
      { name: 'cycle', number: '0xC00', value: join(csr.cycle, csr.cycleh), meaning: 'clock cycles (ESP32-C6 timing)' },
      { name: 'time', number: '0xC01', value: join(csr.time, csr.timeh), meaning: 'nanoseconds of game time' },
      { name: 'instret', number: '0xC02', value: join(csr.instret, csr.instreth), meaning: 'instructions finished' },
    ];
  }

  // The words around the stack pointer, top first: [{address, value, offset, isSp}].
  function stackRows(state, memory, count) {
    const sp = state.registers[2] >>> 0;
    const rows = [];
    for (let i = -2; i < (count || 16) - 2; i++) {
      const address = (sp + i * 4) >>> 0;
      const value = readUnsigned(memory, address, 4);
      if (value === null) continue;
      rows.push({ address, value, offset: i * 4, isSp: i === 0 });
    }
    return rows;
  }

  return { create, csrRows, stackRows, registerNumber, REGISTER_NAMES };
});
