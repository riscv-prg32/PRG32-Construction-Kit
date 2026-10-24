"""Run generated C and generated RISC-V assembly side by side and log every firmware call.

The C file is compiled with the host C compiler and linked with stub firmware
functions written in C. The assembly is assembled with a RISC-V toolchain and run
in the small RV32IM interpreter below, whose firmware stubs (reached with ecall)
behave exactly like the C ones. Both runs print one line per firmware call; the
two logs must be identical.

The Python stubs print 32-bit registers without masking them, so an argument the
assembly forgot to widen to its C type (uint8_t, uint16_t, int16_t) shows up as
a difference.
"""
from __future__ import annotations

import glob
import os
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
HOST_CC = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")

# name -> (result type, parameter types). "str" is a C string, "bits" an 8-byte picture,
# "peer" a prg32_player_state_t the stub fills in.
SIGNATURES: dict[str, tuple[str, list[str]]] = {
    "prg32_input_read": ("u32", []),
    "prg32_random_number": ("u32", ["u32", "u32"]),
    "prg32_gfx_clear": ("void", ["u16"]),
    "prg32_gfx_clear_indexed": ("void", ["u8"]),
    "prg32_gfx_pixel": ("void", ["int", "int", "u16"]),
    "prg32_gfx_rect": ("void", ["int", "int", "int", "int", "u16"]),
    "prg32_gfx_pixel_indexed": ("void", ["int", "int", "u8"]),
    "prg32_gfx_rect_indexed": ("void", ["int", "int", "int", "int", "u8"]),
    "prg32_palette_set": ("void", ["u8", "u16"]),
    "prg32_gfx_text8": ("void", ["int", "int", "str", "u16", "u16"]),
    "prg32_splash_show_game": ("void", ["str", "str", "u32", "u16", "u16", "u16"]),
    "prg32_band_set_game_info": ("void", ["str"]),
    "prg32_sprite_hitbox": ("int", ["int"] * 8),
    "prg32_sprite_draw_8x8": ("void", ["int", "int", "bits", "u16", "u16"]),
    "prg32_tile_define": ("void", ["u8", "bits", "u16", "u16"]),
    "prg32_playfield_clear": ("void", ["u8", "u8"]),
    "prg32_playfield_put": ("void", ["u8", "u8", "u8", "u8"]),
    "prg32_playfield_get": ("u8", ["u8", "u8", "u8"]),
    "prg32_playfield_scroll": ("void", ["u8", "int", "int"]),
    "prg32_playfield_camera": ("void", ["int", "int"]),
    "prg32_playfield_draw": ("void", ["u8", "int"]),
    "prg32_audio_note": ("void", ["u8", "u8", "u8", "u8", "u32"]),
    "prg32_audio_note_off": ("void", ["u8"]),
    "prg32_audio_set_master_volume": ("void", ["u8"]),
    "prg32_audio_stop_all": ("void", []),
    "prg32_audio_play_track": ("void", ["u16"]),
    "prg32_audio_stop_track": ("void", []),
    "prg32_score_submit_current_player": ("int", ["str", "u32"]),
    "prg32_scoreboard_show": ("int", ["str", "str"]),
    "prg32_score_player_prompt": ("int", []),
    "prg32_multiplayer_join": ("int", ["str", "u32"]),
    "prg32_multiplayer_tick": ("void", []),
    "prg32_multiplayer_set_local_state": ("int", ["i16", "i16", "u16", "u16"]),
    "prg32_multiplayer_get_peer_count": ("int", []),
    "prg32_multiplayer_get_peer": ("int", ["int", "peer"]),
}
_C_TYPES = {"int": "int", "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "i16": "int16_t",
            "str": "const char *", "bits": "const uint8_t *", "peer": "prg32_player_state_t *", "void": "void"}


def find_riscv_gcc() -> str | None:
    """A RISC-V GCC that can build rv32im code: $PRG32_RISCV_GCC, PATH, or ESP-IDF's tools."""
    if os.environ.get("PRG32_RISCV_GCC"):
        return os.environ["PRG32_RISCV_GCC"]
    for name in ("riscv32-esp-elf-gcc", "riscv64-unknown-elf-gcc", "riscv32-unknown-elf-gcc"):
        if shutil.which(name):
            return shutil.which(name)
    found = sorted(glob.glob(os.path.expanduser("~/.espressif/tools/riscv32-esp-elf/*/riscv32-esp-elf/bin/riscv32-esp-elf-gcc")))
    return found[-1] if found else None


def input_script(frames: int) -> list[int]:
    """Button masks for each frame: held buttons, fresh presses, both players."""
    state, out, mask = 12345, [], 0
    for frame in range(frames):
        state = (state * 1103515245 + 12345) & 0xFFFFFFFF
        if frame % 3 == 0:
            mask = (state >> 8) & 0x7F7F
        if frame in (1, 2, 9):
            mask |= 1 << 6  # START
        out.append(mask)
    return out


# ---- the C side -------------------------------------------------------------
def _c_stubs() -> str:
    lines = ['#include <stdio.h>', '#include "prg32.h"',
             "uint32_t harness_input;",
             "static uint32_t harness_seed = 7u;",
             "static void show_str(const char *s) {",
             "    putchar('\"');",
             "    for (; *s; ++s) { unsigned char c = (unsigned char)*s;",
             "        if (c == '\"' || c == '\\\\') printf(\"\\\\%c\", c); else if (c >= 32 && c < 127) putchar(c); else printf(\"\\\\x%02x\", c); }",
             "    putchar('\"');",
             "}",
             "static void show_bits(const uint8_t *b) { int i; putchar('['); for (i = 0; i < 8; ++i) printf(\"%02x\", b[i]); putchar(']'); }"]
    for name, (result, params) in SIGNATURES.items():
        args = ", ".join(f"{_C_TYPES[kind]} p{i}" for i, kind in enumerate(params)) or "void"
        lines.append(f"{_C_TYPES[result]} {name}({args}) {{")
        lines.append(f'    printf("{name}(");')
        for i, kind in enumerate(params):
            if i:
                lines.append('    printf(", ");')
            if kind == "str":
                lines.append(f"    show_str(p{i});")
            elif kind == "bits":
                lines.append(f"    show_bits(p{i});")
            elif kind == "peer":
                lines.append('    printf("&peer");')
            elif kind in ("u8", "u16", "u32"):
                lines.append(f'    printf("%u", (unsigned)p{i});')
            else:
                lines.append(f'    printf("%d", (int)p{i});')
        lines.append('    printf(")\\n");')
        if name == "prg32_input_read":
            lines.append("    return harness_input;")
        elif name == "prg32_random_number":
            lines += ["    harness_seed = harness_seed * 1103515245u + 12345u;",
                      "    if (p1 < p0 || p1 - p0 == 0xFFFFFFFFu) return harness_seed;",
                      "    return p0 + (harness_seed >> 8) % (p1 - p0 + 1u);"]
        elif name == "prg32_sprite_hitbox":
            lines.append("    return p0 < p4 + p6 && p4 < p0 + p2 && p1 < p5 + p7 && p5 < p1 + p3;")
        elif name == "prg32_playfield_get":
            lines.append("    return (uint8_t)(p0 * 7 + p1 * 3 + p2);")
        elif name == "prg32_multiplayer_get_peer_count":
            lines.append("    return 2;")
        elif name == "prg32_multiplayer_get_peer":
            lines += ["    if (p0 < 0 || p0 > 1) return -1;",
                      "    p1->player_id = 100u + (uint32_t)p0; p1->x = (int16_t)(-5 - p0); p1->y = (int16_t)(20 + p0);",
                      "    p1->sprite = (uint16_t)(0x8000 + p0); p1->flags = 0; p1->input = 0; p1->frame = 0; p1->last_seen_ms = 0;",
                      "    return 0;"]
        elif result != "void":
            lines.append("    return 0;")
        lines.append("}")
    return "\n".join(lines) + "\n"


def run_c(source: str, prefix: str, frames: int, work: Path) -> list[str]:
    inputs = input_script(frames)
    (work / "game.c").write_text(source)
    (work / "stubs.c").write_text(_c_stubs())
    (work / "driver.c").write_text("\n".join([
        "#include <stdio.h>", "#include <stdint.h>", "extern uint32_t harness_input;",
        f"void {prefix}_init(void); void {prefix}_update(void); void {prefix}_draw(void);",
        f"static const uint32_t inputs[{frames}] = {{{', '.join(map(str, inputs))}}};",
        "int main(void) { int f;",
        f'    harness_input = inputs[0]; printf("init\\n"); {prefix}_init();',
        f"    for (f = 0; f < {frames}; ++f) {{ harness_input = inputs[f]; printf(\"frame %d\\n\", f);"
        f" {prefix}_update(); {prefix}_draw(); }}",
        "    return 0; }", ""]))
    exe = work / "game_host"
    subprocess.run([HOST_CC, "-std=c99", "-O0", "-fwrapv", "-w", "-I", str(FIXTURES), "-o", str(exe),
                    str(work / "game.c"), str(work / "stubs.c"), str(work / "driver.c")], check=True)
    return subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout.splitlines()


# ---- the assembly side --------------------------------------------------------
_LINKER = """
SECTIONS {
  . = 0x10000;
  .text : { *(.text*) }
  .rodata : { *(.rodata*) }
  . = ALIGN(4);
  .data : { *(.data*) *(.sdata*) }
  . = ALIGN(4);
  .bss : { *(.bss*) *(.sbss*) *(COMMON) }
}
"""


def build_asm(source: str, work: Path, gcc: str) -> tuple[bytes, dict[str, int]]:
    """Assemble and link the game with ecall stubs; return the memory image and the symbols."""
    (work / "game.S").write_text(source)
    stubs = [".section .text", ".balign 4"]
    for index, name in enumerate(SIGNATURES):
        stubs += [f".globl {name}", f"{name}:", f"    li t0, {index}", "    ecall", "    ret"]
    (work / "stubs.S").write_text("\n".join(stubs) + "\n")
    (work / "link.ld").write_text(_LINKER)
    tools = gcc[: -len("gcc")]
    common = ["-march=rv32im", "-mabi=ilp32"]
    subprocess.run([gcc, *common, "-x", "assembler-with-cpp", "-c", str(work / "game.S"), "-o", str(work / "game.o")],
                   check=True, capture_output=True, text=True)
    subprocess.run([gcc, *common, "-c", str(work / "stubs.S"), "-o", str(work / "stubs.o")], check=True)
    subprocess.run([gcc, *common, "-nostdlib", "-Wl,--no-relax", "-Wl,--no-warn-rwx-segments", "-Wl,-T," + str(work / "link.ld"),
                    str(work / "game.o"), str(work / "stubs.o"), "-o", str(work / "game.elf")], check=True)
    subprocess.run([tools + "objcopy", "-O", "binary", str(work / "game.elf"), str(work / "game.bin")], check=True)
    symbols = {}
    for line in subprocess.run([tools + "nm", str(work / "game.elf")], check=True, capture_output=True,
                               text=True).stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            symbols[parts[2]] = int(parts[0], 16)
    return (work / "game.bin").read_bytes(), symbols


def _s32(value: int) -> int:
    value &= 0xFFFFFFFF
    return value - 0x100000000 if value & 0x80000000 else value


class RV32IM:
    """A small RV32IM interpreter: enough to run generated cartridges with stub firmware."""

    BASE = 0x10000
    SIZE = 0x400000
    RETURN = 0xFFFFFFF0

    def __init__(self, image: bytes):
        self.mem = bytearray(self.SIZE)
        self.mem[self.BASE:self.BASE + len(image)] = image
        self.x = [0] * 32
        self.x[2] = self.SIZE - 16
        self.log: list[str] = []
        self.input = 0
        self.seed = 7
        self.decoded: dict[int, tuple] = {}
        self.names = list(SIGNATURES)

    # memory
    def load(self, addr: int, size: int, signed: bool) -> int:
        return int.from_bytes(self.mem[addr:addr + size], "little", signed=signed)

    def store(self, addr: int, size: int, value: int) -> None:
        self.mem[addr:addr + size] = (value & ((1 << (8 * size)) - 1)).to_bytes(size, "little")

    def cstring(self, addr: int) -> bytes:
        end = self.mem.index(0, addr)
        return bytes(self.mem[addr:end])

    # firmware stubs
    def ecall(self) -> None:
        name = self.names[self.x[5]]  # t0 holds the stub number (a7 may be the 8th argument)
        result, params = SIGNATURES[name]
        shown = []
        for index, kind in enumerate(params):
            reg = self.x[10 + index]
            if kind == "str":
                text = "".join(f"\\{chr(b)}" if b in (0x22, 0x5C) else chr(b) if 32 <= b < 127 else f"\\x{b:02x}"
                               for b in self.cstring(reg))
                shown.append(f'"{text}"')
            elif kind == "bits":
                shown.append("[" + self.mem[reg:reg + 8].hex() + "]")
            elif kind == "peer":
                shown.append("&peer")
            elif kind in ("u8", "u16", "u32"):
                shown.append(str(reg))  # unmasked on purpose: the caller must have widened it
            else:
                shown.append(str(_s32(reg)))
        self.log.append(f"{name}({', '.join(shown)})")
        a = [self.x[10 + i] for i in range(8)]
        value = 0
        if name == "prg32_input_read":
            value = self.input
        elif name == "prg32_random_number":
            self.seed = (self.seed * 1103515245 + 12345) & 0xFFFFFFFF
            low, high = a[0], a[1]
            value = self.seed if high < low or high - low == 0xFFFFFFFF else low + (self.seed >> 8) % (high - low + 1)
        elif name == "prg32_sprite_hitbox":
            s = [_s32(v) for v in a]
            value = int(s[0] < _s32(s[4] + s[6]) and s[4] < _s32(s[0] + s[2]) and s[1] < _s32(s[5] + s[7])
                        and s[5] < _s32(s[1] + s[3]))
        elif name == "prg32_playfield_get":
            value = (a[0] * 7 + a[1] * 3 + a[2]) & 0xFF
        elif name == "prg32_multiplayer_get_peer_count":
            value = 2
        elif name == "prg32_multiplayer_get_peer":
            index = _s32(a[0])
            if 0 <= index <= 1:
                self.mem[a[1]:a[1] + 24] = struct.pack("<IhhHHIII", 100 + index, -5 - index, 20 + index,
                                                       0x8000 + index, 0, 0, 0, 0)
            else:
                value = -1
        self.x[10] = value & 0xFFFFFFFF

    def decode(self, pc: int) -> tuple:
        ins = self.load(pc, 4, False)
        op, rd, f3 = ins & 0x7F, (ins >> 7) & 31, (ins >> 12) & 7
        rs1, rs2, f7 = (ins >> 15) & 31, (ins >> 20) & 31, ins >> 25
        imm_i = _s32(ins) >> 20
        imm_s = (_s32(ins) >> 25 << 5) | ((ins >> 7) & 31)
        imm_b = ((_s32(ins) >> 31) << 12) | (((ins >> 7) & 1) << 11) | (((ins >> 25) & 63) << 5) | (((ins >> 8) & 15) << 1)
        imm_u = _s32(ins & 0xFFFFF000)
        imm_j = ((_s32(ins) >> 31) << 20) | (((ins >> 12) & 255) << 12) | (((ins >> 20) & 1) << 11) | (((ins >> 21) & 1023) << 1)
        return (op, rd, f3, rs1, rs2, f7, imm_i, imm_s, imm_b, imm_u, imm_j)

    def call(self, address: int, limit: int = 20_000_000) -> None:
        x = self.x
        x[1] = self.RETURN
        pc = address
        steps = 0
        while pc != self.RETURN:
            steps += 1
            if steps > limit:
                raise RuntimeError("too many instructions (endless loop?)")
            d = self.decoded.get(pc)
            if d is None:
                d = self.decoded[pc] = self.decode(pc)
            op, rd, f3, rs1, rs2, f7, imm_i, imm_s, imm_b, imm_u, imm_j = d
            a, b = x[rs1], x[rs2]
            nxt = pc + 4
            value = None
            if op == 0x13:  # OP-IMM
                if f3 == 0:
                    value = a + imm_i
                elif f3 == 1:
                    value = a << (imm_i & 31)
                elif f3 == 2:
                    value = int(_s32(a) < imm_i)
                elif f3 == 3:
                    value = int(a < (imm_i & 0xFFFFFFFF))
                elif f3 == 4:
                    value = a ^ imm_i
                elif f3 == 5:
                    value = (_s32(a) >> (imm_i & 31)) if (imm_i >> 10) & 1 else (a >> (imm_i & 31))
                elif f3 == 6:
                    value = a | imm_i
                else:
                    value = a & imm_i
            elif op == 0x33:  # OP and the M extension
                if f7 == 1:
                    sa, sb = _s32(a), _s32(b)
                    if f3 == 0:
                        value = sa * sb
                    elif f3 == 1:
                        value = (sa * sb) >> 32
                    elif f3 == 2:
                        value = (sa * b) >> 32
                    elif f3 == 3:
                        value = (a * b) >> 32
                    elif f3 == 4:
                        value = -1 if sb == 0 else sa if (sa == -0x80000000 and sb == -1) else int(abs(sa) // abs(sb)) * (1 if (sa < 0) == (sb < 0) else -1)
                    elif f3 == 5:
                        value = 0xFFFFFFFF if b == 0 else a // b
                    elif f3 == 6:
                        value = sa if sb == 0 else 0 if (sa == -0x80000000 and sb == -1) else sa - sb * (int(abs(sa) // abs(sb)) * (1 if (sa < 0) == (sb < 0) else -1))
                    else:
                        value = a if b == 0 else a % b
                else:
                    if f3 == 0:
                        value = a - b if f7 == 0x20 else a + b
                    elif f3 == 1:
                        value = a << (b & 31)
                    elif f3 == 2:
                        value = int(_s32(a) < _s32(b))
                    elif f3 == 3:
                        value = int(a < b)
                    elif f3 == 4:
                        value = a ^ b
                    elif f3 == 5:
                        value = (_s32(a) >> (b & 31)) if f7 == 0x20 else (a >> (b & 31))
                    elif f3 == 6:
                        value = a | b
                    else:
                        value = a & b
            elif op == 0x03:  # LOAD
                addr = (a + imm_i) & 0xFFFFFFFF
                size, signed = {0: (1, True), 1: (2, True), 2: (4, False), 4: (1, False), 5: (2, False)}[f3]
                value = self.load(addr, size, signed)
            elif op == 0x23:  # STORE
                self.store((a + imm_s) & 0xFFFFFFFF, {0: 1, 1: 2, 2: 4}[f3], b)
            elif op == 0x63:  # BRANCH
                taken = {0: a == b, 1: a != b, 4: _s32(a) < _s32(b), 5: _s32(a) >= _s32(b), 6: a < b, 7: a >= b}[f3]
                if taken:
                    nxt = pc + imm_b
            elif op == 0x37:
                value = imm_u
            elif op == 0x17:
                value = pc + imm_u
            elif op == 0x6F:
                value, nxt = pc + 4, pc + imm_j
            elif op == 0x67:
                value, nxt = pc + 4, (a + imm_i) & 0xFFFFFFFE
            elif op == 0x73:
                self.ecall()
            elif op != 0x0F:
                raise RuntimeError(f"unknown instruction at 0x{pc:x}")
            if value is not None and rd:
                x[rd] = value & 0xFFFFFFFF
            pc = nxt & 0xFFFFFFFF


def run_asm(source: str, prefix: str, frames: int, work: Path, gcc: str) -> list[str]:
    image, symbols = build_asm(source, work, gcc)
    cpu = RV32IM(image)
    inputs = input_script(frames)
    out: list[str] = []
    cpu.input = inputs[0]
    cpu.log.append("init")
    cpu.call(symbols[f"{prefix}_init"])
    for frame in range(frames):
        cpu.input = inputs[frame]
        cpu.log.append(f"frame {frame}")
        for phase in ("update", "draw"):
            saved = [8, 9, *range(18, 28)]  # s0..s11 must survive every call
            for reg in saved:
                cpu.x[reg] = 0x5A000000 + reg
            cpu.call(symbols[f"{prefix}_{phase}"])
            if cpu.x[2] != RV32IM.SIZE - 16:
                raise RuntimeError(f"{phase}: the stack pointer was not restored")
            if any(cpu.x[reg] != 0x5A000000 + reg for reg in saved):
                raise RuntimeError(f"{phase}: a callee-saved register was changed")
    out.extend(cpu.log)
    return out
