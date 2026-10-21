# Audio handoff after the audit of f4b74bc

This answers `docs/briefs/CLAUDE_PRG32_AUDIO_REFINEMENT_AFTER_AUDIT_F4B74BC.md`. Scores are
the auditor's; `docs/capabilities.json` has only notes and evidence updated.

**Scope (project owner's decision):** the kit does not change the PRG32 SDK or PRG32-QT. Their
changes are delivered as patches, built and tested against clean clones, with evidence.
There are **no canonical upstream commits or PRs yet**, so the kit's SDK and PRG32-QT pins are
unchanged (`679dfb5`, `f6d80ad`). The two human sessions (console capture, screen reader) are
prepared; neither has been held.

## Work by brief section

| § | Commit | Delivered |
|---|---|---|
| 1 Buzzer out of the SDK ABI | `ca2e232` | `docs/upstream/prg32-sdk-retire-buzzer.patch`: ABI 1.7; slots 5/7/8 kept and pointing at a silent stub; no import name and no public declaration; the 1.6 hash compatible; generator and builder understand retired slots; 4 C games, 13 assembly files and `devicedemo` migrated; docs updated. Kit: the index builder skips retired slots; `tests/test_upstream_sdk_patches.py` (CI). |
| 2 PRG32-QT firmware engine | `112999d` (builds on `0263deb`) | `docs/upstream/prg32-qt-firmware-audio.patch`: the firmware engine by default (SDK fetched at the pinned commit when no folder is given; OFF keeps the old mixer); an output-device test. |
| 3 QEMU audio time | `46b2a97` | `docs/upstream/prg32-sdk-audio-clock-and-reset.patch`: the QEMU path advances by rendered audio and keeps the period on the emulated clock; a fresh mixer per cartridge. That second change fixes a console bug: sounds played before a cartridge (such as the setup menu's) left a voice quieter. Before/after evidence and a drift regression. |
| 4 Physical stereo capture | `37614c5`, `2cf9449` | Ready, **not recorded**. The cartridge (SHA-256 `4f821b30…d712`), the procedure, the I2S/microphone comparator, the firmware note, and a test that refuses incomplete evidence. |
| 5 Screen-reader session | `2cf9449` | Ready, **not held**. Tasks 10–14 and the record format in `docs/accessibility_session.md`. |

## Supported-runtime matrix

| Runtime | Conformance fixture | Console check | Evidence |
|---|---|---|---|
| Browser (WebAssembly), reference | `2e6c5af207d3d5f2` | `a3d2c6520ba8aea2` | `tests/fixtures/audio/expected.json`, `hardware/BUILD.json` |
| Native build of the same core | identical | identical | `test_the_native_build_renders_the_same_samples` |
| PRG32-QT `f6d80ad` + patch, default build | identical | identical | `tests/test_prg32qt_firmware_audio.py` (CI) |
| PRG32-QT desktop output device (macOS 26.6.2, Qt 6.11.2, LG UltraFine Display Audio) | Bach: the device's frames equal the engine's | equal | `docs/evidence/prg32qt-audio/2026-10-21/` |
| PRG32-QT as released | own mixer, no ADSR; not a reference | | |
| PRG32 firmware in QEMU, unpatched | 117/348 chunks at one shift | 120/540 | `docs/evidence/qemu-audio/2026-10-21/` |
| PRG32 firmware in QEMU + SDK audio patch (`-icount`) | 279/348 | 531/546 (phase A; first 6.6 s exact) or 502/546 (phase B) | `docs/evidence/qemu-audio/2026-10-21-patched/` |
| PRG32 firmware in QEMU + buzzer patch, 1.6 legacy cartridge | | loads; 3 s of exact silence | `docs/upstream/README.md` §2 |
| PRG32 console | **not recorded** | | `docs/hardware_audio_check.md` |

**Whole-recording hashes do not match in QEMU.** What still differs are effects started from
the cartridge's frames. They land one 20 ms buffer earlier or later, because the firmware's
audio buffers run on their own schedule (from boot) while the cartridge's frames run on theirs.
Restarting the schedule at cartridge start was tried; it only moved the effects the other way.
Exact whole-recording identity needs the firmware's audio buffers to follow the cartridge's
frame clock, which is an SDK design change. The soundtrack, driven by the tracker, is exact.

## Commands and results (macOS, this machine)

| Command | Result |
|---|---|
| Full `pytest` with `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, PRG32-QT and SDK checkouts, the toolchain on PATH | see "Final run" |
| `service_worker_lock`, `render_capabilities`, `build_language_index`, `build_contract_fixtures`, `make_sbom`, `lock_requirements`, `build_audio_fixtures`, `build_hardware_audio_check`, `build_debug_fixtures` with `--check`; `build_wasm.py --check` | all ok |
| `tools/check_build.py --students 2 --windows 2` | 8 Blocks cartridges built concurrently, isolated (rlimit locally; the CI container uses bubblewrap) |
| PRG32 SDK `pytest tests`, both SDK patches | 89 passed (87 before) |
| `python3 -m prg32 abi check`, patched SDK | ok |
| 18 migrated SDK sources built with the toolchain; C and assembly calling the buzzer | 18 built; refused (compile, link) |
| PRG32-QT `ctest`, patched, default options / option OFF | 5/5 (device test included) / 4/4 |
| `PRG32_LIVE_QEMU=1` drift regression | passed |

CI (`.github/workflows/tests.yml`) runs the patch tests in the WebAssembly job. It keeps the
conformance PCM and trace, and the browser failure screenshots, as artifacts. The toolchain
container rebuilds the debugger fixtures, the audio fixtures and the console check, and
compares them byte for byte (SDK pinned to the fixtures' revision).

## When the upstream changes exist

Pin the kit to them: follow the four steps at the end of `docs/upstream/README.md` §2, and move
`static/wasm/BUILD.json` `core.revision` once PRG32-QT carries the engine.

## Exceptions

1. The SDK still publishes the buzzer, and PRG32-QT still has the old mixer, until the patches
   are merged upstream.
2. QEMU whole-recording identity: effects started by frames land one buffer apart (above).
3. No physical stereo capture yet.
4. No human screen-reader session yet.
5. The PRG32-QT device test proves what the output device takes, not what a listener hears.

## Final run

With `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, the PRG32-QT and SDK checkouts and the RISC-V
toolchain on PATH: **1134 passed, 0 failed, 40 skipped.** The skips, all reported by pytest
with their reason:

- the opt-in live suites: cloud (7), identity provider (9), Store (6) and QEMU (1, run
  separately: passed);
- sandbox tests that need Linux (7; CI's container runs them);
- the RV32 C-versus-assembly differential harness (9; it needs a host GCC with the PRG32
  argument order; CI's container covers real builds);
- the console-evidence check (1: no recording exists yet).

Real cartridges for Advanced C and handwritten assembly are compiled in this run by
`test_source_debugger`, `test_handwritten_assembly` and `test_build_provenance`; Blocks
cartridges by `tools/check_build.py` and the console check's rebuild.
