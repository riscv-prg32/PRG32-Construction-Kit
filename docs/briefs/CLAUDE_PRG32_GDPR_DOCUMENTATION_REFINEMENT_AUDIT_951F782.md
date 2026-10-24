# Claude refinement audit note: GDPR and documentation hard gates

Use this note to refine PRG32-Construction-Kit after the audit of
`951f782f3c54a306d2bad70396127fc74a596158`. The governing audit brief now adds
two mandatory rows: `GDPR-01` and `DOC-02`. They increase the matrix from 37
to 39 scored requirements and the denominator from 148 to 156.

Follow `AGENTS.md`, all ADRs and the existing security/storage constraints.
Do not edit auditor-owned scores. Return implementation and operational evidence
for an independent rescore.

## Important legal boundary

“Perfect GDPR compliance” cannot be established by code changes or automated
tests alone. The required outcome is current, demonstrable compliance for the
actual deployment and processing context, with qualified privacy counsel or the
responsible DPO approving legal judgments, Member-State rules, controller/
processor allocations, legal bases, DPIA conclusions and transfer mechanisms.
Do not describe the product as GDPR-certified or guarantee compliance merely
because this checklist passes.

Primary legal references to keep current:

- [Regulation (EU) 2016/679 — consolidated GDPR text](https://eur-lex.europa.eu/eli/reg/2016/679/)
- [European Commission — obligations for organisations](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/obligations_en)
- [European Commission — rights of individuals](https://commission.europa.eu/law/law-topic/data-protection/information-individuals_en)
- [European Commission — GDPR processing principles](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en)
- [EDPB guidelines and recommendations](https://www.edpb.europa.eu/our-work-tools/general-guidance/guidelines-recommendations-best-practices_en)

Record the review date and exact guidance/version used. Reassess when law,
supervisory guidance, subprocessors or product data flows change.

## GDPR-01: required implementation and evidence

### 1. Governance and processing inventory

Create a maintained privacy area under `docs/privacy/` containing:

- controller, processor and joint-controller role analysis for classroom
  operators, schools, the Kit, CartridgeStore, identity providers, Google Drive,
  Microsoft Graph and hosting/backup operators;
- an Article 30-style ROPA/data inventory with every field and derived identifier;
- purposes, Article 6 legal bases and Article 9 analysis where applicable;
- data-subject categories, explicitly including students and minors;
- recipients, subprocessors, storage locations and international transfers;
- retention/deletion schedule and documented exceptions;
- owner, review date and change history for each processing activity.

Inventory at least accounts, external identities, email/display names, academic
roles/classes, projects, sprites, audio and other assets, artifacts/builds,
cloud tokens, API tokens, Store tickets, sessions/cookies, IP/user-agent and
security/audit logs, backups, diagnostics and support evidence.

### 2. Privacy notices and lawful collection

Add concise, layered and age-appropriate privacy notices at every collection
point. They must identify controller/DPO contacts where applicable, purposes,
legal basis, categories, recipients, transfers, retention, rights, complaint
route, source of indirectly obtained data and automated-decision information.

Do not default to consent. Where consent is genuinely used, prove it is freely
given, specific, informed, unambiguous, recorded, granular and as easy to
withdraw as to give. Determine applicable Member-State rules for children's
consent and educational/public-interest processing with counsel/DPO input.

### 3. Data-subject rights

Implement authenticated, auditable workflows for:

- information and access;
- rectification;
- erasure;
- restriction;
- portability in a structured machine-readable format;
- objection where applicable;
- withdrawal of consent;
- human review where automated decision rules apply;
- complaint and DPO/controller contact.

Exercise requests end to end across SQLite, artifact/build folders, cloud copies,
CartridgeStore identity/tickets, OAuth/token stores, logs and backups. Document
identity verification, response deadlines, exemptions, partial failures and
how backup deletion ages out. A project archive alone is not a complete personal-
data export.

### 4. Privacy by design and default

Make the default classroom deployment minimise data:

- guests remain local-only;
- collect no analytics, tracking or optional identifiers by default;
- minimise logs and redact credentials, tokens, project content and student data;
- restrict teacher/facilitator supervision to the documented least privilege;
- use shortest justified retention and privacy-preserving defaults;
- separate tenants/classes and test IDOR/cross-account boundaries;
- encrypt secrets/tokens and document encryption/key operations;
- require explicit user choices for cloud overwrite/copy conflicts.

### 5. Processors, transfers and contracts

Maintain a subprocessor register, processor instructions, Article 28 contract/
DPA checklist, deletion/return obligations, security commitments, audit support
and change-notification procedure. For data leaving the EEA, document the
transfer mechanism, destination, supplementary measures and transfer impact
assessment where required. Configuration must not imply that enabling Google,
Microsoft, an IdP or CartridgeStore automatically supplies a lawful basis or
valid transfer mechanism.

### 6. Security, breaches, DPIA and DPO

Document and test:

- Article 32 risk-based controls and periodic effectiveness review;
- breach detection, evidence preservation, risk assessment and the supervisory-
  authority notification workflow, including the 72-hour decision timeline;
- notification to affected people when required;
- incident roles, templates, contacts and tabletop exercise;
- DPIA screening and a completed DPIA where high-risk processing is likely,
  especially systematic educational monitoring or children's data;
- whether a DPO is mandatory, the reasoned decision, independence and contact;
- prior-consultation escalation when residual high risk cannot be mitigated.

### 7. Tests and release evidence

Add tests for privacy-route authorization, complete export, deletion propagation,
retention, backup behavior, token revocation, audit redaction, notice/version
recording, consent withdrawal where applicable, cross-tenant denial and breach-
workflow timing. Use synthetic students only.

The release evidence must include counsel/DPO review status and unresolved legal
questions. Any material unresolved legal basis, children's-data safeguard,
required DPIA, processor/transfer mechanism or rights failure is NO-GO.

## DOC-02: README, screenshots, images and architecture schemas

### 1. Rewrite the main README as the accurate entry point

Update root `README.md` to reflect the current product rather than the earlier
Blocks/simulator-only shape. It must cover:

- Full IDE modes and safe real-compiler diagnostics;
- real cartridge toolchain and supported targets;
- WASM runtime/debugger;
- SpriteLab and AudioStudio with eight SID-like ADSR voices/stereo;
- account, guest, school SSO, cloud and CartridgeStore boundaries;
- privacy/GDPR operator responsibilities and link to `docs/privacy/`;
- current quick-start, deployment, configuration and security warnings;
- explicit unsupported/unverified areas such as physical hardware or iOS when
  still true;
- a current documentation map.

Keep README setup-focused as required by `AGENTS.md`; link to detailed docs
rather than duplicating them.

### 2. Refresh every visual

Inventory all PNG/JPEG/SVG/WebP/diagram sources and every Markdown reference.
Replace stale UI screenshots, including the main README hero, with captures from
the audited revision using synthetic data. Define viewport, browser, theme,
locale, seed project and capture command/manual procedure.

For each visual:

- store reproducible source or a documented refresh recipe;
- record product commit and capture date;
- provide meaningful alt text and, for complex diagrams, a text equivalent;
- remove secrets, tokens, real names/emails, school identifiers and personal data;
- verify legibility in light/dark rendering and at common zoom levels;
- avoid claiming hardware/provider behavior the image did not demonstrate.

### 3. Update architectural schemas

Refresh `docs/architecture.md`, `docs/architecture/current-state.md`,
`docs/figures/pipeline.svg`, `docs/figures/game_loop.svg` and any other
architecture diagrams so they show:

- browser/PWA, Flask, SQLite and artifact/build boundaries;
- validated Blocks/C/assembly pipelines and real toolchain;
- PRG32-QT/WASM and debugger/source-map flows;
- AudioStudio/AUD0/stereo firmware-engine path;
- guest, registered, school SSO, cloud and CartridgeStore flows;
- controller/processor and personal-data trust boundaries;
- token/secret boundaries, retention/deletion and backups;
- external systems and unsupported/unverified paths.

Diagram labels, route names, ABI versions and component names must be generated
or checked against current sources where practical.

### 4. Automated freshness gates

Add CI checks for:

- broken internal/external links and missing image targets;
- orphaned or unreferenced documentation visuals;
- missing alt text/captions;
- obsolete routes, configuration names, labels, ABI versions and feature claims;
- README/docs contradictions with `docs/capabilities.json`;
- architecture capability IDs and ADR references;
- screenshot/diagram manifest entries whose recorded commit is older than a
  relevant UI/architecture change without an explicit review acknowledgement.

Include a human documentation/visual review checklist in release evidence.
Stale visuals that materially misstate privacy, security, setup, architecture,
API or supported behavior are release blockers.

## Suggested implementation sequence

1. Privacy data-flow discovery and field-level ROPA.
2. Counsel/DPO role, legal-basis, children's-data, DPIA and transfer decisions.
3. Privacy notices, rights endpoints/workflows and operator documentation.
4. Retention/export/erasure propagation and breach-response automation/tests.
5. README and documentation information architecture.
6. Screenshot/image inventory and reproducible capture refresh.
7. Architecture diagrams with privacy/trust/data-flow overlays.
8. Link, accessibility, capability-consistency and visual-freshness CI gates.
9. Independent GDPR/documentation audit and legal sign-off.

Keep GDPR work and documentation refresh in reviewable commits. Avoid combining
legal-policy decisions with unrelated refactors.

## Handoff to the auditor

Return:

- updated processing inventory/ROPA, role/legal-basis matrix and retention table;
- privacy notices and version history;
- rights-request and breach-exercise results;
- processor/subprocessor and international-transfer evidence;
- DPIA/DPO/counsel decisions with confidential details redacted appropriately;
- updated README and documentation map;
- visual manifest, refresh recipes and before/after screenshots/diagrams;
- automated documentation/privacy test commands and results;
- exact remaining exceptions.

Do not claim “perfect GDPR compliance” until the technical, operational and legal
evidence is current for the actual deployment and qualified counsel/DPO has
approved the applicable conclusions.
