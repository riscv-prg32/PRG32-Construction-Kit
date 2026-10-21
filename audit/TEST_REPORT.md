# Test report

Audited HEAD: `13766c9173353f10d4b89222df0c1e60291725a5` on 2026-10-21.

## Audio-focused evidence

Command covered `test_audio_contract.py`, `test_audio_block.py`, `test_audio_conformance.py`, `test_audio_studio.py` and `test_no_buzzer.py`: **95 passed**.

Verified behaviors include eight active voices, independent ADSR traces, exact sustain values, deterministic native/WASM PCM hashes, stereo separation, clipping, silence, pan/volume updates, busy-voice replacement, malformed audio-block rejection, AudioStudio validation/CRUD/conflicts/ownership/quotas, deterministic AUD0 packing, archives, named generated C/assembly and Kit-side buzzer rejection.

## Reproducibility gates

| Gate | Result |
|---|---|
| Python/JavaScript syntax | Pass |
| Service-worker cache lock | Pass |
| Language-index reproducibility | Pass |
| Store-contract fixtures | Pass |
| SBOM | Pass |
| Requirements lock | Pass: 28 hashed packages |
| Audio fixtures | Not rerun: PRG32 toolchain absent |

## Broader regression evidence

- Broad feasible suite: **965 passed, 72 skipped, 1 deselected**. The initial run also reported one expected audit-edit mismatch because `docs/capabilities.md` had not yet been regenerated, plus four sandbox-denied loopback fixture setups.
- Generated capability/document consistency rerun after rendering: **156 passed**.
- Mandatory real-browser suites with `PRG32_REQUIRE_BROWSER=1`, including both AudioStudio scenarios: **85 passed**.
- Loopback delivery suite rerun with local-server permission: **6 passed**.

The 72 broad-suite skips were explicit environment/opt-in limitations: unavailable PRG32/RISC-V toolchains, Linux-only sandbox mechanisms, live external providers/Store, and browser tests that were then covered by the separate mandatory Chrome run.

## Audio evidence limitations

- No firmware/QEMU stereo capture at the inspected SDK revision.
- No physical hardware stereo capture.
- PRG32-QT uses a divergent non-ADSR floating-point renderer, so it is not sample-identical.
- Canonical SDK still exposes buzzer ABI symbols even though the Kit refuses them.

## Reference revisions

- Construction Kit: `13766c9173353f10d4b89222df0c1e60291725a5`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
