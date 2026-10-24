"""The top menu of an open project in a real browser (base.html, app.js, ide.js, player.js).

- In the IDE the menu bar shows the PRG32 logo and the kit's name; Sprite Lab, AudioStudio and Editor switch tab
  without loading the page again, and the menu marks the one shown; Player opens the project's
  Player; the logo closes the project and goes back to Projects.
- The Day/Night switch changes the colours at once and they stay after a reload.
- Each project card on the Projects page opens Sprite Lab, AudioStudio and Player for its project.
"""

from __future__ import annotations

from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures
from test_guest_ide_browser import api

READY = "document.getElementById('ide').dataset.ready === 'true'"


def selected_tab(page) -> str:
    return page.evaluate("document.querySelector('#ideTabs [aria-selected=true]').id")


def marked(page) -> str:
    return page.evaluate("document.querySelector('[data-ide-tool].active').dataset.ideTool")


def test_the_top_menu_works_on_the_open_project(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Menu Racer"})

    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    assert page.inner_text(".navbar-brand").strip() == "PRG32 Construction Kit"
    assert marked(page) == "editor"
    page.evaluate("window.notReloaded = true")    # gone if a menu click loaded the page again

    page.click("[data-ide-tool=sprites]")
    wait_until(page, "!!document.querySelector('#tab-tool-sprites[aria-selected=true]')")
    assert page.evaluate("location.hash") == "#sprites" and marked(page) == "sprites"
    page.click("[data-ide-tool=sound]")
    wait_until(page, "!!document.querySelector('#tab-tool-sound[aria-selected=true]')")
    assert page.evaluate("location.hash") == "#sound" and marked(page) == "sound"
    page.click("[data-ide-tool=editor]")
    wait_until(page, "!!document.querySelector('#tab-blocks[aria-selected=true]')")
    assert page.evaluate("location.hash") == "" and marked(page) == "editor"
    assert page.evaluate("window.notReloaded") is True

    # Player: this project's newest cartridge; none compiled yet, so it says how to make one.
    page.click("[data-ide-tool=player]")
    page.wait_for_url(f"{live_kit}/player?project={project['id']}")
    wait_until(page, "document.getElementById('playerStatus').textContent.includes('no compiled cartridge yet')")
    assert marked(page) == "player"
    assert page.get_attribute("#playerStatus a", "href") == f"/ide/{project['id']}"

    # The icon closes the project: the Projects page has the kit's own menu again.
    page.click("#navCloseProject")
    page.wait_for_url(f"{live_kit}/")
    assert page.query_selector("#navCloseProject") is None
    assert page.inner_text(".navbar-brand").strip() == "PRG32 Construction Kit"
    assert record.csp_violations() == []
    context.close()


def test_each_project_card_opens_its_tools(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Card Game"})
    page.goto(live_kit + "/")
    card = ".project-card:has-text('Card Game')"
    page.wait_for_selector(card)
    links = page.eval_on_selector_all(f"{card} a", "links => links.map(a => a.getAttribute('href'))")
    ide = f"/ide/{project['id']}"
    assert [ide, ide + "#sprites", ide + "#sound", f"/player?project={project['id']}"] == links[:4]

    page.click(f"{card} a[href='{ide}#sprites']")
    wait_until(page, READY)
    wait_until(page, "!!document.querySelector('#tab-tool-sprites[aria-selected=true]')")
    assert marked(page) == "sprites"
    context.close()


def test_day_and_night_colours_are_this_readers_choice(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    scheme = "document.documentElement.getAttribute('data-bs-theme')"
    assert page.evaluate(scheme) == "light"     # the kit's default (Settings, Appearance)
    page.click("#schemeSwitch")
    assert page.evaluate(scheme) == "dark" and page.get_attribute("#schemeSwitch", "aria-pressed") == "true"
    page.reload()
    assert page.evaluate(scheme) == "dark"      # theme.js applies it before the page is drawn
    project = api(page, "/api/projects", "POST", {"title": "Night Coder", "kind": "c"})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    page.click("#schemeSwitch")                 # Day again: the code editor follows at once
    wait_until(page, "!!document.querySelector('.monaco-editor.vs') || !document.querySelector('.monaco-editor')")
    assert page.evaluate(scheme) == "light"
    page.goto(live_kit + "/static/offline.html")
    assert page.evaluate(scheme) == "light"
    assert record.csp_violations() == []
    context.close()


def test_the_blocks_follow_day_and_night(browser, live_kit):  # noqa: F811
    """The workspace and the block list get Night colours; the labels never take the page's text colour."""
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    page.evaluate("localStorage.setItem('prg32-kit-color-scheme', 'night')")
    project = api(page, "/api/projects", "POST", {"title": "Night Blocks"})
    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, READY)
    wait_until(page, "!!document.querySelector('#blocklyDiv .blocklyTreeLabel')")
    style = "([selector, name]) => getComputedStyle(document.querySelector('#blocklyDiv ' + selector))[name]"
    def colours():
        return (page.evaluate(style, [".blocklyTreeLabel", "color"]), page.evaluate(style, [".blocklyToolboxDiv", "backgroundColor"]),
                page.evaluate(style, [".blocklyMainBackground", "fill"]))
    assert colours() == ("rgb(236, 230, 245)", "rgb(26, 15, 43)", "rgb(18, 10, 29)")
    page.click("#schemeSwitch")                     # Day, at once
    assert colours() == ("rgb(22, 12, 36)", "rgb(243, 238, 251)", "rgb(255, 255, 255)")
    page.goto(live_kit + "/static/offline.html")    # the offline editor follows too, with no CSP violation
    page.evaluate("localStorage.setItem('prg32-kit-color-scheme', 'night')")
    page.reload()
    wait_until(page, "!!document.querySelector('#blocklyDiv .blocklyTreeLabel')")
    assert colours()[0] == "rgb(236, 230, 245)"
    assert record.csp_violations() == []
    context.close()
