window.PRG32Simulator = (function () {
  const COLOR = {
    BLACK: '#000000', WHITE: '#ffffff', RED: '#ef4444', GREEN: '#22c55e', BLUE: '#2563eb',
    YELLOW: '#fde047', CYAN: '#22d3ee', MAGENTA: '#d946ef', ORANGE: '#f97316', PINK: '#ec4899'
  };

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
    const input = inputs[name] || inputs.DO || inputs.STACK;
    return input && (input.block || input.shadow) || null;
  }

  function next(block) {
    return block && block.next && block.next.block ? block.next.block : null;
  }

  function stack(block) {
    const out = [];
    const seen = new Set();
    while (block && !seen.has(block.id || block)) {
      seen.add(block.id || block);
      out.push(block);
      block = next(block);
    }
    return out;
  }

  // Same rules as prg32_construction_kit/generator.py, so the simulator and the C agree.
  const RESERVED = new Set(('auto break case char const continue default do double else enum extern float for goto if inline int long ' +
    'register restrict return short signed sizeof static struct switch typedef union unsigned void volatile while bool true false asm input').split(' '));
  const TOKEN = /\s*(?:((?:0[xX][0-9A-Fa-f]+|[0-9]+)(?![A-Za-z0-9_]))|([A-Za-z_][A-Za-z0-9_]*)|(<<|>>|<=|>=|==|!=|&&|\|\||[-+*/%()<>!&|^~]))/y;

  function saneIdentifier(name) {
    let out = String(name || 'state').trim().toLowerCase().replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!out) out = 'state';
    if (/^[0-9]/.test(out)) out = '_' + out;
    out = out.slice(0, 48);
    if (RESERVED.has(out) || out.startsWith('prg32_')) out += '_var';
    return out;
  }

  // Split an expression into tokens; returns null when it uses anything outside the Blocks language.
  function tokenize(expr) {
    const text = String(expr).trim();
    if (!text || text.length > 200 || /\/\*|\*\/|\/\//.test(text)) return null;
    const tokens = [];
    let depth = 0;
    TOKEN.lastIndex = 0;
    while (TOKEN.lastIndex < text.length) {
      const start = TOKEN.lastIndex;
      const match = TOKEN.exec(text);
      if (!match || TOKEN.lastIndex === start) return null;
      const raw = match[1] !== undefined ? match[1] : match[2] !== undefined ? match[2] : match[3];
      const lead = match[0].slice(0, match[0].length - raw.length);
      let token;
      if (match[1] !== undefined) token = { kind: 'number', text: raw, value: /^0[xX]/.test(raw) ? parseInt(raw, 16) : parseInt(raw, 10) };
      else if (match[2] !== undefined) token = { kind: 'name', text: raw.startsWith('PRG32_') ? raw : saneIdentifier(raw) };
      else {
        token = { kind: 'op', text: raw };
        if (raw === '(') {
          const prev = tokens[tokens.length - 1];
          if (prev && prev.kind !== 'op') return null; // no function calls
          depth += 1;
        } else if (raw === ')' && --depth < 0) return null;
      }
      token.lead = lead;
      tokens.push(token);
    }
    return depth === 0 ? tokens : null;
  }

  function saneExpr(expr, fallback) {
    const value = expr == null || expr === '' ? fallback : expr;
    const tokens = tokenize(value);
    if (tokens) return tokens.map(t => t.lead + t.text).join('');
    return fallback === undefined ? '0' : saneExpr(fallback);
  }

  // A tiny C-style integer expression interpreter: no eval(), 32-bit ints, division truncates like C.
  const BINARY = [['||'], ['&&'], ['|'], ['^'], ['&'], ['==', '!='], ['<', '>', '<=', '>='], ['<<', '>>'], ['+', '-'], ['*', '/', '%']];
  const exprCache = new Map();

  function parseExpr(text) {
    const tokens = tokenize(text);
    if (!tokens || !tokens.length) return null;
    let pos = 0;
    const peek = () => tokens[pos] && tokens[pos].kind === 'op' ? tokens[pos].text : null;
    function primary() {
      const token = tokens[pos++];
      if (!token) throw new Error('missing value');
      if (token.kind === 'number') return { num: token.value | 0 };
      if (token.kind === 'name') return { name: token.text };
      if (token.text === '(') {
        const inner = binary(0);
        if (peek() !== ')') throw new Error('missing )');
        pos += 1;
        return inner;
      }
      if (['-', '+', '!', '~'].includes(token.text)) return { unary: token.text, arg: primary() };
      throw new Error('unexpected ' + token.text);
    }
    function binary(level) {
      if (level >= BINARY.length) return primary();
      let left = binary(level + 1);
      while (BINARY[level].includes(peek())) {
        const op = tokens[pos++].text;
        left = { op, left, right: binary(level + 1) };
      }
      return left;
    }
    const tree = binary(0);
    if (pos !== tokens.length) throw new Error('extra text');
    return tree;
  }

  function evalNode(node, state) {
    if ('num' in node) return node.num;
    if ('name' in node) return Number(state[node.name] || 0) | 0;
    if ('unary' in node) {
      const v = evalNode(node.arg, state);
      return node.unary === '-' ? -v | 0 : node.unary === '+' ? v : node.unary === '!' ? (v ? 0 : 1) : ~v;
    }
    if (node.op === '&&') return evalNode(node.left, state) && evalNode(node.right, state) ? 1 : 0;
    if (node.op === '||') return evalNode(node.left, state) || evalNode(node.right, state) ? 1 : 0;
    const a = evalNode(node.left, state), b = evalNode(node.right, state);
    switch (node.op) {
      case '+': return (a + b) | 0;
      case '-': return (a - b) | 0;
      case '*': return Math.imul(a, b);
      case '/': return b === 0 ? 0 : Math.trunc(a / b) | 0;
      case '%': return b === 0 ? 0 : (a % b) | 0;
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

  function parseStack(block, ctx) {
    return stack(block).map(b => parseStatement(b, ctx)).filter(Boolean);
  }

  function ensureVar(ctx, raw, initial) {
    const name = saneIdentifier(raw);
    if (!(name in ctx.vars)) ctx.vars[name] = Math.trunc(Number(initial)) || 0;
    return name;
  }

  function parseStatement(block, ctx) {
    const type = block.type;
    if (type === 'prg32_set_state') {
      const name = ensureVar(ctx, field(block, 'VAR', 'score'), Number(field(block, 'VALUE', 0)));
      return { op: 'set', var: name, value: saneExpr(field(block, 'VALUE', 0), 0) };
    }
    if (type === 'prg32_change_state') {
      const name = ensureVar(ctx, field(block, 'VAR', 'score'), 0);
      return { op: 'change', var: name, delta: saneExpr(field(block, 'DELTA', 1), 1) };
    }
    if (type === 'prg32_clamp_state') {
      const name = ensureVar(ctx, field(block, 'VAR', 'x'), 0);
      return { op: 'clamp', var: name, low: saneExpr(field(block, 'LOW', 0), 0), high: saneExpr(field(block, 'HIGH', 320), 320) };
    }
    if (type === 'prg32_random_state') {
      const name = ensureVar(ctx, field(block, 'VAR', 'target_x'), 0);
      return { op: 'random', var: name, low: saneExpr(field(block, 'LOW', 0), 0), high: saneExpr(field(block, 'HIGH', 304), 304) };
    }
    if (type === 'prg32_if_button') {
      return { op: 'if_button', button: String(field(block, 'BUTTON', 'A')).toUpperCase(), then: parseStack(child(block, 'DO'), ctx) };
    }
    if (type === 'prg32_if_touching') {
      return {
        op: 'if_touching', ax: saneExpr(field(block, 'AX', 'player_x'), 'player_x'), ay: saneExpr(field(block, 'AY', 'player_y'), 'player_y'), aw: saneExpr(field(block, 'AW', 16), 16), ah: saneExpr(field(block, 'AH', 16), 16),
        bx: saneExpr(field(block, 'BX', 'enemy_x'), 'enemy_x'), by: saneExpr(field(block, 'BY', 'enemy_y'), 'enemy_y'), bw: saneExpr(field(block, 'BW', 16), 16), bh: saneExpr(field(block, 'BH', 16), 16), then: parseStack(child(block, 'DO'), ctx)
      };
    }
    if (type === 'prg32_clear_screen') return { op: 'clear', color: String(field(block, 'COLOR', 'BLACK')).toUpperCase() };
    if (type === 'prg32_draw_rect') return { op: 'rect', x: saneExpr(field(block, 'X', 0), 0), y: saneExpr(field(block, 'Y', 0), 0), w: saneExpr(field(block, 'W', 16), 16), h: saneExpr(field(block, 'H', 16), 16), color: String(field(block, 'COLOR', 'WHITE')).toUpperCase() };
    if (type === 'prg32_draw_pixel') return { op: 'pixel', x: saneExpr(field(block, 'X', 0), 0), y: saneExpr(field(block, 'Y', 0), 0), color: String(field(block, 'COLOR', 'WHITE')).toUpperCase() };
    if (type === 'prg32_palette_set') return { op: 'palette_set', index: saneExpr(field(block, 'INDEX', 1), 1), color: String(field(block, 'COLOR', 'WHITE')).toUpperCase() };
    if (type === 'prg32_clear_indexed') return { op: 'clear_indexed', index: saneExpr(field(block, 'INDEX', 0), 0) };
    if (type === 'prg32_draw_rect_indexed') return { op: 'rect_indexed', x: saneExpr(field(block, 'X', 0), 0), y: saneExpr(field(block, 'Y', 0), 0), w: saneExpr(field(block, 'W', 16), 16), h: saneExpr(field(block, 'H', 16), 16), index: saneExpr(field(block, 'INDEX', 1), 1) };
    if (type === 'prg32_draw_pixel_indexed') return { op: 'pixel_indexed', x: saneExpr(field(block, 'X', 0), 0), y: saneExpr(field(block, 'Y', 0), 0), index: saneExpr(field(block, 'INDEX', 1), 1) };
    if (type === 'prg32_draw_text') return { op: 'text', text: String(field(block, 'TEXT', 'HELLO')), x: saneExpr(field(block, 'X', 8), 8), y: saneExpr(field(block, 'Y', 8), 8), fg: String(field(block, 'FG', 'WHITE')).toUpperCase(), bg: String(field(block, 'BG', 'BLACK')).toUpperCase() };
    if (type === 'prg32_play_beep') return { op: 'beep', freq: saneExpr(field(block, 'FREQ', 880), 880), ms: saneExpr(field(block, 'MS', 80), 80) };
    if (type === 'prg32_audio_note') return { op: 'note', note: saneExpr(field(block, 'NOTE', 60), 60), channel: saneExpr(field(block, 'CHANNEL', 0), 0), ms: saneExpr(field(block, 'MS', 250), 250) };
    if (type === 'prg32_comment') return { op: 'comment', text: String(field(block, 'TEXT', 'comment')) };
    ctx.warnings.push('Skipped unsupported block type: ' + type);
    return null;
  }

  function compileBlocks(data) {
    const ctx = { vars: {}, warnings: [] };
    const ir = { abi: 'prg32-construction-kit-game-1.0', state: [], init: [], update: [], draw: [], warnings: ctx.warnings };
    asBlocks(data).forEach(top => {
      if (top.type === 'prg32_on_start') ir.init.push(...parseStack(child(top, 'DO'), ctx));
      else if (top.type === 'prg32_update') ir.update.push(...parseStack(child(top, 'DO'), ctx));
      else if (top.type === 'prg32_draw') ir.draw.push(...parseStack(child(top, 'DO'), ctx));
      else {
        const stmt = parseStatement(top, ctx);
        if (stmt) ir.update.push(stmt);
      }
    });
    if (Object.keys(ctx.vars).length === 0) ctx.vars = { player_x: 150, player_y: 180, score: 0 };
    if (ir.draw.length === 0) {
      if (!('player_x' in ctx.vars)) ctx.vars.player_x = 150;
      if (!('player_y' in ctx.vars)) ctx.vars.player_y = 180;
      ir.draw = [{ op: 'clear', color: 'BLACK' }, { op: 'rect', x: 'player_x', y: 'player_y', w: '16', h: '16', color: 'YELLOW' }];
    }
    ir.state = Object.entries(ctx.vars).map(([name, initial]) => ({ name, type: 'int', initial }));
    return ir;
  }

  function evalExpr(expr, state) {
    const text = String(expr == null ? '0' : expr);
    if (!exprCache.has(text)) {
      let tree = null;
      try { tree = parseExpr(text); } catch (_) { tree = null; }
      if (exprCache.size > 2000) exprCache.clear();
      exprCache.set(text, tree);
    }
    const tree = exprCache.get(text);
    return tree ? evalNode(tree, state) : 0;
  }

  function hit(ax, ay, aw, ah, bx, by, bw, bh) {
    return ax < bx + bw && ax + aw > bx && ay < by + bh && ay + ah > by;
  }

  class Simulator {
    constructor(canvas, debugElement) {
      this.canvas = canvas;
      this.ctx = canvas.getContext('2d');
      this.debugElement = debugElement;
      this.keys = {};
      this.ir = compileBlocks({});
      this.state = {};
      this.running = false;
      this.frame = 0;
      this.audio = null;
      this.inputSources = {};
      this.bindKeys();
      this.bindGamepad();
      this.reset();
    }

    setInput(button, source, down) {
      if (!this.inputSources[button]) this.inputSources[button] = new Set();
      const sources = this.inputSources[button];
      if (down) sources.add(source);
      else sources.delete(source);
      this.keys[button] = sources.size > 0;
    }

    bindKeys() {
      const set = (event, down) => {
        const map = { ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', ArrowUp: 'UP', ArrowDown: 'DOWN', z: 'A', Z: 'A', x: 'B', X: 'B', Enter: 'START', Shift: 'SELECT' };
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
      this.state = {};
      this.palette = { 0: COLOR.BLACK, 1: COLOR.WHITE };
      this.ir.state.forEach(item => { this.state[item.name] = Number(item.initial || 0); });
      this.frame = 0;
      this.exec(this.ir.init || []);
      this.draw();
      this.report('Reset');
    }

    play() {
      if (this.running) return;
      this.running = true;
      const tick = () => {
        if (!this.running) return;
        this.step();
        requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }

    stop() {
      this.running = false;
    }

    toggle() {
      this.running ? this.stop() : this.play();
      return this.running;
    }

    step() {
      this.exec(this.ir.update || []);
      this.draw();
      this.frame += 1;
      this.report('Frame ' + this.frame);
    }

    // Runs logic and drawing blocks alike, in order, just like the generated C functions.
    exec(statements) {
      const ctx = this.ctx;
      const value = expr => evalExpr(expr, this.state);
      const paletteColor = expr => this.palette[value(expr) & 255] || COLOR.BLACK;
      ctx.imageSmoothingEnabled = false;
      statements.forEach(stmt => {
        if (stmt.op === 'set') this.state[stmt.var] = value(stmt.value);
        else if (stmt.op === 'change') this.state[stmt.var] = (Number(this.state[stmt.var] || 0) + value(stmt.delta)) | 0;
        else if (stmt.op === 'clamp') {
          const current = Number(this.state[stmt.var] || 0);
          const low = value(stmt.low), high = value(stmt.high);
          this.state[stmt.var] = current < low ? low : current > high ? high : current;
        } else if (stmt.op === 'random') {
          const low = Math.max(0, value(stmt.low));
          const high = Math.max(0, value(stmt.high));
          this.state[stmt.var] = high <= low ? low : low + Math.floor(Math.random() * (high - low + 1));
        } else if (stmt.op === 'palette_set') this.palette[value(stmt.index) & 255] = COLOR[stmt.color] || COLOR.WHITE;
        else if (stmt.op === 'if_button') { if (this.keys[stmt.button]) this.exec(stmt.then || []); }
        else if (stmt.op === 'if_touching') {
          const values = ['ax', 'ay', 'aw', 'ah', 'bx', 'by', 'bw', 'bh'].map(k => value(stmt[k]));
          if (hit(...values)) this.exec(stmt.then || []);
        } else if (stmt.op === 'beep') this.beep(value(stmt.freq), value(stmt.ms));
        else if (stmt.op === 'note') this.beep(440 * Math.pow(2, (value(stmt.note) - 69) / 12), value(stmt.ms));
        else if (stmt.op === 'clear') {
          ctx.fillStyle = COLOR[stmt.color] || '#000';
          ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        } else if (stmt.op === 'rect') {
          ctx.fillStyle = COLOR[stmt.color] || '#fff';
          ctx.fillRect(value(stmt.x), value(stmt.y), value(stmt.w), value(stmt.h));
        } else if (stmt.op === 'pixel') {
          ctx.fillStyle = COLOR[stmt.color] || COLOR.WHITE;
          ctx.fillRect(value(stmt.x), value(stmt.y), 1, 1);
        } else if (stmt.op === 'clear_indexed') {
          ctx.fillStyle = paletteColor(stmt.index);
          ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        } else if (stmt.op === 'rect_indexed' || stmt.op === 'pixel_indexed') {
          const pixel = stmt.op === 'pixel_indexed';
          ctx.fillStyle = paletteColor(stmt.index);
          ctx.fillRect(value(stmt.x), value(stmt.y), pixel ? 1 : value(stmt.w), pixel ? 1 : value(stmt.h));
        } else if (stmt.op === 'text') {
          const text = String(stmt.text || '');
          const x = value(stmt.x), y = value(stmt.y);
          ctx.fillStyle = COLOR[stmt.bg] || '#000';
          ctx.fillRect(x - 1, y - 1, text.length * 8 + 2, 11);
          ctx.fillStyle = COLOR[stmt.fg] || '#fff';
          ctx.font = '8px monospace';
          ctx.textBaseline = 'top';
          ctx.fillText(text, x, y);
        }
      });
    }

    draw() {
      this.exec(this.ir.draw || []);
    }

    beep(freq, ms) {
      try {
        this.audio = this.audio || new (window.AudioContext || window.webkitAudioContext)();
        const osc = this.audio.createOscillator();
        const gain = this.audio.createGain();
        osc.frequency.value = Math.max(40, Math.min(5000, freq));
        gain.gain.value = 0.04;
        osc.connect(gain).connect(this.audio.destination);
        osc.start();
        osc.stop(this.audio.currentTime + Math.max(0.02, Math.min(0.5, ms / 1000)));
      } catch (_) {}
    }

    report(prefix) {
      if (!this.debugElement) return;
      const compact = Object.entries(this.state).slice(0, 8).map(([k, v]) => `${k}=${Math.round(v)}`).join('  ');
      this.debugElement.textContent = `${prefix}: ${compact}`;
    }
  }

  return { compileBlocks, evalExpr, saneExpr, Simulator };
})();
