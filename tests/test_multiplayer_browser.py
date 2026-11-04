"""Multiplayer on this computer (ADR-0031): two windows of one browser play a Blocks game together.

The game (tests/fixtures/multiplayer/two_windows.*) is made of Blocks and compiled by the PRG32 SDK
from the kit's own generated C, so the multiplayer blocks, the WebAssembly core's multiplayer calls,
prg32_multiplayer.js and the Player are all the real code. One window gets a game controller with
the stick to the right and A held; the other sees that player arrive, move and press.
"""
from __future__ import annotations

import json
from pathlib import Path

from test_browser_offline import browser, live_kit, sign_in, wait_until  # noqa: F401

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "multiplayer"
CARTRIDGE = FIXTURES / "two_windows.prg32"
FAKE_PADS = """
window.__pads = [];
Object.defineProperty(navigator, 'getGamepads', { value: () => window.__pads });
"""
PAD_RIGHT_AND_A = ("window.__pads = [{id: 'Test Pad', index: 0, mapping: 'standard', connected: true, axes: [1, 0],"
                   " buttons: [" + ", ".join("{pressed: %s}" % ("true" if i == 0 else "false") for i in range(16)) + "]}]")
# What the game shows: its own square (yellow), the other player's (cyan) and the markers on top.
SCREEN = """(() => {
  const canvas = document.getElementById('playerScreen');
  const data = canvas.getContext('2d').getImageData(0, 0, 320, 200).data;
  const at = (x, y) => Array.from(data.slice((y * 320 + x) * 4, (y * 320 + x) * 4 + 3));
  const find = test => {
    for (let y = 8; y < 200; y++) for (let x = 0; x < 320; x++) if (test(...at(x, y))) return [x, y];
    return null;
  };
  const on = x => at(x + 2, 2).some(value => value > 60);
  return {
    me: find((r, g, b) => r > 200 && g > 200 && b < 60),
    other: find((r, g, b) => r < 60 && g > 200 && b > 200),
    look: on(0), pressed: on(16), my_id: on(32), other_id: on(48),
    status: (document.getElementById('multiplayerStatus') || {}).textContent || ''
  };
})()"""


def open_window(context, live_kit):  # noqa: F811
    page = context.new_page()
    page.goto(f"{live_kit}/player")
    page.set_input_files("#cartridgeFile", str(CARTRIDGE))
    wait_until(page, "!document.getElementById('playPause').disabled")
    page.click("#playPause")
    wait_until(page, "/Frame [1-9]/.test(document.getElementById('playerStatus').textContent)")
    return page


def seen(page, expression):
    wait_until(page, f"(() => {{ const s = {SCREEN}; return {expression}; }})()")
    return page.evaluate(SCREEN)


def test_the_fixture_is_the_generated_c_of_its_blocks():
    """The cartridge plays what a student's Blocks project generates (tools/build_multiplayer_fixture.py)."""
    from prg32_construction_kit.generator import blocks_to_c

    blocks = json.loads((FIXTURES / "two_windows.blocks.json").read_text(encoding="utf-8"))
    ir, c_source = blocks_to_c(blocks, {"title": "Two Windows", "entry_prefix": "tw"})
    assert ir["required_features"] == ["multiplayer"] and ir["warnings"] == []
    assert c_source == (FIXTURES / "two_windows.c").read_text(encoding="utf-8")


def test_two_windows_in_one_room_see_each_other(browser, live_kit):  # noqa: F811
    context = browser.new_context()
    context.add_init_script(FAKE_PADS)
    sign_in(context.new_page(), live_kit)
    first = open_window(context, live_kit)
    alone = seen(first, "s.me && s.my_id")
    assert alone["me"] == [150, 60] and alone["other"] is None and not alone["look"]
    assert "kit-two-windows: 0" in alone["status"]

    second = open_window(context, live_kit)
    second.evaluate(PAD_RIGHT_AND_A)                     # the second player: stick right, A held
    # The first window sees the second player 40 pixels lower, with the stick to the right...
    together = seen(first, "s.other && s.other[0] > 250 && s.pressed")
    assert together["me"] == [150, 60]
    assert together["other"][1] == 100 and together["other"][0] >= 270
    assert together["look"] and together["pressed"] and together["other_id"]
    assert "kit-two-windows: 1" in together["status"]
    # ...and the second window sees the first one, standing still with no button held.
    other_side = seen(second, "s.other && s.look")
    assert other_side["other"] == [150, 100] and not other_side["pressed"]
    assert other_side["me"][0] >= 270

    # A window that closes leaves the room at once.
    second.close()
    gone = seen(first, "!s.other")
    assert "kit-two-windows: 0" in gone["status"]
    context.close()


def test_other_browsers_do_not_share_a_room(browser, live_kit):  # noqa: F811
    """Each browser profile (here: each context) is its own computer: nothing crosses between them."""
    contexts = [browser.new_context() for _ in range(2)]
    pages = []
    for context in contexts:
        sign_in(context.new_page(), live_kit)
        pages.append(open_window(context, live_kit))
    first = seen(pages[0], "s.me && s.my_id")
    pages[0].wait_for_timeout(1000)
    assert first["other"] is None and page_status(pages[0]).endswith("0 other players")
    for context in contexts:
        context.close()


def page_status(page):
    return page.evaluate(SCREEN)["status"].strip()


PREVIEW = """blocks => {
  const canvas = document.createElement('canvas');
  canvas.width = 320; canvas.height = 200;
  window.__sim = new PRG32Simulator.Simulator(canvas, null);
  window.__sim.loadBlocks(blocks, 'Two Windows');
  return window.__sim.env.my_id;
}"""


def test_the_blocks_preview_plays_multiplayer_between_windows_too(browser, live_kit):  # noqa: F811
    """The quick Blocks preview (simulator.js) joins the same rooms as the PRG32 core."""
    blocks = json.loads((FIXTURES / "two_windows.blocks.json").read_text(encoding="utf-8"))
    context = browser.new_context()
    pages = [context.new_page() for _ in range(2)]
    ids = []
    for page in pages:
        page.goto(f"{live_kit}/static/offline.html")
        ids.append(page.evaluate(PREVIEW, blocks))
    assert all(ids) and ids[0] != ids[1]                       # my_id(): each window its own player
    for _ in range(3):
        for page in pages:
            page.evaluate("window.__sim.step(false)")
    peers = pages[0].evaluate("window.__sim.env.peers")
    assert [(peer["id"], peer["x"], peer["y"], peer["look"], peer["flags"]) for peer in peers] == [(ids[1], 150, 60, 7, 3)]
    # The cyan square of the other player is drawn where the generated C would draw it.
    cyan = pages[0].evaluate("Array.from(window.__sim.fb).filter(p => p === 0x07FF).length")
    assert cyan == 64
    context.close()
