# Keeping projects in Google Drive or OneDrive

Optional: a kit without cloud settings works exactly as before, and guests never
see it (their games stay in the browser). See ADR-0019 for the design.

## For students

1. On **My account → Cloud storage**, read what the kit will be allowed to do, tick
   the box and press **Connect**. Google or Microsoft asks you again.
2. On the dashboard, the cloud button of a project opens **Cloud copy**:
   - **Save to cloud** puts the project in your Drive/OneDrive (the same
     `.prg32project.zip` file as *Download project*);
   - **Get cloud version** brings back what is in the cloud, for example after
     working on it from home.
3. If the project changed **here and in the cloud**, the kit never replaces one
   with the other by itself. You choose:
   - **Keep both**: you get a copy, nothing is replaced;
   - **Take the cloud version**: your version here goes into the project's
     **History** first;
   - **Overwrite the cloud copy** with your version here.
4. **My account → Cloud storage** lists your cloud projects: **Open as new
   project**, or move one to the cloud trash (you can get it back from there).
5. **Disconnect** when you no longer want the kit to reach your cloud. Your files
   stay where they are.

What the kit may see:

| Provider | Permission | Means |
|---|---|---|
| Google Drive | `drive.file` | only the files the kit created; not your other files |
| OneDrive | `Files.ReadWrite.AppFolder`, `User.Read`, `offline_access` | only the kit's own folder (*Apps*), your account's name and id, and staying connected |

## For teachers

- A project in the cloud belongs to the student's own account: a teacher who
  supervises a class still only reads it in the kit.
- Quotas apply to projects brought back from the cloud like to any other.
- Disconnecting from Google revokes the permission at Google. Microsoft has no way
  for an app to do that: after disconnecting, the student removes the kit at
  <https://account.live.com/consent/Manage> (personal) or
  <https://myapps.microsoft.com> (school).

## For administrators

Register an OAuth app with each provider you want to offer. The redirect address is
`<PUBLIC_URL>/cloud/google/callback` or `<PUBLIC_URL>/cloud/onedrive/callback`.

| Setting | Default | Meaning |
|---|---|---|
| `PRG32_CLOUD_GOOGLE_CLIENT_ID` / `_SECRET` | unset | Google Drive (scope `https://www.googleapis.com/auth/drive.file` only) |
| `PRG32_CLOUD_ONEDRIVE_CLIENT_ID` / `_SECRET` | unset | OneDrive (scopes `Files.ReadWrite.AppFolder User.Read offline_access`); the secret is optional (PKCE public client) |
| `PRG32_CLOUD_ONEDRIVE_TENANT` | `common` | `organizations`, `consumers` or a tenant id |
| `PRG32_CLOUD_TOKEN_KEY` | from `SECRET_KEY` | key the stored tokens are encrypted with; changing it (or `SECRET_KEY`) asks students to connect again |

The kit talks only to `www.googleapis.com`, `oauth2.googleapis.com`,
`graph.microsoft.com`, `login.microsoftonline.com` and, for OneDrive downloads,
Microsoft's download hosts (`*.1drv.com`, `*.sharepoint.com`, ...), over HTTPS, with
no redirects and a size limit.

## Limits, said plainly

- **Google Drive has no conditional upload.** The kit checks the file's version right
  before writing; a change in the second between the check and the write could still
  be replaced. OneDrive writes are conditional (`If-Match`).
- **OneDrive:** projects up to 4 MB (Graph's simple upload).
- Tokens are refreshed when they expire; if the provider refuses the refresh (the
  student removed the permission or changed their password), the kit asks them to
  connect again and changes nothing.
- Busy or unreachable providers: up to three tries with short waits, then *nothing
  was changed; try again*. Creating a file is not repeated blindly: the next try first
  looks for the file it may already have made.

## How it is tested

| Check | Where |
|---|---|
| One contract run against fake Google Drive and OneDrive: consent, PKCE, scopes, encrypted tokens, create/update/in-sync, conflicts and the three choices, renames, deleted files, token expiry and refusal, disconnect and revocation, account switching, outages and retries, a create stored but not confirmed, ownership, `user_changed`, allowed hosts | `tests/test_cloud_storage.py`, `tests/fake_cloud.py` |
| Files the kit did not make stay invisible and untouched; an outage while taking the cloud version changes nothing here or there; the check-then-write window (Drive replaces, OneDrive refuses) | `tests/test_cloud_storage.py` |
| The Account page and the dashboard dialog in a real browser | `tests/test_cloud_browser.py` |
| A real test account (opt-in): refresh after expiry, account identity, granted scopes are only the least-privilege ones, create/list/load/conditional save, stale revision refused, files it did not make unreachable, unknown refresh token refused, OneDrive 4 MB limit, trash at the end | `tests/test_cloud_live.py` |

**Status:** the live suite has **not** been run against a Google or Microsoft test
account yet, so nothing here is verified against a real provider. To record evidence,
run it once per provider with a dedicated, non-personal test account and add the
result (date, provider, pass/skip counts, kit commit) to `implementation-status.md`.

The live suite runs only with `PRG32_LIVE_CLOUD=google` or `onedrive` and settings
from the environment (never from files): `PRG32_LIVE_CLOUD_CLIENT_ID`,
`PRG32_LIVE_CLOUD_CLIENT_SECRET`, `PRG32_LIVE_CLOUD_TENANT` and
`PRG32_LIVE_CLOUD_REFRESH_TOKEN`. Get the refresh token by connecting a **test**
account once to a kit that uses the same app registration. The suite touches only
files it creates (`prg32-live-test-...`) and moves them to the trash at the end;
`PRG32_LIVE_CLOUD_REVOKE=1` also revokes the token (Google).

```bash
PRG32_LIVE_CLOUD=google python3 -m pytest -q -rs tests/test_cloud_live.py
```
