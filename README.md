# PRG32-Construction-Kit

A classroom web app for making PRG32 games. Students write a game with Blocks, C or RISC-V
assembly, compile a real `.prg32` cartridge, and run and debug it in the browser. Teachers
follow their classes' work. Flask, SQLite, Bootstrap, jQuery, Blockly and Monaco, installable
as a PWA, with every library served by the kit itself. MIT License.

![The IDE with the Pong project: project files, the Blocks program, the tool window and the simulator](docs/figures/PRG32-Construction-Kit_01.png)

## What it does

- **Three ways to write a game, one IDE** laid out like JetBrains: files, editor, tool window,
  simulator ([ide.md](docs/ide.md)). The type is chosen in **New Project**; Blocks can be
  converted to C or assembly once:
  - Blocks, with the generated C and RV32IM assembly explained line by line
    ([generated_code.md](docs/generated_code.md));
  - C against the portable PRG32 ABI;
  - handwritten assembly ([handwritten_assembly.md](docs/handwritten_assembly.md)).
- **Real compiler, real cartridges.** Validators check the source first. Then the PRG32
  toolchain compiles it in a sandbox, one folder per build, and its messages appear at their
  lines ([build_sandbox.md](docs/build_sandbox.md),
  [install_cartridge_build.md](docs/install_cartridge_build.md)).
- **Run and debug in the browser.** **Run** builds any game (also without an account, keeping
  nothing) and plays it on the right in the PRG32-QT core compiled to WebAssembly, with
  breakpoints, stepping and source and block debugging. Its limits are listed in
  [wasm_runtime.md](docs/wasm_runtime.md).
- **Sprite Lab and AudioStudio**, as tabs of the open project:
  - pixel sprites and tiles ([sprite_editor.md](docs/sprite_editor.md));
  - eight voices with their own ADSR envelopes, samples, a soundtrack grid and stereo, played
    by the PRG32 firmware's own audio engine ([audio_studio.md](docs/audio_studio.md),
    [audio_engine.md](docs/audio_engine.md)).
- **GitHub**: commit, push and pull a project from the IDE's Git tab, for signed-in users
  ([github.md](docs/github.md)).
- **Accounts and boundaries**:
  - guests keep their games in the browser only ([storage.md](docs/storage.md));
  - registered and school sign-in accounts, classes with read-only supervision
    ([accounts_and_sso.md](docs/accounts_and_sso.md),
    [classes_and_roles.md](docs/classes_and_roles.md));
  - optional copies in the student's own Google Drive or OneDrive
    ([cloud_storage.md](docs/cloud_storage.md));
  - reviewed publishing to a PRG32 Cartridge Store
    ([cartridge_store_publish.md](docs/cartridge_store_publish.md)).
- **Privacy.** The school or organisation that runs the kit is responsible for the personal
  data in it. [docs/privacy/](docs/privacy/README.md) has the records, notices, rights
  workflows and incident playbook. The legal decisions there are still open: read it before
  going live.

## What is verified, and what is not

| Path | Status | Evidence |
|---|---|---|
| Browser runtime (WebAssembly) | verified: same results as the native core and PRG32-QT | [wasm_runtime.md](docs/wasm_runtime.md) |
| PRG32-QT (desktop) | verified through its web API; the Import menu has not been driven | [delivery.md](docs/delivery.md) |
| PRG32 firmware in QEMU | verified, including sound over whole recordings | [audio_engine.md](docs/audio_engine.md) |
| PRG32 console (ESP32-C6) | **not verified**: cartridges download, but no delivery or sound capture is recorded | [hardware_audio_check.md](docs/hardware_audio_check.md) |
| PRG32-iOS | **unsupported** | [ADR-0020](docs/adr/0020-delivery-targets-and-evidence.md) |
| School sign-in | verified against a throwaway Keycloak; no real school tenant | [identity_live_testing.md](docs/identity_live_testing.md) |
| Google Drive, OneDrive | **not run against real accounts** | [cloud_storage.md](docs/cloud_storage.md) |
| GitHub | **not run against real GitHub**: an in-process fake only | [github.md](docs/github.md) |
| Cartridge Store | verified against a throwaway Store | [live_testing.md](docs/live_testing.md) |

Every capability's status, source and tests: [capabilities.md](docs/capabilities.md).

## Quick start with Python

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5090/>: anyone can make games there without an account, kept in their
browser ([guest_mode.md](docs/guest_mode.md)). To build cartridges, publish and change the
**Settings**, sign in as `admin`. The first start writes a random
password to `data/initial_admin_password`, or uses `PRG32_ADMIN_PASSWORD` if you set a long
one. Change the password on **My account**; the file is then deleted. Data is stored in
`data/`, or in `PRG32_KIT_DATA` if set.

## Quick start with Docker Compose

```bash
cp examples/deploy/classroom.env .env   # change PRG32_ADMIN_PASSWORD
docker compose up --build
docker compose exec prg32-construction-kit python tools/check_build.py
```

The image includes the RISC-V compiler and the PRG32 build tools, so **Compile**
makes real `.prg32` cartridges. The compose file mounts `./data` to `/data`.

## Cartridge builds without Docker

Put a [PRG32](https://github.com/riscv-prg32/PRG32) checkout next to this one, install it
into the kit's environment, and put ESP-IDF 5.4's `riscv32-esp-elf-gcc` on `PATH`:

```bash
.venv/bin/pip install --no-deps -e ../PRG32
examples/deploy/start-kit.sh   # finds the compiler, checks builds, starts the kit
```

Without the toolchain, **Compile** makes a source bundle (generated C, project,
game IR, manifest). Step by step for Docker, macOS, Linux and Windows:
[install_cartridge_build.md](docs/install_cartridge_build.md).

## Documentation

- [docs/index.md](docs/index.md): every guide, for students, teachers and operators;
- [architecture.md](docs/architecture.md): components, trust boundaries, data flows;
- [privacy/](docs/privacy/README.md): personal data, for the school running the kit;
- [release_checklist.md](docs/release_checklist.md): what a person checks before a release;
- [AGENTS.md](AGENTS.md): the rules for contributors.

## License

MIT License. See `LICENSE`.
