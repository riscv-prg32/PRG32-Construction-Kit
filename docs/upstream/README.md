# Upstream proposals from the kit

The kit never changes the PRG32 SDK, PRG32-QT or the Cartridge Store. When kit work finds
something one of them should change, it is written here. If the kit could prove the change,
it is a patch, built and tested against a copy of that repository.

## 1. PRG32-QT: render sound with the PRG32 firmware's engine (patch)

**Problem.** PRG32-QT mixes sound with its own floating-point renderer (`QtAudioEngine`). It
has no ADSR envelopes, so the desktop does not sound like the console and cannot be an audio
reference.

**Patch.** [`prg32-qt-firmware-audio.patch`](prg32-qt-firmware-audio.patch), against PRG32-QT
`f6d80ad`. It adds an opt-in CMake option, `PRG32QT_FIRMWARE_AUDIO=ON` with `PRG32_SDK_DIR`, that
compiles the SDK's `components/prg32_audio` unchanged into PRG32-QT. This is the same port as
the kit's browser core (`src/core/firmware_audio/` is the kit's `wasm/audio/`). The patch adds:

- host-call hooks in `Runtime`;
- `FirmwareAudio`, which drives the engine from the cartridge's audio calls;
- in `prg32qt-headless`, `--audio-wav` and a printed `AUDIO … pcm_fnv1a=` line;
- in the desktop app, the engine's PCM played through `QtAudioEngine` (resampled to the device).

The option is off by default, so the usual build is unchanged.

**Proof** (`tests/test_prg32qt_firmware_audio.py`, also run by CI's WebAssembly job):

- the patch applies to PRG32-QT;
- `prg32qt-headless` builds with the option;
- it renders the conformance fixture and the console check with the same PCM hash as the
  browser core (`2e6c5af207d3d5f2`, `a3d2c6520ba8aea2`);
- old buzzer cartridges stay silent, and their calls are counted.

PRG32-QT's own tests pass with and without the option. With the patch the desktop app also
builds (Qt 6, macOS), but its sound was not checked by ear.

```bash
cd PRG32-QT && git apply ../PRG32-Construction-Kit/docs/upstream/prg32-qt-firmware-audio.patch
cmake -S . -B build -DPRG32QT_FIRMWARE_AUDIO=ON -DPRG32_SDK_DIR=../PRG32 && cmake --build build
```

## 2. PRG32 SDK: retire the buzzer from the portable ABI (patch)

[`prg32-sdk-retire-buzzer.patch`](prg32-sdk-retire-buzzer.patch), against PRG32 SDK `679dfb5`
(it applies together with §3's patch), implements this policy:

- **ABI 1.7.** Entries 5, 7 and 8 (`prg32_buzzer_tone`, `_play_notes`, `_sample_u8`) are
  marked `"retired"` in `prg32_abi.json`. They keep their slot, so the other 136 entries
  never move, and point at one silent stub, `prg32_abi_retired_silent`, which returns 0.
  They have no import name (`IMPORT_NAMES` holds `None`), and the generator writes
  `PRG32_ABI_FN_RETIRED_n`. `abi_gen.py` and its users understand retired slots.
- **Old cartridges.** The 1.6 hash (`0x260f6136`) is in `compatible_hashes`, so cartridges
  built for 1.6 still load, and their buzzer calls do nothing. No call is reinterpreted as a
  synthesizer call.
- **New source.** `prg32.h` no longer declares the calls or `prg32_note_t`. C calling them
  fails to compile, and assembly calling them fails to link (the portable stubs have no
  symbol). The firmware keeps its own PWM driver for boards with a buzzer pin, in a private
  header (`components/prg32/prg32_buzzer.h`), for the setup menu and the splash.
- **Examples and docs.** 4 C games, 13 assembly files and `devicedemo` play
  `prg32_audio_note` or `prg32_audio_notes`, with the nearest MIDI note in a comment. The
  sound lab, the tutorial, the framework manual and the audio pages say what to use instead.

What was checked in a clean clone:

| Check | Result |
|---|---|
| The SDK's own tests, with 2 new tests (retired slots, no public buzzer, stub offsets) | 89 passed (87 before) |
| `python3 -m prg32 abi check` | generated files match |
| The 18 changed example and cartridge sources, built with the RISC-V toolchain (`--portable`) | 18 built |
| A C file calling `prg32_buzzer_tone` | does not compile (implicit declaration) |
| The same call in assembly | does not link (`undefined reference`); it builds with the unpatched SDK |
| QEMU firmware with the patch, running the kit's 1.6 `legacy_buzzer.prg32` | loads; 3 s of exact silence, equal to the browser core |
| The kit's language index from the patched SDK (ABI pin set to 1.7) | identical apart from the ABI version |

`tests/test_upstream_sdk_patches.py` (in CI) applies both SDK patches to a copy of the
checkout and repeats the ABI, header and example checks.

**When it lands upstream:**

1. Set `project_format.SDK_ABI` to 1.7 and the new hash.
2. Run `tools/build_language_index.py`.
3. Rebuild the fixtures (`build_audio_fixtures.py`, `build_debug_fixtures.py`,
   `build_hardware_audio_check.py`): new cartridges carry the 1.7 hash.
4. Move `static/wasm/BUILD.json` `audio.revision` to the new SDK commit.

## 3. PRG32 SDK: QEMU audio clock, and a fresh mixer per cartridge (patch)

[`prg32-sdk-audio-clock-and-reset.patch`](prg32-sdk-audio-clock-and-reset.patch), against
PRG32 SDK `679dfb5`, changes two files in `components/prg32_audio`:

- **QEMU path only.** The engine advances by the audio it renders, 20 ms per buffer, and
  the buffer period stays on the emulated clock (`vTaskDelayUntil`).
- **Cartridge start** (`prg32_audio_load_block`, `prg32_audio_clear_assets`) stops the voices
  and the tracker, and sets channel volumes to 255 and pans to centre. Without this, sounds
  played before a cartridge, such as the setup menu's, change how loud its soundtrack notes
  are on the console.

With both, QEMU recordings line up over the whole recording at one fixed shift:

- console check: 531 of 546 chunks equal, against 120 of 540 before;
- conformance: 279 of 348, against 117 of 348.

The remaining chunks are frame-timed effects one 20 ms buffer apart, which come from the
phase between the audio buffers and the cartridge's frames.

The SDK's own tests pass (87) with the patch. Evidence and the full explanation are in
`docs/evidence/qemu-audio/2026-10-21-patched/`.

The background, before the patch:

On the QEMU path (`PRG32_QEMU_AUDIO_REDIRECT`), `audio_task` advances the tracker and envelopes
by the emulated clock (`esp_timer`), about 28 ms per loop. Each loop still sends exactly 20 ms
of samples and then waits for an acknowledgement. Events therefore land in earlier chunks than
on the console (`docs/evidence/qemu-audio/`). Advancing by the samples rendered (20 ms per
chunk) on that path would make QEMU sound like the console.

## 4. PRG32 SDK: QEMU audio set-up and headless runs

- The QEMU profile sets the I2S pins to −1. `detect_audio_output` then refuses to start audio,
  although QEMU sends the sound over UART1. The kit's overlay
  (`tests/fixtures/audio/sdkconfig.qemu-stereo`) works around it.
- The `esp_lcd_qemu_rgb` panel only finishes a frame when QEMU draws its display. With
  `-display none` the firmware hangs in `rgb_qemu_draw_bitmap`; SDL's dummy video driver works.
- QEMU boots into the setup menu even with one cartridge; RUN CARTRIDGE has to be chosen.

## 5. PRG32 SDK: smaller audio findings

- `tools/midi2prg32audio.py` writes the MIDI meaning of `delta` (wait before the event). The
  firmware's tracker waits after it (contract `tracker.delta`), so converted songs play one
  gap early.
- `audio_config.h` falls back to 6 voices when `CONFIG_PRG32_AUDIO_MAX_VOICES` is missing; the
  profiles say 8.
- The shipped profiles are mono. The stereo check (`docs/hardware_audio_check.md`) needs
  `CONFIG_PRG32_AUDIO_MODE_STEREO=y`.

## 6. Cartridge Store

- API tokens have no expiry. The kit refuses tokens older than `PRG32_STORE_TOKEN_MAX_DAYS`.
- The Store accepts the same cartridge id and version twice. The kit sends one bundle per id
  and version.
