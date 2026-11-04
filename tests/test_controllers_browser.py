"""Game controllers and the on-screen stick, in a real browser, on a real cartridge.

There is no physical controller here: navigator.getGamepads is replaced before the page loads, so
everything after that call (prg32_controllers.js, the Player, the WebAssembly core and the cartridge's
ABI calls) is the real code.
"""
from __future__ import annotations

from pathlib import Path

from test_browser_offline import browser, live_kit, sign_in, wait_until  # noqa: F401

CARTRIDGE = Path(__file__).resolve().parent / "fixtures" / "input" / "stick.prg32"
FAKE_PADS = """
window.__pads = [];
Object.defineProperty(navigator, 'getGamepads', { value: () => window.__pads });
"""
# What the cartridge shows: the place of the yellow square and which markers are on.
SCREEN = """(() => {
  const canvas = document.getElementById('playerScreen');
  const data = canvas.getContext('2d').getImageData(0, 0, 320, 200).data;
  const at = (x, y) => Array.from(data.slice((y * 320 + x) * 4, (y * 320 + x) * 4 + 3));
  let square = null;
  for (let y = 8; y < 200 && !square; y++) for (let x = 0; x < 320; x++) {
    const [r, g, b] = at(x, y);
    if (r > 200 && g > 200 && b < 60) { square = [x, y]; break; }
  }
  const on = x => at(x, 2).some(value => value > 60);
  return { square, analog: on(2), c: on(18), raw: on(34), right: on(50), r: on(66) };
})()"""


def open_cartridge(browser, live_kit, script=None):  # noqa: F811
    context = browser.new_context()
    if script:
        context.add_init_script(script)
    page = context.new_page()
    sign_in(page, live_kit)
    page.goto(f"{live_kit}/player")
    page.set_input_files("#cartridgeFile", str(CARTRIDGE))
    wait_until(page, "!document.getElementById('playPause').disabled")
    page.click("#playPause")
    wait_until(page, "/Frame [1-9]/.test(document.getElementById('playerStatus').textContent)")
    return context, page


def seen(page, expression):
    wait_until(page, f"(() => {{ const s = {SCREEN}; return {expression}; }})()")
    return page.evaluate(SCREEN)


def pad(axes=(0, 0), pressed=()):
    buttons = ", ".join("{pressed: %s}" % ("true" if index in pressed else "false") for index in range(16))
    return f"window.__pads = [{{id: 'Test Pad', mapping: 'standard', connected: true, axes: {list(axes)}, buttons: [{buttons}]}}]"


def test_a_cartridge_reads_a_game_controller(browser, live_kit):  # noqa: F811
    context, page = open_cartridge(browser, live_kit, FAKE_PADS)
    at_rest = seen(page, "s.square && !s.analog")
    assert at_rest["square"] == [150, 90] and not at_rest["c"]        # no controller: no stick

    page.evaluate(pad())
    rest = seen(page, "s.analog")
    assert rest["square"] == [150, 90] and not rest["right"]

    page.evaluate(pad(axes=(1, 0)))
    tilted = seen(page, "s.square && s.square[0] > 250")
    assert tilted["square"] == [277, 90]
    assert tilted["right"] and tilted["raw"]                          # the direction, and the raw reading

    # Inside the deadzone a stick reads 0.
    page.evaluate(pad(axes=(0.05, 0)))
    assert seen(page, "s.square && s.square[0] === 150")["square"] == [150, 90]

    # Buttons: left is C, the right bumper is R; the cross steers through the digital axis.
    page.evaluate(pad(pressed=(2, 5, 15)))
    pressed = seen(page, "s.c && s.r && s.square && s.square[0] === 277")
    assert pressed["right"] is True
    page.evaluate(pad())
    assert not seen(page, "!s.c && !s.r")["c"]
    context.close()


def test_the_page_names_the_controller(browser, live_kit):  # noqa: F811
    context, page = open_cartridge(browser, live_kit, FAKE_PADS)
    status = "document.querySelector('[data-controller-status]').textContent"
    assert "press" in page.evaluate(status)
    page.evaluate(pad())
    page.evaluate("window.dispatchEvent(new Event('gamepadconnected'))")
    assert "Test Pad" in page.evaluate(status)
    context.close()


def test_the_on_screen_stick_moves_the_game_and_springs_back(browser, live_kit):  # noqa: F811
    context, page = open_cartridge(browser, live_kit)
    box = page.locator("[data-analog-stick]").bounding_box()
    middle = (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.move(*middle)
    page.mouse.down()
    page.mouse.move(middle[0] + box["width"], middle[1])              # beyond the edge: full tilt
    held = seen(page, "s.square && s.square[0] === 277")
    assert held["analog"] is True and held["right"] is True
    page.mouse.up()
    released = seen(page, "s.square && s.square[0] === 150")
    assert released["analog"] is True and released["right"] is False
    context.close()


def test_the_new_buttons_have_keys_and_on_screen_buttons(browser, live_kit):  # noqa: F811
    context, page = open_cartridge(browser, live_kit)
    page.focus("#playerScreen")
    page.keyboard.down("c")
    assert seen(page, "s.c")["c"] is True
    page.keyboard.up("c")
    box = page.locator(".touch-button[data-button=R]").bounding_box()
    page.mouse.move(box["x"] + 2, box["y"] + 2)
    page.mouse.down()
    assert seen(page, "s.r")["r"] is True
    page.mouse.up()
    context.close()


def two_pads(first_axes, second_axes):
    def one(index, axes):
        buttons = ", ".join("{pressed: false}" for _ in range(16))
        return f"{{id: 'Pad {index + 1}', index: {index}, mapping: 'standard', connected: true, axes: {list(axes)}, buttons: [{buttons}]}}"
    return f"window.__pads = [{one(0, first_axes)}, {one(1, second_axes)}]"


def test_a_window_can_use_one_controller_of_its_own(browser, live_kit):  # noqa: F811
    """Two controllers, two windows: each window picks its controller, so they are two players."""
    context, page = open_cartridge(browser, live_kit, FAKE_PADS)
    page.evaluate(two_pads((1, 0), (-1, 0)))
    page.evaluate("window.dispatchEvent(new Event('gamepadconnected'))")
    options = page.eval_on_selector_all("#controllerChoice option", "all => all.map(o => o.value + ' ' + o.textContent)")
    assert options[0].startswith("all ") and "Pad 1" in options[1] and "Pad 2" in options[2]
    # All controllers: the first stick that is tilted wins (the first controller).
    assert seen(page, "s.square && s.square[0] === 277")["square"] == [277, 90]
    page.select_option("#controllerChoice", "1")
    assert seen(page, "s.square && s.square[0] === 23")["square"] == [23, 90]
    # The choice is kept for this tab when the page opens again; a missing controller is named.
    page.reload()
    page.evaluate("window.__pads = []")
    assert page.input_value("#controllerChoice") == "1"
    assert "not connected" in page.eval_on_selector("#controllerChoice option:checked", "o => o.textContent")
    context.close()
