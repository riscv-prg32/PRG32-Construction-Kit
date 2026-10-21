# Findings

## Critical

No exploitable critical security issue was confirmed.

## High

### H-01 — Browser audio does not implement the canonical ADSR synth

- Evidence: `static/js/prg32_runtime.js:84-180` explicitly describes an approximation; `AudioHost.oscillator` creates a constant-gain oscillator and never consumes attack, decay, sustain or release from synth records.
- Existing test: `tests/test_wasm_runtime.py::test_audio_calls_reach_the_browser_host` asserts call kinds/counts, not samples or envelopes.
- Impact: browser playback materially differs from the required PRG32 audio behavior and cannot demonstrate eight independent SID-like ADSR voices.
- Remedy: transmit the complete synth parameters or render the canonical mixer, implement deterministic ADSR and add an eight-active-voice envelope fixture.

### H-02 — AudioStudio is absent

- Evidence: there is a SpriteLab route/template/documentation, but no AudioStudio route, editor, versioned audio asset CRUD, sequencer, soundtrack/effect management or browser suite.
- Impact: students cannot create or manage instruments, soundtracks and effects as first-class project assets.
- Remedy: add a safe, accessible AudioStudio parallel to SpriteLab with deterministic assets, preview, import/export, history/conflicts and cartridge integration.

### H-03 — Obsolete buzzer support remains reachable

- Evidence: `tools/build_language_index.py:75` describes `prg32_buzzer_tone`; the generated `static/js/ide/prg32_language_index.js` exposes `prg32_buzzer_tone`, `prg32_buzzer_play_notes` and `prg32_buzzer_sample_u8`. Teaching presentations still render “play beep” as buzzer-like UI.
- Impact: the IDE recommends an API the product requirement says is no longer supported, creating incompatible new projects and misleading lessons.
- Remedy: remove buzzer APIs from the portable SDK/index and all UI/examples, regenerate the index, and add an explicit legacy migration or unsupported-format diagnostic plus a repository-wide absence test.

## Medium

### M-01 — Stereo behavior is wired but not verified as audio

`AudioHost.output` uses `StereoPannerNode`, and PRG32-QT renders two channels, but current tests compare guest state and audio call counts rather than left/right PCM, clipping, silence, reset and deterministic timing. Add fixed virtual-time PCM hashes/tolerances across firmware/QEMU, native/Qt and WASM/browser.

### M-02 — Audio asset packaging is not integrated

The canonical PRG32 audio block supports samples, instruments and tracks, but Construction Kit project/archive/artifact workflows do not expose a versioned AudioStudio asset model or prove deterministic audio-block packaging.

### M-03 — Real cloud and delivery evidence remains incomplete

Google/Microsoft tenant runs, physical hardware, end-user Qt import and iOS handoff remain externally unverified.

### M-04 — Builds still share the host service identity

Disk budgets and AppArmor improve containment, but builds share one UID outside namespaces. Keep this limitation explicit and continue Linux escape/resource testing.

## Low

### L-01 — Audio documentation is internally inconsistent

`docs/wasm_runtime.md` and compatibility material admit approximation, while the old capability score claimed reference-verified audio. `docs/prg32_feature_coverage.md` still lists buzzer in advanced audio coverage.

### L-02 — Upstream configuration fallback deserves alignment

PRG32 Kconfig defaults to eight voices, but `audio_config.h` falls back to six when the sdkconfig symbol is absent. Audit host/reference builds must prove which configuration is used and reject fewer than eight voices for this product target.

## Release conclusion

**NO-GO.** The non-audio platform has advanced substantially, but the updated mandatory audio contract is not implemented end to end.
