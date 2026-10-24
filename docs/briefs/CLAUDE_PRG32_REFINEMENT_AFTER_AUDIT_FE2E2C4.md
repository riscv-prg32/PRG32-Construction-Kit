# Claude refinement note after the audit of fe2e2c4

Refine PRG32-Construction-Kit after the independent audit of
`fe2e2c4978ff67c0e3f48987b80187cff40c1094` (2026-10-23). Read `AGENTS.md`
and all current `audit/` deliverables first. Do not edit auditor-owned scores.

Result: **NO-GO, 131/156 (84.0%)**. The score is unchanged because the latest
work supplies strong fixes and evidence, but the decisive Store change is still
an unmerged upstream patch and the Docker process-limit repair was not freshly
demonstrated on Linux.

## Fresh evidence

The broad feasible suite ran with disposable loopback services and compiler
cache access:

```text
1,332 passed, 57 skipped, 3 failed in 271.00 s
```

All three failures are the shared-identity assertions against the adjacent,
canonical, unpatched CartridgeStore `4a3138b`:

- `test_kit_user_can_sign_in_to_the_store`;
- `test_the_username_is_shared_and_the_store_handle_stays_public_only`;
- `test_a_store_only_account_with_the_same_username_is_never_joined`.

Retained evidence reports **91 Store tests** and **89 Kit cross-repository
tests** passing against a clean `4a3138b` clone with
`docs/upstream/cartridge-store-shared-identity.patch` applied. Treat this as
credible proposed remediation, not canonical closure.

## Phase 1 — merge and pin the Store identity contract

The selected contract is settled:

- email matches the account across Kit and Store;
- the private account username is shared and visible only to its owner/admins;
- the Store has a separate pseudonymous public handle for catalogs, scores,
  reviews and multiplayer;
- username or handle collisions never join accounts;
- one-time tickets, roles, scopes and Kit-side publisher authorization remain
  unchanged.

Have CartridgeStore maintainers review and merge the supplied patch or an
equivalent change. Do not copy the patch into runtime code or weaken privacy
notice/CSRF checks merely to make the Kit test pass.

After merge:

1. update the pinned CartridgeStore revision and contract metadata;
2. regenerate `tests/fixtures/contract/` with
   `tools/build_contract_fixtures.py`;
3. verify `sso_protocol.py` remains byte-identical in both repositories;
4. run Store migration tests from pre-handle accounts;
5. run username, email and public-handle collision tests;
6. run the complete live SSO, one-time-ticket and publishing suite against a
   clean merged Store without applying any local patch.

Acceptance: Store tests and the Kit cross-repository suite pass from canonical
commits, and public responses never expose the private username/email.

## Phase 2 — prove the Docker process-limit repair on Linux

The new kernel-count approach addresses a real failure mode: container `/proc`
does not show every process charged to the same host UID, so the old
RLIMIT_NPROC limit could already be exhausted before a compiler started.

Run the Linux/Docker CI scenario with dozens of same-UID processes outside the
build sandbox. Prove both sides:

- an ordinary PRG32 cartridge build starts and finishes;
- a build attempting excess forks is refused within
  `PRG32_BUILD_MAX_PROCESSES`;
- time, memory, open-file, output and disk limits still operate;
- no build process survives timeout/failure;
- production never falls back silently from bubblewrap/AppArmor isolation.

Acceptance: `tests/test_build_sandbox.py::test_the_process_limit_starts_from_what_the_kernel_counts`, the Docker sandbox suite and `tools/check_build.py`
pass in the production image, with logs retained as release evidence.

## Phase 3 — deployment GDPR authorization

Technical `GDPR-01` remains 3/4. Do not invent deployment facts. The actual
controller, with DPO or qualified counsel, must complete decisions D-0–D-10:

- controller/contact/DPO;
- applicable legal bases and Member-State children/education rules;
- completed DPIA and residual-risk decision;
- retention and backup periods;
- named processors, regions, Article 28 terms and transfer mechanisms;
- optional cloud/GitHub/publishing choices for minors;
- staffed breach tabletop and supervisory-authority contacts;
- dated approval and privacy changelog entry.

The release stays NO-GO until these describe the real deployment. Passing code
tests does not establish GDPR certification.

## Remaining ecosystem evidence

1. Merge PRG32 audio/buzzer and PRG32-QT firmware-engine patches upstream and
   regenerate pinned evidence.
2. Resolve frame-triggered audio scheduling alignment.
3. Perform physical PRG32 transfer and stereo eight-voice ADSR/pan capture.
4. Exercise the visible PRG32-QT desktop Import workflow.
5. Complete AudioStudio with a named screen reader.
6. Run test-owned institutional OIDC, Google, Microsoft and GitHub scenarios.

PRG32-iOS remains unsupported; do not invent an interface.

## Preserve

Keep deterministic inspectable C/assembly, validator-first builds, one private
build folder, byte-identical debug cartridges, eight firmware-engine voices,
no buzzer, local-only guest projects, ephemeral guest run builds,
`expected_version` conflict handling, sealed least-privilege provider tokens,
strict CSP, vendored libraries, the one-IDE/fixed-project-type model and
auditor-owned scores.

## Reaudit handoff

Return exact canonical commits, the merged Store contract and migration proof,
Linux production-image logs, completed deployment privacy decisions, exact
test counts, browser/toolchain/device matrix, upstream audio commits and every
remaining limitation.
