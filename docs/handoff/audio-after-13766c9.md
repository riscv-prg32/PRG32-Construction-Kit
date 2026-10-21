# Audio handoff after the audit of 13766c9

This answers `docs/briefs/CLAUDE_PRG32_AUDIO_REFINEMENT_AFTER_AUDIT_13766C9.md` for the auditor.
Scores are the auditor's; `docs/capabilities.json` has only notes and evidence updated.

**Scope decision (project owner):** the kit does not change the PRG32 SDK, PRG32-QT or the
Cartridge Store. Where the brief asks for a change there, the kit delivers a patch proven
against a copy, or a written proposal (`docs/upstream/README.md`).

## Commits by work area

| Area | Commits | What |
|---|---|---|
| 1. Retire the buzzer in the canonical ABI | `0263deb` (proposal only) | inventory and policy in `docs/upstream/README.md` §2; the SDK is unchanged at the owner's request |
| 2. Renderer divergence | `0263deb` | `docs/upstream/prg32-qt-firmware-audio.patch`; `tests/test_prg32qt_firmware_audio.py` (in CI) |
| 3. Firmware/QEMU stereo capture | `6dbb471` | `tools/qemu_audio_capture.py --build`; `docs/evidence/qemu-audio/2026-10-21/` |
| 4. Physical path | `37614c5`, `6dbb471` | the console-check cartridge, `tools/hardware_audio_compare.py`, `docs/hardware_audio_check.md` |
| 5. Product evidence | `be5190c` | keyboard-only, archive and Compile browser scenarios; CI keeps PCM, traces and failure screenshots |
| Defect found on the way | `bffa043` | AudioStudio soundtracks played each note one gap early (tracker delta semantics); fixed, contract `tracker.delta` |

## Supported-runtime matrix

| Runtime | Engine | Result on the 8-voice fixtures | Evidence |
|---|---|---|---|
| Browser (WebAssembly) | PRG32 firmware `components/prg32_audio`, kit port | reference: conformance `2e6c5af207d3d5f2`, console check `a3d2c6520ba8aea2` | `tests/test_audio_conformance.py`, `tests/fixtures/audio/hardware/BUILD.json` |
| Native build of the same core | same | bit-identical | `test_the_native_build_renders_the_same_samples` |
| PRG32-QT with the proposed patch | same, linked into PRG32-QT | bit-identical (both hashes) | `tests/test_prg32qt_firmware_audio.py` |
| PRG32-QT as released (`f6d80ad`) | own float mixer, no ADSR | not a reference | `docs/upstream/README.md` §1 |
| PRG32 firmware in QEMU (`679dfb5`, ESP-IDF 5.4, QEMU 9.0.0 esp) | the firmware itself | equal sample for sample between events: 76/234 and 66/269 sounding 20 ms chunks; QEMU's clock moves events earlier (upstream §3) | `docs/evidence/qemu-audio/`, `test_the_qemu_firmware_evidence_still_holds` |
| PRG32 console (ESP32-C6, stereo) | the firmware itself | **not recorded yet** | `docs/hardware_audio_check.md` (I2S capture with a logic analyser; bit-exact single-voice checks) |

## Hashes

- Console-check cartridge, the same portable bytes for esp32c6 and qemu:
  `4f821b3047dcb9d000cc1a94f7b7c4ab8f2d707f018593eee66b787cf379d712`.
- Its AUD0 block: `28a65e5d5c2b22609cb8d248b89255d638da5a8f39623fda6c8d07d01f0e5577`.
- Built with riscv32-esp-elf-gcc 14.2.0 (esp-14.2.0_20241119) and PRG32 SDK `679dfb5`.
- Reproduce with `tools/build_hardware_audio_check.py --check`; CI runs it in the toolchain
  container when the toolchain versions match.
- The QEMU firmware recordings, their hashes and segment tables are in each
  `comparison.json` under `docs/evidence/qemu-audio/2026-10-21/`.
- CI artifacts per commit: `audio-evidence-<sha>` (conformance PCM as WAV and per-frame voice
  trace) and `browser-test-results-<sha>` (junit; screenshots on failure).

## Commands run (macOS, this machine)

| Command | Result |
|---|---|
| `python3 -m pytest -q` with `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, PRG32-QT and SDK checkouts | see "Final run" below |
| `tools/service_worker_lock.py`, `render_capabilities.py`, `build_language_index.py`, `build_contract_fixtures.py`, `make_sbom.py`, `lock_requirements.py` with `--check` | ok |
| `tools/build_audio_fixtures.py --check`, `tools/build_hardware_audio_check.py --check` (toolchain) | ok |
| `tools/build_wasm.py --check` | up to date |
| `ruff check .`, `git diff --check` | clean |
| `tools/qemu_audio_capture.py` on both cartridges | `docs/evidence/qemu-audio/2026-10-21/` |
| PRG32-QT `ctest` with and without `PRG32QT_FIRMWARE_AUDIO` (scratch clone) | 4/4 and 4/4; desktop app builds with the option |

## ABI migration notes (buzzer)

The kit's policy is in force for kit-built PRG32 cartridges:

- the buzzer is refused at authoring time, in C and in assembly;
- old cartridges run silently, and their calls are counted (browser core, and PRG32-QT with the
  patch);
- nothing reinterprets an old call as another sound.

The SDK change proposed in `docs/upstream/README.md` §2 keeps indices 5, 7 and 8 reserved,
points them at a silent stub, removes the declarations and JSON entries, regenerates the
derived files, bumps the ABI minor version and moves 17 example files and `devicedemo` to
`prg32_audio_note`.

## Remaining exceptions

1. **No console recording.** The cartridge, the procedure and the strict comparison are ready.
   A person with a stereo-wired console and a logic analyser has to run it and commit the
   result to `docs/evidence/hardware-audio/`.
2. **The SDK still exports the buzzer** in its portable ABI. This is proposed, not changed.
3. **The PRG32-QT patch is not merged upstream.** Its desktop playback was built but not
   heard.
4. **QEMU event timing differs from the console** (upstream §3), so the QEMU comparison is
   exact between events, not over the whole recording.
5. **No human screen-reader session** for AudioStudio. Tasks 10–14 are in
   `docs/accessibility_session.md`.

## Final run

With `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, the PRG32-QT and SDK checkouts and the RISC-V
toolchain on PATH, the full suite finished with 1123 passed, 1 failed and 38 skipped. The
failure was `test_ci_runs_every_browser_suite_and_forbids_skipping`, which still expected the
old single-line artifact `path:`. It was fixed with this handoff, and its file then passed
(58/58).

The 38 skips are the opt-in live suites (Store, cloud, identity provider) and the bubblewrap
sandbox tests, which need Linux user namespaces; CI's container job runs those. During
the work, `tests/test_no_buzzer.py` failed at `37614c5` and `6dbb471`, and the CI workflow
test failed from `be5190c`. Both pass now.
