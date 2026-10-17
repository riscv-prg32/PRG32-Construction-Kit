# Accounts and single sign-on

The Construction Kit uses the same kind of accounts as PRG32 Cartridge Store.
Accounts live in the kit's own database: no cloud service is needed.

## For students

- Open the kit and **sign in** with your username (or email) and password.
- No account yet? Choose **Create an account**, type your email, and open the
  link you receive to pick a password (at least 10 characters). If your school
  turned this off, ask your teacher for an account.
- Your projects, sprites and files are **yours**: classmates cannot see or
  change them. Your teacher can.
- The starter games are **shared** with the whole class. You can open and read
  them; press **Make my copy** to change, run and build your own version.
- If your teacher linked the kit with the Cartridge Store, your account works
  in both places. The **Cartridge Store** button opens the store already signed
  in, and **Publish** sends your cartridge as you.

## For teachers

### First start

The first start creates the account `admin` / `admin@localhost`. Its password
is `PRG32_ADMIN_PASSWORD`, or `password` when that is not set. **Change it
right away** on the **My account** page (click your name in the menu).

The kit only ever creates this account while there is no admin at all, so
renaming or deleting it never brings it back.

### Roles and groups

| Role | Can do |
|---|---|
| `reader`, `user`, `player` | Make and build their own projects |
| `publisher` | The same (the Cartridge Store uses it for publishing rights) |
| `admin` | See and change everything, manage users |

Groups are labels such as `editors` or `class-3b`. The Cartridge Store uses
the `editors` group for its review queue.

The **Users** page (admins only) creates, edits and deletes accounts. The kit
refuses to delete or demote the last admin, and you cannot delete yourself.

### Who sees what

| Item | Owner | Other students | Admins |
|---|---|---|---|
| Project, sprite, artifact, build, publish profile | read and change | nothing | read and change |
| Shared item (no owner, e.g. starter games) | - | read only | read and change |

Projects made before accounts existed have no owner, so they become shared
items. An admin can give one to a student by setting `owner_id` (the user's
id) with `PUT /api/projects/<id>`.

### Settings

| Variable | Default | Meaning |
|---|---|---|
| `SECRET_KEY` | random, kept in `data/secret_key` | Signs the sign-in cookie |
| `PRG32_ADMIN_PASSWORD` | `password` | Password of the first `admin` account |
| `PRG32_KIT_ALLOW_REGISTRATION` | `true` | Let people create their own accounts |
| `PRG32_KIT_REQUIRE_EMAIL_DOMAIN` | empty | Only allow emails like `name@school.edu` |
| `PRG32_KIT_DEFAULT_ROLE` | `user` | Role of self-registered accounts |
| `PRG32_KIT_SESSION_HOURS` | `12` | How long a sign-in lasts |
| `PRG32_KIT_SECURE_COOKIES` | `false` | Set `true` when the kit is served over HTTPS |
| `PRG32_SMTP_HOST`, `_PORT`, `_FROM`, `_USER`, `_PASSWORD`, `_TLS` | empty | Mail server for registration links. Without one, the link is printed in the server log. |
| `PRG32_OIDC_*`, `PRG32_SAML_*` | off | School sign-in, same names as the Cartridge Store |

### Scripts and API tokens

On **My account**, make an API token. Scripts send it as
`Authorization: Bearer prg32_...`. The token is shown once; the kit keeps
only a hash. Revoke it there if it leaks.

## Linking the kit with a Cartridge Store

When the option is turned on **on both sides**:

- a user created on one side is created on the other one;
- changing a password, email, role or groups on one side changes it on the
  other one;
- deleting a user on one side deletes it on the other one;
- the **Cartridge Store** button in the kit (and **Construction Kit** in the
  store) signs the user in on the other side without a second password;
- publishing from the kit to that store happens as the signed-in student, so
  the store's publish profile needs no token.

### Turning it on

Pick a long random secret once:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Give both services the **same secret** and **each other's address**:

```bash
# Construction Kit
export PRG32_SSO_SECRET="the-same-long-secret"
export PRG32_SSO_PEER_URL="http://store.school.lan:5080"

# Cartridge Store
export PRG32_SSO_SECRET="the-same-long-secret"
export PRG32_SSO_PEER_URL="http://kit.school.lan:5090"
```

Restart both, sign in to either one as an admin, open **Users** and press
**Sync now** once. That copies the accounts that existed before sync was
turned on. After that, changes are sent right away.

Both services start with an `admin@localhost` account. Once linked they are
the same account, with the password that was changed most recently. Change
the admin password on one side after the first sync, and use that password on
both.

Then add a publish profile in the kit whose store address is exactly
`PRG32_SSO_PEER_URL`, with no token. The profile list shows
"publishes as you (single sign-on)".

### How it works

```text
 Construction Kit                                Cartridge Store
 ----------------                                ---------------
 user changed  ──signed POST /api/sso/users──▶  same user changed
 same user changed ◀──signed POST /api/sso/users── user changed

 "Cartridge Store" button ──one-time login ticket──▶ /auth/sso/accept
 Publish ──bundle + one-time API ticket (Bearer)──▶ /api/publish/bundle
```

- **Same email = same person.** Accounts are matched by email.
- **Newest change wins.** Every account has an `updated_at` time; an older
  change never overwrites a newer one.
- **Passwords are copied as hashes**, never as plain text, so the same
  password works on both sides.
- **Signed requests.** Every sync request carries an HMAC signature of its body
  and the time. Without the secret nobody can create or change users, and old
  requests are refused after 5 minutes.
- **Tickets** name the user's email and the service they are for, expire after
  60 seconds (sign-in) or 120 seconds (publishing), and work only once.
- **Offline is fine.** If the other side cannot be reached, the change waits
  in an outbox and goes out with the next change or the next **Sync now**.
- **The last admin is safe.** A synced change never deletes or demotes the last
  admin of a service.
- API tokens are **not** shared: each service has its own.

The protocol is in `prg32_construction_kit/sso_protocol.py`, the same file as
`cartridge_store/sso_protocol.py` in the Cartridge Store.

### Safety notes

- Serve both services over **HTTPS** when they are not on a closed classroom
  network: synced records carry password hashes.
- Anyone who knows the secret can create admin accounts on both sides. Keep it
  like a password, and change it on both sides if it leaks.
- Linking means an admin on one side is an admin on the other side too.
