# Security review

No new critical security issue was confirmed. The compiler-on-save path first applies the existing C/assembly validators, runs in an isolated build directory and returns sanitized diagnostics without preserving a build. Live Store evidence confirms one-time sign-on/upload tickets reject reuse and forgery, while publisher authorization remains enforced by the Kit.

AudioStudio retains ownership, conflict, quota and bounded-data validation. Patch tests operate on clean copies rather than mutating neighboring repositories. Buzzer compatibility remains silent and reserved rather than repurposing ABI slots.

Residual risks remain: builds share a host UID outside Linux namespaces; institutional/cloud tenants are untested; upstream patch supply-chain adoption is pending; and physical target resource behavior has not been observed. The recorded PRG32-QT delivery also deserves a small evidence-tool review because asynchronous runtime state must always be tied unambiguously to the cartridge just selected.

## GDPR and privacy

`GDPR-01` scores **0/4** and is a release blocker. The code contains useful
privacy-supporting controls: guests are local-only, ownership and cross-account
denial are tested, cloud connections require an explicit choice, OAuth tokens
are encrypted, retention can remove project/account items, and backups are
tested. Those controls do not establish complete GDPR compliance.

No maintained `docs/privacy/` evidence set was found. In particular, the audit
found no field-level ROPA; controller/processor/joint-controller and Article 6
legal-basis matrix; children's-data/Member-State decision; layered privacy
notices; complete authenticated access, rectification, erasure, restriction,
portability, objection and consent-withdrawal workflows; subprocessor/Article
28/transfer register; breach 72-hour exercise; DPIA screening/result; DPO
determination; or counsel/DPO approval. Project archives are not complete
personal-data exports, and admin account deletion is not demonstrated across
real providers, Store records, logs and backup expiry.

Therefore this audit makes no claim of GDPR certification or legal
non-compliance. It finds that the release has insufficient technical,
operational and legal evidence to pass the expressly required gate.
