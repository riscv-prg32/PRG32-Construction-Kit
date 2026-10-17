#!/bin/sh
# Start PRG32-Construction-Kit inside the Docker image.
#
# Before the web server starts, check that this container can build PRG32
# cartridges (the RISC-V compiler and the PRG32 build tools). The result is
# printed in `docker compose logs`.
#
# PRG32_REQUIRE_TOOLCHAIN=1 (the default in the full image) stops the
# container when the tools are broken, so students never meet a server that
# says "the PRG32 compiler toolchain is not installed". Set it to 0 to start
# anyway and only make C and source bundles.
set -e

if python tools/check_build.py --quick; then
  :
elif [ "${PRG32_REQUIRE_TOOLCHAIN:-0}" = "1" ]; then
  echo "PRG32 cartridge builds do not work in this container, so it will not start."
  echo "Rebuild the image: docker compose build --no-cache  (see docs/install_cartridge_build.md)"
  exit 1
else
  echo "Starting without cartridge builds: students get C and source bundles only."
fi

exec "$@"
