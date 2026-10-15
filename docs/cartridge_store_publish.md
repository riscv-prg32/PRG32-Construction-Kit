# Publishing to Cartridge Store

## Bundle shape

PRG32-Construction-Kit prepares a zip bundle shaped for Cartridge Store:

```text
manifest.json
icon.png
<game>-esp32c6.prg32
<game>-qemu.prg32
source/game.c
source/project.blocks.json
source/game.ir.json
```

The `source/` directory is extra teaching material. Cartridge Store uses the manifest and `.prg32` files.

## Configure a publish profile

Open **Publish** and create a profile:

```text
Name: Local Cartridge Store
URL:  http://127.0.0.1:5080
Token: optional bearer token
```

The token is write-only: after you save it, the kit only shows "token saved"
and never sends the token back to the browser. To change it, create a new
profile (or `PUT /api/publish_profiles/<id>` with a new `bearer_token`).

Only bundles stored in the kit's own data folders can be downloaded or
published; an artifact whose `path` points elsewhere is treated as missing.

## Publish flow

1. Open a project.
2. Click **Compile Cartridge**.
3. Open **Publish**.
4. Select the store profile.
5. Click **Publish** on a store bundle.

The backend sends:

```http
POST /api/publish/bundle
Content-Type: multipart/form-data
Authorization: Bearer <token>

bundle=@game-store-bundle.zip
```

## Review behavior

A Cartridge Store may accept the upload as a pending submission rather than immediately publishing it. Teachers/editors review and verify submissions in Cartridge Store.
