# How PRG32 games sound

## For students

A PRG32 game has **8 voices**: 8 sounds can play at the same time. Each voice plays an
**instrument**:

- a **synth sound** like old home computers: triangle, saw, pulse (a square whose width
  you choose) or noise, through a filter (cutoff and resonance);
- or a recorded **sample** (8-bit sound).

Every synth note has an **envelope**, ADSR:

| | What it does | Range |
|---|---|---|
| **A**ttack | how fast the note gets loud | 0 (at once) … 255 (about 2 s) |
| **D**ecay | how fast it falls to the sustain level | 0 … 255 |
| **S**ustain | how loud it stays while the note is held | 0 … 255 |
| **R**elease | how fast it fades after the note ends | 0 … 255 |

Each voice also has a **volume** (0–255) and a **pan** from −64 (all left) to 63 (all
right). A **soundtrack** is a list of notes over time; in a soundtrack, voice 0 plays
instrument 0, voice 1 instrument 1, and so on.

The Player in the browser uses **the same sound engine as the PRG32 console**, so what you
hear is what the console plays. (The old *buzzer* is gone: games use the 8 voices.)

## For teachers

- The browser core runs the PRG32 firmware's own audio code (ADR-0021), not an imitation:
  same voices, envelopes, filter, samples, soundtracks, stereo mix and clipping.
- Sound starts when you press **Play** (browsers allow sound only after a click), pauses
  with the game, and is silent at debug speeds.
- An old game that still uses the buzzer plays without that sound; the Player says so.
  Advanced C and assembly projects that call it get an error explaining what to use.

## The numbers (contracts/prg32-audio-contract-1.json)

| | |
|---|---|
| Voices | 8 (0–7) |
| Output | 22050 Hz, signed 16-bit, stereo (left, right) |
| Mixing | each voice: `pcm × voice >> 8 × channel >> 8 × master >> 9`; voices summed; clamped to −32768…32767 |
| Pan gains | left `255 − pan×255/63` for pan > 0, right `255 − (−pan)×255/64` for pan < 0, else 255 |
| ADSR time | `1 + v×v×2000/65025` ms (0 = at once); the level moves a whole step per sample, so a stage can end a little early |
| Sustain level | `sustain × 257` of 65535 |
| Tracker | one tick = `60000 / (bpm × 4)` ms; bpm 30–300, default 120; an event runs, then the tracker waits its delta before the next one |
| Audio block | `AUD0` v1: at most 64 samples, 32 instruments, 16 tracks |

## How it is checked

| Check | Where |
|---|---|
| Every number above, read again from the PRG32 SDK sources | `tests/test_audio_contract.py` |
| The kit's audio-block packer writes the SDK packer's bytes; bad blocks refused | `tests/test_audio_block.py` |
| 8 voices at once, sustain levels, attack and release times, hard left/right separation, pan and volume changes, clipping, exact silence, soundtrack (instrument N on voice N), voice replacement, old cartridges silent, damaged blocks refused | `tests/test_audio_conformance.py` on `tests/fixtures/audio/conformance.prg32` |
| The same samples from the WebAssembly and native builds; a recorded PCM hash and envelope trace | `tests/test_audio_conformance.py`, `tests/fixtures/audio/expected.json` |
| The Player schedules the frames, bounded, and stops on Pause | `tests/test_audio_browser.py` |
| The buzzer is reachable nowhere | `tests/test_no_buzzer.py` |
| An AudioStudio cartridge on a real console: built by the kit, compared with the browser core (I2S capture or microphones) | `hardware_audio_check.md`, `tests/test_hardware_audio_check.py` |

Make the fixtures again (needs the PRG32 toolchain):

```bash
python3 tools/build_audio_fixtures.py
```

Record a cartridge's sound from the browser core, with a WAV file:

```bash
node tools/audio_capture.mjs tests/fixtures/audio/conformance.prg32 170 conformance.wav
```

`tools/qemu_audio_capture.py` records the real firmware in QEMU and compares it chunk by
chunk. At PRG32 `679dfb5` the QEMU firmware does not start its audio stream (its I2S
pins are −1), so no such recording exists yet.
