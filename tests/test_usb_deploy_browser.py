"""Deploy over USB in a real browser, with a pretend PRG32 behind Web Serial.

Playwright cannot press the browser's own port chooser, so navigator.serial is
replaced by tests/js/fake_prg32_serial.js before the page loads. Everything
else is real: the Deploy page, usb_deploy.js, prg32_usb_protocol.js, the kit's
artifact download and SHA-256 check, the Content Security Policy and the
translations. The physical counterpart is tools/usb_device_check.mjs.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from test_accounts_browser import serious
from test_browser_offline import Recorder, browser, sign_in, wait_until  # noqa: F401 - fixtures
from test_deploy_evaluate_browser import compiled_project, deploy_kit  # noqa: F401 - fixture
from test_i18n_browser import api

FAKE = (Path(__file__).resolve().parent / "js" / "fake_prg32_serial.js").read_text(encoding="utf-8")


def usb_page(browser, kit, **options):  # noqa: F811
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_init_script(FAKE + f"\nwindow.__fakeSerial = installFakeSerial(navigator, {json.dumps(options)});")
    record = Recorder(context, kit.url)
    page = record.watch(context.new_page())
    sign_in(page, kit.url)
    return context, record, page


def open_usb_deploy(page, kit, title: str, slot: str, command: str) -> dict:
    project = compiled_project(page, title)
    page.goto(f"{kit.url}/deploy?project={project['id']}")
    wait_until(page, "document.querySelectorAll('#deployCartridge option[value]:not([value=\"\"])').length > 0")
    page.select_option("#usbDeploySlot", slot)
    page.select_option("#usbDeployCommand", command)
    assert page.is_disabled("#usbDeployStart")
    page.check("#usbDeployConfirm")
    return project


def device(page, field: str):
    return page.evaluate(f"window.__fakeSerial.port.device.{field}")


def test_a_student_stores_a_cartridge_over_usb(browser, deploy_kit):  # noqa: F811
    context, record, page = usb_page(browser, deploy_kit)
    open_usb_deploy(page, deploy_kit, "USB Store", "cart5", "store")
    page.click("#usbDeployStart")
    wait_until(page, "document.querySelector('#usbDeployStatus .text-success') !== null", timeout=30)
    assert page.text_content("#usbDeployStatus") == "cart5 holds the cartridge. The PRG32 is back in setup."
    assert page.get_attribute("#usbDeployProgress", "aria-valuenow") == "100"
    log = page.text_content("#usbDeployLog")
    assert "Device firmware: fake (esp32c6)" in log and "chunk: 4096 bytes" in log
    stored = page.evaluate("Array.from(window.__fakeSerial.port.device.slots.cart5 || [])")
    assert bytes(stored[:4]) == b"PRG2"
    assert page.evaluate("window.__fakeSerial.requestPortFilters") == [{"usbVendorId": 0x303A, "usbProductId": 0x1001}]
    assert device(page, "setSignalsCalls") == 0
    assert device(page, "closed") == 1
    assert record.csp_violations() == [] and serious(page) == []
    context.close()


def test_run_starts_the_cartridge_and_reuses_the_authorized_port(browser, deploy_kit):  # noqa: F811
    context, _record, page = usb_page(browser, deploy_kit, authorized=True)
    open_usb_deploy(page, deploy_kit, "USB Run", "cart2", "run")
    page.click("#usbDeployStart")
    wait_until(page, "document.querySelector('#usbDeployStatus .text-success') !== null", timeout=30)
    assert page.text_content("#usbDeployStatus") == "cart2 holds the cartridge and it is running."
    assert page.evaluate("window.__fakeSerial.requestPortFilters") is None
    context.close()


def test_debug_is_refused_before_the_slot_is_touched(browser, deploy_kit):  # noqa: F811
    context, _record, page = usb_page(browser, deploy_kit)
    open_usb_deploy(page, deploy_kit, "USB Debug", "cart1", "debug")
    page.click("#usbDeployStart")
    wait_until(page, "document.querySelector('#usbDeployStatus .text-danger') !== null", timeout=30)
    message = page.text_content("#usbDeployStatus")
    assert "PRG32-QT" in message and "Nothing was written." in message
    assert device(page, "requests") == [0x01]
    context.close()


def test_closing_the_port_chooser_writes_nothing(browser, deploy_kit):  # noqa: F811
    context, _record, page = usb_page(browser, deploy_kit, cancelChooser=True)
    open_usb_deploy(page, deploy_kit, "USB Cancel", "cart0", "store")
    page.click("#usbDeployStart")
    wait_until(page, "document.querySelector('#usbDeployStatus .text-danger') !== null", timeout=30)
    assert page.text_content("#usbDeployStatus") == "No USB device was selected; nothing was written."
    assert device(page, "opened") == 0
    assert not page.is_disabled("#usbDeployStart")
    context.close()


def test_the_page_starts_with_the_newest_esp32c6_cartridge_when_a_build_crosses_a_second(browser, deploy_kit, monkeypatch):  # noqa: F811
    # Every saved time is one second after the last, so qemu, saved after esp32c6, always looks newer.
    now = [datetime.now(timezone.utc).replace(microsecond=0)]

    def ticking():
        now[0] += timedelta(seconds=1)
        return now[0].isoformat()
    monkeypatch.setattr(sys.modules["prg32_construction_kit.db"], "utcnow", ticking)
    context, _record, page = usb_page(browser, deploy_kit)
    project = compiled_project(page, "USB Twice")
    first = api(page, f"/api/artifacts?kind=prg32_cartridge&project_id={project['id']}", "GET")["artifacts"]
    api(page, f"/api/projects/{project['id']}/package", "POST", {})
    second = [item for item in api(page, f"/api/artifacts?kind=prg32_cartridge&project_id={project['id']}", "GET")["artifacts"]
              if item["id"] not in {old["id"] for old in first}]
    newest = next(item["id"] for item in second if item["metadata"]["architecture"] == "esp32c6")
    page.goto(f"{deploy_kit.url}/deploy?project={project['id']}")
    wait_until(page, "document.querySelectorAll('#deployCartridge option[value]:not([value=\"\"])').length > 0")
    assert page.input_value("#deployCartridge") == newest
    page.select_option("#usbDeploySlot", "cart0")
    page.check("#usbDeployConfirm")
    assert not page.is_disabled("#usbDeployStart")
    context.close()


def test_performance_results_are_read_over_usb(browser, deploy_kit):  # noqa: F811
    context, _record, page = usb_page(browser, deploy_kit, authorized=True,
                                      performanceChunks=['{"cases":', '[{"name":"fill"}]}'])
    page.goto(f"{deploy_kit.url}/deploy")
    page.click("#usbPerformanceGet")
    wait_until(page, "!document.querySelector('#usbPerformanceResult').classList.contains('d-none')", timeout=30)
    assert json.loads(page.text_content("#usbPerformanceResult")) == {"cases": [{"name": "fill"}]}
    assert device(page, "performanceFlags") == [1, 0]
    context.close()


def test_the_usb_card_explains_a_browser_without_web_serial(browser, deploy_kit):  # noqa: F811
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    context.add_init_script("Object.defineProperty(navigator, 'serial', { value: undefined, configurable: true });")
    page = context.new_page()
    sign_in(page, deploy_kit.url)
    page.goto(f"{deploy_kit.url}/deploy")
    wait_until(page, "!document.querySelector('#usbDeployUnsupported').classList.contains('d-none')")
    assert page.is_disabled("#usbDeployStart") and page.is_disabled("#usbPerformanceGet")
    assert api(page, "/api/deploy/targets") is not None
    context.close()
