"""Deploy and Evaluate in a real browser, start to finish (docs/deploy.md, docs/evaluate.md).

The kit runs in this process with a stand-in compiler (it writes a PRG2 header, so the build
records and hashes are real), and the target is tests/fake_prg32.py. A student compiles, opens
Deploy from the project menu, looks at the console, chooses and confirms a slot, deploys, and
sees it running with its evidence label. Then Evaluate makes the protocol's cartridge, runs it,
and shows the table, the chart and the downloads. No CSP violation, no serious axe problem.
"""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from conftest import make_app
from fake_prg32 import FakePrg32, cartridge
from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, sign_in, wait_until  # noqa: F401 - fixtures
from test_i18n_browser import api


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
    project = api(page, "/api/projects", "POST", {"title": "Deploy Me"})
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
