"""The classroom lessons exist in every interface language and say the same thing (ADR-0027).

docs/tutorials/<lesson>.md is the English lesson; <lesson>.<locale>.md is the same lesson in
another language. A translation keeps the lesson's sections and its code exactly (a ```text block
shows blocks, whose words are translated); a lesson changed in English and not in a translation
shows up as a different section count or different code.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from prg32_construction_kit import i18n

TUTORIALS = Path(__file__).resolve().parent.parent / "docs" / "tutorials"
LESSONS = sorted(path.stem for path in TUTORIALS.glob("0[1-9]_*.md") if "." not in path.stem)
CODE = re.compile(r"```(\w*)\n(.*?)```", re.S)


def sections(text: str) -> int:
    return len(re.findall(r"^## ", text, re.M))


def code(text: str) -> list[str]:
    return [body for kind, body in CODE.findall(text) if kind != "text"]


def test_there_are_nine_lessons_and_a_quick_start():
    assert len(LESSONS) == 9
    assert all((TUTORIALS / f"quickstart.{locale}.md").is_file() for locale in i18n.LOCALES)


@pytest.mark.parametrize("locale", i18n.LOCALES[1:])
@pytest.mark.parametrize("lesson", LESSONS)
def test_every_lesson_is_translated_with_the_same_sections_and_code(lesson, locale):
    english = (TUTORIALS / f"{lesson}.md").read_text()
    path = TUTORIALS / f"{lesson}.{locale}.md"
    assert path.is_file(), f"translate {lesson}.md into {locale}"
    translated = path.read_text()
    assert sections(translated) == sections(english), f"{path.name}: the sections differ from the English lesson"
    assert code(translated) == code(english), f"{path.name}: the code differs from the English lesson"
    names = re.compile(r"`(prg32[^`\n]*|[a-z_]+\.(?:md|py|c|S|prg32))`")
    inline = set(names.findall(CODE.sub("", english)))
    assert inline <= set(names.findall(CODE.sub("", translated))), f"{path.name}: names or files left out"
