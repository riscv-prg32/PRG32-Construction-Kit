# Test report

Audited HEAD: `f4b74bcfe2f0b70563daae4fd76cc1c1b8acaf78` on 2026-10-21.

## Fresh execution

| Scope | Result |
|---|---|
| Audio contract, block, conformance, AudioStudio, hardware-check tooling, no-buzzer and PRG32-QT patch tests | **113 passed, 1 skipped** |
| Mandatory Chrome suites with `PRG32_REQUIRE_BROWSER=1` | **87 passed** |
| Broad feasible suite | **988 passed, 75 skipped, 1 deselected, 4 sandbox setup errors** |
| Delivery suite with loopback permission | **6 passed** |
| Python compile and JavaScript syntax | Pass |
| Capability render, service-worker lock, language index, Store fixtures, SBOM and requirements lock | Pass |
| Audio and hardware fixture rebuild checks | Blocked locally: PRG32 toolchain absent |

The broad-suite errors were all `tests/test_delivery_check.py` fixtures denied permission to bind `127.0.0.1` inside the filesystem sandbox. The same complete file passed after loopback permission. Browser skips in the broad run were independently covered by the required Chrome run. Other skips are explicit toolchain, Linux sandbox or live-provider opt-ins.

## Retained reference evidence inspected

- QEMU firmware captures under `docs/evidence/qemu-audio/2026-10-21/` include WAV files, comparison JSON, SDK configuration and hashes.
- The real firmware produces samples equal to the browser between events: 76/234 sounding chunks for the conformance cartridge and 66/269 for the AudioStudio console check.
- The PRG32-QT patch is tested against `f6d80add`; its headless output matches browser hashes `2e6c5af207d3d5f2` and `a3d2c6520ba8aea2`.
- The AudioStudio console-check cartridge SHA-256 is `4f821b3047dcb9d000cc1a94f7b7c4ab8f2d707f018593eee66b787cf379d712`.

## Limitations

- No physical PRG32 stereo capture exists.
- The firmware/QEMU clock places events earlier than the rendered-sample timeline; comparisons are exact between events, not for the whole recording.
- The PRG32-QT firmware-engine patch is not merged upstream and its desktop sound was not heard.
- The PRG32 SDK still exports buzzer ABI entries.
- No human screen-reader session was recorded for AudioStudio.

## Reference revisions

- Construction Kit: `f4b74bcfe2f0b70563daae4fd76cc1c1b8acaf78`
- PRG32: `679dfb58783bd007125de9ca0b75eaa077908739`
- PRG32-QT: `f6d80addf49d0512c2e4390251a81d797a35b157`
- CartridgeStore: `820f74bfe9364c8727db92cb0f15f3b9dd85feab`
