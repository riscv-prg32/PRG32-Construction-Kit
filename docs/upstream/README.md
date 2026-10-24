# Upstream proposals from the kit

The kit never changes the PRG32 SDK, PRG32-QT or the Cartridge Store. When kit work finds
something one of them should change, it is written here. If the kit could prove the change,
it is a patch, built and tested against a copy of that repository.

**Pull requests (2026-10-21, open, not merged).** Each was made from a fresh clone of the
canonical head (PRG32 `679dfb5`, PRG32-QT `f6d80ad`) with the patch below applied unchanged,
and checked again there:

| Patch | Pull request |
|---|---|
| §1 `prg32-qt-firmware-audio.patch` | [riscv-prg32/PRG32-QT#1](https://github.com/riscv-prg32/PRG32-QT/pull/1) |
| §2 `prg32-sdk-retire-buzzer.patch` | [riscv-prg32/PRG32#45](https://github.com/riscv-prg32/PRG32/pull/45) |
| §3 `prg32-sdk-audio-clock-and-reset.patch` | [riscv-prg32/PRG32#46](https://github.com/riscv-prg32/PRG32/pull/46) |

The kit keeps pinning `679dfb5` and `f6d80ad` until the maintainers merge. After that, follow
"When it lands upstream" in §2 and move `static/wasm/BUILD.json` to the merged SDK commit.

## 1. PRG32-QT: render sound with the PRG32 firmware's engine (patch)

**Problem.** PRG32-QT mixes sound with its own floating-point renderer (`QtAudioEngine`). It
has no ADSR envelopes, so the desktop does not sound like the console and cannot be an audio
reference.

**Patch.** [`prg32-qt-firmware-audio.patch`](prg32-qt-firmware-audio.patch), against PRG32-QT
`f6d80ad`, compiles the SDK's `components/prg32_audio` unchanged into PRG32-QT. It uses the
same port as the kit's browser core: `src/core/firmware_audio/` is the kit's `wasm/audio/`.

- **On by default** (`PRG32QT_FIRMWARE_AUDIO=ON`). With no `PRG32_SDK_DIR`, CMake fetches
  the SDK at `PRG32_SDK_REVISION` (`679dfb5`), sources only, so the SDK's ESP-IDF build is
  never configured. `-DPRG32QT_FIRMWARE_AUDIO=OFF` keeps the older mixer, documented as not
  an audio reference.
- It adds:
  - host-call hooks in `Runtime`;
  - `FirmwareAudio`, which drives the engine from the cartridge's audio calls;
  - in `prg32qt-headless`, `--audio-wav` and an `AUDIO … pcm_fnv1a=` line;
  - in the desktop app, the engine's PCM played through `QtAudioEngine` (resampled to the device).
- **The frame clock** (ADR-0021, §3): `FirmwareAudio::frameDone()` after every frame, run or
  stepped in the debugger. Audio calls take effect at their frame's start (N × 33 ms), so
  whole recordings equal the browser core's and the firmware's in QEMU: the console check
  over 331 frames and the conformance cartridge over 211 frames have the same SHA-256 in all
  three (`a035b9ed…`, `a5af4874…`).
- **Output device test.** `prg32qt_audio_device_check` (a CTest test, skipped without an
  output device) runs a cartridge in real time and plays it through the default output
  device. It checks the device processed the time, and that the frames the device pulled are
  exactly the engine's samples.

**Proof:**

| Check | Result |
|---|---|
| Clean PRG32-QT with the patch, default options (SDK fetched from GitHub at `679dfb5`) | builds; conformance hash `2e6c5af207d3d5f2`, as the browser core |
| PRG32-QT's CTest suite (default options, desktop app included) | 5/5, including the device test |
| Same, `-DPRG32QT_FIRMWARE_AUDIO=OFF` | 4/4 (no device test) |
| Device test on macOS 26.6.2, Qt 6.11.2, *LG UltraFine Display Audio* | Bach 2.68 s and the console check 3.67 s processed; the device's frames equal the engine's samples (`docs/evidence/prg32qt-audio/2026-10-21/`) |
| `tests/test_prg32qt_firmware_audio.py` (kit, in CI) | the patch applies; the default build of `prg32qt-headless` gives the browser core's hashes for the conformance fixture and the console check; old buzzer cartridges are silent and counted |

The device test proves what the device takes, not what a listener hears.

```bash
cd PRG32-QT && git apply ../PRG32-Construction-Kit/docs/upstream/prg32-qt-firmware-audio.patch
cmake -S . -B build && cmake --build build && (cd build && ctest)
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

## 3. PRG32 SDK: the audio frame clock in QEMU, and a fresh mixer per cartridge (patch)

[`prg32-sdk-audio-clock-and-reset.patch`](prg32-sdk-audio-clock-and-reset.patch), against
PRG32 SDK `679dfb5`, changes `components/prg32_audio` and `main/main.c`:

- **One scheduling boundary (QEMU path only).** While a cartridge runs, its frames drive
  the audio. Frame N (from 0, run together with init) starts at N × 33 ms, and every audio
  call made by init or by that frame takes effect at its start. After each frame
  (`prg32_audio_cartridge_frame(33)`, in `main.c`) the audio task renders the whole 20 ms
  buffers up to the next frame's start and the cartridge waits for them. The waits inside
  `prg32_audio_notes` are rendered the same way. A sound started in frame N sounds from
  buffer ⌊N × 33 / 20⌋ on every run. The kit's browser core and PRG32-QT (§1) follow the
  same rule (ADR-0021). The rule is declared in a new header,
  `prg32_audio_frame_clock.h`.
- **Outside a cartridge** (setup menu, QEMU path), the engine advances by the audio it
  renders, 20 ms per buffer, on the emulated clock (`vTaskDelayUntil`).
- **On the console nothing changes.** The I2S DMA paces the audio task there, and the
  three `prg32_audio_cartridge_*` calls do nothing.
- **Cartridge start** (`prg32_audio_load_block`, `prg32_audio_clear_assets`) stops the voices
  and the tracker, and sets channel volumes to 255 and pans to centre. Without this, sounds
  played before a cartridge, such as the setup menu's, change how loud its soundtrack notes
  are on the console.

Result in QEMU (`-icount shift=3,sleep=off`): **the whole recordings equal the browser core's,
sample for sample, in every run.** Three runs of each, with the same aligned SHA-256:

| Recording | Before the patch | First version of the patch | Now |
|---|---|---|---|
| Console check, 11 s | 120 of 540 chunks | 531 of 546 (two phases) | **546 of 546** |
| Conformance, 7 s | 117 of 348 | 279 of 348 | **348 of 348** |

Evidence: `docs/evidence/qemu-audio/2026-10-21-frame-clock/`. The patched SDK's own tests pass
(87; 89 together with §2), the firmware builds for the ESP32-C6 console with no warnings, and the kit's browser core built from the
patched audio sources gives the recorded hashes (`2e6c5af207d3d5f2`, `a3d2c6520ba8aea2`).

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

### 6.1 Shared identity with the kit (patch)

**Problem.** From `4a3138b` (GDPR remediation) the Store's `/api/me` returned its new public
handle (`player-…`) as `username`. The kit documents one shared username, so a kit user
signed in to the Store saw another name. The same commit also redirected `/api/me` and
every other `/api/` call to the privacy-notice page until it was acknowledged, and answered
an unsigned `POST /api/…` with a CSRF `400` instead of `401`. Authentication itself was
never weakened.

**Chosen model (2026-10-22, raffmont): shared username, private handle.**

- The **account username** is the sign-in name both services share. It is private: the
  Store returns it only to its owner (`/api/me`), and the kit as today.
- The Store's **public handle** is the only name other people see (catalog, scores,
  reviews, multiplayer). It is pseudonymous and is never made from the username or email
  for an account that arrives over SSO.
- **Same email = same person.** Accounts are matched by email over SSO, never by username
  or handle. If the Store already has another account with the kit's username, the kit's
  account gets its own Store account named by its email; the two are never joined.
- The SSO protocol (`sso_protocol.py`, ABI unchanged) and its tickets, issuer/subject
  identities, roles and scopes are unchanged.

**Patch.** [`cartridge-store-shared-identity.patch`](cartridge-store-shared-identity.patch),
against CartridgeStore `4a3138b` (`git am`):

- `Principal.as_dict()` (`/api/me`) gives `username` = the account username and
  `public_handle` beside it (`name` stays the handle); `public_dict()` is what other people
  see, and multiplayer errors use it (they no longer carry the email);
- SSO sign-in shows the Store's privacy notice once per notice version, as a local sign-in
  does (before, every SSO sign-in asked again);
- while the notice is pending, `/api/me` answers with `"privacy_notice_pending": true` and
  other `/api/` routes answer `403 privacy_notice_required` in JSON, not an HTML redirect;
- an `/api/` `POST` with no signed-in session and no Bearer token gets `401`; a signed-in
  browser still needs its CSRF token;
- the Store's `tests/test_privacy.py` reads the handle from `public_handle`; the new
  `tests/test_shared_identity.py` covers the contract, a username collision, a rename onto a
  taken username, a handle equal to another username, migration of pre-handle accounts, the
  notice gate and the CSRF order. Its `docs/api.md` and `docs/gdpr.md` describe the model.

**Kit side** (this repository): `tests/test_sso_with_cartridge_store.py` adds the contract
and the collision test; `tests/test_store_live.py` and `tests/test_sso_live.py` sign in on
the Store's forms as a browser does (the CSRF token from `<meta name="csrf-token">`, then
the notice acknowledged once). They pass against both Store revisions.

**Proof (2026-10-22, macOS, Python 3.12.10):**

| Store revision | Store's own tests | Kit cross-repository suite* |
|---|---|---|
| `820f74b` (the kit's CI pin, `contracts/prg32-store-contract-1.json`) | n/a | 89 passed |
| `4a3138b` (Store `main`), unpatched | 81 passed† | 6 failed, 83 passed |
| `4a3138b` + this patch | 91 passed | 89 passed |

\* `PRG32_CARTRIDGE_STORE_SOURCE=<clone> PRG32_LIVE_STORE=local PRG32_REQUIRE_STORE=1 python3 -m pytest -q
tests/test_store_contract.py tests/test_store_live.py tests/test_sso_with_cartridge_store.py
tests/test_sso.py tests/test_sso_live.py tests/test_publish_authorization.py`, each Store a
fresh clone of the canonical repository. † Without the new `test_shared_identity.py`.

The unpatched failures are the username (3 tests), the notice redirect of `/api/me`, the
CSRF `400` on the SSO live test's role change, and the unsigned upload getting `400`.

```bash
cd CartridgeStore && git am ../PRG32-Construction-Kit/docs/upstream/cartridge-store-shared-identity.patch
python3 -m pytest -q tests
```

**When it lands upstream:** move `store_reference.checked_against` in
`contracts/prg32-store-contract-1.json` to the merged commit (CI's Store job checks out that
commit), regenerate `tests/fixtures/contract/` with `tools/build_contract_fixtures.py`, and
run the suite above.

### 6.2 Other records

- API tokens have no expiry. The kit refuses tokens older than `PRG32_STORE_TOKEN_MAX_DAYS`.
- The Store accepts the same cartridge id and version twice. The kit sends one bundle per id
  and version.
- `POST /api/publish/bundle` asks only for a signed-in user, not the publisher role, and the
  submission does not record who sent it. The kit's publisher check is what stops a student;
  `tests/test_sso_live.py::test_store_bundle_upload_checks_sign_in_only` fails when the Store
  changes this, so the record can be updated.
