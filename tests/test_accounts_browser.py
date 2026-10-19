"""Account, Classes and school sign-in pages in a real browser (ADR-0016).

No CSP violation and no serious accessibility problem on the pages that manage
identities, sessions, API tokens, classes and identity providers; a teacher makes a
class and adds a student from the page.
"""

from __future__ import annotations

import json
from pathlib import Path

from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures

AXE = Path(__file__).resolve().parent / "vendor" / "axe-core" / "4.10.2" / "axe.min.js"


def serious(page):
    page.wait_for_timeout(300)  # let Bootstrap's colour transitions finish
    page.evaluate(AXE.read_text())
    found = page.evaluate("""axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})
        .then(r => r.violations.filter(v => ['serious', 'critical'].includes(v.impact))
        .map(v => ({id: v.id, target: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
    return found


def test_account_pages_are_clean_and_classes_work(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = context.new_page()
    record.watch(page)
    sign_in(page, live_kit)
    for path in ("/account", "/admin/users", "/admin/identity", "/classes"):
        page.goto(live_kit + path)
        page.wait_for_load_state("networkidle")
        assert serious(page) == [], (path, json.dumps(serious(page), indent=1))
    # An administrator makes a class and adds a student from the page.
    page.evaluate("""fetch('/api/users', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-PRG32-Kit': '1'},
        body: JSON.stringify({username: 'pupil', email: 'pupil@school.test', password: 'pupil-password-1'})})""")
    page.goto(live_kit + "/classes")
    page.fill("#className", "3B")
    page.press("#className", "Enter")
    wait_until(page, "document.querySelectorAll('.add-member').length === 1")
    page.fill(".add-member input[name=username]", "pupil")
    page.press(".add-member input[name=username]", "Enter")
    wait_until(page, "document.getElementById('classCards').innerText.includes('pupil')")
    assert record.csp_violations() == [] and record.third_party() == []
    context.close()
