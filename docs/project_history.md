# Going back: History and Recently deleted

The kit keeps earlier versions of your project, and a deleted project is not
gone straight away. So a wrong change or a wrong click can be undone.

## For students

**Go back to an earlier version**

1. Open your project and choose **History**.
2. Each line is a version that was kept, newest first: its number, when it
   was saved, and how many sprites it had.
3. Press **Restore** to go back to that version, or the download button to
   get it as a project archive (`.zip`, see `project_archive.md`).

When is a version kept? Every time you **Save** and the save changes your
blocks, your Advanced C or your handwritten assembly, the version *before* the change is kept. Saving
without changes keeps nothing new. Restoring also keeps the version you had
just before, so you can always go back again.

Restore puts back the blocks (or the C, or the assembly), the title and summary, and the
sprites and assets as they were in that version.

**Get a deleted project back**

Deleting a project moves it to **Recently deleted** at the bottom of the
Projects page. Press **Restore** there and it is back, with its sprites and
its history.

## For teachers

- Only the owner of a project and admins see its History. Students cannot see
  other students' history or deleted projects.
- The kit keeps the newest 50 versions per project. Change it with
  `PRG32_KIT_MAX_REVISIONS` (see `setup.md`).
- Only an admin can **Delete for good** (in Recently deleted). That removes
  the project, its history, its assets and its builds; its sprites and
  generated files (artifacts) stay, without a project.
- A version is the same set of files as a project archive, so a downloaded
  version imports like any hand-in.

API details: `api.md`, section *Project history and Recently deleted*.
