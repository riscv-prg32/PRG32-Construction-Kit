# Container Execution Guide

## Docker Compose

From the repository root:

```bash
cp examples/deploy/classroom.env .env    # then change PRG32_ADMIN_PASSWORD
docker compose up --build
```

Open:

```text
http://127.0.0.1:5090/
```

Stop the service:

```bash
docker compose down
```

The compose file mounts:

```text
./data -> /data
```

That directory stores SQLite data, generated C, packages, uploaded artifacts, and build logs.

The image runs gunicorn (`PRG32_KIT_WORKERS`, default 2, with
`PRG32_KIT_THREADS`, default 16, threads each) so many students can build
at once. `PRG32_MAX_PARALLEL_BUILDS` limits how many compilers run together;
see `concurrent_builds.md`.

SQLite is the convenient single-container default. For a multi-user production
deployment, run PostgreSQL as a separate managed service or Compose service,
install `requirements-production.txt`, and provide:

```yaml
environment:
  DATABASE_URL: postgresql+psycopg://prg32:${PRG32_DB_PASSWORD}@database/prg32_kit
```

Keep generated artifacts on persistent shared storage if the web application
runs with more than one replica. The SQL database stores their metadata, not
the large cartridge and bundle files themselves.

## Manual Docker build and run

```bash
docker build -t prg32-construction-kit .
docker run --rm -it \
  -p 5090:5090 \
  --env-file .env \
  -e PRG32_KIT_DATA=/data \
  -v "$PWD/data:/data" \
  prg32-construction-kit
```

## Connecting to Cartridge Store from Docker

If Cartridge Store runs on the host at port `5080`, the included compose file sets:

```yaml
PRG32_STORE_URL: http://host.docker.internal:5080
```

On Linux, `host.docker.internal` may need extra configuration. A simple classroom option is to run both services in the same Docker Compose network and set `PRG32_STORE_URL` to the service name.

## Cartridge builds in the container

The image installs the RISC-V compiler (ESP-IDF 5.4's `riscv32-esp-elf-gcc`)
and the PRG32 build tools by default, so **Compile Cartridge** and
**Download .prg32** work straight away. Check it:

```bash
docker compose exec prg32-construction-kit python tools/check_build.py
```

The container runs the quick check (`tools/check_build.py --quick`) every
time it starts and stops if cartridge builds are broken; set
`PRG32_REQUIRE_TOOLCHAIN=0` to start anyway with source bundles only.

Build arguments (set them in `.env`; see `examples/deploy/classroom.env`):

| Argument | Default | Meaning |
| --- | --- | --- |
| `PRG32_TOOLCHAIN` | `1` | `0` builds a smaller image without cartridge builds. |
| `PRG32_REF` | `main` | PRG32 branch, tag or commit id. Pin one for a term. |
| `PRG32_REPO` | PRG32 on GitHub | Use your own fork. |
| `RISCV_GCC_VERSION` | `esp-14.2.0_20241119` | Espressif compiler release. |

Rebuild after changing one: `docker compose build --no-cache`.

A running server says "this server cannot compile PRG32 cartridges yet" when
it was started from an older image made before the toolchain was part of it,
or with `PRG32_TOOLCHAIN=0`. `docker compose up` alone keeps that old image, so
rebuild it once (student projects stay in `./data`):

```bash
git pull
docker compose build --no-cache
docker compose up -d
docker compose logs prg32-construction-kit
```

From any computer, the discovery document says whether a server can build:

```bash
curl http://SERVER:5090/.well-known/prg32-construction-kit.json
```

Look for `"cartridge_builds": {"available": true, ...}`. The container's
health check uses the same address.

The kit appends these arguments to the build command:

```text
<source.c> --portable --architecture <esp32c6|qemu> --cart-ram-kib 64 --entry-prefix <prefix> --name <name> --out <file.prg32>
```

Change `PRG32_CART_RAM_KIB` only when the target PRG32 firmware uses a different
cartridge RAM profile. The full guide, with troubleshooting, is
`install_cartridge_build.md`.
