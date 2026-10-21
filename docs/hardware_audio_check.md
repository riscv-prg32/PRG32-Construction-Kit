# Checking the sound on a real PRG32 console

The kit's tests prove that the browser plays the PRG32 firmware's sound engine
(`audio_engine.md`). This check proves the last step: a PRG32 cartridge made in
AudioStudio sounds the same on the console. It needs a person, a console and about
30 minutes. The result goes into `docs/evidence/hardware-audio/`.

## What is played

`tests/fixtures/audio/hardware/audio_check-esp32c6.prg32` was made like any student
project: Blocks, an AudioStudio document (`audio_studio.json`) and a WAV sample, built by
the kit with the real PRG32 toolchain (`tools/build_hardware_audio_check.py`, hashes in
`BUILD.json`). It repeats a programme of 330 frames (about 10.9 s):

| Time | What you hear |
|---|---|
| 0.0–2.0 s | all 8 voices at once: 8 instruments, pans from hard left to hard right, 8 different envelopes |
| 2.0–2.9 s | the notes fade out, then silence |
| 3.0–4.0 s | voice 0 alone, **left** speaker only |
| 4.25–5.25 s | voice 7 alone, **right** speaker only |
| 6.6 s | the "Drum" sound effect (a recorded sample) |
| 7.6–8.1 s | a held note, cut by "stop all sounds" |
| 8.1–10.9 s | silence |

The screen shows `PRG32 AUDIO CHECK` and the frame counter.

## You need

- A PRG32 console wired for **stereo** (two MAX98357A amplifiers, `hardware.md` in the
  PRG32 repository), with firmware built with `CONFIG_PRG32_AUDIO_MODE_STEREO=y`. With the
  shipped mono profile both channels carry the same sound and the left/right checks fail.
- **Recommended:** a logic analyser that sigrok supports (any FX2-based 8-channel USB
  analyser works) and `sigrok-cli`. It records the I2S data the ESP32-C6 sends to the
  amplifiers: the console's own samples, so the checks can be exact.
- Otherwise: two microphones (or a stereo recorder), one close to each speaker.
  **Never connect the speaker outputs to a line or microphone input**: the amplifiers
  drive the speakers directly and can damage the input.

## Steps

1. **Put the cartridge on the console.** Pick a slot you do not need (`cart7` here):

   ```bash
   python3 tools/delivery_check.py device --url http://192.168.4.1 --slot cart7 --target "PRG32 console (stereo)" --out audio-check-delivery.json tests/fixtures/audio/hardware/audio_check-esp32c6.prg32
   ```

   The record has the cartridge's SHA-256. It must match `BUILD.json`.

2. **Record at least 25 seconds.**

   - *Logic analyser:* connect ground, and D0 to BCLK (GPIO4), D1 to LRC/WS (GPIO11) and
     D2 to DIN (GPIO23). Then run:

     ```bash
     sigrok-cli -d fx2lafw -c samplerate=8m --time 25s -C D0,D1,D2 -P i2s:sck=D0:ws=D1:sd=D2 -B i2s=wav > audio-check-i2s.wav
     ```

   - *Microphones:* record stereo (left microphone on the left channel) at 44.1 or 48 kHz,
     with the level well below clipping, into `audio-check-mics.wav`.

3. **Compare with the browser core.** This needs Node.js; it runs the same cartridge in
   the browser core as the reference:

   ```bash
   python3 tools/hardware_audio_compare.py audio-check-i2s.wav --digital --out audio-check-report.json
   ```

   For microphones, leave out `--digital`. Exit code 0 means every check passed.

4. **Keep the evidence.** Put these files in `docs/evidence/hardware-audio/<date>/`:
   the delivery record, the recording, the report, the firmware commit and its
   `sdkconfig`, and a line on what you heard. Commit them.

## What the report checks

| Check | Digital (I2S) | Microphones |
|---|---|---|
| A whole programme is found in the recording | correlation ≥ 0.5 | same |
| Left and right loudness follow the reference | correlation ≥ 0.98 | ≥ 0.85 |
| The 8-voice chord sounds on both channels | ≥ −20 dB of the peak | same |
| Silence after the chord and after "stop all sounds"; a buzzer, hum or leftover voice would show here | ≤ −120 dB (digital zero) | ≤ −40 dB |
| Hard left and hard right are separate | ≥ 120 dB (nothing on the other channel) | ≥ 6 dB |
| The sample sound effect is heard | ≥ 20 dB over the silence | same |
| "Stop all sounds" cuts the held note at once | ≤ −40 dB within 60–300 ms | same |
| 4096 samples of the left-only and the right-only voice appear unchanged in the capture | required | — |

The bit-exact check uses single voices on purpose. Event timing on the console follows
its own audio buffers, so the 8-voice parts can start a buffer earlier or later than in
the browser, but a voice's own samples cannot differ if the engine is the same.

`tests/test_hardware_audio_check.py` proves the tool itself. Good captures pass. It fails
captures with one changed sample, swapped channels, a tone in the silence, crosstalk in a
digital capture, the wrong sample rate, or a recording that is too short.

## Status

No console recording has been made yet. Until one is in `docs/evidence/hardware-audio/`,
the physical path is the remaining audio exception.
