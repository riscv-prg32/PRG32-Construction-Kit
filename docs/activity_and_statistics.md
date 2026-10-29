# Email queue, activity log and statistics

Three tools for the people who run the kit (admins). Students never see them.

## Email sending queue (Settings, Email)

Every email the kit sends (sign-up links, "new sign-in" notices, the test mail) first waits
in a queue. At most **Email sending queue size** messages (`SMTP_MAX_PARALLEL`, default **5**)
are handed to the SMTP server at the same time, across every server process, so a whole class
signing up at once never floods the school's mail server.

The Email tab of **Admin > Settings** lists the queue:

| State | Meaning |
|---|---|
| **To send** | waiting for a free place (or for its next try after a refusal) |
| **Sending** | with the SMTP server right now |
| **Sent** | the server took it |
| **Failed** | refused three times (after 1 and 5 minutes); **Send again** puts it back |

Privacy: the address is shown shortened (`ma***@school.example`); the text is stored encrypted
and wiped when the message is sent. Rows are removed after **Days sent mail stays listed**
(`PRG32_KIT_MAIL_DAYS`, 30).

## Activity log (Admin > Activity)

Every page and API request is written down **after** it is answered: who, what kind of action
(`compile`, `project_save`, `run`, `page_view`, ...), the route *pattern*, the outcome and how long
it took. Pick a person on the left to see only what they did; download the log as CSV.

What is **never** logged: request bodies, project text, file names, query strings, cookies or full
addresses. What is logged about the computer: its network (`192.0.2.0/24`) and browser family
(`Firefox · Windows`).

**Visitors without an account** are identified as far as the law allows: they get a pseudonym
like `guest-3fa2c19b0d`, a keyed hash of their address and browser made with a *random salt that
changes every day*. Yesterday's salt is deleted, so a visitor can be followed within one day but
never linked across days, and the pseudonym can never be turned back into an address. Browsers
that send **Global Privacy Control** or **Do Not Track** are counted without a pseudonym.

## Statistics (Admin > Statistics)

Charts and tables for any range of days: active accounts and visitor-days per day, requests per
day and per hour, what people do, accounts by role, builds by outcome, and one row per active
account. Every table downloads as **CSV** (UTF-8, opens in any spreadsheet).

Visitors without an account are counted as **visitor-days**: one visitor on three days counts
three times, because the kit deliberately cannot link the days.

## GDPR in short

- **Data minimisation:** no content, shortened addresses, coarse browser names, daily pseudonyms.
- **Pseudonymisation:** the per-account statistics and every CSV show `person-...` pseudonyms
  unless the admin switches on usernames.
- **Accountability:** opening one person's activity, showing usernames and every CSV download
  are written to the audit log.
- **Storage limitation:** the log is kept `PRG32_KIT_ACTIVITY_DAYS` (90) days and can be switched
  off (`PRG32_KIT_ACTIVITY_LOG`), both on **Settings > Privacy**.
- **Rights:** a person's activity is in their data export and is erased with their account.
- The record of processing lists both (`docs/privacy/ropa.md`, *activity_log* and *email_queue*);
  the school confirms the legal basis with its DPO (`docs/privacy/decisions.md`).
