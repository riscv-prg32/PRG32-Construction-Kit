# PRG32 firmware in QEMU against the browser core (2026-10-21)

The real PRG32 firmware, run in Espressif's QEMU, recorded by `tools/qemu_audio_capture.py`.

| | |
|---|---|
| Firmware | PRG32 SDK `679dfb5`, built from a clean clone with ESP-IDF v5.4, the QEMU profile and the kit's overlay `tests/fixtures/audio/sdkconfig.qemu-stereo` (stereo, I2S pin numbers); full `firmware-sdkconfig` here |
| QEMU | QEMU emulator version 9.0.0 (esp_develop_9.0.0_20240606), SDL "dummy" display |
| Kit | `37614c5` plus the console check's master-volume block (committed with this evidence) |
| Cartridges | `conformance.prg32` (7 s) and `hardware/audio_check-qemu.prg32` (11 s); SHA-256 in each `comparison.json` |

Each folder has the firmware's stereo PCM (`firmware.wav`, 22050 Hz, 16-bit), its console
log and `comparison.json`. The browser side is made again from the cartridge (its SHA-256
is recorded), and `tests/test_audio_conformance.py::test_the_qemu_firmware_evidence_still_holds`
checks that it still is.

## Result

| Cartridge | Sounding 20 ms chunks (browser) | Equal sample for sample in the firmware | Longest equal run |
|---|---|---|---|
| conformance | 234 | 76 | 380 ms |
| audio_check | 269 | 66 | 720 ms |

Between cartridge events the firmware and the browser core produce the same samples. The
runs end at events because the two do not put events at the same time. In QEMU the
firmware's audio task advances the engine by the emulated clock (`esp_timer`), about 28 ms
per 20 ms chunk, instead of by the samples it has rendered. So its tracker and envelopes run
ahead of its own output (firmware chunk 154 is browser chunk 212; 234 is 330). This happens
only on the QEMU path, which waits for an acknowledgement per chunk. On the console the I2S
DMA paces the task (upstream finding).

## How to make it again

```bash
. $HOME/esp-idf/export.sh
python3 tools/qemu_audio_capture.py --build tests/fixtures/audio/conformance.prg32 --sdk ../PRG32 --seconds 7 --out DIR
```
