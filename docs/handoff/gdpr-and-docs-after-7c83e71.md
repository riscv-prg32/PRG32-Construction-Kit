# Handoff after the GDPR and documentation audit of 7c83e71

This answers `audit/CLAUDE_REFINEMENT_AFTER_GDPR_DOC_AUDIT_7C83E71.md` (127/156, NO-GO).
Scores are the auditor's: `docs/capabilities.json` gains the two new rows GDPR-01 (0) and
DOC-02 (1) with the auditor's scores, and otherwise has only notes and evidence updated.

**Boundary.** Nothing here claims GDPR certification or legal compliance. The project owner
chose that the records name **the deploying school or operator as controller**: the kit's
behaviour is described exactly, and every legal decision is a proposal. No DPO or counsel
has been engaged, so legal bases, the DPIA, the DPO determination, processor terms and
transfer mechanisms are all **open**. A deployment is **NO-GO** until they are decided
(`docs/privacy/decisions.md`, D-0 to D-11). Synthetic people only, everywhere.

## Commits

| Commit | What |
|---|---|
| `622b2d4` | The auditor's update (audit files, brief) |
| `d68a0e7` | PR 1–3: `docs/privacy/`, rights workflows, notices, breach playbook and rehearsal [GDPR-01] |
| `ea005c9` | Session cookie sent only when it changes (found by the live Keycloak suite) |
| this commit | PR 4–5: README, architecture, diagrams, visual manifest, `tools/check_docs.py` in CI, release checklist [DOC-02] |

## PR 1: inventory and accountable decisions

| Deliverable | Where | Checked by |
|---|---|---|
| Field-level record of processing: every column of all 23 tables, plus 10 stores outside the database. Each entry has purpose, people, legal basis (proposed), special categories, access, recipients, location, retention, deletion, transfers, review owner and next review. | `docs/privacy/ropa.json` → `ropa.md` (`tools/render_ropa.py`) | `tests/test_privacy_records.py::test_the_record_of_processing_names_every_column_once`, `…rendered_from_the_json` |
| Controller / processor / joint-controller matrix; Article 6 and 9 per activity | `docs/privacy/roles_and_legal_bases.md` | review (proposals) |
| Retention and deletion; recipients and subprocessors; storage locations; transfers and supplementary measures | `retention.md`, `processors_and_transfers.md` | `tests/test_privacy_rights.py` (retention, backups) |
| Children and Member State rules, DPIA screening (result: recommended, not done), DPO determination (not engaged), owners, dates, change history | `children_dpia_dpo.md`, `decisions.md`, `CHANGELOG.md` | `test_nothing_claims_the_gdpr_gate_while_a_blocker_is_open` |

## PR 2: notices and rights

- **Notices:**
  - six notices (guest, account, school_sign_in, cloud, publishing, classes), version 1.0;
  - a short layer at each collection point, a full layer in `docs/privacy/notices/`, and a
    public `/privacy` page;
  - the version each signed-in person was shown is recorded in `privacy_notice_records`.
- **Rights** (`prg32_construction_kit/privacy.py`, ADR-0022; procedure in
  `docs/privacy/rights_requests.md`):
  - structured export, not a project archive;
  - a request register with 30-day deadlines, extensions with reasons, identity-check
    notes, refusals with reasons, and pseudonyms after erasure;
  - restriction (HTTP 423 on any change);
  - erasure across tables, build folders, artifact files, sample folders and cloud tokens
    (revoked at Google), with the audit log pseudonymised, Store publications listed, and
    the Store told when accounts are shared;
  - backups dated and pruned (`backup_restore.py prune`), and the erasure register
    re-applied after a restore.
- **Tests with synthetic students** (`tests/test_privacy_rights.py`, 10 tests):
  - authorization, cross-account denial, API tokens refused;
  - export completeness without secrets;
  - erasure propagation: no cell in any table names the student afterwards, no file or
    folder is left, the token is revoked;
  - the restored-backup case;
  - restriction;
  - notice-version recording;
  - backup expiry;
  - audit-log expiry.
- **Defects fixed on the way:**
  - uploaded artifact files were never deleted;
  - local sign-ins were not audited;
  - the session-cookie race.

## PR 3: processors, transfers, incidents

- **Processors and transfers** (`processors_and_transfers.md`):
  - the subprocessor register: hosting, SMTP, identity provider, Google, Microsoft,
    Cartridge Store;
  - the Article 28 checklist, including deletion or return, change notification and breach
    notice;
  - the transfer assessment, and the settings that create transfers.
- **Article 32 review** with open items (`security_article32.md`):
  - **S-1:** Store bearer tokens stored in clear;
  - S-2 to S-4: the operator's configuration and a penetration test;
  - S-5 and S-6: found in the rehearsal.
- **Breach playbook** (`breach_playbook.md`):
  - evidence preservation;
  - risk assessment;
  - the 72-hour timeline;
  - Article 34 criteria;
  - contacts, still blank (D-10).
- **Rehearsal:** `tools/breach_rehearsal.py`, recorded in
  `docs/privacy/exercises/2026-10-21-breach-rehearsal/`:
  - detection from the audit log, then containment: the stolen token and session both get
    401 afterwards;
  - the evidence extract has its SHA-256 recorded;
  - the assessment and the 72-hour deadline are written down;
  - findings F-1 (fixed), F-2, F-3, F-4.

  **This is a technical rehearsal, not a staffed exercise.**

## PR 4: entry point and architecture

- `README.md`: short and setup-focused. It links each IDE mode, the real compiler and
  builds, the WebAssembly runtime and debugger with their limits, Sprite Lab and AudioStudio
  (8 voices, ADSR, stereo), and the guest, registered, school sign-in, cloud and Store
  boundaries. It points to the privacy and operator responsibilities, and has a
  verified / not verified / unsupported table.
- `docs/architecture.md`: rebuilt around four generated diagrams (`tools/build_diagrams.py`):
  - components and trust boundaries;
  - from source to cartridge;
  - the game loop and frame clock;
  - personal data and retention.

  The tables show each component's code location, the secrets, retention, and what is
  unsupported. The stale pipeline through the JavaScript simulator, and the "validation is
  not an OS sandbox" remark, are gone.
- `docs/architecture/current-state.md` and `docs/index.md` refreshed.

## PR 5: visual and documentation freshness

- **`docs/figures/manifest.json`:** all 54 tracked pictures (vendored library media
  excluded). Each records purpose, kind, recipe, viewport, browser, theme, locale, seed,
  product commit, capture date, reviewer and review date, plus the paths it shows (`watch`).
  Release evidence is `frozen`.
  - Re-captured from synthetic data (`tools/capture_visuals.py`): the README hero (the IDE)
    and the five editor screenshots.
  - Re-rendered: 12 simulator and PRG32-QT frames (`tools/runtime_check.py --figures`) and
    5 title screens (`tools/simulate.js`), all **identical pixel for pixel**.
  - QEMU frames: re-rendered afterwards from a scratch clone of SDK `679dfb5` with the cicd
    QEMU build (all six games pass). QEMU runs on the host clock, so its picture is a
    different moment of the same game on every run. The games README now says so, instead
    of claiming "the same frame on three runtimes".
  - Before and after: the old README hero showed the classic editor (git history of
    `docs/figures/PRG32-Construction-Kit_01.png`); the new one shows the IDE.
- **`tools/check_docs.py`**, in the CI Python job, with `fetch-depth: 0`. It checks:
  - broken internal links and images, and missing alt text;
  - SVG titles and descriptions;
  - manifest completeness, review dates and staleness (a content diff of the watched paths
    since the commit shown, unless a person acknowledged it);
  - orphan pictures;
  - settings, routes and ABI versions named in current docs;
  - ADR and capability IDs, and README status tags.

  `tests/test_docs_check.py` proves that each check catches a planted problem.
- `tools/build_diagrams.py --check` and `tools/render_ropa.py --check` also run in CI.
- Human release checklist: `docs/release_checklist.md`.

## Commands and results (macOS, this machine)

| Command | Result |
|---|---|
| Full `pytest` with `PRG32_REQUIRE_BROWSER=1 PRG32_REQUIRE_SDK=1`, RISC-V toolchain and SDK on PATH | **1218 passed, 0 failed, 45 skipped** (skips listed in current-state.md) |
| `tools/check_docs.py`, `build_diagrams.py --check`, `render_ropa.py --check`, `render_capabilities.py --check`, `service_worker_lock.py --check`, `ruff check .` | all clean |
| `tools/run_live_suites.py` (throwaway Store, disposable Keycloak 26.0.7, QEMU), at the final state | Store 11, Keycloak 9, QEMU 1 passed; school tenant and cloud not run |
| `tools/breach_rehearsal.py` | record in `docs/privacy/exercises/` |

## After the handoff: open items closed

| Item | Now | Checked by |
|---|---|---|
| S-1: Store bearer tokens in clear | Encrypted at rest (`secrets_at_rest.py`); older databases encrypted at start-up; a changed secret key gives a clear refusal | `tests/test_publish_authorization.py` (3 new tests) |
| S-5: reads not audited | Every API-token request logged (`api_token_use`: method and path) | `tests/test_security_controls.py::test_what_an_api_token_does_is_in_the_audit_log` |
| S-6: no alerting | `login_new_address`, an email to the person, *Recent sign-ins* on the Account page | `tests/test_security_controls.py::test_a_sign_in_from_a_new_address_is_logged_and_the_person_told` |
| R-1: request register retention | `PRG32_KIT_PRIVACY_REQUEST_DAYS` (0 = keep until the controller decides) | `tests/test_privacy_rights.py::test_answered_requests_expire_only_when_the_controller_sets_a_period` |
| CI on `b12b4e8` | The generated diagrams were reported stale against their own generator. Their freshness is now `build_diagrams.py --check`, and the checker compares against the working tree. | CI |

## Remaining exceptions

1. **GDPR-01 stays NO-GO.** No controller decisions, no DPO or counsel review, no DPIA, no
   processor agreements, no staffed breach exercise. S-1, S-5, S-6 and R-1 were closed
   afterwards (above).
2. Reads in a signed-in browser are left to the server's access logs.
3. Carried over: the upstream audio PRs are unmerged (PRG32#45, #46, PRG32-QT#1); no
   physical stereo capture or console delivery; no human screen-reader session; the PRG32-QT
   desktop Import menu was not driven (computer use was unavailable); no real Google,
   Microsoft or school tenant; iOS unsupported.
