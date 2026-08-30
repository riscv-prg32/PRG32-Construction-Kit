static prg32_platform_actor_t player;

void platformer_c_init(void) {
    fill_world();                                    /* build the tile map */
    prg32_platform_tile_flags(2, PRG32_TILE_FLAG_SOLID);
    prg32_platform_actor_init(&player, 1, 32, 120, 8, 8);
}

void platformer_c_update(void) {
    uint32_t input = prg32_input_read();
    /* move_speed, jump_speed, gravity, max_fall */
    uint16_t state = prg32_platform_actor_step(&player, input, 2, -7, 1, 5);
    if (state & PRG32_PLATFORM_HAZARD) {
        prg32_audio_beep(120, 60);                   /* hit a hazard */
    }
    prg32_platform_camera_follow(&player, 64, 48);   /* scroll the world */
}
