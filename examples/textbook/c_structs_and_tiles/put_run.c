static void put_run(uint8_t layer, uint8_t x0, uint8_t x1,
                    uint8_t y, uint8_t tile) {
    for (uint8_t x = x0; x <= x1 && x < PRG32_PLAYFIELD_COLS; ++x) {
        prg32_playfield_put(layer, x, y, tile);
    }
}
