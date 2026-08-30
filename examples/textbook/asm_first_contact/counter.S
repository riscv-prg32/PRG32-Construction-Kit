.option norelax
.section .data
    counter:  .word 0

.section .rodata
    title:    .asciz "HELLO PRG32\n"

.section .text
.global counter_init
.global counter_update
.global counter_draw

counter_init:
    addi sp, sp, -16
    sw   ra, 12(sp)         # save return address
    
    li   a0, 440            # 440 Hz: a short beep on start
    li   a1, 60             # 60 ms duration
    call prg32_audio_beep   # silent on QEMU, audible on the board

    lw   ra, 12(sp)
    addi sp, sp, 16
    ret

counter_update:
    addi sp, sp, -16
    sw   ra, 12(sp)         # save return address

    la   t0, counter
    lw   t1, 0(t0)
    addi t1, t1, 1          # count one tick per frame
    sw   t1, 0(t0)

    lw   ra, 12(sp)         # load return address
    addi sp, sp, 16
    ret

counter_draw:
    addi sp, sp, -16
    sw   ra, 12(sp)         # save return address

    call prg32_console_clear
    
    la   a0, title
    call prg32_console_write

    la   t0, counter
    lw   a0, 0(t0)
    call prg32_console_hex32 # print numeric value
    
    lw   ra, 12(sp)
    addi sp, sp, 16         # load return address
    ret