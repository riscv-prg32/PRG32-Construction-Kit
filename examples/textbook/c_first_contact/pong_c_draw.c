void pong_c_draw(void) {
    prg32_gfx_clear(PRG32_COLOR_BLACK);
    prg32_gfx_rect(paddle_x, 188, 64, 8, PRG32_COLOR_WHITE);
    prg32_gfx_rect(ball_x, ball_y, 8, 8, PRG32_COLOR_YELLOW);
    prg32_gfx_text8(8, 96, "PONG C", PRG32_COLOR_GREEN, PRG32_COLOR_BLACK);
}
