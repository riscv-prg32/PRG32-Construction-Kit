# PRG32 firmware in QEMU with the proposed audio fixes (2026-10-21)

These recordings were made the same way as `../2026-10-21/`. The firmware was built with
[`docs/upstream/prg32-sdk-audio-clock-and-reset.patch`](../../../upstream/prg32-sdk-audio-clock-and-reset.patch)
applied to a clean clone of PRG32 SDK `679dfb5`, and QEMU ran with
`-icount shift=3,sleep=off`, so emulated time comes from instructions rather than the host.

| | |
|---|---|
| Firmware | PRG32 `679dfb5` plus the patch, ESP-IDF v5.4, QEMU profile plus `tests/fixtures/audio/sdkconfig.qemu-stereo` (`firmware-sdkconfig`) |
| QEMU | 9.0.0 (esp_develop_9.0.0_20240606), SDL dummy display, `-icount shift=3,sleep=off` |
| The SDK's own tests | `pytest tests`: 87 passed, before and after the patch |

## What the patch changes

1. **QEMU audio clock.** On the QEMU path only (`PRG32_QEMU_AUDIO_REDIRECT`), the audio
   task advances the engine by the audio it renders, 20 ms per buffer. It keeps the buffer
   period on the emulated clock with `vTaskDelayUntil`. Before, it advanced by `esp_timer`,
   about 28 ms per buffer, so events ran ahead of the samples. The console's I2S path is
   not changed.
2. **A cartridge starts with a fresh mixer.** Loading a cartridge's audio, or clearing
   it, stops every voice and the tracker and sets channel volumes back to 255 and pans to
   centre. Starting a voice stores its volume as the channel volume, and tracker notes use
   the channel volume. On the console, the setup menu's sounds therefore left voice 0 at
   about 35 % volume for the cartridge that followed (found in these recordings). This
   changes the console's behaviour, deliberately: a cartridge now sounds the same whatever
   played before it, as in the kit.

## Result: whole recordings at one fixed alignment

Each 20 ms chunk is compared sample for sample, at the single best shift.

| Recording | Before (unpatched, `../2026-10-21`) | After (this folder) |
|---|---|---|
| Console check (`audio_check`) | 120 of 540 chunks equal | **531 of 546** (phase A) or 502 of 546 (phase B) |
| Conformance | 117 of 348 | **279 of 348** |

In phase A, everything before the first frame-timed effect is equal sample for sample.
That is 6.6 s: the 8-voice chord with its 8 envelopes and pans, hard left, hard right,
and the silences.

The chunks that still differ are effects started from the cartridge's frames: the drum,
the held note and "stop all sounds" in the console check, and most events in the
conformance cartridge. Each lands one 20 ms buffer earlier or later. The firmware's audio
task renders buffers on its own schedule, which started at boot, and the cartridge's frames
run on theirs. The browser core starts both together when the cartridge loads. Two phases
occur run to run, A and B; runs in the same phase give identical firmware PCM. Restarting
the audio schedule at cartridge start was tried, and it only moved the effects one buffer
the other way. So **whole-recording equality is not reached**. It would need the firmware's
audio buffers to follow the cartridge's frame clock, which is a design change for the SDK.

## Checked by

- `tests/test_audio_conformance.py::test_patched_qemu_firmware_lines_up_over_the_whole_recording`:
  the recordings are intact, the browser side is reproduced, and the alignment numbers hold;
- `test_the_whole_console_check_soundtrack_is_equal_in_qemu`;
- opt-in `test_live_qemu_audio_does_not_drift` (`PRG32_LIVE_QEMU=1`): builds the patched
  firmware and fails if the recording drifts again.

```bash
. $HOME/esp-idf/export.sh
PRG32_QEMU_EXTRA="-icount shift=3,sleep=off" python3 tools/qemu_audio_capture.py --build \
    --patch docs/upstream/prg32-sdk-audio-clock-and-reset.patch \
    tests/fixtures/audio/hardware/audio_check-qemu.prg32 --seconds 11 --out DIR
```
