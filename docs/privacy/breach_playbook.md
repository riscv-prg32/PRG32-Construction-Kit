# Personal-data breach playbook (Articles 33 and 34)

**Version 1.0, 2026-10-21. Contacts to be filled in by the controller (D-10).**

A personal-data breach is any security incident that leads to personal data being
**destroyed, lost, altered, disclosed or accessed without authorisation**. Examples:

- a leaked password or API token used by someone else;
- a backup left readable;
- a server compromised;
- a wrong person given the admin role;
- data lost with no backup.

## Contacts (fill in)

| Role | Name | How to reach them |
|---|---|---|
| Incident lead (operator) | | |
| Controller's privacy lead | | |
| DPO | | |
| Hosting provider's security contact (processor) | | |
| Supervisory authority, with its online breach form | | |
| School leadership, to tell families | | |

## The clock

**T0 is when the controller becomes aware** that a breach has happened, meaning reasonably
certain, not just suspecting. Notification to the supervisory authority is due **within 72
hours of T0**, unless the breach is *unlikely to result in a risk* to people (Art. 33(1)). A
processor tells the controller without undue delay (Art. 33(2)). Late notification needs its
reasons.

| By | Step |
|---|---|
| T0 + 1 h | **Contain:** stop the leak. Each action is in the audit log:<br>• revoke tokens (`DELETE /auth/tokens/<id>`, or deactivate the account, which deletes its tokens);<br>• end sessions (`POST /api/users/<id>/sessions/revoke`);<br>• reset passwords;<br>• disconnect cloud accounts;<br>• take a server offline if needed. |
| T0 + 4 h | **Preserve evidence**, before retention or rotation removes it:<br>• export the audit log (`GET /api/admin/audit?limit=1000`, filtered by address or account, as `tools/breach_rehearsal.py` shows);<br>• copy the server logs;<br>• take a backup with `tools/backup_restore.py backup`, and keep it out of pruning while the incident is open.<br>Record the SHA-256 of each file. |
| T0 + 24 h | **Assess:**<br>• whose data, which data, how many people, and whether children are among them;<br>• what could happen to them: identity misuse, embarrassment, loss of work;<br>• whether the data is unintelligible (hashed or encrypted) or was recovered.<br>Record the risk level: none / risk / high risk. |
| T0 + 48 h | **Decide**, and write down why:<br>• notify the supervisory authority (Art. 33)?<br>• tell the people affected (Art. 34)?<br>• tell processors and the Cartridge Store's operator? |
| **T0 + 72 h** | **Notify the authority**, unless no risk was found. Partial information is acceptable, and the rest follows in phases (Art. 33(4)). |
| without undue delay | **Tell the people affected** when the risk is high, and their families for children: in plain language, what happened, what it means, what was done, what they can do, and whom to contact (Art. 34(2)). Not needed when the data was unintelligible to the attacker, when later measures removed the high risk, or when telling everyone individually would take disproportionate effort (then a public notice instead) (Art. 34(3)). |
| T0 + 30 days | **Learn:** what failed, what changes, and the playbook updated. |

Every breach, notified or not, goes into the **breach register** (Art. 33(5)) with these
fields:

- facts and timeline;
- the data and the people affected;
- the consequences;
- the measures taken;
- the decision on notification and its reasons;
- the reference numbers of any notification.

Use the template in [exercises/](exercises/).

## Risk: a rough guide for the kit's data

| Data involved | Usual risk |
|---|---|
| Games, sprites, sounds (no real names) | low |
| Usernames, emails, class membership of minors | risk: notify the authority unless clearly unlikely |
| Password hashes or API token hashes | risk: force password resets |
| Encrypted cloud tokens together with the secret key (from a backup) | high: revoke at the providers, tell the people affected |
| A whole backup, or the database, with the secret key | high |
| Data that was only altered or lost, and was restored from a backup | depends on how long, and on what was missed |

## Evidence collected by the kit

- Audit events: sign-ins, sign-in failures and throttling, token use per scope, role changes,
  deletions, exports, privacy requests, cloud connections, publishing. Each records the
  time, the actor and the address the request came from.
- API tokens: `last_used`.
- **Not logged:** ordinary reads of projects by their owner or teacher. This is open item S-5,
  found in the 2026-10-21 rehearsal. Server access logs cover reads when the operator keeps
  them.
