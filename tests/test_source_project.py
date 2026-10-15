from __future__ import annotations

import pytest

from prg32_construction_kit.source_project import validate_c_source

LIFECYCLE = "void game_init(void) {}\nvoid game_update(void) {}\nvoid game_draw(void) {}\n"


def test_valid_source_is_accepted():
    source = '#include "prg32.h"\n/* a "#include" in a comment is fine */\nstatic const char *s = "/* not a comment";\n' + LIFECYCLE
    assert validate_c_source(source, "Game") == "game"


@pytest.mark.parametrize("prefix", [
    '/**/ #include "/etc/passwd"\n',
    '/*\n*/ #include "/etc/passwd"\n',
    '%:include "/etc/passwd"\n',
    '#\\\ninclude "/etc/passwd"\n',
    '??=include "/etc/passwd"\n',
    '#pragma once\n',
    '__asm__(".incbin \\"/etc/passwd\\"");\n',
    'void f(void) { asm volatile(""); }\n',
    '_Pragma("GCC poison x")\n',
    '#define CAT(a, b) a##b\n',
    '/* never closed\n',
])
def test_host_access_tricks_are_rejected(prefix):
    with pytest.raises(ValueError):
        validate_c_source(prefix + LIFECYCLE, "Game")


def test_lifecycle_inside_comment_does_not_count():
    with pytest.raises(ValueError):
        validate_c_source("/*\n" + LIFECYCLE + "*/\n", "Game")
