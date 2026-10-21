# Privacy: records, decisions and procedures

**Version 1.0, 2026-10-21. Owner: the deploying school's or operator's privacy lead.**

The PRG32 Construction Kit is software. The school or organisation that runs it is the
**controller** of the personal data in it. That organisation makes the legal decisions,
with its Data Protection Officer (DPO) or counsel.

This folder gives them two things:

- an exact description of what the kit does with personal data;
- the procedures and tools to run it lawfully.

> **Status: NO-GO for a deployment until the controller has made the decisions in
> [decisions.md](decisions.md).** Nothing here is legal advice. Tests prove what the
> software does. They do not prove that a deployment complies with the GDPR. No DPO or
> counsel has reviewed this material yet (2026-10-21).

## What is here

| Document | What it answers |
|---|---|
| [ropa.md](ropa.md) (from [ropa.json](ropa.json)) | Article 30 record, field by field. Every database column and every other store: purpose, legal basis, access, recipients, location, retention, deletion, transfers, review owner. |
| [roles_and_legal_bases.md](roles_and_legal_bases.md) | Who is controller, processor or joint controller; Articles 6 and 9, per party and activity. |
| [retention.md](retention.md) | How long each thing is kept, and what deletes it. Includes backups, logs, and restoring a backup after an erasure. |
| [processors_and_transfers.md](processors_and_transfers.md) | Subprocessor register, Article 28 checklist, international transfers, and the settings that create transfers. |
| [children_dpia_dpo.md](children_dpia_dpo.md) | Children's data and Member State rules, DPIA screening, DPO determination. |
| [rights_requests.md](rights_requests.md) | Access, portability, rectification, erasure, restriction, objection and withdrawal: how each works, deadlines, identity checks, exemptions, partial failures. |
| [notices.md](notices.md) and [notices/](notices/) | The layered notices shown where data is collected, and their versions. |
| [security_article32.md](security_article32.md) | Article 32 review: the measures, and the open items. |
| [breach_playbook.md](breach_playbook.md) | Personal-data breaches: evidence, risk assessment, the 72-hour decision, telling people, contacts. |
| [exercises/](exercises/) | Breach exercises: what was rehearsed, the timeline, the findings. |
| [decisions.md](decisions.md) | Open legal and organisational decisions: who owns each, and its status. |
| [CHANGELOG.md](CHANGELOG.md) | Change history of these records and of the notices. |

## What the kit does for privacy (checked by tests)

- **Guests store nothing on the server.** Their games stay in the browser (ADR-0017).
- **Ownership and permissions.** Each item belongs to its creator. Teachers can read their
  class's work and cannot change it. Administrators can do everything, and their actions are
  audited.
- **Notices.** A short notice is shown at each collection point, and the version each
  person was shown is recorded (`tests/test_privacy_rights.py`).
- **Rights.** People can download their data as one structured document, and make requests
  that staff answer within one month. The workflows cover erasure across every table,
  folder, file and cloud token, restriction, objection and withdrawal (ADR-0022,
  [rights_requests.md](rights_requests.md)).
- **Retention.** Retention runs automatically for deleted projects, old builds, the audit
  log and sign-up links. Backups can be pruned and erasures re-applied after a restore
  ([retention.md](retention.md)).
- **Secrets.** Passwords and tokens are stored as hashes, and cloud tokens are encrypted.
  Logs never contain secrets. Store bearer tokens are the exception: they are stored in clear
  (open item S-1 in [security_article32.md](security_article32.md)).

## For a school putting the kit into service

1. Name the controller, the privacy lead and the DPO in [decisions.md](decisions.md).
   Set `PRG32_PRIVACY_CONTROLLER` and `PRG32_PRIVACY_CONTACT`, which `/privacy` shows.
2. Go through [decisions.md](decisions.md) with the DPO. Each line needs a decision, a date
   and an owner.
3. Choose where the kit runs and which optional services are on (school sign-in, cloud,
   Cartridge Store, email). Complete [processors_and_transfers.md](processors_and_transfers.md).
4. Do the DPIA if the screening says so (it does, for children at school).
5. Set the retention settings, and plan backup pruning and log rotation
   ([retention.md](retention.md)).
6. Run a breach exercise with the people named in the playbook. Keep the record in
   [exercises/](exercises/).
