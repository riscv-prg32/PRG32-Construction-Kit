# Roles and legal bases

**Version 1.0, 2026-10-21. Status: PROPOSED.** Each row is a proposal for the deploying
controller and its DPO to confirm or change. The decision, date and owner go in
[decisions.md](decisions.md).

## Who is who

| Party | Proposed role | Why | Agreement needed |
|---|---|---|---|
| School or operator running the kit | **Controller** | Decides why and how pupils' and staff's data is processed for teaching. | None (it is the controller) |
| The kit's authors (PRG32 project) | **No role** | They supply open-source software. They do not run it and receive no data: the kit has no telemetry and no phone-home. | None. If they host or support a deployment, they become a processor and need an Article 28 agreement. |
| Hosting provider (servers, backups) | **Processor** | Stores and runs the kit on the controller's instructions. | Article 28 DPA ([processors_and_transfers.md](processors_and_transfers.md)) |
| Email (SMTP) provider | **Processor** | Delivers sign-up and password emails. | Article 28 DPA |
| School identity provider (Google Workspace for Education, Microsoft Entra ID, Keycloak, etc.) | **The school's processor**, already in place | Authenticates the school's own accounts. | The school's existing DPA with that provider |
| Google Drive / Microsoft OneDrive (cloud copies) | **Separate controller** for the person's own account; the kit only writes to a folder of the person's own choosing | The person connects their own account by consent. The provider processes it under its own terms with that person (or the school, for school-managed accounts). | For school-managed accounts: the school's DPA. For personal accounts: none with the kit. To be decided ([decisions.md](decisions.md) D-6). |
| PRG32 Cartridge Store | **Same controller** if the school runs it; **joint or separate controller** if another organisation runs it | It receives published games and, with shared accounts, the accounts themselves. | If another organisation runs it: an Article 26 arrangement or a controller-to-controller agreement (D-7) |
| Teachers and facilitators | People acting under the controller's authority (Art. 29) | They see their class's work. | Staff instructions |

## Legal bases, by activity (Article 6)

| Activity | Proposed basis (public school) | Alternative (private operator) | Notes |
|---|---|---|---|
| Accounts, classes, students' work, builds | 6(1)(e) public task: teaching (national education law) | 6(1)(b) contract with the family / 6(1)(f) | The Member State law must be named (D-2) |
| School sign-in | 6(1)(e) | 6(1)(f) | Data minimised to issuer, subject and email ([notices/school_sign_in.md](notices/school_sign_in.md)) |
| Cloud copies (optional) | **6(1)(a) consent**, with a parent's consent below the national age (Art. 8) | same | Withdrawal = disconnect, which takes effect at once and revokes tokens where the provider allows |
| Publishing to the Store (optional) | 6(1)(e) if part of the course; otherwise 6(1)(a) | 6(1)(a) | Nicknames advised |
| Security log, sign-in throttling | 6(1)(c) Art. 32 obligation, with (e) or (f) | 6(1)(f) | Kept 365 days by default |
| Privacy records (notices shown, requests) | 6(1)(c) legal obligation (Art. 5(2), 12, 30) | same | |

**Article 9 (special categories).** The kit asks for none. Free text (project titles, code
comments, class names) could hold any information a person types. The notices and staff
instructions ask for nicknames, and for class names that reveal nothing sensitive (D-4).

**Automated decisions (Article 22).** None. The kit makes no decision with legal or similar
effects. Compiler checks and validators judge code, not people.
