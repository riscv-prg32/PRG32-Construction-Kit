# Rights requests

**Version 1.0, 2026-10-21.** How the kit supports Articles 15 to 22, and what staff do.
Implementation: `prg32_construction_kit/privacy.py` (ADR-0022). Tests with synthetic
students: `tests/test_privacy_rights.py`.

## Who can ask, and how identity is checked

- **The person, signed in**, on their Account page under "Your data". Being signed in
  is the identity check. Requests made with an API token are refused (403), because a
  leaked token must never download or erase someone.
- **On their behalf** (a parent, a letter, in person): an administrator registers the
  request with `POST /api/admin/privacy/users/<id>/requests`. They must say how identity
  was checked (`verified_by`, for example "parent in person, school ID seen"). The kit
  refuses the request without it.

## Deadlines

Every request gets `due_at` = received + 30 days (Art. 12(3)). An administrator may extend it
by up to 60 days, with a reason recorded (`action: "extend"`). The person must be told of an
extension within the first month. Requests past `due_at` and still open are flagged
`overdue` in the register (`GET /api/admin/privacy/requests`).

## Each right

| Right | How | Done by | What it covers |
|---|---|---|---|
| **Access** (15) and **portability** (20) | "Download my data": `GET /api/me/privacy/export`, at once. Recorded as a completed access request. | the person (self-service); an administrator for someone else (`/api/admin/privacy/users/<id>/export`) | One JSON document (`prg32-personal-data-export`, version 1). Every row about the person in every table (`privacy.PERSONAL_TABLES`), a list of their files with SHA-256, the notice versions, and where else data may be (`not_in_this_export`). Never secrets: hashes and tokens appear as "(kept secret, not exported)". Others' names in the audit log appear as "(staff or system)". **A project archive is not this export.** |
| **Rectification** (16) | Request. Staff correct it with the account editor (`PUT /api/users/<id>`), then complete the request with what was done. | administrator | username, email, roles, classes. The person corrects their own work themselves. |
| **Erasure** (17) | Request. An administrator completes it with `confirm_user_id`, the account's id, so it cannot happen by accident. | administrator | See "Erasure, step by step". |
| **Restriction** (18) | Request. An administrator completes it, and lifts it later with `restricted: false`. | administrator | The person can still sign in, read and download. Every change, build, publication and cloud sync is refused (HTTP 423, code `restricted`). |
| **Objection** (21) | Request. The controller decides; the outcome is recorded (and may lead to restriction or erasure). | controller | |
| **Withdrawal of consent** (7(3)) | Cloud: "Disconnect" on the Account page, at once (tokens revoked at Google). Other consent: request. | the person / the controller | |
| **Not subject to automated decisions** (22) | none made | | |

## Erasure, step by step

`privacy.erase_account` runs these steps in order. Each step's failure is recorded, and the
rest still runs. A partial erasure is reported as `partial`, with the failed steps.

1. **Cloud tokens:** revoked at the provider where it allows it (Google). Otherwise the
   result tells the person or the school to remove the app's access in the account settings
   (Microsoft).
2. **Store publications:** listed for the Store's operator. The Cartridge Store is a
   separate service.
3. **Items and folders:** projects with their history, sprites, assets, builds with their
   `<build_id>/` folders, artifacts with their files, the AudioStudio sample folder, publish
   profiles.
4. **Rows naming the person:** API tokens, cloud accounts and links, school identities,
   groups, class memberships, publish attempts, notice records, pending account sync, sign-up
   links. Classes they created stay for their other members, without a creator.
5. **Audit log:** the person becomes a pseudonym (`person-…`, keyed with the installation's
   secret). The address their requests came from is dropped, and their username and email
   are removed from event details. The events stay, as security evidence.
6. **Request register:** their requests stay, under the pseudonym, without their name.
7. **The account:** deleted. With shared accounts, the deletion is sent to the Cartridge Store.

The result also lists what is outside the kit, for the controller to deal with:

- backups, until `backups_expire_by`;
- the school's sign-in service;
- copies in the person's own cloud account;
- their browser;
- web-server logs.

After a backup is restored, erasures are applied again from the erasure register
([retention.md](retention.md)).

## Exemptions and refusals

A request may be refused, or partly refused, under Article 12(5) or 17(3), or under national
law. The refusal must give its reason (`action: "refuse"`, `reason`), and tell the person
they can complain to the supervisory authority. The reason is kept in the register.

## Audit and redaction

Every request, export and decision is in the audit log: `privacy_request`, `privacy_export`,
`privacy_request_complete`/`_refuse`/`_extend`, `privacy_erasure`. Event details never hold
secrets (`security.safe_metadata`). After an erasure they hold only the pseudonym.
