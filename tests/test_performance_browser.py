"""Performance budgets for classroom devices, in a real browser (docs/performance.md).

A low-end classroom laptop or Chromebook is stood in for by Chromium with its CPU slowed
down 4x (DevTools CPU throttling). The kit is served locally, as on a school server.
Budgets are generous on purpose: they catch a page that becomes much heavier or slower,
not small changes. Each test prints what it measured, for the record.

| What | Budget |
| --- | --- |
| Dashboard ready (projects listed) | 4 s |
| IDE ready (editors and blocks loaded) | 8 s |
| Player: a real cartridge running (first frames drawn) | 6 s |
| JavaScript a page downloads (uncompressed) | dashboard 0.6 MB, IDE 12 MB |
"""

from __future__ import annotations

import time

from test_browser_offline import browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures

CPU_SLOWDOWN = 4
BUDGETS = {"dashboard_s": 4.0, "ide_s": 8.0, "player_s": 6.0, "dashboard_js_mb": 0.6, "ide_js_mb": 12.0}


def slow_page(context):
    page = context.new_page()
    session = context.new_cdp_session(page)
    session.send("Emulation.setCPUThrottlingRate", {"rate": CPU_SLOWDOWN})
    return page


def javascript_bytes(page) -> int:
    return page.evaluate("performance.getEntriesByType('resource').filter(e => e.initiatorType === 'script' ||"
                         " e.name.endsWith('.js')).reduce((n, e) => n + (e.decodedBodySize || 0), 0)")


def record(name, value, budget):
    print(f"\nperformance: {name} = {value:.2f} (budget {budget})")
    assert value < budget, f"{name} is {value:.2f}, over its budget of {budget}"


def test_dashboard_is_ready_quickly_on_a_slow_laptop(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = slow_page(context)
    sign_in(page, live_kit)
    started = time.monotonic()
    page.goto(live_kit + "/")
    wait_until(page, "document.querySelectorAll('#projectGrid .project-card').length > 0", timeout=60)
    record("dashboard_s", time.monotonic() - started, BUDGETS["dashboard_s"])
    record("dashboard_js_mb", javascript_bytes(page) / 1e6, BUDGETS["dashboard_js_mb"])
    context.close()


def test_ide_is_ready_on_a_slow_laptop(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    page = slow_page(context)
    sign_in(page, live_kit)
    project_id = page.evaluate("fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())"
                               ".then(d => d.projects.find(p => p.title === 'Pong').id)")
    started = time.monotonic()
    page.goto(f"{live_kit}/ide/{project_id}")
    wait_until(page, "document.getElementById('ide').dataset.ready === 'true'", timeout=60)
    record("ide_s", time.monotonic() - started, BUDGETS["ide_s"])
    record("ide_js_mb", javascript_bytes(page) / 1e6, BUDGETS["ide_js_mb"])
    context.close()


def test_a_real_cartridge_runs_quickly_in_the_player(browser, live_kit):  # noqa: F811
    from pathlib import Path

    cartridge = Path(__file__).resolve().parent / "fixtures" / "debug" / "pong.prg32"
    context = browser.new_context()
    page = slow_page(context)
    sign_in(page, live_kit)
    page.goto(live_kit + "/player")
    started = time.monotonic()
    page.set_input_files("#cartridgeFile", str(cartridge))
    wait_until(page, "!document.getElementById('playPause').disabled", timeout=60)
    page.click("#playPause")
    wait_until(page, "/Frame ([3-9]|[1-9][0-9])/.test(document.getElementById('playerStatus').textContent)", timeout=60)
    record("player_s", time.monotonic() - started, BUDGETS["player_s"])
    context.close()
