"""The eight-voice audio engine in the browser core, on the conformance cartridge (ADR-0021).

tests/fixtures/audio/conformance.prg32 (tools/build_audio_fixtures.py) runs in the
WebAssembly core under Node (tools/audio_capture.mjs). What is checked comes from
contracts/prg32-audio-contract-1.json, not from the engine's own output:

- all 8 voices sound at once, each with its own waveform, ADSR, volume and pan;
- sustain levels are exactly sustain * 257; releases end; the attack of a slow voice lasts;
- hard left and hard right are really separate (zero energy on the other side);
- channel pan, channel volume and master volume change the sound while voices play;
- the mix clips at the 16-bit limits and never beyond; stop and release leave exact silence;
- the soundtrack in the cartridge's audio block plays instrument N on voice N;
- a note on a busy voice replaces it; an old buzzer cartridge is silent and counted;
- a damaged audio block stops the cartridge from loading, as on the console;
- the run is deterministic, equal to the native build, and to the recorded trace and hash.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures" / "audio"
CONTRACT = json.loads((ROOT / "contracts" / "prg32-audio-contract-1.json").read_text())
EXPECTED = FIXTURES / "expected.json"
FRAMES = 170
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")


def capture(cartridge: str, frames: int = FRAMES, module: str | None = None, label: str | None = None) -> dict:
    """Run a fixture cartridge in the browser core. With PRG32_AUDIO_EVIDENCE=<folder> (CI sets it),
    its stereo PCM (WAV) and the per-frame voice trace (JSON) are kept there as evidence."""
    evidence = os.environ.get("PRG32_AUDIO_EVIDENCE")
    wav = []
    if evidence and label:
        Path(evidence).mkdir(parents=True, exist_ok=True)
        wav = [str(Path(evidence) / f"{label}.wav")]
    command = ["node", str(ROOT / "tools" / "audio_capture.mjs"), *(["--module", module] if module else []),
               str(FIXTURES / cartridge), str(frames), *wav]
    result = subprocess.run(command, capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr
    if wav:
        (Path(evidence) / f"{label}.json").write_text(result.stdout)
    return json.loads(result.stdout)


@pytest.fixture(scope="module")
def run():
    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    return capture("conformance.prg32", label="conformance-wasm")


def frame(run, number):
    return run["frames"][number]


def active(run, number):
    return [voice["active"] for voice in frame(run, number)["voices"]]


def adsr_ms(value: int) -> float:
    return 0 if value == 0 else 1 + value * value * 2000 // 65025    # the contract's formula


def envelope_ms(value: int, distance: int) -> float:
    """How long a stage really takes: the level moves by a whole step per sample (contract "adsr")."""
    samples = max(1, 22050 * adsr_ms(value) // 1000)
    step = -(-distance // samples)
    return -(-distance // step) * 1000 / 22050


def test_eight_voices_sound_at_once_each_with_its_own_envelope(run):
    voices = frame(run, 2)["voices"]
    assert all(voice["active"] and voice["synth"] for voice in voices)
    assert [voice["pan"] for voice in voices] == [-64, -45, -27, -9, 9, 27, 45, 63]
    assert [voice["volume"] for voice in voices] == [255, 230, 205, 180, 155, 130, 105, 80]
    assert len({voice["state"] for voice in voices}) >= 3       # attack, decay and sustain at the same time
    assert frame(run, 2)["peakLeft"] > 0 and frame(run, 2)["peakRight"] > 0


def test_sustain_levels_are_exactly_sustain_times_257(run):
    sustains = [160, 200, 120, 60, 255, 80, 230, 255]
    voices = frame(run, 22)["voices"]                              # every voice has reached sustain
    assert all(voice["state"] == 3 for voice in voices)
    assert [voice["level"] for voice in voices] == [value * 257 for value in sustains]


def test_a_slow_attack_lasts_its_time_and_releases_end(run):
    attack_frames = envelope_ms(100, 65535) / (1000 / 30)          # voice 4: about 308 ms, 9 frames
    in_attack = [number for number in range(2, 20) if frame(run, number)["voices"][4]["state"] == 1]
    assert abs(len(in_attack) - attack_frames) <= 2
    for voice, release, sustain in ((0, 80, 160), (1, 40, 200), (2, 120, 120), (3, 30, 60)):   # released at 24
        ended = next(number for number in range(24, 40) if not active(run, number)[voice])
        assert abs(ended - 24 - envelope_ms(release, sustain * 257) / (1000 / 30)) <= 1.5, (voice, ended)
        assert frame(run, 25)["voices"][voice]["state"] in (4, 0)
    assert all(active(run, 30)[4:])                                # 4..7 still sustaining


def test_hard_left_and_hard_right_are_separate(run):
    left_only = [frame(run, number) for number in range(45, 59)]   # the sample, pan -64
    assert all(item["energyRight"] == 0 for item in left_only) and sum(item["energyLeft"] for item in left_only) > 0
    right_only = [frame(run, number) for number in range(61, 70)]  # one voice, pan 63
    assert all(item["energyLeft"] == 0 for item in right_only) and sum(item["energyRight"] for item in right_only) > 0


def test_pan_and_volume_changes_act_on_playing_voices(run):
    assert frame(run, 13)["voices"][2]["pan"] == 63                # moved hard right at frame 12
    assert frame(run, 13)["voices"][5]["volume"] == 130            # its note volume stays; the channel is turned down
    before = sum(frame(run, number)["energyLeft"] + frame(run, number)["energyRight"] for number in (16, 17))
    after = sum(frame(run, number)["energyLeft"] + frame(run, number)["energyRight"] for number in (20, 21))
    assert 0.25 < after / before < 0.5                             # master 160 -> 96: about (96/160)^2 = 0.36


def test_the_mix_clips_at_the_16_bit_limits(run):
    loud = [frame(run, number) for number in range(135, 144)]
    assert all(item["clipped"] for item in loud)
    assert all(item["peakLeft"] <= 32768 and item["peakRight"] <= 32768 for item in run["frames"])


def test_stop_and_release_leave_exact_silence(run):
    for first, last in ((41, 43), (131, 133), (145, 147), (157, FRAMES)):
        for number in range(first, last + 1):
            item = frame(run, number)
            assert item["count"] > 0 and item["peakLeft"] == 0 and item["peakRight"] == 0, number
            assert not any(active(run, number)), number


def test_the_soundtrack_plays_instrument_n_on_voice_n(run):
    voices = frame(run, 71)["voices"]
    assert active(run, 71)[:3] == [1, 1, 1]
    assert voices[2]["state"] == 1 and voices[1]["state"] in (2, 3)    # instrument 2 attacks slowly, 1 at once
    assert any(frame(run, number)["voices"][7]["active"] for number in range(80, 120))
    assert sum(frame(run, number)["energyLeft"] for number in range(71, 120)) > 0


def test_a_note_on_a_busy_voice_replaces_it(run):
    voice = frame(run, 149)["voices"][0]
    assert voice["active"] and voice["state"] == 1                 # instrument 2's attack, not instrument 1's
    assert not any(active(run, 149)[1:])


def test_the_run_is_deterministic_and_matches_the_record(run):
    again = capture("conformance.prg32")
    assert again["pcm_fnv1a"] == run["pcm_fnv1a"] == run["state"]["audio_pcm_fnv1a"]
    assert run["samples"] == 2 * sum(item["count"] for item in run["frames"]) and run["dropped"] == 0
    trace = [[[v["active"], v["state"], v["level"], v["volume"], v["pan"]] for v in item["voices"]]
             for item in run["frames"]]
    record = {"pcm_fnv1a": run["pcm_fnv1a"], "samples": run["samples"], "voice_trace": trace}
    if os.environ.get("PRG32_RECORD_AUDIO") == "1":
        EXPECTED.write_text(json.dumps(record, separators=(",", ":")) + "\n")
    assert json.loads(EXPECTED.read_text()) == record


@needs_node
def test_an_old_buzzer_cartridge_is_silent_and_counted():
    legacy = capture("legacy_buzzer.prg32", frames=10, label="legacy-buzzer-wasm")
    assert legacy["buzzer_calls"] == 2
    assert all(item["peakLeft"] == 0 and item["peakRight"] == 0 for item in legacy["frames"])


@needs_node
def test_a_damaged_audio_block_stops_the_cartridge_from_loading(tmp_path):
    cartridge = bytearray((FIXTURES / "conformance.prg32").read_bytes())
    block = cartridge.index(b"AUD0")
    cartridge[block + 8:block + 10] = (200).to_bytes(2, "little")   # sample_count beyond the limit (64)
    damaged = tmp_path / "damaged.prg32"
    damaged.write_bytes(bytes(cartridge))
    result = subprocess.run(["node", str(ROOT / "tools" / "audio_capture.mjs"), str(damaged), "1"],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 3 and ("AUDIO block" in result.stderr or "AUD0" in result.stderr)


def test_the_contract_numbers_the_test_relies_on():
    assert CONTRACT["voices"]["count"] == 8 and CONTRACT["output"]["sample_rate_hz"] == 22050
    assert CONTRACT["adsr"]["sustain_level"] == "sustain * 257 of 65535"
    assert adsr_ms(255) == 2001 and adsr_ms(1) == 1


def test_the_native_build_renders_the_same_samples(run, tmp_path_factory):
    """The same engine compiled natively (the golden-test harness) gives the same PCM, bit for bit."""
    from test_wasm_runtime import PRG32_SDK, PRG32QT, native_states

    if not (PRG32QT / "src" / "core" / "Runtime.cpp").is_file() or shutil.which("cmake") is None:
        pytest.skip("needs a PRG32-QT checkout and CMake")
    if not (PRG32_SDK / "components" / "prg32_audio" / "audio_synth.c").is_file():
        pytest.skip("needs a PRG32 SDK checkout")
    build = tmp_path_factory.mktemp("audio-native")
    subprocess.run(["cmake", "-S", str(ROOT / "wasm"), "-B", str(build), f"-DPRG32QT_DIR={PRG32QT}",
                    f"-DPRG32_DIR={PRG32_SDK}", "-DCMAKE_BUILD_TYPE=Release"], check=True, capture_output=True)
    subprocess.run(["cmake", "--build", str(build), "--parallel"], check=True, capture_output=True)
    native = native_states(build / "prg32-core-harness", FIXTURES / "conformance.prg32", frames=FRAMES, every=10)
    wasm = {item["frame"]: item for item in run["frames"]}
    assert native[-1]["audio_pcm_fnv1a"] == run["pcm_fnv1a"]
    assert native[-1]["frames"] == FRAMES and wasm[FRAMES]["count"] > 0


@needs_node
def test_the_qemu_firmware_evidence_still_holds():
    """docs/evidence/qemu-audio: the firmware recordings are intact, this browser core still renders the
    recorded browser side, and comparing them again gives the recorded equal runs."""
    import hashlib
    import sys
    import wave

    sys.path.insert(0, str(ROOT / "tools"))
    from qemu_audio_capture import compare

    evidence = ROOT / "docs" / "evidence" / "qemu-audio" / "2026-10-21"
    cartridges = {"conformance": FIXTURES / "conformance.prg32",
                  "audio_check-qemu": FIXTURES / "hardware" / "audio_check-qemu.prg32"}
    for name, cartridge in cartridges.items():
        report = json.loads((evidence / name / "comparison.json").read_text())
        assert hashlib.sha256(cartridge.read_bytes()).hexdigest() == report["cartridge"]["sha256"], name
        with wave.open(str(evidence / name / "firmware.wav")) as source:
            firmware = source.readframes(source.getnframes())
        assert hashlib.sha256(firmware).hexdigest() == report["firmware_pcm_sha256"]
        seconds = report.get("seconds") or round(report["browser_chunks"] / 50)   # what --seconds was
        run = subprocess.run(["node", str(ROOT / "tools" / "audio_capture.mjs"), str(cartridge),
                              str(int(seconds * 30) + 1), str(evidence / name / "browser-check.wav")],
                             capture_output=True, text=True, timeout=300)
        assert run.returncode == 0, run.stderr
        try:
            with wave.open(str(evidence / name / "browser-check.wav")) as source:
                browser = source.readframes(source.getnframes())
        finally:
            (evidence / name / "browser-check.wav").unlink()
        assert hashlib.sha256(browser).hexdigest() == report["browser_pcm_sha256"], name
        again = compare(firmware, browser)
        assert again["identical_sounding_chunks"] == report["identical_sounding_chunks"] > 0
        assert again["segments"] == report["segments"]


PATCHED = ROOT / "docs" / "evidence" / "qemu-audio" / "2026-10-21-patched"
PATCHED_CARTRIDGES = {"conformance": FIXTURES / "conformance.prg32",
                      "audio_check-qemu-phase-a": FIXTURES / "hardware" / "audio_check-qemu.prg32",
                      "audio_check-qemu-phase-b": FIXTURES / "hardware" / "audio_check-qemu.prg32"}
# With docs/upstream/prg32-sdk-audio-clock-and-reset.patch, QEMU keeps audio on the emulated clock:
# whole recordings line up at one fixed shift. Before it, they drifted (2026-10-21: 117/348, 120/540).
ALIGNED_AT_LEAST = {"conformance": 0.75, "audio_check-qemu-phase-a": 0.95, "audio_check-qemu-phase-b": 0.9}


@needs_node
@pytest.mark.parametrize("name", sorted(PATCHED_CARTRIDGES))
def test_patched_qemu_firmware_lines_up_over_the_whole_recording(name, tmp_path):
    """docs/evidence/qemu-audio/2026-10-21-patched: the recordings are intact, this browser core still renders
    the recorded browser side, and at one fixed shift most 20 ms chunks are equal sample for sample."""
    import hashlib
    import sys
    import wave

    sys.path.insert(0, str(ROOT / "tools"))
    from qemu_audio_capture import aligned

    report = json.loads((PATCHED / name / "comparison.json").read_text())
    cartridge = PATCHED_CARTRIDGES[name]
    assert hashlib.sha256(cartridge.read_bytes()).hexdigest() == report["cartridge"]["sha256"]
    patch = ROOT / "docs" / "upstream" / "prg32-sdk-audio-clock-and-reset.patch"
    assert report["firmware"]["patches"][0]["sha256"] == hashlib.sha256(patch.read_bytes()).hexdigest()
    with wave.open(str(PATCHED / name / "firmware.wav")) as source:
        firmware = source.readframes(source.getnframes())
    assert hashlib.sha256(firmware).hexdigest() == report["firmware_pcm_sha256"]
    wav = tmp_path / "browser.wav"
    run = subprocess.run(["node", str(ROOT / "tools" / "audio_capture.mjs"), str(cartridge),
                          str(int(report["seconds"] * 30) + 1), str(wav)], capture_output=True, text=True, timeout=300)
    assert run.returncode == 0, run.stderr
    with wave.open(str(wav)) as source:
        browser = source.readframes(source.getnframes())
    assert hashlib.sha256(browser).hexdigest() == report["browser_pcm_sha256"]
    again = aligned(firmware, browser)
    assert again == report["aligned"]
    assert again["equal_chunks"] / again["compared_chunks"] >= ALIGNED_AT_LEAST[name]


def test_the_whole_console_check_soundtrack_is_equal_in_qemu():
    """Phase A: everything before the first frame-timed effect (the 8-voice chord, hard left, hard right,
    silences: 6.6 s) is equal sample for sample; only the frame-timed effects may land one 20 ms
    buffer away (the console's audio buffers and the cartridge's frames have their own phases)."""
    report = json.loads((PATCHED / "audio_check-qemu-phase-a" / "comparison.json").read_text())
    differing = report["aligned"]["differing_chunks"]
    assert report["aligned"]["shift_chunks"] == 0 and differing and min(differing) >= 329


@pytest.mark.skipif(os.environ.get("PRG32_LIVE_QEMU") != "1",
                    reason="live QEMU firmware run is opt-in: PRG32_LIVE_QEMU=1 (needs ESP-IDF and Espressif QEMU)")
def test_live_qemu_audio_does_not_drift(tmp_path):
    """Builds the PRG32 firmware with the proposed SDK patch, records the console check in QEMU and
    fails if the whole recording no longer lines up (the QEMU audio clock drifting again)."""
    out = tmp_path / "evidence"
    env = {**os.environ, "PRG32_QEMU_EXTRA": "-icount shift=3,sleep=off"}
    # ESP-IDF's own Python (export.sh sets IDF_PYTHON_ENV_PATH): the firmware build runs idf.py with it.
    idf_python = Path(os.environ.get("IDF_PYTHON_ENV_PATH", "")) / "bin" / "python"
    python = str(idf_python) if idf_python.is_file() else sys.executable
    result = subprocess.run([python, str(ROOT / "tools" / "qemu_audio_capture.py"), "--build",
                             "--patch", str(ROOT / "docs" / "upstream" / "prg32-sdk-audio-clock-and-reset.patch"),
                             str(FIXTURES / "hardware" / "audio_check-qemu.prg32"), "--seconds", "11", "--out", str(out)],
                            capture_output=True, text=True, timeout=3600, env=env)
    assert result.returncode == 0, result.stderr[-3000:]
    aligned = json.loads((out / "comparison.json").read_text())["aligned"]
    assert aligned["equal_chunks"] / aligned["compared_chunks"] >= 0.9, aligned
