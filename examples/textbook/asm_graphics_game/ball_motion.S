
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
