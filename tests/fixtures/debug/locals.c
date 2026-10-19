/* Debugger fixture (ADR-0015): globals, locals, parameters, a struct, an array and a
   call chain draw -> paint_row -> paint_cell, for the source debugger's tests.
   Built by tools/build_debug_fixtures.py with the PRG32 SDK. */
#include "prg32.h"

typedef struct {
    int x;
    int y;
    uint16_t colour;
} spot_t;

int score = 3;
int heights[4] = {10, 20, 30, 40};
spot_t player = {150, 90, PRG32_COLOR_YELLOW};

/* noinline: keep a real call chain to unwind, even at -Os. */
__attribute__((noinline)) static int paint_cell(int column, int row, uint16_t colour) {
    int left = column * 16;
    int top = row * 8 + heights[column & 3];
    prg32_gfx_rect(left, top, 14, 6, colour);
    return left + top;
}

__attribute__((noinline)) static int paint_row(int row) {
    int total = 0;
    for (int column = 0; column < 4; column++) {
        total += paint_cell(column, row, (uint16_t)(PRG32_COLOR_GREEN + row));
    }
    return total;
}

void dbg_init(void) {
    score = 3;
}

void dbg_update(void) {
    uint32_t input = prg32_input_read();
    if (input & PRG32_BTN_LEFT) {
        player.x -= 2;
    }
    if (input & PRG32_BTN_RIGHT) {
        player.x += 2;
    }
    score += 1;
}

void dbg_draw(void) {
    prg32_gfx_clear(PRG32_COLOR_BLACK);
    int sum = 0;
    for (int row = 0; row < 3; row++) {
        sum += paint_row(row);
    }
    prg32_gfx_rect(player.x, player.y, 8, 8, player.colour);
    heights[0] = sum & 15;
}
