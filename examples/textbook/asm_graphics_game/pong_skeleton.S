.section .data
    paddle_x: .word 140
    ball_x: .word 80 
    ball_y: .word 80  
    ball_dx: .word 2   # positive dx means moving right
    ball_dy: .word 2   # positive dy means moving down

.section .text
.global pong_skeleton_init
.global pong_skeleton_update
.global pong_skeleton_draw

pong_skeleton_init:
    ret

pong_skeleton_update:
    addi sp, sp, -16
    sw   ra, 12(sp)     # save return address
    
    # --- PADDLE INPUT AND X MOVEMENT ---
    call prg32_input_read  # read controller bits into a0
    mv   t0, a0            # save input mask in t0

    la   t1, paddle_x
    lw   t2, 0(t1)         # t2 = paddle_x

    andi t3, t0, 1         # test LEFT (bit 0)
    beqz t3, 1f
    addi t2, t2, -3        # move paddle left
1:  andi t3, t0, 2         # test RIGHT (bit 1)
    beqz t3, 2f
    addi t2, t2, 3         # move paddle right

2:   # clamp paddle_x to the visible range [0, 256] 
     # 256 = 320 - 64, the paddle_width

    # --- LEFT CLAMP ---
    bgez t2, clamp_right   # t2 >= 0, then check right side
    li   t2, 0             # else, clamp to 0
    j    store_paddle_x
    
    # --- RIGHT CLAMP ---
clamp_right:
    li   t3, 256
    ble  t2, t3, store_paddle_x  # t2 <= 256, the position is saved.
    li   t2, 256                 # else, clamp it to 256.

store_paddle_x:
    sw   t2, 0(t1)

# --- BALL X MOVEMENT ---
    la   t1, ball_x
    lw   t2, 0(t1)       # t2 = ball x
    la   t3, ball_dx
    lw   t4, 0(t3)       # t4 = ball dx
    add  t2, t2, t4      # x = x + dx

    # Check Left Edge (x < 0)
    bgez t2, check_right_edge
    li   t2, 0           # clamp to left edge
    neg  t4, t4          # reverse direction
    j    save_ball_x

check_right_edge:
    li   t5, 312         # 320 - ball width (8)
    ble  t2, t5, save_ball_x
    mv   t2, t5          # clamp to right edge
    neg  t4, t4          # reverse direction

save_ball_x:
    sw   t2, 0(t1)       # store new x
    sw   t4, 0(t3)       # store dx

# --- BALL Y MOVEMENT ---
    la   t1, ball_y
    lw   t2, 0(t1)       # t2 = ball y
    la   t3, ball_dy
    lw   t4, 0(t3)       # t4 = ball dy
    add  t2, t2, t4      # y = y + dy

    # Check Top Edge (y < 0)
    bgez t2, save_ball_y
    li   t2, 0           # clamp to top edge
    neg  t4, t4          # reverse direction (bounce down)

save_ball_y:
    sw   t2, 0(t1)       # store new y
    sw   t4, 0(t3)       # store new dy 

# --- PADDLE COLLISION CHECK ---
    la   t0, ball_x
    lw   a0, 0(t0)     # a0 = ball x
    la   t0, ball_y
    lw   a1, 0(t0)     # a1 = ball y
    li   a2, 8         # a2 = ball width
    li   a3, 8         # a3 = ball height

    la   t0, paddle_x
    lw   a4, 0(t0)     # a4 = paddle x
    li   a5, 188       # a5 = paddle y
    li   a6, 64        # a6 = paddle width
    li   a7, 8         # a7 = paddle height

    call prg32_sprite_hitbox  # a0 = non-zero if overlapping
    beqz a0, no_overlap       # no overlap: skip the bounce
    
    # overlap found!
    # play a sound
    li   a0, 440            # 440 Hz: a short beep on start
    li   a1, 60             # 60 ms duration
    call prg32_audio_beep   # silent on QEMU, audible on the board

    # reverse direction
    la   t0, ball_dy
    lw   t1, 0(t0)
    blez t1, no_overlap       # only bounce if ball is moving down (t1 > 0)
    neg  t1, t1               # Reverse dy natively
    sw   t1, 0(t0)

no_overlap:
    lw   ra, 12(sp)
    addi sp, sp, 16
    ret

pong_skeleton_draw:
    addi sp, sp, -16
    sw   ra, 12(sp)

    li   a0, 0              # RGB565 black
    call prg32_gfx_clear   # black background

    la   t0, paddle_x      # draw the paddle
    lw   a0, 0(t0)
    li   a1, 188
    li   a2, 64
    li   a3, 8
    li   a4, 65535         # RGB565 white
    call prg32_gfx_rect

    la   t0, ball_x        # draw the ball
    lw   a0, 0(t0)
    la   t0, ball_y
    lw   a1, 0(t0)
    li   a2, 8
    li   a3, 8
    li   a4, 65504         # yellow
    call prg32_gfx_rect

    lw   ra, 12(sp)
    addi sp, sp, 16
    ret