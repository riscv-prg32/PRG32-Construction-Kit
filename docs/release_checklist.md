# Release checklist

What a person checks before a release, after CI is green. CI already runs the tests, the
browser suites, the toolchain container and `tools/check_docs.py`. This list is what
machines cannot judge. Copy it into the release notes and tick each line with your name.

## Documentation

- [ ] **README.md** describes the product as it is now. Each feature links to its guide, and
  the "verified / not verified" table matches [capabilities.md](capabilities.md).
- [ ] [architecture.md](architecture.md) still matches the code: new components, new
  external services, changed trust boundaries. If not, update
  `tools/build_diagrams.py`, run it, and update the tables.
- [ ] **Screenshots** show today's pages. If a page changed, run
  `python3 tools/capture_visuals.py`, look at each picture, and record the review in
  [figures/manifest.json](figures/manifest.json) (`reviewed`, `reviewer`).
- [ ] **No real people in any picture or record**: no real names, emails, school names,
  tokens or addresses. Synthetic accounts and documentation addresses only.
- [ ] Alt texts and diagram descriptions say what the picture shows, not just its title.
- [ ] Every new feature has a short explanation for teachers or students in `docs/` or
  `docs/tutorials/` (AGENTS.md).
- [ ] [release-notes.md](release-notes.md) lists what changed, including what is still not
  verified.

## Privacy (for a deployment, by the controller)

- [ ] [privacy/decisions.md](privacy/decisions.md): no release-blocking line open. Otherwise
  the deployment is NO-GO.
- [ ] Notice texts changed? Raise their version ([privacy/notices.md](privacy/notices.md)).
- [ ] New table, column or external service? [privacy/ropa.json](privacy/ropa.json) and
  [privacy/processors_and_transfers.md](privacy/processors_and_transfers.md) are updated
  (the tests refuse an unclassified column).
- [ ] Retention, backup pruning and log rotation are scheduled
  ([privacy/retention.md](privacy/retention.md)).
- [ ] Breach contacts are current. The last staffed exercise is less than a year old
  ([privacy/exercises/](privacy/exercises/README.md)).

## Evidence

- [ ] CI run for the release commit is green, and its artifacts are kept
  ([evidence.md](evidence.md)).
- [ ] The live suites were run where services are available
  ([live_testing.md](live_testing.md)). What was not run is written down as not run.
- [ ] Audit scores are the auditor's: no change to `audit_score` in `capabilities.json`.

| Checked by | Date | Release commit |
|---|---|---|
| | | |
