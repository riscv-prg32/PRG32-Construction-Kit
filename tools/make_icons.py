#!/usr/bin/env python3
"""Make the kit's logo and app icons from the official PRG32 logo.

    python3 tools/make_icons.py [path/to/PRG32/assets/prg32_logo.png]

The logo (320x200, the PRG32 firmware's own assets/prg32_logo.png) is copied unchanged to
static/img/prg32-logo.png, for the menu bar. The square icons for the browser tab, the home
screen and the installed app (static/img/prg32-icon-<size>.png) put the whole logo in the
middle of a black square, the logo's own background. The same logo always gives the same files.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOGO = ROOT.parent / "PRG32" / "assets" / "prg32_logo.png"
SIZES = (32, 180, 192, 512)


def main() -> int:
    logo_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_LOGO
    logo = Image.open(logo_path).convert("RGB")
    out = ROOT / "static" / "img"
    shutil.copyfile(logo_path, out / "prg32-logo.png")
    for size in SIZES:
        square = Image.new("RGB", (size, size), (0, 0, 0))
        width = size
        height = round(logo.height * size / logo.width)
        scaled = logo.resize((width, height), Image.LANCZOS)
        square.paste(scaled, (0, (size - height) // 2))
        square.save(out / f"prg32-icon-{size}.png", optimize=True)
    print(f"Wrote static/img/prg32-logo.png and prg32-icon-{{{','.join(map(str, SIZES))}}}.png from {logo_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
