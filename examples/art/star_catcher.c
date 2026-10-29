/*
 * Star Catcher (C): catch the falling star with the rocket.
 *
 * The art is made in Sprite Lab ("rocket", "star"), Backgrounds ("sky") and AudioStudio
 * ("Coin", "Theme"). #include "prg32_assets.h" gives this file that art as C:
 *   rocket_draw(x, y), star_draw(x, y)   draw a sprite with its top-left corner at x, y
 *   sky_load(), sky_draw()               put the background in the playfield, draw it
 *   sfx_coin()                           play the sound effect
 *   TRACK_THEME                          the soundtrack's number, for prg32_audio_play_track
 * Open prg32_assets.h in the project files (Project art) to read that code.
 */
#include <stdint.h>
#include "prg32.h"
#include "prg32_assets.h"

#define ROCKET_Y 160
#define NAVY 0x000F   /* RGB565: a little blue, no red, no green (PRG32_COLOR_NAVY in the kit) */

static int rocket_x = 152;
static int star_x = 100;
static int star_y = 0;
static int score = 0;

/* Send the star back to the top, at a new place. */
static void new_star(void) {
    star_y = 0;
    star_x = (int)prg32_random_number(8, 304);
}

/* The score as decimal digits, written from the right end of a small text. */
static void draw_score(void) {
    char text[12];
    int at = 11;
    int value = score;
    text[at] = 0;
    do {
        at -= 1;
        text[at] = (char)('0' + value % 10);
        value /= 10;
    } while (value > 0 && at > 0);
    prg32_gfx_text8(8, 8, &text[at], PRG32_COLOR_YELLOW, NAVY);
}

void star_catcher_c_init(void) {
    rocket_x = 152;
    star_x = 100;
    star_y = 0;
    score = 0;
    sky_load();                          /* the tiles and the map of the sky */
    prg32_audio_play_track(TRACK_THEME); /* the music made in AudioStudio */
}

void star_catcher_c_update(void) {
    uint32_t input = prg32_input_read();
    if (input & PRG32_BTN_LEFT) rocket_x -= 3;
    if (input & PRG32_BTN_RIGHT) rocket_x += 3;
    if (rocket_x < 0) rocket_x = 0;
    if (rocket_x > 304) rocket_x = 304;
    star_y += 2;
    if (prg32_sprite_hitbox(rocket_x, ROCKET_Y, ROCKET_WIDTH, ROCKET_HEIGHT, star_x, star_y, STAR_WIDTH, STAR_HEIGHT)) {
        score += 1;
        sfx_coin();
        new_star();
    }
    if (star_y > 176) new_star();
}

void star_catcher_c_draw(void) {
    sky_draw();
    rocket_draw(rocket_x, ROCKET_Y);
    star_draw(star_x, star_y);
    draw_score();
}
