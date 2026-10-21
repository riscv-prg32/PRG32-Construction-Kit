// The PRG32 sound engine for previews (AudioStudio, the Blocks preview): ADR-0021.
//
// It is the same engine the Player uses (the PRG32 firmware's audio code inside
// static/wasm/prg32-core.wasm), in its own instance of the core, driven without a
// cartridge: load the project's audio block, then play notes, sound effects and
// soundtracks. Time passes in real time while something may sound; the rendered
// stereo frames go to the same PcmAudioOutput as the Player's.
(function () {
  'use strict';

  const BASE = '/static/wasm/';
  let scriptPromise = null;

  function loadScript() {
    if (window.createPrg32Core) return Promise.resolve();
    if (!scriptPromise) {
      scriptPromise = new Promise((resolve, reject) => {
        const script = document.createElement('script');
        script.src = BASE + 'prg32-core.js';
        script.onload = resolve;
        script.onerror = () => reject(new Error('Could not load the PRG32 sound engine'));
        document.head.appendChild(script);
      });
    }
    return scriptPromise;
  }

  class PRG32AudioEngine {
    constructor() {
      this.core = null;
      this.output = new window.PRG32PcmAudioOutput();
      this.timer = null;
      this.last = 0;
      this.onVoices = null;   // optional: called with the 8 voices' state while sounding
    }

    // Start (or restart) the engine with an AUD0 block (Uint8Array or ArrayBuffer), or none.
    async start(block) {
      if (!this.core) {
        await loadScript();
        this.core = await window.createPrg32Core({ locateFile: name => BASE + name });
      }
      this.stop();
      this.core._prg32_preview_start();
      if (block && block.byteLength) {
        const bytes = block instanceof Uint8Array ? block : new Uint8Array(block);
        const pointer = this.core._malloc(bytes.length);
        this.core.HEAPU8.set(bytes, pointer);
        const ok = this.core._prg32_preview_load(pointer, bytes.length);
        this.core._free(pointer);
        if (!ok) throw new Error('The sound engine refused this audio block');
      }
      return this;
    }

    // Browsers allow sound only after a click: call from the click that plays something.
    resume() { this.output.resume(); }

    note(voice, instrument, note, volume, ms) { this.wake(); this.core._prg32_preview_note(voice, instrument, note, volume, ms); }
    noteOn(voice, instrument, note, volume, pan) { this.wake(); this.core._prg32_preview_note_on(voice, instrument, note, volume, pan); }
    noteOff(voice) { if (this.core) this.core._prg32_preview_note_off(voice); }
    playTrack(track) { this.wake(); this.core._prg32_preview_play_track(track); }
    stopTrack() { if (this.core) this.core._prg32_preview_stop_track(); }
    master(volume) { if (this.core) this.core._prg32_preview_master(volume); }

    // Silence everything at once: no voice or scheduled sound is left behind.
    stop() {
      if (this.core) {
        this.core._prg32_preview_stop_track();
        this.core._prg32_preview_stop_all();
        this.core._prg32_audio_take();
      }
      this.output.stopAll();
      clearInterval(this.timer);
      this.timer = null;
    }

    voices() {
      const out = [];
      if (!this.core) return out;
      const buffer = this.core._malloc(24);
      for (let voice = 0; voice < 8; voice += 1) {
        this.core._prg32_audio_voice(voice, buffer);
        const v = this.core.HEAP32.slice(buffer >> 2, (buffer >> 2) + 6);
        out.push({ active: v[0] === 1, state: v[2], level: v[3], volume: v[4], pan: v[5] });
      }
      this.core._free(buffer);
      return out;
    }

    // Run engine time in step with real time while voices may sound; stop when all are quiet.
    wake() {
      this.output.resume();
      if (this.timer) return;
      this.last = performance.now();
      this.timer = setInterval(() => this.pump(), 20);
    }

    pump() {
      const now = performance.now();
      const ms = Math.min(200, Math.round(now - this.last));
      if (ms < 20) return;
      this.last += ms;
      this.core._prg32_preview_advance(ms);
      const frames = this.core._prg32_audio_frames();
      if (frames) {
        const at = this.core._prg32_audio_samples() >> 1;
        this.output.play(this.core.HEAP16.subarray(at, at + frames * 2));
        this.core._prg32_audio_take();
      }
      const voices = this.voices();
      if (this.onVoices) this.onVoices(voices);
      // A soundtrack can wait between notes with every voice quiet: time keeps running for it.
      if (!voices.some(voice => voice.active) && !this.core._prg32_preview_track_active()) {
        clearInterval(this.timer);
        this.timer = null;
      }
    }
  }

  window.PRG32AudioEngine = PRG32AudioEngine;
})();
