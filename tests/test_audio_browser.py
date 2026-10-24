"""The Player's sound in a real browser (ADR-0021).

The conformance cartridge (tests/fixtures/audio) is opened on the Player page and played:
pressing Play starts the AudioContext (browsers allow sound only after a click), the
firmware engine's stereo frames are scheduled after every frame, the amount queued stays
bounded, Pause stops every scheduled buffer, and the page has no CSP violation.
"""

from __future__ import annotations

import contextlib
import os
from pathlib import Path

from test_browser_offline import Recorder, browser, live_kit, settled, sign_in, wait_until  # noqa: F401 - fixtures

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


@contextlib.contextmanager
def evidence_on_failure(page, name):
    """On a failure, keep a screenshot and the page's status line (CI sets PRG32_BROWSER_EVIDENCE)."""
    try:
        yield
    except BaseException:
        folder = os.environ.get("PRG32_BROWSER_EVIDENCE")
        if folder:
            Path(folder).mkdir(parents=True, exist_ok=True)
            with contextlib.suppress(Exception):
                page.screenshot(path=str(Path(folder) / f"{name}.png"), full_page=True)
                Path(folder, f"{name}.txt").write_text(page.url + "\n" + page.inner_text("body")[:20000])
        raise


def test_audio_studio_edits_previews_saves_and_reloads(browser, live_kit):  # noqa: F811
    import json

    context = browser.new_context(accept_downloads=True)
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    with evidence_on_failure(page, "audio-studio-edit"):
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
        page.click("#audioStudio .kit-sections [data-section=effects]")
        page.click("#addEffect")
        page.click("#audioStudio .kit-sections [data-section=tracks]")
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
        page.click("#audioStudio .kit-sections [data-section=tracks]")
        page.fill("#trackEditor input[type=number] >> nth=0", "100")
        page.keyboard.press("Tab")
        page.click("#saveAudio")
        wait_until(page, "!!document.getElementById('versionConflict')", timeout=10)
        page.click("#versionConflict [data-choice='reload']")

        page.evaluate(AXE.read_text())
        for panel in ("voices", "effects", "tracks", "samples"):
            page.click(f"#audioStudio .kit-sections [data-section={panel}]")
            settled(page)
            results = page.evaluate("""axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})
                .then(r => r.violations.filter(v => v.impact === 'serious' || v.impact === 'critical')
                .map(v => ({id: v.id, target: v.nodes.slice(0, 3).map(n => n.target.join(' '))})))""")
            assert results == [], (panel, results)
        assert record.csp_violations() == []
    context.close()


def api(page, path, body=None, method=None):
    """Kit.api in the page (it sends the kit's headers); bytes come back as a list of numbers."""
    return page.evaluate("""([path, body, method]) => Kit.api(path, body === null ? {method: method || 'GET'}
        : {method: method || 'POST', body}).then(d => d instanceof ArrayBuffer ? Array.from(new Uint8Array(d)) : d)""",
                         [path, body, method])


def test_audio_studio_works_with_the_keyboard_only(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    project = api(page, "/api/projects", {"title": "Keys"})
    page.goto(f"{live_kit}/audio-studio/{project['id']}")
    wait_until(page, "!!window.PRG32AudioStudio && !!PRG32AudioStudio.document()", timeout=30)
    with evidence_on_failure(page, "audio-studio-keyboard"):
        # Sections: focus Voices, arrow to Sound effects (a tab list, kit_tool.js).
        page.focus("#audioStudio .kit-sections [data-section=voices]")
        page.keyboard.press("ArrowRight")
        page.keyboard.press("Enter")
        wait_until(page, "document.getElementById('audioStudio').dataset.section === 'effects'")
        page.focus("#addEffect")
        page.keyboard.press("Enter")
        wait_until(page, "PRG32AudioStudio.document().effects.length === 1")
        # The effect's name field is reachable and labelled; change it with the keyboard.
        name = page.locator("#effectEditor").get_by_label("Name")
        name.focus()
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.type("Zap")
        page.keyboard.press("Tab")
        wait_until(page, "PRG32AudioStudio.document().effects[0].name === 'Zap'")
        # Every control in the editor has a label a screen reader can announce.
        unlabeled = page.evaluate("""Array.from(document.querySelectorAll('main input, main select, main button, main textarea,'
            + ' .container input, .container select, .container button'))
            .filter(el => el.offsetParent !== null && !el.labels?.length && !el.getAttribute('aria-label')
                    && !el.textContent.trim() && !el.getAttribute('title')).map(el => el.outerHTML.slice(0, 80))""")
        assert unlabeled == []
        # Try it with Enter on the focused button, then Escape silences everything.
        page.focus("#effectEditor button:has-text('Try it')")
        page.keyboard.press("Enter")
        wait_until(page, "PRG32AudioStudio.engine.core && PRG32AudioStudio.engine.voices()[7].active", timeout=30)
        page.keyboard.press("Escape")
        wait_until(page, "!PRG32AudioStudio.engine.voices().some(v => v.active)", timeout=5)
        # Save with the keyboard; the status line (role=status) says so.
        page.focus("#saveAudio")
        page.keyboard.press("Enter")
        wait_until(page, "/Saved \\(version/.test(document.getElementById('audioStatus').textContent)", timeout=10)
        assert page.get_attribute("#audioStatus", "role") == "status"
    assert record.csp_violations() == []
    context.close()


def test_audio_studio_sound_goes_into_the_archive_and_the_cartridge(browser, live_kit, monkeypatch):  # noqa: F811
    import hashlib
    import io
    import zipfile
    from types import SimpleNamespace

    from test_asm_generator import program, stmt
    from test_audio_studio import song_document, wav

    blocks = []

    def fake_builder(command, **_kwargs):
        if "--audio-block" in command:
            blocks.append(Path(command[command.index("--audio-block") + 1]).read_bytes())
        Path(command[command.index("--out") + 1]).write_bytes(b"PRG2" + b"\x00" * 60)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    context = browser.new_context(accept_downloads=True)
    record = Recorder(context, live_kit)
    page = record.watch(context.new_page())
    sign_in(page, live_kit)
    with evidence_on_failure(page, "audio-studio-archive-cartridge"):
        game = program(start=[stmt("prg32_soundtrack_play", TRACK="Theme")], update=[stmt("prg32_sound_effect", EFFECT="Jump")])
        project = api(page, "/api/projects", {"title": "Packed", "blocks_json": game})
        url = f"/api/projects/{project['id']}/audio"
        sample = page.evaluate("""([url, bytes]) => { const form = new FormData();
            form.append('file', new Blob([new Uint8Array(bytes)], {type: 'audio/wav'}), 'drum.wav');
            form.append('name', 'Drum'); return Kit.api(url + '/samples', {method: 'POST', body: form}); }""",
                               [url, list(wav([12000, -12000, 0] * 200))])
        document = song_document()
        document["samples"].append({"name": "Drum", "artifact_id": sample["artifact_id"], "base_note": 60,
                                    "loop": False, "loop_start": 0, "loop_end": 0})
        document["effects"][1]["instrument"] = {**document["effects"][1]["instrument"], "sound": "sample", "sample": "Drum"}
        api(page, url, {"document": document, "expected_version": 0}, "PUT")
        preview = bytes(api(page, url + "/preview", {}))

        # The IDE's Compile button builds the cartridge with exactly the previewed audio block.
        page.goto(f"{live_kit}/ide/{project['id']}")
        wait_until(page, "document.getElementById('ide').dataset.ready === 'true'", timeout=30)
        page.click("#ideCompile")
        wait_until(page, "document.getElementById('statusBuild').textContent === 'Cartridge ready'", timeout=30)
        assert blocks and all(block == preview for block in blocks)

        # The project archive (IDE: Project, Export) carries the sample and imports again on the dashboard.
        with page.expect_download() as download_info:
            page.evaluate("$('#ideExportArchive').trigger('click')")
        archive = Path(download_info.value.path()).read_bytes()
        assert "audio/samples/01-drum.u8" in zipfile.ZipFile(io.BytesIO(archive)).namelist()
        page.goto(f"{live_kit}/")
        with page.expect_navigation(url=lambda target: "/ide/" in target, timeout=30000):
            page.set_input_files("#importProjectFile", files=[{"name": "packed.prg32project.zip",
                                                                 "mimeType": "application/zip", "buffer": archive}])
        imported = page.url.rsplit("/", 1)[-1]
        assert imported != project["id"]
        answer = api(page, f"/api/projects/{imported}/audio")
        assert answer["missing_samples"] == [] and answer["document"]["effects"] == document["effects"]
        again = bytes(api(page, f"/api/projects/{imported}/audio/preview", {}))
        assert hashlib.sha256(again).hexdigest() == hashlib.sha256(preview).hexdigest()
    assert record.csp_violations() == []
    context.close()
