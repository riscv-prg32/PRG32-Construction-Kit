# Architecture review

The core architecture remains coherent: Blockly JSON or validated source plus versioned assets enters deterministic generation/building, and students can inspect generated C and RV32IM assembly. Compiler checks run only after the same safety validators and inside the build sandbox; diagnostics are returned without retaining build artifacts.

Build evidence now covers generated C, generated assembly, Advanced C and handwritten assembly for ESP32-C6 and QEMU. PRG32-QT delivery and live CartridgeStore interoperability exercise real adjacent repositories rather than local substitutes.

Audio has a clear convergence path. Browser, native and patched Qt use the firmware engine; patched QEMU advances from rendered audio and resets mixer state per cartridge. Yet the system-of-record revisions remain unchanged, so the architecture is not ecosystem-canonical until those patches land upstream. The Kit correctly keeps buzzer hidden/refused and legacy calls silent meanwhile.

Current revisions: Kit `951f782f3c54a306d2bad70396127fc74a596158`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.

## Documentation and privacy architecture reassessment

The gap is closed for repository documentation. `docs/architecture.md` and the
generated architecture, pipeline, game-loop and personal-data diagrams now show
the single IDE, validated Blocks/C/assembly paths, isolated builds, WASM/debugger,
AudioStudio/AUD0, browser/SQLite/files/backups, identity/cloud/GitHub/Store and
secret/retention boundaries. The visual manifest and generators passed their
freshness checks.

The field-level ROPA and privacy diagrams are technical templates rather than an
approved deployment architecture until the controller fills the provider,
hosting, transfer, legal-basis, DPIA and DPO decisions.

The chosen Store identity architecture now separates the private account username
from a pseudonymous public handle and matches accounts by email. This is coherent
and better documents the privacy boundary, but it is not ecosystem-canonical
until `docs/upstream/cartridge-store-shared-identity.patch` is merged upstream.

The build guard no longer estimates UID-wide processes from container-visible
`/proc`; it probes the kernel before setting RLIMIT_NPROC. Exact-SHA CI verified
the repair in the production image beside 300 same-UID processes in another
container, while preserving bwrap, AppArmor, resource budgets and real builds.

Current Kit revision: `f5b3a0ff3f261f424172e57b30602026bd1ffaca`.
