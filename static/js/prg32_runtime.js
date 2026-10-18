// Runs real PRG32 cartridges (.prg32) in the browser.
//
// The cartridge's RISC-V code is interpreted by the PRG32-QT core compiled to
// WebAssembly (static/wasm/prg32-core.wasm, see docs/wasm_runtime.md). This file
// is only the "host": it draws the 320 x 200 picture on a canvas, turns keys into
// PRG32 buttons, keeps time, and plays the sounds the cartridge asks for.
//
// Guest time and wall time are different things here: the cartridge always sees
// 33 ms per frame (the PRG32 console's frame period); the speed setting only
// changes how many of those frames run per real second.
//
// The debugger (docs/wasm_runtime.md, ADR-0006) uses PRG32-QT's /api/debug
// vocabulary: player.debug({command: 'pause' | 'resume' | 'step' | 'breakpoint' |
// 'speed' | 'enable', ...}) returns the same state object as GET /api/debug,
// plus a few fields the kit adds. In debug mode the core checks breakpoints
// before every instruction (prg32_debug_run) instead of running whole frames.
(function () {
  'use strict';

  const BUTTONS = { LEFT: 1, RIGHT: 2, UP: 4, DOWN: 8, A: 16, B: 32, SELECT: 64 };
  // The same keys as PRG32-QT (qml/Main.qml).
  const KEYS = {
    ArrowLeft: 'LEFT', KeyA: 'LEFT', ArrowRight: 'RIGHT', KeyD: 'RIGHT', ArrowUp: 'UP', KeyW: 'UP',
    ArrowDown: 'DOWN', KeyS: 'DOWN', KeyZ: 'A', KeyJ: 'A', KeyX: 'B', KeyK: 'B',
    Enter: 'SELECT', NumpadEnter: 'SELECT', Space: 'SELECT'
  };
  const FRAME_MS = 33; // PRG32 VirtualClock::FramePeriodNanoseconds
  const AUDIO_RECORD_WORDS = 12;
  // PRG32-QT's debugger speeds (AppController::setDebugSpeed).
  const SPEEDS = [0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 4];
  // prg32_debug_run results (wasm/prg32_core_api.cpp).
  const RUN = { ERROR: -1, BUDGET: 0, FRAME_END: 1, BREAKPOINT: 2, DONE: 3 };
  const MEMORY_LIMIT = 1024; // PRG32-QT's /api/debug reads at most 1024 bytes
  const STEP_BUDGET = 20000000; // the core's per-call instruction budget

  // A cartridge's identity for remembering its breakpoints: SHA-256 of its bytes.
  async function sha256Hex(data) {
    if (window.crypto && window.crypto.subtle) {
      const digest = await window.crypto.subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
    }
    let hash = 0x811c9dc5; // no Web Crypto (plain http on another computer): FNV-1a is enough for a key
    for (const byte of data) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
    return 'fnv1a-' + hash.toString(16);
  }

  function storedBreakpoints(sha) {
    try { return JSON.parse(localStorage.getItem('prg32-kit-breakpoints:' + sha) || '[]'); } catch (_) { return []; }
  }

  function storeBreakpoints(sha, addresses) {
    try { localStorage.setItem('prg32-kit-breakpoints:' + sha, JSON.stringify(addresses)); } catch (_) { /* private window */ }
  }

  // "0x40800100", "1082130688" or a number -> an unsigned 32-bit address, or null.
  function parseAddress(value) {
    if (typeof value === 'number') return Number.isInteger(value) && value >= 0 && value <= 0xffffffff ? value : null;
    const text = String(value ?? '').trim();
    if (!/^(0x[0-9a-f]{1,8}|[0-9]{1,10})$/i.test(text)) return null;
    const number = Number(text);
    return number <= 0xffffffff ? number : null;
  }
  let corePromise = null;

  function loadScript(url) {
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = url;
      script.onload = resolve;
      script.onerror = () => reject(new Error('Could not load ' + url));
      document.head.appendChild(script);
    });
  }

  // One WebAssembly instance is shared by the page; it runs one cartridge at a time.
  function loadCore(base) {
    if (!corePromise) {
      corePromise = (window.createPrg32Core ? Promise.resolve() : loadScript(base + 'prg32-core.js'))
        .then(() => window.createPrg32Core({ locateFile: name => base + name }));
    }
    return corePromise;
  }

  // Plays the cartridge's audio calls with Web Audio. An approximation of
  // PRG32-QT's mixer (see docs/compatibility.md): tones and notes are simple
  // oscillators, PCM samples are played as recorded.
  class AudioHost {
    constructor() {
      this.context = null;
      this.master = null;
      this.voices = new Map();
      this.channelGain = new Map();
      this.masterVolume = 220 / 255;
      this.muted = false;
    }
    ensure() {
      if (this.context || this.muted) return this.context;
      const Context = window.AudioContext || window.webkitAudioContext;
      if (!Context) return null;
      this.context = new Context();
      this.master = this.context.createGain();
      this.master.gain.value = this.masterVolume * 0.3;
      this.master.connect(this.context.destination);
      return this.context;
    }
    setMuted(muted) {
      this.muted = muted;
      if (this.master) this.master.gain.value = muted ? 0 : this.masterVolume * 0.3;
    }
    stopChannel(channel) {
      const voice = this.voices.get(channel);
      if (voice) {
        try { voice.stop(); } catch (_) { /* already ended */ }
        this.voices.delete(channel);
      }
    }
    stopAll() {
      for (const channel of Array.from(this.voices.keys())) this.stopChannel(channel);
    }
    output(channel, volume, pan) {
      const gain = this.context.createGain();
      gain.gain.value = (volume / 255) * ((this.channelGain.get(channel) ?? 255) / 255);
      let node = gain;
      if (this.context.createStereoPanner) {
        const panner = this.context.createStereoPanner();
        panner.pan.value = Math.max(-1, Math.min(1, pan / 127));
        gain.connect(panner);
        node = panner;
      }
      node.connect(this.master);
      return gain;
    }
    oscillator(channel, frequency, volume, pan, type, durationMs) {
      this.stopChannel(channel);
      const osc = this.context.createOscillator();
      osc.type = type;
      osc.frequency.value = Math.max(20, Math.min(12000, frequency));
      osc.connect(this.output(channel, volume, pan));
      osc.start();
      if (durationMs) osc.stop(this.context.currentTime + durationMs / 1000);
      this.voices.set(channel, osc);
    }
    // records: Int32Array view (12 words per call); floats: Float32Array view of the same memory.
    play(records, floats, count, pcm) {
      if (!count || !this.ensure()) return;
      const waveforms = ['square', 'triangle', 'sawtooth', 'sine'];
      for (let index = 0; index < count; index += 1) {
        const at = index * AUDIO_RECORD_WORDS;
        const kind = records[at];
        const channel = records[at + 1];
        const a = records[at + 2];
        const b = records[at + 3];
        const volume = records[at + 6];
        const pan = records[at + 7];
        if (kind === 2) this.oscillator(100, floats[at + 4], volume, 0, 'square', a); // tone
        else if (kind === 3 || kind === 4) {
          const frequency = 440 * Math.pow(2, (a - 69) / 12); // MIDI note
          this.oscillator(channel, frequency, volume, pan, kind === 4 ? waveforms[records[at + 10] % 4] : 'square', 0);
        } else if (kind === 5 || kind === 7) this.stopChannel(channel);
        else if (kind === 6 && b > 0) { // PCM
          this.stopChannel(channel);
          const rate = Math.max(3000, Math.min(96000, floats[at + 4] || 22050));
          const buffer = this.context.createBuffer(1, b, rate);
          buffer.copyToChannel(pcm.slice(a, a + b), 0);
          const source = this.context.createBufferSource();
          source.buffer = buffer;
          const loopEnd = records[at + 9];
          if (loopEnd > 0) {
            source.loop = true;
            source.loopStart = records[at + 8] / rate;
            source.loopEnd = loopEnd / rate;
          }
          source.connect(this.output(channel, volume, pan));
          source.start();
          this.voices.set(channel, source);
        } else if (kind === 8) this.stopAll();
        else if (kind === 9) { this.masterVolume = b / 255; this.setMuted(this.muted); }
        else if (kind === 10) this.channelGain.set(channel, b);
      }
    }
  }

  class PRG32CartridgePlayer {
    /**
     * canvas: a <canvas> (it is sized 320 x 200 here; scale it with CSS).
     * options.base: folder of prg32-core.js/.wasm; options.onStatus(status) after every tick.
     */
    constructor(canvas, options = {}) {
      this.canvas = canvas;
      this.canvas.width = 320;
      this.canvas.height = 200;
      this.context2d = canvas.getContext('2d');
      this.image = this.context2d.createImageData(320, 200);
      this.base = options.base || '/static/wasm/';
      this.onStatus = options.onStatus || (() => {});
      this.core = null;
      this.running = false;
      this.speed = 1;
      this.held = 0;      // buttons held now
      this.pressed = 0;   // buttons pressed since the last frame (a quick tap still counts)
      this.frames = 0;
      this.wallMs = 0;
      this.error = '';
      this.audio = new AudioHost();
      this.lastTime = 0;
      this.debt = 0;
      this.onDebug = options.onDebug || (() => {});
      this.debugEnabled = false;
      this.debugReason = '';            // why the debugger last stopped: breakpoint, step, pause...
      this.sha256 = '';
      this.instructionsPerFrame = 8192; // measured each frame, sets the slice size at slow speeds
      this.instructionsThisFrame = 0;
      this.tick = this.tick.bind(this);
      this.keyHandler = this.keyHandler.bind(this);
      window.addEventListener('keydown', this.keyHandler);
      window.addEventListener('keyup', this.keyHandler);
    }

    async load(bytes) {
      this.pause();
      this.core = await loadCore(this.base);
      const data = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
      const pointer = this.core._malloc(data.length);
      this.core.HEAPU8.set(data, pointer);
      const ok = this.core._prg32_load(pointer, data.length);
      this.core._free(pointer);
      this.frames = 0;
      this.wallMs = 0;
      this.instructionsThisFrame = 0;
      this.debugReason = '';
      this.error = ok ? '' : this.core.UTF8ToString(this.core._prg32_last_error());
      if (!ok) {
        this.status();
        throw new Error(this.error);
      }
      // Breakpoints are remembered per cartridge (PRG32-QT forgets them when another one is loaded).
      this.sha256 = await sha256Hex(data);
      for (const address of storedBreakpoints(this.sha256)) this.core._prg32_breakpoint(address >>> 0, 1);
      this.audio.stopAll();
      this.draw();
      this.status();
      return { name: this.core.UTF8ToString(this.core._prg32_cartridge_name()) };
    }

    get loaded() { return Boolean(this.core && this.core._prg32_loaded()); }

    keyHandler(event) {
      const button = KEYS[event.code];
      if (!button || !this.loaded || !this.capturesKeys(event)) return;
      event.preventDefault();
      const bit = BUTTONS[button];
      if (event.type === 'keydown') { this.held |= bit; this.pressed |= bit; } else this.held &= ~bit;
    }

    // Keys typed into a text box or code editor are not game buttons.
    // Game keys only while the screen has the focus (or nothing has it): Enter and the arrows
    // must still operate buttons, menus and the debugger's lists.
    capturesKeys(event) {
      const target = event.target;
      return !target || target === this.canvas || target === document.body || target === document.documentElement;
    }

    // On-screen buttons (touch screens) call this.
    setButton(name, down) {
      const bit = BUTTONS[name] || 0;
      if (down) { this.held |= bit; this.pressed |= bit; } else this.held &= ~bit;
    }

    input() {
      const mask = this.held | this.pressed;
      this.pressed = 0;
      return mask;
    }

    frame() {
      if (!this.loaded) return false;
      if (this.debugEnabled) return this.debugFrame();
      if (!this.core._prg32_frame(this.input())) {
        this.error = this.core.UTF8ToString(this.core._prg32_last_error());
        this.pause();
        return false;
      }
      this.playAudio();
      return true;
    }

    playAudio() {
      const count = this.core._prg32_audio_count();
      if (count) {
        const records = this.core._prg32_audio_records() >> 2;
        const words = this.core.HEAP32.subarray(records, records + count * AUDIO_RECORD_WORDS);
        const floats = this.core.HEAPF32.subarray(records, records + count * AUDIO_RECORD_WORDS);
        const pcmPointer = this.core._prg32_audio_pcm() >> 2;
        this.audio.play(words, floats, count, this.core.HEAPF32.subarray(pcmPointer));
      }
      this.core._prg32_audio_clear();
    }

    draw() {
      if (!this.loaded) return;
      const pointer = this.core._prg32_framebuffer() >> 1;
      const pixels = this.core.HEAPU16.subarray(pointer, pointer + 320 * 200);
      const out = this.image.data;
      for (let index = 0, at = 0; index < pixels.length; index += 1, at += 4) {
        const pixel = pixels[index];
        out[at] = ((pixel >> 11) & 31) * 255 / 31;
        out[at + 1] = ((pixel >> 5) & 63) * 255 / 63;
        out[at + 2] = (pixel & 31) * 255 / 31;
        out[at + 3] = 255;
      }
      this.context2d.putImageData(this.image, 0, 0);
    }

    start() {
      if (!this.loaded || this.running) return;
      this.audio.ensure(); // browsers allow sound only after a click
      if (this.audio.context && this.audio.context.state === 'suspended') this.audio.context.resume();
      this.running = true;
      this.canvas.focus({ preventScroll: true });  // the game keys now reach the game
      this.lastTime = performance.now();
      this.debt = 0;
      requestAnimationFrame(this.tick);
      this.status();
    }

    pause() {
      this.running = false;
      this.audio.stopAll();
      this.status();
    }

    toggle() {
      if (this.debugEnabled) this.debug({ command: this.running ? 'pause' : 'resume' });
      else if (this.running) this.pause();
      else this.start();
      return this.running;
    }

    step() {
      if (this.debugEnabled) {
        this.debug({ command: 'step_frame' });
        return;
      }
      this.pause();
      if (this.frame()) this.draw();
      this.status();
    }

    setSpeed(speed) { this.speed = Math.max(0.01, Math.min(4, Number(speed) || 1)); this.status(); }

    tick(now) {
      if (!this.running) return;
      const elapsed = Math.min(250, now - this.lastTime); // after a hidden tab, do not race to catch up
      this.lastTime = now;
      this.wallMs += elapsed;
      if (this.debugEnabled) {
        this.debugTick(elapsed);
        if (this.running) requestAnimationFrame(this.tick);
        return;
      }
      this.debt += elapsed * this.speed;
      let ran = 0;
      while (this.debt >= FRAME_MS && ran < 8 && this.running) {
        this.debt -= FRAME_MS;
        if (!this.frame()) break;
        ran += 1;
      }
      if (ran) this.draw();
      this.status();
      if (this.running) requestAnimationFrame(this.tick);
    }

    // --- debugger -------------------------------------------------------------

    // One instrumented run of the core; returns a RUN code and keeps the frame bookkeeping.
    debugRun(budget, mode) {
      const result = this.core._prg32_debug_run(this.held | this.pressed, budget, mode, 1);
      this.instructionsThisFrame += this.core._prg32_debug_last_steps();
      if (result === RUN.FRAME_END) this.frameEnded();
      else if (result === RUN.BREAKPOINT) this.stopped('breakpoint');
      else if (result === RUN.ERROR) {
        this.error = this.core.UTF8ToString(this.core._prg32_last_error());
        this.stopped('error');
      }
      return result;
    }

    frameEnded() {
      this.pressed = 0;
      this.instructionsPerFrame = Math.max(1, this.instructionsThisFrame);
      this.instructionsThisFrame = 0;
      this.playAudio();
    }

    stopped(reason) {
      this.debugReason = reason;
      this.pause();
    }

    // A whole frame (or the rest of the current one), stopping at breakpoints.
    debugFrame() {
      let result = RUN.BUDGET;
      for (let tries = 0; tries < 8 && result === RUN.BUDGET; tries += 1) result = this.debugRun(STEP_BUDGET, 0);
      return result === RUN.FRAME_END;
    }

    // Play in debug mode: run as many instructions as the speed allows in this much real time,
    // so at 0.01x the program counter visibly walks through the code (PRG32-QT's slices).
    debugTick(elapsed) {
      this.debt += (elapsed * this.speed) / FRAME_MS * this.instructionsPerFrame;
      let budget = Math.min(Math.floor(this.debt), this.instructionsPerFrame * 8);
      this.debt -= Math.floor(this.debt);
      let frames = 0;
      while (budget > 0 && this.running && frames < 8) {
        const result = this.debugRun(budget, 0);
        budget -= Math.max(1, this.core._prg32_debug_last_steps());
        if (result === RUN.FRAME_END) frames += 1;
        else break;
      }
      this.draw();
      this.status();
      this.onDebug(this.debugState());
    }

    /**
     * PRG32-QT's POST /api/debug commands: enable {enabled}, pause, resume, step, speed {speed},
     * breakpoint {address, enabled}. The kit adds step_over, step_out, step_frame and
     * clear_breakpoints. Returns the debugger state, or {ok: false, error} like PRG32-QT's HTTP 400.
     */
    debug(request) {
      const command = String((request && request.command) || '').toLowerCase();
      const refuse = error => ({ ok: false, error });
      if (command === 'enable') {
        this.debugEnabled = request.enabled !== false;
        this.debt = 0;
        return this.debugAnswer();
      }
      if (command === 'speed') {
        const speed = Number(request.speed);
        if (!SPEEDS.includes(speed)) return refuse('supported speeds are 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, and 4');
        this.setSpeed(speed);
        return this.debugAnswer();
      }
      if (!this.debugEnabled) return refuse('debug mode is disabled');
      if (!this.loaded) return refuse('no cartridge is running');
      if (command === 'breakpoint') {
        const address = parseAddress(request.address);
        if (address === null || !this.core._prg32_breakpoint(address, request.enabled === false ? 0 : 1)) {
          return refuse('invalid breakpoint address');
        }
        storeBreakpoints(this.sha256, this.breakpoints());
        return this.debugAnswer();
      }
      if (command === 'clear_breakpoints') {
        this.core._prg32_breakpoints_clear();
        storeBreakpoints(this.sha256, []);
        return this.debugAnswer();
      }
      if (command === 'pause') {
        this.debugReason = 'pause';
        this.pause();
        return this.debugAnswer();
      }
      if (command === 'resume') {
        this.core._prg32_debug_resume(); // ignore the breakpoint we are standing on, once
        this.debugReason = '';
        this.start();
        return this.debugAnswer();
      }
      if (command === 'step' || command === 'step_over' || command === 'step_out' || command === 'step_frame') {
        this.pause();
        this.debugReason = command;
        let ok = true;
        if (command === 'step') ok = Boolean(this.core._prg32_debug_step_instruction(this.input()));
        else if (command === 'step_frame') {
          this.core._prg32_debug_resume();
          this.debugFrame();
        } else {
          const result = this.debugRun(STEP_BUDGET, command === 'step_over' ? 1 : 2);
          if (result === RUN.BUDGET) this.debugReason = 'budget';
          ok = result !== RUN.ERROR;
        }
        if (command === 'step') {
          this.instructionsThisFrame += this.core._prg32_debug_last_steps();
          if (this.core._prg32_debug_phase() === 0) this.frameEnded();
        }
        if (!ok) this.error = this.core.UTF8ToString(this.core._prg32_last_error());
        this.draw();
        this.status();
        return ok ? this.debugAnswer() : refuse(this.error || 'unable to step guest execution');
      }
      return refuse('expected command enable, pause, step, resume, breakpoint or speed');
    }

    debugAnswer() {
      const state = this.debugState();
      this.onDebug(state);
      return state;
    }

    breakpoints() {
      return this.loaded ? JSON.parse(this.core.UTF8ToString(this.core._prg32_debug_state_json())).breakpoints : [];
    }

    /** Bounded guest memory read (at most 1024 bytes, like PRG32-QT); null outside guest memory. */
    readMemory(address, length) {
      const start = parseAddress(address);
      if (!this.loaded || start === null) return null;
      const size = Math.max(1, Math.min(MEMORY_LIMIT, Number(length) || 128));
      const buffer = this.core._malloc(size);
      const got = this.core._prg32_read_memory(start, buffer, size);
      const bytes = this.core.HEAPU8.slice(buffer, buffer + got);
      this.core._free(buffer);
      return got ? bytes : null;
    }

    /** count instructions from address: [{address, width, word, text}] (PRG32-QT's disassembler). */
    disassemble(address, count) {
      const start = parseAddress(address);
      if (!this.loaded || start === null) return [];
      return JSON.parse(this.core.UTF8ToString(this.core._prg32_disassemble(start, Math.min(256, count || 16))));
    }

    /** PRG32-QT's GET /api/debug state (+ kit fields). query: {address, length} for the memory bytes. */
    debugState(query = {}) {
      if (!this.loaded) return { ok: true, enabled: this.debugEnabled, running: false, paused: false, loaded: false };
      const core = JSON.parse(this.core.UTF8ToString(this.core._prg32_debug_state_json()));
      const address = parseAddress(query.address) ?? core.pc;
      const memory = this.readMemory(address, query.length || 128);
      return {
        ok: true, loaded: true, enabled: this.debugEnabled, running: this.running, paused: !this.running,
        phase: core.phase, speed: this.speed, pc: core.pc, breakpoints: core.breakpoints, registers: core.registers,
        memory_address: address,
        memory_hex: memory ? Array.from(memory, byte => byte.toString(16).padStart(2, '0')).join('') : '',
        // What the kit adds:
        reason: this.debugReason, error: this.error, entries: core.entries, call_active: core.call_active,
        breakpoint_hits: core.breakpoint_hits, last_breakpoint: core.last_breakpoint,
        frames: core.frames, retired: core.retired, cycles: core.cycles, guest_ns: core.guest_ns,
        wall_ms: Math.round(this.wallMs), sha256: this.sha256
      };
    }

    // What students see under the screen.
    state() {
      if (!this.loaded) return null;
      return JSON.parse(this.core.UTF8ToString(this.core._prg32_state_json()));
    }

    status() {
      const state = this.loaded ? this.state() : null;
      this.frames = state ? state.frames : 0; // the core counts frames, whichever way they ran
      this.onStatus({
        loaded: this.loaded, running: this.running, speed: this.speed, error: this.error,
        frames: this.frames, guestMs: this.frames * FRAME_MS, wallMs: Math.round(this.wallMs),
        retired: state ? state.retired : 0, pc: state ? state.pc : null
      });
    }

    destroy() {
      this.pause();
      window.removeEventListener('keydown', this.keyHandler);
      window.removeEventListener('keyup', this.keyHandler);
      if (this.core) this.core._prg32_unload();
    }
  }

  window.PRG32CartridgePlayer = PRG32CartridgePlayer;
  window.PRG32CartridgePlayer.BUTTONS = BUTTONS;
  window.PRG32CartridgePlayer.SPEEDS = SPEEDS;
  window.PRG32CartridgePlayer.parseAddress = parseAddress;
})();
