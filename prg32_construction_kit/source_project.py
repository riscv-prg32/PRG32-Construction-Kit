"""Explicit advanced C projects for cartridge APIs beyond the Blocks toolbox."""

from __future__ import annotations

import re

from .generator import c_identifier
from .messages import text as say

_INCLUDE = re.compile(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]\s*$')
# prg32_assets.h is not a file: the kit writes the project's art in its place (project_assets.py).
_ALLOWED_HEADERS = {"prg32.h", "prg32_audio.h", "prg32_assets.h", "stdint.h", "stddef.h", "stdbool.h"}
FEATURES = {"audio", "wifi", "multiplayer", "metrics", "audio_plus", "keyboard", "tilemap", "platformer", "sprites"}
_LIFECYCLE = r'\bvoid\s+({prefix}_(?:init|update|draw))\s*\(\s*void\s*\)\s*\{{'
_DIRECTIVE_START = re.compile(r"^\s*(?:#|%:)")
# Words that let C code reach the host at compile time (inline assembly can
# `.incbin` any file) or build forbidden words out of pieces.
_FORBIDDEN_WORDS = re.compile(r"\b(?:asm|__asm|__asm__|_Pragma|__has_include|__has_include_next|__has_embed)\b")
# The buzzer is obsolete (contracts/prg32-audio-contract-1.json, "legacy_buzzer"): PRG32 games use
# the eight-voice audio engine. The SDK still lists these functions, so they are refused here, by
# name, with what to use instead. The IDE's language index takes the same list.
OBSOLETE_FUNCTIONS = {
    "prg32_buzzer_tone": "prg32_audio_note_on_pan (a voice playing an instrument), or an AudioStudio sound effect",
    "prg32_buzzer_play_notes": "prg32_audio_play_track with an AudioStudio soundtrack",
    "prg32_buzzer_sample_u8": "prg32_audio_play_sample_pan with a sample from the cartridge's audio block",
}
OBSOLETE_TYPES = {"prg32_note_t": "prg32_midi_note_t (prg32_audio_notes) or an AudioStudio soundtrack"}
_OBSOLETE = re.compile(r"\b(prg32_buzzer_\w*|prg32_note_t|PRG32_PIN_BUZZER)\b")


def _refuse_obsolete(code: str, where=lambda _offset: "") -> None:
    found = _OBSOLETE.search(code)
    if found:
        name = found.group(1)
        instead = OBSOLETE_FUNCTIONS.get(name) or OBSOLETE_TYPES.get(name) or "the PRG32 audio engine (prg32_audio_*)"
        raise ValueError(say("source", "{value}{name} belongs to the old PRG32 buzzer, which is no longer supported. Use {instead}.", value=where(found.start()), name=name, instead=instead))


def _without_comments(source: str) -> str:
    """Remove comments the way the C preprocessor does (each becomes one space).

    Line continuations are joined first, string and character literals are kept,
    so a comment can no longer hide the start of a directive.
    """
    return _without_comments_mapped(source)[0]


def _without_comments_mapped(source: str) -> tuple[str, list[int]]:
    """_without_comments, plus the offset in ``source`` that each output character came from.

    The IDE shows problems on the line the student wrote, even when a comment
    spanning several lines or a line continuation moved the text.
    """
    text_chars: list[str] = []
    text_origin: list[int] = []
    i = 0
    while i < len(source):  # join line continuations: backslash-newline (or backslash-CR-LF)
        if source[i] == "\\" and source.startswith("\n", i + 1):
            i += 2
        elif source[i] == "\\" and source.startswith("\r\n", i + 1):
            i += 3
        else:
            text_chars.append(source[i])
            text_origin.append(i)
            i += 1
    text = "".join(text_chars)
    out: list[str] = []
    origin: list[int] = []
    i = 0
    quote = ""
    while i < len(text):
        ch = text[i]
        if quote:
            out.append(ch)
            origin.append(text_origin[i])
            if ch == "\\" and i + 1 < len(text):
                out.append(text[i + 1])
                origin.append(text_origin[i + 1])
                i += 2
                continue
            if ch == quote or ch == "\n":
                quote = ""
            i += 1
        elif ch in "\"'":
            quote = ch
            out.append(ch)
            origin.append(text_origin[i])
            i += 1
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise ValueError(say("source", "C source has a comment that never ends"))
            out.append(" ")
            origin.append(text_origin[i])
            i = end + 2
        elif text.startswith("//", i):
            end = text.find("\n", i)
            out.append(" ")
            origin.append(text_origin[i])
            i = len(text) if end < 0 else end
        else:
            out.append(ch)
            origin.append(text_origin[i])
            i += 1
    return "".join(out), origin


def _source_lines(source: str, code: str, origin: list[int]) -> list[int]:
    """The line of ``source`` on which each of ``code.splitlines()`` starts."""
    lines, offset = [], 0
    for line in code.splitlines(keepends=True):
        start = origin[offset] if offset < len(origin) else len(source)
        lines.append(source.count("\n", 0, start) + 1)
        offset += len(line)
    return lines


_STRING = re.compile(r'"(?:\\.|[^"\\\n])*"|\'(?:\\.|[^\'\\\n])*\'')


def _without_strings(code: str) -> str:
    return _STRING.sub('""', code)


def _without_strings_mapped(code: str, origin: list[int]) -> tuple[str, list[int]]:
    """_without_strings, carrying the source offset of every character along."""
    out, mapped, last = [], [], 0
    for match in _STRING.finditer(code):
        out.append(code[last:match.start()])
        mapped.extend(origin[last:match.start()])
        out.append('""')
        mapped.extend([origin[match.start()], origin[match.end() - 1]])
        last = match.end()
    out.append(code[last:])
    mapped.extend(origin[last:])
    return "".join(out), mapped


def validate_c_source(source: str, title: str) -> str:
    """Check the small, explicit source contract before invoking the toolchain.

    This does not replace the C compiler or make untrusted native compilation a
    sandbox. It prevents host-file includes, inline assembly and mismatched
    entry names.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError(say("source", "C source is empty"))
    if len(source.encode("utf-8")) > 256 * 1024 or "\x00" in source:
        raise ValueError(say("source", "C source exceeds 256 KiB or contains NUL bytes"))
    if "??=" in source or "??/" in source:
        raise ValueError(say("source", "C trigraphs (??= and ??/) are not supported"))
    code = _without_comments(source)
    for line in code.splitlines():
        if _DIRECTIVE_START.match(line):
            directive = re.sub(r"^\s*%:", "#", line)
            match = _INCLUDE.fullmatch(directive)
            if match and match.group(1) in _ALLOWED_HEADERS:
                continue
            if re.match(r'^\s*#\s*(?:define|ifndef|ifdef|if|elif|else|endif|undef)\b', directive):
                continue
            raise ValueError(say("source", "Only approved PRG32/standard headers and basic conditional or define directives are supported"))
    bare = _without_strings(code)
    if "##" in bare or "%:%:" in bare:
        raise ValueError(say("source", "The ## token-pasting operator is not supported"))
    forbidden = _FORBIDDEN_WORDS.search(bare)
    if forbidden:
        raise ValueError(say("source", "'{value}' is not supported in PRG32 cartridge C", value=forbidden.group(0)))
    _refuse_obsolete(bare)
    prefix = c_identifier(title, "prg32_game")
    found = set(re.findall(_LIFECYCLE.format(prefix=re.escape(prefix)), bare))
    required = {f"{prefix}_{phase}" for phase in ("init", "update", "draw")}
    if found != required:
        raise ValueError(say("source", "C source must define void {prefix}_init/update/draw(void)", prefix=prefix))
    return prefix


def validate_features(value: object) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in FEATURES for item in value):
        raise ValueError(say("source", "Features must be a list of current PRG32 feature names"))
    return list(dict.fromkeys(value))


# --- handwritten RISC-V assembly (docs/adr/0004-handwritten-assembly-mode.md) ---
#
# A .S file goes through the C preprocessor and then the GNU assembler. Both
# can read files on the server (#include, .include, .incbin), so only the
# directives below are allowed. Everything else on a line is an instruction,
# which the assembler checks itself.
ALLOWED_ASM_DIRECTIVES = {
    ".option",                                              # .option norelax, ...
    ".section", ".text", ".data", ".bss", ".rodata",        # where the bytes go
    ".globl", ".global", ".local", ".type", ".size",        # symbol visibility and debug info
    ".balign", ".align", ".p2align",                        # alignment
    ".word", ".half", ".short", ".byte", ".2byte", ".4byte",  # numbers
    ".zero", ".space", ".skip",                             # reserved bytes
    ".ascii", ".asciz", ".string",                          # text
    ".equ", ".set", ".equiv",                               # named constants
}
_ASM_SECTION = re.compile(r"^\.(?:text|data|bss|rodata)(?:\.[A-Za-z0-9_.]+)?$")
_ASM_LABEL = re.compile(r"^\s*(?:[A-Za-z_.$][\w.$]*|\d+)\s*:")
_ASM_DEFINE = re.compile(r"^\s*#\s*define\s+[A-Za-z_]\w*(?:\s+[\w\s+\-*/%()<>&|^~]*)?$")
_ASM_CONDITIONAL = re.compile(r"^\s*#\s*(?:ifndef|ifdef|if|elif|else|endif|undef)\b")
# Every directive the C preprocessor knows. A full-line "# text" whose first
# word is not one of these is an ordinary assembly comment.
_CPP_DIRECTIVES = {"define", "undef", "if", "ifdef", "ifndef", "elif", "elifdef", "elifndef", "else", "endif",
                   "include", "include_next", "import", "embed", "line", "pragma", "error", "warning", "ident",
                   "sccs", "assert", "unassert"}
# Words that read a file on the server, however they are spelled or hidden in a macro.
_ASM_FILE_WORDS = re.compile(r"incbin|include|__has_include|_Pragma", re.IGNORECASE)


def _asm_statements(line: str) -> list[str]:
    """Split one source line into statements: ';' separates them, '#' starts a comment."""
    return [part.strip() for part in line.split("#", 1)[0].split(";") if part.strip()]


def validate_asm_source(source: str, title: str) -> str:
    """Check handwritten assembly before the PRG32 builder assembles it.

    Like validate_c_source, this is a guard against reading server files and
    against wrong entry names; it is not an OS sandbox.
    """
    if not isinstance(source, str) or not source.strip():
        raise ValueError(say("source", "Assembly source is empty"))
    if len(source.encode("utf-8")) > 256 * 1024 or "\x00" in source:
        raise ValueError(say("source", "Assembly source exceeds 256 KiB or contains NUL bytes"))
    if "??=" in source or "??/" in source:
        raise ValueError(say("source", "Trigraphs (??= and ??/) are not supported"))
    # The one include allowed: #include "prg32_assets.S" on a line of its own. It names no file:
    # the kit writes the project's art in its place before the assembler runs (project_assets.py),
    # so it is blanked here and every other include is still refused below.
    from .project_assets import blank_include
    source = blank_include(source)
    bare, origin = _without_strings_mapped(*_without_comments_mapped(source))
    source_line = _source_lines(source, bare, origin)  # the line the student sees, for each line of bare
    # After an instruction '#' starts a comment; a line that starts with '#' is a preprocessor line.
    code = "\n".join(line if _DIRECTIVE_START.match(line) else line.split("#", 1)[0] for line in bare.splitlines())
    found = _ASM_FILE_WORDS.search(code)
    if found:
        raise ValueError(say("source", "'{value}' is not allowed in PRG32 cartridge assembly: it could read files on the server", value=found.group(0)))
    lines = bare.splitlines()
    _refuse_obsolete("\n".join(lines), lambda offset: f"Line {source_line[bare[:offset].count(chr(10))]}: ")
    for index, line in enumerate(bare.splitlines()):
        number = source_line[index]
        if _DIRECTIVE_START.match(line):
            directive = re.sub(r"^\s*%:", "#", line)
            word = re.match(r"^\s*#\s*(\w*)", directive).group(1)
            if _ASM_CONDITIONAL.match(directive):
                continue
            if _ASM_DEFINE.match(directive):
                continue  # only "#define NAME number-expression": no macros with arguments
            if word not in _CPP_DIRECTIVES:
                continue  # "# move the ball": a comment line, the preprocessor leaves it alone
            raise ValueError(say("source", "Line {number}: only '#define NAME value' and #if/#ifdef/#else/#endif are allowed as preprocessor lines", number=number))
        for statement in _asm_statements(line):
            while _ASM_LABEL.match(statement):
                statement = _ASM_LABEL.sub("", statement, count=1).strip()
            if not statement.startswith("."):
                continue
            name, _, rest = statement.partition(" ")
            name = name.split("\t")[0].lower()
            if name not in ALLOWED_ASM_DIRECTIVES:
                raise ValueError(f"Line {number}: the directive {name} is not allowed. Allowed: "
                                 + ", ".join(sorted(ALLOWED_ASM_DIRECTIVES)))
            if name == ".section":
                section = rest.split(",")[0].strip()
                if not _ASM_SECTION.match(section):
                    raise ValueError(say("source", "Line {number}: use .text, .rodata, .data or .bss sections, not {section}", number=number, section=repr(section)))
    prefix = c_identifier(title, "prg32_game")
    for phase in ("init", "update", "draw"):
        name = re.escape(f"{prefix}_{phase}")
        if not re.search(rf"^\s*{name}\s*:", bare, re.MULTILINE):
            raise ValueError(say("source", "Assembly source must define the label {prefix}_{phase}:", prefix=prefix, phase=phase))
        if not re.search(rf"^\s*\.glob(?:a)?l\s+{name}\s*(?:[#;]|$)", bare, re.MULTILINE | re.IGNORECASE):
            raise ValueError(say("source", "Assembly source must make {prefix}_{phase} visible with .globl {prefix}_{phase}", prefix=prefix, phase=phase))
    return prefix
