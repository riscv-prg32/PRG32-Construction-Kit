# ADR-0001: Versioned `prg32.project.json` and portable project archive

**Status:** Accepted (implemented in G1)

## Context

A project is stored as one `projects` row: `blocks_json`, `game_json` (which
also carries Advanced C source) and metadata. Sprites and assets live in
their own tables, linked by `project_id`. The old export
(`prg32-construction-kit-project-1.0`) is a single JSON file with the row only,
so sprites and assets are lost, and nothing records which mode is the source.

## Decision

1. A project is described by **`prg32.project.json`**, schema
   `prg32-project`, `schema_version` 1. It names the **authoring mode**
   (`blocks` or `c`; `assembly` is reserved, see ADR-0004), the entry-point
   prefix, the canonical source file, required PRG32 features, the SDK/ABI it
   targets, build targets, build profiles, assets and tests.
2. The **canonical source** stays in its mode: `src/blocks.json` for Blocks,
   `src/game.c` for C. Generated C and assembly are *derived*; they are never
   written back over the source and are not part of the archive (they are
   rebuilt deterministically).
3. The **portable archive** is a zip (`.prg32project.zip`) holding the
   manifest, the source, sprites (`assets/sprites/*.json`) and assets
   (`assets/data/*.json`). It is written deterministically: sorted entries,
   fixed timestamps, so the same project always gives the same bytes.
4. **Migrations** are pure functions `migrate_vN_to_vN+1`. Reading any older
   document (including the legacy single-file export) yields the newest
   schema. Database rows are not migrated: the manifest is computed from the
   row, so no SQLite schema change is needed.
5. Import is defensive: size and entry-count limits, no absolute paths,
   no `..`, only known file locations, and the imported project always
   belongs to the importing user.

## Consequences

- Existing API routes keep their shapes; `POST /api/projects/import` also
  accepts the archive.
- Revision history and snapshots (G1 follow-up) can store manifests plus
  source blobs without new formats.
