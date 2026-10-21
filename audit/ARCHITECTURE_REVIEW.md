# Architecture review

The validated Blocks/IR/C/assembly/build pipeline remains coherent and the browser executes the pinned PRG32-QT guest core. Audio is where architectural parity breaks: WASM forwards semantic audio records to a separate JavaScript `AudioHost`, which approximates synth notes with native Web Audio oscillators. That host does not reproduce the canonical synth envelope/mixer, so sharing the guest execution core does not imply audio-output parity.

The canonical upstream model already includes samples, instruments, tracks, synth waveforms, ADSR, eight configured mixer voices and stereo pan. Construction Kit exposes only basic sound blocks and has no first-class versioned audio asset/editor path. A complete design needs: AudioStudio asset JSON/binary schema -> validated project references -> deterministic PRG32 audio block -> generated teaching source/assembly references -> package validation -> canonical runtime renderer.

AudioStudio should parallel SpriteLab in navigation, CRUD ownership, project attachment, conversion/artifact APIs, quotas, history/conflicts, import/export and documentation. Preview must reuse the same deterministic renderer used for cartridges rather than a second musical interpretation.

The current buzzer functions cross the language-index boundary and therefore remain product-visible even if newer audio APIs exist. Removal must begin in the canonical portable ABI inputs; hand-editing only the generated index would violate reproducibility.

Current revisions: Kit `c0d115e80c53b1d7d46afb639d104efd2b1c8516`; PRG32 `679dfb58783bd007125de9ca0b75eaa077908739`; PRG32-QT `f6d80addf49d0512c2e4390251a81d797a35b157`; CartridgeStore `820f74bfe9364c8727db92cb0f15f3b9dd85feab`.
