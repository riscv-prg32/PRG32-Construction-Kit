# Saving a whole project in one file

A **project archive** is one `.zip` file that holds everything you made for a
game: the blocks (or your Advanced C), your sprites and your assets. You can
keep it as a backup, hand it in to your teacher, or open it on another
PRG32-Construction-Kit.

## For students

**Save your project as a file**

1. Open your project and press **Save**.
2. Choose **Export → Project archive (.zip)**.
3. Your browser downloads a file such as `my-game.prg32project.zip`.

The file holds what you saved last. If the editor says you have unsaved
changes, save first.

**Open a project file**

1. Go to **Projects** (the first page).
2. Choose **Import project** and pick the `.zip` file (or an older `.json`
   export).
3. The kit opens your imported copy. It belongs to you, even if somebody else
   made the file.

**Make a copy**

Shared classroom games are read-only. Press **Make my copy** in the editor to
get your own version you can change.

## What is inside

```text
my-game.prg32project.zip
├── prg32.project.json        the "label" of the project
├── src/blocks.json           your blocks   (Blocks projects)
├── src/game.c                your C code   (Advanced C projects)
├── src/game.S                your assembly (Assembly projects)
└── assets/
    ├── sprites/01-ship.json  one file per sprite
    └── data/01-level.json    one file per asset
```

`prg32.project.json` is plain JSON you can read. The important fields:

| Field | Meaning |
| --- | --- |
| `schema`, `schema_version` | Which version of this file format it is. |
| `authoring_mode` | `blocks`, `c` or `assembly`: what you write the game in. |
| `source` | The file holding your program. |
| `entry_points` | The names of the cartridge's `init`, `update` and `draw` functions, made from the title. |
| `required_features` | PRG32 features an Advanced C or assembly game needs (for example `sprites`). |
| `sdk` | The PRG32 cartridge ABI the kit builds for (1.6, hash `0x260f6136`). |
| `targets` | Where cartridges can be built: `esp32c6` (the console) and `qemu`. |
| `assets` | The list of sprite and asset files. |

Generated code (the C and assembly made from blocks) and the `.prg32`
cartridges are **not** in the archive. They are made again from your source,
and the kit makes exactly the same code every time.

## For teachers

- Ask students to hand in the archive: it is small, contains only their own
  work, and imports into your account as your copy.
- Exporting the same saved project twice gives byte-for-byte identical files,
  so you can compare hand-ins with a checksum.
- The importer refuses unsafe archives (file names with `..`, links,
  encrypted files, files over 4 MiB, more than 512 files) and tells the
  student why. Files it does not use are skipped and listed.
- Older `.json` exports still import; they are upgraded automatically.

Earlier versions of a project can be downloaded the same way from
**History**: see `project_history.md`.

API details: `api.md`, section *Project import/export*.
