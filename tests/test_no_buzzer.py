"""No reachable buzzer (contracts/prg32-audio-contract-1.json "legacy_buzzer", ADR-0021).

Everything a student or the kit can reach (server code, pages, scripts, blocks, examples,
tutorials, presentations, tools) is searched for the old buzzer. The only places allowed to
name it are the ones that refuse it, each listed here with why. Old content gets a clear
"no longer supported" message; nothing is quietly turned into something else.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from prg32_construction_kit.source_project import validate_asm_source, validate_c_source

ROOT = Path(__file__).resolve().parent.parent
BUZZER = re.compile(r"buzzer|prg32_note_t", re.IGNORECASE)
REACHABLE = ["prg32_construction_kit", "static/js", "templates", "examples", "docs/tutorials", "docs/presentations",
             "tools", "wasm", "app.py"]
SKIP_PARTS = {"vendor", "__pycache__"}
# Where the buzzer may be named, and why.
ALLOWED = {
    "prg32_construction_kit/source_project.py": "the validators refuse it, naming what to use instead",
    "static/js/ide/language.js": "the editor marks it as an error, like the server",
    "static/js/ide/prg32_language_index.js": "only in the 'obsolete' list the editor checks against",
    "tools/build_language_index.py": "keeps it out of suggestions and lists it as obsolete",
    "wasm/prg32_core_api.cpp": "old cartridges calling it are silent and counted (like a board without a buzzer)",
    "static/js/prg32_runtime.js": "reports how many obsolete buzzer calls an old cartridge made",
    "tools/build_audio_fixtures.py": "builds the legacy test cartridge that proves old cartridges stay silent",
    "tools/audio_capture.mjs": "records how many obsolete calls a test cartridge made",
    "tools/build_hardware_audio_check.py": "records that the console check makes no obsolete calls",
    "tools/hardware_audio_compare.py": "explains that a buzzer would show in the silence checks",
}


def reachable_files():
    for entry in REACHABLE:
        path = ROOT / entry
        files = [path] if path.is_file() else [item for item in path.rglob("*") if item.is_file()]
        for item in files:
            if SKIP_PARTS & set(item.parts) or item.suffix in {".wasm", ".png", ".jpg", ".pdf", ".zip", ".prg32"}:
                continue
            yield item


def test_nothing_reachable_names_the_buzzer_except_its_refusal():
    found = []
    for path in reachable_files():
        relative = path.relative_to(ROOT).as_posix()
        if relative in ALLOWED:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if BUZZER.search(line):
                found.append(f"{relative}:{number}: {line.strip()[:100]}")
    assert found == [], "\n".join(found)


def test_the_language_index_names_it_only_as_obsolete():
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import build_language_index

    index = build_language_index.read_committed()
    for key in ("functions", "resident_only", "constants", "types"):
        assert not [item for item in index["c"][key] if BUZZER.search(item["name"])], key
    assert not BUZZER.search(index["header"]["text"])


def test_no_block_or_generated_code_offers_it():
    from test_examples import EXAMPLE_FILES, load_project

    from prg32_construction_kit.asm_generator import ir_to_asm
    from prg32_construction_kit.generator import blocks_to_c

    blocks = (ROOT / "static/js/blockly_blocks.js").read_text()
    assert not BUZZER.search(blocks)
    for path in EXAMPLE_FILES:
        project = load_project(path)
        game_ir, c_source = blocks_to_c(project["blocks_json"], project)
        assert not BUZZER.search(c_source) and not BUZZER.search(ir_to_asm(game_ir)), path.name


LIFECYCLE_C = "void demo_init(void) {{ {call} }}\nvoid demo_update(void) {{}}\nvoid demo_draw(void) {{}}\n"
LIFECYCLE_ASM = ".globl demo_init\n.globl demo_update\n.globl demo_draw\ndemo_init:\n    {call}\n    ret\n" \
                "demo_update:\n    ret\ndemo_draw:\n    ret\n"


@pytest.mark.parametrize("call", ["prg32_buzzer_tone(440, 100, 512);", "prg32_buzzer_play_notes(0, 0);",
                                  "prg32_buzzer_sample_u8(0, 0, 8000);", "prg32_note_t n = {440, 100};",
                                  "void (*f)(uint32_t, uint32_t, uint16_t) = prg32_buzzer_tone;"])
def test_c_projects_using_it_get_a_clear_message(call):
    with pytest.raises(ValueError, match="old PRG32 buzzer, which is no longer supported. Use "):
        validate_c_source('#include "prg32.h"\n' + LIFECYCLE_C.format(call=call), "demo")


@pytest.mark.parametrize("call", ["call prg32_buzzer_tone", "la t0, prg32_buzzer_sample_u8", "tail prg32_buzzer_play_notes"])
def test_assembly_projects_using_it_get_a_clear_message_with_the_line(call):
    with pytest.raises(ValueError, match=r"^Line 5: prg32_buzzer_\w+ belongs to the old PRG32 buzzer"):
        validate_asm_source(LIFECYCLE_ASM.format(call=call), "demo")


def test_mentioning_it_in_a_comment_or_string_is_fine():
    source = '#include "prg32.h"\n/* we used prg32_buzzer_tone once */\n' + LIFECYCLE_C.format(call='(void)"buzzer";')
    assert validate_c_source(source, "demo") == "demo"


def test_a_project_using_it_cannot_be_compiled(client):
    source = '#include "prg32.h"\n' + LIFECYCLE_C.format(call="prg32_buzzer_tone(440, 100, 512);")
    project = client.post("/api/projects", json={"title": "Demo", "game_json": {"source_mode": "c", "source_c": source}})
    project = project.get_json()
    answer = client.post(f"/api/projects/{project['id']}/convert", json={})
    assert answer.status_code == 400 and "no longer supported" in answer.get_json()["error"]


def test_the_index_builder_skips_retired_abi_slots(tmp_path):
    """The proposed SDK change (docs/upstream/prg32-sdk-retire-buzzer.patch) keeps the buzzer's ABI slots
    but without a name (None) and marks them "retired": the language index must not offer them."""
    import json
    import sys

    sys.path.insert(0, str(ROOT / "tools"))
    import build_language_index

    abi = tmp_path / "prg32" / "abi"
    abi.mkdir(parents=True)
    (abi / "abi_generated.py").write_text("ABI_MAJOR = 1\nABI_MINOR = 7\nABI_HASH = 0xb32d1d76\n"
                                          "IMPORT_NAMES = ['prg32_ticks_ms', None, 'prg32_audio_note']\n")
    (abi / "prg32_abi.json").write_text(json.dumps({"functions": [
        {"name": "prg32_ticks_ms"}, {"name": "prg32_buzzer_tone", "retired": {"since": "1.7"}},
        {"name": "prg32_audio_note"}]}))
    loaded = build_language_index.load_abi(tmp_path)
    assert loaded["imports"] == ["prg32_ticks_ms", "prg32_audio_note"]
    assert "prg32_buzzer_tone" not in loaded["functions"]
