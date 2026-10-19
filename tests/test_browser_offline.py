"""Real-browser checks of the self-contained frontend (refinement phase 1, ADR-0012).

These drive Google Chrome (or Playwright's Chromium) through Playwright against
a live kit on 127.0.0.1. They skip cleanly when Playwright or a browser is not
installed, except where PRG32_REQUIRE_BROWSER=1 is set (the CI browser job): there a
missing browser, Playwright or golden cartridge fails the run instead of hiding it.
What they prove, in a real browser:

- every page loads only from the kit itself (no CDN, no third-party request);
- no Content Security Policy violation is reported;
- Blockly is editable;
- after one online visit, a cold offline start shows the static offline page with
  an editable Blockly scratchpad, and the offline player runs a real cartridge;
- a page that is already open keeps working when the network goes away;
- the service worker caches static files only (never pages or API answers).
"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from conftest import ADMIN_PASSWORD, make_app

# The CI browser job sets this, so the browser tests can never pass by skipping there.
REQUIRE_BROWSER = os.environ.get("PRG32_REQUIRE_BROWSER") == "1"


def skip_or_fail(reason: str):
    """Skip on a learner's laptop; fail in the CI browser job."""
    if REQUIRE_BROWSER:
        pytest.fail(f"PRG32_REQUIRE_BROWSER=1 but {reason}", pytrace=False)
    pytest.skip(reason)


try:
    import playwright.sync_api as playwright_api
except ImportError:
    if REQUIRE_BROWSER:
        raise
    pytest.skip("Playwright is not installed (pip install -r requirements-browser.txt)", allow_module_level=True)
ROOT = Path(__file__).resolve().parent.parent
GOLDEN = Path(os.environ.get("PRG32QT_DIR") or ROOT.parent / "PRG32-QT") / "tests" / "fixtures" / "Asteroids.prg32"


@pytest.fixture(scope="module")
def live_kit(tmp_path_factory):
    from werkzeug.serving import make_server

    app = make_app(tmp_path_factory.mktemp("browser-kit"))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({"channel": "chrome"}, {}):
            try:
                launched = playwright.chromium.launch(headless=True, **options)
                break
            except Exception:  # noqa: BLE001, S112 - this browser is not installed: try the next, then skip
                continue
        if launched is None:
            skip_or_fail("no Chrome or Playwright Chromium is installed")
        yield launched
        launched.close()


class Recorder:
    """Every request and every console message of a browser context."""

    def __init__(self, context, origin):
        self.origin = origin
        self.requests: list[str] = []
        self.console: list[str] = []
        context.on("request", lambda request: self.requests.append(request.url))

    def watch(self, page):
        page.on("console", lambda message: self.console.append(f"{message.type}: {message.text}"))
        return page

    def third_party(self):
        return [url for url in self.requests
                if urlsplit(url).scheme not in ("data", "blob") and not url.startswith(self.origin)]

    def csp_violations(self):
        return [line for line in self.console if "Content Security Policy" in line or "Refused to" in line]


def wait_until(page, expression: str, timeout: float = 15.0):
    """Poll a JavaScript expression with page.evaluate.

    Playwright's wait_for_function runs its predicate through eval inside the page, which the
    kit's Content Security Policy forbids (as it should); page.evaluate is not affected.
    """
    import time

    deadline = time.monotonic() + timeout
    while True:
        try:
            if page.evaluate(expression):
                return
        except playwright_api.Error:
            pass  # the page is still loading
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for: {expression}")
        time.sleep(0.1)


def sign_in(page, live_kit):
    page.goto(f"{live_kit}/auth/login")
    page.fill("input[name=username]", "admin")
    page.fill("input[name=password]", ADMIN_PASSWORD)
    page.click("button[type=submit]")
    page.wait_for_url(f"{live_kit}/")


def first_project(page, live_kit):
    return page.evaluate("fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())"
                         ".then(d => d.projects[0].id)")


def blockly_is_editable(page) -> bool:
    return page.evaluate("""() => {
        const ws = PRG32Blocks.getWorkspace();
        const before = ws.getAllBlocks(false).length;
        const block = ws.newBlock('prg32_on_start'); block.initSvg(); block.render();
        return !ws.options.readOnly && ws.getAllBlocks(false).length === before + 1;
    }""")


def test_pages_load_only_from_the_kit_without_csp_violations(browser, live_kit):
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = first_project(page, live_kit)
    for path in ("/", f"/projects/{project}", "/player", "/publish", "/sprites", "/artifacts"):
        page.goto(live_kit + path)
        page.wait_for_load_state("networkidle")
    page.goto(f"{live_kit}/projects/{project}")
    wait_until(page, "window.PRG32Blocks && PRG32Blocks.getWorkspace()")
    assert blockly_is_editable(page)
    # Bootstrap's icon font and Blockly's media come from the kit too.
    assert any("/static/vendor/bootstrap-icons/" in url for url in record.requests)
    assert record.third_party() == []
    assert record.csp_violations() == []
    context.close()


def test_cold_offline_start_shows_an_editable_scratchpad(browser, live_kit):
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = first_project(page, live_kit)
    page.goto(f"{live_kit}/projects/{project}")
    page.evaluate("navigator.serviceWorker.ready")
    wait_until(page, "caches.keys().then(keys => keys.length > 0)")
    wait_until(page, "caches.open('prg32-kit-v14').then(c => c.match('/static/offline.html')).then(Boolean)")
    page.close()

    context.set_offline(True)
    offline = record.watch(context.new_page())
    offline.goto(f"{live_kit}/projects/{project}")  # a signed-in page: not cached, so the offline page
    wait_until(offline, "window.PRG32Blocks && PRG32Blocks.getWorkspace()")
    assert "Offline" in offline.title()
    assert blockly_is_editable(offline)
    offline.click("#offlinePlay")
    wait_until(offline, "document.getElementById('debugState').textContent.startsWith('Frame')")
    # The scratchpad stays in this browser after a reload.
    offline.reload()
    wait_until(offline, "window.PRG32Blocks && PRG32Blocks.getWorkspace()")
    assert offline.evaluate("PRG32Blocks.getWorkspace().getAllBlocks(false).length") >= 1
    assert record.third_party() == []
    assert record.csp_violations() == []
    context.close()


def test_offline_player_runs_a_real_cartridge(browser, live_kit):
    if not GOLDEN.is_file():
        skip_or_fail("no PRG32-QT checkout with tests/fixtures/Asteroids.prg32 (set PRG32QT_DIR)")
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, live_kit)
    page.evaluate("navigator.serviceWorker.ready")
    wait_until(page, "caches.open('prg32-kit-v14').then(c => c.match('/static/wasm/prg32-core.wasm')).then(Boolean)")
    context.set_offline(True)
    player = context.new_page()
    player.goto(f"{live_kit}/static/offline-player.html")
    player.set_input_files("#cartridgeFile", str(GOLDEN))
    wait_until(player, "!document.getElementById('playPause').disabled")
    player.click("#playPause")
    wait_until(player, "/Frame [1-9]/.test(document.getElementById('playerStatus').textContent)")
    context.close()


def test_an_open_page_keeps_working_when_the_network_goes(browser, live_kit):
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, live_kit)
    project = first_project(page, live_kit)
    page.goto(f"{live_kit}/projects/{project}")
    wait_until(page, "window.PRG32Blocks && PRG32Blocks.getWorkspace()")
    context.set_offline(True)
    assert blockly_is_editable(page)
    page.click("#runGame")
    wait_until(page, "document.getElementById('debugState').textContent.startsWith('Frame')")
    page.click("#saveProject")  # the server is unreachable: a clear message, no crash
    page.wait_for_selector(".toast", timeout=10000)
    context.close()


def test_the_service_worker_caches_static_files_only(browser, live_kit):
    context = browser.new_context()
    page = context.new_page()
    sign_in(page, live_kit)
    project = first_project(page, live_kit)
    for path in ("/", f"/projects/{project}", "/player", "/api/projects"):
        page.goto(live_kit + path)
    page.evaluate("navigator.serviceWorker.ready")
    cached = page.evaluate("""async () => {
        const urls = [];
        for (const key of await caches.keys()) {
            for (const request of await (await caches.open(key)).keys()) urls.push(new URL(request.url).pathname);
        }
        return urls;
    }""")
    assert cached and all(path.startswith("/static/") for path in cached), cached
    scope = page.evaluate("navigator.serviceWorker.getRegistration().then(r => new URL(r.scope).pathname)")
    assert scope == "/"
    context.close()
