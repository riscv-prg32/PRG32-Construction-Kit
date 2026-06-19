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

  function saneIdentifier(name) {
    let out = String(name || 'state').trim().toLowerCase().replace(/[^a-zA-Z0-9_]+/g, '_').replace(/^_+|_+$/g, '');
    if (!out) out = 'state';
    if (/^[0-9]/.test(out)) out = '_' + out;
    return out;
  }

  function saneExpr(expr, fallback) {
    const value = String(expr == null || expr === '' ? fallback : expr).trim();
    return /^[A-Za-z0-9_\s+\-*/%()<>!=&|]+$/.test(value) ? value : String(fallback || 0);
  }

  function parseStack(block, ctx) {
    return stack(block).map(b => parseStatement(b, ctx)).filter(Boolean);
  }

  function ensureVar(ctx, raw, initial) {
    const name = saneIdentifier(raw);
    if (!(name in ctx.vars)) ctx.vars[name] = Number(initial || 0);
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
    if (type === 'prg32_draw_text') return { op: 'text', text: String(field(block, 'TEXT', 'HELLO')), x: saneExpr(field(block, 'X', 8), 8), y: saneExpr(field(block, 'Y', 8), 8), fg: String(field(block, 'FG', 'WHITE')).toUpperCase(), bg: String(field(block, 'BG', 'BLACK')).toUpperCase() };
    if (type === 'prg32_play_beep') return { op: 'beep', freq: saneExpr(field(block, 'FREQ', 880), 880), ms: saneExpr(field(block, 'MS', 80), 80) };
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
    ir.state = Object.entries(ctx.vars).map(([name, initial]) => ({ name, type: 'int', initial }));
    if (ir.draw.length === 0) ir.draw = [{ op: 'clear', color: 'BLACK' }, { op: 'rect', x: 'player_x', y: 'player_y', w: '16', h: '16', color: 'YELLOW' }];
    return ir;
  }

  function evalExpr(expr, state) {
    const text = saneExpr(expr, 0);
    try {
      const names = Object.keys(state);
      const values = names.map(name => state[name]);
      const fn = new Function(...names, '"use strict"; return Number(' + text + ');');
      const result = fn(...values);
      return Number.isFinite(result) ? result : 0;
    } catch (_) {
      return 0;
    }
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
      this.bindKeys();
      this.reset();
    }

    bindKeys() {
      const set = (event, down) => {
        const map = { ArrowLeft: 'LEFT', ArrowRight: 'RIGHT', ArrowUp: 'UP', ArrowDown: 'DOWN', z: 'A', Z: 'A', x: 'B', X: 'B', Enter: 'START', Shift: 'SELECT' };
        if (map[event.key]) {
          this.keys[map[event.key]] = down;
          event.preventDefault();
        }
      };
      window.addEventListener('keydown', event => set(event, true));
      window.addEventListener('keyup', event => set(event, false));
    }

    loadBlocks(blocks) {
      this.ir = compileBlocks(blocks);
      this.reset();
      return this.ir;
    }

    reset() {
      this.state = {};
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

    exec(statements) {
      statements.forEach(stmt => {
        if (stmt.op === 'set') this.state[stmt.var] = evalExpr(stmt.value, this.state);
        else if (stmt.op === 'change') this.state[stmt.var] = Number(this.state[stmt.var] || 0) + evalExpr(stmt.delta, this.state);
        else if (stmt.op === 'clamp') this.state[stmt.var] = Math.max(evalExpr(stmt.low, this.state), Math.min(evalExpr(stmt.high, this.state), Number(this.state[stmt.var] || 0)));
        else if (stmt.op === 'if_button' && this.keys[stmt.button]) this.exec(stmt.then || []);
        else if (stmt.op === 'if_touching') {
          const values = ['ax', 'ay', 'aw', 'ah', 'bx', 'by', 'bw', 'bh'].map(k => evalExpr(stmt[k], this.state));
          if (hit(...values)) this.exec(stmt.then || []);
        } else if (stmt.op === 'beep') this.beep(evalExpr(stmt.freq, this.state), evalExpr(stmt.ms, this.state));
      });
    }

    draw() {
      const ctx = this.ctx;
      ctx.imageSmoothingEnabled = false;
      (this.ir.draw || []).forEach(stmt => {
        if (stmt.op === 'clear') {
          ctx.fillStyle = COLOR[stmt.color] || '#000';
          ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        } else if (stmt.op === 'rect') {
          ctx.fillStyle = COLOR[stmt.color] || '#fff';
          ctx.fillRect(evalExpr(stmt.x, this.state), evalExpr(stmt.y, this.state), evalExpr(stmt.w, this.state), evalExpr(stmt.h, this.state));
        } else if (stmt.op === 'text') {
          ctx.fillStyle = COLOR[stmt.bg] || '#000';
          const x = evalExpr(stmt.x, this.state), y = evalExpr(stmt.y, this.state);
          ctx.fillRect(x - 1, y - 1, stmt.text.length * 8 + 2, 11);
          ctx.fillStyle = COLOR[stmt.fg] || '#fff';
          ctx.font = '8px monospace';
          ctx.textBaseline = 'top';
          ctx.fillText(stmt.text, x, y);
        }
      });
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

  return { compileBlocks, Simulator };
})();
