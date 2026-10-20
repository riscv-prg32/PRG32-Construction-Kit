"""Read a debug ELF into the small JSON debug map the Player uses (ADR-0015).

The map has what a classroom debugger needs and nothing that names the server:

    {"schema": "prg32-debug-map/1", "status": "ok", "link_base": 1082130432, "image_size": 6420,
     "files": ["game.c", "portable_stubs.S"],
     "lines": [[address, file, line, is_stmt], ...],          # file -1 = end of a sequence
     "functions": [{"name", "low", "high", "file", "line", "frame_base", "variables": [...],
                    "inlined": [{"name", "ranges": [[low, high], ...], "call_file", "call_line", "depth"}]}],
     "globals": [{"name", "address", "type", "file", "line"}],
     "types": {"<id>": {"kind": "base" | "pointer" | "array" | "struct" | "enum" | ..., ...}},
     "cfi": [{"low", "high", "rows": [[pc, cfa_register, cfa_offset, {"1": -4, ...}], ...]}],
     "symbols": [{"name", "address", "size", "kind": "function" | "object" | "label"}]}

"inlined" (only when the compiler inlined calls into the function) says which
addresses belong to an inlined function, and from which line it was called; the call
stack shows such a function as its own frame, "inlined into" the real one.

The symbols come from the ELF symbol table: they name handwritten assembly's labels
(which have no DWARF functions or variables) in the call stack and the variables view.

A variable's location is a list of operations such as [["fbreg", -20]] or, when it
moves while the function runs, [[low, high, [["reg", 10]]], ...]. The browser evaluates
the simple ones and says "not available here" for the rest.

Anything unexpected (no DWARF, a damaged ELF, a size limit) gives
{"schema": ..., "status": "unavailable", "reason": "..."}: the Player then stays an
address-level debugger. File names keep only their last part.
"""

from __future__ import annotations

import io
from pathlib import Path, PurePosixPath
from typing import Any

SCHEMA = "prg32-debug-map/1"
MAX_ELF_BYTES = 4 * 1024 * 1024
MAX_IMAGE_BYTES = 1024 * 1024     # loadable span; a cartridge's RAM is far smaller
MAX_LINE_ROWS = 200_000
MAX_DIES = 100_000
MAX_TYPE_DEPTH = 12
MAX_INLINED = 2_000          # inlined calls in one map
MAX_INLINE_DEPTH = 16


class DebugInfoError(Exception):
    pass


def unavailable(reason: str) -> dict[str, Any]:
    return {"schema": SCHEMA, "status": "unavailable", "reason": reason}


def _name(value: Any) -> str:
    if isinstance(value, bytes):
        value = value.decode("utf-8", "replace")
    return PurePosixPath(str(value).replace("\\", "/")).name


def _open(path: Path):
    from elftools.elf.elffile import ELFFile

    data = path.read_bytes()
    if len(data) > MAX_ELF_BYTES:
        raise DebugInfoError("the ELF is larger than 4 MiB")
    return ELFFile(io.BytesIO(data))


def elf_image(elf) -> tuple[int, bytes]:
    """The loadable bytes, as `objcopy -O binary` writes them: (first address, bytes)."""
    sections = [s for s in elf.iter_sections()
                if s["sh_flags"] & 0x2 and s["sh_type"] != "SHT_NOBITS" and s["sh_size"] > 0]
    if not sections:
        raise DebugInfoError("the ELF has no loadable sections")
    base = min(s["sh_addr"] for s in sections)
    end = max(s["sh_addr"] + s["sh_size"] for s in sections)
    if end - base > MAX_IMAGE_BYTES:   # a damaged or crafted ELF must not make the server allocate gigabytes
        raise DebugInfoError("the ELF's loadable image is larger than 1 MiB")
    image = bytearray(end - base)
    for section in sections:
        start = section["sh_addr"] - base
        image[start:start + section["sh_size"]] = section.data()
    return base, bytes(image)


def cartridge_code(cartridge: bytes) -> bytes:
    """The code of a PRG2 cartridge: header_size and code_size are in its fixed header."""
    if cartridge[:4] != b"PRG2" or len(cartridge) < 20:
        raise DebugInfoError("not a PRG32 cartridge")
    header_size = int.from_bytes(cartridge[8:10], "little")
    code_size = int.from_bytes(cartridge[16:20], "little")
    return cartridge[header_size:header_size + code_size]


def matches_cartridge(elf_path: Path, cartridge_path: Path) -> bool:
    """True when the ELF holds exactly the code of the cartridge (so its debug info describes it)."""
    try:
        _, image = elf_image(_open(elf_path))
        return image == cartridge_code(cartridge_path.read_bytes())
    except Exception:  # noqa: BLE001 - any doubt means "no debug info", never a failed build
        return False


# --- DWARF ------------------------------------------------------------------------

def _ops(parser, raw) -> list[list[Any]]:
    out = []
    for op in parser.parse_expr(raw):
        name = op.op_name[len("DW_OP_"):] if op.op_name.startswith("DW_OP_") else op.op_name
        out.append([name, *[arg if isinstance(arg, int) else str(arg) for arg in op.args]])
    return out


def _location(die, cu, base: int, locations, parser) -> list[Any] | None:
    from elftools.dwarf.locationlists import LocationEntry

    attribute = die.attributes.get("DW_AT_location")
    if attribute is None:
        return None
    parsed = locations.parse_from_attribute(attribute, cu["version"], die)
    if isinstance(parsed, list):
        ranges = []
        for entry in parsed:
            if isinstance(entry, LocationEntry):
                low = entry.begin_offset if entry.is_absolute else base + entry.begin_offset
                high = entry.end_offset if entry.is_absolute else base + entry.end_offset
                ranges.append([low, high, _ops(parser, entry.loc_expr)])
            elif hasattr(entry, "base_address"):
                base = entry.base_address
        return ranges
    return _ops(parser, parsed.loc_expr)


class _Reader:
    def __init__(self, dwarf):
        from elftools.dwarf.dwarf_expr import DWARFExprParser
        from elftools.dwarf.locationlists import LocationParser

        self.dwarf = dwarf
        self.locations = LocationParser(dwarf.location_lists())
        self.parser = DWARFExprParser(dwarf.structs)
        self.types: dict[str, dict[str, Any]] = {}
        self.dies = 0

    def count(self) -> None:
        self.dies += 1
        if self.dies > MAX_DIES:
            raise DebugInfoError("too much debug information")

    def type_id(self, die, depth: int = 0) -> str | None:
        attribute = die.attributes.get("DW_AT_type")
        if attribute is None:
            return None
        return self.type_of(die.get_DIE_from_attribute("DW_AT_type"), depth)

    def type_of(self, die, depth: int = 0) -> str:
        key = str(die.offset)
        if key in self.types:
            return key
        if depth > MAX_TYPE_DEPTH:
            self.types[key] = {"kind": "unknown"}
            return key
        self.types[key] = {"kind": "unknown"}  # placeholder: breaks cycles (struct with a pointer to itself)
        attrs = die.attributes
        name = attrs["DW_AT_name"].value.decode("utf-8", "replace") if "DW_AT_name" in attrs else ""
        size = attrs["DW_AT_byte_size"].value if "DW_AT_byte_size" in attrs else None
        tag = die.tag
        if tag == "DW_TAG_base_type":
            encoding = attrs["DW_AT_encoding"].value if "DW_AT_encoding" in attrs else 0
            kind = {2: "bool", 5: "signed", 6: "char", 7: "unsigned", 8: "char", 16: "char"}.get(encoding, "unsigned")
            info = {"kind": "base", "name": name, "size": size or 4, "encoding": kind}
        elif tag == "DW_TAG_pointer_type":
            info = {"kind": "pointer", "size": size or 4, "target": self.type_id(die, depth + 1)}
        elif tag in ("DW_TAG_typedef", "DW_TAG_const_type", "DW_TAG_volatile_type"):
            info = {"kind": "alias", "name": name, "target": self.type_id(die, depth + 1)}
        elif tag == "DW_TAG_array_type":
            count = None
            for child in die.iter_children():
                if child.tag == "DW_TAG_subrange_type":
                    if "DW_AT_count" in child.attributes:
                        count = child.attributes["DW_AT_count"].value
                    elif "DW_AT_upper_bound" in child.attributes:
                        count = child.attributes["DW_AT_upper_bound"].value + 1
                    break
            info = {"kind": "array", "target": self.type_id(die, depth + 1), "count": count}
        elif tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
            members = []
            for child in die.iter_children():
                if child.tag == "DW_TAG_member" and "DW_AT_name" in child.attributes:
                    offset = child.attributes.get("DW_AT_data_member_location")
                    members.append({"name": child.attributes["DW_AT_name"].value.decode("utf-8", "replace"),
                                    "offset": offset.value if offset is not None and isinstance(offset.value, int) else 0,
                                    "type": self.type_id(child, depth + 1)})
            info = {"kind": "struct", "name": name, "size": size or 0, "members": members}
        elif tag == "DW_TAG_enumeration_type":
            values = {}
            for child in die.iter_children():
                if child.tag == "DW_TAG_enumerator":
                    values[str(child.attributes["DW_AT_const_value"].value)] = \
                        child.attributes["DW_AT_name"].value.decode("utf-8", "replace")
            info = {"kind": "enum", "name": name, "size": size or 4, "values": values}
        else:
            info = {"kind": "unknown", "name": name}
        self.types[key] = info
        return key

    def variable(self, die, cu, base: int, files: list[str]) -> dict[str, Any] | None:
        origin = die
        if "DW_AT_abstract_origin" in die.attributes:
            origin = die.get_DIE_from_attribute("DW_AT_abstract_origin")
        if "DW_AT_name" not in origin.attributes:
            return None
        attrs = origin.attributes
        line = attrs["DW_AT_decl_line"].value if "DW_AT_decl_line" in attrs else 0
        return {"name": attrs["DW_AT_name"].value.decode("utf-8", "replace"),
                "kind": "parameter" if die.tag == "DW_TAG_formal_parameter" else "local",
                "type": self.type_id(origin), "line": line,
                "location": _location(die, cu, base, self.locations, self.parser)}


def _pc_range(die, base: int) -> tuple[int, int] | None:
    attrs = die.attributes
    if "DW_AT_low_pc" not in attrs or "DW_AT_high_pc" not in attrs:
        return None
    low = attrs["DW_AT_low_pc"].value
    high = attrs["DW_AT_high_pc"]
    return low, (high.value if high.form == "DW_FORM_addr" else low + high.value)


def _ranges(die, cu, base: int, dwarf) -> list[list[int]]:
    """[[low, high], ...] of a DIE: low/high_pc, or DW_AT_ranges (DWARF 4 and 5). Empty ranges dropped."""
    single = _pc_range(die, base)
    if single:
        return [list(single)] if single[1] > single[0] else []
    attribute = die.attributes.get("DW_AT_ranges")
    if attribute is None:
        return []
    lists = dwarf.range_lists()
    if lists is None:
        return []
    if attribute.form == "DW_FORM_rnglistx":
        entries = lists.get_range_list_at_index(attribute.value, cu) if hasattr(lists, "get_range_list_at_index") else []
    else:
        entries = lists.get_range_list_at_offset(attribute.value, cu=cu)
    out = []
    for entry in entries:
        if hasattr(entry, "base_address"):
            base = entry.base_address
        elif hasattr(entry, "begin_offset"):
            low = entry.begin_offset if entry.is_absolute else base + entry.begin_offset
            high = entry.end_offset if entry.is_absolute else base + entry.end_offset
            if high > low:
                out.append([low, high])
    return out


def _inlined(reader: _Reader, die, cu, base: int, file_index, depth: int, out: list) -> None:
    """Every inlined call inside a function, outermost first (depth 0 = called by the function itself)."""
    for child in die.iter_children():
        reader.count()
        if child.tag == "DW_TAG_subprogram":
            continue
        if child.tag == "DW_TAG_inlined_subroutine" and depth < MAX_INLINE_DEPTH:
            origin = child.get_DIE_from_attribute("DW_AT_abstract_origin") \
                if "DW_AT_abstract_origin" in child.attributes else child
            ranges = _ranges(child, cu, base, reader.dwarf)
            if ranges and "DW_AT_name" in origin.attributes:
                attrs = child.attributes
                out.append({"name": origin.attributes["DW_AT_name"].value.decode("utf-8", "replace"), "ranges": ranges,
                            "call_file": file_index(attrs["DW_AT_call_file"].value) if "DW_AT_call_file" in attrs else -1,
                            "call_line": attrs["DW_AT_call_line"].value if "DW_AT_call_line" in attrs else 0,
                            "depth": depth})
                if len(out) > MAX_INLINED:
                    raise DebugInfoError("too many inlined calls")
            _inlined(reader, child, cu, base, file_index, depth + 1, out)
        else:
            _inlined(reader, child, cu, base, file_index, depth, out)


def _line_table(dwarf, cu, files: list[str], rows: list[list[int]]):
    """Add the CU's line rows; return its file-number -> files index function."""
    program = dwarf.line_program_for_CU(cu)
    if program is None:
        return lambda _number: -1
    entries = program["file_entry"]
    version = program["version"]

    def file_index(number: int) -> int:
        index = number if version >= 5 else number - 1
        name = _name(entries[index].name) if 0 <= index < len(entries) else "?"
        if name not in files:
            files.append(name)
        return files.index(name)

    for entry in program.get_entries():
        state = entry.state
        if state is None:
            continue
        if state.end_sequence:
            rows.append([state.address, -1, 0, 0])
        else:
            rows.append([state.address, file_index(state.file), state.line, 1 if state.is_stmt else 0])
        if len(rows) > MAX_LINE_ROWS:
            raise DebugInfoError("the line table is too large")
    return file_index


def _scopes(reader: _Reader, die, cu, base: int, files: list[str], scope: list[int] | None, out: list) -> None:
    for child in die.iter_children():
        reader.count()
        if child.tag in ("DW_TAG_variable", "DW_TAG_formal_parameter"):
            variable = reader.variable(child, cu, base, files)
            if variable:
                if scope:
                    variable["scope"] = scope
                out.append(variable)
        elif child.tag == "DW_TAG_lexical_block":
            inner = _pc_range(child, base)
            _scopes(reader, child, cu, base, files, list(inner) if inner else scope, out)


def _cfi(dwarf) -> list[dict[str, Any]]:
    if not dwarf.has_CFI():
        return []
    out = []
    for entry in dwarf.CFI_entries():
        if "initial_location" not in entry.header:
            continue  # a CIE
        low = entry["initial_location"]
        rows = []
        for row in entry.get_decoded().table:
            cfa = row["cfa"]
            saved = {str(reg): rule.arg for reg, rule in row.items()
                     if isinstance(reg, int) and getattr(rule, "type", "") == "OFFSET"}
            rows.append([row["pc"], cfa.reg, cfa.offset, saved])
        out.append({"low": low, "high": low + entry["address_range"], "rows": rows})
    return sorted(out, key=lambda item: item["low"])


def build_debug_map(elf_path: Path) -> dict[str, Any]:
    """The debug map of one ELF, or unavailable(reason). Never raises."""
    try:
        return _build(elf_path)
    except DebugInfoError as error:
        return unavailable(str(error))
    except Exception as error:  # noqa: BLE001 - a damaged ELF must not break a build
        return unavailable(f"the debug information could not be read ({type(error).__name__})")


def _symbols(elf) -> list[dict[str, Any]]:
    table = elf.get_section_by_name(".symtab")
    if table is None:
        return []
    out = {}
    for symbol in table.iter_symbols():
        name = symbol.name
        kind = {"STT_FUNC": "function", "STT_OBJECT": "object", "STT_NOTYPE": "label"}.get(symbol["st_info"]["type"])
        if (not name or kind is None or symbol["st_shndx"] in ("SHN_UNDEF", "SHN_ABS")
                or name.startswith((".L", "$")) or "." in name):
            continue
        out[(symbol["st_value"], name)] = {"name": name, "address": symbol["st_value"], "size": symbol["st_size"],
                                           "kind": kind}
    return [out[key] for key in sorted(out)]


def _build(elf_path: Path) -> dict[str, Any]:
    elf = _open(elf_path)
    if not elf.has_dwarf_info():
        return unavailable("the cartridge was built without debug information")
    link_base, image = elf_image(elf)
    dwarf = elf.get_dwarf_info()
    reader = _Reader(dwarf)
    files: list[str] = []
    rows: list[list[int]] = []
    functions: list[dict[str, Any]] = []
    globals_: list[dict[str, Any]] = []
    for cu in dwarf.iter_CUs():
        top = cu.get_top_DIE()
        base = top.attributes["DW_AT_low_pc"].value if "DW_AT_low_pc" in top.attributes else 0
        file_index = _line_table(dwarf, cu, files, rows)
        for die in top.iter_children():
            reader.count()
            if die.tag == "DW_TAG_variable":
                variable = reader.variable(die, cu, base, files)
                location = variable and variable["location"]
                if location and not isinstance(location[0][0], int) and location[0][0] == "addr":
                    globals_.append({"name": variable["name"], "address": location[0][1],
                                     "type": variable["type"], "line": variable["line"]})
            elif die.tag == "DW_TAG_subprogram":
                pc = _pc_range(die, base)
                origin = die.get_DIE_from_attribute("DW_AT_abstract_origin") \
                    if "DW_AT_abstract_origin" in die.attributes else die
                if pc is None or "DW_AT_name" not in origin.attributes:
                    continue
                variables: list[dict[str, Any]] = []
                _scopes(reader, die, cu, base, files, None, variables)
                frame = die.attributes.get("DW_AT_frame_base")
                inlined: list[dict[str, Any]] = []
                _inlined(reader, die, cu, base, file_index, 0, inlined)
                functions.append({
                    "name": origin.attributes["DW_AT_name"].value.decode("utf-8", "replace"),
                    "low": pc[0], "high": pc[1],
                    "line": origin.attributes["DW_AT_decl_line"].value if "DW_AT_decl_line" in origin.attributes else 0,
                    "frame_base": _ops(reader.parser, frame.value) if frame is not None else [],
                    "variables": variables, **({"inlined": inlined} if inlined else {})})
                # Function-level statics live at fixed addresses: show them with the globals.
                for variable in variables:
                    location = variable["location"]
                    if location and not isinstance(location[0][0], int) and location[0][0] == "addr":
                        globals_.append({"name": variable["name"], "address": location[0][1],
                                         "type": variable["type"], "line": variable["line"],
                                         "function": functions[-1]["name"]})
    rows.sort(key=lambda row: (row[0], row[1] >= 0))  # at one address, an end of sequence comes first
    return {
        "schema": SCHEMA, "status": "ok", "link_base": link_base, "image_size": len(image),
        "files": files, "lines": rows,
        "functions": sorted(functions, key=lambda item: item["low"]),
        "globals": sorted(globals_, key=lambda item: (item["address"], item["name"])),
        "types": dict(sorted(reader.types.items(), key=lambda item: int(item[0]))),
        "cfi": _cfi(dwarf),
        "symbols": _symbols(elf),
    }
