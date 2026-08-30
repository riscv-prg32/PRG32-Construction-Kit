la t0, hello_x         # t0 = ADDRESS of hello_x
lw t1, 0(t0)           # t1 = VALUE stored at that address
addi t1, t1, 1         # change the value (in the register)
sw t1, 0(t0)           # write the new value back to memory