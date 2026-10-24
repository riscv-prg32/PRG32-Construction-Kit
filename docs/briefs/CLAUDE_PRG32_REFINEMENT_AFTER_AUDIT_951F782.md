# Claude refinement note after audit 951f782

This implementation brief follows the independent audit of PRG32-Construction-Kit at `951f782f3c54a306d2bad70396127fc74a596158` on 2026-10-21. Follow every repository's `AGENTS.md`, ADRs and contracts. Audit scores belong to the auditor; provide evidence for rescoring rather than editing them.

## Current result

The project scores **126/148 (85.1%)**. The evidenced Construction Kit browser, build, PRG32-QT delivery and AudioStudio workflows are approved. Complete ecosystem audio/hardware release remains blocked by:

1. audio patches not merged into canonical PRG32 and PRG32-QT;
2. no physical stereo PRG32 capture or physical delivery;
3. a one-buffer ambiguity for frame-triggered effects in QEMU;
4. no human AudioStudio screen-reader session;
5. no user-driven PRG32-QT desktop Import test;
6. no iOS handoff or real Google/Microsoft/institutional tenant evidence.

Do not rework completed features without a failing regression. Preserve the validated, deterministic and inspectable teaching pipeline.

## Priority 1: move audio patches upstream

The following patches are proved against clean copies but remain local proposals:

- `docs/upstream/prg32-sdk-retire-buzzer.patch`
- `docs/upstream/prg32-qt-firmware-audio.patch`
- `docs/upstream/prg32-sdk-audio-clock-and-reset.patch`

Prepare upstream-quality commits or pull requests in the actual PRG32 and PRG32-QT repositories. Rebase carefully onto their current canonical heads; do not modify neighboring working trees merely to satisfy this audit.

For buzzer retirement:

- publish ABI 1.7 or the maintainer-approved equivalent;
- keep slots 5, 7 and 8 reserved and silent for legacy cartridges;
- remove public declarations, imports, examples and documentation;
- never reinterpret old calls as synth operations;
- regenerate ABI outputs and prove all unrelated indices/hash compatibility.

For PRG32-QT:

- make the firmware audio engine the supported default;
- keep eight voices, independent ADSR, samples, tracker and stereo behavior bit-identical;
- test headless WAV and the real desktop output path;
- remove or explicitly deprecate the divergent non-ADSR mixer.

After upstream acceptance, update Kit pins, WASM provenance, language indexes, contracts and fixtures from the canonical revisions.

## Priority 2: physical PRG32 evidence

Run `docs/hardware_audio_check.md` on a stereo-configured ESP32-C6 PRG32. Prefer I2S capture with a logic analyser. Use the committed cartridge SHA-256:

`4f821b3047dcb9d000cc1a94f7b7c4ab8f2d707f018593eee66b787cf379d712`

Retain:

- physical delivery record and selected slot;
- firmware commit, ABI and full audio configuration;
- raw stereo WAV/I2S capture;
- `tools/hardware_audio_compare.py` report;
- hardware and capture-tool identity;
- short listening observations.

The report must demonstrate all eight voices, independent envelopes, stereo separation, soundtrack, WAV effect, stop/reset silence and absence of buzzer output. Do not mark physical delivery or audio complete without these artifacts.

## Priority 3: eliminate the QEMU effect timing ambiguity

The clock/reset patch aligns tracker audio and most recordings, but cartridge-frame-triggered effects can land one 20 ms buffer apart. Define one deterministic scheduling boundary between cartridge frames and audio buffers.

Acceptance:

- the conformance and AudioStudio console-check recordings align over the complete timeline;
- frame-triggered samples, note gates, stop/reset and tracker events occur at specified sample indices;
- whole L/R PCM hashes match when running the same engine/configuration;
- physical-console scheduling semantics remain authoritative and unchanged unless explicitly versioned.

Add a regression that fails on a one-buffer shift.

## Priority 4: delivery UX and evidence integrity

Repeat the five-cartridge PRG32-QT delivery through the visible desktop Import menu, not only its web API:

- Blocks generated C;
- Blocks generated assembly;
- Advanced C;
- handwritten assembly;
- AudioStudio console check.

Record hashes, screenshots and runtime results after each selection. Ensure the evidence collector waits until runtime identity, generation and screenshot all correspond to the cartridge just selected; add a regression for stale asynchronous state.

Execute physical-console delivery with the same integrity checks when hardware is available. Keep iOS marked unsupported/unverified until its actual file-import contract and device behavior are exercised.

## Priority 5: human accessibility

Complete AudioStudio tasks 10–14 in `docs/accessibility_session.md` using a named screen reader. Record OS, browser, assistive-technology versions, keyboard path, announcements and defects. Fix issues without weakening CSP or introducing inline scripts.

## Priority 6: remaining integrations

Using dedicated test data only:

- run Google Drive and OneDrive live suites with least-privilege scopes;
- run institutional OIDC if an approved tenant is available;
- verify iOS handoff only against the real PRG32-iOS interface;
- retain no bearer tokens, secrets or personal data in logs/artifacts.

## Required regression evidence

Run and report:

- full pytest with `PRG32_REQUIRE_BROWSER=1` and `PRG32_REQUIRE_SDK=1`;
- live disposable Store SSO/publishing;
- real toolchain builds for all four authoring paths and both targets;
- upstream PRG32 and PRG32-QT native suites;
- audio/QEMU/Qt/device/no-buzzer tests;
- service-worker, capabilities, language-index, Store-contract, SBOM, dependency-lock and all fixture rebuild checks;
- Linux bubblewrap/AppArmor isolation jobs.

Provide exact revisions, commands, pass/skip counts, cartridge/PCM hashes and artifact paths. Missing hardware, toolchains or tenants are explicit limitations, not passes.

## Non-negotiable constraints

- Blockly JSON and versioned assets -> validated IR -> deterministic C/RV32IM assembly -> PRG32 cartridge.
- Never compile arbitrary unvalidated LLM-provided C.
- Keep generated source and explanatory comments visible to students.
- Preserve ownership, quotas, optimistic conflicts, CSP, vendored browser libraries, build isolation, offline classroom use and debug/cartridge byte identity.
- AI proposals must never silently alter student projects.

## Handoff to the auditor

Return canonical upstream PR/commit links, updated runtime matrix, physical capture and delivery paths, whole-recording hashes, desktop Import evidence, screen-reader record, integration results and a concise remaining-exceptions list. Do not claim complete audio support while the canonical SDK still exposes buzzer or while physical stereo evidence is absent.
