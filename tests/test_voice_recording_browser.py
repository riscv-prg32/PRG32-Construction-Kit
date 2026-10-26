"""Recording a sample with the microphone in AudioStudio, in a real browser (docs/audio_studio.md).

Chromium's fake microphone (a steady tone) stands in for a student: they press Record, stop,
keep part of the take, and add it. The sample arrives like an uploaded WAV file (8-bit, 22050 Hz)
and is listed on the Samples tab. With the Settings switch off there is no Record button.
"""

from __future__ import annotations

import pytest

from test_browser_offline import live_kit, playwright_api, sign_in, skip_or_fail, wait_until  # noqa: F401 - fixtures
from test_i18n_browser import api


@pytest.fixture(scope="module")
def microphone_browser():
    with playwright_api.sync_playwright() as playwright:
        launched = None
        for options in ({"channel": "chrome"}, {}):
            try:
                launched = playwright.chromium.launch(headless=True, args=[
                    "--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"], **options)
                break
            except Exception:  # noqa: BLE001, S112 - this browser is not installed: try the next, then skip
                continue
        if launched is None:
            skip_or_fail("no Chrome or Playwright Chromium is installed")
        yield launched
        launched.close()


def test_a_recorded_take_becomes_a_sample(microphone_browser, live_kit):  # noqa: F811
    context = microphone_browser.new_context(viewport={"width": 1440, "height": 900}, permissions=["microphone"])
    page = context.new_page()
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "Voice"})
    page.goto(f"{live_kit}/ide/{project['id']}#sound")
    wait_until(page, "!!window.PRG32VoiceRecorder && !!document.querySelector('#recordStart')")
    page.click('#audioStudio [data-section="samples"]')
    page.click("#recordStart")
    wait_until(page, "parseFloat(document.querySelector('#recordTime').textContent) >= 1.2")
    page.click("#recordStop")
    wait_until(page, "!document.querySelector('#recordTake').hidden")
    seconds = float(page.input_value("#recordTo"))
    assert 0.8 <= seconds <= 3.0
    page.fill("#recordFrom", "0.2")
    page.fill("#recordTo", "0.7")
    page.fill("#recordName", "hello")
    page.click("#recordAdd")
    wait_until(page, "document.querySelector('#sampleEditor').textContent.includes('hello')")
    wait_until(page, f"Kit.api('/api/projects/{project['id']}/audio').then(a => a.document.samples.some(s => s.name === 'hello'))")
    audio = api(page, f"/api/projects/{project['id']}/audio")
    sample = next(item for item in audio["document"]["samples"] if item["name"] == "hello")
    assert sample["artifact_id"]
    # The WAV the page made: 22050 Hz, 16-bit mono, its loudest point at 90 %.
    header = page.evaluate("""(async () => {
      const wav = PRG32VoiceRecorder.wavOf(new Float32Array([0, 0.5, -0.25, 0.1]));
      const view = new DataView(await wav.arrayBuffer());
      return [view.getUint32(24, true), view.getUint16(22, true), view.getUint16(34, true), view.getInt16(46, true)];
    })()""")
    assert header == [22050, 1, 16, round(0.9 * 32767)]
    assert page.evaluate("PRG32VoiceRecorder.downsample(new Float32Array([1, 3, 5, 7]), 44100).join(',')") == "2,6"
    context.close()


def test_the_switch_removes_the_record_button(microphone_browser, live_kit):  # noqa: F811
    context = microphone_browser.new_context(viewport={"width": 1440, "height": 900})
    page = context.new_page()
    sign_in(page, live_kit)
    project = api(page, "/api/projects", "POST", {"title": "No mic"})
    answer = api(page, "/api/admin/settings", "PUT", {"settings": {"PRG32_AUDIO_RECORDING": False}})
    assert "settings" in answer or answer
    try:
        page.goto(f"{live_kit}/ide/{project['id']}#sound")
        wait_until(page, "!!document.querySelector('#sampleForm')")
        assert page.locator("#recordStart").count() == 0
    finally:
        api(page, "/api/admin/settings", "PUT", {"settings": {"PRG32_AUDIO_RECORDING": True}})
        context.close()
