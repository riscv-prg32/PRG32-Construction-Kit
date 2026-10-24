"""The guest workspace in a real browser (ADR-0023): the full kit without an account.

- A visitor makes a game in the IDE, a sprite in Sprite Lab and a sound in AudioStudio; all of it
  is kept in this browser and survives a reload, and no game is sent to the server to be kept.
- Generate shows the C and assembly (the server makes them and keeps nothing); Compile asks
  for a sign-in instead of building.
- After signing in, the Projects page moves the game, its sound and its sprite into the account.
- The settings pages, the footer and the storage note: no CSP violation, no serious axe problem.
"""

from __future__ import annotations

import json

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures

GAME = {"blocks": {"languageVersion": 0, "blocks": [{"type": "prg32_on_start", "id": "g1", "x": 20, "y": 20}]}}


def api(page, path, method="GET", body=None):
    """Kit.api from the page: for a guest it is answered in the browser (guest_api.js)."""
    return page.evaluate("([path, method, body]) => Kit.api(path, body === null ? {method} : {method, body})",
                         [path, method, body])


def guest_home(context, live_kit):  # noqa: F811 - the fixture's value is passed in
    page = context.new_page()
    page.goto(live_kit + "/")
    wait_until(page, "window.Kit && Kit.guest === true && !!window.PRG32GuestApi")
    return page


def kept_on_server(record):
    """Requests that would have kept a game on the server (the guest API keeps nothing)."""
    return [url for url in record.requests if "/api/" in url and "/api/guest/" not in url and "/api/examples" not in url]


def test_a_guest_makes_a_game_and_it_stays_in_this_browser(browser, live_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})   # the menu, with its badge, unfolded
    record = Recorder(context, live_kit)
    page = record.watch(guest_home(context, live_kit))
    assert page.is_visible("text=Guest: games stay in this browser")
    project = api(page, "/api/projects", "POST", {"title": "Space chase", "blocks_json": GAME})
    assert project["id"].startswith("guest-")

    page.goto(f"{live_kit}/ide/{project['id']}")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'")
    assert page.inner_text("#ideTitle").strip() == "Space chase"
    page.click("#ideGenerate")
    wait_until(page, "document.getElementById('ideOutput').textContent.includes('Generated')")
    generated = api(page, f"/api/projects/{project['id']}/convert", "POST", {"source_language": "both"})
    assert "prg32" in generated["c_source"] and generated["asm_source"]
    # Building a cartridge needs an account: the dialog says so, and nothing is built.
    page.click("#ideCompile")
    wait_until(page, "!!document.querySelector('#signInNeeded.show')")
    assert "needs an account" in page.inner_text("#signInNeeded")

    # A sprite and a sound for the game.
    api(page, "/api/sprites", "POST", {"project_id": project["id"], "name": "hero", "width": 2, "height": 2,
                                       "pixels": [["#ff0000", "#00ff00"], ["#0000ff", "#ffffff"]]})
    sound = api(page, f"/api/projects/{project['id']}/audio")
    saved = api(page, f"/api/projects/{project['id']}/audio", "PUT",
                {"document": sound["document"], "expected_version": sound["version"]})
    assert saved["version"] == 1

    # Everything is still there after a reload, on every page.
    page.goto(live_kit + "/")
    wait_until(page, "document.getElementById('projectCount').textContent === '1'")
    page.goto(f"{live_kit}/audio-studio/{project['id']}")
    wait_until(page, "document.getElementById('projectTitle').textContent === 'Space chase'")
    page.goto(f"{live_kit}/ide/{project['id']}#sprites")         # Sprite Lab, a tab of the game's IDE
    wait_until(page, "document.querySelectorAll('.sprite-choice').length === 1")
    page.goto(live_kit + "/audio-studio")
    wait_until(page, "document.querySelectorAll('#audioProjects a').length === 1")

    assert kept_on_server(record) == [], kept_on_server(record)
    assert record.csp_violations() == []
    context.close()


def test_guest_games_move_into_the_account_with_their_sound_and_sprites(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = guest_home(context, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Moving day", "blocks_json": GAME})
    api(page, "/api/sprites", "POST", {"project_id": project["id"], "name": "mover", "width": 1, "height": 1,
                                       "pixels": [["#ff0000"]]})
    sound = api(page, f"/api/projects/{project['id']}/audio")
    api(page, f"/api/projects/{project['id']}/audio", "PUT", {"document": sound["document"], "expected_version": 0})

    sign_in(page, live_kit)
    wait_until(page, "!document.getElementById('guestProjectsBanner').hidden")
    page.click("#moveGuestProjects")
    wait_until(page, "document.getElementById('guestProjectsBanner').hidden")
    moved = page.evaluate("""fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())
        .then(d => d.projects.find(p => p.title === 'Moving day'))""")
    assert moved and moved["blocks_json"] == GAME
    headers = "{headers: {'X-PRG32-Kit': '1'}}"
    sprites = page.evaluate(f"fetch('/api/sprites?project_id={moved['id']}', {headers}).then(r => r.json())")
    assert [sprite["name"] for sprite in sprites["sprites"]] == ["mover"]
    audio = page.evaluate(f"fetch('/api/projects/{moved['id']}/audio', {headers}).then(r => r.json())")
    assert audio["version"] == 1
    assert page.evaluate("PRG32GuestStore.list().then(rows => rows.length)") == 0
    context.close()


def test_the_storage_note_is_read_once_and_the_new_pages_are_clean(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(guest_home(context, live_kit))
    assert page.is_visible("#storageNotice")
    assert page.get_attribute("footer a[href='/privacy#storage']", "href") == "/privacy#storage"
    page.click("#storageNoticeOk")
    assert page.is_hidden("#storageNotice")
    page.reload()
    wait_until(page, "window.Kit && Kit.guest")
    assert page.is_hidden("#storageNotice")
    for path in ("/", "/privacy", "/audio-studio"):
        page.goto(live_kit + path)
        page.wait_for_load_state("networkidle")
        assert serious(page) == [], (path, json.dumps(serious(page), indent=1))
    sign_in(page, live_kit)
    page.goto(live_kit + "/admin/settings")
    wait_until(page, "document.querySelectorAll('.settings-field').length > 20")
    assert serious(page) == [], json.dumps(serious(page), indent=1)
    assert record.csp_violations() == []
    context.close()


def test_a_skin_and_the_site_name_apply_at_once(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, live_kit)
    page.click("#storageNoticeOk")            # the storage note sits over the page until read
    page.goto(live_kit + "/admin/settings#appearance")
    wait_until(page, "!!document.getElementById('setting-SITE_NAME')")
    page.fill("#setting-SITE_NAME", "Room 12 Game Lab")
    page.select_option("#setting-SKIN", "ocean")
    page.select_option("#setting-COLOR_SCHEME", "dark")
    page.click("#pane-appearance button[type=submit]")
    wait_until(page, "document.querySelector('[data-key=SITE_NAME] .badge') !== null")
    page.goto(live_kit + "/")
    assert page.inner_text(".navbar-brand").strip() == "Room 12 Game Lab"
    assert page.get_attribute("html", "data-bs-theme") == "dark"
    assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--kit-navy').trim()") == "#0c4a6e"
    # Back to the kit's own look for the other tests on this live kit.
    page.evaluate("""fetch('/api/admin/settings', {method: 'PUT', headers: {'Content-Type': 'application/json',
        'X-PRG32-Kit': '1'}, body: JSON.stringify({settings: {SITE_NAME: null, SKIN: null, COLOR_SCHEME: null}})})""")
    context.close()


def test_new_project_asks_blocks_c_or_assembly(browser, live_kit):  # noqa: F811
    """The New Project dialog offers the three kinds; C and assembly open in the IDE, ready to edit."""
    context = browser.new_context()
    page = guest_home(context, live_kit)
    page.click("#storageNoticeOk")
    for kind, mode, title in (("c", "c", "Rocket C"), ("asm", "asm", "Rocket Asm")):
        page.goto(live_kit + "/")
        wait_until(page, "window.Kit && Kit.guest")
        page.click("button[data-bs-target='#newProjectModal']")
        wait_until(page, "!!document.querySelector('#newProjectModal.show')")
        page.check(f"#newProjectKinds input[value={kind}]")
        assert page.input_value("#newProjectSummary").endswith("C." if kind == "c" else "assembly.")
        page.fill("#newProjectName", title)
        page.click("#newProjectForm button[type=submit]")
        page.wait_for_url(f"{live_kit}/ide/**")
        wait_until(page, "document.getElementById('ide').dataset.ready === 'true'")
        assert page.evaluate("PRG32Ide.mode") == mode
        assert page.get_attribute("#ideType", "data-type") == mode
    context.close()
