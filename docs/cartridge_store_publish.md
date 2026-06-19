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

## Publish flow

1. Open a project.
2. Click **Prepare Cartridge**.
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
