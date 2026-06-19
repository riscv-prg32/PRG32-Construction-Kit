# Container Execution Guide

## Docker Compose

From the repository root:

```bash
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

## Manual Docker build and run

```bash
docker build -t prg32-construction-kit .
docker run --rm -it \
  -p 5090:5090 \
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

## Adding the PRG32 build toolchain

The base Dockerfile installs only the web app dependencies. To build `.prg32` files inside the container, extend the image and install the PRG32 SDK/tooling. The important runtime check is:

```bash
docker compose exec prg32-construction-kit python3 -m prg32 build --help
```

If your build command is different, set:

```yaml
environment:
  PRG32_BUILD_COMMAND: /path/to/prg32-cart
```

The app appends these arguments:

```text
<source.c> --portable --entry-prefix <prefix> --name <name> --out <file.prg32>
```
