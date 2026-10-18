"""Build the IDE's PRG32 language index from the PRG32 SDK (refinement phase 3, ADR-0014).

    python3 tools/build_language_index.py            # write static/js/ide/prg32_language_index.js
    python3 tools/build_language_index.py --check    # fail if the committed index is out of date
    python3 tools/build_language_index.py --sdk ../PRG32

The IDE's completion, hover, signature help, "go to declaration" and live
diagnostics read this one file; they never ask a server or the internet. Its
inputs are fixed, so the same SDK always gives the same index:

- the PRG32 SDK headers that a cartridge may include (prg32.h and the headers
  it includes), for signatures, constants, types and their comments;
- the SDK's ABI table (prg32/abi): which functions a *portable* cartridge can
  call. A function declared in prg32.h but missing from that table belongs to
  the resident firmware only: a portable cartridge that calls it fails to link;
- the kit's own validators (source_project.py), so the editor suggests exactly
  the headers and assembly directives that the server accepts, and no others;
- the tables below: RV32IMC + Zicsr instructions, registers and the calling
  convention, written for students.

The index also carries a generated, read-only "prg32.h (portable API)" text,
which the editor opens for "go to declaration".
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit import project_format, source_project  # noqa: E402

OUTPUT = ROOT / "static" / "js" / "ide" / "prg32_language_index.js"
SCHEMA = "prg32-language-index/1"
# The headers a cartridge can reach with #include "prg32.h" / "prg32_audio.h", in the SDK.
SDK_HEADERS = (
    "components/prg32/include/prg32.h",
    "components/prg32_audio/include/prg32_audio.h",
    "components/prg32/include/prg32_metrics.h",
    "components/prg32/include/prg32_multiplayer.h",
)
SDK_ABI = ("prg32/abi/abi_generated.py", "prg32/abi/prg32_abi.json")
# The group name of declarations outside a "@name" group, per header.
HEADER_GROUPS = {"prg32_audio.h": "Audio engine", "prg32_metrics.h": "Performance metrics",
                 "prg32_multiplayer.h": "Multiplayer"}

# The preprocessor lines each validator accepts (source_project.validate_c_source / validate_asm_source).
C_PREPROCESSOR = ["include", "define", "undef", "if", "ifdef", "ifndef", "elif", "else", "endif"]
ASM_PREPROCESSOR = ["define", "undef", "if", "ifdef", "ifndef", "elif", "else", "endif"]
ASM_SECTIONS = [".text", ".rodata", ".data", ".bss"]

# Short, student-readable help for the functions most games use. Every other function
# gets the SDK's own comment for its group.
STUDENT_HELP = {
    "prg32_gfx_clear": "Fill the whole game screen with one colour. Call it first in your draw function.",
    "prg32_gfx_rect": "Draw a filled rectangle: top-left corner (x, y), width w, height h, colour.",
    "prg32_gfx_pixel": "Colour one pixel at (x, y).",
    "prg32_gfx_text8": "Write text with the 8x8 font, top-left corner at (x, y).",
    "prg32_gfx_present": "Show the finished frame. The kit's runtime does this for you after draw.",
    "prg32_input_read": "Read the buttons held down now. Test one with  & PRG32_BTN_LEFT  and so on.",
    "prg32_input_read_player": "Read the buttons of player 1 or 2.",
    "prg32_ticks_ms": "Milliseconds since the console started. Compare differences, not absolute times.",
    "prg32_random_number": "A random number. Use  % n  to get a number from 0 to n-1.",
    "prg32_audio_note": "Play a MIDI note (0-127) on a channel for duration_ms milliseconds.",
    "prg32_audio_note_off": "Stop the note on a channel.",
    "prg32_audio_stop_all": "Stop every sound.",
    "prg32_buzzer_tone": "Play a tone on the buzzer: frequency in Hz, duration in ms, duty sets the volume.",
    "prg32_sprite_draw_8x8": "Draw an 8x8 sprite (RGB565 pixels) at (x, y).",
    "prg32_sprite_draw_16x16": "Draw a 16x16 sprite (RGB565 pixels) at (x, y).",
    "prg32_sprite_hitbox": "Check whether two rectangles overlap (for collisions).",
    "prg32_console_write": "Write text on the 40x25 text console.",
    "prg32_score_submit": "Save a score for a game and a player.",
}

# --- RISC-V assembly (the kit builds with -march=rv32imc_zicsr_zifencei, -mabi=ilp32) ---

# (name, syntax, help, extension). Pseudo-instructions are expanded by the assembler.
INSTRUCTIONS = [
    ("lui", "lui rd, imm20", "Load the upper 20 bits: rd = imm20 << 12.", "RV32I"),
    ("auipc", "auipc rd, imm20", "rd = pc + (imm20 << 12). Used for PC-relative addresses.", "RV32I"),
    ("jal", "jal rd, label", "Jump to label and save the return address in rd.", "RV32I"),
    ("jalr", "jalr rd, offset(rs1)", "Jump to rs1 + offset and save the return address in rd.", "RV32I"),
    ("beq", "beq rs1, rs2, label", "Branch to label if rs1 == rs2.", "RV32I"),
    ("bne", "bne rs1, rs2, label", "Branch to label if rs1 != rs2.", "RV32I"),
    ("blt", "blt rs1, rs2, label", "Branch if rs1 < rs2 (signed).", "RV32I"),
    ("bge", "bge rs1, rs2, label", "Branch if rs1 >= rs2 (signed).", "RV32I"),
    ("bltu", "bltu rs1, rs2, label", "Branch if rs1 < rs2 (unsigned).", "RV32I"),
    ("bgeu", "bgeu rs1, rs2, label", "Branch if rs1 >= rs2 (unsigned).", "RV32I"),
    ("lb", "lb rd, offset(rs1)", "Load a signed byte from memory.", "RV32I"),
    ("lh", "lh rd, offset(rs1)", "Load a signed 16-bit half-word from memory.", "RV32I"),
    ("lw", "lw rd, offset(rs1)", "Load a 32-bit word from memory.", "RV32I"),
    ("lbu", "lbu rd, offset(rs1)", "Load an unsigned byte from memory.", "RV32I"),
    ("lhu", "lhu rd, offset(rs1)", "Load an unsigned 16-bit half-word from memory.", "RV32I"),
    ("sb", "sb rs2, offset(rs1)", "Store the low byte of rs2 in memory.", "RV32I"),
    ("sh", "sh rs2, offset(rs1)", "Store the low 16 bits of rs2 in memory.", "RV32I"),
    ("sw", "sw rs2, offset(rs1)", "Store the 32-bit word rs2 in memory.", "RV32I"),
    ("addi", "addi rd, rs1, imm12", "rd = rs1 + imm12 (-2048..2047).", "RV32I"),
    ("slti", "slti rd, rs1, imm12", "rd = 1 if rs1 < imm12 (signed), else 0.", "RV32I"),
    ("sltiu", "sltiu rd, rs1, imm12", "rd = 1 if rs1 < imm12 (unsigned), else 0.", "RV32I"),
    ("xori", "xori rd, rs1, imm12", "rd = rs1 XOR imm12.", "RV32I"),
    ("ori", "ori rd, rs1, imm12", "rd = rs1 OR imm12.", "RV32I"),
    ("andi", "andi rd, rs1, imm12", "rd = rs1 AND imm12.", "RV32I"),
    ("slli", "slli rd, rs1, shamt", "Shift left by shamt bits (0..31).", "RV32I"),
    ("srli", "srli rd, rs1, shamt", "Shift right by shamt bits, filling with zeros.", "RV32I"),
    ("srai", "srai rd, rs1, shamt", "Shift right by shamt bits, keeping the sign.", "RV32I"),
    ("add", "add rd, rs1, rs2", "rd = rs1 + rs2.", "RV32I"),
    ("sub", "sub rd, rs1, rs2", "rd = rs1 - rs2.", "RV32I"),
    ("sll", "sll rd, rs1, rs2", "Shift rs1 left by rs2 bits.", "RV32I"),
    ("slt", "slt rd, rs1, rs2", "rd = 1 if rs1 < rs2 (signed), else 0.", "RV32I"),
    ("sltu", "sltu rd, rs1, rs2", "rd = 1 if rs1 < rs2 (unsigned), else 0.", "RV32I"),
    ("xor", "xor rd, rs1, rs2", "rd = rs1 XOR rs2.", "RV32I"),
    ("srl", "srl rd, rs1, rs2", "Shift rs1 right by rs2 bits, filling with zeros.", "RV32I"),
    ("sra", "sra rd, rs1, rs2", "Shift rs1 right by rs2 bits, keeping the sign.", "RV32I"),
    ("or", "or rd, rs1, rs2", "rd = rs1 OR rs2.", "RV32I"),
    ("and", "and rd, rs1, rs2", "rd = rs1 AND rs2.", "RV32I"),
    ("fence", "fence", "Order memory accesses.", "RV32I"),
    ("fence.i", "fence.i", "Make instruction fetches see earlier stores.", "Zifencei"),
    ("ecall", "ecall", "Call the execution environment. Cartridges call PRG32 functions instead.", "RV32I"),
    ("ebreak", "ebreak", "Stop in the debugger.", "RV32I"),
    ("mul", "mul rd, rs1, rs2", "rd = low 32 bits of rs1 * rs2.", "RV32M"),
    ("mulh", "mulh rd, rs1, rs2", "rd = high 32 bits of rs1 * rs2 (signed).", "RV32M"),
    ("mulhsu", "mulhsu rd, rs1, rs2", "rd = high 32 bits of rs1 (signed) * rs2 (unsigned).", "RV32M"),
    ("mulhu", "mulhu rd, rs1, rs2", "rd = high 32 bits of rs1 * rs2 (unsigned).", "RV32M"),
    ("div", "div rd, rs1, rs2", "rd = rs1 / rs2 (signed). Dividing by 0 gives -1.", "RV32M"),
    ("divu", "divu rd, rs1, rs2", "rd = rs1 / rs2 (unsigned).", "RV32M"),
    ("rem", "rem rd, rs1, rs2", "rd = remainder of rs1 / rs2 (signed).", "RV32M"),
    ("remu", "remu rd, rs1, rs2", "rd = remainder of rs1 / rs2 (unsigned).", "RV32M"),
    ("csrrw", "csrrw rd, csr, rs1", "Swap a control register with rs1.", "Zicsr"),
    ("csrrs", "csrrs rd, csr, rs1", "Read a control register and set the bits of rs1.", "Zicsr"),
    ("csrrc", "csrrc rd, csr, rs1", "Read a control register and clear the bits of rs1.", "Zicsr"),
    ("csrrwi", "csrrwi rd, csr, uimm5", "Swap a control register with a small constant.", "Zicsr"),
    ("csrrsi", "csrrsi rd, csr, uimm5", "Read a control register and set constant bits.", "Zicsr"),
    ("csrrci", "csrrci rd, csr, uimm5", "Read a control register and clear constant bits.", "Zicsr"),
    ("c.addi4spn", "c.addi4spn rd', sp, uimm", "Compressed: rd' = sp + uimm.", "RV32C"),
    ("c.lw", "c.lw rd', offset(rs1')", "Compressed lw.", "RV32C"),
    ("c.sw", "c.sw rs2', offset(rs1')", "Compressed sw.", "RV32C"),
    ("c.nop", "c.nop", "Compressed nop.", "RV32C"),
    ("c.addi", "c.addi rd, imm6", "Compressed addi rd, rd, imm6.", "RV32C"),
    ("c.jal", "c.jal label", "Compressed jal ra, label.", "RV32C"),
    ("c.li", "c.li rd, imm6", "Compressed li.", "RV32C"),
    ("c.addi16sp", "c.addi16sp sp, imm", "Compressed: sp = sp + imm (multiple of 16).", "RV32C"),
    ("c.lui", "c.lui rd, imm6", "Compressed lui.", "RV32C"),
    ("c.srli", "c.srli rd', shamt", "Compressed srli.", "RV32C"),
    ("c.srai", "c.srai rd', shamt", "Compressed srai.", "RV32C"),
    ("c.andi", "c.andi rd', imm6", "Compressed andi.", "RV32C"),
    ("c.sub", "c.sub rd', rs2'", "Compressed sub.", "RV32C"),
    ("c.xor", "c.xor rd', rs2'", "Compressed xor.", "RV32C"),
    ("c.or", "c.or rd', rs2'", "Compressed or.", "RV32C"),
    ("c.and", "c.and rd', rs2'", "Compressed and.", "RV32C"),
    ("c.j", "c.j label", "Compressed j.", "RV32C"),
    ("c.beqz", "c.beqz rs1', label", "Compressed beqz.", "RV32C"),
    ("c.bnez", "c.bnez rs1', label", "Compressed bnez.", "RV32C"),
    ("c.slli", "c.slli rd, shamt", "Compressed slli.", "RV32C"),
    ("c.lwsp", "c.lwsp rd, offset(sp)", "Compressed lw from the stack.", "RV32C"),
    ("c.jr", "c.jr rs1", "Compressed jr.", "RV32C"),
    ("c.mv", "c.mv rd, rs2", "Compressed mv.", "RV32C"),
    ("c.ebreak", "c.ebreak", "Compressed ebreak.", "RV32C"),
    ("c.jalr", "c.jalr rs1", "Compressed jalr ra, 0(rs1).", "RV32C"),
    ("c.add", "c.add rd, rs2", "Compressed add rd, rd, rs2.", "RV32C"),
    ("c.swsp", "c.swsp rs2, offset(sp)", "Compressed sw to the stack.", "RV32C"),
    ("nop", "nop", "Do nothing (addi x0, x0, 0).", "pseudo"),
    ("li", "li rd, value", "Load any 32-bit constant into rd.", "pseudo"),
    ("la", "la rd, symbol", "Load the address of a label or variable into rd.", "pseudo"),
    ("lla", "lla rd, symbol", "Load a PC-relative address into rd.", "pseudo"),
    ("mv", "mv rd, rs", "Copy rs into rd.", "pseudo"),
    ("not", "not rd, rs", "rd = all bits of rs inverted.", "pseudo"),
    ("neg", "neg rd, rs", "rd = -rs.", "pseudo"),
    ("seqz", "seqz rd, rs", "rd = 1 if rs == 0, else 0.", "pseudo"),
    ("snez", "snez rd, rs", "rd = 1 if rs != 0, else 0.", "pseudo"),
    ("sltz", "sltz rd, rs", "rd = 1 if rs < 0, else 0.", "pseudo"),
    ("sgtz", "sgtz rd, rs", "rd = 1 if rs > 0, else 0.", "pseudo"),
    ("beqz", "beqz rs, label", "Branch if rs == 0.", "pseudo"),
    ("bnez", "bnez rs, label", "Branch if rs != 0.", "pseudo"),
    ("blez", "blez rs, label", "Branch if rs <= 0.", "pseudo"),
    ("bgez", "bgez rs, label", "Branch if rs >= 0.", "pseudo"),
    ("bltz", "bltz rs, label", "Branch if rs < 0.", "pseudo"),
    ("bgtz", "bgtz rs, label", "Branch if rs > 0.", "pseudo"),
    ("bgt", "bgt rs1, rs2, label", "Branch if rs1 > rs2 (signed).", "pseudo"),
    ("ble", "ble rs1, rs2, label", "Branch if rs1 <= rs2 (signed).", "pseudo"),
    ("bgtu", "bgtu rs1, rs2, label", "Branch if rs1 > rs2 (unsigned).", "pseudo"),
    ("bleu", "bleu rs1, rs2, label", "Branch if rs1 <= rs2 (unsigned).", "pseudo"),
    ("j", "j label", "Jump to label.", "pseudo"),
    ("jr", "jr rs", "Jump to the address in rs.", "pseudo"),
    ("ret", "ret", "Return to the caller (jr ra).", "pseudo"),
    ("call", "call symbol", "Call a function: saves the return address in ra.", "pseudo"),
    ("tail", "tail symbol", "Jump to a function that returns straight to your caller.", "pseudo"),
    ("csrr", "csrr rd, csr", "Read a control register.", "pseudo"),
    ("csrw", "csrw csr, rs", "Write a control register.", "pseudo"),
    ("csrs", "csrs csr, rs", "Set bits in a control register.", "pseudo"),
    ("csrc", "csrc csr, rs", "Clear bits in a control register.", "pseudo"),
    ("csrwi", "csrwi csr, uimm5", "Write a small constant to a control register.", "pseudo"),
    ("csrsi", "csrsi csr, uimm5", "Set constant bits in a control register.", "pseudo"),
    ("csrci", "csrci csr, uimm5", "Clear constant bits in a control register.", "pseudo"),
    ("rdcycle", "rdcycle rd", "Read the low 32 bits of the cycle counter.", "pseudo"),
    ("rdcycleh", "rdcycleh rd", "Read the high 32 bits of the cycle counter.", "pseudo"),
    ("rdtime", "rdtime rd", "Read the low 32 bits of the timer.", "pseudo"),
    ("rdtimeh", "rdtimeh rd", "Read the high 32 bits of the timer.", "pseudo"),
    ("rdinstret", "rdinstret rd", "Read the low 32 bits of the retired-instruction counter.", "pseudo"),
    ("rdinstreth", "rdinstreth rd", "Read the high 32 bits of the retired-instruction counter.", "pseudo"),
    ("unimp", "unimp", "An illegal instruction: stops the program on purpose.", "pseudo"),
]

# x-number, ABI name, role, who saves it across a call
REGISTERS = [
    (0, "zero", "always 0; writes are ignored", "-"),
    (1, "ra", "return address", "caller"),
    (2, "sp", "stack pointer (keep it a multiple of 16)", "callee"),
    (3, "gp", "global pointer (do not change)", "-"),
    (4, "tp", "thread pointer (do not change)", "-"),
    (5, "t0", "temporary", "caller"),
    (6, "t1", "temporary", "caller"),
    (7, "t2", "temporary", "caller"),
    (8, "s0", "saved register / frame pointer (also called fp)", "callee"),
    (9, "s1", "saved register", "callee"),
    *[(10 + n, f"a{n}", f"argument {n + 1}" + (" and return value" if n == 0 else
                                                    " (second half of a 64-bit result)" if n == 1 else ""), "caller")
      for n in range(8)],
    *[(16 + n, f"s{n}", "saved register", "callee") for n in range(2, 12)],
    *[(25 + n, f"t{n}", "temporary", "caller") for n in range(3, 7)],
]
REGISTER_ALIASES = {"fp": "s0"}

DIRECTIVE_HELP = {
    ".option": (".option push | pop | norelax | rvc | norvc", "Change how the assembler works for the next lines."),
    ".section": (".section .text | .rodata | .data | .bss", "Put what follows into a section. Only these four (and their .name sub-sections) are allowed."),
    ".text": (".text", "What follows is code."),
    ".data": (".data", "What follows is variables with a starting value."),
    ".bss": (".bss", "What follows is variables that start at zero."),
    ".rodata": (".rodata", "What follows is read-only data, like tables and text."),
    ".globl": (".globl symbol", "Make a label visible outside this file. Your init, update and draw labels need it."),
    ".global": (".global symbol", "Same as .globl."),
    ".local": (".local symbol", "Keep a symbol private to this file."),
    ".type": (".type symbol, @function | @object", "Tell the debugger what a symbol is."),
    ".size": (".size symbol, . - symbol", "Tell the debugger how big a symbol is."),
    ".balign": (".balign bytes", "Align the next item to a multiple of bytes."),
    ".align": (".align n", "Align the next item to 2^n bytes."),
    ".p2align": (".p2align n", "Align the next item to 2^n bytes."),
    ".word": (".word value, ...", "Store 32-bit numbers."),
    ".half": (".half value, ...", "Store 16-bit numbers."),
    ".short": (".short value, ...", "Store 16-bit numbers."),
    ".byte": (".byte value, ...", "Store 8-bit numbers."),
    ".2byte": (".2byte value, ...", "Store 16-bit numbers without alignment."),
    ".4byte": (".4byte value, ...", "Store 32-bit numbers without alignment."),
    ".zero": (".zero bytes", "Reserve bytes filled with 0."),
    ".space": (".space bytes", "Reserve bytes filled with 0."),
    ".skip": (".skip bytes", "Reserve bytes filled with 0."),
    ".ascii": ('.ascii "text"', "Store text without an ending 0 byte."),
    ".asciz": ('.asciz "text"', "Store text with an ending 0 byte (a C string)."),
    ".string": ('.string "text"', "Store text with an ending 0 byte (a C string)."),
    ".equ": (".equ NAME, value", "Give a number a name."),
    ".set": (".set NAME, value", "Give a number a name (it can be changed later)."),
    ".equiv": (".equiv NAME, value", "Give a number a name; an error if the name exists."),
}

CALLING_CONVENTION = (
    "Calling a PRG32 function from assembly (RISC-V ilp32): put the arguments in a0, a1, ... a7 "
    "(in order), then `call prg32_name`. The result comes back in a0. A call may change ra, t0-t6 "
    "and a0-a7, so save what you still need (and ra, if your function calls others) on the stack "
    "first; s0-s11 and sp keep their values. Keep sp a multiple of 16."
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sdk_revision(sdk: Path) -> str:
    try:
        result = subprocess.run(["git", "-C", str(sdk), "rev-parse", "--short=7", "HEAD"], capture_output=True,
                                text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip()


def load_abi(sdk: Path) -> dict:
    namespace: dict = {}
    exec(compile((sdk / SDK_ABI[0]).read_text(), SDK_ABI[0], "exec"), namespace)  # noqa: S102 - pinned SDK data file
    table = json.loads((sdk / SDK_ABI[1]).read_text())
    return {"major": namespace["ABI_MAJOR"], "minor": namespace["ABI_MINOR"], "hash": f"0x{namespace['ABI_HASH']:08x}",
            "imports": list(namespace["IMPORT_NAMES"]), "functions": {row["name"]: row for row in table["functions"]}}


def clean_comment(lines: list[str]) -> str:
    text = []
    for line in lines:
        line = re.sub(r"^\s*/\*\*?\s?|\s*\*/\s*$|^\s*\*\s?", "", line).strip()
        line = re.sub(r"@name\s+|@\{|@\}", "", line).strip()
        if line:
            text.append(line)
    return " ".join(text)


def split_params(text: str) -> list[dict]:
    text = text.strip()
    if text in ("", "void"):
        return []
    params = []
    for index, part in enumerate(re.split(r"\s*,\s*", text)):
        match = re.match(r"^(.*?)([A-Za-z_]\w*)\s*(\[[^\]]*\])?$", part)
        if match and match.group(1).strip() and match.group(2) not in ("void", "char", "int"):
            params.append({"type": re.sub(r"\s+", " ", match.group(1).strip() + (match.group(3) or "")),
                           "name": match.group(2)})
        else:
            params.append({"type": part, "name": f"arg{index + 1}"})
    return params


def parse_header(path: Path, relative: str) -> dict:
    """Declarations, object-like PRG32_ macros and prg32_*_t types, with their comments."""
    functions, constants, types = [], [], []
    group, group_doc, comment = "", "", []
    lines = path.read_text().splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if stripped.startswith("/**") and "@name" in stripped:
            block = [line]
            while "@{" not in lines[index] and index + 1 < len(lines):
                index += 1
                block.append(lines[index])
            group = re.sub(r".*@name\s+", "", block[0]).strip()
            group_doc = clean_comment(block[1:])
            comment = []
        elif "@}" in stripped:
            group, group_doc, comment = "", "", []
        elif stripped.startswith("/*"):
            block = [line]
            while "*/" not in lines[index] and index + 1 < len(lines):
                index += 1
                block.append(lines[index])
            comment = block
        elif not stripped:
            comment = []
        elif re.match(r"^#define\s+(PRG32_[A-Z0-9_]+)\s+(\S.*)$", stripped) and "(" not in stripped.split()[1]:
            name, value = re.match(r"^#define\s+(PRG32_[A-Z0-9_]+)\s+(.*)$", stripped).groups()
            constants.append({"name": name, "value": value.strip(), "doc": clean_comment(comment), "header": relative})
        elif re.match(r"^}\s*(prg32_\w+_t)\s*;", stripped) or re.match(r"^typedef\b[^;(]*\b(prg32_\w+_t)\s*;", stripped):
            name = re.search(r"(prg32_\w+_t)\s*;", stripped).group(1)
            types.append({"name": name, "header": relative})
        elif re.match(r"^[A-Za-z_][\w\s*]*\bprg32_\w+\s*\(", stripped) and not stripped.startswith(("typedef", "static")):
            statement = stripped
            while ";" not in statement and index + 1 < len(lines):
                index += 1
                statement += " " + lines[index].strip()
            match = re.match(r"^(.*?)\b(prg32_\w+)\s*\((.*)\)\s*;", re.sub(r"\s+", " ", statement))
            if match:
                returns = match.group(1).strip()
                functions.append({"name": match.group(2), "returns": returns, "params": split_params(match.group(3)),
                                  "group": group or HEADER_GROUPS.get(Path(relative).name, "More functions"),
                                  "group_doc": group_doc, "comment": clean_comment(comment), "header": relative})
            comment = []
        index += 1
    return {"functions": functions, "constants": constants, "types": types}


def signature(function: dict) -> str:
    params = ", ".join(f"{p['type']} {p['name']}".replace("* ", "*") for p in function["params"]) or "void"
    returns = function["returns"]
    return f"{returns}{'' if returns.endswith('*') else ' '}{function['name']}({params})"


def build(sdk: Path) -> dict:
    abi = load_abi(sdk)
    kit_abi = project_format.SDK_ABI
    if (abi["major"], abi["minor"], abi["hash"]) != (kit_abi["major"], kit_abi["minor"], kit_abi["hash"]):
        raise SystemExit(f"the SDK has ABI {abi['major']}.{abi['minor']} {abi['hash']}, the kit builds for "
                         f"{kit_abi['major']}.{kit_abi['minor']} {kit_abi['hash']}")
    parsed = {"functions": [], "constants": [], "types": []}
    for relative in SDK_HEADERS:
        found = parse_header(sdk / relative, relative)
        for key in parsed:
            parsed[key].extend(found[key])
    declared = {}
    for function in parsed["functions"]:
        declared.setdefault(function["name"], function)
    missing = [name for name in abi["imports"] if name not in declared]
    if missing:
        raise SystemExit(f"ABI functions without a declaration in the SDK headers: {', '.join(missing)}")
    portable = set(abi["imports"])
    groups = {}
    for function in parsed["functions"]:
        if function["name"] in portable and function["group_doc"]:
            groups.setdefault(function["group"], function["group_doc"])
    functions, resident = [], []
    for name, function in declared.items():
        row = abi["functions"].get(name, {})
        note = row.get("notes", "")
        summary = STUDENT_HELP.get(name) or (note if note and note != "PRG32 cartridge ABI entry point." else "") \
            or function["comment"] or f"{function['group']}."
        entry = {"name": name, "signature": signature(function), "returns": function["returns"],
                 "params": function["params"], "group": function["group"], "summary": summary,
                 "header": function["header"]}
        if name in portable:
            entry["feature"] = row.get("feature", "core")
            functions.append(entry)
        else:
            resident.append({"name": name, "signature": entry["signature"], "group": function["group"]})
    functions.sort(key=lambda item: abi["imports"].index(item["name"]))
    resident.sort(key=lambda item: item["name"])
    constants = sorted({row["name"]: row for row in parsed["constants"]}.values(), key=lambda item: item["name"])
    types = sorted({row["name"]: row for row in parsed["types"]}.values(), key=lambda item: item["name"])
    revision = sdk_revision(sdk)
    header, lines = portable_header(abi, revision, functions, constants, types)
    for item in functions + constants + types:
        item["line"] = lines[item["name"]]
    return {
        "schema": SCHEMA,
        "generated_by": "tools/build_language_index.py",
        "abi": {"name": kit_abi["name"], "major": abi["major"], "minor": abi["minor"], "hash": abi["hash"]},
        "sdk": {"revision": revision,
                "inputs": {relative: sha256(sdk / relative) for relative in SDK_HEADERS + SDK_ABI}},
        "c": {
            "headers": sorted(source_project._ALLOWED_HEADERS),
            "preprocessor": C_PREPROCESSOR,
            "functions": functions,
            "groups": groups,
            "resident_only": resident,
            "constants": constants,
            "types": types,
            "features": sorted(source_project.FEATURES),
        },
        "asm": {
            "directives": [{"name": name, "syntax": DIRECTIVE_HELP[name][0], "help": DIRECTIVE_HELP[name][1]}
                           for name in sorted(source_project.ALLOWED_ASM_DIRECTIVES)],
            "sections": ASM_SECTIONS,
            "preprocessor": ASM_PREPROCESSOR,
            "instructions": [{"name": n, "syntax": s, "help": h, "extension": e} for n, s, h, e in INSTRUCTIONS],
            "registers": [{"name": f"x{n}", "abi": abi_name, "role": role, "saved_by": saved}
                          for n, abi_name, role, saved in REGISTERS],
            "register_aliases": REGISTER_ALIASES,
            "calling_convention": CALLING_CONVENTION,
        },
        "header": {"name": "prg32.h (portable API)", "text": header},
    }


def portable_header(abi: dict, revision: str, functions: list, constants: list, types: list) -> tuple[str, dict]:
    """The read-only declarations file "go to declaration" opens, and the line of every name in it."""
    out = [
        f"/* PRG32 portable cartridge API: ABI {abi['major']}.{abi['minor']} (hash {abi['hash']}).",
        f" * Generated by tools/build_language_index.py from the PRG32 SDK at {revision}.",
        " * Read-only, for learning. Your game still writes  #include \"prg32.h\".",
        " * A PRG32 cartridge can call exactly the functions listed here. */",
        "",
    ]
    lines = {}
    group = None
    for function in functions:
        if function["group"] != group:
            group = function["group"]
            out.append("")
            out.append(f"/* ==== {group or 'More functions'} ==== */")
        out.append(f"/* {function['summary']}  [feature: {function['feature']}] */")
        lines[function["name"]] = len(out) + 1
        out.append(signature(function) + ";")
    out += ["", "/* ==== Types ==== */"]
    for item in types:
        lines[item["name"]] = len(out) + 1
        out.append(f"/* {item['name']}: see {Path(item['header']).name} in the PRG32 SDK. */")
    out += ["", "/* ==== Constants ==== */"]
    for item in constants:
        lines[item["name"]] = len(out) + 1
        out.append(f"#define {item['name']} {item['value']}")
    return "\n".join(out) + "\n", lines


def render(index: dict) -> str:
    body = json.dumps(index, indent=1, sort_keys=True, ensure_ascii=True)
    return ("// Generated by tools/build_language_index.py from the PRG32 SDK and the kit's validators.\n"
            "// Do not edit: run  python3 tools/build_language_index.py  (ADR-0014).\n"
            "(function (root) { 'use strict'; root.PRG32LanguageIndex = " + body + ";\n"
            "})(typeof window !== 'undefined' ? window : globalThis);\n")


def read_committed() -> dict:
    text = OUTPUT.read_text()
    return json.loads(text[text.index("= ") + 2:text.rindex(";\n})")])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sdk", type=Path, default=Path(os.environ.get("PRG32_SDK_DIR") or ROOT.parent / "PRG32"))
    parser.add_argument("--check", action="store_true", help="fail if the committed index differs")
    args = parser.parse_args()
    if not (args.sdk / SDK_HEADERS[0]).is_file():
        print(f"no PRG32 SDK at {args.sdk} (use --sdk or PRG32_SDK_DIR)", file=sys.stderr)
        return 2
    text = render(build(args.sdk))
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text() != text:
            print(f"{OUTPUT.relative_to(ROOT)} is out of date: run python3 tools/build_language_index.py",
                  file=sys.stderr)
            return 1
        print(f"{OUTPUT.relative_to(ROOT)} is up to date")
        return 0
    OUTPUT.write_text(text)
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
