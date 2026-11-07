"""PRG32-QT with the PRG32 firmware's audio engine renders exactly what the browser core renders.

PRG32-QT compiles the firmware's engine by default since 7683be1 (riscv-prg32/PRG32-QT#1, the kit's
proposal, merged): its src/core/firmware_audio/ is the kit's wasm/audio/ port. PRG32-QT pins an
older SDK; SDK 1fa8474's engine also needs an esp_log.h and xSemaphoreCreateBinary in the port, which
docs/upstream/prg32-qt-sdk-main.patch adds (the kit never changes the PRG32-QT checkout: the patch
is applied to a copy when the checkout does not have it yet). This test builds prg32qt-headless
against the kit's SDK and requires the same PCM, bit for bit, as the browser core on the
conformance fixture and the console check. PRG32_REQUIRE_SDK=1 (the CI WebAssembly job) turns a
missing checkout into a failure.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from test_wasm_runtime import PRG32_SDK, PRG32QT

ROOT = Path(__file__).resolve().parent.parent
PATCH = ROOT / "docs" / "upstream" / "prg32-qt-sdk-main.patch"
FIXTURES = ROOT / "tests" / "fixtures" / "audio"
PORT = Path("src") / "core" / "firmware_audio"


def missing(reason: str):
    if os.environ.get("PRG32_REQUIRE_SDK") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def test_the_patch_adds_what_the_kits_port_has():
    """What the patch adds to PRG32-QT's port is the kit's wasm/audio, file for file (one source of truth)."""
    text = PATCH.read_text()
    files = dict(re.findall(r"^diff --git a/(\S+) b/\S+\n(?:.*\n)*?^@@[^\n]*\n((?:[+].*\n?)*)", text, re.MULTILINE))
    added = files.get(f"{PORT.as_posix()}/shim/esp_log.h")
    assert added is not None
    assert "".join(line[1:] + "\n" for line in added.splitlines()) == (ROOT / "wasm/audio/shim/esp_log.h").read_text()
    assert "+#define xSemaphoreCreateBinary() ((SemaphoreHandle_t)1)" in text


@pytest.fixture(scope="module")
def patched_prg32qt(tmp_path_factory):
    if not (PRG32QT / "src" / "core" / "Runtime.cpp").is_file():
        missing(f"no PRG32-QT checkout at {PRG32QT} (set PRG32QT_DIR)")
    if not (PRG32QT / PORT / "audio_port.c").is_file():
        missing(f"PRG32-QT at {PRG32QT} is older than 7683be1 (no firmware audio engine)")
    work = tmp_path_factory.mktemp("prg32qt-firmware-audio")
    copy = work / "PRG32-QT"
    shutil.copytree(PRG32QT, copy, ignore=shutil.ignore_patterns("build*", ".git", "*.app"))
    if not (copy / PORT / "shim" / "esp_log.h").is_file():
        applied = subprocess.run(["git", "apply", "--directory=", str(PATCH)], cwd=copy, capture_output=True, text=True)
        assert applied.returncode == 0, "the patch no longer applies to this PRG32-QT: " + applied.stderr
    return copy


def test_the_kits_port_is_prg32qts(patched_prg32qt):
    kit = sorted(path.relative_to(ROOT / "wasm/audio") for path in (ROOT / "wasm/audio").rglob("*") if path.is_file())
    theirs = sorted(path.relative_to(patched_prg32qt / PORT) for path in (patched_prg32qt / PORT).rglob("*") if path.is_file())
    assert kit == theirs
    for name in kit:
        assert (ROOT / "wasm/audio" / name).read_text() == (patched_prg32qt / PORT / name).read_text(), name


@pytest.fixture(scope="module")
def headless(patched_prg32qt):
    if not (PRG32_SDK / "components" / "prg32_audio" / "audio_synth.c").is_file():
        missing(f"no PRG32 SDK checkout at {PRG32_SDK} (set PRG32_SOURCE)")
    if shutil.which("cmake") is None or shutil.which("git") is None:
        missing("needs CMake and git")
    build = patched_prg32qt.parent / "build"
    # The default configuration (no PRG32QT_FIRMWARE_AUDIO option): the firmware engine is on by default.
    subprocess.run(["cmake", "-S", str(patched_prg32qt), "-B", str(build), "-DPRG32QT_BUILD_APP=OFF",
                    f"-DPRG32_SDK_DIR={PRG32_SDK}", "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel", "--target", "prg32qt-headless"], check=True,
                   capture_output=True)
    return build / "prg32qt-headless"


def pcm_hash(headless: Path, cartridge: Path, frames: int) -> tuple[str, int]:
    result = subprocess.run([str(headless), str(cartridge), str(frames)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    found = re.search(r"AUDIO engine=prg32-firmware pcm_fnv1a=([0-9a-f]{16}) obsolete_buzzer_calls=(\d+)", result.stdout)
    assert found, result.stdout
    return found.group(1), int(found.group(2))


def test_prg32qt_renders_the_conformance_fixture_like_the_browser(headless):
    expected = json.loads((FIXTURES / "expected.json").read_text())["pcm_fnv1a"]
    assert pcm_hash(headless, FIXTURES / "conformance.prg32", 170) == (expected, 0)


def test_prg32qt_renders_the_console_check_like_the_browser(headless):
    build = json.loads((FIXTURES / "hardware" / "BUILD.json").read_text())
    assert pcm_hash(headless, FIXTURES / "hardware" / "audio_check-qemu.prg32", build["frames"]) == \
        (build["reference_pcm_fnv1a"], 0)


def test_prg32qt_keeps_old_buzzer_cartridges_silent(headless):
    _hash, calls = pcm_hash(headless, FIXTURES / "legacy_buzzer.prg32", 10)
    assert calls == 2
