    andi t3, t0, 1   # PRG32_BTN_LEFT is bit 0 (value 1)
    beqz t3, 1f      # if the LEFT bit is clear, skip the add
    addi t1, t1, -1  # LEFT is pressed: move the object left
1: ...