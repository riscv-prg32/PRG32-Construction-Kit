# Privacy notices

The kit shows a short notice where it collects personal data. The full notice is one click
away, and `/privacy` brings them all together. The texts live in
`prg32_construction_kit/privacy_notices.json` (short) and [notices/](notices/) (full). Both
carry a version.

When a signed-in person reaches a collection point, the kit records the version they were
shown (`privacy_notice_records`). This happens once per version:

| Notice | Shown | Recorded when |
|---|---|---|
| [guest](notices/guest.md) | sign-in page, "Try without an account" | not recorded (no account) |
| [account](notices/account.md) | sign-in and registration pages | at each sign-in, until this version was recorded |
| [school_sign_in](notices/school_sign_in.md) | beside the school sign-in buttons | at school sign-in |
| [cloud](notices/cloud.md) | Account page, beside the consent box | when connecting |
| [publishing](notices/publishing.md) | Publish page; in the review summary | at review, before confirming |
| [classes](notices/classes.md) | Classes page | at sign-in, for class members |

**Changing a notice:** edit both texts, raise the `version` and `effective` date in
`privacy_notices.json`, and add a line to [CHANGELOG.md](CHANGELOG.md).
`tests/test_privacy_rights.py` checks that every full notice exists and shows the current
version.
