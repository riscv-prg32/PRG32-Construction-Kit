/*
 * Minimal stand-in for PRG32's prg32.h, used only by the test suite to check
 * that generated C compiles on a normal host compiler (CI has no RISC-V
 * toolchain). Signatures are copied from riscv-prg32/PRG32
 * components/prg32/include/prg32.h, prg32_audio.h and prg32_multiplayer.h.
 */
#ifndef PRG32_H
#define PRG32_H
#include <stddef.h>
#include <stdint.h>

#define PRG32_GAME_W 320
#define PRG32_GAME_H 200
#define PRG32_LCD_W 320
#define PRG32_LCD_H 240
#define PRG32_TEXT_COLS 40
#define PRG32_TEXT_ROWS 25
#define PRG32_TILE_W 8
#define PRG32_TILE_H 8
#define PRG32_TILE_COLS 40
#define PRG32_TILE_ROWS 25
#define PRG32_PLAYFIELD_LAYERS 2
#define PRG32_PLAYFIELD_COLS 64
#define PRG32_PLAYFIELD_ROWS 32
#define PRG32_BTN_LEFT (1u << 0)
#define PRG32_BTN_RIGHT (1u << 1)
#define PRG32_BTN_UP (1u << 2)
#define PRG32_BTN_DOWN (1u << 3)
#define PRG32_BTN_A (1u << 4)
#define PRG32_BTN_B (1u << 5)
#define PRG32_BTN_START (1u << 6)
#define PRG32_BTN_SELECT PRG32_BTN_START
#define PRG32_P2_BTN_LEFT (1u << 8)
#define PRG32_P2_BTN_RIGHT (1u << 9)
#define PRG32_P2_BTN_UP (1u << 10)
#define PRG32_P2_BTN_DOWN (1u << 11)
#define PRG32_P2_BTN_A (1u << 12)
#define PRG32_P2_BTN_B (1u << 13)
#define PRG32_P2_BTN_START (1u << 14)
#define PRG32_P2_BTN_SELECT PRG32_P2_BTN_START
#define PRG32_COLOR_BLACK 0x0000
#define PRG32_COLOR_WHITE 0xffff
#define PRG32_COLOR_RED 0xf800
#define PRG32_COLOR_GREEN 0x07e0
#define PRG32_COLOR_BLUE 0x001f
#define PRG32_COLOR_YELLOW 0xffe0
#define PRG32_COLOR_CYAN 0x07ff
#define PRG32_COLOR_MAGENTA 0xf81f
#define PRG32_MP_FLAG_ENABLE (1u << 0)

typedef struct {
    uint32_t player_id;
    int16_t x;
    int16_t y;
    uint16_t sprite;
    uint16_t flags;
    uint32_t input;
    uint32_t frame;
    uint32_t last_seen_ms;
} prg32_player_state_t;

uint32_t prg32_input_read(void);
uint32_t prg32_random_number(uint32_t min, uint32_t max);
void prg32_gfx_clear(uint16_t color);
void prg32_gfx_clear_indexed(uint8_t index);
void prg32_gfx_pixel(int x, int y, uint16_t color);
void prg32_gfx_rect(int x, int y, int w, int h, uint16_t color);
void prg32_gfx_pixel_indexed(int x, int y, uint8_t index);
void prg32_gfx_rect_indexed(int x, int y, int w, int h, uint8_t index);
void prg32_palette_set(uint8_t index, uint16_t rgb565);
void prg32_gfx_text8(int x, int y, const char *s, uint16_t fg, uint16_t bg);
void prg32_splash_show_game(const char *title, const char *subtitle, uint32_t duration_ms, uint16_t bg,
                            uint16_t fg, uint16_t accent);
void prg32_band_set_game_info(const char *text);
int prg32_sprite_hitbox(int ax, int ay, int aw, int ah, int bx, int by, int bw, int bh);
void prg32_sprite_draw_8x8(int x, int y, const uint8_t *bits, uint16_t fg, uint16_t bg);
void prg32_tile_define(uint8_t id, const uint8_t *bitmap8x8, uint16_t fg, uint16_t bg);
void prg32_playfield_clear(uint8_t layer, uint8_t tile_id);
void prg32_playfield_put(uint8_t layer, uint8_t tx, uint8_t ty, uint8_t id);
uint8_t prg32_playfield_get(uint8_t layer, uint8_t tx, uint8_t ty);
void prg32_playfield_scroll(uint8_t layer, int x, int y);
void prg32_playfield_camera(int x, int y);
void prg32_playfield_draw(uint8_t layer, int transparent_zero);
void prg32_audio_note(uint8_t channel, uint8_t instrument, uint8_t note, uint8_t volume, uint32_t duration_ms);
void prg32_audio_note_off(uint8_t channel);
void prg32_audio_set_master_volume(uint8_t volume);
void prg32_audio_stop_all(void);
void prg32_audio_play_track(uint16_t track_id);
void prg32_audio_stop_track(void);
int prg32_score_submit_current_player(const char *game, uint32_t score);
int prg32_scoreboard_show(const char *game, const char *title);
int prg32_score_player_prompt(void);
int prg32_multiplayer_join(const char *cartridge_signature, uint32_t flags);
void prg32_multiplayer_tick(void);
int prg32_multiplayer_set_local_state(int16_t x, int16_t y, uint16_t sprite, uint16_t flags);
int prg32_multiplayer_get_peer_count(void);
int prg32_multiplayer_get_peer(int index, prg32_player_state_t *out);
#endif
