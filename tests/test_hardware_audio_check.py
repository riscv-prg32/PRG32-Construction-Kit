"""The console audio check (docs/hardware_audio_check.md): its cartridges, and the comparison tool.

A real line-out recording is made by a person with a PRG32 console. These tests prove the
comparison tool on recordings made from the reference itself with what an analogue
recording does to it (another sample rate, a delay, lower gain, noise, 24 bits), and that
it fails on what a broken console or cable would produce.
"""

from __future__ import annotations

import hashlib
import json
import math
import random
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tests" / "fixtures" / "audio" / "hardware"
BUILD = json.loads((CHECK / "BUILD.json").read_text())
sys.path.insert(0, str(ROOT / "tools"))


def test_the_committed_check_files_are_the_recorded_ones():
    for name, digest in BUILD["sha256"].items():
        assert hashlib.sha256((CHECK / name).read_bytes()).hexdigest() == digest, name
    assert BUILD["buzzer_calls"] == 0
    document = json.loads((CHECK / "audio_studio.json").read_text())
    assert len(document["voices"]) == 8 and len({voice["pan"] for voice in document["voices"]}) == 8
    assert len({(v["attack"], v["decay"], v["sustain"], v["release"]) for v in document["voices"]}) == 8
    assert any(effect["instrument"]["sound"] == "sample" for effect in document["effects"])
    c_source = (CHECK / "audio_check.c").read_text()
    assert "prg32_audio_play_track(0);" in c_source and "prg32_audio_stop_all();" in c_source
    assert "buzzer" not in c_source


@pytest.fixture(scope="module")
def reference(tmp_path_factory):
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    from hardware_audio_compare import reference_wav

    return reference_wav(tmp_path_factory.mktemp("hw") / "reference.wav")


def read(path: Path) -> tuple[list[int], list[int]]:
    with wave.open(str(path)) as source:
        data = source.readframes(source.getnframes())
    values = struct.unpack(f"<{len(data) // 2}h", data)
    return list(values[0::2]), list(values[1::2])


def recording(reference: Path, out: Path, *, swap=False, tone_in_silence=False, programmes=2) -> Path:
    """What a line-out recording looks like: 48 kHz 24-bit, delayed, quieter, with a little noise."""
    left, right = read(reference)
    if swap:
        left, right = right, left
    rate, gain, rng = 48000, 0.4, random.Random(7)
    lead = [0.0] * int(0.7 * rate)
    channels = []
    for source in (left, right):
        once = []
        for n in range(int(len(source) * rate / 22050)):
            position = n * 22050 / rate
            i = int(position)
            a = source[min(i, len(source) - 1)]
            b = source[min(i + 1, len(source) - 1)]
            once.append((a + (b - a) * (position - i)) / 32768 * gain)
        channels.append(lead + once * programmes)
    frames = bytearray()
    for n in range(len(channels[0])):
        for channel in channels:
            value = channel[n] + rng.gauss(0, 10 ** (-75 / 20))
            if tone_in_silence:
                value += 0.05 * math.sin(2 * math.pi * 1000 * n / rate)
            sample = max(-(1 << 23), min((1 << 23) - 1, int(value * (1 << 23))))
            frames += sample.to_bytes(3, "little", signed=True)
    with wave.open(str(out), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(3)
        target.setframerate(rate)
        target.writeframes(bytes(frames))
    return out


def test_a_good_recording_passes(reference, tmp_path):
    from hardware_audio_compare import compare

    report = compare(recording(reference, tmp_path / "good.wav"), reference)
    assert report["outcome"] == "passed", json.dumps(report["checks"], indent=1)
    assert abs(report["recording"]["programme_starts_at_s"] - 0.7) <= 0.04
    assert report["reference"]["reference_pcm_fnv1a"] == BUILD["reference_pcm_fnv1a"]


def test_swapped_channels_fail_the_separation(reference, tmp_path):
    from hardware_audio_compare import compare

    checks = compare(recording(reference, tmp_path / "swap.wav", swap=True), reference)["checks"]
    assert not checks["separation_left_db"]["ok"] and not checks["separation_right_db"]["ok"]


def test_a_tone_in_the_silence_fails(reference, tmp_path):
    """A buzzer (or any leftover sound) is heard where the console must be silent."""
    from hardware_audio_compare import compare

    report = compare(recording(reference, tmp_path / "tone.wav", tone_in_silence=True), reference)
    assert report["outcome"] == "failed"
    assert not report["checks"]["silence_after_stop_db"]["ok"]


def test_a_recording_shorter_than_a_programme_fails(reference, tmp_path):
    from hardware_audio_compare import compare

    short = tmp_path / "short.wav"
    with wave.open(str(reference)) as source, wave.open(str(short), "wb") as target:
        target.setparams(source.getparams())
        target.writeframes(source.readframes(22050 * 3))
    assert compare(short, reference)["outcome"] == "failed"


def test_mono_recordings_are_refused(tmp_path):
    from hardware_audio_compare import read_wav

    mono = tmp_path / "mono.wav"
    with wave.open(str(mono), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(48000)
        target.writeframes(b"\x00\x00" * 100)
    with pytest.raises(SystemExit, match="stereo"):
        read_wav(mono)


def test_the_check_rebuilds_byte_for_byte_with_the_toolchain():
    """With the PRG32 toolchain, the cartridges are what the kit makes from the AudioStudio project."""
    from prg32_construction_kit.build_check import toolchain_present
    from prg32_construction_kit.config import Config

    if not toolchain_present(Config.PRG32_BUILD_COMMAND):
        pytest.skip("the PRG32 toolchain is not installed")
    result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_hardware_audio_check.py"), "--check"],
                            capture_output=True, text=True, timeout=900)
    assert result.returncode == 0, result.stderr + result.stdout


def i2s_capture(reference: Path, out: Path, *, programmes=2, lead_s=0.4, change=None, width=2) -> Path:
    """What sigrok's I2S decoder writes: the console's own 22050 Hz stereo samples (here, the reference's)."""
    with wave.open(str(reference)) as source:
        frames = source.readframes(source.getnframes())
    data = bytearray(b"\x00" * int(lead_s * 22050) * 4 + frames * programmes)
    if change:
        change(data)
    if width == 4:          # 32-bit slots carrying 16-bit samples
        data = bytearray(b"".join(b"\x00\x00" + bytes(data[i:i + 2]) for i in range(0, len(data), 2)))
    with wave.open(str(out), "wb") as target:
        target.setnchannels(2)
        target.setsampwidth(width)
        target.setframerate(22050)
        target.writeframes(bytes(data))
    return out


@pytest.mark.parametrize("width", [2, 4])
def test_an_exact_i2s_capture_passes_the_strict_checks(reference, tmp_path, width):
    from hardware_audio_compare import compare

    report = compare(i2s_capture(reference, tmp_path / "i2s.wav", width=width), reference, digital=True)
    assert report["outcome"] == "passed", json.dumps(report["checks"], indent=1)
    assert report["checks"]["bit_exact_left_only"]["ok"] and report["checks"]["bit_exact_right_only"]["ok"]


def test_one_changed_sample_in_a_voice_fails_the_bit_exact_check(reference, tmp_path):
    from hardware_audio_compare import compare
    from build_hardware_audio_check import TIMELINE

    def nudge(data):
        lead = int(0.4 * 22050)
        for programme in range(2):
            frame = lead + programme * BUILD["reference_samples"] // 2 + int((TIMELINE["left_only"][0] + 0.25) * 22050)
            data[frame * 4] ^= 1                # one bit of one left sample, in both programmes

    checks = compare(i2s_capture(reference, tmp_path / "nudged.wav", change=nudge), reference, digital=True)["checks"]
    assert not checks["bit_exact_left_only"]["ok"] and checks["bit_exact_right_only"]["ok"]


def test_crosstalk_that_a_microphone_allows_fails_a_digital_capture(reference, tmp_path):
    from hardware_audio_compare import compare

    def leak(data):                             # the left sample also, very quietly, on the right
        for frame in range(0, len(data) // 4):
            left = int.from_bytes(data[frame * 4:frame * 4 + 2], "little", signed=True)
            if left:
                data[frame * 4 + 2:frame * 4 + 4] = (left // 256).to_bytes(2, "little", signed=True)

    checks = compare(i2s_capture(reference, tmp_path / "leak.wav", change=leak), reference, digital=True)["checks"]
    assert not checks["separation_left_db"]["ok"]


def test_a_digital_capture_at_another_rate_is_refused(reference, tmp_path):
    from hardware_audio_compare import compare

    capture = i2s_capture(reference, tmp_path / "rate.wav")
    with wave.open(str(capture)) as source:
        params, frames = source.getparams(), source.readframes(source.getnframes())
    with wave.open(str(capture), "wb") as target:
        target.setparams(params._replace(framerate=44100))
        target.writeframes(frames)
    assert compare(capture, reference, digital=True)["outcome"] == "failed"
