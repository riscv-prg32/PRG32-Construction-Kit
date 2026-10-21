# Handoff after the audit of 951f782

This answers `docs/briefs/CLAUDE_PRG32_REFINEMENT_AFTER_AUDIT_951F782.md`. Scores are the
auditor's; `docs/capabilities.json` has only notes and evidence updated.

## Work by brief priority

| Priority | Commit | Delivered |
|---|---|---|
| 1 Patches upstream | `dc0222f` | Three pull requests, **open and not merged**, each made from a fresh clone of the canonical head with the kit's patch applied unchanged and checked again there. The kit's pins stay `679dfb5` / `f6d80ad` until the maintainers merge. |
| 2 Physical PRG32 capture | none | **Not recorded:** no console was available. Procedure, cartridge (SHA-256 `4f821b30…d712`), comparator and an evidence check that refuses incomplete records are ready (`docs/hardware_audio_check.md`). |
| 3 QEMU effect timing | `dc0222f` | One scheduling boundary, the frame clock (ADR-0021). The whole recordings are equal in QEMU, the browser core and PRG32-QT; a regression fails on a one-buffer shift. |
| 4 Delivery integrity | `46b24aa`, this commit | The evidence collector waits for the selected cartridge's identity and frames before and after the screenshot (stale/late/swap regressions). The five cartridges were delivered again with these checks. **The desktop Import menu was not driven:** computer use was not available in this session. |
| 5 Screen-reader session | none | **Not held:** it needs a person. Tasks 10–14 are ready in `docs/accessibility_session.md`. |
| 6 Integrations | none | **No test tenants** (the project owner's answer): Google Drive, OneDrive and institutional OIDC are not run; iOS stays unsupported. Live Store SSO/publishing was run (below). |

## Upstream pull requests

| Patch | Pull request | Checked in the PR's clone |
|---|---|---|
| `docs/upstream/prg32-sdk-retire-buzzer.patch` | [riscv-prg32/PRG32#45](https://github.com/riscv-prg32/PRG32/pull/45) | SDK `pytest tests` 89 passed |
| `docs/upstream/prg32-sdk-audio-clock-and-reset.patch` | [riscv-prg32/PRG32#46](https://github.com/riscv-prg32/PRG32/pull/46) | 87 passed; ESP32-C6 firmware builds with no warnings; QEMU whole recordings equal |
| `docs/upstream/prg32-qt-firmware-audio.patch` | [riscv-prg32/PRG32-QT#1](https://github.com/riscv-prg32/PRG32-QT/pull/1) | builds with no warnings; `ctest` 5/5 (device test included), OFF build 4/4; the two whole-recording hashes below |

## The scheduling boundary (Priority 3)

Frame N of a cartridge (from 0, run together with init) starts at N × 33 ms. Every audio call
made by init or by that frame takes effect at that start. The engine renders whole 20 ms
buffers, so a sound started in frame N sounds from buffer ⌊N × 33 / 20⌋.

- **Browser core** (`wasm/prg32_core_api.cpp::syncAudio`): the clock is the frame count, no
  longer the instruction-timed virtual clock. Every recorded hash is unchanged.
- **Firmware, QEMU path (#46):** after each frame the audio task renders those buffers while
  the cartridge waits. The waits of `prg32_audio_notes` are rendered the same way.
- **PRG32-QT (QT#1):** `FirmwareAudio::frameDone()` runs after every frame, including frames
  stepped in the debugger.
- **The physical console is unchanged:** its I2S DMA paces the audio. The three
  `prg32_audio_cartridge_*` calls do nothing there.

## Runtime matrix

| Runtime | Conformance, 211 frames (whole) | Console check, 331 frames (whole) | Evidence |
|---|---|---|---|
| Browser core (WebAssembly), reference | `a5af4874…5fb95b31` | `a035b9ed…6b025ef3` | `tests/fixtures/audio/`, FNV-1a hashes `2e6c5af207d3d5f2` / `a3d2c6520ba8aea2` unchanged |
| Native build of the same core | identical | identical | `test_the_native_build_renders_the_same_samples` |
| PRG32-QT `f6d80ad` + QT#1 (`prg32qt-headless --audio-wav`) | identical | identical | this handoff; `tests/test_prg32qt_firmware_audio.py` |
| PRG32 firmware in QEMU + #46, 3 runs each | **348/348 buffers, identical** | **546/546, identical** | `docs/evidence/qemu-audio/2026-10-21-frame-clock/` |
| PRG32 firmware in QEMU, first version of the patch | 279/348 | 531 or 502 of 546 | `…/2026-10-21-patched/` (history) |
| PRG32 console | not recorded | not recorded | `docs/hardware_audio_check.md` |

The full SHA-256 values are in the evidence README.

Regressions:

- `test_frame_triggered_effects_sound_from_their_frames_buffer`: the drum, held note and stop
  land in buffers 330, 379 and 404;
- `test_a_one_buffer_shift_of_one_effect_breaks_whole_recording_equality`;
- `test_qemu_firmware_equals_the_browser_core_over_the_whole_recording`;
- opt-in `test_live_qemu_audio_does_not_drift`, which builds #46 and now requires whole
  equality.

## Delivery (Priority 4)

`docs/evidence/delivery/2026-10-21-prg32qt-checked/`:

- Setup: canonical PRG32-QT `f6d80ad`, offscreen, isolated HOME, web API, slot `cart3`.
- The cartridges: Blocks as C, Blocks as assembly, Advanced C, handwritten assembly, and
  the console check.
- For each one, PRG32-QT reported that cartridge (name and code size) loaded before and
  after its screenshot, with frames advancing. Screenshots and SHA-256 are kept, and
  `test_the_checked_prg32_qt_delivery_shows_each_cartridge_running_itself` enforces them.
- The first record (`2026-10-21-prg32qt/`) took the handwritten-assembly screenshot while
  `audio-check` was still reported.

## Commands and results (macOS, this machine)

| Command | Result |
|---|---|
| Full `pytest` with `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, the RISC-V toolchain on PATH and the SDK on `PYTHONPATH` | **1155 passed, 0 failed, 45 skipped** |
| `PRG32_LIVE_STORE=local pytest tests/test_store_live.py tests/test_sso_live.py` (loopback CartridgeStore) | 11 passed |
| `PRG32_LIVE_QEMU=1 pytest -k live_qemu` (ESP-IDF v5.4, Espressif QEMU 9.0.0) | 1 passed |
| `service_worker_lock --check` (cache `prg32-kit-v20`), `render_capabilities` | ok |
| PRG32 SDK `pytest tests`, in the PR clones | 89 (#45), 87 (#46) |
| PRG32-QT `ctest`, PR clone, default / OFF | 5/5 / 4/4 |

The 45 skips:

| Tests | Why |
|---|---|
| live Store, 11 | run separately above, all passed |
| live OIDC, 9 | no tenant |
| live cloud, 7 | no tenant |
| bubblewrap, 6, and RLIMIT, 1 | Linux only; CI runs them |
| host-GCC assembly comparison, 9 | needs a host GCC with the PRG32 argument order (CI) |
| live QEMU, 1 | passed separately |
| empty console-evidence set, 1 | no physical capture yet |

## Exceptions

1. The patches are proposed, not merged: canonical PRG32 still publishes the buzzer, and
   canonical PRG32-QT still mixes with its own renderer. **Complete audio support is not
   claimed.**
2. No physical stereo capture and no physical delivery (no console available).
3. The PRG32-QT desktop Import menu was not driven: computer use was not available in this
   session. The API delivery with integrity checks is recorded instead.
4. No human screen-reader session.
5. No Google Drive, OneDrive or institutional OIDC tenant; iOS stays unsupported/unverified.
