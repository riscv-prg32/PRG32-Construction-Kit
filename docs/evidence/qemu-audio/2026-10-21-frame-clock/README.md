# PRG32 firmware in QEMU with the audio frame clock (2026-10-21)

The PRG32 firmware's sound in Espressif's QEMU equals the browser core's, sample for sample,
over the whole recording, in every run.

| | |
|---|---|
| Firmware | PRG32 `679dfb5` + [`prg32-sdk-audio-clock-and-reset.patch`](../../../upstream/prg32-sdk-audio-clock-and-reset.patch) (as in [riscv-prg32/PRG32#46](https://github.com/riscv-prg32/PRG32/pull/46)), ESP-IDF v5.4, QEMU profile + `tests/fixtures/audio/sdkconfig.qemu-stereo` (`firmware-sdkconfig`) |
| QEMU | 9.0.0 (esp_develop_9.0.0_20240606), SDL dummy display, `-icount shift=3,sleep=off` |
| Browser core | `static/wasm` (kit `46b24aa` plus the frame-clock change in `wasm/prg32_core_api.cpp`) |

## The scheduling boundary

Frame N of a cartridge (from 0, run together with init) starts at N × 33 ms. Every audio call
made by init or by that frame takes effect at its start. The engine renders whole 20 ms
buffers (441 stereo frames), so a sound started in frame N sounds from buffer ⌊N × 33 / 20⌋.
The console check's drum (frame 200), held note (230) and stop (245) therefore start at
buffers 330, 379 and 404, in the firmware, the browser core and PRG32-QT alike. The physical
console keeps its I2S timing; ADR-0021 has the rule.

## Results

| Recording | Buffers equal at one shift | Whole-recording SHA-256 (firmware aligned = browser) |
|---|---|---|
| `audio_check-qemu/`, 11 s, 331 frames | **546 of 546**, runs 1–3 | `a035b9ed5602d759112eb1e7617909bc89a9c1fda7fa3c8e735bf6ef6b025ef3` |
| `conformance/`, 7 s, 211 frames | **348 of 348**, runs 1–3 | `a5af48747f363fc3fef3184ce55d9dd9fde78a78927c79f6219064025fc95b31` |

PRG32-QT with [riscv-prg32/PRG32-QT#1](https://github.com/riscv-prg32/PRG32-QT/pull/1)
(`prg32qt-headless --audio-wav`, the same frame counts) gives the same two hashes.

The shift (0 or 1 buffer) is where the recorder noticed the cartridge's start line on the
serial console. It is capture timing, not sound: at it, every buffer is equal.
`run2-comparison.json` and `run3-comparison.json` are the repeat runs; `firmware.wav` and
`firmware-serial.log` are from run 1. The firmware recording runs 10 buffers longer than the
browser's, so the shift can still pair every buffer.

Before the frame clock (`../2026-10-21-patched/`), frame-triggered effects landed one 20 ms
buffer apart, in two phases from run to run: 531 or 502 of 546, and 279 of 348.

## Checked by

- `tests/test_audio_conformance.py::test_qemu_firmware_equals_the_browser_core_over_the_whole_recording`:
  the recordings are intact and come from today's patch; the browser side is reproduced; every
  buffer is equal and the aligned firmware PCM has the browser PCM's SHA-256, in all three runs;
- `test_frame_triggered_effects_sound_from_their_frames_buffer`: the browser core puts the
  drum, the held note and the stop in buffers 330, 379 and 404, not one earlier or later;
- `test_a_one_buffer_shift_of_one_effect_breaks_whole_recording_equality`;
- opt-in `test_live_qemu_audio_does_not_drift` (`PRG32_LIVE_QEMU=1`): builds the patched
  firmware, records the console check and fails unless the whole recording is equal.

```bash
. $HOME/esp-idf/export.sh
PRG32_QEMU_EXTRA="-icount shift=3,sleep=off" python3 tools/qemu_audio_capture.py --build \
    --patch docs/upstream/prg32-sdk-audio-clock-and-reset.patch \
    tests/fixtures/audio/hardware/audio_check-qemu.prg32 --seconds 11 --out DIR
```
