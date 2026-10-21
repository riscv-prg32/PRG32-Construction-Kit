# Remediation plan

| Priority | Owner | Size | Work | Acceptance evidence |
|---:|---|:---:|---|---|
| 1 | Runtime/audio | L | Implement one canonical eight-voice SID-like stereo ADSR renderer for browser/WASM parity, preserving the portable ABI. | Eight concurrent voice fixture; per-voice ADSR traces; left/right PCM hashes/tolerances against PRG32-QT and firmware/QEMU. |
| 2 | Product/frontend | L | Add accessible AudioStudio parallel to SpriteLab for instruments, effects and soundtracks. | Keyboard/browser scenario covering CRUD, preview, eight-voice arrangement, save/reload, import/export and project attachment. |
| 3 | Assets/build | L | Define versioned audio assets and deterministic PRG32 audio-block generation/packaging. | Round trips, malformed/oversized rejection, reproducible source/block/cartridge hashes and all three source modes. |
| 4 | SDK/docs | M | Remove buzzer from canonical portable API, index, blocks, examples and docs; define legacy migration/rejection. | Reproducible index plus repository-wide no-reachable-buzzer test and migration fixtures. |
| 5 | Audio QA | M | Add stop/reset, clipping, master/channel volume/pan, voice exhaustion, timing and offline tests. | Cross-runtime PCM and no-stuck-note browser tests. |
| 6 | Delivery | M | Validate stereo hardware, Qt import and iOS handoff. | Recorded tool versions, hashes and stereo capture/device results. |
| 7 | Operations | M | Complete real cloud evidence and per-build identity evaluation. | Safe tenant suites and Linux isolation evidence. |

Audio PRs must not weaken deterministic generation, server validation, cartridge/debug identity, CSP, ownership, offline use or educational source visibility.
