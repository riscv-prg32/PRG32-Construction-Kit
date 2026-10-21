# Architecture review

The validated Blocks -> game IR -> deterministic C/assembly -> cartridge pipeline remains coherent. Audio now follows the same principle: a versioned AudioStudio document is validated, resolved into named block operands, packed deterministically as an `AUD0` cartridge block and rendered in the browser by the PRG32 firmware audio engine compiled into WASM.

This closes the former JavaScript-oscillator split. Eight engine voices carry independent waveform, ADSR, volume and stereo pan state, and native/WASM conformance tests compare deterministic stereo PCM from the same fixture. AudioStudio parallels SpriteLab with owned/versioned assets, conflict handling, project attachment, WAV samples, instruments, effects, soundtracks, preview, archives and teaching-oriented generated C/assembly.

Two architecture boundaries remain incomplete. First, the canonical PRG32 SDK still exposes legacy buzzer ABI entries even though the Kit hides, rejects and silences them. Removal must occur in the canonical ABI inputs with an explicit compatibility/versioning decision, then flow through regenerated indexes and consumers. Second, PRG32-QT has a separate floating-point non-ADSR renderer and the inspected QEMU path cannot emit a comparable stereo capture. Native/WASM identity therefore proves one engine implementation, not yet every supported runtime.

Current revisions: Kit `13766c9173353f10d4b89222df0c1e60291725a5`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.
