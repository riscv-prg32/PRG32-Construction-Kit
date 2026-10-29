# API Reference

All responses are JSON unless a download endpoint is used.

## Signing in

Every `/api/` route needs a signed-in user (see `accounts_and_sso.md`).
Browsers use the session cookie set by `POST /auth/login`; scripts send an API
token as `Authorization: Bearer prg32_...`. Without either, the API answers
`401`. Browser `POST` requests must be JSON or carry the header
`X-PRG32-Kit: 1` (the kit's pages add it); this stops other web sites from
posting forms with a student's cookie.

The kit's pages also send `X-PRG32-User: <user id>`, the account the window
was opened as. If somebody signed in as a different user in another window of
the same browser, the API answers `409` with `"code": "user_changed"` instead
of saving or compiling with the wrong account (see `concurrent_builds.md`).
Requests with an API token skip this check.

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/auth/login` | Sign-in page / sign in (`username`, `password`, `next`) |
| `POST` | `/auth/logout` | Sign out |
| `GET` | `/auth/me` | Current user and single sign-on status |
| `GET/POST` | `/auth/register` | Ask for a registration link by email |
| `GET/POST` | `/auth/register/complete` | Choose a password from the emailed link |
| `POST` | `/auth/password` | Change your password (`current_password`, `new_password`) |
| `GET/POST` | `/auth/tokens` | List / create your API tokens (a new token is shown once) |
| `PATCH/DELETE` | `/auth/tokens/<id>` | Rename / revoke one of your tokens |
| `GET/POST` | `/api/users` | Admins: list / create users |
| `GET/PUT/DELETE` | `/api/users/<id>` | Admins: read / change / delete a user |
| `GET` | `/auth/oidc/login`, `/auth/saml/login` | School sign-in, when configured |
| `GET` | `/api/admin/audit` | Admins: audit log, newest first (`limit`, `action`, `before`) |
| `DELETE` | `/api/admin/throttles` | Admins: clear all sign-in limits |

Sign-in, registration, registration links and new API tokens are limited
(`security.md`, *Sign-in limits*). Over the limit they answer `429` with a
`Retry-After` header (seconds) and `{"error", "retry_after"}`; a known and an
unknown username get the same answer.

Each item has an `owner_id` and a `can_edit` flag. Users see their own items
and shared items (`owner_id` empty); admins see everything.

## School sign-in, classes and token scopes (ADR-0016)

| Route | Who | What |
| --- | --- | --- |
| `GET /auth/oidc/<provider>/login`, `GET /auth/oidc/<provider>/callback` | anyone | OIDC Authorization Code + PKCE sign-in |
| `GET /auth/identities`, `POST /auth/identities/<provider>/link`, `DELETE /auth/identities/<id>` | signed in | the account's school identities; link answers `{"redirect": url}` |
| `POST /auth/sessions/revoke` | signed in | sign out everywhere |
| `POST /auth/tokens` | signed in | `{"label", "scopes": ["read","write","build","publish","admin"], "expires_in_days"}` |
| `GET/POST /api/admin/identity_providers`, `PUT/DELETE /api/admin/identity_providers/<slug>` | admin | providers; `client_secret_ref` is `env:NAME` or `file:/path` |
| `POST /api/users/<id>/deactivate`, `/reactivate`, `/sessions/revoke` | admin | deprovisioning and session revocation |
| `GET/POST /api/classes`, `GET/PUT/DELETE /api/classes/<id>` | members, teachers, admin | classes |
| `POST /api/classes/<id>/members`, `DELETE /api/classes/<id>/members/<user>` | class teachers (students only), admin | membership |
| `GET /api/classes/<id>/projects` | class teachers and facilitators, admin | students' projects, read-only |

A token request without the needed scope answers `403` with `"code": "insufficient_scope"`.
`PUT /api/users/<id>` accepts `kit_role` (admin only; not your own).

## Saving safely, quotas and retention (ADR-0017)

- `PUT /api/projects/<id>` accepts `expected_version` (the `version` the client
  loaded). If the project changed since, the answer is `409` with
  `"code": "version_conflict"` and `"current"` (the saved project); nothing is
  changed. `"autosave": true` adds to History at most every
  `PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES`.
- Going over a quota answers `413` with `"code": "quota_exceeded"` and `"usage"`.
  `GET /api/storage` returns `{bytes, parts, projects, quota_bytes, quota_projects}`.
- `POST /api/admin/retention` (admin): `{"dry_run": true}` by default; returns what
  was (or would be) removed.
- `DELETE /api/users/<id>?with_items=1` (admin) also removes the account's items.

## Store lifecycle rules (contract `tokens`, `versioning`)

- Publish profiles show `token_expires_on` (`""` = never or no token); `token_set_at` is
  set by the server whenever `bearer_token` is put in and cannot be sent by clients.
- `POST /api/publish/review` and `POST /api/publish` refuse with `reason`
  `token_too_old` (400) or `version_already_published` (409). Publishing an id/version
  already accepted by that Store with the same files answers `"duplicate": true` and
  uploads nothing.

## Cloud storage (ADR-0019)

Only when an administrator configured a provider (`google`, `onedrive`); otherwise
`404 not_configured`. Errors carry `code` and `retryable`; conflicts also `choices`,
`remote` and `local`.

| Route | What it does |
|---|---|
| `GET /api/cloud` | offered providers, scopes, and this account's connection (never tokens) |
| `POST /api/cloud/<provider>/connect` `{"consent": true}` | `{"redirect": url}` to the provider (browser sign-in only) |
| `GET /cloud/<provider>/callback` | the provider comes back here (single-use state, PKCE) |
| `POST /api/cloud/<provider>/disconnect` | forget the tokens; `revoked_at_provider` says whether the provider revoked them |
| `GET /api/cloud/<provider>/files` | the kit's project files there, with the linked `project_id` |
| `POST /api/cloud/<provider>/files/<file_id>/open` | a new project from a cloud file |
| `DELETE /api/cloud/<provider>/files/<file_id>?revision=` | to the provider's trash, only for that revision |
| `GET /api/projects/<id>/cloud` | the project's links (kit records only) |
| `POST /api/projects/<id>/cloud/<provider>/push` | `{}`, `{"choice": "copy"}` or `{"choice": "overwrite", "expected_remote_revision": r}` → `result` `created`, `saved`, `in_sync`, `overwritten` |
| `POST /api/projects/<id>/cloud/<provider>/pull` | `{}`, `{"choice": "copy"}` or `{"choice": "take_remote", "expected_version": v}` → `result` `taken`, `nothing_new`, `copied` |

Codes: `cloud_conflict`, `remote_missing`, `other_account`, `reconnect`,
`not_connected`, `consent_required`, `unavailable` (retryable), `too_large`,
`bad_file`, `forbidden`.

## Single sign-on with a Cartridge Store

Only when `PRG32_SSO_SECRET` and `PRG32_SSO_PEER_URL` are set:

| Method | Path | Purpose |
|---|---|---|
| `GET/POST` | `/api/sso/users` | Signed requests from the linked store: list / apply user records |
| `POST` | `/api/sso/sync` | Admins: send waiting changes, then merge all users both ways |
| `GET` | `/auth/sso/peer?next=/path` | Open the linked store already signed in |
| `POST` | `/auth/sso/accept` | Receives a one-time login ticket from the store |

A user record looks like this:

```json
{"email": "ada@school.test", "username": "ada", "password_hash": "scrypt:...",
 "role": "user", "groups": ["class-3b"], "updated_at": "2026-10-17T09:30:00.000000Z",
 "deleted": false, "previous_email": null}
```

## Built-in Blocks examples

`GET /api/examples` lists the built-in Blocks examples. Each entry has a
`slug`, `title`, `description` and `kind`: `"game"` for the five complete games
(`pong`, `breakout`, `space_invaders`, `asteroids`, `snake`, read from
`examples/games/`) and `"sketch"` for the short adaptations of the other
upstream PRG32 examples, `"python"` for the PRG32 Python game and `"art"` for the four Star
Catcher games (`star_catcher_blocks`, `_python`, `_c`, `_asm`; their entries also have a
`language`). `POST /api/examples/<slug>/import` creates a new project from one of them; it never
changes the built-in example. An `"art"` example also gets its sprites, its background and its
AudioStudio sound.

## Project art

```http
GET /api/projects/<id>/art
```

The project's sprites, backgrounds and sounds as code (`project_assets.py`, docs/project_art.md):

```json
{"catalog": {"sprites": [{"name": "rocket", "title": "rocket", "width": 16, ...}], "backgrounds": [...],
             "effects": [...], "soundtracks": [...], "skipped": []},
 "c_header": "/* prg32_assets.h ... */", "asm_include": "/* prg32_assets.S ... */",
 "usage": {"sprites": [{"title": "rocket", "name": "rocket", "blocks": "...", "python": "...",
                        "c": "rocket_draw(10, 20);", "asm": "..."}], ...},
 "features": ["audio", "sprites", "tilemap"], "files": {"c": "prg32_assets.h", "asm": "prg32_assets.S"}}
```

A guest gets the same answer from `POST /api/guest/art` with `{title, sprites, backgrounds,
audio_studio}`; nothing is stored. A C or assembly project that writes `#include
"prg32_assets.h"` (or `"prg32_assets.S"`) gets this code in place of that line when it is
converted, checked or built.

## Compile and download a cartridge

`POST /api/projects/<id>/package` validates the saved Blocks JSON, generates
deterministic C, and invokes the configured PRG32 toolchain. When compilation
succeeds, the response's `cartridge_artifacts` array contains portable
`.prg32` files. Download one through
`GET /api/artifacts/<artifact-id>/download`.

To build only some targets, send `{"architectures": ["esp32c6"]}` (or
`["qemu"]`, or both). Unknown names are rejected with `400`. The editor's
The IDE's **Compile** button uses this; a script can ask for one architecture and download it
directly.

Many students, or one student in several browser windows, can build at the
same time; see `concurrent_builds.md`. Two optional fields protect against a
save from another window: send `"expected_blocks_json"` (Blocks projects) or
`"expected_source_c"` (Advanced C projects) or `"expected_source_asm"`
(handwritten assembly projects) with the version you just saved,
and the server answers `409` instead of compiling a different version. When
every build slot stays busy for `PRG32_BUILD_QUEUE_TIMEOUT` seconds the server
answers `503` with a `Retry-After` header; try again a little later.

## Discovery

```http
GET /.well-known/prg32-construction-kit.json
```

Returns service URLs for projects, sprites, assets, artifacts, builds, publish profiles, and publish action,
plus `auth` (sign-in is required), `sso` (`{"enabled": true|false, "abi": "prg32-sso-1.0"}`) and
`cartridge_builds` (`{"available": true|false, "architectures": ["esp32c6", "qemu"]}`).
`available` is `false` when this server has no working PRG32 build tools, so
**Compile** makes source bundles only (see `install_cartridge_build.md`).
The check runs once per server process.

## CRUD resources

Every resource supports:

```http
GET    /api/<resource>
POST   /api/<resource>
GET    /api/<resource>/<id>
PUT    /api/<resource>/<id>
DELETE /api/<resource>/<id>
```

Resources:

- `projects`
- `sprites`
- `assets`
- `artifacts`
- `builds`
- `publish_profiles`

Supported filters on list endpoints:

```text
project_id
sprite_id
kind
status
```

Example:

```bash
curl http://127.0.0.1:5090/api/artifacts?kind=c_source
```

Request rules and errors:

- The body must be a JSON object; anything else returns `400`.
- A custom `id` may use letters, digits, `-` and `_` (up to 64 characters).
- Text fields must be text, and sprite `width`/`height` whole numbers (`400`).
- A duplicate `id`, or a `project_id`/`sprite_id` that does not exist, returns `409`.
- `publish_profiles` never return `bearer_token`; they return `has_token: true/false`.
- `artifacts` never return their server-side `path`; use
  `GET /api/artifacts/<id>/download` to retrieve artifact contents.
- Packaging responses omit internal build and bundle directory paths.
- Build logs show the private build folder as `<build>` instead of exposing
  the server's filesystem layout.

## Project import/export

```http
POST /api/projects/import
GET  /api/projects/<id>/export
GET  /api/projects/<id>/archive
GET  /api/projects/<id>/manifest
POST /api/projects/<id>/duplicate
```

- `archive` downloads the portable project archive
  (`<title>.prg32project.zip`): `prg32.project.json`, the source
  (`src/blocks.json` or `src/game.c`), sprites and assets. The same project
  always gives the same bytes. Generated C, assembly and cartridges are not
  included; they are made again from the source.
- `manifest` returns the `prg32.project.json` that `archive` would write.
- `duplicate` makes the caller's own copy, with sprites and assets. Optional
  body: `{"title": "My copy"}`. Works on shared classroom projects too.
- `import` accepts a JSON body, or the multipart field `file` holding either
  JSON or a project archive. Archive imports answer `201` with the new project
  plus `ignored_files` (files in the zip that the manifest does not list), or
  `400` with a reason: unsafe file names, links, encrypted entries, files over
  4 MiB, more than 512 files, or a newer `schema_version`. Projects in all
  three authoring modes (`blocks`, `c`, `assembly`) import.
- `export` still writes the older single JSON file
  (`prg32-construction-kit-project-1.0`). Importing that file goes through the
  project-format migration (schema version 0 → 1).

Format details: `project_archive.md` and `adr/0001-project-manifest.md`.

## Project history and Recently deleted

```http
GET    /api/projects/<id>/revisions
GET    /api/projects/<id>/revisions/<revision_id>/archive
POST   /api/projects/<id>/revisions/<revision_id>/restore
GET    /api/projects?deleted=1
POST   /api/projects/<id>/restore
DELETE /api/projects/<id>?purge=1
```

- When `PUT /api/projects/<id>` changes `blocks_json`, the Advanced C or the
  handwritten assembly (`game_json.source_mode` / `source_c` / `source_asm`), the version before the
  change is kept as a revision. A revision holds the same files as the project
  archive. A revision equal to the newest one is not kept again. The newest
  `PRG32_KIT_MAX_REVISIONS` (default 50) are kept per project.
- `revisions` lists them newest first:
  `{"project_id", "revisions": [{"id", "number", "created_at", "reason", "title",
  "authoring_mode", "source_bytes", "sprite_count", "asset_count", ...}]}`.
  `reason` is `save` or `restore`.
- `.../archive` downloads one revision as `<title>-revision-<n>.prg32project.zip`.
- `.../restore` keeps the current version as a revision first (`reason: restore`),
  then puts back the source, title, summary, author, tags, sprites and
  assets in one transaction. Sprites and assets keep their ids where the
  version still has them (`project_history.md`, *How restore matches*).
  Answer: `{"project", "restored_revision", "saved_revision"}`
  (`saved_revision` is `null` when the current version was already kept);
  `422` when the saved version is damaged (nothing changes).
- Each revision in the list has `damaged: true|false`.
- History routes are for the project's owner and admins: `404` if you cannot
  see the project, `403` for a shared classroom project you cannot change.
- `DELETE /api/projects/<id>` answers `{"deleted": true, "id": ...}` as before,
  but moves the project to Recently deleted (it sets `deleted_at`). Deleted
  projects are left out of lists and answer `404` everywhere else.
- `GET /api/projects?deleted=1` lists your deleted projects (admins: all).
- `POST /api/projects/<id>/restore` brings one back (owner or admin).
- `DELETE /api/projects/<id>?purge=1` removes a project for good, deleted or
  not: admins only (`403` otherwise). Its revisions, assets and builds go too;
  its sprites and artifacts stay, unlinked.
- Project items now include `deleted_at` (`null` unless deleted). It cannot be
  set with `PUT`.

## Convert project to C or RISC-V assembly

```http
POST /api/projects/<id>/convert
Content-Type: application/json

{"source_language": "both"}
```

`source_language` is optional: `"c"` (the default), `"asm"` (RISC-V assembly)
or `"both"`. Anything else is rejected with `400`. Assembly is generated from
Blocks only: an Advanced C project answers `400` for `"asm"` and `"both"`.
A handwritten assembly project (`game_json: {"source_mode": "asm", "source_asm": "...",
"required_features": [...]}`) always uses its own assembly: `source_language`
may be left out or be `"asm"`; anything else answers `400`. Its source is
checked first (`handwritten_assembly.md`); a refused source answers `400`
with the reason, before anything is assembled.
A PRG32 Python project (`game_json: {"source_mode": "python", "source_python": "...",
"python_language_version": 1}`, ADR-0026) behaves like Blocks: `"c"`, `"asm"` and `"both"`
are all allowed, generated from the game IR its `game.py` becomes. A refused `game.py`
answers `400` with `"error": "Line N: ..."` (`python_language.md`); the IR is shown, never
stored over the source. Saving a Python project with an unknown `python_language_version`
answers `400`. Builds accept `expected_source_python` like `expected_source_c`.
See `generated_code.md` for how to read the two files.

Response fields:

- `project`
- `game_ir`
- `source_language`
- `c_source` (when C was asked for)
- `asm_source` and `asm_artifact` (when assembly was asked for)
- `artifact` (the first artifact made: C, or assembly for `"asm"`)
- `artifacts` (every artifact made, C first)

Generated C is stored as a `c_source` artifact (`text/x-csrc`), generated
assembly as an `asm_source` artifact (`text/x-asm`).

## Prepare cartridge bundle

```http
POST /api/projects/<id>/package
```

`source_language` works as for convert. `"asm"` compiles the generated
assembly (`game.S`); `"c"` and `"both"` compile the generated C. With `"both"`
the bundle holds `source/game.c` and `source/game.S`.

Response fields:

- `build` (`build.metadata.built_from` is `"c"` or `"asm"`)
- `c_artifact` (`null` for `"asm"`)
- `asm_artifact` (`null` unless assembly was asked for)
- `bundle_artifact`
- `cartridge_artifacts`
- `result`

Status codes: `200` built (check `build.status`), `400` invalid project,
`409` the project changed in another window, `503` all build slots busy.

`build.status` is `ready` (at least one `.prg32`), `failed` (build tools are
installed but the compiler made no cartridge, or packaging crashed) or
`source-only` (this server has no build tools). `result.publishable` is true
only when `.prg32` files were created. `build.metadata.provenance` records
what made the build, with SHA-256 fingerprints of the source and of every
cartridge (`build_provenance.md`); each `prg32_cartridge` artifact also has
`metadata.sha256` and `metadata.bytes`. Responses and logs contain no server
folders: the build folder appears as `<build>`.

With debug information on (`PRG32_DEBUG_INFO`, default `1`), the PRG32 builder
compiles with `-g` on the side: the cartridge is byte-identical, and each
`prg32_cartridge` artifact gets `metadata.debug_map_artifact_id` (and, for
Blocks projects, `metadata.source_map_artifact_id`). `result.debug_info` says,
per architecture, `ok` or `unavailable`.

## Debug a cartridge at source and block level

```http
GET /api/artifacts/<cartridge-artifact-id>/debug
```

Read-only, for the cartridge's owner (ADR-0015). Returns `debug_map` (line
table, functions, variables, types, call-frame rules and symbols, or
`{"status": "unavailable", "reason": ...}`), `source_map` (Blockly block → IR
path → lines, or `null`), `source` (`{file, language, text}`) and `blocks_json`
(the blocks the cartridge was built from). No server folders appear in it.

## Convert sprite to C

```http
POST /api/sprites/<id>/convert
```

Creates a `sprite_c_source` artifact.

## Artifact upload and download

```http
POST /api/artifacts/upload
GET  /api/artifacts/<id>/download
```

Upload uses multipart form field `file` and optional fields `kind` and `project_id`.

## Publish bundle

Publishing is two calls (ADR-0009) and needs the `publisher` or `admin`
role (`403` otherwise):

```http
POST /api/publish/review
{"profile_id": "publish_profile_...", "bundle_artifact_id": "artifact_..."}

-> 200 {"summary": {...}, "review_token": "...", "expires_in": 900}

POST /api/publish
{"profile_id": "...", "bundle_artifact_id": "...", "review_token": "...", "confirm": true}
```

- Only a `store_bundle` with `metadata.publishable` is accepted, with a valid
  `prg32-metadata-1.0` manifest whose cartridge files exist, start with `PRG2`
  and (for kit builds) match the build provenance SHA-256 (`400` with
  `reason`: `not_publishable`, `bad_manifest`, `missing_cartridge`,
  `not_a_cartridge`, `hash_mismatch`, ...).
- `summary`: `store` (origin, host, authentication), `profile`, `bundle`
  (name, SHA-256, size, build id), `cartridge` (id, title, version),
  `architectures` (id, file, bytes, SHA-256), `after_upload`.
- `POST /api/publish` without `review_token` and `"confirm": true` answers
  `428`; a token that is expired, forged, for another user, or for a summary
  that changed answers `409` (`reason: review_mismatch`).
- Answer: `{"state": "submitted" | "failed", "duplicate", "summary", "result"}`.
  Confirming an already submitted review returns the stored result with
  `"duplicate": true` and uploads nothing; while it is being sent, `409`
  (`reason: in_progress`). A failed attempt can be confirmed again.
- **Migration:** the route is unchanged but one-step publishing is gone;
  scripts must call `/api/publish/review` first.

The backend posts the bundle to the profile's Cartridge Store URL at
`/api/publish/bundle`, following the Store egress policy (ADR-0008).

- Saving a publish profile (`POST`/`PUT /api/publish_profiles`) with a
  `store_url` that is not an approved origin, or not https, answers `400`.
- `POST /api/publish` answers `400 {"error", "reason"}` when the Store is not
  allowed (`reason`: `not_allowed`, `insecure`, `private_address`, `resolve`,
  `redirect`, ...), and `502 {"error", "reason"}` when it cannot be reached
  (`timeout`, `tls`, `connection`). Nothing is sent to a refused Store.
- On success, `result` is `{"ok", "status_code", "store_host", "message",
  "response"}`; `response` holds only CartridgeStore's documented fields
  (`ok`, `status`, `review_required`, `submission_id`, `id`, `version`,
  `submitted`, `error`). The previous `endpoint` field was removed.
