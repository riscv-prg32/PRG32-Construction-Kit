# Claude refinement note after the audit of bb2b062

Refine PRG32-Construction-Kit after the independent audit of
`bb2b0625abd6b9740948c12f4c7b55170bcdd8b0` (2026-10-22). Read `AGENTS.md`
and every file in `audit/` first. Do not edit auditor-owned scores.

Audit result: **NO-GO, 131/156 (84.0%)**.

## What the refinement closed

- `GDPR-01` technical implementation rose from 0/4 to **3/4**: generated
  field-level ROPA; layered/versioned notices; full personal-data export;
  request tracking; rectification procedure; erasure across known tables,
  files and tokens; restriction; backup re-erasure; processor/transfer
  templates; breach playbook and synthetic rehearsal.
- `DOC-02` rose from 1/4 to **4/4**: truthful README and architecture,
  generated diagrams, synthetic screenshots, complete visual manifest,
  capture recipes, reviewer/date records and CI freshness/link/alt/claim gates.
- Guest full-IDE run builds, runtime settings, the one-IDE layout and GitHub
  remote support have substantial source and test coverage.

Fresh execution produced **1,330 passed, 56 skipped, 1 failed**. A focused
privacy/docs/security run produced **441 passed, 1 skipped**. Browser tests
could not run locally because Chrome/Playwright Chromium is absent; the forced
run refused 40 setups rather than silently passing.

## Hard gate 1 — complete the actual deployment's GDPR decisions

The repository correctly says NO-GO while `docs/privacy/decisions.md` D-0–D-10
remain open. This is not a code-generation task and must not be filled with
invented facts.

The deploying controller, with its DPO or qualified counsel, must:

1. name the controller, privacy contact and DPO and configure the displayed
   controller/contact values;
2. select and document the legal basis for each processing activity and the
   applicable national education/children rules;
3. complete and approve the DPIA, including residual risk and any required
   prior consultation;
4. approve retention periods, request-register retention and backup ageing;
5. name hosting/email/identity/cloud/GitHub/Store parties, roles and regions;
6. execute Article 28 terms, joint-controller arrangements where applicable,
   and transfer assessments/mechanisms;
7. decide whether optional cloud, GitHub and publishing services are enabled
   for minors and how any valid consent is obtained/withdrawn;
8. fill breach contacts and supervisory authority details, then run a staffed
   tabletop with the controller's incident lead, privacy lead, DPO and school
   leadership;
9. record decisions, dates, owners, review versions and unresolved questions in
   the privacy changelog and release evidence.

Acceptance: no material release-blocker row remains open, the DPO/counsel review
is dated, and the records describe the real deployment. Never describe the
software as GDPR-certified solely because tests pass.

## Hard gate 2 — reconcile Kit/CartridgeStore shared identity

The sole fresh test failure is reproducible:

```text
tests/test_sso_with_cartridge_store.py::test_kit_user_can_sign_in_to_the_store
expected username: ada
actual username:   player-<random>
```

Authentication succeeds, so this is not evidence of an auth bypass. It is a
contract mismatch between the Kit's documented shared username and the current
adjacent CartridgeStore behavior.

Choose and document one canonical model with both repository maintainers:

- preserve the Kit username when the Store imports/authenticates the shared
  account; or
- intentionally use a pseudonymous Store display name, version the shared SSO
  contract, migrate old accounts safely, update UI/docs/tests, and ensure stable
  issuer+subject/account identity does not depend on the display name.

Do not weaken issuer/subject identity, ticket single-use, role/scope checks or
publisher authorization. Keep `sso_protocol.py` byte-identical across repos.

Acceptance:

```bash
python3 -m pytest -q tests/test_sso_with_cartridge_store.py \
  tests/test_sso.py tests/test_sso_live.py tests/test_publish_authorization.py
```

must pass against pinned clean Kit and CartridgeStore revisions, with migration
and collision tests for the chosen identity model.

## Remaining ecosystem gates

1. Merge the buzzer-retirement, firmware-audio Qt integration and QEMU
   clock/reset behavior into canonical PRG32/PRG32-QT revisions; update pins and
   regenerate evidence.
2. Resolve the remaining frame/audio scheduling ambiguity for effects and prove
   whole-recording event alignment.
3. Run physical PRG32 transfer and stereo capture with the prepared eight-voice
   ADSR/pan cartridge and comparator.
4. Exercise the visible PRG32-QT desktop Import workflow.
5. Complete AudioStudio tasks with a named screen reader and record OS/browser/
   assistive-technology versions and defects.
6. Run safe, test-owned institutional OIDC, Google, Microsoft and GitHub
   scenarios; do not use real student data or publish a public cartridge.

PRG32-iOS remains explicitly unsupported; do not invent a delivery interface.

## Preserve these invariants

- deterministic inspectable generated C and RISC-V assembly;
- validator-first compilation and one private folder per build;
- byte-identical debug/non-debug PRG32 cartridge;
- eight firmware-engine voices, independent ADSR and stereo, no buzzer;
- guest data in IndexedDB only, ephemeral bounded guest run builds;
- `expected_version` conflict handling and explicit cloud overwrite choices;
- sealed tokens, fixed provider hosts, least privilege and redacted audit logs;
- one IDE, fixed project type, tools as project tabs;
- strict CSP, vendored browser libraries and static-only service-worker cache;
- auditor-owned scores remain unchanged by implementation work.

## Reaudit handoff

Return:

- exact Kit, PRG32, PRG32-QT and CartridgeStore commits;
- the resolved shared-identity contract and passing cross-repository tests;
- completed deployment privacy decisions and redacted approval/tabletop evidence;
- exact commands, pass/fail/skip counts and browser/toolchain/device matrix;
- canonical upstream audio commits and regenerated PCM/ADSR/hardware evidence;
- every remaining limitation, especially real-provider, hardware, accessibility
  and unsupported iOS status.

Request reassessment only after the legal/operational decision owners have acted
and the complete feasible suite has no unexplained product failure.
