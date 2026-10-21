# Security review

No new critical security issue was confirmed. AudioStudio preserves authenticated ownership, version conflicts, quotas, bounded document/WAV validation and deterministic packaging. Browser preview executes the compiled firmware engine rather than uploaded code. Archive imports remap owned samples, and the normal generation pipeline still refuses arbitrary unvalidated LLM C.

The added QEMU, patch-application and hardware-check tooling operates on explicit copies/artifacts and has negative tests for malformed or misleading captures. Legacy buzzer calls are never reinterpreted as another sound operation.

Residual risks are primarily availability and supply-chain reproducibility: local toolchain rebuilds were unavailable; the upstream patches are not canonical releases; and target CPU/memory behavior lacks physical-device observation. Existing non-audio residuals—shared host UID outside namespaces and absent real external-provider/device-delivery evidence—remain.
