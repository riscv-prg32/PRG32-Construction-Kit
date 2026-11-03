# The rebased SDK patches in QEMU (2026-11-03)

PRG32 `1eff2e2` (the commit the kit pins) with the rebased patches in `docs/upstream/`, built
with ESP-IDF for Espressif's QEMU 9.0.0 (`-icount shift=3,sleep=off`) by
`tools/qemu_audio_capture.py --build`. One run of each; each `comparison.json` records the
SHA-256 of the patches it was built with, the flash image, and both recordings.

| Folder | Firmware | Cartridge | Buffers equal to the browser core | Aligned SHA-256 |
|---|---|---|---|---|
| `clock-console-check/` | + frame clock | console check, 11 s | **546 of 546** | `a035b9ed…`, as on 2026-10-21 |
| `both-conformance/` | + frame clock + buzzer retired | conformance, 7 s | **348 of 348** | `a5af4874…`, as on 2026-10-21 |
| `both-legacy-buzzer/` | + both | `legacy_buzzer.prg32` (ABI 1.6), 3 s | **150 of 150**, silent | `a8df0419…` |
| `both-abi18-buzzer/` | + both | `abi18_buzzer.c` built with the unpatched SDK (ABI 1.8 hash `0x71b93e23`), 3 s | **150 of 150** | `c1df2d34…` |

The last cartridge calls all three buzzer calls and then plays a note. On the ABI 1.9 firmware
it loads, the buzzer calls do nothing, and the note sounds when the browser core plays it. A first
run of it without a master volume differed in loudness only: the firmware starts at 96, the
browser core at another value. That is not about the patches; the cartridge now sets it.

The WAV files are not kept (about 1 MB each); the serial logs show each cartridge loaded.
The same two patches also build the ESP32-C6 firmware (`pcb1` pin profile) with no warnings
from PRG32's own sources.
