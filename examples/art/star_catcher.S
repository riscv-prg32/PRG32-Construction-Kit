/*
 * Star Catcher (assembly): catch the falling star with the rocket.
 *
 * The art is made in Sprite Lab ("rocket", "star"), Backgrounds ("sky") and AudioStudio
 * ("Coin", "Theme"). The line  #include "prg32_assets.S"  gives this file that art as
 * assembly; open prg32_assets.S in the project files (Project art) to read it:
 *   rocket_draw, star_draw   a0 = x, a1 = y: draw the sprite with its top-left corner there
 *   sky_load, sky_draw       put the background in the playfield (once), draw it (every frame)
 *   sfx_coin                 play the sound effect
 *   TRACK_THEME              the soundtrack's number, for prg32_audio_play_track
 *   ROCKET_WIDTH, STAR_HEIGHT, ...   the sizes of the sprites
 * Every one of them follows the calling convention, like a firmware function.
 */
    .option norelax
#include "prg32_assets.S"

    .equ ROCKET_Y, 160
    .equ BTN_LEFT, 1                # PRG32_BTN_LEFT: bit 0 of the buttons
    .equ BTN_RIGHT, 2               # PRG32_BTN_RIGHT: bit 1
    .equ YELLOW, 0xFFE0             # RGB565
    .equ NAVY, 0x000F

    .section .data
    .balign 4
rocket_x:   .word 152
star_x:     .word 100
star_y:     .word 0
score:      .word 0

    .section .bss
score_text: .zero 12                # the score as text, written from the right

    .section .text
    .balign 4
    .globl star_catcher_assembly_init
    .globl star_catcher_assembly_update
    .globl star_catcher_assembly_draw

/* new_star: the star goes back to the top (star_y = 0), at a random x from 8 to 304. */
new_star:
    addi sp, sp, -16
    sw ra, 12(sp)
    la t0, star_y
    sw zero, 0(t0)                  # star_y = 0
    li a0, 8
    li a1, 304
    call prg32_random_number        # a0 = a number from 8 to 304
    la t0, star_x
    sw a0, 0(t0)                    # star_x = a0
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

/* init: starting values, the sky in the playfield, the music. */
star_catcher_assembly_init:
    addi sp, sp, -16
    sw ra, 12(sp)
    la t0, rocket_x
    li t1, 152
    sw t1, 0(t0)
    la t0, star_x
    li t1, 100
    sw t1, 0(t0)
    la t0, star_y
    sw zero, 0(t0)
    la t0, score
    sw zero, 0(t0)
    call sky_load                   # the tiles and the map of the sky
    li a0, TRACK_THEME
    call prg32_audio_play_track     # the music made in AudioStudio
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

/* update: move the rocket, let the star fall, catch it. */
star_catcher_assembly_update:
    addi sp, sp, -16
    sw ra, 12(sp)
    call prg32_input_read           # a0 = the buttons held
    la t0, rocket_x
    lw t1, 0(t0)                    # t1 = rocket_x
    andi t2, a0, BTN_LEFT
    beqz t2, update_not_left
    addi t1, t1, -3                 # left: 3 pixels to the left
update_not_left:
    andi t2, a0, BTN_RIGHT
    beqz t2, update_not_right
    addi t1, t1, 3                  # right: 3 pixels to the right
update_not_right:
    bgez t1, update_not_too_left
    li t1, 0                        # never left of the screen
update_not_too_left:
    li t2, 304
    ble t1, t2, update_not_too_right
    li t1, 304                      # never right of it (320 - 16)
update_not_too_right:
    sw t1, 0(t0)
    la t0, star_y
    lw t1, 0(t0)
    addi t1, t1, 2                  # the star falls 2 pixels
    sw t1, 0(t0)
    la t0, rocket_x
    lw a0, 0(t0)                    # rectangle a: the rocket
    li a1, ROCKET_Y
    li a2, ROCKET_WIDTH
    li a3, ROCKET_HEIGHT
    la t0, star_x
    lw a4, 0(t0)                    # rectangle b: the star
    la t0, star_y
    lw a5, 0(t0)
    li a6, STAR_WIDTH
    li a7, STAR_HEIGHT
    call prg32_sprite_hitbox        # a0 = 1 when they overlap
    beqz a0, update_missed
    la t0, score
    lw t1, 0(t0)
    addi t1, t1, 1
    sw t1, 0(t0)                    # one more star caught
    call sfx_coin
    call new_star
update_missed:
    la t0, star_y
    lw t1, 0(t0)
    li t2, 176
    ble t1, t2, update_done
    call new_star                   # it reached the grass: a new star
update_done:
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

/* draw: the sky, the rocket, the star, then the score. */
star_catcher_assembly_draw:
    addi sp, sp, -16
    sw ra, 12(sp)
    call sky_draw
    la t0, rocket_x
    lw a0, 0(t0)
    li a1, ROCKET_Y
    call rocket_draw
    la t0, star_x
    lw a0, 0(t0)
    la t0, star_y
    lw a1, 0(t0)
    call star_draw
    call draw_score
    lw ra, 12(sp)
    addi sp, sp, 16
    ret

/* draw_score: the score's digits, from the last one, into score_text, then on the screen. */
draw_score:
    addi sp, sp, -16
    sw ra, 12(sp)
    la t0, score
    lw t1, 0(t0)                    # t1 = the value still to write
    la t2, score_text
    addi t2, t2, 11                 # t2 = the end of the text
    sb zero, 0(t2)                  # a text ends with a 0 byte
    li t3, 10
draw_score_digit:
    addi t2, t2, -1
    rem t4, t1, t3                  # the last digit
    addi t4, t4, 48                 # as a character: '0' is 48
    sb t4, 0(t2)
    div t1, t1, t3                  # the digits that are left
    bnez t1, draw_score_digit
    li a0, 8
    li a1, 8
    mv a2, t2                       # a2 = the first digit
    li a3, YELLOW
    li a4, NAVY
    call prg32_gfx_text8
    lw ra, 12(sp)
    addi sp, sp, 16
    ret
