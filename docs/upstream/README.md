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

## 2. PRG32 SDK: retire the buzzer from the portable ABI (proposal, no patch)

The kit already treats the buzzer as obsolete. It refuses it in C and assembly, lists it only
as obsolete in the editor, and keeps old cartridges silent while counting their calls
(contract `legacy_buzzer`). The SDK at `679dfb5` still publishes it:

| Where | What |
|---|---|
| `components/prg32/include/prg32.h` | `prg32_buzzer_tone`, `prg32_buzzer_play_notes`, `prg32_buzzer_sample_u8` |
| `prg32/abi/prg32_abi.json` → `abi_gen.py` → `prg32_abi_index.h`, `abi_generated.py`, `prg32_abi_table.c`, `prg32_abi_exports.c` | ABI entries 5, 7, 8 |
| `examples/games/*` (4 C files and 13 assembly files), `cartridges/devicedemo` | calls to `prg32_buzzer_tone` |
| `components/prg32/prg32_audio.c`, `prg32_system.c`, `prg32_splash.c`, `prg32_led.c`, `Kconfig`, `main/prg32_config.h`, a pin profile | the board's PWM buzzer driver (setup and splash sounds) |
| 13 documentation pages | the buzzer API and wiring |

The kit's proposed policy:

- keep indices 5, 7 and 8 reserved, so no other entry moves, and point them at one silent
  stub;
- remove the declarations and the JSON entries, and regenerate the derived files;
- bump the ABI's minor version;
- move the examples to `prg32_audio_note`;
- keep the PWM driver private to the firmware, or remove it, as the SDK decides.

Do not reinterpret old calls as another sound command. When the SDK changes, run
`tools/build_language_index.py` in the kit. `tests/test_audio_contract.py` reads the SDK
and will show what moved.

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
