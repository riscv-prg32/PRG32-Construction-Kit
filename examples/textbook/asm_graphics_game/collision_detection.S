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