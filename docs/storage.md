# Where your games are kept

## For students

**With an account**, your projects are on the kit's server.

- The IDE **saves by itself** a few seconds after you stop typing (the status
  bar says *Autosaved*). **Save** (Ctrl+S) also adds a step to **History**.
- If the same project is open in two windows (or a classmate shares it) and
  both change it, the kit **never overwrites** one with the other. The window
  that saves second asks you:
  - **Keep mine as a copy**: your version becomes a new project, the other stays;
  - **Load the saved version**: you see the other version (yours is dropped);
  - **Save mine over it**: you choose to replace the other version.
- There is a limit on how many projects and how much space each student has.
  If it is full, saving bigger or compiling stops with a message: delete old
  projects or ask your teacher.

**In your own cloud** (optional, if the kit offers it): see `cloud_storage.md`.
The same rule holds there: when both copies changed, you choose.

**Without an account** (the kit opens without one, see [guest_mode.md](guest_mode.md); or the
offline page when the server cannot be reached), your games are kept **in this browser
only**, on this computer:

- make several games, give them names, play them;
- **Save as file** downloads a game; **Open file** loads one back. The
  dashboard's **Import project** reads the same file;
- clearing the browser's data, or a full disk, can lose them: save the ones you
  care about as files;
- when you later **sign in** on this browser, the Projects page offers to
  **move them into your account**. Each game leaves the browser only after the
  server has it.

Nothing you make as a guest is kept on the server. To show you the generated C or play a
sound, the server looks at it for one request and forgets it.

## For teachers and administrators

| Setting | Default | Meaning |
| --- | --- | --- |
| `PRG32_KIT_LOGIN_REQUIRED` | off | off: the kit opens without an account, games kept in the browser ([guest_mode.md](guest_mode.md)); on: every page asks for a sign-in |
| `PRG32_GUEST_MODE` | `local` | `local`: visitors without an account may use the kit (and the sign-in page offers *Try without an account*); `off`: they may not (the offline page still works, but stores nothing on the server either way) |
| `PRG32_KIT_QUOTA_PROJECTS` | `200` | Projects per student (0 = no limit; administrators have none) |
| `PRG32_KIT_QUOTA_MB` | `200` | Space per student in MB: projects, history, sprites, assets, generated sources and their build files |
| `PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES` | `10` | Autosaves add to History at most this often |
| `PRG32_KIT_TRASH_DAYS` | `30` | Projects in *Recently deleted* are removed for good after this many days |
| `PRG32_KIT_KEEP_BUILDS` | `10` | Builds kept per project (older ones, with their cartridges and folders, are removed) |

- **Usage:** `GET /api/storage` shows a student's usage and limits.
- **Retention:** builds are pruned after every compile. Run the rest (trash,
  interrupted build folders) with `flask --app app prg32-retention` (shows what
  would go) and `--apply`, or `POST /api/admin/retention` with
  `{"dry_run": false}`. It also lists switched-off accounts, but never deletes
  accounts.
- **Leaving students:** switch the account off (Users page); export what must
  be kept; then `DELETE /api/users/<id>?with_items=1` removes the account with
  its projects, builds and files.
- Guest games live only in each browser, so the server holds no data about
  guests at all. Temporary server storage for guests is deliberately not
  offered.

Design: `adr/0017-storage-policy.md`.
