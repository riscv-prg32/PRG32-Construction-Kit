# Test report

Audited HEAD: `c0d115e80c53b1d7d46afb639d104efd2b1c8516` on 2026-10-21.

## Core gates

| Gate | Result |
|---|---|
| Python and JavaScript syntax | Pass |
| Service-worker cache lock | Pass |
| Language-index reproducibility | Pass |
| Store-contract fixture reproducibility | Pass |
| SBOM reproducibility | Pass |
| Requirements lock and hashes | Pass: 28 packages |
| Broad feasible pytest run | 857 passed, 70 skipped, 1 deselected; 4 sandbox loopback errors and 2 transient doc failures rerun separately |
| Delivery fake-device tests | 6 passed after loopback permission |
| Required Chromium suites | 81 passed, no skips |
| Disposable Store contract/lifecycle suite | 51 passed |
| Store-egress suite | 94 passed |
| Capability/document consistency | 150 passed after audit capability rendering |

## Audio-specific inspection and execution

| Requirement | Evidence/result |
|---|---|
| Audio calls reach browser | Pass, but test checks only record kinds/counts |
| Eight simultaneous voices | No dedicated fixture or assertion |
| ADSR | Firmware and PRG32-QT contain envelope fields/logic; browser host does not apply them |
| Stereo | Browser pan node and Qt stereo renderer exist; no left/right PCM comparison |
| AudioStudio | No route, editor, asset format or tests found |
| Buzzer removal | Fail: generated portable index exposes three buzzer functions; docs/examples remain |

## Environment limitations

No physical PRG32 stereo output, real Google/Microsoft account, iOS target, local RISC-V/PRG32 toolchain rebuild or exact Emscripten rebuild was used. Linux-only bubblewrap/RLIMIT checks skipped locally; CI evidence was inspected. Browser and loopback suites were rerun outside the restricted sandbox where required.

## Reference revisions

- Construction Kit: `c0d115e80c53b1d7d46afb639d104efd2b1c8516`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
