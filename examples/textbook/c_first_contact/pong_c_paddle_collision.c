if (prg32_sprite_hitbox(
    ball_x, ball_y, 8, 8,
    paddle_x, 188, 64, 8)) {
        ball_dy = -1;        /* send the ball back upward */
}
