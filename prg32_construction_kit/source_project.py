"""Explicit advanced C projects for cartridge APIs beyond the Blocks toolbox."""

from __future__ import annotations

import re

from .generator import c_identifier

_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]\s*$')
_ALLOWED_HEADERS = {"prg32.h", "prg32_audio.h", "stdint.h", "stddef.h", "stdbool.h"}
FEATURES = {"audio", "wifi", "multiplayer", "metrics", "audio_plus", "keyboard", "tilemap", "platformer", "sprites"}
_LIFECYCLE = r'\bvoid\s+({prefix}_(?:init|update|draw))\s*\(\s*void\s*\)\s*\{{'
_DIRECTIVE_START = re.compile(r"^\s*(?:#|%:)")
# Words that let C code reach the host at compile time (inline assembly can
# `.incbin` any file) or build forbidden words out of pieces.
_FORBIDDEN_WORDS = re.compile(r"\b(?:asm|__asm|__asm__|_Pragma|__has_include|__has_include_next|__has_embed)\b")


def _without_comments(source: str) -> str:
    """Remove comments the way the C preprocessor does (each becomes one space).

    Line continuations are joined first, string and character literals are kept,
    so a comment can no longer hide the start of a directive.
    """
    text = re.sub(r"\\\r?\n", "", source)
    out: list[str] = []
    i = 0
    quote = ""
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                i += 2
                continue
            if ch == quote or ch == "\n":
                quote = ""
            i += 1
        elif ch in "\"'":
            quote = ch
            out.append(ch)
            i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError("C source has a comment that never ends")
            out.append(" ")
            i = end + 2
        elif text.startswith("//", i):
            end = text.find("\n", i)
            out.append(" ")
            i = len(text) if end < 0 else end
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def _without_strings(code: str) -> str:
    return re.sub(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'', '""', code)


def validate_c_source(source: str, title: str) -> str:
    """Check the small, explicit source contract before invoking the toolchain.

    This does not replace the C compiler or make untrusted native compilation a
    sandbox. It prevents host-file includes, inline assembly and mismatched
    entry names.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError("C source is empty")
    if len(source.encode("utf-8")) > 256 * 1024 or "\x00" in source:
        raise ValueError("C source exceeds 256 KiB or contains NUL bytes")
    if "??=" in source or "??/" in source:
        raise ValueError("C trigraphs (??= and ??/) are not supported")
    code = _without_comments(source)
    for line in code.splitlines():
        if _DIRECTIVE_START.match(line):
            directive = re.sub(r"^\s*%:", "#", line)
            match = _INCLUDE.fullmatch(directive)
            if match and match.group(1) in _ALLOWED_HEADERS:
                continue
            if re.match(r'^\s*#\s*(?:define|ifndef|ifdef|if|elif|else|endif|undef)\b', directive):
                continue
            raise ValueError("Only approved PRG32/standard headers and basic conditional or define directives are supported")
    bare = _without_strings(code)
    if "##" in bare or "%:%:" in bare:
        raise ValueError("The ## token-pasting operator is not supported")
    forbidden = _FORBIDDEN_WORDS.search(bare)
    if forbidden:
        raise ValueError(f"'{forbidden.group(0)}' is not supported in PRG32 cartridge C")
    prefix = c_identifier(title, "prg32_game")
    found = set(re.findall(_LIFECYCLE.format(prefix=re.escape(prefix)), bare))
    required = {f"{prefix}_{phase}" for phase in ("init", "update", "draw")}
    if found != required:
        raise ValueError(f"C source must define void {prefix}_init/update/draw(void)")
    return prefix


def validate_features(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in FEATURES for item in value):
        raise ValueError("Features must be a list of current PRG32 feature names")
    return list(dict.fromkeys(value))
