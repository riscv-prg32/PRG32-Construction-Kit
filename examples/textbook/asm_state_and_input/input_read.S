.option norelax

.section .data
game_x:  .word 5    # starting value of 5
text_update: .word 0

.section .rodata
program_title: .asciz "INPUT_READ\n"

.section .text
.global input_read_init
.global input_read_update
.global input_read_draw

input_read_init:
    addi sp, sp, -16
    sw   ra, 12(sp)

    # we draw the title and score at the start

    call prg32_console_clear           

    la   a0, program_title
    call prg32_console_write  # draw the title

    la   t0, game_x
    lw   a0, 0(t0)
    # draw the starting x value
    call prg32_console_hex32

    lw   ra, 12(sp)
    addi sp, sp, 16
    ret                     

input_read_update:
    addi sp, sp, -16
    sw   ra, 12(sp)

    call prg32_input_read  # the result is stored in a0
    mv   t0, a0   # t0 now stores the input result
                  

    la   t1, game_x  # t1 = game_x address
    lw   t2, 0(t1)   # t2 = game_x value

    andi t3, t0, 1   # test LEFT (bit 0)
    beqz t3, 1f
    addi t2, t2, -1  # move left

    # when an update occurs, we want to take note 
    # that the screen should update
    li   t4, 1      
    la   t5, text_update
    sw   t4, 0(t5)

1:  andi t3, t0, 2   # test RIGHT (bit 1)
    beqz t3, 2f
    addi t2, t2, 1   # move right

    li   t4, 1         
    la   t5, text_update
    sw   t4, 0(t5)

2:  sw   t2, 0(t1)          # store the new x

    lw   ra, 12(sp)
    addi sp, sp, 16
    ret

input_read_draw:
    addi sp, sp, -16
    sw   ra, 12(sp)
    
    la   t0, text_update # we check if an update has occurred
    lw   t1, 0(t0)
    beqz t1, 2f  # when nothing happens, we skip the draw

    call prg32_console_clear

    la a0, program_title
    call prg32_console_write

    la t0, game_x
    lw a0, 0(t0)
    call prg32_console_hex32  # redraw the current position

    li   t1, 0       # clear the update flag once drawn
    la   t0, text_update
    sw   t1, 0(t0)

2:  lw   ra, 12(sp)
    addi sp, sp, 16
    ret          