"""The kit's proposed PRG32 SDK changes (docs/upstream/) still apply and do what they say.

The kit never changes the SDK checkout: both patches are applied to a copy. This proves:
they apply together, the SDK's generated ABI files match its ABI table, the buzzer slots
keep their indices but lose their names, no public header offers the buzzer, and every
other entry keeps its index. PRG32_REQUIRE_SDK=1 (CI's WebAssembly job) turns a missing
checkout into a failure. The SDK's own test suite is run by hand (docs/upstream/README.md).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_wasm_runtime import PRG32_SDK

ROOT = Path(__file__).resolve().parent.parent
PATCHES = [ROOT / "docs" / "upstream" / "prg32-sdk-audio-clock-and-reset.patch",
           ROOT / "docs" / "upstream" / "prg32-sdk-retire-buzzer.patch"]


@pytest.fixture(scope="module")
def patched(tmp_path_factory):
    if not (PRG32_SDK / "prg32" / "abi" / "prg32_abi.json").is_file():
        if os.environ.get("PRG32_REQUIRE_SDK") == "1":
            pytest.fail(f"no PRG32 SDK checkout at {PRG32_SDK}")
        pytest.skip(f"no PRG32 SDK checkout at {PRG32_SDK} (set PRG32_SOURCE)")
    if shutil.which("git") is None:
        pytest.skip("needs git")
    copy = tmp_path_factory.mktemp("sdk") / "PRG32"
    shutil.copytree(PRG32_SDK, copy, ignore=shutil.ignore_patterns(".git", "build", "build-*", "managed_components", "__pycache__"))
    for patch in PATCHES:
        applied = subprocess.run(["git", "apply", "--directory=", str(patch)], cwd=copy, capture_output=True, text=True)
        assert applied.returncode == 0, f"{patch.name} no longer applies: {applied.stderr}"
    return copy


def generated(copy: Path) -> dict:
    namespace: dict = {}
    exec(compile((copy / "prg32/abi/abi_generated.py").read_text(), "abi_generated.py", "exec"), namespace)  # noqa: S102
    return namespace


def test_the_generated_abi_files_match_the_patched_table(patched):
    result = subprocess.run([sys.executable, "-m", "prg32", "abi", "check"], cwd=patched, capture_output=True, text=True,
                            env={**os.environ, "PYTHONPATH": str(patched)})
    assert result.returncode == 0, result.stderr


def test_the_buzzer_slots_are_retired_and_every_other_slot_keeps_its_index(patched):
    original = json.loads((PRG32_SDK / "prg32/abi/prg32_abi.json").read_text())
    table = json.loads((patched / "prg32/abi/prg32_abi.json").read_text())
    assert (table["major"], table["minor"]) == (1, 7)
    assert len(table["functions"]) == len(original["functions"])
    for index, (before, after) in enumerate(zip(original["functions"], table["functions"])):
        assert before["name"] == after["name"], index          # the slot's history stays readable
        assert bool(after.get("retired")) == (index in (5, 7, 8)), index
    names = generated(patched)["IMPORT_NAMES"]
    assert [index for index, name in enumerate(names) if name is None] == [5, 7, 8]
    assert not any(name and "buzzer" in name for name in names)
    assert generated(patched)["COMPATIBLE_ABI_HASHES"][-1] == 0x260F6136   # 1.6 cartridges still load
    c_table = (patched / "components/prg32/prg32_abi_table.c").read_text()
    assert c_table.count("(const void *)prg32_abi_retired_silent") == 3 and "buzzer" not in c_table


def test_no_public_sdk_header_offers_the_buzzer(patched):
    for header in sorted((patched / "components").glob("*/include/*.h")):
        text = header.read_text()
        assert not re.search(r"\bprg32_buzzer_\w+\s*\(", text), header.name
        assert "prg32_note_t" not in text, header.name


def test_the_examples_use_the_audio_engine(patched):
    for source in sorted((patched / "examples").rglob("game.*")) + sorted((patched / "cartridges").rglob("*.c")):
        if source.suffix in (".c", ".S"):
            assert "prg32_buzzer" not in source.read_text(), source.relative_to(patched)
