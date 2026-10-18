# PRG32-Construction-Kit — Quality Improvement Round

Work in the `PRG32-Construction-Kit` repository on the `development` branch.

Read and obey the repository-wide `AGENTS.md` before making changes. Inspect the current implementation and tests directly; do not rely only on status documents or earlier summaries.

## Objective

Improve the production readiness of the existing PRG32 construction-kit foundation without claiming that the planned Full IDE, WASM runtime, or machine-level debugger is complete.

This round should address the most important bounded quality and security gaps that can be implemented and tested independently:

1. unsafe default administrator bootstrap;
2. missing build provenance and artifact hashes;
3. revision restoration breaking sprite/asset relationships;
4. missing application-level authentication throttling and administrative audit records;
5. documentation and traceability updates for everything actually changed.

Do not implement unrelated Full IDE features during this round.

## Baseline

The latest independent inspection found:

- Branch: `development`
- Construction Kit HEAD at inspection: `dfed78e4cc86549909bc058a5fd01f6b771a8b07`
- Tests: `266 passed, 12 skipped`
- Python and JavaScript syntax checks passed.
- Real cartridge and ABI tests skipped locally when their external toolchains were unavailable.
- `prg32_construction_kit/sso_protocol.py` matched CartridgeStore byte-for-byte.

Re-establish the baseline before editing and record the current HEAD, working-tree state, runtime versions, test result, failures, and skips.

Preserve unrelated working-tree changes and untracked files.

## Required work

### 1. Secure administrator bootstrap

Eliminate the network-deployable `admin` / `password` default.

Requirements:

- Production and Docker deployments must not silently create an administrator with a well-known password.
- Prefer a clear first-run bootstrap mechanism or fail-fast configuration.
- A simple local classroom/development startup may remain convenient, but insecure behavior must be explicit, visibly warned, and unavailable under production configuration.
- Do not log administrator passwords, registration tokens, bearer tokens, or other secrets.
- Existing installations and existing administrator accounts must continue to work.
- Do not recreate a default administrator after an administrator is renamed or deleted.
- Update Docker Compose, setup, deployment, and administrator documentation.
- Add tests for fresh production startup, explicit bootstrap, existing databases, invalid or missing configuration, and secret non-disclosure.

### 2. Reproducible build provenance

Every cartridge build must record enough immutable metadata to explain what produced it.

At minimum record:

- Construction Kit version or Git revision when available;
- PRG32 SDK version/revision when discoverable;
- portable ABI name, version, and hash;
- selected architecture;
- source language;
- entry prefix;
- requested features and cartridge RAM;
- normalized build-command identity without leaking secrets;
- toolchain/compiler version when discoverable;
- SHA-256 of canonical source;
- SHA-256 and size of every resulting `.prg32`;
- build start/end timestamps and final status.

Requirements:

- Keep build data explainable to students and teachers.
- Do not expose server filesystem paths or secrets.
- Provenance must be stored through the existing build/artifact data model and returned only where appropriate.
- Identical inputs should yield identical canonical source hashes and provenance fields other than timestamps/build identifiers.
- Do not falsely mark source-only bundles as successful cartridge builds.
- Add tests for C, generated assembly, handwritten assembly, failed builds, source-only builds, path redaction, and deterministic fields.
- Toolchain-dependent tests must skip cleanly when the toolchain is unavailable.

### 3. Relationship-safe revision restoration

Fix the known issue where restoring a revision creates new sprite rows and causes artifacts to lose their sprite relationships.

Requirements:

- Determine and document stable identity rules for sprites and assets.
- Restore existing children in place when they represent the same logical item.
- Correctly add, remove, and reorder children to match the selected revision.
- Avoid cross-project or cross-owner reassignment.
- Restoration must be transactional: failure must leave the current project and children intact.
- Existing revision archives must remain readable.
- Add regression tests covering stable IDs, additions, deletions, reordering, artifact relationships, ownership/IDOR, malformed historical data, and rollback after an injected failure.

If preserving relationships requires a schema migration, make it idempotent and compatible with existing SQLite databases.

### 4. Authentication throttling and audit events

Add conservative, understandable application-level protection.

Authentication throttling must cover at least:

- local login failures;
- registration requests;
- registration-token completion;
- API-token creation or other credential-issuing endpoints.

Requirements:

- Key limits safely without trusting arbitrary forwarding headers unless proxy trust is explicitly configured.
- Do not reveal whether a username or email exists.
- Define bounded windows and a recovery path appropriate for classrooms behind shared addresses.
- Include tests for normal use, threshold behavior, expiration, successful-login reset where appropriate, and isolation between principals.
- Document interaction with reverse-proxy rate limits.

Create an administrative audit trail for security-relevant actions, including:

- user creation, update, deletion, enable/disable if supported;
- role and group changes;
- API-token creation and revocation;
- administrator bootstrap;
- publish attempts and results;
- relevant configuration or SSO administrative changes if such endpoints exist.

Audit records must contain actor, action, target, timestamp, outcome, and safe metadata. Never store passwords, raw tokens, SSO tickets, session cookies, or full sensitive request bodies. Access to audit records must be administrator-only and tested for IDOR.

### 5. Documentation and traceability

Update the relevant material under `docs/`:

- architecture and threat boundaries;
- deployment/setup instructions;
- administrator guidance;
- implementation status;
- security review;
- traceability from each changed requirement to source and tests;
- any schema migration or rollback considerations.

Keep `README.md` short and setup-focused.

Do not describe planned work as implemented. Clearly distinguish source inspection, automated validation, external-toolchain validation, and manual validation.

## Non-goals

Do not implement in this round:

- Monaco or a JetBrains-style IDE shell;
- the PRG32-QT WebAssembly port;
- instruction-level browser debugging;
- DWARF, watches, or source breakpoints;
- Google Drive or OneDrive;
- new physical-device or iOS protocols;
- guest IndexedDB projects;
- a new role model that is not coordinated with CartridgeStore;
- arbitrary new assembly directives;
- changes to the required CRUD/action routes;
- silent project changes by an AI assistant.

Do not weaken current C, assembly, archive, ownership, CSRF, or account-switch protections.

## Required validation

Run, where available:

```bash
python3 -m compileall -q app.py prg32_construction_kit tests tools

for file in static/js/*.js static/service-worker.js; do
  node --check "$file"
done

python3 -m pytest -q -rs
```

Also run focused tests while developing.

If the PRG32 SDK and RISC-V toolchain are available, run the real cartridge, ABI, concurrency, and C-versus-assembly differential tests. Otherwise report their exact skips and do not claim they passed.

Inspect the final diff for:

- secrets or raw tokens;
- host paths;
- unrelated changes;
- non-idempotent migrations;
- nondeterministic generated output;
- missing ownership checks;
- documentation claims unsupported by tests.

## Acceptance criteria

The round is complete only when:

- insecure production administrator bootstrap is prevented;
- build provenance and hashes are persisted and tested;
- revision restoration preserves logical child identity and relationships;
- authentication throttling and administrator audit events are implemented and tested;
- existing CRUD, conversion, packaging, SSO, ownership, archive, C-generation, and assembly-generation tests still pass;
- all new database initialization remains idempotent;
- skipped external validations are reported honestly;
- documentation and traceability match the final source;
- there are no unexplained test regressions.

## Final response

Report:

1. branch and inspected starting/final SHAs;
2. working-tree state before and after;
3. concise description of each implemented change;
4. migrations and compatibility impact;
5. security decisions and remaining threat boundaries;
6. exact commands executed with pass/fail/skip counts;
7. external validations that were unavailable;
8. files changed;
9. remaining findings ordered by severity;
10. suggested next PR boundaries.

Cite important claims with exact `path:line` references. Do not claim Full IDE readiness, hardware validation, iOS validation, IdP validation, or WASM execution unless actually demonstrated.
