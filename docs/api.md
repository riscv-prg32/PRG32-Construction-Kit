# API Reference

All responses are JSON unless a download endpoint is used.

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
- `result`

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
