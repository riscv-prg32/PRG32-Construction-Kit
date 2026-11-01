/* What the browser sees of the stick and the buttons, for tests/test_controllers_browser.py.
 * Rebuild stick.prg32 with:
 *   python3 -m prg32 cartridge build tests/fixtures/input/stick.c --portable --architecture qemu \
 *     --entry-prefix stick --name stick --out tests/fixtures/input/stick.prg32
 */
#include "prg32.h"

void stick_init(void) {}

void stick_update(void) {}

void stick_draw(void) {
    int raw_x = 0, raw_y = 0;
    uint32_t input = prg32_input_read();
    int has_raw = prg32_input_axes_raw(&raw_x, &raw_y) == 0;
    prg32_gfx_clear(PRG32_COLOR_BLACK);
    /* The yellow square moves with the stick: x 150 +- 127, y 90 +- 63. */
    prg32_gfx_rect(150 + prg32_input_axis_x(), 90 + prg32_input_axis_y() / 2, 8, 8, PRG32_COLOR_YELLOW);
    /* One marker per answer, along the top. */
    if (prg32_input_has_analog()) prg32_gfx_rect(0, 0, 8, 8, PRG32_COLOR_GREEN);
    if (input & PRG32_BTN_C) prg32_gfx_rect(16, 0, 8, 8, PRG32_COLOR_RED);
    if (has_raw && raw_x > 3000) prg32_gfx_rect(32, 0, 8, 8, PRG32_COLOR_BLUE);
    if (input & PRG32_BTN_RIGHT) prg32_gfx_rect(48, 0, 8, 8, PRG32_COLOR_CYAN);
    if (input & PRG32_BTN_R) prg32_gfx_rect(64, 0, 8, 8, PRG32_COLOR_MAGENTA);
}
