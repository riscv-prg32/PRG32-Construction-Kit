# Writing a cartridge in RISC-V assembly

Blocks can show you the assembly they turn into (`generated_code.md`). When
you are ready, you can write the whole game in assembly yourself.

## Start a project

1. **New Project**, choose **Assembly (RISC-V)** and give it a title, for example **Bouncer**.
   It starts from a small working game, explained line by line. (A Blocks project can also
   become assembly once: **Project, Convert to Assembly…** in the IDE.)
2. Change it, press **Save**: the compiler checks it and lists problems at their lines.
3. **Run** plays it in the simulator on the right; **Compile** makes the cartridges.

The browser simulator runs Blocks only. Test assembly cartridges on QEMU,
PRG32-QT or a PRG32 console.

## The three labels

The console calls three functions. Their names come from the title: `Bouncer`
→ `bouncer_init`, `bouncer_update`, `bouncer_draw`. Each must be a label and
must be made visible with `.globl`:

```asm
/* Bouncer: counts frames. */
    .option norelax
    .section .data
    .balign 4
frames: .word 0

    .section .text
    .globl bouncer_init
    .globl bouncer_update
    .globl bouncer_draw
bouncer_init:
    ret
bouncer_update:
    la   t0, frames          # t0 = address of frames
    lw   t1, 0(t0)
    addi t1, t1, 1           # frames = frames + 1
    sw   t1, 0(t0)
    ret
bouncer_draw:
    ret
```

The file goes through the C preprocessor before the assembler, so:

- write full-line comments as `/* ... */` (a line starting with `#` followed by
  text also works, unless the first word is a preprocessor word such as
  `if`, `define` or `include`);
- after an instruction, `#` starts a comment;
- `#define SPEED 3` and `#if` / `#ifdef` / `#else` / `#endif` are allowed.

## What is allowed

| Allowed | Examples |
| --- | --- |
| Sections | `.text`, `.rodata`, `.data`, `.bss`, `.section .data` |
| Symbols | `.globl`, `.global`, `.local`, `.type`, `.size` |
| Alignment | `.balign`, `.align`, `.p2align` |
| Data | `.word`, `.half`, `.short`, `.byte`, `.2byte`, `.4byte`, `.zero`, `.space`, `.skip` |
| Text | `.ascii`, `.asciz`, `.string` |
| Constants | `.equ`, `.set`, `.equiv` |
| Options | `.option norelax` (and other `.option` settings) |
| Instructions | every RV32IMC instruction the assembler knows |

**Not allowed:** `#include`, `.include`, `.incbin` and anything else that
could read a file on the server, macros (`.macro`, `.rept`, `.irp`,
`#define` with arguments), and other sections. The words `include` and
`incbin` are refused anywhere in your code (but are fine inside strings and
comments). The kit tells you the line and the reason.

## For teachers

- Assembly projects export and import like any other project
  (`project_archive.md`): the archive holds `src/game.S`.
- The check protects the server from file-reading tricks; it does not make
  compiling a sandbox. Keep builds for trusted users until per-build
  containers exist (`security.md`).
- In the IDE the assembly editor suggests instructions, registers, the allowed
  directives and PRG32 functions, and underlines problems while you type
  (`ide.md`).
- Design record: `adr/0004-handwritten-assembly-mode.md`.
