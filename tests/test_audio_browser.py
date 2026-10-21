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
