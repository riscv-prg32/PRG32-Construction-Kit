#!/usr/bin/env bash
# Start PRG32-Construction-Kit with real cartridge builds on macOS or Linux.
#
#   examples/deploy/start-kit.sh            start the server
#   examples/deploy/start-kit.sh --check    only run the build check
#
# Expects this layout (see docs/install_cartridge_build.md):
#   PRG32-Construction-Kit/.venv     the kit's virtual environment, with
#                                    `pip install -e ../PRG32 --no-deps` done
#   ~/.espressif/tools/riscv32-esp-elf/<version>/riscv32-esp-elf/bin
#                                    the RISC-V compiler (ESP-IDF 5.4 or the
#                                    plain download); or set RISCV_GCC_BIN.
set -euo pipefail

KIT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$KIT_DIR"

if [ -z "${RISCV_GCC_BIN:-}" ]; then
  RISCV_GCC_BIN="$(ls -d "$HOME"/.espressif/tools/riscv32-esp-elf/esp-14.2.0_*/riscv32-esp-elf/bin 2>/dev/null | tail -n 1 || true)"
fi
if [ -n "$RISCV_GCC_BIN" ]; then
  export PATH="$RISCV_GCC_BIN:$PATH"
fi

if [ -f examples/deploy/classroom.local.env ]; then
  set -a; . examples/deploy/classroom.local.env; set +a
fi

PYTHON="$KIT_DIR/.venv/bin/python"
[ -x "$PYTHON" ] || PYTHON="$(command -v python3)"

"$PYTHON" tools/check_build.py --students 2 --windows 2
if [ "${1:-}" = "--check" ]; then
  exit 0
fi
exec "$PYTHON" app.py
