# Claude refinement note: close the PRG32 audio release gates

Use this note as an implementation brief. It summarizes the remaining work after the 2026-10-21 audit of PRG32-Construction-Kit at `13766c9173353f10d4b89222df0c1e60291725a5`. Treat the repository's `AGENTS.md`, ADRs and contracts as authoritative; this is a task brief, not permission to weaken them.

## Outcome required

Move the audio audit from **116/148 (78.4%)** and conditional classroom-preview status to release-quality evidence for:

1. eight simultaneous SID-like voices with independent ADSR;
2. deterministic stereo output across supported reference runtimes;
3. complete AudioStudio-to-cartridge-to-device operation; and
4. total removal of supported buzzer functionality.

Do not reimplement completed AudioStudio features unless a failing test proves a defect. Preserve the validated pipeline: Blocks JSON and versioned AudioStudio data -> validated IR/assets -> deterministic inspectable C or RV32IM assembly -> PRG32 cartridge. Never compile arbitrary unvalidated LLM C.

## Current verified baseline

- AudioStudio manages instruments, WAV samples, effects and soundtracks with ownership, quotas, optimistic conflicts, archives and project attachment.
- Named sound blocks generate commented teaching C/assembly and deterministic `AUD0` cartridge data.
- The browser/WASM runtime uses the PRG32 firmware audio engine, not a JavaScript oscillator approximation.
- A committed conformance fixture covers eight active voices, waveforms, independent ADSR, per-voice volume/pan, clipping, silence, stop/reset and deterministic PCM.
- Native and WASM builds of that engine produce bit-identical stereo output.
- Kit authoring hides and rejects buzzer APIs; old buzzer calls are silent and counted.
- Focused audio tests: 95 passed. Capability/document consistency: 156 passed.

## Mandatory work, in order

### 1. Retire buzzer in the canonical PRG32 ABI

The inspected PRG32 SDK still publishes legacy buzzer functions. Define the ABI compatibility/versioning decision in the canonical SDK, remove supported declarations/metadata/dispatch exposure, regenerate all derived language indexes, and update every consumer. Preserve an explicit safe policy for old cartridges: silent compatibility or a clear version error, never reinterpretation as another sound command.

Acceptance:

- a repository-family guard finds no buzzer API reachable from supported headers, blocks, completion data, examples or documentation;
- generated files reproduce from canonical inputs;
- legacy fixtures prove the chosen behavior;
- no unrelated portable ABI function moves accidentally.

### 2. Eliminate renderer divergence

PRG32-QT currently has a separate floating-point renderer without equivalent ADSR. Prefer linking or adapting the canonical firmware renderer. If PRG32-QT is intentionally not a reference runtime, document that scope formally and identify the replacement reference.

Acceptance:

- run the identical eight-voice fixture in native engine, browser/WASM and the supported desktop reference;
- compare L/R PCM, per-voice ADSR state, pan separation, clipping, silence, reset and voice exhaustion;
- require exact hashes when representations match, otherwise document a justified numerical tolerance and test it.

### 3. Add firmware/QEMU stereo capture

Make the real PRG32 toolchain produce the fixture and expose deterministic stereo samples from firmware/QEMU. Record SDK/toolchain revisions and fixture hashes. Tests must skip clearly when the toolchain is missing but must be required in the equipped CI job.

### 4. Prove the physical path

Build a project in AudioStudio containing eight concurrent voices, contrasting pans, distinct ADSR envelopes, a sample effect and a soundtrack. Package the PRG32 cartridge, install it on target hardware and capture both channels. Verify playback, silence/reset, clipping behavior and absence of buzzer output. Preserve hashes, tool versions and captures as audit artifacts.

### 5. Finish product evidence

Run the mandatory real-browser AudioStudio scenarios with `PRG32_REQUIRE_BROWSER=1`, including keyboard-only navigation, save/reload, conflict recovery, preview, archive round-trip and cartridge packaging. Add a brief human screen-reader review. Keep useful PCM/trace/browser failure artifacts in CI.

## Tests and constraints

- Keep `tests/test_audio_contract.py`, `test_audio_block.py`, `test_audio_conformance.py`, `test_audio_studio.py`, `test_audio_browser.py` and `test_no_buzzer.py` passing.
- Run the full suite, mandatory browser suite, reproducibility checks, Store contract tests and real cartridge build job.
- Do not hand-edit generated capability or language-index output; run their generators.
- Do not weaken CSP, authentication, ownership, quotas, build isolation, debug/cartridge identity or offline classroom behavior.
- Keep all browser libraries vendored and bump the service-worker cache version when cached assets change.
- Do not change auditor-owned scores. Return implementation evidence so the auditor can rescore.

## Delivery back to the auditor

Provide commits grouped by the five work areas, exact commands/results, supported-runtime matrix, PCM/trace hashes, hardware capture paths, ABI migration notes and a concise list of any remaining exceptions. A claim of completion without firmware/QEMU and physical stereo evidence is insufficient for score 4.
