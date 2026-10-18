# PRG32-Construction-Kit

PRG32-Construction-Kit is a Flask, Bootstrap, jQuery, JavaScript, and Blockly progressive web application for classroom PRG32 game creation.

![Construction Kit](docs/figures/PRG32-Construction-Kit_01.png)


Students can:

- create Scratch-inspired block programs with variables, lists, loops,
  pictures, tiles, sound, scores and multiplayer;
- start from five complete classic-inspired games (Pong, Breakout, Space
  Invaders, Asteroids, Snake), each with a step-by-step tutorial deck;
- save PRG32 block games as JSON;
- edit sprites and imported images in a browser pixel editor;
- play and debug games in an online JavaScript simulator that draws like the
  PRG32 firmware (same font, RGB565 colours, 30 frames per second);
- convert block programs to real PRG32-style C source, RISC-V assembly, or
  both, each explained block by block and line by line;
- author advanced C cartridges against the portable PRG32 ABI when a feature
  is beyond the Blocks toolbox;
- prepare Cartridge Store publishing bundles;
- publish bundles to a PRG32 Cartridge Store instance.

The app intentionally follows the same classroom-friendly shape as Cartridge Store: a small Flask service, installable PWA frontend, SQLite persistence, Docker support, `docs/` documentation, and simple HTTP APIs.

## Quick start with Python

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:5090/> and sign in as `admin`. The first start writes a
random password to `data/initial_admin_password` (or uses `PRG32_ADMIN_PASSWORD`
if you set a long one). Change it on **My account**; the file is then deleted.

Data is stored in `data/` by default. To move it:

```bash
export PRG32_KIT_DATA=/path/to/data
python app.py
```

## Quick start with Docker Compose

```bash
cp examples/deploy/classroom.env .env   # change PRG32_ADMIN_PASSWORD
docker compose up --build
docker compose exec prg32-construction-kit python tools/check_build.py
```

Open <http://127.0.0.1:5090/>. The image includes the RISC-V compiler and the
PRG32 build tools, so **Compile Cartridge** and **Download .prg32** make real
`.prg32` cartridges. The compose file mounts `./data` to `/data`.

## Cartridge builds with Python

The app always generates C. To also build `.prg32` cartridges without Docker,
put a [PRG32](https://github.com/riscv-prg32/PRG32) checkout next to this one,
install it into the kit's environment, and put ESP-IDF 5.4's
`riscv32-esp-elf-gcc` on `PATH`:

```bash
.venv/bin/pip install --no-deps -e ../PRG32
examples/deploy/start-kit.sh   # finds the compiler, checks builds, starts the kit
```

`tools/check_build.py` compiles real cartridges for several students in
several browser windows at once and reports anything missing. Step-by-step
instructions for Docker, macOS, Linux and Windows, plus troubleshooting:
`docs/install_cartridge_build.md`.

Without the toolchain, **Compile Cartridge** still creates a source bundle with
the generated C, project JSON, game IR and manifest.

## Repository layout

```text
app.py                         Flask entrypoint
prg32_construction_kit/        Flask app package, CRUD API, C and assembly generators, packager, publisher
templates/                     Bootstrap/Jinja pages
static/                        PWA assets, JavaScript, CSS, Blockly integration
examples/                      Example Blocks JSON and sprite JSON
examples/games/                Five complete Blocks games
tools/                         Example game and tutorial builders, simulator CLI, runtime and build checks
wasm/                          C interface + build of PRG32-QT's core for the browser (static/wasm/)
docs/                          Setup, API, architecture, Docker, tutorials, how-to guides
tests/                         pytest tests
.github/workflows/tests.yml    GitHub Actions CI and GHCR container delivery
Dockerfile                     Container image (with the PRG32 cartridge toolchain)
docker/                        Container entrypoint
examples/deploy/               Classroom env file, systemd unit, start script
docker-compose.yml             Local persistent deployment
AGENTS.md                      Formal development constraints
LICENSE                        MIT License
```

## Documentation

Start with:

- `docs/setup.md`
- `docs/docker.md`
- `docs/install_cartridge_build.md` (install with cartridge builds switched on)
- `docs/ci_cd.md` (CI checks and published container images)
- `docs/architecture.md`
- `docs/api.md`
- `docs/generated_code.md` (reading the generated C and RISC-V assembly)
- `docs/concurrent_builds.md` (many students building at once)
- `docs/accounts_and_sso.md` (accounts and single sign-on with Cartridge Store)
- `docs/tutorials/01_first_project.md`
- `docs/tutorials/games/README.md` (classic games and slide decks)
- `docs/prg32_feature_coverage.md`

## License

MIT License. See `LICENSE`.
