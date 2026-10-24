# Test report

Audited HEAD: `f5b3a0ff3f261f424172e57b30602026bd1ffaca` on 2026-10-23.

## Fresh execution

| Scope | Result |
|---|---|
| Exact-SHA GitHub Actions run | **Success**, run `39924578831` |
| Toolchain production-image job | **Success**: same-UID 300-process scenario, bwrap/budgets/AppArmor, real and concurrent cartridges, fixtures and health |
| Local affected-selection rerun | **234 passed, 8 skipped** in 8.43 s; skips are Linux/bubblewrap-only paths covered by successful CI |
| Current broad feasible suite with loopback/cache access | **1,332 passed, 57 skipped, 3 failed** in 271.00 s |
| Three failures | Shared username/private-handle assertions against adjacent unpatched CartridgeStore `4a3138b` |
| Retained patched-Store evidence | Store **91 passed**; Kit cross-repository suite **89 passed** against clean `4a3138b` + proposed patch |
| Privacy, docs, guest, run-build, settings, GitHub, project-type, security, authorization and consistency selection | **441 passed, 1 skipped** in 49.51 s |
| Broad feasible suite, rerun with disposable loopback/compiler-cache access | **1,330 passed, 56 skipped, 1 failed** in 267.76 s |
| Mandatory browser selection with `PRG32_REQUIRE_BROWSER=1` | **5 passed, 40 setup errors**: no Chrome or Playwright Chromium installed |
| Isolated failing interoperability scenario | **1 failed**, reproduced twice |
| Documentation, capability, authentication, authorization, storage, cloud, backup and API selection | **331 passed** in 34.42 s |
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

- The current failures are `test_kit_user_can_sign_in_to_the_store`, `test_the_username_is_shared_and_the_store_handle_stays_public_only`, and `test_a_store_only_account_with_the_same_username_is_never_joined`. They pass only when the proposed Store patch is applied; canonical Store has not merged it.
- Browser tests could not execute locally because this host has no Chrome or Playwright Chromium. They were forced with `PRG32_REQUIRE_BROWSER=1`, so absence produced errors rather than false passes.
- No live real-provider data-subject request, staffed breach tabletop, completed DPIA/DPO decision or legal review was available.
- The RLIMIT_NPROC test is Linux-only and skipped locally, but the exact audited SHA's production-image CI job executed and passed it under the intended cross-container same-UID load.
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
