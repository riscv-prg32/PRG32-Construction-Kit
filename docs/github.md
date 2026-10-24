# Keeping a project on GitHub

## For students

GitHub keeps every version of your code, with a message saying what you changed. The kit can
**commit** your project there and **pull** it back.

1. **Once:** on the **Account page**, under *Cloud storage*, tick the box and **Connect GitHub**.
   GitHub asks you to sign in and allow the kit.
2. **Once:** **install the kit's GitHub App** on a repository (the link is on the Account page),
   then choose that repository and a branch (usually `main`) and press **Use this repository**.
3. **In the IDE**, open the **Git** tab at the bottom:
   - write what you changed, then **Commit & push**. The project becomes a folder of normal files
     in your repository: `prg32.project.json`, `src/game.c` (or `src/game.S`, or
     `src/blocks.json`), your sprites and sounds;
   - **Pull** takes the version on GitHub, for example after you changed it on another computer;
   - the list shows the latest commits of your project's folder, with a link to each one on GitHub.

If you changed the project here **and** on GitHub, the kit stops and asks: keep both (a new
copy), take GitHub's version (yours stays in History), or put your version on GitHub.

## For teachers

- It is optional, and needs an account. Students under the age their country sets need a
  parent's or guardian's agreement; your school decides (privacy decision D-6).
- The kit sees only the repositories a student installs its GitHub App on, and only commits
  to the one they choose.
- **Disconnect** on the Account page revokes the kit's permission at GitHub.

## For administrators

1. Register a **GitHub App** (GitHub, Settings, Developer settings, GitHub Apps):
   - *Callback URL*: `https://<your kit>/cloud/github/callback` (set `PRG32_KIT_PUBLIC_URL`);
   - *Expire user authorization tokens*: on; *Request user authorization during installation*: off;
   - *Repository permissions*: **Contents: read and write**, **Metadata: read**; nothing else;
   - *Where can it be installed*: any account (students install it on their own repositories).
2. Set on the server: `PRG32_CLOUD_GITHUB_CLIENT_ID`, `PRG32_CLOUD_GITHUB_CLIENT_SECRET` and
   `PRG32_CLOUD_GITHUB_APP_SLUG` (the name in `github.com/apps/<slug>`). Restart.
3. **Settings, Store & cloud, GitHub repositories** switches it off again without a restart.

## Limits, said plainly

- Tested against an in-process GitHub, not yet against real GitHub.
- One repository and branch per student; pull requests and merges happen on GitHub.
- A project folder can hold at most the files and size of a project archive.
