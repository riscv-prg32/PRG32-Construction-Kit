# Upstream proposals from the kit

The kit never changes the PRG32 SDK, PRG32-QT or the Cartridge Store. When kit work finds
something one of them should change, it is written here. If the kit could prove the change,
it is a patch, built and tested against a copy of that repository.

**Where the proposals stand (2026-11-04).** The kit follows the `main` branches: PRG32 `1fa8474`
and PRG32-QT `7683be1` (`static/wasm/BUILD.json`).

| Proposal | Pull request | State |
|---|---|---|
| §1 PRG32-QT plays sound with the firmware's audio engine | [riscv-prg32/PRG32-QT#1](https://github.com/riscv-prg32/PRG32-QT/pull/1) | **merged** (`7683be1`, 2026-11-01) |
| §1.1 PRG32-QT builds against SDK `main` (`prg32-qt-sdk-main.patch`) | none yet | **new**, waits for the maintainer's go-ahead |
| §2 PRG32 SDK retires the buzzer (`prg32-sdk-retire-buzzer.patch`) | [riscv-prg32/PRG32#45](https://github.com/riscv-prg32/PRG32/pull/45) | **closed without merging** (2026-11-03); the patch, rebased onto `1fa8474`, stays the kit's record |
| §3 PRG32 SDK audio frame clock and fresh mixer | [riscv-prg32/PRG32#46](https://github.com/riscv-prg32/PRG32/pull/46) | the pull request was closed, but its commit is **in `main`** (`01663b7`), with later fixes by upstream (`1fa8474`) |

The kit keeps refusing the buzzer on its own side whatever the SDK does (ADR-0021,
`tests/test_no_buzzer.py`). The §1 and §3 patch files stay here unchanged: the evidence recorded
with them names them.

## 1. PRG32-QT: render sound with the PRG32 firmware's engine (patch)

**Merged** as riscv-prg32/PRG32-QT#1 (`7683be1`). What follows describes the patch as it was
proposed; the kit's `wasm/audio/` is now the same, file for file, as PRG32-QT's
`src/core/firmware_audio/` with §1.1 applied (`tests/test_prg32qt_firmware_audio.py`).

**Problem.** PRG32-QT mixes sound with its own floating-point renderer (`QtAudioEngine`). It
has no ADSR envelopes, so the desktop does not sound like the console and cannot be an audio
reference.

**Patch.** [`prg32-qt-firmware-audio.patch`](prg32-qt-firmware-audio.patch), against PRG32-QT
`b98a6aa`, compiles the SDK's `components/prg32_audio` unchanged into PRG32-QT. It uses the
same port as the kit's browser core: `src/core/firmware_audio/` is the kit's `wasm/audio/`.

- **On by default** (`PRG32QT_FIRMWARE_AUDIO=ON`). With no `PRG32_SDK_DIR`, CMake fetches
  the SDK at `PRG32_SDK_REVISION` (`1eff2e2`), sources only, so the SDK's ESP-IDF build is
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
| Clean PRG32-QT `b98a6aa` with the patch, default options (SDK fetched from GitHub at `1eff2e2`), 2026-11-01, macOS, Homebrew Qt 6.11.2 | builds with no warnings |
| PRG32-QT's CTest suite (default options, desktop app included) | 5/5, including the device test |
| Same, `-DPRG32QT_FIRMWARE_AUDIO=OFF` | 4/4 (no device test) |
| Device test on macOS 26.6.2, Qt 6.11.2, *LG UltraFine Display Audio* (2026-10-21, on `f6d80ad`) | Bach 2.68 s and the console check 3.67 s processed; the device's frames equal the engine's samples (`docs/evidence/prg32qt-audio/2026-10-21/`) |
| `tests/test_prg32qt_firmware_audio.py` (kit, in CI; rerun on `b98a6aa` + the SDK at `1eff2e2`) | the patch applies; the default build of `prg32qt-headless` gives the browser core's hashes for the conformance fixture and the console check; old buzzer cartridges are silent and counted |

The device test proves what the device takes, not what a listener hears.

```bash
cd PRG32-QT && git apply ../PRG32-Construction-Kit/docs/upstream/prg32-qt-firmware-audio.patch
cmake -S . -B build && cmake --build build && (cd build && ctest)
```

### 1.1 PRG32-QT: build against SDK `main` (patch)

**Problem.** PRG32-QT `7683be1` fetches the SDK at `679dfb5`. With SDK `main` (`1fa8474`) its
firmware audio build stops: the engine's `audio.c` now includes `esp_log.h` and creates a binary
semaphore (`xSemaphoreCreateBinary`), and the port's shim has neither.

**Patch.** [`prg32-qt-sdk-main.patch`](prg32-qt-sdk-main.patch), against PRG32-QT `7683be1`:
`src/core/firmware_audio/shim/esp_log.h` (the four log macros, doing nothing), one line in
`shim/freertos/semphr.h`, and `PRG32_SDK_REVISION` moved to `1fa8474`.

| Check (2026-11-04, macOS, clean clones) | Result |
|---|---|
| PRG32-QT `7683be1`, unpatched, `-DPRG32_SDK_DIR=` SDK `1fa8474` | does not build (`'esp_log.h' file not found`) |
| Same with the patch, `prg32qt-headless` and the core library | builds, no warnings |
| PRG32-QT's CTest suite (`-DPRG32QT_BUILD_APP=OFF`) | 4/4 |
| Conformance cartridge, 170 frames | `pcm_fnv1a=2e6c5af207d3d5f2`, the browser core's |
| `tests/test_prg32qt_firmware_audio.py` (kit) | 5 passed: the kit's port equals PRG32-QT's with the patch; conformance, console check and old buzzer cartridges as the browser core |

## 2. PRG32 SDK: retire the buzzer from the portable ABI (patch)

**Closed without merging** (riscv-prg32/PRG32#45, 2026-11-03). The patch is kept up to date for
the record: [`prg32-sdk-retire-buzzer.patch`](prg32-sdk-retire-buzzer.patch), against PRG32 SDK
`1fa8474` (`main`; rebased 2026-11-04 with exactly the same changed lines as on `1eff2e2`),
implements this policy:

- **ABI 1.9.** Entries 5, 7 and 8 (`prg32_buzzer_tone`, `_play_notes`, `_sample_u8`) are
  marked `"retired"` (`"since": "1.9"`) in `prg32_abi.json`. They keep their slot, so the other
  141 entries never move, and point at one silent stub, `prg32_abi_retired_silent`, which returns 0.
  They have no import name (`IMPORT_NAMES` holds `None`), and the generator writes
  `PRG32_ABI_FN_RETIRED_n`. `abi_gen.py` and its users understand retired slots.
- **Old cartridges.** The 1.8 hash (`0x71b93e23`) joins the 1.6 and 1.7 ones in
  `compatible_hashes`, so cartridges built before 1.9 still load, and their buzzer calls do
  nothing. No call is reinterpreted as a synthesizer call. The SDK's prefix test proves each
  compatible hash again from the table with the retired marks removed.
- **New source.** `prg32.h` no longer declares the calls or `prg32_note_t`. C calling them
  fails to compile, and assembly calling them fails to link (the portable stubs have no
  symbol). The firmware keeps its own PWM driver for boards with a buzzer pin, in a private
  header (`components/prg32/prg32_buzzer.h`), for the setup menu and the splash.
- **Examples and docs.** 4 C games, 13 assembly files and `devicedemo` play
  `prg32_audio_note` or `prg32_audio_notes`, with the nearest MIDI note in a comment. The
  sound lab, the tutorial, the framework manual and the audio pages say what to use instead.
  The rebase also removes two passages upstream added after `679dfb5` (the framework manual and
  `docs/usage/qemu.md`: "buzzer calls remain audible in QEMU"), and `docs/software/abi.md`
  describes minor 9.
- **Not covered:** `tools/prg32_audio_convert.py --format c` (and `docs/tools/assets.md`) still
  write a `prg32_note_t` melody, which no longer compiles. It did before the rebase too.

On `1fa8474` (2026-11-04, macOS, without `pyserial`): the SDK's own tests give 194 passed and the
same 7 `test_find_port` failures as unpatched `main` (192 passed); `tests/test_upstream_sdk_patches.py`
passes. What was checked in clean clones of `1eff2e2` (2026-11-01, macOS):

| Check | Result |
|---|---|
| The SDK's own tests (with `pyserial`), 2 new tests (retired slots, no public buzzer, stub offsets) | 191 passed, 3 skipped (189 before) |
| `python3 -m prg32 abi check` | generated files match |
| The 18 changed example and cartridge sources, built with the RISC-V toolchain (`--portable`) | 18 built, each with hash `0xa9f89cec` |
| A C file calling `prg32_buzzer_tone` | does not compile (implicit declaration) |
| The same call in assembly | does not link (`undefined reference`) |
| QEMU firmware with both patches, the kit's 1.6 `legacy_buzzer.prg32` | loads; 3 s of exact silence, equal to the browser core |
| Same firmware, a cartridge built with the unpatched SDK (1.8) calling all three buzzer calls, then a note | loads; the buzzer calls do nothing; 150 of 150 buffers equal to the browser core |
| ESP32-C6 firmware with both patches (`pcb1` profile) | builds; no warnings from PRG32's sources |

QEMU evidence: `docs/evidence/qemu-audio/2026-11-03-rebased/`.

`tests/test_upstream_sdk_patches.py` (in CI) applies the patch to a copy of the pinned SDK and
repeats the ABI, header and example checks.

**How the kit's tests reach it, until it lands.** The Store tests (`test_store_contract.py`,
`test_store_live.py`, `test_sso_with_cartridge_store.py`, `tools/run_live_suites.py`) take the
Store from [`tools/pinned_store.py`](../../tools/pinned_store.py):
`PRG32_CARTRIDGE_STORE_SOURCE` when it is set (CI's own pin), else the Store next to the kit
when it already has the contract (`tests/test_shared_identity.py`), else a clean clone of it at
`4a3138b` with this patch applied by `git am`, in `build/pinned-store/4a3138be6784-shared-identity`.
The Store next to the kit is only cloned, never changed.

Rerun 2026-10-26 (macOS, Python 3.12.10), adjacent Store at `4a3138b`, clean, unchanged after
the run; the clone at `8426331` (`4a3138b` + this patch):

| Suite | Result |
|---|---|
| Store's own tests in the clone (`python3 -m pytest -q tests`) | 91 passed |
| Kit cross-repository suite* (no `PRG32_CARTRIDGE_STORE_SOURCE`) | 89 passed |
| of which `tests/test_sso_with_cartridge_store.py` (username shared, handle public only, same-username Store account never joined, registration, admin changes and deletes, both-way sign-on, publish, sync) | 9 passed |

**When it lands upstream:**

1. PRG32-QT must accept the 1.9 hash `0xa9f89cec` (`Runtime.h`, `CurrentAbiHash`, with
   `0x71b93e23` moved to the compatible ones), and the kit's browser core rebuilt from it.
   Until then a 1.9 cartridge is refused there as an incompatible ABI.
2. Set `project_format.SDK_ABI` to 1.9 and `0xa9f89cec`, and add `0x71b93e23` to
   `SDK_COMPATIBLE_ABI_HASHES`.
3. Run `tools/build_language_index.py`.
4. Rebuild the fixtures (`build_audio_fixtures.py`, `build_debug_fixtures.py`,
   `build_hardware_audio_check.py`): new cartridges carry the 1.9 hash.
5. Move `static/wasm/BUILD.json` `audio.revision` to the new SDK commit.

## 3. PRG32 SDK: the audio frame clock in QEMU, and a fresh mixer per cartridge (patch)

**In `main`** since `01663b7` (the commit of riscv-prg32/PRG32#46), followed by upstream's own
fixes in `1fa8474`: the audio task waits for the old task's exit without a time limit, runs at
`tskIDLE_PRIORITY + 6`, and stops waiting for the QEMU audio player after 500 ms without one. The
kit's browser core is built from that engine. The text below describes the patch as proposed.

[`prg32-sdk-audio-clock-and-reset.patch`](prg32-sdk-audio-clock-and-reset.patch), against
PRG32 SDK `1eff2e2`, changes `components/prg32_audio` and `main/main.c`:

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

Evidence: `docs/evidence/qemu-audio/2026-10-21-frame-clock/`, recorded at `679dfb5` with the
patch kept beside it (`tests/test_audio_conformance.py` checks that today's patch changes exactly
the same lines). Rerun on `1eff2e2` with the rebased patch (`docs/evidence/qemu-audio/2026-11-03-rebased/`):
the console check gives 546 of 546 buffers and the conformance cartridge, with §2 as well, 348 of
348, with the same SHA-256 as above; the SDK's own tests pass (189; 191 with §2). On 2026-10-21 the
patched SDK's own tests passed (87; 89 together with §2), the firmware builds for the ESP32-C6 console with no warnings, and the kit's browser core built from the
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
