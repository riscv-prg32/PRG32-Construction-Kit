# Installing Cartridge Builds

When students click **Compile Cartridge** or **Download .prg32**, the server
turns their generated C into a PRG32 cartridge. To do that it needs two
tools:

1. **The RISC-V compiler** `riscv32-esp-elf-gcc` (the one in ESP-IDF 5.4).
2. **The PRG32 build tools** (`python -m prg32 cartridge build`) from the
   [PRG32 repository](https://github.com/riscv-prg32/PRG32).

If either one is missing, students see this message in the editor:

> The source bundle is ready, but this server cannot compile PRG32 cartridges yet.

Their C is still generated and saved, but no `.prg32` file is made.

The easiest fix is the Docker image. It already contains both tools, so you
don't install anything else.

## Recommended: the Docker image

You need Docker (Docker Desktop on macOS and Windows, Docker Engine on
Linux) and the PRG32-Construction-Kit folder.

```bash
cd PRG32-Construction-Kit
cp examples/deploy/classroom.env .env      # then edit PRG32_ADMIN_PASSWORD
docker compose up -d --build
```

That's it. `--build` creates the image. The first build downloads the RISC-V
compiler (about 150 MB) and the PRG32 tools, so it takes a few minutes. Later
builds reuse them.

### Check that it works

Every time the container starts, it checks the build tools before the web
server opens. Read the result in the logs:

```bash
docker compose logs prg32-construction-kit
```

```text
  OK    build command runs: /usr/local/bin/python3 -m prg32 cartridge build
  OK    RISC-V compiler on PATH: /opt/riscv32-esp-elf/bin/riscv32-esp-elf-gcc
  OK    build sandbox: bubblewrap (no network, read-only SDK, private build folder)
```

Every compile runs isolated in a bubblewrap sandbox (`build_sandbox.md`). The
compose file starts the container with the kit's seccomp profile
(`docker/seccomp-kit.json`) so the sandbox can work; without it the check
fails and the container does not start.

If a line says `FAIL`, the container stops instead of starting a server
that can't build cartridges. See [Troubleshooting](#troubleshooting).

Before a lesson, test a whole class compiling at the same moment (this uses
throwaway data, so real projects are not touched). It also builds one small game
written each way: Blocks (as C and as assembly), Advanced C and handwritten
assembly. With Node.js installed, each one is then run for 30 frames in the
browser core, and `--evidence FILE` saves their SHA-256:

```bash
docker compose exec prg32-construction-kit python tools/check_build.py --students 10 --windows 2
```

You can also ask a running server from any computer. Look for
`"cartridge_builds": {"available": true, ...}`:

```bash
curl http://SERVER:5090/.well-known/prg32-construction-kit.json
```

### Updating a server that says the toolchain is missing

A server started from an **older** image (made before the toolchain was part
of it, or built with `PRG32_TOOLCHAIN=0`) keeps that image until you rebuild
it. `docker compose up` alone doesn't rebuild. Do this once:

```bash
git pull
docker compose build --no-cache
docker compose up -d
docker compose logs prg32-construction-kit
```

Student projects are safe: they live in `./data`, outside the image.

### Image options

Set these in `.env` (or with `--build-arg` for `docker build`), then rebuild.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PRG32_TOOLCHAIN` | `1` | `1` puts the compiler and PRG32 tools in the image. `0` makes a smaller image that only makes C and source bundles. |
| `PRG32_REF` | `main` | PRG32 version to build with. Use a tag or a commit id so cartridges don't change in the middle of a term. |
| `PRG32_REPO` | PRG32 on GitHub | Another copy of PRG32, for example a school fork. |
| `RISCV_GCC_VERSION` | `esp-14.2.0_20241119` | RISC-V compiler release (the one in ESP-IDF 5.4). |
| `PRG32_REQUIRE_TOOLCHAIN` | same as `PRG32_TOOLCHAIN` | Runtime setting. `1` stops the container when the build tools don't work; `0` starts anyway, without cartridge builds. |

The image works on `amd64` (most servers and PCs) and `arm64` (Apple Silicon
Macs, Raspberry Pi 4/5 with a 64-bit system). To see how an image was built:

```bash
docker image inspect prg32-construction-kit:latest --format '{{json .Config.Labels}}'
```

### Without Docker Compose

```bash
docker build -t prg32-construction-kit .
docker run -d --name prg32-kit -p 5090:5090 -v "$PWD/data:/data" \
  --security-opt seccomp="$PWD/docker/seccomp-kit.json" \
  --security-opt no-new-privileges:true --cap-drop ALL \
  prg32-construction-kit
docker logs prg32-kit
```

## Without Docker

Use this on a teacher laptop, or on a server where Docker isn't allowed.
The kit and the PRG32 tools share one Python virtual environment.

```text
riscv-prg32/
  PRG32/                      git clone https://github.com/riscv-prg32/PRG32.git
  PRG32-Construction-Kit/
```

```bash
cd PRG32-Construction-Kit
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
pip install --no-deps -e ../PRG32   # the cartridge builder needs no extra packages
```

The Docker image installs the same packages pinned with hashes from
`requirements.lock` (`dependencies.md`).

Then put the RISC-V compiler on `PATH`. Pick one:

- **ESP-IDF 5.4 is installed:** it is already in
  `~/.espressif/tools/riscv32-esp-elf/esp-14.2.0_*/riscv32-esp-elf/bin`.
  `examples/deploy/start-kit.sh` finds it there.
- **Compiler only:** download `riscv32-esp-elf-14.2.0_20241119-<your system>.tar.xz`
  from the [Espressif crosstool-NG releases](https://github.com/espressif/crosstool-NG/releases/tag/esp-14.2.0_20241119),
  unpack it, and add its `riscv32-esp-elf/bin` folder to `PATH`.

Check, then start:

```bash
python tools/check_build.py --quick
python app.py
```

`examples/deploy/start-kit.sh` does all of this on macOS and Linux.

### Which compiler file to download

| Computer | File |
| --- | --- |
| Mac with Apple silicon (M1 and later) | `riscv32-esp-elf-14.2.0_20241119-aarch64-apple-darwin.tar.xz` |
| Mac with Intel | `riscv32-esp-elf-14.2.0_20241119-x86_64-apple-darwin.tar.xz` |
| Linux, Intel/AMD | `riscv32-esp-elf-14.2.0_20241119-x86_64-linux-gnu.tar.xz` |
| Linux, ARM (Raspberry Pi 5) | `riscv32-esp-elf-14.2.0_20241119-aarch64-linux-gnu.tar.xz` |

Unpacking it into the folder ESP-IDF uses lets `examples/deploy/start-kit.sh`
find it without any setting. For example, on a Mac with Apple silicon:

```bash
mkdir -p ~/.espressif/tools/riscv32-esp-elf/esp-14.2.0_20241119
curl -L https://github.com/espressif/crosstool-NG/releases/download/esp-14.2.0_20241119/riscv32-esp-elf-14.2.0_20241119-aarch64-apple-darwin.tar.xz | tar -xJ -C ~/.espressif/tools/riscv32-esp-elf/esp-14.2.0_20241119
examples/deploy/start-kit.sh --check
```

If the compiler is somewhere else: `RISCV_GCC_BIN=/path/to/riscv32-esp-elf/bin examples/deploy/start-kit.sh`.
Personal settings (admin password, parallel builds) go in
`examples/deploy/classroom.local.env`, which the start script reads and git ignores.

The kit runs the builder with **its own Python** (the one in `.venv`), so
builds find the PRG32 tools even when the virtual environment is not
activated, for example when an IDE or a service starts `.venv/bin/python app.py`.

### Windows

The PRG32 tools are used on macOS and Linux. On Windows, pick one:

- **Docker Desktop**: follow the Docker steps above in PowerShell, with
  `copy examples\deploy\classroom.env .env` instead of `cp`.
- **WSL 2 (Ubuntu)**: in the Ubuntu terminal, follow *Without Docker* with the
  `x86_64-linux-gnu` compiler. Students on the same network open
  `http://<windows-computer-ip>:5090/`.

### Linux server with systemd

`examples/deploy/prg32-kit.service` runs the kit with gunicorn. It expects the
kit in `/opt/prg32/PRG32-Construction-Kit`, its `.venv` as above, and the
compiler unpacked in `/opt/riscv32-esp-elf`. Edit the paths if yours differ.

## Many students, many windows

Nothing to set up; this is built in. The full check
(`python tools/check_build.py --students 4 --windows 2`, without `--quick`)
proves it on your server: it makes pretend student accounts, opens several
"browser windows" for each, lets them all compile for ESP32-C6 and QEMU at the
same moment, then opens every cartridge to check it holds *that* student's
game and that a classmate gets "not found" when downloading it.

- **Every build has its own folder** (`data/builds/<build id>/`) and its own
  temporary folder inside it, removed afterwards. Two builds never share a
  file, even for the same project in two windows.
- **Downloads go by build and by owner.** Each download button links to the
  cartridge of that build; only its owner (or an admin) can download it.
- **A stale window can't build an old version.** If the project was saved in
  another window after this one saved, the build stops and says so.
- **A window opened as another user is stopped.** All windows of one browser
  share one sign-in. If someone signs in as a different user in another
  window, the old window shows a yellow banner, *"Somebody signed in as a
  different user in another window"*, and refuses to save or compile until it
  is reloaded. To be two users at once, use two browsers or a private window.
- **Shared computers stay private.** The installable app's offline cache keeps
  only scripts, styles and icons, never pages, projects or downloads.
- **A waiting line keeps the server healthy.** At most
  `PRG32_MAX_PARALLEL_BUILDS` compilers run at once; the rest wait their turn.

How big a server:

| Class | `PRG32_MAX_PARALLEL_BUILDS` | `PRG32_KIT_WORKERS` x `PRG32_KIT_THREADS` |
| --- | --- | --- |
| up to 15 students, 2-core laptop | 2 | `python app.py` is fine |
| up to 30 students, 4 cores | 4 | 2 x 16 (Docker default) |
| more than 30 students, 8 cores | 8 | 4 x 16 |

A Blocks game compiles in about a second per target. Keep workers x threads
above the number of students who compile at the same moment, because a build
waiting in line keeps one thread busy. Run
`python tools/check_build.py --students 30 --windows 1` to see how your server
copes with the whole class clicking at once. Details: `concurrent_builds.md`.

## Troubleshooting

| What you see | What to do |
| --- | --- |
| Editor: "this server cannot compile PRG32 cartridges yet" | Rebuild the image: see [Updating a server](#updating-a-server-that-says-the-toolchain-is-missing). Without Docker, run `python tools/check_build.py --quick`. |
| `FAIL build command runs ... No module named prg32` | The PRG32 tools are not installed in the Python that runs the kit. Docker: rebuild with `PRG32_TOOLCHAIN=1`. Without Docker: `pip install --no-deps -e ../PRG32` in the kit's `.venv`. |
| `FAIL RISC-V compiler on PATH` | Add the compiler's `bin` folder to `PATH` for the server process (systemd: the `Environment=PATH=` line). |
| `docker compose build` fails with "No RISC-V compiler download" | The computer is not amd64 or arm64. Use another computer or `PRG32_TOOLCHAIN=0`. |
| `FAIL build sandbox: ... bubblewrap does not work` | The container was started without `docker/seccomp-kit.json` (see `build_sandbox.md`). On Ubuntu 24.04 and other AppArmor hosts, load `docker/apparmor/prg32-kit` and start the container with `--security-opt apparmor=prg32-kit` (*AppArmor hosts* there). |
| `507 build_disk_full` when compiling | All builds together reached `PRG32_BUILD_ROOT_MAX_MB`. Old builds go with retention (`PRG32_KIT_KEEP_BUILDS`, *Retention* in `storage.md`); raise the budget if the disk allows. |
| The container restarts again and again | The start-up check failed. Read `docker compose logs`, or set `PRG32_REQUIRE_TOOLCHAIN=0` to start without builds while you fix it. |
| "All N cartridge build slots are busy" | The server is working; see `concurrent_builds.md`. |
| Debug Log shows a C error | The compiler works; the game's C has a problem. See `cartridge_build.md`. |
| "Somebody signed in as a different user in another window" | Reload that window. Use a second browser or a private window to be two users at once. |
| "This project was changed in another browser window" | Reload the project, then compile again. |
| "Build command timed out" | The server is overloaded: lower `PRG32_MAX_PARALLEL_BUILDS` or raise `PRG32_BUILD_TIMEOUT`. |
| `cartridge needs N bytes, runtime has M` | The game is too big for the firmware's cartridge RAM: make it smaller, or set `PRG32_CART_RAM_KIB` to your firmware's value. |

## Settings for builds

These work with and without Docker. Full list: `setup.md`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PRG32_BUILD_COMMAND` | the kit's Python `-m prg32 cartridge build` | Command that builds one cartridge. |
| `PRG32_CART_RAM_KIB` | `64` | Cartridge RAM of your PRG32 firmware profile (`32` for the classroom profile). |
| `PRG32_MAX_PARALLEL_BUILDS` | CPU cores (`4` in `docker-compose.yml`) | Compilers running at the same time. |
| `PRG32_BUILD_QUEUE_TIMEOUT` | `180` | Seconds a build waits for a free compiler. |
| `PRG32_BUILD_TIMEOUT` | `120` | Seconds one compiler run may take. |
| `PRG32_BUILD_SANDBOX` | `auto` (`bwrap` in the Docker image) | `bwrap` = isolate every compile (required), `rlimit` = limits only, not isolated (a trusted laptop), `auto` = bwrap when it works, else rlimit (never on a production server). See `build_sandbox.md`. |
| `PRG32_BUILD_MEMORY_MB` | `1536` | Memory one compiler run may use. |
| `PRG32_BUILD_MAX_PROCESSES` | `128` | Extra processes one build may start. |
| `PRG32_BUILD_RO_PATHS` | empty | Extra read-only folders a custom build command needs inside the sandbox (`:`-separated). |
