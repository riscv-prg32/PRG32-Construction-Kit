    bltz t2, 3f             # if x < 0, clamp to the left edge
    li   t3, 39             # maximum column
    ble  t2, t3, 4f         # if x <= 39, it is already in range
    mv   t2, t3             # otherwise clamp to the right edge
    j    4f
3:  li   t2, 0              # left clamp
4:  sw   t2, 0(t1)          # store the bounded x