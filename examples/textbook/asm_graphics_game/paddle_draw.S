la   t0, paddle_x          # address of the paddle position
lw   a0, 0(t0)             # a0 = x  (a value read from memory)
li   a1, 188               # a1 = y  (near the bottom)
li   a2, 64                # a2 = width
li   a3, 8                 # a3 = height
li   a4, 65535             # a4 = white (RGB565 0xffff)
call prg32_gfx_rect        # draw the paddle