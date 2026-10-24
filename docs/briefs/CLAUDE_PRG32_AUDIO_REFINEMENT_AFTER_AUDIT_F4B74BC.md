# Claude refinement note: finish the PRG32 ecosystem audio release

This brief follows the independent audit of PRG32-Construction-Kit at `f4b74bcfe2f0b70563daae4fd76cc1c1b8acaf78` on 2026-10-21. Follow each repository's `AGENTS.md`, ADRs and contracts. Do not change auditor-owned scores; return evidence for reassessment.

## Current position

The Construction Kit AudioStudio workflow is approved within its evidenced browser and firmware/QEMU scope. The audit score is **119/148 (80.4%)**. The complete ecosystem audio release remains blocked by upstream and physical evidence:

- the canonical PRG32 SDK still exports the obsolete buzzer;
- the firmware-audio PRG32-QT integration is a tested patch, not an upstream release;
- QEMU advances audio events faster than its emitted sample timeline;
- no physical stereo PRG32 capture exists;
- AudioStudio lacks a recorded human screen-reader session.

Do not rebuild already-complete AudioStudio CRUD, instruments, effects, soundtracks, WAV support, named Blocks, generated C/assembly, archives or deterministic `AUD0` packaging unless a regression test identifies a defect.

## 1. Retire buzzer in the canonical PRG32 SDK

Implement the policy proposed in `docs/upstream/README.md` in the actual PRG32 repository:

1. remove public buzzer declarations and supported ABI metadata;
2. keep portable indices 5, 7 and 8 reserved so later functions never shift;
3. route legacy entries to an explicit silent compatibility stub, or reject them through a documented ABI-version rule;
4. bump the appropriate ABI version;
5. migrate examples and documentation to the eight-voice audio API;
6. regenerate every ABI-derived file.

Never reinterpret a legacy buzzer call as a synthesizer call. Add tests proving old cartridges are silent, new source cannot address the removed API, and all unrelated ABI indices remain stable. Then regenerate the Construction Kit language index and update its contract from “proposed” to the actual upstream revision.

## 2. Upstream the PRG32-QT firmware engine

Start from `docs/upstream/prg32-qt-firmware-audio.patch`, but review it as production PRG32-QT code. Merge or adapt it so the canonical runtime uses the firmware audio engine for eight SID-like ADSR voices and stereo output.

Acceptance:

- clean PRG32-QT checkout builds with its normal test suite;
- conformance and AudioStudio console-check hashes match browser/native references;
- legacy buzzer fixtures remain silent;
- desktop stereo playback is exercised through the actual output device, not only headless WAV;
- the default supported configuration no longer falls back to the divergent non-ADSR mixer.

Record upstream commit/PR identity and update the Construction Kit pin and reproducibility metadata only after the canonical change exists.

## 3. Correct firmware/QEMU audio time

The retained QEMU recordings prove sample identity between events, but event placement runs early because state advances using emulated elapsed time while each acknowledged buffer contains 20 ms of PCM. Change the QEMU redirect path to advance from frames actually rendered.

Acceptance:

- the complete conformance and AudioStudio recordings align, not only selected between-event chunks;
- tracker deltas, attack/decay/release boundaries, sample effects and stop/reset events occur at the same sample indices;
- whole-recording L/R hashes match when the same integer engine and schedule are used;
- console behavior is unchanged.

Retain the before/after comparison JSON and add a regression that fails if QEMU timing drifts again.

## 4. Capture a physical stereo console

Follow `docs/hardware_audio_check.md` using a stereo-configured ESP32-C6 PRG32 and preferably an I2S logic-analyser capture. Use the committed cartridge whose SHA-256 is:

`4f821b3047dcb9d000cc1a94f7b7c4ab8f2d707f018593eee66b787cf379d712`

Run `tools/hardware_audio_compare.py` and retain:

- delivery record and cartridge hash;
- firmware commit and complete audio configuration;
- raw stereo WAV/I2S capture;
- comparison JSON;
- hardware/capture-tool identification;
- a short listening observation.

The evidence must demonstrate all eight voices, distinct ADSR behavior, left/right separation, the WAV effect, soundtrack timing, stop-all silence and no buzzer output. Do not claim hardware verification until those artifacts exist.

## 5. Complete human accessibility evidence

Run AudioStudio tasks 10–14 from `docs/accessibility_session.md` with VoiceOver, NVDA or another named screen reader. Record browser/AT versions, keyboard path, announcements, failures and remediation. Automated axe and keyboard tests remain necessary but do not replace this session.

## Required regression run

Use equipped CI or a documented local environment to run:

- the complete pytest suite with `PRG32_REQUIRE_BROWSER=1` and `PRG32_REQUIRE_SDK=1`;
- audio contract, conformance, hardware comparator, Qt integration and no-buzzer tests;
- real cartridge builds for Blocks, Advanced C and handwritten assembly;
- service-worker, capabilities, language-index, Store-contract, SBOM, requirements-lock, audio-fixture and hardware-fixture reproducibility checks;
- PRG32 and PRG32-QT native test suites affected by upstream changes.

Preserve exact commands, revisions, pass/skip counts, PCM hashes and downloadable artifacts. Toolchain or hardware absence is a reported limitation, never a passing result.

## Constraints

- Preserve Blockly JSON -> validated IR/assets -> deterministic inspectable C/RV32IM assembly -> PRG32 cartridge.
- Never compile arbitrary unvalidated LLM-provided C.
- Keep generated per-block/per-line teaching comments.
- Preserve CSP, vendored browser dependencies, authentication, ownership, quotas, build isolation, debug/cartridge byte identity and offline classroom use.
- Do not silently alter student projects.
- Do not modify external repositories merely to make a local audit pass; changes must be suitable for their upstream maintainers.

## Handoff back to the auditor

Provide canonical upstream commits or PRs, the new supported-runtime matrix, whole-recording PCM hashes, physical capture paths, screen-reader record, complete test results and a short exception list. The release cannot receive full audio credit while buzzer remains public or while physical stereo evidence is absent.
