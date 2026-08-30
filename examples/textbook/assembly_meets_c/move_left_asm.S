call prg32_input_read     # input bitmask in a0
    mv   t0, a0               # keep our copy
    la   t1, paddle_x
    lw   t2, 0(t1)            # load paddle_x from memory
    andi t3, t0, 1            # isolate the LEFT bit
    beqz t3, 1f               # if LEFT is clear, skip
    addi t2, t2, -3           # paddle_x -= 3
1:  sw   t2, 0(t1)            # store paddle_x back
