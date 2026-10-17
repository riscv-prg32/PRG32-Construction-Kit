FROM python:3.14-slim

# --- Cartridge build toolchain ---------------------------------------------------
# With PRG32_TOOLCHAIN=1 (the default) the image can build real .prg32 cartridges:
# it installs the RISC-V compiler used by ESP-IDF 5.4 and the PRG32 build tools.
# Build with --build-arg PRG32_TOOLCHAIN=0 for a smaller image that only makes C
# and source bundles. See docs/install_cartridge_build.md.
ARG PRG32_TOOLCHAIN=1
# PRG32 checkout to build with: a branch, a tag or (best for a class) a commit id.
ARG PRG32_REPO=https://github.com/riscv-prg32/PRG32.git
ARG PRG32_REF=main
# RISC-V GCC release of ESP-IDF 5.4.
ARG RISCV_GCC_VERSION=esp-14.2.0_20241119

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PRG32_KIT_DATA=/data \
    PRG32_KIT_PORT=5090 \
    PRG32_REQUIRE_TOOLCHAIN=$PRG32_TOOLCHAIN \
    PATH=/opt/riscv32-esp-elf/bin:$PATH

# The cartridge builder needs only the Python standard library, so --no-deps
# skips the audio and network packages that other PRG32 commands use.
RUN if [ "$PRG32_TOOLCHAIN" = "1" ]; then \
      set -eux; \
      apt-get update; \
      apt-get install -y --no-install-recommends ca-certificates curl git xz-utils; \
      case "$(dpkg --print-architecture)" in \
        amd64) host=x86_64-linux-gnu ;; \
        arm64) host=aarch64-linux-gnu ;; \
        *) echo "No RISC-V compiler download for $(dpkg --print-architecture)"; exit 1 ;; \
      esac; \
      gcc_release="${RISCV_GCC_VERSION#esp-}"; \
      curl -fsSL "https://github.com/espressif/crosstool-NG/releases/download/${RISCV_GCC_VERSION}/riscv32-esp-elf-${gcc_release}-${host}.tar.xz" \
        | tar -xJ -C /opt; \
      git clone --filter=blob:none "$PRG32_REPO" /opt/PRG32; \
      git -C /opt/PRG32 checkout "$PRG32_REF"; \
      pip install --no-cache-dir --no-deps -e /opt/PRG32; \
      riscv32-esp-elf-gcc --version | head -n 1; \
      python3 -m prg32 cartridge build --help > /dev/null; \
      apt-get purge -y --auto-remove curl git xz-utils; \
      rm -rf /var/lib/apt/lists/*; \
    fi

WORKDIR /app

COPY requirements.txt requirements-production.txt ./
RUN pip install --no-cache-dir -r requirements-production.txt

LABEL org.opencontainers.image.title="PRG32-Construction-Kit" \
      prg32.toolchain="$PRG32_TOOLCHAIN" \
      prg32.ref="$PRG32_REF" \
      prg32.riscv-gcc="$RISCV_GCC_VERSION"

COPY . .
RUN mkdir -p /data && useradd -ms /bin/bash kit && chown -R kit:kit /data /app
USER kit

EXPOSE 5090
# Checks the cartridge build tools at every start (docker/entrypoint.sh), then
# runs the web server.
ENTRYPOINT ["/app/docker/entrypoint.sh"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/.well-known/prg32-construction-kit.json' % os.environ.get('PRG32_KIT_PORT', '5090'), timeout=4)"
# Several workers and threads serve many students at once. Long builds wait for a
# build slot (PRG32_MAX_PARALLEL_BUILDS), so the request timeout is generous.
CMD ["sh", "-c", "exec gunicorn --preload --workers ${PRG32_KIT_WORKERS:-2} --threads ${PRG32_KIT_THREADS:-16} --timeout 600 --bind 0.0.0.0:${PRG32_KIT_PORT:-5090} app:app"]
