"""The kit's interface in six languages: English, Italian, Spanish, French, German and Simplified
Chinese (ADR-0027).

One catalog per language, ``static/i18n/<locale>.json``: a flat object from message key to text.
The server renders pages with ``t(key, **values)`` (a Jinja global); the browser reads the same
catalog from ``static/i18n/<locale>.js`` (made by tools/build_i18n.py) through ``Kit.t``.

- ``{name}`` in a text is a value filled in when it is shown; every language has the same names.
- A key ending in ``.one``/``.other`` is a plural pair: ``t(key, count=n)`` picks the right one.
- A missing key falls back to English, then to the key itself, so a page never breaks.
- The language is a choice of the reader only: the ``prg32_locale`` cookie (set by the language
  menu), else the browser's ``Accept-Language``, else English. It never reaches the game IR,
  the generated C or assembly, the cartridge or any saved project (tests/test_i18n.py proves
  it), so a project builds byte for byte the same in every language.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

LOCALES = ("en", "it", "es", "fr", "de", "zh-Hans")
DEFAULT = "en"
NAMES = {"en": "English", "it": "Italiano", "es": "Español", "fr": "Français", "de": "Deutsch", "zh-Hans": "简体中文"}
# Chinese written in Simplified characters: zh-Hans, and the regions that use it. Traditional
# Chinese (zh-Hant, zh-TW, zh-HK, zh-MO) is a different script: those readers get English, not
# the wrong characters.
SIMPLIFIED_CHINESE = ("zh", "zh-hans", "zh-cn", "zh-sg", "zh-my")
TRADITIONAL_CHINESE = ("zh-hant", "zh-tw", "zh-hk", "zh-mo")
# The names Blockly's and Monaco's own language packs use (static/vendor; English needs none).
BLOCKLY_PACKS = {"it": "it", "es": "es", "fr": "fr", "de": "de", "zh-Hans": "zh-hans"}
MONACO_PACKS = {"it": "it", "es": "es", "fr": "fr", "de": "de", "zh-Hans": "zh-cn"}


def locale_of(tag: str) -> str | None:
    """The kit's locale for one language tag (en-GB -> en, zh-Hans-CN -> zh-Hans), or None."""
    tag = tag.strip().replace("_", "-").lower()
    if tag.startswith("zh"):
        if any(tag == prefix or tag.startswith(prefix + "-") for prefix in TRADITIONAL_CHINESE):
            return None
        return "zh-Hans" if any(tag == prefix or tag.startswith(prefix + "-") for prefix in SIMPLIFIED_CHINESE) else None
    code = tag.split("-", 1)[0]
    return code if code in LOCALES else None
COOKIE = "prg32_locale"
CATALOG_DIR = Path(__file__).resolve().parent.parent / "static" / "i18n"
PLACEHOLDER = re.compile(r"\{([a-z_][a-z0-9_]*)\}")


@lru_cache(maxsize=None)
def catalog(locale: str) -> dict[str, str]:
    """The messages of one language (read once; the files ship with the kit)."""
    if locale not in LOCALES:
        return {}
    path = CATALOG_DIR / f"{locale}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {key: value for key, value in data.items() if not key.startswith("_")}


def choose(cookie: str | None, accept_language: str | None) -> str:
    """The reader's language: their choice, else the first supported language their browser asks for."""
    if cookie in LOCALES:
        return cookie  # type: ignore[return-value]
    wanted: list[tuple[float, int, str]] = []
    for index, part in enumerate((accept_language or "").split(",")[:20]):
        pieces = part.strip().split(";")
        code = locale_of(pieces[0])
        quality = 1.0
        for piece in pieces[1:]:
            name, _, value = piece.strip().partition("=")
            if name == "q":
                try:
                    quality = float(value)
                except ValueError:
                    quality = 0.0
        if code is not None and quality > 0:
            wanted.append((-quality, index, code))
    return sorted(wanted)[0][2] if wanted else DEFAULT


def plural_form(locale: str, count: int) -> str:
    """'one' or 'other': one for 1 (and 0 in French); Chinese has no plural, so always 'other'."""
    if locale == "zh-Hans":
        return "other"
    if count == 1 or (locale == "fr" and count == 0):
        return "one"
    return "other"


def translate(locale: str, key: str, **values: Any) -> str:
    """The text of ``key`` in ``locale``, with ``{name}`` filled in from ``values``."""
    if "count" in values and isinstance(values["count"], int):
        form = f"{key}.{plural_form(locale, values['count'])}"
        if form in catalog(locale) or form in catalog(DEFAULT):
            key = form
    text = catalog(locale).get(key) or catalog(DEFAULT).get(key) or key
    return PLACEHOLDER.sub(lambda match: str(values.get(match.group(1), match.group(0))), text)


def current() -> str:
    """The language of the page being drawn (outside a request: English)."""
    from flask import g, has_request_context, request

    if not has_request_context():
        return DEFAULT
    if not hasattr(g, "prg32_locale"):
        g.prg32_locale = choose(request.cookies.get(COOKIE), request.headers.get("Accept-Language"))
    return g.prg32_locale


def t(key: str, **values: Any) -> str:
    return translate(current(), key, **values)


def init_app(app) -> None:
    app.jinja_env.globals["t"] = t

    @app.context_processor
    def inject_locale() -> dict:
        locale = current()
        return {"locale": locale, "locales": [(code, NAMES[code]) for code in LOCALES],
                "blockly_pack": BLOCKLY_PACKS.get(locale), "monaco_pack": MONACO_PACKS.get(locale)}

    @app.after_request
    def vary_on_language(response):
        # Pages differ by language: caches must keep one copy per Accept-Language and cookie.
        if response.mimetype == "text/html":
            response.vary.add("Accept-Language")
            response.vary.add("Cookie")
        return response
