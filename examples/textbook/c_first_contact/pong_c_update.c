void pong_c_update(void) {
    uint32_t input = prg32_input_read();
    if (input & PRG32_BTN_LEFT) {
        paddle_x -= 3;
    }
    if (input & PRG32_BTN_RIGHT) {
        paddle_x += 3;
    }
    if (paddle_x < 0)   { paddle_x = 0; }
    if (paddle_x > 256) { paddle_x = 256; }   /* 320 - 64-wide paddle */
}
