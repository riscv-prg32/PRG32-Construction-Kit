# Claude refinement note after the GDPR and documentation audit

Refine PRG32-Construction-Kit after the independent audit of
`7c83e716796ae8b2a5771173d885d5f20a390209`. Read `AGENTS.md` and the complete
`audit/` deliverables first. The audit recommendation is **NO-GO**, scoring
**127/156 (81.4%)**. Do not edit the auditor-owned scores.

The two new hard gates fail:

- `GDPR-01`: **0/4**. Useful security, ownership, retention, cloud-token and
  backup controls exist, but there is no current, complete privacy governance,
  rights, processor/transfer, incident or legal-accountability evidence.
- `DOC-02`: **1/4**. Documentation is extensive, but the main README,
  architecture overview and visuals do not reliably represent the current IDE,
  WASM/debug/audio/auth/cloud/Store/privacy architecture, and there is no
  repository-wide visual provenance/freshness gate.

## Non-negotiable boundary

Do not claim GDPR certification or legal compliance from code/tests. Engage the
deployment's responsible controller, privacy lead and qualified DPO/counsel for
role allocation, Article 6 legal bases, children's and Member-State rules,
DPIA/DPO decisions, processor terms and international transfers. Record review
dates, versions and unresolved questions. Synthetic test users only.

## PR 1 — privacy inventory and accountable decisions

Create `docs/privacy/` with an owned, versioned:

1. Field-level ROPA covering accounts, issuer+subject identities, names/email,
   roles/classes, projects, sprites/audio/assets, artifacts/builds, sessions,
   API/OAuth tokens, Store tickets, IP/user-agent and audit/security logs,
   backups, diagnostics and support evidence.
2. Controller/processor/joint-controller and Article 6/Article 9 matrix for the
   school/operator, Kit, CartridgeStore, IdPs, Google/Microsoft and hosting.
3. Retention/deletion table, recipients/subprocessors, storage locations,
   international-transfer mechanisms and supplementary measures.
4. Children's-data and Member-State decision, DPIA screening/result, DPO
   determination, counsel/DPO status, owners, dates and change history.

Acceptance: every data item has purpose, role, legal basis, access control,
recipient, location, retention/deletion, transfer safeguard and review owner.

## PR 2 — notices and complete rights workflows

Add layered, age-appropriate notices at each collection point. Implement
authenticated, auditable access, rectification, erasure, restriction,
portability, objection and withdrawal/human-review workflows where applicable.
Do not treat a project archive as a personal-data export.

Exercise propagation through SQLite, artifact/build folders, OAuth/token
stores, cloud copies, CartridgeStore boundaries, logs and backup ageing. Define
identity verification, deadlines, exemptions, partial failures and audit
redaction. Revoke external tokens and make every destructive conflict choice
explicit.

Acceptance: tests with synthetic students prove authorization, cross-tenant
denial, structured export completeness, deletion/revocation propagation,
notice-version recording and documented backup expiry.

## PR 3 — processors, transfers, incidents and release evidence

Add the subprocessor register, Article 28/DPA checklist, instruction and
deletion/return obligations, change notification, transfer assessment and
operator configuration warnings. Document Article 32 review and implement a
breach playbook with evidence preservation, risk assessment, the 72-hour
decision timeline, affected-person notification criteria, contacts and a
tabletop exercise.

Acceptance: dated exercise artifacts and redacted operational evidence are in
the release record; unresolved material legal bases, required DPIA, processor
terms, transfer mechanisms or rights failures remain NO-GO.

## PR 4 — truthful entry point and architecture

Keep `README.md` short and setup-focused, but make it accurately link to:

- Blocks, Advanced C and handwritten/generated assembly IDE modes;
- validated real compiler diagnostics and real `.prg32` builds;
- PRG32-QT-derived WASM runtime, source/block debugger and limitations;
- SpriteLab and AudioStudio with eight ADSR voices and stereo;
- guest, registered, school SSO, cloud and CartridgeStore boundaries;
- privacy/operator responsibilities and `docs/privacy/`;
- verified versus unsupported hardware, iOS and real-provider paths.

Replace the stale linear pipeline in `docs/architecture.md` and refresh
`docs/architecture/current-state.md`, `docs/figures/pipeline.svg`,
`docs/figures/game_loop.svg` and related diagrams. Show browser/IndexedDB,
Flask/session, SQLite, build/artifact folders, backups, validators/toolchain,
WASM/debugger/source maps, AudioStudio/AUD0/stereo, IdPs/cloud/Store, personal
data, secrets, retention/deletion and unsupported boundaries.

## PR 5 — visual and documentation freshness gates

Create a visual manifest recording file, purpose, source/recipe, viewport,
browser, theme, locale, synthetic seed, product commit, capture/review date and
reviewer. Refresh every stale PNG/JPEG/SVG/WebP without real personal data,
tokens or school identifiers. Provide meaningful alt text and text equivalents
for complex diagrams.

Add CI checks for broken internal links and image targets, orphan visuals,
missing alt/captions, obsolete routes/config/ABI/labels, contradictions with
`docs/capabilities.json`, ADR/capability ID drift and stale visual-manifest
commits without an explicit review acknowledgement. Include a human release
checklist.

## Existing non-GDPR blockers to preserve

Do not regress the already evidenced deterministic generation, validator-first
compiler checks, source visibility, CSP, ownership, quotas, sandboxing,
debug/cartridge identity, guest local-only behavior or eight-voice audio.
Continue the open work for canonical upstream audio patch adoption, physical
stereo/device evidence, QEMU event alignment, human screen-reader evidence,
desktop PRG32-QT import, real-provider tests and iOS handoff.

## Handoff for independent reaudit

Return exact commits, changed files, commands/results and remaining exceptions,
plus:

- ROPA, role/legal-basis and retention/transfer matrices;
- notice/version history and rights-request test artifacts;
- DPIA/DPO/counsel and breach-exercise status (redacted as needed);
- updated README/documentation map and architecture/data-flow diagrams;
- visual manifest, capture recipes and before/after evidence;
- documentation/privacy CI results.

Request a rescore only when the implementation, operational evidence and
qualified legal decisions are all current for the actual deployment.
