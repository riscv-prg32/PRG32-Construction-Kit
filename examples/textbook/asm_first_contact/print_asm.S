.option norelax
.section .text

.global print_init
.global print_update
.global print_draw

print_init:
    addi sp, sp, -16   # make 16-byte frame (keep sp 16-aligned)
    sw   ra, 12(sp)         # save return address into the frame
    call prg32_console_clear # clear text console (C helper)
    la   a0, title  # put address of string in a0 (1st argument)
    call prg32_console_write # print it
    lw   ra, 12(sp)          # restore the return address
    addi sp, sp, 16          # tear down the frame
    ret                      # now ret goes to the right place

print_update:
    ret                     

print_draw:
    ret                     

.section .rodata
title:
    .asciz "HELLO PRG32\n"   # a zero-terminated string