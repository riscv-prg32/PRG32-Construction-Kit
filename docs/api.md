# API Reference

All responses are JSON unless a download endpoint is used.

## Built-in Blocks examples

`GET /api/examples` lists the editable Blocks adaptations of the upstream
PRG32 example games and feature demos. `POST /api/examples/<slug>/import`
creates a new project from one of them; it never changes the built-in example.

## Compile and download a cartridge

`POST /api/projects/<id>/package` validates the saved Blocks JSON, generates
deterministic C, and invokes the configured PRG32 toolchain. When compilation
succeeds, the response's `cartridge_artifacts` array contains portable
`.prg32` files. Download one through
`GET /api/artifacts/<artifact-id>/download`.

To build only some targets, send `{"architectures": ["esp32c6"]}` (or
`["qemu"]`, or both). Unknown names are rejected with `400`. The editor's
**Download .prg32** button uses this to compile one cartridge and download it
directly.

Many students, or one student in several browser windows, can build at the
same time; see `concurrent_builds.md`. Two optional fields protect against a
save from another window: send `"expected_blocks_json"` (Blocks projects) or
`"expected_source_c"` (Advanced C projects) with the version you just saved,
and the server answers `409` instead of compiling a different version. When
every build slot stays busy for `PRG32_BUILD_QUEUE_TIMEOUT` seconds the server
answers `503` with a `Retry-After` header; try again a little later.

## Discovery

```http
GET /.well-known/prg32-construction-kit.json
```

Returns service URLs for projects, sprites, assets, artifacts, builds, publish profiles, and publish action.

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

## Project import/export

```http
POST /api/projects/import
GET  /api/projects/<id>/export
```

Import accepts JSON body or multipart field `file`.

## Convert project to C

```http
POST /api/projects/<id>/convert
```

Response fields:

- `project`
- `game_ir`
- `c_source`
- `artifact`

## Prepare cartridge bundle

```http
POST /api/projects/<id>/package
```

Response fields:

- `build`
- `c_artifact`
- `bundle_artifact`
- `cartridge_artifacts`
- `result`

Status codes: `200` built (check `build.status`), `400` invalid project,
`409` the project changed in another window, `503` all build slots busy.

`result.publishable` is true only when `.prg32` files were created.

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

```http
POST /api/publish
Content-Type: application/json

{
  "profile_id": "publish_profile_...",
  "bundle_artifact_id": "artifact_..."
}
```

The backend posts the bundle to the profile's Cartridge Store URL at `/api/publish/bundle`.
