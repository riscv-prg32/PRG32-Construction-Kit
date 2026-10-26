# The Settings page

Admins have a **Settings** item in the menu (`/admin/settings`). It changes how the kit
works for everybody, **without a restart**: a change applies at once on every page and in
every server process. **Back to the default** is beside each changed setting.

## Who wins: the page or the server?

Every setting also has an environment variable (the table below). When the server sets that
variable, for example in `docker-compose.yml` or `examples/deploy/classroom.env`, the page
shows the setting greyed out with **set on the server**. To change it, change the variable and
restart. That keeps a deployment's files the source of truth. Otherwise the value saved on the
page counts; with neither, the kit's default does.

## The tabs

| Tab | What you can change | Variables |
|---|---|---|
| **Access** | whether every page needs a sign-in; whether visitors without an account can make games in their own browser; whether people can create their own account, and which email domain they need; the role of a new account | `PRG32_KIT_LOGIN_REQUIRED`, `PRG32_GUEST_MODE`, `PRG32_KIT_ALLOW_REGISTRATION`, `PRG32_KIT_REQUIRE_EMAIL_DOMAIN`, `PRG32_KIT_DEFAULT_ROLE` |
| **Maintenance** | maintenance mode and its message: only admins can use the kit; everybody else sees the message. Signing in, `/privacy` and the docs stay open | `PRG32_KIT_MAINTENANCE`, `PRG32_KIT_MAINTENANCE_MESSAGE` |
| **Sign-in** | the kit's public address; single sign-on with a Cartridge Store (address, shared secret, timeout). School sign-in providers have their own page, linked from this tab | `PRG32_KIT_PUBLIC_URL`, `PRG32_SSO_PEER_URL`, `PRG32_SSO_SECRET`, `PRG32_SSO_TIMEOUT` |
| **Email** | the SMTP server for sign-up links and new sign-in notices; **Send a test mail to me** | `PRG32_SMTP_HOST`, `PRG32_SMTP_PORT`, `PRG32_SMTP_FROM`, `PRG32_SMTP_USER`, `PRG32_SMTP_PASSWORD`, `PRG32_SMTP_TLS` |
| **Appearance** | site name, the welcome text on the Projects page, colour scheme (light, dark, or *auto*: each computer's own setting; each reader can still pick Day or Night in the menu bar) and skin (prg32: the PRG32 logo's colours, the default; classic: the kit's first navy and gold; ocean, forest, high contrast) | `PRG32_KIT_SITE_NAME`, `PRG32_KIT_WELCOME_TEXT`, `PRG32_KIT_COLOR_SCHEME`, `PRG32_KIT_SKIN` |
| **Classroom** | projects and storage per user, saved versions, autosave interval, days in Recently deleted, builds kept | `PRG32_KIT_QUOTA_PROJECTS`, `PRG32_KIT_QUOTA_MB`, `PRG32_KIT_MAX_REVISIONS`, `PRG32_KIT_AUTOSAVE_SNAPSHOT_MINUTES`, `PRG32_KIT_TRASH_DAYS`, `PRG32_KIT_KEEP_BUILDS` |
| **Privacy** | who runs the kit and the privacy contact (shown on `/privacy`); how long the audit log, backups and answered requests are kept; whether AudioStudio may record a sample with the microphone | `PRG32_PRIVACY_CONTROLLER`, `PRG32_PRIVACY_CONTACT`, `PRG32_KIT_AUDIT_DAYS`, `PRG32_KIT_BACKUP_DAYS`, `PRG32_KIT_PRIVACY_REQUEST_DAYS`, `PRG32_AUDIO_RECORDING` |
| **Store & cloud** | the Cartridge Store address and other allowed Stores, a Store on the school network, the oldest Store token accepted; Google Drive and OneDrive on or off | `PRG32_STORE_URL`, `PRG32_STORE_ALLOWED_ORIGINS`, `PRG32_STORE_TRUSTED_LOCAL`, `PRG32_STORE_TOKEN_MAX_DAYS`, `PRG32_CLOUD_GOOGLE_ENABLED`, `PRG32_CLOUD_ONEDRIVE_ENABLED` |
| **Build limits** | builds at the same time, waiting and compile time, memory, processes and disk per build, disk for all builds, cartridge RAM, debug information | `PRG32_MAX_PARALLEL_BUILDS`, `PRG32_BUILD_QUEUE_TIMEOUT`, `PRG32_BUILD_TIMEOUT`, `PRG32_BUILD_MEMORY_MB`, `PRG32_BUILD_MAX_PROCESSES`, `PRG32_BUILD_MAX_MB`, `PRG32_BUILD_ROOT_MAX_MB`, `PRG32_CART_RAM_KIB`, `PRG32_DEBUG_INFO` |
| **Server only** | read-only: what can only be set in the server's environment (secret key, data folder, build sandbox and command, proxies, sign-in limits, SAML, cloud app credentials) | |

Each value is checked before it is saved (numbers within their limits, one of the listed
choices, web addresses that start with `https://` or `http://`). One wrong value refuses the
whole save, and nothing is changed.

## Safety

- Only admins open the page or its API (`/api/admin/settings`); an API token needs the
  `admin` scope.
- Passwords and secrets (SMTP password, single sign-on secret) are stored encrypted with a key
  derived from the server's secret key. They are never sent back to the page: it only shows
  whether one is set. Leave the field empty to keep the stored one.
- Every save is in the audit log (`settings_update`) with the **names** of the settings changed,
  never their values.
- A skin only changes colours: it is a stylesheet in `static/css/themes/`, so the kit's strict
  Content Security Policy is unchanged.
