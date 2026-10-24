"""The interface in English, Italian, Spanish, French, German and Simplified Chinese (ADR-0027,
docs/i18n.md).

Catalogs: the same keys and placeholders everywhere, nothing left in English by accident.
Pages and scripts: every visible text goes through a catalog. Locale: chosen by the reader,
offline too. Builds: the language never changes generated code, cartridges or saved projects.
"""
from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from prg32_construction_kit import i18n

ROOT = Path(__file__).resolve().parent.parent
CATALOGS = {locale: json.loads((ROOT / "static" / "i18n" / f"{locale}.json").read_text()) for locale in i18n.LOCALES}
EN = {key: value for key, value in CATALOGS["en"].items() if not key.startswith("_")}
PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]*\}|%\d+")
SAME_AS_ENGLISH = json.loads((ROOT / "tests" / "fixtures" / "i18n" / "same_as_english.json").read_text())
SCRIPTS = sorted([*(ROOT / "static" / "js").glob("*.js"), *(ROOT / "static" / "js" / "ide").glob("*.js")])
JS_CALL = re.compile(r"(?<![\w.$])tr\('([\w.]+)', '((?:\\.|[^'\\])*)'")


def messages(locale: str) -> dict[str, str]:
    return {key: value for key, value in CATALOGS[locale].items() if not key.startswith("_")}


# --- the catalogs ------------------------------------------------------------------------------

def test_the_six_languages_are_offered():
    assert i18n.LOCALES == ("en", "it", "es", "fr", "de", "zh-Hans")
    assert set(i18n.NAMES) == set(i18n.LOCALES)


@pytest.mark.parametrize("locale", i18n.LOCALES[1:])
def test_every_language_has_exactly_the_english_keys(locale):
    assert set(messages(locale)) == set(EN)


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_no_message_is_empty(locale):
    assert not [key for key, value in messages(locale).items() if not value.strip()]


@pytest.mark.parametrize("locale", i18n.LOCALES[1:])
def test_placeholders_are_the_same_in_every_language(locale):
    """{name} values and Blockly's %1 inputs must all be there, or a message breaks or loses a value."""
    wrong = {key: value for key, value in messages(locale).items()
             if not key.endswith(".one") and sorted(PLACEHOLDER.findall(value)) != sorted(PLACEHOLDER.findall(EN[key]))}
    assert not wrong


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_plural_pairs_are_complete(locale):
    keys = set(messages(locale))
    for key in keys:
        if key.endswith(".one"):
            assert key[:-4] + ".other" in keys
        if key.endswith(".other"):
            assert key[:-6] + ".one" in keys and key[:-6] in keys


@pytest.mark.parametrize("locale", i18n.LOCALES[1:])
def test_nothing_is_left_in_english_by_accident(locale):
    """A message equal to English must be a reviewed cognate, name or code (fixtures/i18n/same_as_english.json)."""
    same = sorted(key for key, value in messages(locale).items() if value == EN[key])
    assert same == SAME_AS_ENGLISH[locale]


def test_the_browser_copies_of_the_catalogs_are_up_to_date():
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_i18n.py"), "--check"],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


# --- pages and scripts use the catalogs ---------------------------------------------------------

def template_keys() -> set[str]:
    keys: set[str] = set()
    for path in (ROOT / "templates").glob("*.html"):
        keys |= set(re.findall(r"""\bt\(["']([\w.]+)["']""", path.read_text()))
    return keys


def test_every_key_a_template_uses_exists():
    assert template_keys() - set(EN) == set()


def test_every_script_message_exists_with_the_same_english():
    """tr('key', 'English'): the English stays in the script; it must be the catalog's English."""
    wrong = []
    for path in SCRIPTS:
        for key, english in JS_CALL.findall(path.read_text()):
            text = english.replace("\\'", "'").replace("\\\\", "\\")
            if EN.get(key) != text:
                wrong.append((path.name, key, text, EN.get(key)))
    assert not wrong


def test_every_catalog_key_is_used():
    used = template_keys() | {key for path in SCRIPTS for key, _ in JS_CALL.findall(path.read_text())}
    for page in ("offline.html", "offline-player.html"):
        used |= set(re.findall(r'data-i18n(?:-attr)?="(?:[\w-]+:)?([\w.]+)"', (ROOT / "static" / page).read_text()))
        used |= set(re.findall(r':([\w.]+)"', (ROOT / "static" / page).read_text()))
    base = {key.rsplit(".", 1)[0] if key.endswith((".one", ".other")) else key for key in EN}
    assert sorted(key for key in base if key not in used and key != "base.language") == []


VISIBLE = re.compile(r"(<!--.*?-->|\{#.*?#\}|\{%.*?%\}|<[^>]*>)", re.S)
BRANDS = re.compile(r"^(PRG32[\w\-]*( cartridge)?|AudioStudio|Sprite Lab|C|OK|RISC-V|Monaco|Blockly|GitHub|Google Drive|"
                    r"OneDrive|Microsoft OneDrive|Cartridge Store|[\w.\-]+\.(c|S|py|json|h|prg32|zip)|[a-z0-9\-]+)$")


@pytest.mark.parametrize("template", sorted(path.name for path in (ROOT / "templates").glob("*.html")))
def test_templates_have_no_untranslated_text(template):
    """Visible text outside t(...): only names, code and markup may stay as written."""
    source = (ROOT / "templates" / template).read_text()
    leftovers, skip = [], 0
    for piece in VISIBLE.split(source):
        tag = re.match(r"<\s*(/?)\s*(script|style|code|pre|kbd|textarea|samp)\b", piece or "", re.I)
        if tag:
            skip += -1 if tag.group(1) else 1
            continue
        if not piece or piece.startswith(("<", "{%", "{#")) or skip:
            continue
        text = html.unescape(re.sub(r"\{\{.*?\}\}", " ", piece, flags=re.S)).strip()
        if re.search(r"[A-Za-z]{2,}", text) and not BRANDS.match(text):
            leftovers.append(text)
    for value in re.findall(r'\s(?:title|aria-label|placeholder|alt)="([^"{]*[A-Za-z]{2,}[^"{]*)"', source):
        if not BRANDS.match(value.strip()):
            leftovers.append(value)
    assert leftovers == []


def test_scripts_build_no_untranslated_html_text():
    """Text nodes and labels inside HTML that scripts build must come from tr(...)."""
    leftovers = []
    for path in SCRIPTS:
        if path.name in ("prg32_language_index.js", "simulator.js", "prg32_runtime.js", "monaco_setup.js"):
            continue
        source = re.sub(r"tr\('[^']*', '(?:\\.|[^'\\])*'(?:, \{[^}]*\})?\)", "TR", path.read_text())
        source = re.sub(r"^\s*//.*$", "", source, flags=re.M)
        for match in re.finditer(r">([^<>${}`'\n]*[A-Za-z]{3,} [A-Za-z]{2,}[^<>${}`'\n]*)<", source):
            leftovers.append((path.name, match.group(1).strip()))
        for match in re.finditer(r'\s(?:title|aria-label|placeholder)="([A-Z][a-z]+ [^"${}]*)"', source):
            leftovers.append((path.name, match.group(1)))
    assert leftovers == []


def test_static_offline_pages_load_the_catalogs_before_their_scripts():
    for page in ("offline.html", "offline-player.html"):
        text = (ROOT / "static" / page).read_text()
        assert text.index("/static/i18n/en.js") < text.index("/static/js/i18n.js") < text.index("/static/js/offline")
        for key in re.findall(r'data-i18n="([\w.]+)"', text):
            assert key in EN, (page, key)


def test_the_service_worker_caches_the_catalogs_for_offline_use():
    worker = (ROOT / "static" / "service-worker.js").read_text()
    for locale in i18n.LOCALES:
        assert f"'/static/i18n/{locale}.js'" in worker
    assert "'/static/js/i18n.js'" in worker


# --- choosing the language ----------------------------------------------------------------------

@pytest.mark.parametrize("cookie,accept,expected", [
    ("it", "de-DE,de;q=0.9", "it"),                 # the reader's choice wins
    (None, "fr-CH, fr;q=0.9, en;q=0.8", "fr"),
    (None, "pt-BR,pt;q=0.9,es;q=0.5", "es"),        # first supported language asked for
    (None, "de;q=0.2,it;q=0.8", "it"),              # quality decides, not order
    (None, "ja,ko", "en"),                          # nothing supported: English
    (None, "ja,zh", "zh-Hans"),                     # Chinese: Simplified characters
    (None, "zh-CN,zh;q=0.9,en;q=0.5", "zh-Hans"),
    (None, "zh-Hans-SG", "zh-Hans"),
    (None, "zh_CN", "zh-Hans"),
    (None, "zh-TW,en;q=0.5", "en"),                 # Traditional characters are another script:
    (None, "zh-Hant-HK", "en"),                     # not the wrong characters, English
    (None, "zh-HK,zh;q=0.8", "zh-Hans"),            # unless the reader also accepts plain zh
    ("zh-Hans", "en", "zh-Hans"),
    ("zh", "", "en"),                               # the cookie names a locale exactly
    ("xx", "", "en"),                               # an unknown cookie is ignored
    (None, "es;q=0", "en"),
])
def test_the_language_is_the_readers_choice_then_the_browsers(cookie, accept, expected):
    assert i18n.choose(cookie, accept) == expected


def test_messages_fall_back_and_fill_in_values():
    assert i18n.translate("it", "common.save") == "Salva"
    assert i18n.translate("de", "ide.ide", name="Kit") == "IDE - Kit"
    assert i18n.translate("it", "no.such.key") == "no.such.key"
    assert i18n.translate("fr", "js.ide.compiler_problems", count=0) == "Compilateur : 0 problème"
    assert i18n.translate("fr", "js.ide.compiler_problems", count=2) == "Compilateur : 2 problèmes"
    assert i18n.translate("en", "js.ide.compiler_problems", count=1) == "Compiler: 1 problem"
    # Chinese has no plural forms: one text for every count.
    assert i18n.translate("zh-Hans", "js.ide.compiler_problems", count=1) == "编译器：1 个问题"
    assert i18n.translate("zh-Hans", "js.ide.compiler_problems", count=2) == "编译器：2 个问题"


@pytest.mark.parametrize("locale,word", [("en", "Projects"), ("it", "Progetti"), ("es", "Proyectos"),
                                         ("fr", "Projets"), ("de", "Projekte"), ("zh-Hans", "项目")])
def test_pages_are_drawn_in_the_chosen_language(anon, locale, word):
    anon.set_cookie(i18n.COOKIE, locale)
    page = anon.get("/auth/login")
    text = page.get_data(as_text=True)
    assert page.status_code == 200 and f'<html lang="{locale}"' in text and word in text
    assert "Accept-Language" in page.headers.get("Vary", "")
    if locale != "en":
        assert f'/static/i18n/{locale}.js' in text


def test_accept_language_picks_the_page_language(anon):
    text = anon.get("/auth/login", headers={"Accept-Language": "de-AT,de;q=0.9"}).get_data(as_text=True)
    assert '<html lang="de"' in text and "Anmelden" in text


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_signed_in_pages_render_in_every_language(client, locale):
    client.set_cookie(i18n.COOKIE, locale)
    for path in ("/", "/account", "/privacy", "/player", "/publish", "/artifacts", "/classes", "/documentation",
                 "/admin/settings", "/admin/users", "/admin/identity"):
        response = client.get(path)
        assert response.status_code == 200, (path, locale)
    project = client.post("/api/projects", json={"title": "Lang"}).get_json()
    assert client.get(f"/ide/{project['id']}").status_code == 200


def test_privacy_notices_are_shown_in_the_readers_language(anon):
    from prg32_construction_kit.privacy import BROWSER_STORAGE, notices

    for notice in notices().values():
        assert set(notice["translations"]) == set(i18n.LOCALES[1:]), notice["id"]
    storage = notices()["storage"]
    for locale in i18n.LOCALES[1:]:
        assert CATALOGS[locale]["notice.storage"] == storage["translations"][locale]
        anon.set_cookie(i18n.COOKIE, locale)
        from markupsafe import escape
        assert str(escape(storage["translations"][locale])) in anon.get("/auth/login").get_data(as_text=True)
    assert CATALOGS["en"]["notice.storage"] == storage["summary"]
    assert {"prg32_locale", "prg32-kit-locale"} <= {item["name"] for item in BROWSER_STORAGE}


# --- the browser runtime --------------------------------------------------------------------------

@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node.js")
def test_the_browser_runtime_translates_with_fallback_and_plurals():
    script = r"""
      const fs = require('fs'), vm = require('vm');
      const ctx = { console, Intl };
      ctx.window = ctx; ctx.globalThis = ctx;
      ctx.navigator = { languages: ['fr-FR'] };
      ctx.localStorage = { getItem: () => null, setItem: () => {} };
      ctx.location = { protocol: 'http:' };
      ctx.document = { cookie: '', readyState: 'complete', querySelectorAll: () => [], head: { appendChild() {} },
        documentElement: { getAttribute: () => 'it', hasAttribute: () => true, setAttribute() {} } };
      vm.createContext(ctx);
      for (const file of process.argv.slice(1)) vm.runInContext(fs.readFileSync(file, 'utf8'), ctx);
      const out = {
        locale: ctx.PRG32I18n.locale,
        save: ctx.tr('common.save', 'Save'),
        missing: ctx.tr('js.no.such', 'Plain {x}', { x: 3 }),
        one: ctx.tr('js.ide.compiler_problems', 'Compiler: {count} problems', { count: 1 }),
        many: ctx.tr('js.ide.compiler_problems', 'Compiler: {count} problems', { count: 4 }),
        t: ctx.PRG32I18n.t('ide.ide', { name: 'X' }),
      };
      console.log(JSON.stringify(out));
    """
    files = [ROOT / "static" / "i18n" / "en.js", ROOT / "static" / "i18n" / "it.js", ROOT / "static" / "js" / "i18n.js"]
    result = subprocess.run(["node", "-e", script, *map(str, files)], capture_output=True, text=True, check=True)
    out = json.loads(result.stdout)
    assert out == {"locale": "it", "save": "Salva", "missing": "Plain 3", "one": "Compilatore: 1 problema",
                   "many": "Compilatore: 4 problemi", "t": "IDE - X"}


# --- the language never reaches the build -----------------------------------------------------------

def test_generated_code_and_cartridges_are_the_same_in_every_language(client, monkeypatch):
    """The same saved projects build byte for byte the same whatever the interface language."""
    from types import SimpleNamespace

    from prg32_construction_kit import python_project
    from prg32_construction_kit.sample_data import default_blocks

    def fake_builder(command, **_kwargs):
        source = Path(next(arg for arg in command if arg.endswith(("game.c", "game.S"))))
        Path(command[command.index("--out") + 1]).write_bytes(b"PRG2" + source.read_bytes()[:64])
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    blocks = client.post("/api/projects", json={"title": "Same Game", "blocks_json": default_blocks()}).get_json()
    python = client.post("/api/projects", json={"title": "Same Py", "game_json": {
        "source_mode": "python", "source_python": python_project.STARTER, "python_language_version": 1}}).get_json()
    seen: dict[str, set[str]] = {}
    for locale in i18n.LOCALES:
        client.set_cookie(i18n.COOKIE, locale)
        for project in (blocks, python):
            generated = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"},
                                    headers={"Accept-Language": locale}).get_json()
            built = client.post(f"/api/projects/{project['id']}/package",
                                json={"architectures": ["qemu"], "source_language": "c"}).get_json()
            provenance = built["build"]["metadata"]["provenance"]
            fingerprint = json.dumps([generated["c_source"], generated["asm_source"], generated["game_ir"],
                                      provenance["sources"], [c["sha256"] for c in provenance["cartridges"]]],
                                     sort_keys=True)
            seen.setdefault(project["id"], set()).add(fingerprint)
            stored = client.get(f"/api/projects/{project['id']}").get_json()
            assert stored["blocks_json"] == project["blocks_json"]
    assert all(len(fingerprints) == 1 for fingerprints in seen.values())


def test_generators_never_read_the_language():
    """No generator, compiler or packager module imports the interface language."""
    for name in ("generator.py", "asm_generator.py", "python_project.py", "expressions.py", "packager.py",
                 "source_maps.py", "project_format.py", "provenance.py"):
        text = (ROOT / "prg32_construction_kit" / name).read_text()
        assert "i18n" not in text and "Accept-Language" not in text, name
