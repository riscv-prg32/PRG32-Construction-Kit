# Architecture review

The core architecture remains coherent: Blockly JSON or validated source plus versioned assets enters deterministic generation/building, and students can inspect generated C and RV32IM assembly. Compiler checks run only after the same safety validators and inside the build sandbox; diagnostics are returned without retaining build artifacts.

Build evidence now covers generated C, generated assembly, Advanced C and handwritten assembly for ESP32-C6 and QEMU. PRG32-QT delivery and live CartridgeStore interoperability exercise real adjacent repositories rather than local substitutes.

Audio has a clear convergence path. Browser, native and patched Qt use the firmware engine; patched QEMU advances from rendered audio and resets mixer state per cartridge. Yet the system-of-record revisions remain unchanged, so the architecture is not ecosystem-canonical until those patches land upstream. The Kit correctly keeps buzzer hidden/refused and legacy calls silent meanwhile.

Current revisions: Kit `951f782f3c54a306d2bad70396127fc74a596158`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.
