"""The IDE's language services (refinement phase 3, ADR-0014).

static/js/ide/language.js runs under Node here (tools/language_fixtures.mjs), against the
committed language index (static/js/ide/prg32_language_index.js, made from the PRG32 SDK by
tools/build_language_index.py). The tests prove that:

- completion, hover, signature help, navigation and diagnostics give exactly the answers in
  tests/fixtures/language/cases.json;
- the live checks agree with the server's validators (validate_c_source, validate_asm_source)
  on every fixture and on thousands of generated sources, on the same lines;
- unsafe sources are still refused by the server and flagged by the editor;
- the editor suggests only what the validators accept, and only the portable ABI;
- the index matches the kit's ABI and, where the SDK is checked out, is up to date;
- compiler messages come back without server paths.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from test_examples import EXAMPLE_FILES, load_project
from test_handwritten_assembly import GAME as ASM_GAME

from prg32_construction_kit import project_format, source_project
from prg32_construction_kit.asm_generator import ir_to_asm
from prg32_construction_kit.generator import blocks_to_c, c_identifier
from prg32_construction_kit.source_project import validate_asm_source, validate_c_source

ROOT = Path(__file__).resolve().parent.parent
INDEX_FILE = ROOT / "static" / "js" / "ide" / "prg32_language_index.js"
CASES = json.loads((ROOT / "tests" / "fixtures" / "language" / "cases.json").read_text())
SDK = Path(os.environ.get("PRG32_SDK_DIR") or ROOT.parent / "PRG32")
# The live checks that repeat a server rule; the others (registers, instructions, resident-only
# calls) are extra help about what the compiler or linker would refuse later.
SERVER_RULES = {"empty", "too-big", "trigraph", "comment", "c-include", "c-directive", "c-token-paste", "c-forbidden",
                "c-entry", "asm-file-access", "asm-preprocessor", "asm-directive", "asm-section", "asm-entry",
                "obsolete-buzzer"}
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
sys.path.insert(0, str(ROOT / "tools"))
import build_language_index  # noqa: E402

INDEX = build_language_index.read_committed()
C_LIFECYCLE = "void demo_init(void) {}\nvoid demo_update(void) {}\nvoid demo_draw(void) {}\n"


def run_js(requests: list[dict]) -> list:
    result = subprocess.run(["node", str(ROOT / "tools" / "language_fixtures.mjs")], input=json.dumps(requests),
                            capture_output=True, text=True, check=True, timeout=120)
    return json.loads(result.stdout)


def diagnostics(language: str, source: str, title: str) -> list[dict]:
    return run_js([{"op": "diagnostics", "language": language, "source": source, "title": title}])[0]


def server_verdict(language: str, source: str, title: str):
    """None when the server accepts the source, else its message."""
    try:
        (validate_asm_source if language == "asm" else validate_c_source)(source, title)
    except ValueError as error:
        return str(error)
    return None


# --- exact fixtures ---------------------------------------------------------------------------

@needs_node
def test_every_fixture_gives_exactly_the_recorded_answer():
    answers = run_js([case["request"] for case in CASES])
    for case, answer in zip(CASES, answers):
        assert answer == case["expected"], case["name"]


@needs_node
def test_answers_are_deterministic():
    requests = [case["request"] for case in CASES]
    assert run_js(requests) == run_js(list(requests))


def test_fixtures_cover_every_service_and_language():
    covered = {(case["request"]["op"], case["request"]["language"]) for case in CASES}
    for op in ("completions", "hover", "definition", "diagnostics", "normalize"):
        assert {(op, "c"), (op, "asm")} <= covered, op
    assert ("signatureHelp", "c") in covered


# --- the live checks agree with the server ------------------------------------------------------

C_CORPUS = [
    C_LIFECYCLE,
    '#include "prg32.h"\n/* a "#include" in a comment is fine */\nstatic const char *s = "/* not a comment";\n' + C_LIFECYCLE,
    '#include <stdint.h>\n#define SPEED 3\n#ifdef SPEED\n#endif\n' + C_LIFECYCLE,
    "/* void demo_init(void) {} */\nvoid demo_update(void) {}\nvoid demo_draw(void) {}\n",
    C_LIFECYCLE.replace("demo_update(void)", "demo_update(int x)"),
    C_LIFECYCLE + "void demo_extra(void) { prg32_gfx_clear(0); }\n",
    # the host-access tricks of tests/test_source_project.py
    *[prefix + C_LIFECYCLE for prefix in (
        '/**/ #include "/etc/passwd"\n', '/*\n*/ #include "/etc/passwd"\n', '%:include "/etc/passwd"\n',
        '#\\\ninclude "/etc/passwd"\n', '??=include "/etc/passwd"\n', '#pragma once\n',
        '__asm__(".incbin \\"/etc/passwd\\"");\n', 'void f(void) { asm volatile(""); }\n', '_Pragma("GCC poison x")\n',
        '#define CAT(a, b) a##b\n', '/* never closed\n', '#include <stdio.h>\n', '#include "../prg32.h"\n',
        'int x; /*\n*/ #include "x.h"\n')],
]
ASM_GAME_DEMO = ASM_GAME.replace("my_asm", "demo")
ASM_CORPUS = [
    ASM_GAME_DEMO,
    ASM_GAME_DEMO + '    .section .rodata\nmsg: .asciz "#include .incbin"   # not .incbin\n/* .include */\n',
    "# --- PADDLE INPUT ---\n     # 256 = 320 - 64\n#define SPEED 3\n#ifdef SPEED\n#endif\n" + ASM_GAME_DEMO,
    ASM_GAME_DEMO.replace("demo_draw:\n", "other_draw:\n"),
    ASM_GAME_DEMO.replace("    .globl demo_update\n", ""),
    ASM_GAME_DEMO + "    .equ incbinx, 1\n",
    "/* a\nlong\ncomment */\n" + ASM_GAME_DEMO + "    .fill 1, 1, 0\n",
    # the file-reading and unknown directives of tests/test_handwritten_assembly.py
    *[line + "\n" + ASM_GAME_DEMO for line in (
        '#include "/etc/passwd"', '%:include "/etc/passwd"', '#\\\ninclude "/etc/passwd"', '/**/ #include "x.h"',
        '#import "x.h"', '#embed "/etc/passwd"', '#pragma GCC poison x', '#define F(a) a', '#define D .incbin',
        '#define CAT a##b', '    .incbin "/etc/passwd"', '    .INCBIN "/etc/passwd"', '    .include "other.S"',
        '    .macro boom', '    .irp r, a0, a1', '    .fill 4, 1, 0', '    .section .init_array',
        '    .section .text.x; .incbin "/etc/passwd"', '    nop; .print "hi"', 'label: .rept 3', '??=include "x"')],
]


def check_agreement(language: str, sources: list[str], title: str = "Demo"):
    answers = run_js([{"op": "diagnostics", "language": language, "source": source, "title": title}
                      for source in sources])
    for source, problems in zip(sources, answers):
        verdict = server_verdict(language, source, title)
        mirrored = [problem for problem in problems if problem["code"] in SERVER_RULES]
        if verdict is None:
            assert mirrored == [], (source, mirrored)
        else:
            assert mirrored, (source, verdict)
            reported = re.match(r"Line (\d+): ", verdict)
            if reported:  # the server names a line: the editor marks a problem on that same line
                assert int(reported.group(1)) in {problem["line"] for problem in mirrored}, (source, verdict, mirrored)


@needs_node
def test_live_c_checks_agree_with_the_server():
    check_agreement("c", C_CORPUS)


@needs_node
def test_live_assembly_checks_agree_with_the_server():
    check_agreement("asm", ASM_CORPUS)


def random_sources(pieces: list[str], count: int, seed: int) -> list[str]:
    generator = random.Random(seed)
    return ["".join(generator.choice(pieces) for _ in range(generator.randint(1, 16))) for _ in range(count)]


@needs_node
def test_live_checks_agree_with_the_server_on_generated_sources():
    c_pieces = ["\n", "\r\n", "\\\n", "/*", "*/", "//", "#", '"', "'", " ", "%:", "??=", "##", "include", "<stdio.h>",
                '"prg32.h"', "define X 1", "pragma", "asm", "_Pragma", "void demo_init(void) {}",
                "void demo_update(void) {}", "void demo_draw(void) {}", "void demo_draw(int) {}", "{", "}", "x;"]
    asm_pieces = ["\n", "\r", "\r\n", "\\\n", "/*", "*/", "//", "#", '"', "'", ";", " ", "\t", "\f", ".text", ".fill 1",
                  ".section .init", ".section .data", ".section\t.text", "#define A 1", "#include x", "#if 1", "nop",
                  "demo_init:", ".globl demo_init", "demo_update:", ".globl demo_update", "demo_draw:",
                  ".globl demo_draw", "lbl:", ".incbin", "# comment", ".GLOBL demo_draw", "%:define B 2"]
    check_agreement("c", random_sources(c_pieces, 1500, 3))
    check_agreement("asm", random_sources(asm_pieces, 1500, 4))


@needs_node
def test_kit_generated_sources_are_clean_in_the_editor():
    """Every example's generated C and assembly passes the live checks with no problem at all."""
    sources = []
    for path in EXAMPLE_FILES:
        project = load_project(path)
        ir, c_source = blocks_to_c(project["blocks_json"], project)
        title = project["title"]
        sources.append(("c", c_source, title))
        sources.append(("asm", ir_to_asm(ir), title))
    assert sources, "no example projects found"
    answers = run_js([{"op": "diagnostics", "language": language, "source": source, "title": title}
                      for language, source, title in sources])
    for (language, source, title), problems in zip(sources, answers):
        assert problems == [], (title, language, problems[:3])


# --- suggestions come only from what the server accepts -------------------------------------------

def test_suggested_headers_and_directives_are_exactly_the_allowed_ones():
    assert set(INDEX["c"]["headers"]) == source_project._ALLOWED_HEADERS
    assert {directive["name"] for directive in INDEX["asm"]["directives"]} == source_project.ALLOWED_ASM_DIRECTIVES


def test_suggested_preprocessor_lines_and_sections_are_accepted():
    for word in INDEX["c"]["preprocessor"]:
        line = '#include "prg32.h"' if word == "include" else f"#{word} X 1" if word == "define" else f"#{word} X"
        validate_c_source(line + "\n" + C_LIFECYCLE, "Demo")
    for word in INDEX["asm"]["preprocessor"]:
        line = f"#{word} X 1" if word == "define" else f"#{word} X"
        validate_asm_source(line + "\n" + ASM_GAME_DEMO, "Demo")
    for section in INDEX["asm"]["sections"]:
        validate_asm_source(f"    .section {section}\n" + ASM_GAME_DEMO, "Demo")
    with pytest.raises(ValueError):
        validate_c_source("#pragma once\n" + C_LIFECYCLE, "Demo")


def test_resident_only_functions_are_never_offered_as_portable():
    portable = {function["name"] for function in INDEX["c"]["functions"]}
    resident = {function["name"] for function in INDEX["c"]["resident_only"]}
    assert portable and resident and not portable & resident
    assert "prg32_init" in resident  # firmware-owned: a cartridge must not call it


def test_generated_c_calls_only_portable_functions():
    portable = {function["name"] for function in INDEX["c"]["functions"]}
    resident = {function["name"] for function in INDEX["c"]["resident_only"]}
    for path in EXAMPLE_FILES:
        project = load_project(path)
        called = set(re.findall(r"\b(prg32_\w+)\s*\(", blocks_to_c(project["blocks_json"], project)[1]))
        sdk_calls = called & (portable | resident)
        assert sdk_calls, path.name
        assert sdk_calls <= portable, (path.name, sdk_calls - portable)


# --- the index -----------------------------------------------------------------------------------

def test_index_matches_the_abi_the_kit_builds_for():
    abi = INDEX["abi"]
    assert (abi["major"], abi["minor"], abi["hash"]) == (project_format.SDK_ABI["major"],
                                                          project_format.SDK_ABI["minor"], project_format.SDK_ABI["hash"])
    assert INDEX["schema"] == build_language_index.SCHEMA


def test_navigation_lines_point_at_their_declarations():
    lines = INDEX["header"]["text"].split("\n")
    for function in INDEX["c"]["functions"]:
        assert lines[function["line"] - 1] == function["signature"] + ";"
    for constant in INDEX["c"]["constants"]:
        assert lines[constant["line"] - 1].startswith(f"#define {constant['name']} ")


def test_the_index_holds_no_server_paths_or_secrets():
    text = INDEX_FILE.read_text()
    assert str(ROOT.parent) not in text and "/Users/" not in text and "/home/" not in text
    assert not re.search(r"(?i)(password|token|secret)\s*[:=]", text)


@pytest.mark.skipif(not (SDK / build_language_index.SDK_HEADERS[0]).is_file(), reason="no PRG32 SDK checkout (PRG32_SDK_DIR)")
def test_index_is_up_to_date_with_the_sdk():
    """Regenerating from the SDK gives the committed file byte for byte (only where the SDK is the pinned one)."""
    built = build_language_index.build(SDK)
    if built["sdk"]["inputs"] != INDEX["sdk"]["inputs"]:
        pytest.skip(f"the PRG32 SDK checkout ({built['sdk']['revision']}) is not the one the index was made from "
                    f"({INDEX['sdk']['revision']})")
    assert build_language_index.render(built) == INDEX_FILE.read_text()
    obsolete = set(source_project.OBSOLETE_FUNCTIONS)
    assert [function["name"] for function in built["c"]["functions"]] == [
        name for name in build_language_index.load_abi(SDK)["imports"] if name not in obsolete]


def test_the_obsolete_buzzer_is_never_offered():
    """Not a completion, not in the read-only header, not a type: only in the "obsolete" list."""
    offered = {item["name"] for key in ("functions", "resident_only", "constants", "types") for item in INDEX["c"][key]}
    assert not {name for name in offered if "buzzer" in name.lower() or name == "prg32_note_t"}
    assert "buzzer" not in INDEX["header"]["text"].lower()
    assert {item["name"] for item in INDEX["c"]["obsolete"]} == {*source_project.OBSOLETE_FUNCTIONS,
                                                                 *source_project.OBSOLETE_TYPES}


# --- the server's messages and the compiler's --------------------------------------------------------

def test_entry_names_are_computed_like_the_server():
    titles = ["Demo", "3 Little Pigs!", "  ", "", "Ünïcödé game", "a" * 80, "__x__", "Pong 2", "-"]
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    answers = run_js([{"op": "entryPrefix", "title": title} for title in titles])
    assert answers == [c_identifier(title, "prg32_game") for title in titles]


@needs_node
def test_compiler_messages_come_back_without_server_paths():
    for case in CASES:
        if case["request"]["op"] == "normalize":
            text = json.dumps(case["expected"])
            assert "/srv/" not in text and "/home/" not in text and ".espressif" not in text, case["name"]


def test_server_line_numbers_follow_the_students_lines():
    source = "/* a\nlong\ncomment */\n" + ASM_GAME_DEMO + "    .fill 1, 1, 0\n"
    with pytest.raises(ValueError, match=rf"^Line {source.count(chr(10))}: the directive .fill"):
        validate_asm_source(source, "Demo")
    joined = "    li a0, 1 \\\n  + 2\n    .fill 1\n" + ASM_GAME_DEMO
    with pytest.raises(ValueError, match=r"^Line 3: the directive .fill"):
        validate_asm_source(joined, "Demo")
