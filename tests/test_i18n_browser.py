"""The six interface languages in a real browser (ADR-0027, audit scenario K).

- Every language: the page is drawn in it (html lang, the kit's own texts), Blockly's own menus
  and Monaco's own messages come from their language packs in static/vendor, with no Content
  Security Policy violation, for a guest, a student, a teacher and an admin.
- Simplified Chinese: a CJK font (the computer's or Noto Sans SC from the kit), lines that break
  between characters without making the page scroll sideways, Chinese typed into a project's
  title kept exactly, and the offline page and its Blockly menus in Chinese.
- Changing the language while editing saves the unsaved work first; the language never changes
  what is saved.
"""

from __future__ import annotations

import json

import pytest
from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures
from test_guest_ide_browser import api

from prg32_construction_kit import i18n

ROOT = __import__("pathlib").Path(__file__).resolve().parent.parent
CATALOGS = {locale: json.loads((ROOT / "static" / "i18n" / f"{locale}.json").read_text()) for locale in i18n.LOCALES}
READY = "document.getElementById('ide').dataset.ready === 'true'"
# One Blockly menu text and one Monaco message per language, from their own packs.
BLOCKLY_DELETE = {"en": "Delete Block", "it": "Cancella blocco", "es": "Eliminar bloque", "fr": "Supprimer le bloc",
                  "de": "Baustein löschen", "zh-Hans": "删除块"}


def context(browser, live_kit, locale):  # noqa: F811
    ctx = browser.new_context(viewport={"width": 1440, "height": 800})   # the menu bar unfolded
    ctx.add_cookies([{"name": i18n.COOKIE, "value": locale, "url": live_kit}])
    return ctx


def c_project(page, title: str) -> dict:
    """A C project made the way the Projects page makes one: from the kit's starter game."""
    starter = page.evaluate("t => Kit.api('/api/starters/c?title=' + encodeURIComponent(t))", title)
    return api(page, "/api/projects", "POST", starter)


def blockly_delete_text(page) -> str:
    return page.evaluate("Blockly.Msg.DELETE_BLOCK")


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_a_guest_works_in_every_language(browser, live_kit, locale):  # noqa: F811
    ctx = context(browser, live_kit, locale)
    record = Recorder(ctx, live_kit)
    page = record.watch(ctx.new_page())
    page.goto(live_kit + "/")
    wait_until(page, "window.Kit && Kit.guest === true && !!window.PRG32GuestApi")
    assert page.get_attribute("html", "lang") == locale
    assert CATALOGS[locale]["index.new_project"] in page.inner_text("body")
    project = api(page, "/api/projects", "POST", {"title": "Lingua"})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    assert blockly_delete_text(page) == BLOCKLY_DELETE[locale]
    assert CATALOGS[locale]["ide.generate"] in page.inner_text("#ideGenerate")
    assert record.csp_violations() == []
    ctx.close()


@pytest.mark.parametrize("locale", ("it", "zh-Hans"))
def test_monaco_speaks_the_readers_language(browser, live_kit, locale):  # noqa: F811
    ctx = context(browser, live_kit, locale)
    record = Recorder(ctx, live_kit)
    page = record.watch(ctx.new_page())
    sign_in(page, live_kit)
    project = c_project(page, "Codice")
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY, timeout=60)                  # Monaco and its language pack load first; slow under a full run
    pack = i18n.MONACO_PACKS[locale]
    # The first Chinese page also fetches the font pieces for its characters: give it time.
    wait_until(page, f"!!window.monaco && globalThis._VSCODE_NLS_LANGUAGE === {json.dumps(pack)}", timeout=60)
    messages = page.evaluate("JSON.stringify(globalThis._VSCODE_NLS_MESSAGES || [])")
    assert {"it": "Maiuscole/minuscole", "zh-Hans": "区分大小写"}[locale] in messages
    assert record.csp_violations() == []
    ctx.close()


def test_the_prg32_core_never_takes_monacos_language_pack(browser, live_kit):  # noqa: F811
    """prg32-core.js (Emscripten) calls an anonymous AMD define() when Monaco's loader is on the page.
    Run while Monaco's language pack was on its way, the loader gave the pack the core's define and
    Monaco stayed in English. Forced here: the pack is held until the core has been asked for
    (no service worker, so the page's requests can be held)."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 800}, service_workers="block")
    ctx.add_cookies([{"name": i18n.COOKIE, "value": "zh-Hans", "url": live_kit}])
    page = ctx.new_page()
    sign_in(page, live_kit)
    project = c_project(page, "Race")
    held = []
    page.route("**/vs/nls.messages.zh-cn.js", lambda route: held.append(route))      # answered below, after the core
    page.goto(f"{live_kit}/ide/{project['id']}", wait_until="domcontentloaded")
    for _ in range(300):
        if held:
            break
        page.wait_for_timeout(100)
    assert held, "Monaco asked for its language pack"
    page.evaluate("void window.PRG32LoadPlainScript('/static/wasm/prg32-core.js')")   # not waited for: it may wait for Monaco
    page.wait_for_timeout(1500)                                    # the core would have run by now
    held[0].continue_()
    wait_until(page, READY, timeout=60)
    wait_until(page, "typeof window.createPrg32Core === 'function' && !!window.monaco", timeout=60)
    assert page.evaluate("globalThis._VSCODE_NLS_LANGUAGE") == "zh-cn"
    assert page.evaluate("!!(window.define && window.define.amd)")       # given back to Monaco's loader
    ctx.close()


ROLES = {"student": "user", "teacher": "user", "admin": None}


@pytest.mark.parametrize("locale", i18n.LOCALES)
def test_signed_in_roles_see_their_pages_in_every_language(browser, live_kit, locale):  # noqa: F811
    """Admin pages (Settings, Users), a teacher's Classes page and a student's Account page."""
    ctx = context(browser, live_kit, locale)
    record = Recorder(ctx, live_kit)
    page = record.watch(ctx.new_page())
    sign_in(page, live_kit)
    for path, key in (("/admin/settings", "common.settings"), ("/admin/users", "common.users"),
                      ("/classes", "common.classes"), ("/account", "common.my_account"), ("/privacy", "privacy.what_you_can_do"),
                      ("/publish", "publish.cartridge_store_profiles"), ("/player", "player.cartridge_player_2")):
        page.goto(live_kit + path)
        assert page.get_attribute("html", "lang") == locale, path
        assert CATALOGS[locale][key] in page.inner_text("body"), (path, key)
    assert record.csp_violations() == []
    ctx.close()


def test_chinese_has_a_font_breaks_lines_and_keeps_typed_text(browser, live_kit):  # noqa: F811
    ctx = context(browser, live_kit, "zh-Hans")
    record = Recorder(ctx, live_kit)
    page = record.watch(ctx.new_page())
    sign_in(page, live_kit)
    page.goto(live_kit + "/")
    family = page.evaluate("getComputedStyle(document.body).fontFamily")
    assert "Noto Sans SC" in family and "PingFang SC" in family
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")   # no sideways scroll
    # The long welcome title breaks between characters, onto several lines.
    lines = page.evaluate("""() => { const h = document.querySelector('.kit-hero h1');
        return Math.round(h.getBoundingClientRect().height / parseFloat(getComputedStyle(h).lineHeight)); }""")
    assert lines >= 2
    page.set_viewport_size({"width": 375, "height": 800})
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.set_viewport_size({"width": 1440, "height": 800})

    # Chinese typed with the keyboard (an input method commits text like this) is kept exactly.
    title = "我的第一个游戏：太空射击"
    project = api(page, "/api/projects", "POST", {"title": "x"})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    page.click("#ideProjectMenu")
    page.click("#ideProperties")
    page.fill("#propTitle", "")
    page.focus("#propTitle")
    page.keyboard.insert_text(title)
    page.click("#idePropertiesForm button[type=submit]")
    wait_until(page, f"document.getElementById('ideTitle').textContent === {json.dumps(title)}")
    saved = api(page, f"/api/projects/{project['id']}")
    assert saved["title"] == title
    assert record.csp_violations() == []
    ctx.close()


def test_changing_language_while_editing_saves_first_and_changes_nothing_saved(browser, live_kit):  # noqa: F811
    ctx = context(browser, live_kit, "en")
    page = ctx.new_page()
    sign_in(page, live_kit)
    project = c_project(page, "Switch")
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    wait_until(page, "!!PRG32Ide.editors.src", timeout=60)
    page.evaluate("PRG32Ide.editors.src.setValue(PRG32Ide.editors.src.getValue() + '\\n/* edited before switching */\\n')")
    wait_until(page, "PRG32Ide.dirty === true || document.querySelector('#ideSave') !== null")
    with page.expect_navigation(timeout=30000):   # saved first, then the page is drawn again
        page.select_option("#localeChoice", "zh-Hans")
    wait_until(page, READY)
    assert page.get_attribute("html", "lang") == "zh-Hans"
    saved = api(page, f"/api/projects/{project['id']}")
    assert "/* edited before switching */" in saved["game_json"]["source_c"]
    ctx.close()


def test_the_offline_page_and_its_blocks_speak_chinese(browser, live_kit):  # noqa: F811
    ctx = context(browser, live_kit, "zh-Hans")
    record = Recorder(ctx, live_kit)
    page = record.watch(ctx.new_page())
    page.goto(live_kit + "/static/offline.html?guest=1")
    wait_until(page, "document.documentElement.lang === 'zh-Hans'")
    wait_until(page, f"Blockly.Msg.DELETE_BLOCK === {json.dumps(BLOCKLY_DELETE['zh-Hans'])}")
    assert CATALOGS["zh-Hans"]["offline.save_as_file"] in page.inner_text("body")
    assert record.csp_violations() == []
    ctx.close()


def test_a_server_message_reaches_the_reader_in_their_language(browser, live_kit):  # noqa: F811
    """The PRG32 Python checker's refusal (written by the server in English, with its key) is listed
    in Problems in Chinese, at its line."""
    ctx = context(browser, live_kit, "zh-Hans")
    page = ctx.new_page()
    sign_in(page, live_kit)
    source = ("import prg32\nx: int = 0\n\n\ndef init() -> None:\n    global x\n    x = y + 1\n\n\n"
              "def update() -> None:\n    pass\n\n\ndef draw() -> None:\n    pass\n")
    project = api(page, "/api/projects", "POST", {"title": "Mensaje", "game_json": {
        "source_mode": "python", "source_python": source, "python_language_version": 1}})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY, timeout=60)
    page.click("#ideGenerate")
    wait_until(page, "document.getElementById('ideProblems').textContent.includes('没有定义')", timeout=30)
    text = page.inner_text("#ideProblems")
    assert "第 7 行" in text and "y 没有定义" in text and "is not defined" not in text
    ctx.close()


@pytest.mark.parametrize("width", (375, 1024, 1280, 1366, 1400, 1440, 1600, 1920))
def test_the_menu_bar_is_one_row_in_every_language(browser, live_kit, width):  # noqa: F811
    """Long labels (French, German) never push the menu onto a second row; below 1400 px it folds
    behind the menu button. Signed in as admin: the longest menu."""
    for locale in i18n.LOCALES:
        ctx = browser.new_context(viewport={"width": width, "height": 800})
        ctx.add_cookies([{"name": i18n.COOKIE, "value": locale, "url": live_kit}])
        page = ctx.new_page()
        sign_in(page, live_kit)
        project = api(page, "/api/projects", "POST", {"title": "Row"})
        page.goto(f"{live_kit}/ide/{project['id']}")
        height = page.evaluate("document.querySelector('.kit-navbar').getBoundingClientRect().height")
        assert height < 80, f"{locale} at {width} px: the menu bar is {height:.0f} px tall (two rows)"
        assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), (locale, width)
        ctx.close()
