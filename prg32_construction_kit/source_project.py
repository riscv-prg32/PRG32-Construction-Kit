"""Explicit advanced C projects for cartridge APIs beyond the Blocks toolbox."""

from __future__ import annotations

import re

from .generator import c_identifier

_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]\s*$')
_ALLOWED_HEADERS = {"prg32.h", "prg32_audio.h", "stdint.h", "stddef.h", "stdbool.h"}
FEATURES = {"audio", "wifi", "multiplayer", "metrics", "audio_plus", "keyboard", "tilemap", "platformer", "sprites"}
_LIFECYCLE = r'\bvoid\s+({prefix}_(?:init|update|draw))\s*\(\s*void\s*\)\s*\{{'


def validate_c_source(source: str, title: str) -> str:
    """Check the small, explicit source contract before invoking the toolchain.

    This does not replace the C compiler or make untrusted native compilation a
    sandbox. It prevents accidental host-file includes and mismatched entry names.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("C source is empty")
    if len(source.encode("utf-8")) > 256 * 1024 or "\x00" in source:
        raise ValueError("C source exceeds 256 KiB or contains NUL bytes")
    for line in source.splitlines():
        if line.lstrip().startswith("#"):
            match = _INCLUDE.fullmatch(line)
            if match and match.group(1) in _ALLOWED_HEADERS:
                continue
            if re.match(r'^\s*#\s*(?:define|ifndef|ifdef|if|elif|else|endif|undef)\b', line):
                continue
            raise ValueError("Only approved PRG32/standard headers and basic conditional or define directives are supported")
    prefix = c_identifier(title, "prg32_game")
    found = set(re.findall(_LIFECYCLE.format(prefix=re.escape(prefix)), source))
    required = {f"{prefix}_{phase}" for phase in ("init", "update", "draw")}
    if found != required:
        raise ValueError(f"C source must define void {prefix}_init/update/draw(void)")
    return prefix


def validate_features(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in FEATURES for item in value):
        raise ValueError("Features must be a list of current PRG32 feature names")
    return list(dict.fromkeys(value))
