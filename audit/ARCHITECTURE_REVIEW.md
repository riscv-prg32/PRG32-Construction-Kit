# Architecture review

Audio now follows the project's deterministic teaching pipeline: versioned AudioStudio JSON is validated, names resolve through the game IR, generated C/RV32IM assembly remains inspectable, and a deterministic `AUD0` block enters the PRG32 cartridge. Browser preview and cartridge execution use the PRG32 firmware audio engine compiled to WASM.

The retained QEMU capture materially strengthens the architecture claim: the actual firmware engine and browser port emit equal samples between events. The proposed PRG32-QT patch also compiles the same engine and is hash-identical in headless tests. This is a sound convergence design, but it is not yet the released ecosystem architecture because the patch remains external to PRG32-QT and QEMU's event clock is divergent.

The buzzer boundary is intentionally safe inside the Kit—hidden, rejected for new source, silent for old cartridges—but still contradictory at the SDK boundary. Canonical ABI inputs must retire it; generated indexes alone must never be hand-edited.

Current revisions: Kit `f4b74bcfe2f0b70563daae4fd76cc1c1b8acaf78`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.
