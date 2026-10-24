# Claude refinement brief after audio audit `c0d115e`

Continue PRG32-Construction-Kit from audited commit `c0d115e80c53b1d7d46afb639d104efd2b1c8516`. Read `AGENTS.md`, the current audit files, the expanded audio audit brief, and the canonical PRG32/PRG32-QT audio sources before editing.

## Release decision

**NO-GO.** The expanded audit scores **107/148 (72.3%)**, but the mandatory audio gate fails:

- `AUD-01` — eight SID-like voices with independent ADSR: **1/4**;
- `AUD-02` — stereo cross-runtime sample parity: **2/4**;
- `AUD-03` — AudioStudio: **0/4**;
- `AUD-04` — obsolete buzzer removal: **0/4**.

The browser host explicitly approximates synth notes with simple Web Audio oscillators, does not apply canonical ADSR parameters, and has no rendered PCM parity tests. AudioStudio does not exist. The generated portable language index still exposes `prg32_buzzer_tone`, `prg32_buzzer_play_notes` and `prg32_buzzer_sample_u8`.

Do not spend the next refinement on lower-priority polish until the four audio rows are objectively closed.

## Phase 1 — Freeze the canonical audio contract

Document and test the contract from the current PRG32 and PRG32-QT sources:

- exactly 8 simultaneous voices, numbered 0–7;
- supported SID-like synth waveforms and their exact identifiers;
- pitch/note behavior and gate/note-off semantics;
- independent attack, decay, sustain and release value ranges and timing;
- per-voice volume and pan, channel volume, master volume;
- stereo sample rate, signed sample format, left/right order, mixing and clipping;
- voice replacement/exhaustion, reset, shutdown, track stop and silence behavior;
- sample, instrument, event, track and audio-block limits.

Resolve the upstream configuration discrepancy: PRG32 Kconfig defaults to eight voices while the no-sdkconfig fallback in `audio_config.h` is six. The Construction Kit target and every reference harness must fail if configured for fewer than eight voices.

Add a machine-readable audio contract or deterministic fixture metadata shared by Kit tests and reference harnesses. Never guess values from old documentation.

## Phase 2 — Canonical browser/WASM stereo ADSR rendering

Replace `static/js/prg32_runtime.js::AudioHost` approximation with behavior equivalent to the canonical renderer. Prefer compiling/reusing the reference mixer where practical so browser preview and cartridge execution cannot drift.

Requirements:

- eight voices can remain active concurrently;
- each voice retains independent waveform, pitch, gate, ADSR, volume and pan state;
- note-off enters release rather than immediately deleting an ADSR voice;
- master/channel volume and pan updates affect active voices correctly;
- stop/reset/shutdown leave no stuck notes;
- PCM samples, instruments and tracks use the cartridge audio block;
- render deterministic interleaved stereo samples under virtual time;
- bound CPU, queued events, sample memory and output amplitude;
- remain offline and compatible with browser autoplay restrictions.

Do not satisfy this phase with call counters, silent mocks, prerecorded answers or a beep-only oscillator.

## Phase 3 — Cross-runtime audio conformance

Create one deterministic audio cartridge/fixture that:

1. gates all eight voices at once;
2. assigns deliberately distinct waveforms, notes, ADSR values, volumes and pan positions;
3. exercises attack, decay, sustain and release at fixed virtual-time checkpoints;
4. changes channel/master volume and pan while voices are active;
5. tests clipping, stop-all, reset, silence and voice replacement;
6. plays sample, instrument and soundtrack content from a packaged audio block.

Capture rendered left/right PCM from firmware/QEMU, PRG32-QT native/headless and browser/WASM. Compare exact samples where the contract is deterministic; otherwise define justified numeric tolerances. Store hashes, envelope traces and tool/source SHAs. Test that left-only/right-only content is actually separated.

## Phase 4 — AudioStudio parallel to SpriteLab

Add **AudioStudio** as a first-class, accessible classroom tool—not a hidden developer form.

Core workflows:

- create, rename, duplicate and delete instruments, sound effects and soundtracks;
- choose SID-like waveform and edit ADSR with numeric fields plus an understandable envelope visualization;
- set pitch/note, duration, volume and stereo pan;
- arrange notes/events across eight labeled voices on a simple timeline/tracker;
- solo, mute, loop, play, pause and stop preview without stuck notes;
- import/export versioned audio assets and validate them before use;
- attach/detach assets to projects and show missing references clearly;
- autosave with `expected_version`, history/conflict choices, ownership and quotas;
- work from keyboard and small screens, with labels/status usable by screen readers;
- preview through the same canonical renderer used by the Player.

Use Bootstrap and jQuery. Follow SpriteLab's understandable structure and existing CRUD patterns. Do not require a cloud account.

## Phase 5 — Deterministic assets, generated teaching code and packaging

Define a small versioned JSON representation for editable AudioStudio data and deterministic binary audio-block output matching the canonical PRG32 format.

- Keep editable metadata explainable to students.
- Save large sample content through artifact CRUD, not hidden database blobs.
- Validate sample rates, counts, sizes, loop points, event timing, IDs, offsets and archive paths.
- Generate inspectable, commented C and assembly references without hiding assets or runtime calls.
- Ensure Blocks, Advanced C and handwritten assembly projects can deliberately reference packaged audio assets without mixing source modes.
- Ensure identical project metadata/assets produce byte-identical generated source, audio block and PRG32 cartridge.
- Add project archive, duplication, quota, retention and migration coverage.

## Phase 6 — Remove buzzer support completely

The buzzer is obsolete. Remove it from the authoritative source inputs and then regenerate derived files.

- Remove `prg32_buzzer_tone`, `prg32_buzzer_play_notes`, `prg32_buzzer_sample_u8` and equivalent buzzer declarations from the portable cartridge ABI exposed to new projects.
- Remove buzzer completion/help from `tools/build_language_index.py`; regenerate `static/js/ide/prg32_language_index.js` with the normal tool.
- Remove buzzer blocks, generator paths, examples, tutorials, presentations, feature tables and runtime shims.
- Replace generic “beep” lessons with clearly named AudioStudio effects/instruments using the new engine.
- Decide one explicit legacy policy: deterministic migration into an audio instrument/effect, or a clear unsupported legacy diagnostic. Never silently reinterpret old content.
- Add a repository-wide test that fails if a supported/reachable buzzer symbol or UI choice returns. Historical release notes may mention removal but must not look actionable.

Because the language index is derived from the PRG32 SDK, coordinate the canonical SDK change first. Do not hand-edit only the generated file.

## Phase 7 — Audio security, accessibility and limits

Reject malformed or abusive assets before preview/build:

- oversized samples/audio blocks;
- invalid offsets, counts, rates, event times, loop points and instrument IDs;
- integer overflow and archive traversal;
- unbounded/cyclic event playback;
- excessive preview CPU/memory and stuck audio nodes;
- cross-owner asset references and quota bypasses.

Apply CSP and same-origin rules. Never execute uploaded audio as code. Add keyboard-only, axe and recorded screen-reader evidence for AudioStudio.

## Mandatory tests before reassessment

- deterministic eight-voice ADSR unit tests;
- left/right stereo PCM mixer tests;
- firmware/QEMU vs PRG32-QT vs WASM/browser conformance fixture;
- browser AudioStudio CRUD/edit/preview/stop/save/reload/import/export scenario;
- project attachment, generated C/assembly and deterministic cartridge packaging;
- malformed/oversized audio asset and cross-owner authorization tests;
- legacy migration/rejection fixtures;
- repository-wide no-reachable-buzzer test;
- offline Player and AudioStudio behavior;
- all existing syntax, reproducibility, pytest, required-browser, Store, sandbox and real-cartridge gates.

At minimum run:

```sh
python3 -m compileall -q app.py prg32_construction_kit tests tools
python3 tools/service_worker_lock.py --check
python3 tools/render_capabilities.py --check
python3 tools/build_language_index.py --check
python3 tools/build_contract_fixtures.py --check
python3 tools/make_sbom.py --check
python3 tools/lock_requirements.py --check
python3 -m pytest -q
PRG32_REQUIRE_BROWSER=1 PRG32QT_DIR=../PRG32-QT python3 -m pytest -q -rs tests/test_*browser*.py
git diff --check
```

## Invariants to preserve

- Blockly JSON -> validated IR -> deterministic C/optional RV32IM assembly -> PRG32 toolchain.
- No arbitrary unvalidated LLM C.
- Generated C and assembly remain visible and pedagogically commented.
- Server validation remains authoritative.
- Debug builds remain cartridge-byte-identical and debug ELF files are never served.
- Every build remains private to its `<build_id>/tmp/`.
- Preserve API routes, ownership/shared rules, scopes, `409 user_changed`, CSP, vendored dependencies, static-only service-worker caching and offline classroom use.
- Preserve Store contract checks, cloud conflict semantics and `sso_protocol.py` identity.
- Continue using **PRG32 cartridge** for `.prg32` artifacts.

## Handoff requirements

Report exact files and commits, updated `AUD-01`–`AUD-04` evidence, commands/results, PCM comparison artifacts, envelope traces, browser accessibility evidence, migration policy and every remaining limitation. Explicitly confirm eight voices, independent ADSR, stereo output, AudioStudio end-to-end packaging and complete supported-path buzzer removal. Do not request a GO reassessment without all five confirmations.
