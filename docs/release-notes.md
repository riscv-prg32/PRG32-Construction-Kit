# Release notes

## Unreleased

### The PRG32 look: logo, colours, Day and Night

- The Projects page's title says what the kit does: cartridges in RISC-V assembly, C, Python
  or blocks, with sprites and audio, simulated, run on a real PRG32 and published on the
  Cartridge Store (in all five languages).
- The menu bar shows the official PRG32 logo (`PRG32/assets/prg32_logo.png`) and the name
  **PRG32 Construction Kit**, always; the project's name is in the IDE's toolbar. The logo
  closes an open project. The browser-tab, home-screen and installed-app icons are made from
  the same logo by `tools/make_icons.py`.
- The kit's colours are the logo's (black, deep purple, blue, cyan and neon magenta): the new
  default skin **prg32**. The first navy and gold stay as the skin **classic**.
- A **Day/Night** switch in the menu bar: each reader's choice, kept in this browser
  (`prg32-kit-color-scheme`, on `/privacy#storage`), applied before a page is drawn, also
  on the offline pages; the IDE's code editors follow it.

### The top menu works on the open project (IDE-01)

- While a project is open (the IDE, `/player?project=<id>`), the PRG32 icon closes it and goes
  back to Projects, the project's name replaces the kit's, and **Editor**, **Sprite Lab**,
  **AudioStudio** and **Debug** work on that project: the first three switch tab in the IDE
  without a reload, Debug opens the Player and its debugger on the project's newest compiled
  cartridge (`docs/ide.md`).
- **Generated (read-only)** of a Blocks project now has `game.py`: the same game in PRG32
  Python, to read beside `game.c` and `game.S` (`generated_code.md`). Every example gives a
  `game.py` the PRG32 Python compiler accepts and that plays exactly like the blocks.
  PRG32 Python also accepts player 2's buttons (`prg32.P2_LEFT`, ...) and `prg32.frame()` as
  the frame count, as its guide said.
- Each project card on the Projects page has **Sprite Lab**, **AudioStudio** and **Player**
  beside **Open**; the welcome banner has **Sprite Lab**, **AudioStudio** and **Player** not tied
  to a project (choose the game, or open a `.prg32` file). With no project open, the menu keeps
  the project pickers, and Debug opens the empty Player.

### PRG32 Python projects and five interface languages (I18N-01, PY-01)

- **PRG32 Python** (ADR-0026, `python_language.md`, tutorial 9): a fourth project type. `game.py`
  is parsed without being run, checked against an allow-list with static types and limits, and
  translated into the Blocks' game IR; the same generators write the commented C and RV32IM
  assembly and the sandboxed toolchain builds the cartridge. Editor colours, completion, hover,
  signature help and live checks; the debugger follows `game.py` lines; archives use schema
  version 2 (`src/game.py`); provenance records the language, the parser grammar and the
  SHA-256 of `game.py` and of the IR. An example game: *Brick Catch (Python)*.
- **Five interface languages** (ADR-0027, `i18n.md`): English, Italiano, Español, Français and
  Deutsch for every page, script message, block, tooltip, screen-reader label and the offline
  pages, chosen with a menu (cookie `prg32_locale`) or from the browser; privacy notice summaries
  in all five; the storage notice is now version 1.1 (it names the language cookie). Builds are
  byte-identical in every language. Still English: messages written by the server, Blockly's and
  Monaco's own menus, and the long-form documentation (the quick start is in all five).

### Shared identity with the Cartridge Store (after the audit of bb2b062)

- One model, chosen by the project owner: the **username is shared** between the kit and the
  Store and stays private to its owner; the Store's **public handle** is a separate,
  pseudonymous display name. Accounts are matched by email, never by username, and a
  username already taken in the Store is never joined (`accounts_and_sso.md`).
- The Store from `4a3138b` needs `docs/upstream/cartridge-store-shared-identity.patch`
  (§6.1): `/api/me` returns the account username with `public_handle` beside it, the privacy
  notice gate answers API calls in JSON, SSO users see the Store's notice once per version,
  and unsigned API posts get `401`. The patch is proved in a clone, not merged.
- The kit's Store tests sign in on the Store's forms as a browser does (CSRF token, notice),
  and pass against the pinned Store `820f74b` and `4a3138b` with the patch. Handoff:
  `docs/handoff/refinement-after-bb2b062.md`.

### Privacy and documentation (after the GDPR and documentation audit of 7c83e71)

- Personal data (ADR-0022, `privacy/`). The school or operator running the kit is the
  controller. The kit now has:
  - a field-level record of processing that tests keep in step with every database column;
  - proposed roles and legal bases; retention; processors and transfers; a children, DPIA
    and DPO screening;
  - an Article 32 review, a breach playbook and a scripted breach rehearsal.

  **The deployment stays NO-GO** until the controller and its DPO decide the open questions
  in `privacy/decisions.md`. No legal review has happened yet.
- Rights in the kit:
  - "Download my data": one structured document, without secrets;
  - requests to correct, delete, pause or object, answered by staff within one month;
  - restriction (read and download only);
  - erasure that reaches every table, build folder, file and cloud token, keeps the audit
    log under a pseudonym, and is re-applied after a backup is restored.
- Short notices where data is collected, on a new `/privacy` page and in the Account page's
  "Your data" section. The version each person was shown is recorded.
- Fixed:
  - deleting an artifact now deletes its uploaded file;
  - local sign-ins and their failures are now in the audit log;
  - the session cookie is sent only when it changes. Before, a slow page request could
    overwrite a school sign-in or cloud connection that had just started.
- Retention also removes audit events after 365 days and old sign-up links. Backups record
  their date, and `tools/backup_restore.py prune` deletes old ones.
- README rewritten for today's product. `architecture.md` rebuilt around generated diagrams
  (`tools/build_diagrams.py`): trust boundaries, pipeline, game loop and frame clock,
  personal data.
- Every picture is listed in `figures/manifest.json`. Screenshots were re-captured with
  synthetic data (`tools/capture_visuals.py`), and the runtime frames were re-rendered with
  identical pixels.
- `tools/check_docs.py` runs in CI. It checks:
  - links, images and alt text;
  - orphan and stale pictures;
  - settings, routes and ABI versions named in the docs;
  - ADR and capability IDs.

  A human checklist goes with it (`release_checklist.md`).
- Security follow-ups from the Article 32 review and the breach rehearsal:
  - Store bearer tokens are encrypted at rest (older databases at start-up);
  - every request made with an API token is in the audit log;
  - a sign-in from a new address is flagged in the log, mailed to the person when the kit
    can send email, and listed under *Recent sign-ins* on the Account page;
  - answered rights requests can expire (`PRG32_KIT_PRIVACY_REQUEST_DAYS`).

### Sound on one clock everywhere, and the patches proposed upstream (after the audit of 951f782)

- One scheduling boundary between cartridge frames and audio buffers (ADR-0021): audio calls
  take effect at the start of their frame (N × 33 ms). The browser core counts frames instead
  of instructions; every recorded sound is unchanged.
- The SDK patch adds the same frame clock to the firmware's QEMU path, and PRG32-QT's patch
  to its firmware audio. The whole recordings are now equal in all three, sample for sample,
  run after run (`docs/evidence/qemu-audio/2026-10-21-frame-clock/`). A test fails if an
  effect moves by one 20 ms buffer.
- The three patches are open pull requests (not merged): riscv-prg32/PRG32#45 (buzzer
  retired), riscv-prg32/PRG32#46 (frame clock, fresh mixer), riscv-prg32/PRG32-QT#1 (firmware
  audio engine). Links in `docs/upstream/README.md`.
- PRG32-QT delivery recorded again with the integrity checks: each of the five cartridges
  reported running itself before and after its screenshot
  (`docs/evidence/delivery/2026-10-21-prg32qt-checked/`). Handoff:
  `docs/handoff/refinement-after-951f782.md`.
- Every live suite in one step: `tools/run_live_suites.py` runs the Store, sign-in (a
  disposable Keycloak or a school's test tenant), cloud and QEMU suites the computer can run,
  says "not run" for the rest, and keeps no secrets or machine names (`live_testing.md`).

### The compiler in the IDE, and shared accounts checked live

- IDE: after every save of C or assembly, the real PRG32 compiler checks the saved file
  (sandboxed, nothing kept) and its messages appear in Problems at their lines; **Check
  with the compiler** in the palette (`ide.md`). Compiler errors after Compile now reach
  their line as well (the build log's `<build>/` paths were not recognized).
- Shared accounts with a real Cartridge Store over HTTP (`tests/test_sso_live.py`): sync,
  single sign-on both ways, publishing with one-time tickets; the Store checks sign-in
  only, recorded in `upstream/README.md`.
- Milestones in `architecture/current-state.md` always name their commit.

### Builds and delivery, reproducible without the toolchain

- `tools/check_build.py` also builds one game written each way (Blocks as C and as
  assembly, Advanced C, handwritten assembly), runs each in the browser core, and can save
  the cartridges and their SHA-256 (`--save-cartridges`, `--evidence`).
- `tools/reproduce_toolchain_checks.py` runs every toolchain check in the kit's Docker
  image, for anyone without the RISC-V toolchain (`reproducing.md`). First run:
  `docs/evidence/toolchain/2026-10-21/`.
- The first recorded PRG32-QT delivery: five kit cartridges on canonical PRG32-QT, with
  screenshots (`docs/evidence/delivery/2026-10-21-prg32qt/`). `tools/delivery_check.py`
  now knows PRG32-QT has four slots, and `--screenshots` keeps the pictures.

### Sound: upstream patches proven, console sessions ready (after the audit of f4b74bc)

- PRG32 SDK patches (`docs/upstream/`, the SDK itself is not changed):
  - the buzzer retired from the portable ABI (1.7, same slots, old cartridges silent, examples
    moved to the 8-voice API);
  - QEMU audio on the emulated clock;
  - a fresh mixer for every cartridge. This fixes the console playing a cartridge's
    soundtrack quieter after the setup menu's sounds.
- PRG32-QT patch: the firmware audio engine by default, checked through a real output device.
- QEMU recordings now line up over whole recordings (`docs/evidence/qemu-audio/2026-10-21-patched`).
- The console capture and the AudioStudio screen-reader session are ready to run: a
  procedure, record formats, and a test that refuses incomplete console evidence.

### Sound: soundtracks on time, and a console check (after the audit of 13766c9)

- Fixed: AudioStudio soundtracks played each note one gap early. The PRG32 tracker runs an
  event and then waits its delta; the kit now writes deltas that way (contract
  `tracker.delta`, checked against `audio_tracker.c`), and a test plays a soundtrack
  through the engine and checks each note starts on its step. Saved documents are
  unchanged; their cartridges are now correct when built again.
- Console audio check (`hardware_audio_check.md`): an AudioStudio project built into real
  PRG32 cartridges by the kit (8 voices with their own pans and envelopes, hard left and
  right, a sample effect, "stop all sounds"), and `tools/hardware_audio_compare.py`, which
  compares a console recording with the browser core. With an I2S logic-analyser capture
  it checks digital silence, zero crosstalk and bit-exact single-voice stretches.
- The PRG32 firmware's sound recorded in QEMU (`tools/qemu_audio_capture.py --build`) and
  compared with the browser core: equal sample for sample between cartridge events
  (`docs/evidence/qemu-audio/`). The console check now sets the master volume itself.
- PRG32-QT: a proposed patch (`docs/upstream/`) renders sound with the firmware's engine;
  tested bit-exact against the browser core. Upstream findings are listed there too.
- CI keeps the conformance PCM (WAV) and voice trace, browser failure screenshots, and
  rebuilds the console check in the toolchain container.

### Sound: the console's engine in the browser; the buzzer is gone (audio audit of c0d115e)

- The Player now plays the PRG32 firmware's own audio engine, compiled into the browser
  core: 8 voices, SID-like synth sounds with filter, ADSR envelopes, samples, soundtracks
  and the stereo mix, exactly as the console renders them (ADR-0021, `audio_engine.md`).
- The obsolete buzzer is refused in Advanced C and assembly (with what to use instead),
  no longer suggested by the editor, and silent in old cartridges (the Player says so).
- The audio contract (`contracts/prg32-audio-contract-1.json`) is checked against the PRG32
  SDK; an 8-voice conformance cartridge pins the sound by hash and envelope trace.
- **AudioStudio** (`audio_studio.md`, tutorial 8): a project's instruments, sound effects,
  soundtracks (an 8-voice step grid) and WAV samples, heard through the same engine. New
  blocks: *play sound effect*, *play soundtrack*, *stop soundtrack*, *stop all sounds*; the
  generated C and assembly name the fixed numbers. Builds pack the sound into the cartridge
  (`audio_block_sha256` in the build record); archives, copies and export carry the samples.
- The Blocks simulator plays its sounds through the PRG32 engine with the project's
  instruments, and Pause silences them.
- Service worker `prg32-kit-v19`.

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
