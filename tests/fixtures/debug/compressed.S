/* Debugger fixture (ADR-0015): 16-bit (RV32C) and 32-bit instructions side by side.
   Stepping must move the PC by 2 after a compressed instruction and by 4 after a
   normal one, in the browser core and natively. Built by tools/build_debug_fixtures.py. */
    .option norelax
    .section .bss
    .balign 4
counter: .zero 4
    .section .text
    .globl cfix_init
    .globl cfix_update
    .globl cfix_draw
cfix_init:
    c.li a0, 5
    .option push
    .option norvc
    addi a1, zero, 7
    .option pop
    c.mv a2, a0
    c.add a2, a1
    c.slli a2, 2
    c.addi a2, -1
    .option push
    .option norvc
    add a3, a2, a0
    .option pop
    c.beqz a0, 1f
    c.addi a3, 1
1:
    c.jr ra
cfix_update:
    c.addi16sp sp, -16
    c.swsp ra, 12(sp)
    la a5, counter
    c.lw a4, 0(a5)
    c.addi a4, 1
    c.sw a4, 0(a5)
    c.mv a0, a4
    c.jal twice
    c.lwsp ra, 12(sp)
    c.addi16sp sp, 16
    c.jr ra
twice:
    c.add a0, a0
    c.jr ra
cfix_draw:
    c.li a0, 0
    tail prg32_gfx_clear
