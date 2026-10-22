# ADR-0025: GitHub as a project's remote

**Status:** Accepted (2026-10-22). Extends ADR-0019 (provider-neutral cloud storage).

## Context

Students asked to keep their games in Git, the way programmers do: commits with a message,
a history, and the same code on GitHub that they see in the kit. Google Drive and OneDrive
(ADR-0019) keep one archive file per project, which is a copy, not a history.

## Decision

1. **GitHub is one more cloud provider** (`cloud_storage.GitHub`): the same consent box, Code
   flow with PKCE, encrypted tokens, fixed hosts (`github.com`, `api.github.com`), bounded
   retries and the same three-choice conflicts as ADR-0019. Signed-in users only; off until an
   operator configures it (`PRG32_CLOUD_GITHUB_CLIENT_ID`, `_SECRET`, `_APP_SLUG`) and can be
   switched off on the Settings page (`CLOUD_GITHUB_ENABLED`).
2. **A GitHub App, not an OAuth App.** Its user tokens expire and refresh, and it reaches only
   the repositories the student installs it on, with *Contents: read and write* and *Metadata:
   read*. An OAuth App would need the `repo` scope: every repository the student has.
3. **One repository and branch per account** (`CloudAccount.options`), chosen on the Account
   page from the repositories the App is installed on.
4. **A project is a top-level folder of ordinary files**: the project archive's files
   (`prg32.project.json`, `src/game.c` or `src/blocks.json`, `assets/...`, `audio/...`), so the
   code can be read and changed on GitHub. The folder's tree hash is the "revision" the
   conflict rules compare; a push is one commit with the student's message, made on top of the
   commit the kit expected and never forced (GitHub refuses a branch that moved: nothing
   changes). Files no longer in the project leave the folder; the rest of the repository is
   untouched.
5. **The IDE's Git tool window**: Commit & push, Pull, the folder's latest commits, and the
   conflict choices. Disconnecting revokes the grant at GitHub.

## Consequences

- GitHub, Inc. (Microsoft) is a recipient in the USA: record of processing, processors table,
  notice `cloud` 1.1 and decision D-6 (`docs/privacy/`).
- Tested against an in-process GitHub (`tests/fake_github.py`, `tests/test_github.py`,
  `tests/test_github_browser.py`). **Not run against real GitHub yet.**
- Branches, pull requests and merges are GitHub's: the kit commits to one branch and takes
  that branch's version back.
