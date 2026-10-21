# Breach rehearsal

Run 2026-10-21T18:26:54+00:00 with `tools/breach_rehearsal.py`. **A technical rehearsal by the kit's maintainers, not a staffed exercise:** the controller, the DPO and school leadership were not involved (decision D-10).

Synthetic people only. The addresses come from the RFC 5737 documentation ranges.

## Timeline

| When (UTC) | Step | What |
|---|---|---|
| 2026-10-21T18:26:53+00:00 | setup | throwaway kit: 5 synthetic pupils in class 3B, one project each |
| 2026-10-21T18:26:53+00:00 | incident | someone signs in as s03 from the attacker's address, downloads s03's data, makes an API token and reads projects with it |
| 2026-10-21T18:26:54+00:00 | T0 detection | the audit log shows sign-in activity and a data download for s03 from an address never seen before |
| 2026-10-21T18:26:54+00:00 | containment | sessions ended, account switched off and on again (its API tokens are deleted), password reset |
| 2026-10-21T18:26:54+00:00 | evidence | audit events of the incident exported |
| 2026-10-21T18:26:54+00:00 | assessment | risk assessed and notification decided (rehearsed by the maintainers; a real decision is the controller's and the DPO's) |

72-hour deadline from T0: **2026-10-24T18:26:54+00:00**.

## Assessment and decision (rehearsed)

| | |
|---|---|
| people | 1 |
| children | True |
| data | one pupil's account details (username, email, class), notice records, own projects and the audit events about them; no other pupil's data; no password or token in clear |
| consequences | the pupil's email and school class known to an unauthorised person; their games read |
| risk | risk (not high): a minor's contact details and school class disclosed; contained within minutes |
| notify authority | yes, within 72 hours of T0 (2026-10-24T18:26:54+00:00), because a minor's data was disclosed and the risk is not unlikely |
| tell the person | Art. 34 not required (not high risk); the school's policy is to tell the pupil and family anyway, with what to do (new password, watch for phishing) |
| processors to tell | none involved |
| measures | sessions ended, API tokens deleted, password reset, consider: alert on sign-ins from new addresses (finding F-2) |

## Findings

| Id | Finding | Status |
|---|---|---|
| F-1 | Local sign-ins were not in the audit log before this work; added (login, login_failed with the address, never the typed text) | fixed |
| F-2 | No alert on sign-ins from a new address: detection relies on someone reading the audit log | open |
| F-3 | Ordinary reads of projects are not audited (S-5): the extent of what an API token read is inferred from its scope and last_used | open |
| F-4 | Contacts in the playbook are blank until the controller fills them in (D-10) | open |

Evidence: `audit-extract.json`, with its SHA-256 in `timeline.json`.
