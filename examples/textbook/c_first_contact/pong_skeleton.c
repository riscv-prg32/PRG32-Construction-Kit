#include "prg32.h"

/* Persistent game state, equivalent to the .data section in the assembly version. */
static int paddle_x;
static int ball_x;
static int ball_y;
static int ball_dx;   /* horizontal velocity */
static int ball_dy;   /* vertical velocity */

void pong_skeleton_init(void) {
    /* Same starting values as the assembly data section. */
    paddle_x = 140;
    ball_x = 80;
    ball_y = 80;
    ball_dx = 2;
    ball_dy = 2;
}

void pong_skeleton_update(void) {
    uint32_t input = prg32_input_read();

    /* --- PADDLE INPUT AND X MOVEMENT --- */
    if (input & PRG32_BTN_LEFT) {
        paddle_x -= 3;
    }
    if (input & PRG32_BTN_RIGHT) {
        paddle_x += 3;
    }

    /* Clamp the paddle to [0, 256] */
    if (paddle_x < 0) {
        paddle_x = 0;
    } else if (paddle_x > 256) {
        paddle_x = 256;
    }

    /* --- BALL X MOVEMENT --- */
    ball_x += ball_dx;
    if (ball_x < 0) {
        ball_x = 0;
        ball_dx = -ball_dx;
    } else if (ball_x > 312) {
        ball_x = 312;
        ball_dx = -ball_dx;
    }

    /* --- BALL Y MOVEMENT --- */
    ball_y += ball_dy;
    if (ball_y < 0) {
        ball_y = 0;
        ball_dy = -ball_dy;
    }

    /* --- PADDLE COLLISION CHECK --- */
    if (prg32_sprite_hitbox(
            ball_x, ball_y, 8, 8,
            paddle_x, 188, 64, 8)) {
        /* Match the assembly: beep and only reverse dy when the ball is moving down. */
        prg32_audio_beep(440, 60);
        if (ball_dy > 0) {
            ball_dy = -ball_dy;
        }
    }
}

void pong_skeleton_draw(void) {
    prg32_gfx_clear(PRG32_COLOR_BLACK);
    prg32_gfx_rect(paddle_x, 188, 64, 8, PRG32_COLOR_WHITE);
    prg32_gfx_rect(ball_x, ball_y, 8, 8, PRG32_COLOR_YELLOW);
}
