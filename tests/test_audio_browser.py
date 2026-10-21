"""The Player's sound in a real browser (ADR-0021).

The conformance cartridge (tests/fixtures/audio) is opened on the Player page and played:
pressing Play starts the AudioContext (browsers allow sound only after a click), the
firmware engine's stereo frames are scheduled after every frame, the amount queued stays
bounded, Pause stops every scheduled buffer, and the page has no CSP violation.
"""

from __future__ import annotations

from pathlib import Path

from test_browser_offline import Recorder, browser, live_kit, sign_in, wait_until  # noqa: F401 - fixtures

CARTRIDGE = Path(__file__).resolve().parent / "fixtures" / "audio" / "conformance.prg32"


def test_the_player_plays_the_engines_stereo_frames(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    page.goto(live_kit + "/player")
    page.set_input_files("#cartridgeFile", str(CARTRIDGE))
    wait_until(page, "!document.getElementById('playPause').disabled", timeout=30)
    page.click("#playPause")
    wait_until(page, "/Frame ([4-9][0-9]|[1-9][0-9]{2})/.test(document.getElementById('playerStatus').textContent)",
               timeout=30)
    audio = page.evaluate("({state: prg32Player.audio.context.state, queued: prg32Player.audio.sources.size,"
                          " ahead: prg32Player.audio.nextTime - prg32Player.audio.context.currentTime})")
    assert audio["state"] == "running"
    assert audio["queued"] > 0 and audio["ahead"] <= 0.35       # scheduled, and never piling up
    assert page.evaluate("prg32Player.core._prg32_audio_frames()") < 1000   # taken every frame
    page.click("#playPause")                                       # pause
    wait_until(page, "prg32Player.audio.sources.size === 0", timeout=10)
    assert record.csp_violations() == []
    context.close()


AXE = Path(__file__).resolve().parent / "vendor" / "axe-core" / "4.10.2" / "axe.min.js"


def test_audio_studio_edits_previews_saves_and_reloads(browser, live_kit):  # noqa: F811
    import json

    context = browser.new_context(accept_downloads=True)
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project_id = page.evaluate("""fetch('/api/projects', {method: 'POST', headers: {'Content-Type':
        'application/json', 'X-PRG32-Kit': '1'}, body: JSON.stringify({title: 'Studio'})}).then(r => r.json()).then(p => p.id)""")
    page.goto(f"{live_kit}/audio-studio/{project_id}")
    wait_until(page, "!!window.PRG32AudioStudio && !!PRG32AudioStudio.document()", timeout=30)

    # A voice plays through the PRG32 engine after the click: a voice is active, frames come out.
    page.click("#voiceEditor button:has-text('Try it')")
    wait_until(page, "PRG32AudioStudio.engine.core && PRG32AudioStudio.engine.voices()[0].active", timeout=30)
    assert page.evaluate("PRG32AudioStudio.engine.output.context.state") == "running"
    page.keyboard.press("Escape")                                  # Stop sound
    wait_until(page, "!PRG32AudioStudio.engine.voices().some(v => v.active)", timeout=5)

    # A sound effect and a soundtrack, typed with the keyboard in the grid.
    page.click("[data-bs-target='#effectsPanel']")
    page.click("#addEffect")
    page.click("[data-bs-target='#tracksPanel']")
    page.click("#addTrack")
    page.click(".track-step[data-voice='0'][data-step='0']")
    page.keyboard.type("C4")
    page.keyboard.press("ArrowRight")
    page.keyboard.type("E4")
    page.keyboard.press("ArrowDown")
    page.keyboard.type("off")
    page.keyboard.press("Enter")
    assert page.evaluate("document.activeElement.dataset.voice + ':' + document.activeElement.dataset.step") == "2:1"
    rows = page.evaluate("PRG32AudioStudio.document().soundtracks[0].rows")
    assert rows[0][:2] == [60, 64] and rows[1][1] == "off"
    page.click("#trackEditor button:has-text('Play')")
    wait_until(page, "PRG32AudioStudio.engine.voices()[0].active", timeout=10)
    page.click("#stopSound")
    wait_until(page, "!PRG32AudioStudio.engine.voices().some(v => v.active)", timeout=5)

    # Saved with its version; a reload shows the same sound.
    page.click("#saveAudio")
    wait_until(page, "/Saved \\(version/.test(document.getElementById('audioStatus').textContent)", timeout=10)
    saved = page.evaluate("PRG32AudioStudio.document()")
    page.reload()
    wait_until(page, "!!window.PRG32AudioStudio && !!PRG32AudioStudio.document()", timeout=30)
    assert page.evaluate("PRG32AudioStudio.document()") == saved
    assert page.locator("#effectList").inner_text().strip().startswith("Effect 1")

    # Export, then import into another project.
    with page.expect_download() as download_info:
        page.click("#exportAudio")
    exported = Path(download_info.value.path()).read_text()
    assert json.loads(exported)["schema"] == "prg32-kit-audio-export-1"
    other = page.evaluate("""fetch('/api/projects', {method: 'POST', headers: {'Content-Type':
        'application/json', 'X-PRG32-Kit': '1'}, body: JSON.stringify({title: 'Other'})}).then(r => r.json()).then(p => p.id)""")
    page.goto(f"{live_kit}/audio-studio/{other}")
    wait_until(page, "!!window.PRG32AudioStudio && !!PRG32AudioStudio.document()", timeout=30)
    page.set_input_files("#importAudio", files=[{"name": "s.json", "mimeType": "application/json",
                                                  "buffer": exported.encode()}])
    wait_until(page, "/Imported/.test(document.getElementById('audioStatus').textContent)", timeout=10)
    assert page.evaluate("PRG32AudioStudio.document().soundtracks[0].rows") == saved["soundtracks"][0]["rows"]

    # A save from a window that is behind is refused, and the student gets the choices.
    page.evaluate("""fetch('/api/projects/' + $('#projectId').val() + '/audio').then(r => r.json()).then(a =>
        fetch('/api/projects/' + $('#projectId').val() + '/audio', {method: 'PUT', headers: {'Content-Type':
        'application/json', 'X-PRG32-Kit': '1'}, body: JSON.stringify({document: a.document, expected_version: a.version})}))""")
    page.click("[data-bs-target='#tracksPanel']")
    page.fill("#trackEditor input[type=number] >> nth=0", "100")
    page.keyboard.press("Tab")
    page.click("#saveAudio")
    wait_until(page, "!!document.getElementById('versionConflict')", timeout=10)
    page.click("#versionConflict [data-choice='reload']")

    page.evaluate(AXE.read_text())
    for panel in ("#voicesPanel", "#effectsPanel", "#tracksPanel", "#samplesPanel"):
        page.click(f"[data-bs-target='{panel}']")
        results = page.evaluate("""axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})
            .then(r => r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
            .map(v => ({id: v.id, target: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
        assert results == [], (panel, results)
    assert record.csp_violations() == []
    context.close()
