# Release notes

## Unreleased

### Delivery and evidence (after the audit of fea31c0)

- `delivery.md`: putting a game on the PRG32 console, PRG32-QT or the browser.
  PRG32-iOS handoff is deferred, and the kit no longer suggests it (ADR-0020).
- `tools/delivery_check.py` uploads to a console or PRG32-QT through the PRG32 web
  API and records hashes, slot, screenshot and outcome.
- Builds: a disk budget per build (`PRG32_BUILD_MAX_MB`) and for all builds
  together (`PRG32_BUILD_ROOT_MAX_MB`, 507 when full); builds run inside their own
  folder in every mode, with relative `PATH`/`PYTHONPATH` entries resolved first.
- AppArmor hosts: load `docker/apparmor/prg32-kit` instead of running the
  container unconfined (`build_sandbox.md`).
- Debugger: the source-map markers carry a number instead of the block id, so odd
  block ids can no longer cost a project its block highlighting; the debug-map
  reader refuses ELF images over 1 MiB. Both readers are fuzzed
  (`tests/test_debug_fuzz.py`).
- Store lifecycle: the kit sends one bundle per game version to a Store (save to make
  a new version) and stops using a publish profile's Store token after 180 days
  (`PRG32_STORE_TOKEN_MAX_DAYS`); the profile shows the date. New columns are added on
  start. The Store contract only gained keys, including the proposed Store-side codes.
- Operations: `tools/backup_restore.py` (backup while running, restore into a clean
  folder with artifact paths moved, verify), tested as a restore drill; the Docker image
  installs exactly `requirements.lock` (hashes); `docs/sbom.cdx.json` (CycloneDX);
  `cryptography` 50.0.2 and `pytest` 9.1.1 after an audit (`dependencies.md`).
- Quality gates: `ruff` (pyflakes rules), a coverage floor of 88% (measured 91%), and
  performance budgets in a real browser with a 4x slower CPU (`performance.md`).
- Fixed: taking a cloud version of a project deleted meanwhile answered 500; now 404.
- Debugger: breakpoints stay when the game is compiled again (they follow their
  code, or are listed as "the code changed"), and can be switched off without being
  removed; inlined functions appear in the call stack as "inlined into ...". Service
  worker `prg32-kit-v17`.
- Cloud storage: more checks against the fake providers (files the kit did not
  make, outages while taking the cloud version, the Drive check-then-write window).

### Cloud storage: Google Drive and OneDrive (after the audit of e2d0cef)

- Optional (`cloud_storage.md`, ADR-0019): connect on *My account*, then **Save to
  cloud** / **Get cloud version** from the dashboard. Least-privilege permissions,
  explicit consent, encrypted tokens, bounded retries.
- When the project changed here and in the cloud, you choose: keep both, take the
  cloud version (yours goes into History) or overwrite the cloud copy.
- Fixed: restoring a revision now gives the project a new version, so a window
  still showing the old one cannot save over the restore.
- New tables `cloud_accounts` and `cloud_links` (created on start). Service worker
  `prg32-kit-v16`.

### Shared Store contract (after the audit of e2d0cef)

- `contracts/prg32-store-contract-1.json` (ADR-0018, `store_contract.md`): bundle,
  manifest schema, architectures, versioning, errors and tokens in one file.
- Bundles are checked against it before upload; Store refusals come back with a
  code, a student message and whether to try again.
- The manifest version follows the project (`0.1.<version>`).
- Generated fixture bundles agree with the Cartridge Store's own code; a live suite
  publishes to a throwaway Store (CI job `store-contract`).

### School sign-in against a real provider (after the audit of e2d0cef)

- Opt-in live test suite against Keycloak (`identity_live_testing.md`), also as a
  manual CI job; it can target an institution's test tenant from environment
  variables only.
- Fixed: discovery and key caches could stop refreshing if the server clock was
  stepped back; a negative cache age now counts as stale.
- Signing out after a school sign-in says that the school session may remain
  (logout is local only; no SCIM provisioning: ADR-0016 amendment).

### Guest and registered storage policy (refinement phase 6)

- Guest games: *Try without an account* keeps several blocks games in the
  browser (IndexedDB) with names, export/import as files and a space meter;
  signing in offers to move them into the account. Nothing is stored on the
  server for guests (`PRG32_GUEST_MODE`, ADR-0017, `storage.md`).
- Projects have a `version`; saves from the IDE and the editor are refused
  (409) instead of overwriting a newer save, and the student chooses: keep a
  copy, load the saved one, or save over it.
- The IDE autosaves 5 seconds after the last change; autosaves add to History
  at most every 10 minutes.
- Per-student quotas (projects, MB), `GET /api/storage`.
- Retention: trash emptied after 30 days, 10 builds kept per project,
  interrupted build folders removed (`flask prg32-retention`,
  `POST /api/admin/retention`); `DELETE /api/users/<id>?with_items=1`.
- **Upgrade notes:** new column `projects.version` (added at start-up). The
  offline scratchpad becomes a guest game automatically. Builds beyond 10 per
  project are removed on the next compile of that project: raise
  `PRG32_KIT_KEEP_BUILDS` first if you need them. Service worker `prg32-kit-v15`.
  Rollback: revert; the column is ignored and guest games stay in IndexedDB.

### Academic identity and scoped roles (refinement phase 5)

- School sign-in with OpenID Connect: Authorization Code + PKCE, verified ID
  tokens, several providers set up by an administrator (**Users → School sign-in
  providers**), accounts by issuer + subject (ADR-0016).
- **Change:** an identity provider can no longer take over an account by sending
  its email address. A first sign-in whose email already has an account is
  refused; the owner links the school account on **My account**. Existing
  `PRG32_OIDC_*`/SAML links are kept (issuer `legacy:<provider>`).
- Roles in class (`student`, `teacher`, `facilitator`, `service`) and **Classes**:
  teachers and facilitators read, never change or publish, their students' work.
- API tokens have scopes and an optional expiry; old tokens keep full access.
- Sessions end after a password, role or role-in-class change, on **Sign out
  everywhere** and `PRG32_KIT_SESSION_HOURS` after sign-in. Administrators can
  switch accounts off (deprovisioning) and on again.
- **Upgrade notes:** new tables and columns are added at start-up; `cryptography`
  is now required; `authlib` is no longer used; set `PRG32_KIT_PUBLIC_URL` behind a
  proxy. A role change now signs that user out. Rollback: revert; the new tables
  and columns are ignored, and accounts linked by a new provider fall back to
  password sign-in.

### Source and block debugger (refinement phase 4)

- Cartridges compiled in the kit can be debugged at the level students wrote
  them (ADR-0015, lesson 7): breakpoints on Blockly blocks and on C or
  assembly lines, optionally with a condition (`score > 10`); the running block
  highlighted; Next block / Next line; Blocks variables, locals and globals;
  call stack; watches (`player.x`, `heights[2]`, `a0`); counter CSRs; stack.
- The kit compiles with `-g` beside the normal build: the cartridge is
  byte-identical (checked on every build) and the DWARF is turned into a small
  debug map. Blocks projects also get a block map. Both are artifacts
  (`debug_map`, `source_map`), read with `GET /api/artifacts/<id>/debug`.
- The core's debug state reports the `cycle`/`time`/`instret` counters.
- The server's assembly check keeps its behaviour; a fixture cartridge with
  16- and 32-bit instructions is stepped in tests in the browser core and natively.
- Accessibility fixes on the Player: contrast of the view switch and the Step
  frame button; the code and memory views can take the keyboard focus.
- **Upgrade note:** new Python dependency `pyelftools`; `PRG32_DEBUG_INFO=0`
  turns debug builds off. No database change. Service worker cache `prg32-kit-v14`.
  Rollback: revert; cartridges are unchanged and old builds simply have no maps.

### Language services in the IDE (refinement phase 3)

- C and assembly editors suggest PRG32 functions, constants and types, the
  allowed headers and directives, RV32IMC instructions and registers; hover and
  signature help explain them; F12 opens the declaration in a read-only
  `prg32.h (portable API)` (ADR-0014, `ide.md`).
- Problems are marked while typing, at the exact words, with a short
  explanation; calls to resident-firmware functions are marked before the
  build fails. Compiler messages are shown without server paths.
- Everything comes from `static/js/ide/prg32_language_index.js`, generated from
  the PRG32 SDK by `tools/build_language_index.py`; nothing is fetched.
- The server's assembly check now names the line as the student sees it
  (multi-line comments and line continuations used to shift it). What it
  accepts is unchanged.
- No database change. Rollback: revert; the editors fall back to colours and
  server problems.

### CI and documentation after the audit of 731e378

- The CI browser job also runs the IDE suite (keyboard, Monaco, phone layout,
  axe) and sets `PRG32_REQUIRE_BROWSER=1`: a missing browser fails the job
  instead of skipping. Results are uploaded as `browser-test-results.xml`.
- `architecture/current-state.md` describes `731e378`; `tests/test_doc_consistency.py`
  checks that it, and every `[ID]` tag in the docs, agree with `capabilities.json`.
- No code or database change.

### The IDE (refinement phase 2)

- New **IDE** page per project (`/ide/<id>`, ADR-0013, `ide.md`): file tree,
  editor tabs, Problems/Output/Preview/Run panels, status bar, command
  palette, F6 regions, full keyboard operation, small-screen file panel.
- Monaco 0.52.2 (vendored) for Advanced C and assembly, with a PRG32 RISC-V
  assembly grammar; generated C/assembly/IR as read-only, copyable tabs;
  problems as editor markers with jump-to-line.
- Fixed: the Blocks preview and the Player took Enter and the arrow keys from
  the whole page, so buttons could not be pressed with Enter. Game keys now
  work while the game screen has the focus (it takes it on Play).
- The toast close button has an accessible name.
- No database change. Rollback: revert; the classic editor is unchanged.

### Self-contained frontend, offline page and CSP (refinement phase 1)

- Bootstrap, Bootstrap Icons, jQuery and Blockly (with its media) are served
  from `static/vendor/` (pinned, integrity-checked, licences recorded); no CDN.
- Strict Content Security Policy on every response; `no-store` on pages and
  API answers (ADR-0012).
- The service worker moved to `/service-worker.js` (scope `/`; the old
  `/static/` scope never covered the pages). Offline, any page shows the
  static offline page: blocks scratchpad + local cartridge player.
- **Upgrade note:** no database change. Browsers replace the old worker on the
  next visit. Rollback: revert the code; the old `/static/` registration
  comes back on its own.

### Security: every compile runs in a sandbox (audit H-03)

- Compiles run under bubblewrap (no network, read-only SDK/compiler, only
  their own build folder writable, cleared environment, seccomp filter) with
  resource limits and a process-group kill at the timeout (ADR-0010,
  `build_sandbox.md`). Provenance records `sandbox`.
- The build environment is an allow-list: server secrets no longer reach
  the compiler.
- **Upgrade note:** start the container with `docker/seccomp-kit.json` (the
  compose file does); on AppArmor hosts see `build_sandbox.md`. The image
  refuses to start without a working sandbox. Outside Docker, `auto` keeps
  working with limits only (`rlimit`) except in production. No database
  change; rollback is a code revert.

### Security: publishing needs the publisher role and a confirmed review (audit H-02)

- `POST /api/publish/review` + `POST /api/publish` with `review_token` and
  `"confirm": true`; only `publisher`/`admin`; only bundles with real,
  build-matching cartridges; one upload per review; retries after failures
  (ADR-0009). The Publish page shows a review dialog.
- **Migration:** new table `publish_attempts` (created at start-up). One-step
  `POST /api/publish` now answers `428`. Students who published before need
  the `publisher` role. Rollback: revert the code; the extra table is ignored.

### Security: Store egress policy (audit H-01)

- Bundles are only sent to Cartridge Stores the administrator approved
  (`PRG32_STORE_ALLOWED_ORIGINS`, default: `PRG32_STORE_URL` and
  `PRG32_SSO_PEER_URL`), over https, to public addresses, with the
  connection pinned to the checked address, no redirects, timeouts and a
  bounded answer (ADR-0008).
- Publish profiles with other addresses are refused (`400`); errors no longer
  echo exception text or Store bodies; the result has a new safe shape.
- **Upgrade note:** a Store on a private network or `http://127.0.0.1` now
  needs `PRG32_STORE_TRUSTED_LOCAL=1` (and plain http a non-production
  server). Existing profiles for other Stores stay listed but are refused at
  publish time until the Store is approved. No database change; rollback is a
  plain code revert.

### Debugger in the Player (G5, first slice)

- **Debugger** card on `/player`: Debug mode switch, Continue/Pause, Step
  (one instruction), Step over, Step out, Step frame, speeds 0.01×–4×
  (PRG32-QT's list), breakpoints in the disassembly gutter (remembered per
  cartridge), x0–x31 with ABI names and changed values highlighted, PC and
  update/draw phase, disassembly following the PC with Init/Update/Draw/PC
  views and go-to-address, a 128–1024 byte memory view (decimal or `0x`
  address), game time vs real time. **Beginner** and **Advanced** views
  share one state. Lesson: `docs/tutorials/07_debugger.md`.
- The core's C interface gains breakpoints, an instrumented run with an
  instruction budget, PRG32-QT's resume rule, step over/out and
  disassembly; native and WebAssembly builds are tested to step identically.
  `static/wasm/` rebuilt (≈ 145 KB) from the same PRG32-QT commit.
- JavaScript protocol uses PRG32-QT's `/api/debug` commands and state names
  (ADR-0006 accepted).
- Service worker cache `prg32-kit-v11`. No database changes.

### Browser PRG32 core (G4)

- **Player** page (`/player`) and **Play in browser** after a compile: real
  `.prg32` cartridges run in the browser on PRG32-QT's core compiled to
  WebAssembly (`static/wasm/`, ≈ 125 KB, cached for offline use).
- `tools/build_wasm.py` rebuilds the module from a PRG32-QT checkout and
  records its provenance in `static/wasm/BUILD.json`.
- Golden tests (`tests/test_wasm_runtime.py`) and a CI job prove the browser
  core behaves exactly like the native core and `prg32qt-headless`.
- No database changes.

### Security and quality (round 1)

- **No default admin password.** The first start writes a random password to
  `<data>/initial_admin_password` (mode 600, deleted once an admin changes
  it) unless `PRG32_ADMIN_PASSWORD` is set. With `PRG32_KIT_ENV=production`
  (the Docker image) a short or well-known password stops the start.
  Compose no longer defaults to `password`.
- **Sign-in limits**: wrong passwords (per address+name and per address),
  registration requests, invalid registration links and new API tokens.
  `429` + `Retry-After`. `PRG32_KIT_PROXY_COUNT` for reverse proxies;
  `DELETE /api/admin/throttles` to unlock a class.
- **Audit log** (`GET /api/admin/audit`, admins only) for accounts, roles,
  groups, passwords, API tokens, bootstrap, registrations, sign-in locks,
  publishing, SSO syncs and unlocking. No secrets are stored.
- **Build provenance** in `build.metadata.provenance` and SHA-256/size on
  every `.prg32` artifact (`build_provenance.md`).
- A build whose compiler refused the source is now `failed` (it was shown as
  `source-only`); the editor says so.
- **Restore keeps identity**: sprites and assets are restored in place, in
  one transaction, so artifacts keep their sprite links.
- Build logs and package responses no longer show server folders (the
  Python path in the logged command, `result.source_path`) or secret-looking
  build-command options.

### Migration and rollback

- New tables `audit_events` and `auth_throttle`; new column
  `project_revisions.child_ids` (default `'{}'`). All created at start-up,
  idempotently. Older revisions keep working (matched by name).
- Rollback: the previous release ignores the new tables and column, so
  downgrading the code is safe. Before rolling back, note that the previous
  release would again create `admin`/`password` on an empty database.

### Added

- Portable project archive: **Export → Project archive (.zip)** in the
  editor, `GET /api/projects/<id>/archive`. Holds `prg32.project.json`
  (schema 1), the source, sprites and assets; byte-identical for the same
  project.
- **Import project** on the dashboard accepts archives as well as JSON.
- `GET /api/projects/<id>/manifest` and `POST /api/projects/<id>/duplicate`.
- **History** in the editor: every save that changes the blocks, the
  Advanced C or the handwritten assembly keeps the version before it. Restore one (the current version
  is kept first) or download it as a project archive. Newest 50 per project
  (`PRG32_KIT_MAX_REVISIONS`). API: `/api/projects/<id>/revisions...`.
- **Recently deleted** on the dashboard: deleting a project hides it instead
  of removing it; restore it from there (`POST /api/projects/<id>/restore`,
  `GET /api/projects?deleted=1`). Admins can delete for good
  (`DELETE /api/projects/<id>?purge=1`).
- Full-IDE planning documents: current-state matrix, ADRs, plan, status,
  traceability, compatibility, security, deployment, user and admin guides.

- **Assembly (RISC-V)** editor mode: write a cartridge in handwritten
  assembly. It is checked against a directive allow-list and then built by
  the PRG32 toolchain (ADR-0004, `handwritten_assembly.md`). Archives store it
  as `src/game.S` with `authoring_mode: "assembly"`.

### Changed

- **Make my copy** now copies a shared project on the server, including its
  sprites and assets (it used to copy the blocks only).
- Importing an old single-file JSON export goes through the project-format
  migration. The game IR stored in that file is no longer copied; it is
  derived and is made again on the next convert or build.
- `DELETE /api/projects/<id>` keeps its answer but now moves the project to
  Recently deleted. Project items include `deleted_at`.
- Service worker cache `prg32-kit-v8`.

### Migration

New table `project_revisions` and new column `projects.deleted_at`, added
automatically and idempotently on start; existing databases keep working.
Old exports keep importing.
