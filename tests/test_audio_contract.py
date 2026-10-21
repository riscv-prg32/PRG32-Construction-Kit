"""The audio contract (contracts/prg32-audio-contract-1.json) against the PRG32 SDK sources.

Every number the kit relies on is read again from a PRG32 checkout (next to the kit, or
PRG32_SOURCE): voice count, sample rate, block limits, ADSR timing, synth tables, pan
gains, tracker timing and ABI indices. PRG32_REQUIRE_SDK=1 turns a missing checkout into
a failure instead of a skip.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = json.loads((ROOT / "contracts" / "prg32-audio-contract-1.json").read_text())
SDK = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32")
AUDIO = SDK / "components" / "prg32_audio"


@pytest.fixture(scope="module")
def sdk():
    if not (AUDIO / "audio_synth.c").is_file():
        if os.environ.get("PRG32_REQUIRE_SDK") == "1":
            pytest.fail(f"PRG32_REQUIRE_SDK=1 but there is no PRG32 checkout at {SDK}", pytrace=False)
        pytest.skip("no PRG32 checkout (set PRG32_SOURCE)")
    return {name: (AUDIO / name).read_text() for name in
            ("audio_config.h", "Kconfig", "audio.c", "audio_mixer.c", "audio_synth.c", "audio_tracker.c",
             "include/prg32_audio.h")} | {
        "abi": (SDK / "components" / "prg32" / "include" / "prg32_abi_index.h").read_text(),
        "pack": (SDK / "tools" / "prg32audio_pack.py").read_text()}


def define(text: str, name: str) -> str:
    return re.search(rf"#define {name}\s+(\S+)", text).group(1)


def table(text: str, name: str) -> list[int]:
    body = re.search(rf"{name}\[\d+\]\s*=\s*\{{([^}}]*)\}}", text, re.S).group(1)
    return [int(value) for value in re.findall(r"\d+", body)]


def test_eight_voices_and_the_upstream_fallback(sdk):
    kconfig = re.search(r"config PRG32_AUDIO_MAX_VOICES.*?default (\d+).*?range \d+ (\d+)", sdk["Kconfig"], re.S)
    assert int(kconfig.group(1)) == CONTRACT["voices"]["kconfig_default"] == 8 and int(kconfig.group(2)) == 8
    for profile in ("sdkconfig.defaults", "sdkconfig.defaults.qemu"):
        assert "CONFIG_PRG32_AUDIO_MAX_VOICES=8" in (SDK / "profiles" / profile).read_text()
    # The no-sdkconfig fallback is recorded as it is; the kit never uses it (wasm/audio/sdkconfig.h).
    assert int(define(sdk["audio_config.h"], "CONFIG_PRG32_AUDIO_MAX_VOICES")) == CONTRACT["voices"]["audio_config_h_fallback"]
    assert CONTRACT["voices"]["count"] == 8


def test_output_volume_and_pan(sdk):
    assert int(define(sdk["audio_config.h"], "CONFIG_PRG32_AUDIO_SAMPLE_RATE")) == CONTRACT["output"]["sample_rate_hz"]
    assert int(re.search(r"g_default_master_volume = (\d+)", sdk["audio.c"]).group(1)) == CONTRACT["volume"]["default_master"]
    header = sdk["include/prg32_audio.h"]
    assert int(define(header, "PRG32_AUDIO_PAN_LEFT").strip("()")) == CONTRACT["pan"]["left"]
    assert int(define(header, "PRG32_AUDIO_PAN_RIGHT")) == CONTRACT["pan"]["right"]
    assert ">> 9" in sdk["audio_mixer.c"] and "clamp16(left)" in sdk["audio_mixer.c"]


def test_adsr_synth_and_sample_tables(sdk):
    synth = sdk["audio_synth.c"]
    assert "1u + ((uint32_t)value * value * 2000u) / 65025u" in synth
    assert "(uint32_t)instrument->sustain * 257u" in synth
    assert int(define(synth, "SYNTH_ENV_MAX").rstrip("u")) == CONTRACT["adsr"]["envelope_max"]
    assert table(synth, "cutoff_q15") == CONTRACT["synth"]["filter_cutoff_q15"]
    assert table(synth, "damping_q15") == CONTRACT["synth"]["filter_damping_q15"]
    assert table(synth, "midi0_semitones_q16") == CONTRACT["synth"]["midi0_semitones_q16"]
    assert int(define(synth, "SYNTH_LFSR_SEED").rstrip("u"), 16) == CONTRACT["synth"]["noise"]["lfsr_seed"]
    assert table(sdk["audio_mixer.c"], "ratio_q10") == CONTRACT["samples"]["note_ratio_q10"]
    header = sdk["include/prg32_audio.h"]
    for name, value in CONTRACT["synth"]["waveforms"].items():
        assert int(define(header, f"PRG32_AUDIO_SYNTH_WAVE_{name.upper()}").rstrip("u")) == value


def test_tracker_and_block_limits(sdk):
    tracker = sdk["audio_tracker.c"]
    assert "60000u / ((uint32_t)bpm * 4u)" in tracker
    assert int(define(tracker, "PRG32_AUDIO_TRACKER_MAX_EVENTS_PER_STEP").rstrip("u")) == CONTRACT["tracker"]["max_events_per_step"]
    assert "prg32_audio_note_on(channel, channel," in tracker     # instrument N on voice N
    config = sdk["audio_config.h"]
    for key, name in (("max_samples", "PRG32_AUDIO_MAX_SAMPLES"), ("max_instruments", "PRG32_AUDIO_MAX_INSTRUMENTS"),
                      ("max_tracks", "PRG32_AUDIO_MAX_TRACKS")):
        assert int(define(config, name)) == CONTRACT["block"][key]
    pack = sdk["pack"]
    assert '"<4sHHHHHHIIIIII"' in pack and '"<IIIIHBB"' in pack and '"<BBBB"' in pack
    for name, code in CONTRACT["tracker"]["commands"].items():
        assert f'"{name}": {code}' in pack


def test_abi_indices(sdk):
    abi = sdk["abi"]
    for group in (CONTRACT["abi"]["portable_table_indices"], CONTRACT["legacy_buzzer"]["portable_table_indices"]):
        for name, index in group.items():
            assert re.search(rf"PRG32_ABI_FN_{name.upper()} = {index},", abi), name
