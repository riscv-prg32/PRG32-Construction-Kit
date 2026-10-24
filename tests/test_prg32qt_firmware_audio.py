"""PRG32-QT with the PRG32 firmware's audio engine (docs/upstream/prg32-qt-firmware-audio.patch).

PRG32-QT renders sound with its own floating-point mixer, which has no ADSR, so it cannot be an
audio reference as it is. The kit proposes a patch (it never changes the PRG32-QT checkout):
PRG32-QT compiles the firmware's engine by default (PRG32QT_FIRMWARE_AUDIO, ON), as the kit's
browser core does; OFF keeps the old mixer. This test applies the patch to a copy of the checkout, builds prg32qt-headless with it,
and requires the same PCM, bit for bit, as the browser core on the conformance fixture and the
console check. PRG32_REQUIRE_SDK=1 (the CI WebAssembly job) turns a missing checkout into a failure.
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
PATCH = ROOT / "docs" / "upstream" / "prg32-qt-firmware-audio.patch"
FIXTURES = ROOT / "tests" / "fixtures" / "audio"


def missing(reason: str):
    if os.environ.get("PRG32_REQUIRE_SDK") == "1":
        pytest.fail(reason)
    pytest.skip(reason)


def test_the_patch_carries_the_kits_own_audio_port():
    """The port in the patch is the kit's wasm/audio port, file for file (one source of truth)."""
    text = PATCH.read_text()
    files = dict(re.findall(r"^diff --git a/(\S+) b/\S+\n(?:.*\n)*?^@@[^\n]*\n((?:[+].*\n?)*)", text, re.MULTILINE))
    for kit_file in ("audio_port.c", "audio_port.h", "shim/sdkconfig.h", "shim/esp_timer.h"):
        added = files.get(f"src/core/firmware_audio/{kit_file}")
        assert added is not None, kit_file
        body = "".join(line[1:] + "\n" for line in added.splitlines())
        assert body == (ROOT / "wasm" / "audio" / kit_file).read_text(), kit_file


@pytest.fixture(scope="module")
def headless(tmp_path_factory):
    if not (PRG32QT / "src" / "core" / "Runtime.cpp").is_file():
        missing(f"no PRG32-QT checkout at {PRG32QT} (set PRG32QT_DIR)")
    if not (PRG32_SDK / "components" / "prg32_audio" / "audio_synth.c").is_file():
        missing(f"no PRG32 SDK checkout at {PRG32_SDK} (set PRG32_SOURCE)")
    if shutil.which("cmake") is None or shutil.which("git") is None:
        missing("needs CMake and git")
    work = tmp_path_factory.mktemp("prg32qt-firmware-audio")
    copy = work / "PRG32-QT"
    shutil.copytree(PRG32QT, copy, ignore=shutil.ignore_patterns("build*", ".git", "*.app"))
    applied = subprocess.run(["git", "apply", "--directory=", str(PATCH)], cwd=copy, capture_output=True, text=True)
    assert applied.returncode == 0, "the patch no longer applies to this PRG32-QT: " + applied.stderr
    build = work / "build"
    # The default configuration (no PRG32QT_FIRMWARE_AUDIO option): the firmware engine is on by default.
    subprocess.run(["cmake", "-S", str(copy), "-B", str(build), "-DPRG32QT_BUILD_APP=OFF",
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


def test_patched_prg32qt_renders_the_conformance_fixture_like_the_browser(headless):
    expected = json.loads((FIXTURES / "expected.json").read_text())["pcm_fnv1a"]
    assert pcm_hash(headless, FIXTURES / "conformance.prg32", 170) == (expected, 0)


def test_patched_prg32qt_renders_the_console_check_like_the_browser(headless):
    build = json.loads((FIXTURES / "hardware" / "BUILD.json").read_text())
    assert pcm_hash(headless, FIXTURES / "hardware" / "audio_check-qemu.prg32", build["frames"]) == \
        (build["reference_pcm_fnv1a"], 0)


def test_patched_prg32qt_keeps_old_buzzer_cartridges_silent(headless):
    _hash, calls = pcm_hash(headless, FIXTURES / "legacy_buzzer.prg32", 10)
    assert calls == 2
