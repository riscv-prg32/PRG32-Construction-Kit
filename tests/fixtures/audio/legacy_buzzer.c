/* A legacy PRG32 cartridge that still calls the obsolete buzzer (ADR-0021). The kit itself
 * refuses to build this (source_project.OBSOLETE_FUNCTIONS); tools/build_audio_fixtures.py
 * builds it with the PRG32 SDK directly, to prove that an old cartridge stays silent in the
 * browser, as on a console without a buzzer, and that each call is counted. */
#include "prg32.h"

static uint32_t frame;

void legacy_init(void) {
    frame = 0;
}

void legacy_update(void) {
    if (frame == 2 || frame == 5) {
        prg32_buzzer_tone(880, 100, 512);
    }
    frame++;
}

void legacy_draw(void) {
    prg32_gfx_clear(0);
}
