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
The exact rules are in the shared Store contract (`store_contract.md`); the kit
checks every bundle against it before anything is uploaded.

## Which Stores can be used

Publishing makes the kit's *server* send the bundle, so only Stores your
teacher (the administrator) approved can be used. A profile with any other
address cannot be saved, and an old profile whose Store was removed from the
list is refused when you press **Publish**. The kit also refuses Stores that
lead into a private network or answer with a redirect. See
`admin-guide.md` (*Publishing to a Store*) and `adr/0008-store-egress-policy.md`.

## Configure a publish profile

Open **Publish** and create a profile:

```text
Name: School Cartridge Store
URL:  https://store.your-school.example   (an approved Store)
Token: optional bearer token
```

The token is write-only: after you save it, the kit only shows "token saved"
and never sends the token back to the browser. To change it, create a new
profile (or `PUT /api/publish_profiles/<id>` with a new `bearer_token`).

Only bundles stored in the kit's own data folders can be downloaded or
published; an artifact whose `path` points elsewhere is treated as missing.

When the kit is linked with the Cartridge Store (`accounts_and_sso.md`), a
profile whose address is `PRG32_SSO_PEER_URL` needs no token: the kit sends a
one-time ticket and the bundle is published as the signed-in student.

## Who can publish

Publishing needs the **publisher** role (or admin). Everybody can compile and
download cartridges; a teacher gives the publisher role on the **Users** page
(it is synced with the Cartridge Store). Only bundles with compiled
cartridges can be published: a *source-only* bundle (made on a server without
build tools, or when the compiler failed) cannot.

## Publish flow

1. Open a project.
2. Click **Compile Cartridge** so the bundle contains both architectures (**Download .prg32** builds only one).
3. Open **Publish**.
4. Select the store profile.
5. Click **Review & publish** on a store bundle. The kit opens the bundle and
   shows exactly what will be sent: the Store, the cartridge id, title and
   version, every cartridge file with its size and SHA-256 fingerprint, and
   what the Store does next.
6. Tick *I checked this summary…* and press **Publish**.

If anything changes between review and confirmation (another bundle, another
Store address, an edited file) the kit refuses and asks you to review again.
Pressing **Publish** twice never uploads twice. If the upload fails (the
Store is unreachable, or it refuses the version), you can try again.
The result says why with a contract code (`error_code`) and whether trying again
can help (`retryable`).

The backend sends:

```http
POST /api/publish/bundle
Content-Type: multipart/form-data
Authorization: Bearer <token>

bundle=@game-store-bundle.zip
```

## Review behavior

A Cartridge Store may accept the upload as a pending submission rather than immediately publishing it. Teachers/editors review and verify submissions in Cartridge Store.
