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
      this.error = ok ? '' : this.core.UTF8ToString(this.core._prg32_last_error());
      if (!ok) {
        this.status();
        throw new Error(this.error);
      }
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
    capturesKeys(event) {
      const target = event.target;
      return !(target && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName)));
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
      if (!this.core._prg32_frame(this.input())) {
        this.error = this.core.UTF8ToString(this.core._prg32_last_error());
        this.pause();
        return false;
      }
      this.frames += 1;
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

    toggle() { if (this.running) this.pause(); else this.start(); return this.running; }

    step() {
      this.pause();
      if (this.frame()) this.draw();
      this.status();
    }

    setSpeed(speed) { this.speed = Math.max(0.05, Math.min(4, Number(speed) || 1)); this.status(); }

    tick(now) {
      if (!this.running) return;
      const elapsed = Math.min(250, now - this.lastTime); // after a hidden tab, do not race to catch up
      this.lastTime = now;
      this.wallMs += elapsed;
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

    // What students see under the screen; the debugger (G5) will build on the same state.
    state() {
      if (!this.loaded) return null;
      return JSON.parse(this.core.UTF8ToString(this.core._prg32_state_json()));
    }

    status() {
      const state = this.loaded ? this.state() : null;
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
})();
