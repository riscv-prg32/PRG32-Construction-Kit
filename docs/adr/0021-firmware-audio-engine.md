# ADR-0021: The PRG32 firmware's audio engine in the browser; the buzzer is obsolete

**Status:** Accepted (2026-10-21, audio refinement after audit `c0d115e`)

## Context

The audit's audio gate failed: the Player played cartridges' audio calls with Web Audio
oscillators (no ADSR, no SID-like filter or noise, no PCM parity), there were no rendered
stereo tests, and the obsolete buzzer was still offered. PRG32's canonical engine is the
firmware's `components/prg32_audio`: 8 voices, SID-like synth instruments with ADSR
envelopes, PCM samples, a tracker, stereo pan and an integer mixer. PRG32-QT's renderer
is a different, floating-point mixer without ADSR, so it cannot be the reference for
sound.

## Decision

1. **One contract.** `contracts/prg32-audio-contract-1.json` records the engine as the SDK
   implements it (voices, rates, formats, volume/pan/headroom formulas, synth layout and
   tables, ADSR timing including whole-step envelopes, tracker timing, AUD0 layout and
   limits, ABI indices). `tests/test_audio_contract.py` re-reads every value from an SDK
   checkout. The SDK's no-sdkconfig fallback of 6 voices is recorded and reported
   upstream; the kit's build has exactly 8 (a compile-time `#error` otherwise).
2. **The firmware's code, not a copy or an imitation.** The browser core
   (`static/wasm`) compiles the firmware's `audio.c`, `audio_assets.c`, `audio_mixer.c`,
   `audio_synth.c` and `audio_tracker.c` unchanged from a PRG32 checkout. The kit adds
   only a port (`wasm/audio/`): build settings, FreeRTOS/timer stand-ins (one thread, no
   lock; a delay renders that much audio) and an output queue in place of I2S.
3. **Audio calls reach the engine through a hook, PRG32-QT unchanged in behaviour.**
   `wasm/CMakeLists.txt` copies PRG32-QT's core into the build folder and adds a pair of
   hooks around `Runtime::hostCall` (the build stops if the anchored lines change). The
   core still handles every call itself (timing, state, its own record); the after-hook
   gives audio calls 6 and 9–25, with their arguments, to the firmware engine and returns
   its results (for example the voice `prg32_audio_play_sample` chose).
4. **One scheduling boundary: the frame clock.** The engine renders 20 ms steps of 441
   frames. The cartridge's time is its frame count: frame N (from 0, run together with
   init) starts at N × 33 ms, and every audio call made by init or by that frame takes
   effect at its start, however many instructions update and draw retire. A sound started
   in frame N therefore sounds from 20 ms buffer ⌊N × 33 / 20⌋, sample ⌊N × 33 / 20⌋ × 441,
   on every run (`test_frame_triggered_effects_sound_from_their_frames_buffer`). Normal and
   debugged runs sound the same. (Until 2026-10-21 the engine followed the core's
   instruction-timed virtual clock; for every recorded fixture the samples are identical.)
   PRG32-QT's firmware audio and the firmware under QEMU follow the same rule
   (`docs/upstream/`), so whole recordings are equal; the physical console's I2S path is
   not changed: there the DMA paces the audio.
   Cartridge audio blocks load as on the console; a block the engine refuses stops the
   cartridge from loading.
5. **The browser plays exactly that PCM.** `PcmAudioOutput` schedules the 22050 Hz signed
   16-bit stereo frames gap-free after each frame, at most 0.3 s ahead (older sound is
   dropped, never played late), starts only after a click, stops all buffers on Pause,
   and is silent at debug speeds.
6. **The buzzer is obsolete.** `prg32_buzzer_*`, `prg32_note_t` and `PRG32_PIN_BUZZER`
   are refused by the C and assembly validators with what to use instead, listed only
   as "obsolete" in the language index (errors in the editor, never suggested), and
   silent in the browser for old cartridges (counted and shown, like a console without
   a buzzer). There is no conversion: old content is never reinterpreted.
   `tests/test_no_buzzer.py` fails if the buzzer returns anywhere reachable.
7. **Evidence.** `tests/fixtures/audio/conformance.prg32` (built by the real toolchain)
   gates all 8 voices with distinct waveforms, ADSR, volumes and pans, changes pan and
   volumes, releases, plays a hard-left sample and a hard-right voice, a packaged
   soundtrack, clips, stops and replaces voices. `tests/test_audio_conformance.py` checks
   it against the contract's formulas, pins the PCM hash and envelope trace, and proves
   the WebAssembly and native builds render identical samples.

## Consequences

- Browser sound is the firmware's to the sample; PRG32-QT's desktop sound is not (no
  ADSR, float mixer with tanh): that is reported upstream, not imitated.
- A recording from the firmware under QEMU could not be made at SDK `679dfb5`: the QEMU
  profile's I2S pins are -1, so the firmware never starts its UART audio stream
  (`tools/qemu_audio_capture.py` is ready for when it does).
- Removing the buzzer from the SDK's portable ABI and fixing the 6-voice fallback are
  SDK changes; the kit's refusal stays in place either way.
- `prg32_audio_notes` blocks the console's game while its notes play; in the browser the
  notes play in the same engine time but the game keeps running.
