window.PRG32Simulator = (function () {
  // Same rules as prg32_construction_kit/expressions.py and generator.py, so the simulator and the C agree.
  const W = 320;
  const H = 200;
  const MAX_LIST_SIZE = 1024;
  const MAX_REPEAT = 1024;

  const COLOR = {
    BLACK: 0x0000, WHITE: 0xFFFF, RED: 0xF800, GREEN: 0x07E0, BLUE: 0x001F, YELLOW: 0xFFE0, CYAN: 0x07FF,
    MAGENTA: 0xF81F, ORANGE: 0xFD20, PINK: 0xFE19, GRAY: 0x8410, DARK_GRAY: 0x4208, BROWN: 0xA145,
    PURPLE: 0x780F, NAVY: 0x000F, LIME: 0x87E0
  };
  const BUTTON_BITS = { LEFT: 1, RIGHT: 2, UP: 4, DOWN: 8, A: 16, B: 32, START: 64, SELECT: 64 };
  Object.keys(BUTTON_BITS).forEach(name => { BUTTON_BITS['P2_' + name] = BUTTON_BITS[name] << 8; });

  const CONSTANTS = {
    PRG32_GAME_W: 320, PRG32_GAME_H: 200, PRG32_SCREEN_W: 320, PRG32_SCREEN_H: 200, PRG32_LCD_W: 320, PRG32_LCD_H: 240,
    PRG32_TEXT_COLS: 40, PRG32_TEXT_ROWS: 25, PRG32_TILE_W: 8, PRG32_TILE_H: 8, PRG32_TILE_COLS: 40, PRG32_TILE_ROWS: 25,
    PRG32_PLAYFIELD_LAYERS: 2, PRG32_PLAYFIELD_COLS: 64, PRG32_PLAYFIELD_ROWS: 32
  };
  Object.keys(BUTTON_BITS).forEach(name => {
    const p2 = name.startsWith('P2_');
    CONSTANTS[(p2 ? 'PRG32_P2_BTN_' + name.slice(3) : 'PRG32_BTN_' + name)] = BUTTON_BITS[name];
  });
  Object.keys(COLOR).forEach(name => { CONSTANTS['PRG32_COLOR_' + name] = COLOR[name]; });

  const FUNCTIONS = { abs: 1, sign: 1, min: 2, max: 2, clamp: 3, sin: 1, cos: 1, rgb: 3, random: 2, frame: 0, tile: 3, peers: 0, peer_x: 1, peer_y: 1, peer_look: 1 };
  const FUNCTION_FEATURES = { tile: 'tilemap', peers: 'multiplayer', peer_x: 'multiplayer', peer_y: 'multiplayer', peer_look: 'multiplayer' };
  const SINE = [0, 4, 9, 13, 18, 22, 27, 31, 36, 40, 44, 49, 53, 58, 62, 66, 71, 75, 79, 83, 88, 92, 96, 100,
    104, 108, 112, 116, 120, 124, 128, 132, 136, 139, 143, 147, 150, 154, 158, 161, 165, 168, 171,
    175, 178, 181, 184, 187, 190, 193, 196, 199, 202, 204, 207, 210, 212, 215, 217, 219, 222, 224,
    226, 228, 230, 232, 234, 236, 237, 239, 241, 242, 243, 245, 246, 247, 248, 249, 250, 251, 252,
    253, 254, 254, 255, 255, 255, 256, 256, 256, 256];

  // The PRG32 firmware 8x8 font, characters 32..127, one byte per row, left pixel = high bit.
  const FONT = [
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x18,0x18,0x18,0x00,0x18,0x00,
    0x24,0x24,0x24,0x00,0x00,0x00,0x00,0x00,0x24,0x7e,0x24,0x24,0x7e,0x24,0x00,0x00,
    0x18,0x3e,0x58,0x3c,0x1a,0x7c,0x18,0x00,0x62,0x64,0x08,0x10,0x26,0x46,0x00,0x00,
    0x30,0x48,0x30,0x4a,0x44,0x3a,0x00,0x00,0x18,0x18,0x10,0x00,0x00,0x00,0x00,0x00,
    0x0c,0x10,0x20,0x20,0x20,0x10,0x0c,0x00,0x30,0x08,0x04,0x04,0x04,0x08,0x30,0x00,
    0x00,0x24,0x18,0x7e,0x18,0x24,0x00,0x00,0x00,0x18,0x18,0x7e,0x18,0x18,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x10,0x00,0x00,0x00,0x7e,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x18,0x18,0x00,0x02,0x04,0x08,0x10,0x20,0x40,0x00,0x00,
    0x3c,0x42,0x46,0x4a,0x52,0x62,0x3c,0x00,0x18,0x28,0x08,0x08,0x08,0x08,0x3e,0x00,
    0x3c,0x42,0x02,0x0c,0x30,0x40,0x7e,0x00,0x3c,0x42,0x02,0x1c,0x02,0x42,0x3c,0x00,
    0x0c,0x14,0x24,0x44,0x7e,0x04,0x04,0x00,0x7e,0x40,0x7c,0x02,0x02,0x42,0x3c,0x00,
    0x1c,0x20,0x40,0x7c,0x42,0x42,0x3c,0x00,0x7e,0x02,0x04,0x08,0x10,0x10,0x10,0x00,
    0x3c,0x42,0x42,0x3c,0x42,0x42,0x3c,0x00,0x3c,0x42,0x42,0x3e,0x02,0x04,0x38,0x00,
    0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x00,0x00,0x18,0x18,0x10,
    0x0c,0x10,0x20,0x40,0x20,0x10,0x0c,0x00,0x00,0x00,0x7e,0x00,0x7e,0x00,0x00,0x00,
    0x30,0x08,0x04,0x02,0x04,0x08,0x30,0x00,0x3c,0x42,0x02,0x0c,0x10,0x00,0x10,0x00,
    0x3c,0x42,0x5a,0x56,0x5e,0x40,0x3c,0x00,0x18,0x24,0x42,0x42,0x7e,0x42,0x42,0x00,
    0x7c,0x42,0x42,0x7c,0x42,0x42,0x7c,0x00,0x3c,0x42,0x40,0x40,0x40,0x42,0x3c,0x00,
    0x78,0x44,0x42,0x42,0x42,0x44,0x78,0x00,0x7e,0x40,0x40,0x78,0x40,0x40,0x7e,0x00,
    0x7e,0x40,0x40,0x78,0x40,0x40,0x40,0x00,0x3c,0x42,0x40,0x4e,0x42,0x42,0x3c,0x00,
    0x42,0x42,0x42,0x7e,0x42,0x42,0x42,0x00,0x3e,0x08,0x08,0x08,0x08,0x08,0x3e,0x00,
    0x1e,0x04,0x04,0x04,0x44,0x44,0x38,0x00,0x42,0x44,0x48,0x70,0x48,0x44,0x42,0x00,
    0x40,0x40,0x40,0x40,0x40,0x40,0x7e,0x00,0x42,0x66,0x5a,0x5a,0x42,0x42,0x42,0x00,
    0x42,0x62,0x52,0x4a,0x46,0x42,0x42,0x00,0x3c,0x42,0x42,0x42,0x42,0x42,0x3c,0x00,
    0x7c,0x42,0x42,0x7c,0x40,0x40,0x40,0x00,0x3c,0x42,0x42,0x42,0x4a,0x44,0x3a,0x00,
    0x7c,0x42,0x42,0x7c,0x48,0x44,0x42,0x00,0x3c,0x42,0x40,0x3c,0x02,0x42,0x3c,0x00,
    0x7e,0x08,0x08,0x08,0x08,0x08,0x08,0x00,0x42,0x42,0x42,0x42,0x42,0x42,0x3c,0x00,
    0x42,0x42,0x42,0x42,0x24,0x24,0x18,0x00,0x42,0x42,0x42,0x5a,0x5a,0x66,0x42,0x00,
    0x42,0x24,0x18,0x18,0x18,0x24,0x42,0x00,0x42,0x24,0x18,0x08,0x08,0x08,0x08,0x00,
    0x7e,0x02,0x04,0x18,0x20,0x40,0x7e,0x00,0x3c,0x20,0x20,0x20,0x20,0x20,0x3c,0x00,
    0x40,0x20,0x10,0x08,0x04,0x02,0x00,0x00,0x3c,0x04,0x04,0x04,0x04,0x04,0x3c,0x00,
    0x18,0x24,0x42,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x7e,0x00,
    0x20,0x10,0x08,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x3c,0x02,0x3e,0x42,0x3e,0x00,
    0x40,0x40,0x5c,0x62,0x42,0x62,0x5c,0x00,0x00,0x00,0x3c,0x42,0x40,0x42,0x3c,0x00,
    0x02,0x02,0x3a,0x46,0x42,0x46,0x3a,0x00,0x00,0x00,0x3c,0x42,0x7e,0x40,0x3c,0x00,
    0x0c,0x12,0x10,0x3c,0x10,0x10,0x10,0x00,0x00,0x00,0x3a,0x46,0x46,0x3a,0x02,0x3c,
    0x40,0x40,0x5c,0x62,0x42,0x42,0x42,0x00,0x08,0x00,0x18,0x08,0x08,0x08,0x1c,0x00,
    0x04,0x00,0x0c,0x04,0x04,0x44,0x44,0x38,0x40,0x40,0x44,0x48,0x70,0x48,0x44,0x00,
    0x18,0x08,0x08,0x08,0x08,0x08,0x1c,0x00,0x00,0x00,0x76,0x49,0x49,0x49,0x49,0x00,
    0x00,0x00,0x5c,0x62,0x42,0x42,0x42,0x00,0x00,0x00,0x3c,0x42,0x42,0x42,0x3c,0x00,
    0x00,0x00,0x5c,0x62,0x62,0x5c,0x40,0x40,0x00,0x00,0x3a,0x46,0x46,0x3a,0x02,0x02,
    0x00,0x00,0x5c,0x62,0x40,0x40,0x40,0x00,0x00,0x00,0x3e,0x40,0x3c,0x02,0x7c,0x00,
    0x10,0x10,0x7c,0x10,0x10,0x12,0x0c,0x00,0x00,0x00,0x42,0x42,0x42,0x46,0x3a,0x00,
    0x00,0x00,0x42,0x42,0x24,0x24,0x18,0x00,0x00,0x00,0x41,0x49,0x49,0x49,0x36,0x00,
    0x00,0x00,0x42,0x24,0x18,0x24,0x42,0x00,0x00,0x00,0x42,0x42,0x46,0x3a,0x02,0x3c,
    0x00,0x00,0x7e,0x04,0x18,0x20,0x7e,0x00,0x0e,0x10,0x10,0x60,0x10,0x10,0x0e,0x00,
    0x18,0x18,0x18,0x18,0x18,0x18,0x18,0x00,0x70,0x08,0x08,0x06,0x08,0x08,0x70,0x00,
    0x00,0x00,0x32,0x4c,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00
  ];

  const RESERVED = new Set(('auto break case char const continue default do double else enum extern float for goto if inline int long ' +
    'register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while bool true false asm input ' +
    'int8_t int16_t int32_t int64_t uint8_t uint16_t uint32_t uint64_t intptr_t uintptr_t size_t main').split(' '));
  // `name in object` would also find names such as `constructor` on every plain object.
  const has = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const BINARY = [['||'], ['&&'], ['|'], ['^'], ['&'], ['==', '!='], ['<', '>', '<=', '>='], ['<<', '>>'], ['+', '-'], ['*', '/', '%']];
  const TOKEN = /\s*(?:((?:0[xX][0-9A-Fa-f]+|[0-9]+)(?![A-Za-z0-9_]))|([A-Za-z_][A-Za-z0-9_]*)|(<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%()<>!&|^~\[\],]))/y;

  function saneIdentifier(name) {
    let out = String(name == null ? 'state' : name).trim().toLowerCase().replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!out) out = 'state';
    if (/^[0-9]/.test(out)) out = '_' + out;
    out = out.slice(0, 48);
    if (RESERVED.has(out) || out.startsWith('prg32_')) out += '_var';
    return out;
  }

  function tokenize(text) {
    const tokens = [];
    TOKEN.lastIndex = 0;
    while (TOKEN.lastIndex < text.length) {
      if (!text.slice(TOKEN.lastIndex).trim()) break;
      const start = TOKEN.lastIndex;
      const match = TOKEN.exec(text);
      if (!match || TOKEN.lastIndex === start) throw new Error('unexpected character');
      if (match[1] !== undefined) tokens.push({ kind: 'number', text: match[1] });
      else if (match[2] !== undefined) tokens.push({ kind: 'name', text: match[2] });
      else tokens.push({ kind: 'op', text: match[3] });
    }
    return tokens;
  }

  // Parse one expression into a small tree. `lists` maps list names to sizes.
  function parseTree(value, lists) {
    const text = String(value).trim();
    if (!text || text.length > 200 || /\/\*|\*\/|\/\//.test(text)) throw new Error('empty, too long, or a comment');
    const tokens = tokenize(text);
    const names = new Set();
    const features = new Set();
    let pos = 0;
    const peekOp = () => tokens[pos] && tokens[pos].kind === 'op' ? tokens[pos].text : null;
    const expect = op => { if (peekOp() !== op) throw new Error('expected ' + op); pos += 1; };
    function binary(level) {
      if (level >= BINARY.length) return unary();
      let left = binary(level + 1);
      while (BINARY[level].includes(peekOp())) {
        const op = tokens[pos++].text;
        left = { k: 'bin', op, left, right: binary(level + 1) };
      }
      return left;
    }
    function unary() {
      const op = peekOp();
      if (['-', '+', '!', '~'].includes(op)) { pos += 1; return { k: 'unary', op, arg: unary() }; }
      return primary();
    }
    function primary() {
      const token = tokens[pos++];
      if (!token) throw new Error('missing value');
      if (token.kind === 'number') {
        const v = /^0[xX]/.test(token.text) ? parseInt(token.text, 16) : parseInt(token.text, 10);
        if (v > 0x7FFFFFFF) throw new Error('number too large');
        return { k: 'num', text: token.text, value: v | 0 };
      }
      if (token.kind === 'name') return name(token.text);
      if (token.text === '(') { const inner = binary(0); expect(')'); return { k: 'paren', arg: inner }; }
      throw new Error('unexpected ' + token.text);
    }
    function name(text) {
      const after = peekOp();
      if (after === '(') {
        const fname = text.toLowerCase();
        if (!has(FUNCTIONS, fname)) throw new Error('unknown function ' + text);
        pos += 1;
        const args = [];
        if (peekOp() !== ')') {
          args.push(binary(0));
          while (peekOp() === ',') { pos += 1; args.push(binary(0)); }
        }
        expect(')');
        if (args.length !== FUNCTIONS[fname]) throw new Error(fname + ' needs ' + FUNCTIONS[fname] + ' values');
        if (FUNCTION_FEATURES[fname]) features.add(FUNCTION_FEATURES[fname]);
        return { k: 'call', name: fname, args };
      }
      if (text.startsWith('PRG32_')) {
        if (!has(CONSTANTS, text)) throw new Error('unknown constant ' + text);
        return { k: 'const', text, value: CONSTANTS[text] };
      }
      const id = saneIdentifier(text);
      if (after === '[') {
        if (!has(lists, id)) throw new Error(id + ' is not a list');
        pos += 1;
        const index = binary(0);
        expect(']');
        return { k: 'index', name: id, arg: index };
      }
      if (has(lists, id)) throw new Error(id + ' is a list');
      names.add(id);
      return { k: 'name', text: id };
    }
    const tree = binary(0);
    if (pos !== tokens.length) throw new Error('extra text');
    return { tree, names, features };
  }

  function render(node) {
    switch (node.k) {
      case 'num': case 'const': case 'name': return node.text;
      case 'paren': return '(' + render(node.arg) + ')';
      case 'unary': {
        const inner = render(node.arg);
        return node.op + (inner[0] === '-' || inner[0] === '+' ? ' ' : '') + inner;
      }
      case 'bin': return render(node.left) + ' ' + node.op + ' ' + render(node.right);
      case 'index': return node.name + '[' + render(node.arg) + ']';
      case 'call': return node.name + '(' + node.args.map(render).join(', ') + ')';
    }
    return '0';
  }

  function checkExpr(value, lists) {
    try { return render(parseTree(value, lists || {}).tree); } catch (_) { return null; }
  }

  function saneExpr(expr, fallback) {
    const value = expr == null || expr === '' ? fallback : expr;
    const checked = checkExpr(value, {});
    if (checked !== null) return checked;
    return fallback === undefined ? '0' : saneExpr(fallback);
  }

  // ---- C-style 32-bit integer evaluation (RISC-V rules for division by zero) ----
  function sinDeg(degrees) {
    let a = degrees % 360;
    if (a < 0) a += 360;
    if (a <= 90) return SINE[a];
    if (a <= 180) return SINE[180 - a];
    if (a <= 270) return -SINE[a - 180];
    return -SINE[360 - a];
  }

  function randomInt(low, high) {
    return high <= low ? low : (low + Math.floor(Math.random() * (high - low + 1))) | 0;
  }

  function evalNode(node, env) {
    switch (node.k) {
      case 'num': case 'const': return node.value;
      case 'name': return Number(env.state[node.text] || 0) | 0;
      case 'paren': return evalNode(node.arg, env);
      case 'index': {
        const list = env.lists[node.name];
        const i = evalNode(node.arg, env);
        return list && i >= 0 && i < list.length ? list[i] : 0;
      }
      case 'unary': {
        const v = evalNode(node.arg, env);
        return node.op === '-' ? -v | 0 : node.op === '+' ? v : node.op === '!' ? (v ? 0 : 1) : ~v;
      }
      case 'call': {
        const a = node.args.map(arg => evalNode(arg, env));
        switch (node.name) {
          case 'abs': return Math.abs(a[0]) | 0;
          case 'sign': return a[0] > 0 ? 1 : a[0] < 0 ? -1 : 0;
          case 'min': return Math.min(a[0], a[1]);
          case 'max': return Math.max(a[0], a[1]);
          case 'clamp': return a[0] < a[1] ? a[1] : a[0] > a[2] ? a[2] : a[0];
          case 'sin': return sinDeg(a[0]);
          case 'cos': return sinDeg((a[0] % 360) + 90);
          case 'rgb': {
            const c = v => Math.max(0, Math.min(255, v));
            return ((c(a[0]) & 0xF8) << 8) | ((c(a[1]) & 0xFC) << 3) | (c(a[2]) >> 3);
          }
          case 'random': return randomInt(a[0], a[1]);
          case 'frame': return env.frame | 0;
          case 'tile': return env.tile ? env.tile(a[0], a[1], a[2]) : 0;
          // The simulator is offline, like QEMU: no other players are connected.
          case 'peers': case 'peer_x': case 'peer_y': case 'peer_look': return 0;
        }
        return 0;
      }
    }
    if (node.op === '&&') return evalNode(node.left, env) && evalNode(node.right, env) ? 1 : 0;
    if (node.op === '||') return evalNode(node.left, env) || evalNode(node.right, env) ? 1 : 0;
    const a = evalNode(node.left, env), b = evalNode(node.right, env);
    switch (node.op) {
      case '+': return (a + b) | 0;
      case '-': return (a - b) | 0;
      case '*': return Math.imul(a, b);
      case '/': return b === 0 ? -1 : (a === -2147483648 && b === -1) ? a : (a / b) | 0;
      case '%': return b === 0 ? a : (a === -2147483648 && b === -1) ? 0 : (a % b) | 0;
      case '<<': return a << (b & 31);
      case '>>': return a >> (b & 31);
      case '&': return a & b;
      case '|': return a | b;
      case '^': return a ^ b;
      case '==': return a === b ? 1 : 0;
      case '!=': return a !== b ? 1 : 0;
      case '<': return a < b ? 1 : 0;
      case '>': return a > b ? 1 : 0;
      case '<=': return a <= b ? 1 : 0;
      case '>=': return a >= b ? 1 : 0;
    }
    return 0;
  }

  const treeCache = new Map();
  function cachedTree(text, lists) {
    const key = Object.keys(lists).join(',') + '|' + text;
    if (!treeCache.has(key)) {
      let tree = null;
      try { tree = parseTree(text, lists).tree; } catch (_) { tree = null; }
      if (treeCache.size > 5000) treeCache.clear();
      treeCache.set(key, tree);
    }
    return treeCache.get(key);
  }

  // Evaluate an expression. `env` may be a plain {name: value} state object.
  function evalExpr(expr, env) {
    const full = env && env.state ? env : { state: env || {}, lists: {}, frame: 0 };
    const listSizes = Object.create(null);
    Object.keys(full.lists || {}).forEach(name => { listSizes[name] = full.lists[name].length; });
    const tree = cachedTree(String(expr == null ? '0' : expr), listSizes);
    return tree ? evalNode(tree, full) : 0;
  }

  // ---- Blocks JSON -> game IR (mirrors generator.blocks_to_ir) ----
  function asBlocks(data) {
    if (!data) return [];
    if (data.blocks && Array.isArray(data.blocks.blocks)) return data.blocks.blocks;
    if (Array.isArray(data.blocks)) return data.blocks;
    if (data.type) return [data];
    return [];
  }

  function field(block, name, fallback) {
    const fields = block.fields || {};
    const value = Object.prototype.hasOwnProperty.call(fields, name) ? fields[name] : fallback;
    return value && typeof value === 'object' && 'value' in value ? value.value : value;
  }

  function child(block, name) {
    const inputs = block.inputs || {};
    const input = inputs[name] || (name === 'DO' ? inputs.STACK : null);
    return input && (input.block || input.shadow) || null;
  }

  function next(block) {
    return block && block.next && block.next.block ? block.next.block : null;
  }

  function stack(block) {
    const out = [];
    const seen = new Set();
    while (block && !seen.has(block)) {
      seen.add(block);
      out.push(block);
      block = next(block);
    }
    return out;
  }

  function allBlocks(blocks) {
    const out = [];
    const todo = blocks.slice();
    const seen = new Set();
    while (todo.length) {
      const block = todo.pop();
      if (!block || typeof block !== 'object' || seen.has(block)) continue;
      seen.add(block);
      out.push(block);
      if (next(block)) todo.push(next(block));
      Object.values(block.inputs || {}).forEach(input => {
        if (input && input.block) todo.push(input.block);
        if (input && input.shadow) todo.push(input.shadow);
      });
    }
    return out;
  }

  // Same rules as generator.c_int: a plain decimal number such as 10 or 2.5, else the fallback.
  function cInt(value, fallback) {
    const text = String(value).trim();
    if (!/^[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?$/.test(text)) return fallback;
    const n = Math.trunc(Number(text));
    return Number.isFinite(n) ? n : fallback;
  }

  // Same rules as generator.initial_value: a plain whole number such as -3 or 0x10, else 0.
  function initialValue(value) {
    const match = /^(-?)\s*(0[xX][0-9A-Fa-f]+|[0-9]+)$/.exec(String(value == null ? '' : value).trim());
    if (!match) return 0;
    const number = /^0[xX]/.test(match[2]) ? parseInt(match[2], 16) : parseInt(match[2], 10);
    if (number > 0x7FFFFFFF) return 0;
    return match[1] ? -number : number;
  }

  // Same rules as generator._text: the 8x8 font only has printable ASCII; other characters become '?'.
  function fontText(value, limit) {
    return Array.from(String(value)).slice(0, limit).map(ch => {
      const code = ch.codePointAt(0);
      return code >= 32 && code <= 126 ? ch : '?';
    }).join('');
  }

  function colorName(value, fallback) {
    let key = String(value || fallback || 'WHITE').toUpperCase().trim();
    if (key.startsWith('PRG32_COLOR_')) key = key.slice(12);
    return key in COLOR ? key : (fallback || 'WHITE');
  }

  function bitmapRows(block) {
    const rows = [];
    for (let r = 0; r < 8; r++) {
      const text = String(field(block, 'ROW' + r, '........')).slice(0, 8).padEnd(8, '.');
      let value = 0;
      for (let c = 0; c < 8; c++) if (!/[.\s0_-]/.test(text[c])) value |= 0x80 >> c;
      rows.push(value);
    }
    return rows;
  }

  function makeContext() {
    return {
      vars: Object.create(null), lists: Object.create(null), features: new Set(), warnings: [],
      ensureVar(raw, initial) {
        const name = saneIdentifier(raw);
        if (has(this.lists, name)) { this.warnings.push(name + ' is a list; use the list blocks to change it'); return null; }
        if (!has(this.vars, name)) this.vars[name] = initial || 0;
        return name;
      },
      ensureList(raw) {
        const name = saneIdentifier(raw);
        if (!has(this.lists, name)) { this.warnings.push('List ' + name + " is used but never made with a 'make list' block"); return null; }
        return name;
      },
      expr(value, fallback) {
        if (value == null || value === '') value = fallback;
        let parsed;
        try { parsed = parseTree(value, this.lists); } catch (_) {
          this.warnings.push('Replaced unsupported expression ' + JSON.stringify(String(value).slice(0, 40)) + ' with ' + fallback);
          parsed = parseTree(saneExpr(fallback, '0'), this.lists);
        }
        parsed.names.forEach(name => { if (!has(this.vars, name)) this.vars[name] = 0; });
        parsed.features.forEach(feature => this.features.add(feature));
        return render(parsed.tree);
      }
    };
  }

  function parseStack(block, ctx) {
    return stack(block).map(b => parseStatement(b, ctx)).filter(Boolean);
  }

  function parseStatement(block, ctx) {
    const type = block.type;
    const f = (name, fallback) => ctx.expr(field(block, name, fallback), fallback);
    const text = (name, fallback, limit) => fontText(field(block, name, fallback), limit || 64);
    if (['prg32_set_state', 'prg32_change_state', 'prg32_clamp_state', 'prg32_random_state', 'prg32_wrap_state'].includes(type)) {
      const initial = type === 'prg32_set_state' ? initialValue(field(block, 'VALUE', 0)) : 0;
      const name = ctx.ensureVar(field(block, 'VAR', 'score'), initial);
      if (name === null) return { op: 'comment', text: 'skipped: ' + type + ' cannot change a list' };
      if (type === 'prg32_set_state') return { op: 'set', var: name, value: f('VALUE', 0) };
      if (type === 'prg32_change_state') return { op: 'change', var: name, delta: f('DELTA', 1) };
      const op = { prg32_clamp_state: 'clamp', prg32_random_state: 'random', prg32_wrap_state: 'wrap' }[type];
      const high = op === 'random' ? 304 : op === 'wrap' ? 319 : 320;
      return { op, var: name, low: f('LOW', 0), high: f('HIGH', high) };
    }
    if (type === 'prg32_if' || type === 'prg32_if_else') {
      const stmt = { op: 'if', cond: f('COND', 0), then: parseStack(child(block, 'DO'), ctx) };
      if (type === 'prg32_if_else') stmt.else = parseStack(child(block, 'ELSE'), ctx);
      return stmt;
    }
    if (type === 'prg32_repeat') {
      const name = ctx.ensureVar(field(block, 'VAR', 'i'), 0);
      if (name === null) return { op: 'comment', text: 'skipped: a repeat block cannot count with a list' };
      return { op: 'repeat', var: name, from: f('FROM', 0), to: f('TO', 9), body: parseStack(child(block, 'DO'), ctx) };
    }
    if (type === 'prg32_list_create') return { op: 'list_fill', list: saneIdentifier(field(block, 'LIST', 'items')), value: f('VALUE', 0) };
    if (type === 'prg32_list_set' || type === 'prg32_list_change') {
      const name = ctx.ensureList(field(block, 'LIST', 'items'));
      if (name === null) return { op: 'comment', text: 'skipped: unknown list' };
      if (type === 'prg32_list_set') return { op: 'list_set', list: name, index: f('INDEX', 0), value: f('VALUE', 0) };
      return { op: 'list_change', list: name, index: f('INDEX', 0), delta: f('DELTA', 1) };
    }
    if (type === 'prg32_if_button' || type === 'prg32_if_button_once') {
      let button = String(field(block, 'BUTTON', 'A')).toUpperCase();
      if (!has(BUTTON_BITS, button)) button = 'A';
      return { op: type === 'prg32_if_button' ? 'if_button' : 'if_button_once', button, then: parseStack(child(block, 'DO'), ctx) };
    }
    if (type === 'prg32_if_touching') {
      ctx.features.add('sprites');
      const stmt = { op: 'if_touching' };
      [['AX', 'player_x'], ['AY', 'player_y'], ['AW', 16], ['AH', 16], ['BX', 'enemy_x'], ['BY', 'enemy_y'], ['BW', 16], ['BH', 16]]
        .forEach(([key, fallback]) => { stmt[key.toLowerCase()] = f(key, fallback); });
      stmt.then = parseStack(child(block, 'DO'), ctx);
      return stmt;
    }
    const color = (name, fallback) => colorName(field(block, name, fallback || 'WHITE'), fallback || 'WHITE');
    if (type === 'prg32_clear_screen') return { op: 'clear', color: color('COLOR', 'BLACK') };
    if (type === 'prg32_draw_rect' || type === 'prg32_draw_frame') return { op: type === 'prg32_draw_rect' ? 'rect' : 'frame', x: f('X', 0), y: f('Y', 0), w: f('W', 16), h: f('H', 16), color: color('COLOR') };
    if (type === 'prg32_draw_rect_rgb') return { op: 'rect_rgb', x: f('X', 0), y: f('Y', 0), w: f('W', 16), h: f('H', 16), rgb: f('RGB', '0xFFFF') };
    if (type === 'prg32_draw_pixel') return { op: 'pixel', x: f('X', 0), y: f('Y', 0), color: color('COLOR') };
    if (type === 'prg32_draw_line') return { op: 'line', x1: f('X1', 0), y1: f('Y1', 0), x2: f('X2', 16), y2: f('Y2', 16), color: color('COLOR') };
    if (type === 'prg32_draw_circle') return { op: 'circle', x: f('X', 160), y: f('Y', 100), r: f('R', 8), color: color('COLOR'), fill: String(field(block, 'FILL', 'OUTLINE')).toUpperCase() === 'FILLED' };
    if (type === 'prg32_draw_bitmap') return { op: 'bitmap', rows: bitmapRows(block), x: f('X', 0), y: f('Y', 0), color: color('COLOR'), scale: f('SCALE', 1) };
    if (type === 'prg32_draw_sprite8') { ctx.features.add('sprites'); return { op: 'sprite8', rows: bitmapRows(block), x: f('X', 0), y: f('Y', 0), fg: color('FG'), bg: color('BG', 'BLACK') }; }
    if (type === 'prg32_draw_pixel_indexed') return { op: 'pixel_indexed', x: f('X', 0), y: f('Y', 0), index: f('INDEX', 1) };
    if (type === 'prg32_draw_rect_indexed') return { op: 'rect_indexed', x: f('X', 0), y: f('Y', 0), index: f('INDEX', 1), w: f('W', 16), h: f('H', 16) };
    if (type === 'prg32_palette_set') return { op: 'palette_set', index: f('INDEX', 1), color: color('COLOR') };
    if (type === 'prg32_clear_indexed') return { op: 'clear_indexed', index: f('INDEX', 0) };
    if (type === 'prg32_draw_text') return { op: 'text', x: f('X', 0), y: f('Y', 0), text: text('TEXT', 'HELLO'), fg: color('FG'), bg: color('BG', 'BLACK') };
    if (type === 'prg32_draw_number') return { op: 'number', value: f('VALUE', 'score'), x: f('X', 0), y: f('Y', 0), fg: color('FG'), bg: color('BG', 'BLACK') };
    if (type === 'prg32_tile_define') { ctx.features.add('tilemap'); return { op: 'tile_define', id: f('ID', 1), rows: bitmapRows(block), fg: color('FG'), bg: color('BG', 'BLACK') }; }
    if (type === 'prg32_playfield_clear') { ctx.features.add('tilemap'); return { op: 'playfield_clear', layer: f('LAYER', 0), id: f('ID', 0) }; }
    if (type === 'prg32_playfield_put') { ctx.features.add('tilemap'); return { op: 'playfield_put', layer: f('LAYER', 0), tx: f('TX', 0), ty: f('TY', 0), id: f('ID', 1) }; }
    if (type === 'prg32_playfield_scroll') { ctx.features.add('tilemap'); return { op: 'playfield_scroll', layer: f('LAYER', 0), x: f('X', 0), y: f('Y', 0) }; }
    if (type === 'prg32_playfield_camera') { ctx.features.add('tilemap'); return { op: 'playfield_camera', x: f('X', 0), y: f('Y', 0) }; }
    if (type === 'prg32_playfield_draw') { ctx.features.add('tilemap'); return { op: 'playfield_draw', layer: f('LAYER', 0), transparent: String(field(block, 'TRANSPARENT', 'OPAQUE')).toUpperCase() === 'TRANSPARENT' }; }
    if (type === 'prg32_play_beep') { ctx.features.add('audio'); return { op: 'beep', freq: f('FREQ', 880), ms: f('MS', 80) }; }
    if (type === 'prg32_audio_note') { ctx.features.add('audio'); return { op: 'note', note: f('NOTE', 60), channel: f('CHANNEL', 0), ms: f('MS', 250) }; }
    if (type === 'prg32_audio_stop') { ctx.features.add('audio'); return { op: 'note_off', channel: f('CHANNEL', 0) }; }
    if (type === 'prg32_audio_volume') { ctx.features.add('audio'); return { op: 'volume', volume: f('VOLUME', 200) }; }
    // AudioStudio blocks: names become fixed numbers from the project's document (as on the server).
    if (type === 'prg32_sound_effect' || type === 'prg32_soundtrack_play') {
      ctx.features.add('audio');
      const audio = ctx.audio || { effects: [], soundtracks: [] };
      if (type === 'prg32_sound_effect') {
        const name = String(field(block, 'EFFECT', '')).slice(0, 32);
        const index = (audio.effects || []).findIndex(item => item.name === name);
        if (index < 0) { ctx.warnings.push(`The sound effect '${name}' is not in this project's AudioStudio`); return { op: 'comment', text: `skipped: no sound effect named ${name}` }; }
        const effect = audio.effects[index];
        return { op: 'sfx', name, voice: effect.voice, instrument: 8 + index, note: effect.note, volume: effect.volume, ms: effect.duration_ms };
      }
      const name = String(field(block, 'TRACK', '')).slice(0, 32);
      const index = (audio.soundtracks || []).findIndex(item => item.name === name);
      if (index < 0) { ctx.warnings.push(`The soundtrack '${name}' is not in this project's AudioStudio`); return { op: 'comment', text: `skipped: no soundtrack named ${name}` }; }
      return { op: 'track_play', name, track: index };
    }
    if (type === 'prg32_soundtrack_stop') { ctx.features.add('audio'); return { op: 'track_stop' }; }
    if (type === 'prg32_sound_stop_all') { ctx.features.add('audio'); return { op: 'sound_stop_all' }; }
    // Sprite Lab and Backgrounds (docs/project_art.md): the picture itself goes into the IR, as on the server.
    if (type === 'prg32_draw_project_sprite') {
      ctx.features.add('sprites');
      const wanted = String(field(block, 'SPRITE', ''));
      const entry = ctx.artEntry('sprites', wanted);
      if (!entry) return { op: 'comment', text: 'skipped: no sprite named ' + wanted.slice(0, 64) };
      return { op: 'sprite_draw', sprite: entry.name, name: entry.title, x: f('X', 0), y: f('Y', 0) };
    }
    if (type === 'prg32_background_load' || type === 'prg32_background_draw') {
      ctx.features.add('tilemap');
      const wanted = String(field(block, 'BACKGROUND', ''));
      const entry = ctx.artEntry('backgrounds', wanted);
      if (!entry) return { op: 'comment', text: 'skipped: no background named ' + wanted.slice(0, 64) };
      if (type === 'prg32_background_load' && entry.tiles.some(tile => tile.flags.length)) ctx.features.add('platformer');
      return { op: type === 'prg32_background_load' ? 'background_load' : 'background_draw', background: entry.name, name: entry.title };
    }
    if (type === 'prg32_band_text') {
      const stmt = { op: 'band', text: text('TEXT', 'SCORE', 24) };
      const value = field(block, 'VALUE', '');
      if (String(value).trim()) stmt.value = ctx.expr(value, 0);
      return stmt;
    }
    if (type === 'prg32_score_submit') return { op: 'score_submit', value: f('VALUE', 'score') };
    if (type === 'prg32_scoreboard_show') return { op: 'scoreboard', title: text('TITLE', 'HIGH SCORES', 32) };
    if (type === 'prg32_splash') return { op: 'splash', title: text('TITLE', 'MY GAME', 32), subtitle: text('SUBTITLE', 'PRESS START', 32), ms: f('MS', 1500), bg: color('BG', 'BLACK'), fg: color('FG'), accent: color('ACCENT', 'YELLOW') };
    if (type === 'prg32_player_name') return { op: 'player_name' };
    if (type === 'prg32_mp_join') { ctx.features.add('multiplayer'); return { op: 'mp_join' }; }
    if (type === 'prg32_mp_share') { ctx.features.add('multiplayer'); return { op: 'mp_share', x: f('X', 'player_x'), y: f('Y', 'player_y'), look: f('LOOK', 0) }; }
    if (type === 'prg32_comment') return { op: 'comment', text: String(field(block, 'TEXT', 'comment')) };
    ctx.warnings.push('Skipped unsupported block type: ' + String(type).slice(0, 40));
    return { op: 'comment', text: 'Unsupported block ' + String(type).slice(0, 40) };
  }

  // The project's AudioStudio document (docs/audio_studio.md): sound effect and soundtrack
  // blocks name its sounds, and become the same fixed numbers as in the generated C.
  let audioDocument = null;
  function setAudio(document) { audioDocument = document || null; }

  // The project's art (project_assets.catalog, from /api/projects/<id>/art): sprites and backgrounds by name.
  let artCatalog = null;
  function setArt(catalog) { artCatalog = catalog || null; }
  function findArt(entries, wanted) {
    return (entries || []).find(entry => entry.title === wanted) || (entries || []).find(entry => entry.name === wanted) || null;
  }

  // The MIDI note nearest to a frequency, from C3 (48) to C6 (84): prg32_kit_note_from_hz in the generated C.
  const NOTE_HZ = [131, 139, 147, 156, 165, 175, 185, 196, 208, 220, 233, 247,
    262, 277, 294, 311, 330, 349, 370, 392, 415, 440, 466, 494,
    523, 554, 587, 622, 659, 698, 740, 784, 831, 880, 932, 988, 1047];
  function noteFromHz(hz) {
    if (hz <= NOTE_HZ[0]) return 48;
    for (let index = 0; index < 36; index += 1) {
      if (hz < Math.trunc((NOTE_HZ[index] + NOTE_HZ[index + 1]) / 2)) return 48 + index;
    }
    return 84;
  }

  function compileBlocks(data) {
    const ctx = makeContext();
    ctx.audio = audioDocument;
    const usedArt = { sprites: new Set(), backgrounds: new Set() };
    ctx.artEntry = (kind, wanted) => {
      const entry = findArt((artCatalog || {})[kind], wanted);
      if (!entry) { ctx.warnings.push(`The ${kind === 'sprites' ? 'sprite' : 'background'} '${wanted.slice(0, 64)}' is not in this project`); return null; }
      usedArt[kind].add(entry.name);
      return entry;
    };
    const ir = { abi: 'prg32-construction-kit-game-1.1', state: [], lists: [], required_features: [], init: [], update: [], draw: [], warnings: ctx.warnings };
    const tops = asBlocks(data);
    allBlocks(tops).forEach(block => {
      if (block.type !== 'prg32_list_create') return;
      const name = saneIdentifier(field(block, 'LIST', 'items'));
      const size = Math.max(1, Math.min(MAX_LIST_SIZE, cInt(field(block, 'SIZE', 10), 10)));
      if (has(ctx.lists, name) && ctx.lists[name] !== size) ctx.warnings.push('List ' + name + ' is made twice with different sizes; using the larger one');
      ctx.lists[name] = Math.max(size, ctx.lists[name] || 0);
    });
    tops.forEach(top => {
      if (top.type === 'prg32_on_start') ir.init.push(...parseStack(child(top, 'DO'), ctx));
      else if (top.type === 'prg32_update') ir.update.push(...parseStack(child(top, 'DO'), ctx));
      else if (top.type === 'prg32_draw') ir.draw.push(...parseStack(child(top, 'DO'), ctx));
      else if (top.type) {
        const stmt = parseStatement(top, ctx);
        if (stmt) ir.update.push(stmt);
      }
    });
    if (Object.keys(ctx.vars).length === 0 && Object.keys(ctx.lists).length === 0) ctx.vars = { player_x: 150, player_y: 180, score: 0 };
    if (ir.draw.length === 0) {
      if (!has(ctx.vars, 'player_x')) ctx.vars.player_x = 150;
      if (!has(ctx.vars, 'player_y')) ctx.vars.player_y = 180;
      ir.draw = [{ op: 'clear', color: 'BLACK' }, { op: 'rect', x: 'player_x', y: 'player_y', w: '16', h: '16', color: 'YELLOW' },
        { op: 'text', x: '8', y: '8', text: 'PRG32', fg: 'GREEN', bg: 'BLACK' }];
    }
    ir.state = Object.entries(ctx.vars).map(([name, initial]) => ({ name, type: 'int', initial }));
    ir.lists = Object.entries(ctx.lists).map(([name, size]) => ({ name, size }));
    ir.required_features = Array.from(ctx.features).sort();
    if (usedArt.sprites.size || usedArt.backgrounds.size) {
      ir.assets = { sprites: ((artCatalog || {}).sprites || []).filter(entry => usedArt.sprites.has(entry.name)),
                    backgrounds: ((artCatalog || {}).backgrounds || []).filter(entry => usedArt.backgrounds.has(entry.name)) };
    }
    return ir;
  }

  // '#rrggbb' as RGB565, like generator._rgb565.
  function rgb565Of(hex) {
    const value = parseInt(String(hex).slice(1), 16) || 0;
    return (((value >> 16) & 0xF8) << 8) | (((value >> 8) & 0xFC) << 3) | ((value & 0xFF) >> 3);
  }

  // ---- The simulated PRG32: a 320x200 RGB565 framebuffer drawn the way the firmware draws ----
  function toRgb(c) {
    return [((c >> 11) & 31) * 255 / 31 | 0, ((c >> 5) & 63) * 255 / 63 | 0, (c & 31) * 255 / 31 | 0];
  }

  function defaultPalette() {
    const palette = new Uint16Array(256);
    for (let i = 0; i < 256; i++) {
      if (i < 16) palette[i] = 0;
      else if (i < 232) {
        const v = i - 16, r = Math.floor(v / 36), g = Math.floor(v / 6) % 6, b = v % 6;
        palette[i] = (Math.floor(r * 31 / 5) << 11) | (Math.floor(g * 63 / 5) << 5) | Math.floor(b * 31 / 5);
      } else {
        const gray = Math.floor((i - 232) * 255 / 23);
        palette[i] = (Math.floor(gray * 31 / 255) << 11) | (Math.floor(gray * 63 / 255) << 5) | Math.floor(gray * 31 / 255);
      }
    }
    [COLOR.BLACK, COLOR.WHITE, COLOR.RED, COLOR.GREEN, COLOR.BLUE, COLOR.YELLOW, COLOR.CYAN, COLOR.MAGENTA].forEach((c, i) => { palette[i] = c; });
    return palette;
  }

  class Simulator {
    constructor(canvas, debugElement) {
      this.canvas = canvas;
      this.ctx = canvas ? canvas.getContext('2d') : null;
      this.image = this.ctx ? this.ctx.createImageData(W, H) : null;
      this.debugElement = debugElement;
      this.keys = {};
      this.ir = compileBlocks({});
      this.running = false;
      this.frame = 0;
      this.audio = null;
      this.band = '';
      this.inputSources = {};
      this.latched = {};
      this.fb = new Uint16Array(W * H);
      this.frameMs = 1000 / 30; // PRG32 firmware paces games at about 30 frames per second.
      if (typeof window !== 'undefined' && window.addEventListener && canvas) {
        this.bindKeys();
        this.bindGamepad();
      }
      this.reset();
    }

    setInput(button, source, down) {
      if (!this.inputSources[button]) this.inputSources[button] = new Set();
      const sources = this.inputSources[button];
      if (down) {
        sources.add(source);
        this.latched[button] = true; // a tap shorter than one frame is still seen once
      } else sources.delete(source);
      this.keys[button] = sources.size > 0;
    }

    inputMask() {
      let mask = 0;
      Object.keys(BUTTON_BITS).forEach(name => { if (this.keys[name] || this.latched[name]) mask |= BUTTON_BITS[name]; });
      return mask;
    }

    bindKeys() {
      const map = {
        ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', ArrowUp: 'UP', ArrowDown: 'DOWN', z: 'A', Z: 'A', x: 'B', X: 'B', Enter: 'START', Shift: 'SELECT',
        j: 'P2_LEFT', l: 'P2_RIGHT', i: 'P2_UP', k: 'P2_DOWN', u: 'P2_A', o: 'P2_B'
      };
      // Game keys only while the game screen has the focus (or nothing has it). Otherwise Enter and
      // the arrow keys belong to the page: buttons, menus, lists and editors must keep working.
      const set = (event, down) => {
        const target = event.target;
        if (target && target !== this.canvas && target !== document.body && target !== document.documentElement) return;
        if (map[event.key]) {
          this.setInput(map[event.key], 'keyboard-' + event.code, down);
          event.preventDefault();
        }
      };
      window.addEventListener('keydown', event => set(event, true));
      window.addEventListener('keyup', event => set(event, false));
      window.addEventListener('blur', () => {
        Object.keys(this.inputSources).forEach(button => {
          Array.from(this.inputSources[button]).filter(source => source.startsWith('keyboard-')).forEach(source => this.setInput(button, source, false));
        });
      });
    }

    bindGamepad() {
      document.querySelectorAll('[data-game-button]').forEach(button => {
        const gameButton = button.dataset.gameButton;
        const source = pointerId => 'pointer-' + pointerId;
        const release = event => {
          this.setInput(gameButton, source(event.pointerId), false);
          button.classList.remove('is-pressed');
        };
        button.addEventListener('pointerdown', event => {
          event.preventDefault();
          button.setPointerCapture(event.pointerId);
          this.setInput(gameButton, source(event.pointerId), true);
          button.classList.add('is-pressed');
        });
        button.addEventListener('pointerup', release);
        button.addEventListener('pointercancel', release);
        button.addEventListener('lostpointercapture', release);
        button.addEventListener('contextmenu', event => event.preventDefault());
      });
    }

    loadBlocks(blocks) {
      this.ir = compileBlocks(blocks);
      this.reset();
      return this.ir;
    }

    reset() {
      this.state = Object.create(null);
      this.lists = Object.create(null);
      this.palette = defaultPalette();
      this.tiles = Array.from({ length: 256 }, () => ({ rows: [0, 0, 0, 0, 0, 0, 0, 0], fg: 0, bg: 0 }));
      this.playfield = [new Uint8Array(32 * 64), new Uint8Array(32 * 64)];
      this.scroll = [[0, 0], [0, 0]];
      this.camera = [0, 0];
      this.band = '';
      this.waitUntil = 0;
      this.fb.fill(0);
      (this.ir.state || []).forEach(item => { this.state[item.name] = Number(item.initial || 0) | 0; });
      (this.ir.lists || []).forEach(item => { this.lists[item.name] = new Int32Array(item.size); });
      this.frame = 0;
      this.previousInput = this.inputMask();
      this.sound('stop');   // a reset leaves no note sounding
      this.env = { state: this.state, lists: this.lists, frame: 0, tile: (l, x, y) => this.tileAt(l, x, y) };
      this.exec(this.ir.init || [], 0);
      this.drawFrame();
      this.report('Reset');
    }

    play() {
      if (this.running) return;
      this.running = true;
      this.sound('resume');   // browsers allow sound only after a click: Play is that click
      let last = performance.now();
      let carry = 0;
      const tick = now => {
        if (!this.running) return;
        carry = Math.min(carry + now - last, this.frameMs * 4);
        last = now;
        while (carry >= this.frameMs) {
          carry -= this.frameMs;
          if (now >= this.waitUntil) this.step(false);
        }
        this.present();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }

    stop() { this.running = false; this.sound('stop'); }   // Pause silences the game, like the Player

    toggle() {
      this.running ? this.stop() : this.play();
      // Playing moves the keyboard focus to the screen, so the game keys reach the game.
      if (this.running && this.canvas && this.canvas.focus) this.canvas.focus({ preventScroll: true });
      return this.running;
    }

    // One PRG32 frame: update, then draw.
    step(present) {
      this.input = this.inputMask();
      this.latched = {};
      this.env.frame = this.frame;
      this.exec(this.ir.update || [], 0);
      this.previousInput = this.input;
      this.frame += 1;
      this.env.frame = this.frame;
      this.exec(this.ir.draw || [], 0);
      if (present !== false) this.present();
      this.report('Frame ' + this.frame);
    }

    drawFrame() {
      this.env.frame = this.frame;
      this.exec(this.ir.draw || [], 0);
      this.present();
    }

    value(expr) { return evalExpr(expr, this.env); }

    exec(statements, depth) {
      for (const stmt of statements) this.run(stmt, depth);
    }

    run(stmt, depth) {
      const v = expr => this.value(expr);
      const op = stmt.op;
      if (op === 'set') this.state[stmt.var] = v(stmt.value);
      else if (op === 'change') this.state[stmt.var] = ((this.state[stmt.var] | 0) + v(stmt.delta)) | 0;
      else if (op === 'clamp') {
        let low = v(stmt.low);
        if (this.state[stmt.var] < low) this.state[stmt.var] = low;
        const high = v(stmt.high);
        if (this.state[stmt.var] > high) this.state[stmt.var] = high;
      } else if (op === 'wrap') {
        const low = v(stmt.low), high = v(stmt.high);
        if (this.state[stmt.var] < low) this.state[stmt.var] = (this.state[stmt.var] + (high - low + 1)) | 0;
        else if (this.state[stmt.var] > high) this.state[stmt.var] = (this.state[stmt.var] - (high - low + 1)) | 0;
      } else if (op === 'random') this.state[stmt.var] = randomInt(v(stmt.low), v(stmt.high));
      else if (op === 'if') {
        if (v(stmt.cond)) this.exec(stmt.then || [], depth);
        else if (stmt.else) this.exec(stmt.else, depth);
      } else if (op === 'repeat') {
        const last = v(stmt.to);
        let count = 0;
        for (let k = v(stmt.from); k <= last && count < MAX_REPEAT; k++, count++) {
          this.state[stmt.var] = k;
          this.exec(stmt.body || [], depth + 1);
        }
      } else if (op === 'list_fill') {
        if (this.lists[stmt.list]) this.lists[stmt.list].fill(v(stmt.value));
      } else if (op === 'list_set' || op === 'list_change') {
        const list = this.lists[stmt.list];
        const index = v(stmt.index);
        const value = op === 'list_set' ? v(stmt.value) : null;
        if (list && index >= 0 && index < list.length) {
          list[index] = op === 'list_set' ? value : (list[index] + v(stmt.delta)) | 0;
        }
      } else if (op === 'if_button') {
        if (this.input & BUTTON_BITS[stmt.button]) this.exec(stmt.then || [], depth);
      } else if (op === 'if_button_once') {
        const bit = BUTTON_BITS[stmt.button];
        if ((this.input & bit) && !(this.previousInput & bit)) this.exec(stmt.then || [], depth);
      } else if (op === 'if_touching') {
        const [ax, ay, aw, ah, bx, by, bw, bh] = ['ax', 'ay', 'aw', 'ah', 'bx', 'by', 'bw', 'bh'].map(k => v(stmt[k]));
        if (aw > 0 && ah > 0 && bw > 0 && bh > 0 && ax + aw > bx && bx + bw > ax && ay + ah > by && by + bh > ay) this.exec(stmt.then || [], depth);
      } else if (op === 'clear') this.fb.fill(COLOR[stmt.color] || 0);
      else if (op === 'rect') this.rect(v(stmt.x), v(stmt.y), v(stmt.w), v(stmt.h), COLOR[stmt.color]);
      else if (op === 'rect_rgb') this.rect(v(stmt.x), v(stmt.y), v(stmt.w), v(stmt.h), v(stmt.rgb) & 0xFFFF);
      else if (op === 'frame') {
        const x = v(stmt.x), y = v(stmt.y), w = v(stmt.w), h = v(stmt.h), c = COLOR[stmt.color];
        if (w > 0 && h > 0) { this.rect(x, y, w, 1, c); this.rect(x, y + h - 1, w, 1, c); this.rect(x, y, 1, h, c); this.rect(x + w - 1, y, 1, h, c); }
      } else if (op === 'pixel') this.pixel(v(stmt.x), v(stmt.y), COLOR[stmt.color]);
      else if (op === 'line') this.line(v(stmt.x1), v(stmt.y1), v(stmt.x2), v(stmt.y2), COLOR[stmt.color]);
      else if (op === 'circle') this.circle(v(stmt.x), v(stmt.y), v(stmt.r), COLOR[stmt.color], stmt.fill);
      else if (op === 'bitmap') this.bitmap(v(stmt.x), v(stmt.y), stmt.rows, COLOR[stmt.color], v(stmt.scale));
      else if (op === 'sprite8') this.sprite8(v(stmt.x), v(stmt.y), stmt.rows, COLOR[stmt.fg], COLOR[stmt.bg]);
      else if (op === 'palette_set') this.palette[v(stmt.index) & 255] = COLOR[stmt.color];
      else if (op === 'clear_indexed') this.fb.fill(this.palette[v(stmt.index) & 255]);
      else if (op === 'rect_indexed') this.rect(v(stmt.x), v(stmt.y), v(stmt.w), v(stmt.h), this.palette[v(stmt.index) & 255]);
      else if (op === 'pixel_indexed') this.pixel(v(stmt.x), v(stmt.y), this.palette[v(stmt.index) & 255]);
      else if (op === 'text') this.text(v(stmt.x), v(stmt.y), String(stmt.text || ''), COLOR[stmt.fg], COLOR[stmt.bg]);
      else if (op === 'number') this.text(v(stmt.x), v(stmt.y), String(v(stmt.value)), COLOR[stmt.fg], COLOR[stmt.bg]);
      else if (op === 'tile_define') {
        this.tiles[v(stmt.id) & 255] = { rows: stmt.rows.slice(), fg: COLOR[stmt.fg], bg: COLOR[stmt.bg] };
      } else if (op === 'playfield_clear') {
        const layer = v(stmt.layer) & 255;
        if (layer < 2) { this.playfield[layer].fill(v(stmt.id) & 255); this.scroll[layer] = [0, 0]; }
      } else if (op === 'playfield_put') {
        const layer = v(stmt.layer) & 255, tx = v(stmt.tx) & 255, ty = v(stmt.ty) & 255;
        if (layer < 2 && tx < 64 && ty < 32) this.playfield[layer][ty * 64 + tx] = v(stmt.id) & 255;
      } else if (op === 'playfield_scroll') {
        const layer = v(stmt.layer) & 255;
        if (layer < 2) this.scroll[layer] = [v(stmt.x), v(stmt.y)];
      } else if (op === 'playfield_camera') this.camera = [v(stmt.x), v(stmt.y)];
      else if (op === 'playfield_draw') this.drawPlayfield(v(stmt.layer) & 255, stmt.transparent);
      else if (op === 'sprite_draw') this.drawSprite(stmt.sprite, v(stmt.x), v(stmt.y));
      else if (op === 'background_load') this.loadBackground(stmt.background);
      else if (op === 'background_draw') {
        const background = this.art('backgrounds', stmt.background);
        this.drawPlayfield(0, false);
        if (background && background.layers.length > 1) this.drawPlayfield(1, true);
      }
      else if (op === 'beep') this.sound('note', 0, 0, noteFromHz(v(stmt.freq)), 255, v(stmt.ms));
      else if (op === 'note') this.sound('note', v(stmt.channel) & 7, 0, v(stmt.note) & 127, 255, v(stmt.ms));
      else if (op === 'note_off') this.sound('noteOff', v(stmt.channel) & 7);
      else if (op === 'volume') this.sound('master', v(stmt.volume) & 255);
      else if (op === 'sfx') this.sound('note', stmt.voice, stmt.instrument, stmt.note, stmt.volume, stmt.ms);
      else if (op === 'track_play') this.sound('playTrack', stmt.track);
      else if (op === 'track_stop') this.sound('stopTrack');
      else if (op === 'sound_stop_all') this.sound('stop');
      else if (op === 'band') this.band = stmt.text + ('value' in stmt ? ' ' + v(stmt.value) : '');
      else if (op === 'score_submit') this.band = 'Score submitted: ' + v(stmt.value);
      else if (op === 'player_name') this.band = 'PRG32 asks for the player name here';
      else if (op === 'mp_join') this.band = 'Multiplayer: offline in the simulator (0 peers)';
      else if (op === 'splash') {
        this.fb.fill(COLOR[stmt.bg]);
        this.rect(0, 92, W, 2, COLOR[stmt.accent]);
        this.text(Math.max(0, 160 - stmt.title.length * 4), 76, stmt.title, COLOR[stmt.fg], COLOR[stmt.bg]);
        this.text(Math.max(0, 160 - stmt.subtitle.length * 4), 104, stmt.subtitle, COLOR[stmt.accent], COLOR[stmt.bg]);
        this.present();
        this.waitUntil = (typeof performance !== 'undefined' ? performance.now() : 0) + Math.max(0, Math.min(10000, v(stmt.ms)));
      }
    }

    art(kind, name) {
      return (((this.ir && this.ir.assets) || {})[kind] || []).find(entry => entry.name === name) || null;
    }

    // <name>_draw(x, y): every pixel that is not see-through, as prg32_sprite_draw_frame draws it.
    drawSprite(name, x, y) {
      const sprite = this.art('sprites', name);
      if (!sprite) return;
      sprite.pixels.forEach((row, py) => row.forEach((color, px) => {
        if (color !== 'transparent') this.pixel(x + px, y + py, rgb565Of(color));
      }));
    }

    // <name>_load(): define the tiles, then fill each layer with the map (prg32_tile_define, prg32_playfield_put).
    loadBackground(name) {
      const background = this.art('backgrounds', name);
      if (!background) return;
      background.tiles.forEach(tile => { this.tiles[tile.id] = { rows: tile.rows.slice(), fg: rgb565Of(tile.fg), bg: rgb565Of(tile.bg) }; });
      background.layers.forEach((layer, number) => {
        this.playfield[number].fill(0);
        this.scroll[number] = [0, 0];
        layer.forEach((row, ty) => row.forEach((id, tx) => { this.playfield[number][ty * 64 + tx] = id & 255; }));
      });
    }

    tileAt(layer, tx, ty) {
      if (layer < 0 || tx < 0 || ty < 0 || layer > 255 || tx > 255 || ty > 255) return 0;
      if (layer >= 2 || tx >= 64 || ty >= 32) return 0;
      return this.playfield[layer][ty * 64 + tx];
    }

    pixel(x, y, c) {
      if (x >= 0 && x < W && y >= 0 && y < H) this.fb[y * W + x] = c;
    }

    rect(x, y, w, h, c) {
      if (x < 0) { w += x; x = 0; }
      if (y < 0) { h += y; y = 0; }
      if (x + w > W) w = W - x;
      if (y + h > H) h = H - y;
      if (w <= 0 || h <= 0) return;
      for (let py = y; py < y + h; py++) this.fb.fill(c, py * W + x, py * W + x + w);
    }

    text(x, y, s, fg, bg) {
      for (const ch of s) {
        let code = ch.charCodeAt(0);
        if (code < 32 || code > 126) code = 63;
        const base = (code - 32) * 8;
        for (let row = 0; row < 8; row++) {
          const bits = FONT[base + row];
          for (let col = 0; col < 8; col++) this.pixel(x + col, y + row, (bits & (0x80 >> col)) ? fg : bg);
        }
        x += 8;
      }
    }

    line(x1, y1, x2, y2, c) {
      const dx = Math.abs(x2 - x1), dy = -Math.abs(y2 - y1), sx = x1 < x2 ? 1 : -1, sy = y1 < y2 ? 1 : -1;
      let error = dx + dy, steps = 0;
      while (steps++ < 2048) {
        this.pixel(x1, y1, c);
        if (x1 === x2 && y1 === y2) break;
        const twice = 2 * error;
        if (twice >= dy) { error += dy; x1 += sx; }
        if (twice <= dx) { error += dx; y1 += sy; }
      }
    }

    circle(cx, cy, r, c, filled) {
      if (r < 0) return;
      if (r > 200) r = 200;
      let x = r, y = 0, error = 1 - r;
      while (x >= y) {
        if (filled) {
          this.rect(cx - x, cy + y, 2 * x + 1, 1, c); this.rect(cx - x, cy - y, 2 * x + 1, 1, c);
          this.rect(cx - y, cy + x, 2 * y + 1, 1, c); this.rect(cx - y, cy - x, 2 * y + 1, 1, c);
        } else {
          [[x, y], [-x, y], [x, -y], [-x, -y], [y, x], [-y, x], [y, -x], [-y, -x]].forEach(([px, py]) => this.pixel(cx + px, cy + py, c));
        }
        y++;
        if (error < 0) error += 2 * y + 1;
        else { x--; error += 2 * (y - x) + 1; }
      }
    }

    bitmap(x, y, rows, c, scale) {
      scale = Math.max(1, Math.min(8, scale));
      for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) if (rows[row] & (0x80 >> col)) this.rect(x + col * scale, y + row * scale, scale, scale, c);
      }
    }

    sprite8(x, y, rows, fg, bg) {
      for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) this.pixel(x + col, y + row, (rows[row] & (0x80 >> col)) ? fg : bg);
      }
    }

    drawPlayfield(layer, transparentZero) {
      if (layer >= 2) return;
      const floorDiv = (value, d) => value >= 0 ? Math.floor(value / d) : -Math.floor((-value + d - 1) / d);
      const wrap = (value, limit) => ((value % limit) + limit) % limit;
      const ox = this.scroll[layer][0] + this.camera[0], oy = this.scroll[layer][1] + this.camera[1];
      const stx = floorDiv(ox, 8), sty = floorDiv(oy, 8);
      const offx = ox - stx * 8, offy = oy - sty * 8;
      for (let sy = -offy, row = 0; sy < H; sy += 8, row++) {
        const my = wrap(sty + row, 32);
        for (let sx = -offx, col = 0; sx < W; sx += 8, col++) {
          const id = this.playfield[layer][my * 64 + wrap(stx + col, 64)];
          if (transparentZero && id === 0) continue;
          const tile = this.tiles[id];
          this.rect(sx, sy, 8, 8, tile.bg);
          if (tile.fg === tile.bg) continue;
          for (let r = 0; r < 8; r++) {
            for (let c = 0; c < 8; c++) if (tile.rows[r] & (0x80 >> c)) this.pixel(sx + c, sy + r, tile.fg);
          }
        }
      }
    }

    present() {
      if (!this.ctx) return;
      const data = this.image.data;
      for (let i = 0; i < W * H; i++) {
        const c = this.fb[i];
        data[i * 4] = ((c >> 11) & 31) * 255 / 31;
        data[i * 4 + 1] = ((c >> 5) & 63) * 255 / 63;
        data[i * 4 + 2] = (c & 31) * 255 / 31;
        data[i * 4 + 3] = 255;
      }
      this.ctx.putImageData(this.image, 0, 0);
    }

    // Sound goes to the PRG32 sound engine the page gives it (window.PRG32AudioEngine, the
    // same engine as the Player, ADR-0021); without one the preview is silent.
    sound(method, ...args) {
      const engine = this.audioEngine;
      if (!engine || !engine.core) return;
      try { engine[method](...args); } catch (_) { /* a sound must never stop the game */ }
    }

    report(prefix) {
      if (!this.debugElement) return;
      const compact = Object.entries(this.state).slice(0, 8).map(([k, v]) => `${k}=${v}`).join('  ');
      this.debugElement.textContent = `${prefix}: ${compact}` + (this.band ? `  |  band: ${this.band}` : '');
    }
  }

  return { compileBlocks, setAudio, setArt, noteFromHz, evalExpr, saneExpr, checkExpr, toRgb, COLOR, FONT, Simulator };
})();
