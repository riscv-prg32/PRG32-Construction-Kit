ball_x += ball_dx;
ball_y += ball_dy;
if (ball_x < 0 || ball_x > 312) {   /* 320 - 8-wide ball */
    ball_dx = -ball_dx;             /* bounce horizontally */
}
if (ball_y < 0 || ball_y > 192) {
    ball_dy = -ball_dy;             /* bounce vertically */
}
