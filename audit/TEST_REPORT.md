# Test report

Audited HEAD: `951f782f3c54a306d2bad70396127fc74a596158` on 2026-10-21.

## Fresh execution

| Scope | Result |
|---|---|
| Audio, upstream-patch, compiler-check, delivery, live-SSO, documentation and capability selection | **294 passed, 9 skipped, 5 sandbox setup errors** |
| Delivery tests with loopback permission | **8 passed** |
| Mandatory Chrome suites with `PRG32_REQUIRE_BROWSER=1` | **88 passed** |
| Disposable live Kit/CartridgeStore HTTP suites | **11 passed** |
| Broad feasible suite | **1,009 passed, 85 skipped, 1 deselected, 5 sandbox setup errors** |
| Python compile and JavaScript syntax | Pass |
| Service-worker, capability render, language index, Store fixtures, SBOM and requirements lock | Pass |
| Audio, hardware-audio and debug fixture rebuilds | Blocked locally: PRG32 toolchain absent |

All five errors were `tests/test_delivery_check.py` fixtures denied permission to bind loopback inside the default sandbox. The complete file passed 8/8 with that permission. Browser tests skipped in the broad run were independently required and passed in Chrome.

The nine focused skips were explicit: live QEMU opt-in, local toolchain-dependent compiler/fixture rebuilds, absent physical-console evidence, and Store tests before the separate live invocation. The 85 broad skips additionally include live cloud/identity providers, Linux-only bubblewrap and unavailable local RISC-V tooling.

## Retained evidence inspected

- `docs/evidence/toolchain/2026-10-21/`: pinned Docker image, compiler identity, passing fixture rebuilds, 112 toolchain tests and cross-host hashes.
- `docs/evidence/delivery/2026-10-21-prg32qt/`: five cartridge hashes, upload/select/runtime results and non-black screenshots.
- `docs/evidence/qemu-audio/2026-10-21-patched/`: patched firmware WAVs, logs, configuration and detailed comparison JSON.
- `docs/evidence/prg32qt-audio/2026-10-21/`: frames delivered to a named macOS output device equal the firmware engine.
- `docs/handoff/audio-after-f4b74bc.md`: runtime matrix, patch commands and exact exceptions.

## Limitations

- SDK and PRG32-QT audio fixes are patches in this repository, not merged canonical commits.
- Frame-triggered QEMU effects can differ by one 20 ms audio buffer; whole-recording hashes are not identical.
- No physical stereo PRG32 recording or physical-console delivery exists.
- No human AudioStudio screen-reader session exists.
- PRG32-QT delivery used its web API, not a person clicking the desktop Import menu.
- No iOS handoff was executed.

## Reference revisions

- Construction Kit: `951f782f3c54a306d2bad70396127fc74a596158`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
