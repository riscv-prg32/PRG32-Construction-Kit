# Security review

No new critical security exploit was confirmed. Existing authentication, ownership, PKCE/cloud-token, Store-egress, CSP and build-sandbox controls remain strong. Disk budgets, AppArmor CI, locked dependencies and an SBOM improve the previous posture.

AudioStudio will introduce untrusted sample, instrument and track inputs. Its design must bound sample counts/length/rate, event counts/durations, identifiers, archive expansion, decoded memory, preview CPU and final cartridge block size. Reject malformed offsets, integer overflow, invalid loop points, unsafe names/paths and cyclic/unbounded playback. Preview must never decode or execute arbitrary uploaded code and must obey ownership, quotas and CSP.

Removing buzzer support is also a compatibility/security boundary: legacy content must be explicitly migrated or rejected, never silently reinterpreted as a different audio operation. Generated audio assets must remain deterministic and validated before compilation/packaging.

Residual non-audio risks remain the shared host UID outside namespaces, absent real cloud tenants/device delivery and upstream Store lifecycle limitations.
