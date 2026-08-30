/* dir_q8 holds direction components scaled by 256 (called Q8 fixed point). */
int hx = player_x + (dir_q8[angle][0] * dist) / 256;
int hy = player_y + (dir_q8[angle][1] * dist) / 256;
