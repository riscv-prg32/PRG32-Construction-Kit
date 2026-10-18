# Remediation status

Status at audited revision `6b7aac93554bcdbbeeb0c7b80fcad576b1a9bea6`.

| Prior finding | Status | Current evidence |
|---|---|---|
| H-01 Store SSRF | Implemented and verified by source/tests; live Store unverified | ADR-0008, `store_policy.py`, `publisher.py`, `tests/test_store_egress.py`. |
| H-02 publisher role/confirmation | Implemented and verified locally | ADR-0009, `publishing.py`, `routes.py:1004-1125`, `tests/test_publish_authorization.py`; targeted suite passed. |
| H-03 unsandboxed builds | Implemented; Linux/container execution not independently repeated in this audit | ADR-0010, `build_sandbox.py`, `build_guard.py`, `packager.py`, `tests/test_build_sandbox.py`; macOS-safe subset passed and Linux cases skipped cleanly. |
| H-04 Full IDE incomplete | Open and renamed H-01 in the current findings | `templates/editor.html:72-82`; `docs/traceability.md:32`. |

The security remediations raise STR-02 to 3 and SEC-01 to 3. The release remains **NO-GO** because the Full IDE shell/language services and mandatory source-level debugger behavior are still missing.

## Developer updates since this audit (not audited)

- Refinement phase 0: the named design baseline is committed unchanged as
  `docs/briefs/CLAUDE_PRG32_CONSTRUCTION_KIT_IMPLEMENTATION.md`, with ADR-0011
  recording its role (baseline, not superseded) and precedence (former L-02).
  `docs/architecture/current-state.md` rewritten for the current source.
  `docs/capabilities.json` is the machine-checked status table
  (`tests/test_capabilities.py`); it copies audit scores without changing them.
