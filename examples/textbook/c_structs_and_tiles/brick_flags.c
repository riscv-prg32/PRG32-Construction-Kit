static uint8_t bricks[10];   /* bricks[i] == 1 means brick i is intact */

static void reset_bricks(void) {
    for (int i = 0; i < 10; ++i) {
        bricks[i] = 1;       /* every brick starts present */
    }
}
