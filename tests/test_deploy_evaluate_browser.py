"""Deploy and Evaluate in a real browser, start to finish (docs/deploy.md, docs/evaluate.md).

The kit runs in this process with a stand-in compiler (it writes a PRG2 header, so the build
records and hashes are real), and the target is tests/fake_prg32.py. A student compiles, opens
Deploy from the project menu, looks at the console, chooses and confirms a slot, deploys, and
sees it running with its evidence label. Then Evaluate makes the protocol's cartridge, runs it,
and shows the table, the chart and the downloads. No CSP violation, no serious axe problem.

Then, one at a time: Deploy and Evaluate with the keyboard alone (Tab, arrows, Space, Enter);
the errors a student meets (a target that does not answer, a slot that changed after looking,
a full console, a connection that breaks), each said on the page with what the target holds
now; cancelling a deployment and an evaluation half way; and the four downloads and the
chart's descriptions (the image's alt text, its caption and the SVG's own title and desc).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_app
from fake_prg32 import FakePrg32, cartridge
from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, sign_in, wait_until  # noqa: F401 - fixtures
from test_i18n_browser import api

from prg32_construction_kit.sample_data import default_blocks


@pytest.fixture(scope="module")
def deploy_kit(tmp_path_factory):
    from werkzeug.serving import make_server

    from prg32_construction_kit import deploy

    patch = pytest.MonkeyPatch()

    def fake_builder(command, **_kwargs):
        title = "PRG32 Evaluation" if "prg32_evaluation" in " ".join(command) else "Deploy Me"
        Path(command[command.index("--out") + 1]).write_bytes(cartridge(title))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    patch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    patch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    patch.setattr(deploy, "POLL_SECONDS", 0.2)
    console = FakePrg32()
    app = make_app(tmp_path_factory.mktemp("deploy-kit"))
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield SimpleNamespace(url=f"http://127.0.0.1:{server.server_port}", console=console)
    server.shutdown()
    console.stop()
    patch.undo()


def test_a_student_deploys_then_evaluates_on_the_console(browser, deploy_kit):  # noqa: F811
    live_kit = deploy_kit.url
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    api(page, "/api/admin/deploy_targets", "POST", {"name": "Class console", "kind": "prg32", "address": deploy_kit.console.url})
    project = api(page, "/api/projects", "POST", {"title": "Deploy Me", "blocks_json": default_blocks()})
    api(page, f"/api/projects/{project['id']}/package", "POST", {})
    # Deploy, from the project menu.
    page.goto(f"{live_kit}/ide/{project['id']}")
    page.click('[data-ide-tool="deploy"]')
    page.wait_for_url(f"{live_kit}/deploy?project={project['id']}")
    wait_until(page, "document.querySelectorAll('#deployCartridge option[value]:not([value=\"\"])').length > 0")
    page.click("#deployLook")
    wait_until(page, "!!document.querySelector('#slot-cart3')")
    page.check("#slot-cart3")
    assert "Replace what is in cart3 (empty) on Class console" in page.text_content("#deployConfirmLabel")
    page.check("#deployConfirm")
    page.click("#deployStart")
    wait_until(page, "document.querySelector('#deployStatus').textContent === 'Running'", timeout=30)
    assert "What this run proves: physical device." in page.text_content("#deployResult")
    assert page.is_visible("#deployResult img.deploy-screen")
    assert deploy_kit.console.loaded == "cart3"
    assert serious(page) == []
    # Evaluate, from Tools.
    page.click("#toolsMenu")
    page.click('[data-ide-tool="evaluate"], a[href^="/evaluate"]')
    page.wait_for_url(f"{live_kit}/evaluate?project={project['id']}")
    page.click("#evalMake")
    wait_until(page, "document.querySelector('#evalCartridge').value !== ''", timeout=30)
    page.click("#evalLook")
    wait_until(page, "!!document.querySelector('#eval-cart4')")
    page.check("#eval-cart4")
    page.check("#evalConfirm")
    page.fill("#evalRepetitions", "2")
    page.fill("#evalWarmUp", "0")
    page.click("#evalStart")
    wait_until(page, "document.querySelector('#evalStatus').textContent.startsWith('Complete')", timeout=60)
    wait_until(page, "document.querySelectorAll('#evalTable tbody tr').length === 5")
    assert "physical device" in page.text_content("#evalTable tbody")
    wait_until(page, "document.querySelector('#evalChart').complete && document.querySelector('#evalChart').naturalWidth > 0")
    links = page.eval_on_selector_all("#evalDownloads a", "items => items.map(a => a.getAttribute('href'))")
    assert [link.split("?")[0].rsplit(".", 1)[1] for link in links] == ["csv", "json", "svg", "pdf"]
    csv = page.evaluate(f"fetch({links[0]!r}).then(r => r.text())")
    assert csv.startswith("evaluation_id,target_kind,target_name,evidence") and csv.count(",measured,") == 2 * 5 * 11
    assert record.csp_violations() == [] and serious(page) == []
    context.close()


def page_for(browser, deploy_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1440, "height": 900})
    record = Recorder(context, deploy_kit.url)
    page = record.watch(context.new_page())
    sign_in(page, deploy_kit.url)
    return context, record, page


def target_named(page, name: str, address: str) -> dict:
    found = [item for item in api(page, "/api/deploy/targets") if item["name"] == name]
    return found[0] if found else api(page, "/api/admin/deploy_targets", "POST", {"name": name, "kind": "prg32", "address": address})


def compiled_project(page, title: str) -> dict:
    project = api(page, "/api/projects", "POST", {"title": title, "blocks_json": default_blocks()})
    api(page, f"/api/projects/{project['id']}/package", "POST", {})
    return project


def open_deploy(page, deploy_kit, project: dict, target: dict) -> None:
    page.goto(f"{deploy_kit.url}/deploy?project={project['id']}")
    wait_until(page, "document.querySelectorAll('#deployCartridge option[value]:not([value=\"\"])').length > 0")
    page.select_option("#deployTarget", target["id"])


def look_and_deploy(page, slot: str) -> None:
    page.click("#deployLook")
    wait_until(page, f"!!document.querySelector('#slot-{slot}')")
    page.check(f"#slot-{slot}")
    page.check("#deployConfirm")
    page.click("#deployStart")


def deploy_status(page) -> str:
    return page.text_content("#deployStatus")


def tab_to(page, element_id: str, presses: int = 40) -> None:
    """Press Tab until the element has the focus: it is reachable with the keyboard, in page order."""
    for _ in range(presses):
        if page.evaluate("document.activeElement && document.activeElement.id") == element_id:
            return
        page.keyboard.press("Tab")
    raise AssertionError(f"#{element_id} is not reached with Tab")


def test_deploy_and_evaluate_with_the_keyboard_alone(browser, deploy_kit):  # noqa: F811
    context, record, page = page_for(browser, deploy_kit)
    target = target_named(page, "Class console", deploy_kit.console.url)
    project = compiled_project(page, "Deploy Me")
    open_deploy(page, deploy_kit, project, target)
    page.focus("#deployTarget")
    tab_to(page, "deployLook")
    page.keyboard.press("Enter")
    wait_until(page, "!!document.querySelector('#slot-cart1')")
    tab_to(page, "slot-cart0")                     # Tab enters the slot group on its first slot
    page.keyboard.press("ArrowDown")               # arrows move through the slots and choose one
    assert page.is_checked("#slot-cart1")
    tab_to(page, "deployConfirm")
    page.keyboard.press("Space")
    assert page.is_checked("#deployConfirm")
    tab_to(page, "deployStart")
    page.keyboard.press("Enter")
    wait_until(page, "document.querySelector('#deployStatus').textContent === 'Running'", timeout=30)
    assert deploy_kit.console.loaded == "cart1"
    # The focus ring shows where the keyboard is.
    page.focus("#deployLook")
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    assert page.evaluate("getComputedStyle(document.activeElement).boxShadow !== 'none' || "
                         "getComputedStyle(document.activeElement).outlineStyle !== 'none'")

    page.goto(f"{deploy_kit.url}/evaluate?project={project['id']}")
    wait_until(page, "!!document.querySelector('#evalCartridge option')")
    page.focus("#evalMake")
    page.keyboard.press("Enter")                   # makes (or updates) the protocol's cartridge
    wait_until(page, "document.querySelector('#evalCartridge').value !== '' && !document.querySelector('#evalMake').disabled",
               timeout=30)
    page.select_option("#evalTarget", target["id"])
    page.focus("#evalTarget")
    tab_to(page, "evalLook")
    page.keyboard.press("Enter")
    wait_until(page, "!!document.querySelector('#eval-cart5')")
    page.focus("#eval-cart5")
    page.keyboard.press("Space")
    tab_to(page, "evalRepetitions")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("2")
    tab_to(page, "evalWarmUp")
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("0")
    tab_to(page, "evalConfirm")
    page.keyboard.press("Space")
    tab_to(page, "evalStart")
    page.keyboard.press("Enter")
    wait_until(page, "document.querySelector('#evalStatus').textContent.startsWith('Complete')", timeout=60)
    wait_until(page, "document.querySelectorAll('#evalTable tbody tr').length === 5")
    # The metric is chosen with the keyboard too, and the table follows it.
    before = page.text_content("#evalTableCaption")
    page.focus("#evalMetric")
    page.keyboard.type("D")                        # a select's type-ahead: "Draw time, mean" (arrows open a list on macOS)
    assert page.input_value("#evalMetric") == "draw_us_mean"
    wait_until(page, f"document.querySelector('#evalTableCaption').textContent !== {json.dumps(before)}")
    # The downloads are links: reached with Tab and taken with Enter.
    page.focus("#evalMetric")
    for _ in range(20):
        if page.evaluate("!!document.activeElement.closest('#evalDownloads')"):
            break
        page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.matches('#evalDownloads a')")
    with page.expect_download() as download:
        page.keyboard.press("Enter")
    assert download.value.suggested_filename.endswith(".csv")
    assert record.csp_violations() == [] and serious(page) == []
    context.close()


def test_errors_are_said_on_the_page_with_what_the_target_holds_now(browser, deploy_kit):  # noqa: F811
    context, record, page = page_for(browser, deploy_kit)
    console = deploy_kit.console
    project = compiled_project(page, "Deploy Me")
    # A target that does not answer: said where the slots would be, and no slot can be chosen.
    gone = target_named(page, "Unplugged console", "http://127.0.0.1:9")
    open_deploy(page, deploy_kit, project, gone)
    page.click("#deployLook")
    wait_until(page, "!!document.querySelector('#deployProbe .alert-danger')", timeout=30)
    assert page.text_content("#deployProbe .alert-danger").strip()
    assert page.is_disabled("#deployStart") and page.query_selector("input[name=deploySlot]") is None
    assert serious(page) == []

    target = target_named(page, "Class console", console.url)
    try:
        # A slot that changed after the student looked: refused, nothing overwritten.
        open_deploy(page, deploy_kit, project, target)
        page.click("#deployLook")
        wait_until(page, "!!document.querySelector('#slot-cart6')")
        console.slots["cart6"] = cartridge("Someone Else")
        page.check("#slot-cart6")
        page.check("#deployConfirm")
        page.click("#deployStart")
        wait_until(page, "document.querySelector('#deployStatus').textContent === 'Refused'", timeout=30)
        assert "cart6 holds something else now" in page.text_content("#deployResult .alert-danger")
        assert console.name_of(console.slots["cart6"]) == "Someone Else"
        assert serious(page) == []

        # A full console, then a connection that breaks during every upload.
        for fail, status in (("full", "Refused"), ("drop_upload", "Failed")):
            console.fail, console.drops = fail, 10
            open_deploy(page, deploy_kit, project, target)
            look_and_deploy(page, "cart7")
            wait_until(page, f"document.querySelector('#deployStatus').textContent === {json.dumps(status)}", timeout=60)
            alert = page.text_content("#deployResult .alert-danger")
            assert "The target now:" in alert, (fail, alert)
            assert page.get_attribute("#deployProgress .progress-bar", "class").count("bg-danger") == 1
            assert not page.is_disabled("#deployLook")             # the student can look and try again
    finally:
        console.fail, console.drops = None, 0
    assert record.csp_violations() == []
    context.close()


def test_a_deployment_and_an_evaluation_can_be_cancelled_half_way(browser, deploy_kit):  # noqa: F811
    context, record, page = page_for(browser, deploy_kit)
    console = deploy_kit.console
    target = target_named(page, "Class console", console.url)
    project = compiled_project(page, "Deploy Me")
    try:
        console.fail = "never_runs"                  # the deployment waits for the cartridge to run
        open_deploy(page, deploy_kit, project, target)
        look_and_deploy(page, "cart2")
        wait_until(page, "document.querySelector('#deployStatus').textContent === 'Checking that it runs'", timeout=30)
        assert not page.is_disabled("#deployCancel")
        page.click("#deployCancel")
        wait_until(page, "document.querySelector('#deployStatus').textContent === 'Cancelled'", timeout=30)
        assert "The target now:" in page.text_content("#deployResult .alert-secondary")
        assert page.is_disabled("#deployCancel")
    finally:
        console.fail = None

    console.suite_seconds = 60                       # a suite that would take a minute
    try:
        page.goto(f"{deploy_kit.url}/evaluate?project={project['id']}")
        wait_until(page, "!!document.querySelector('#evalCartridge option')")
        page.click("#evalMake")
        wait_until(page, "document.querySelector('#evalCartridge').value !== '' && !document.querySelector('#evalMake').disabled",
                   timeout=30)
        page.select_option("#evalTarget", target["id"])
        page.click("#evalLook")
        wait_until(page, "!!document.querySelector('#eval-cart4')")
        page.check("#eval-cart4")
        page.check("#evalConfirm")
        page.fill("#evalRepetitions", "2")
        page.fill("#evalWarmUp", "0")
        page.click("#evalStart")
        wait_until(page, "!document.querySelector('#evalCancel').disabled", timeout=30)
        page.click("#evalCancel")
        wait_until(page, "document.querySelector('#evalStatus').textContent.startsWith('Cancelled')", timeout=30)
        latest = api(page, "/api/evaluations")[0]
        assert latest["status"] == "cancelled" and latest["cancel_requested"] is True
    finally:
        console.suite_seconds = 0.2
    assert record.csp_violations() == [] and serious(page) == []
    context.close()


def test_the_downloads_and_the_chart_say_what_they_hold(browser, deploy_kit):  # noqa: F811
    context, record, page = page_for(browser, deploy_kit)
    complete = [item for item in api(page, "/api/evaluations") if item["status"] == "complete"]
    assert complete, "the evaluations above made at least one"
    page.goto(f"{deploy_kit.url}/evaluate")
    page.click(f".eval-open[data-id='{complete[0]['id']}']")
    wait_until(page, "document.querySelector('#evalChart').complete && document.querySelector('#evalChart').naturalWidth > 0")
    metric = page.evaluate("document.querySelector('#evalMetric option:checked').textContent").split(" (")[0]
    alt = page.get_attribute("#evalChart", "alt")
    assert alt.startswith(f"Bar chart of {metric} per case for Class console") and "same numbers are in the table" in alt
    assert "Emulator times are not PRG32 console times" in page.text_content("#evalChartCaption")
    assert metric in page.text_content("#evalTableCaption")

    files = {}
    for link in page.query_selector_all("#evalDownloads a"):
        assert link.get_attribute("download") is not None and link.text_content().strip()
        with page.expect_download() as download:
            link.click()
        path = download.value.path()
        files[download.value.suggested_filename.rsplit(".", 1)[1]] = Path(path).read_bytes()
    assert sorted(files) == ["csv", "json", "pdf", "svg"]
    assert files["csv"].decode().startswith("evaluation_id,target_kind,target_name,evidence")
    dataset = json.loads(files["json"])
    assert dataset["protocol"]["caveat"] and dataset["rows"]
    svg = files["svg"].decode()
    assert 'role="img"' in svg and '<title id="chart-title">' in svg and '<desc id="chart-desc">' in svg
    assert files["pdf"].startswith(b"%PDF-")
    assert record.csp_violations() == [] and serious(page) == []
    context.close()
