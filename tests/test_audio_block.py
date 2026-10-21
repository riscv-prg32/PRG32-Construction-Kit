"""The kit's audio-block packer (prg32_construction_kit/audio_block.py).

- It writes byte for byte what the PRG32 SDK's tools/prg32audio_pack.py writes.
- Reading a block back gives the same content; damaged blocks are refused, never read past.
- Content the firmware would refuse, or that could loop for ever, is refused with a message.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from prg32_construction_kit import audio_block
from prg32_construction_kit.audio_block import AudioBlockError, pack, read, synth_id, validate

ROOT = Path(__file__).resolve().parent.parent
SDK = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32")
PACKER = SDK / "tools" / "prg32audio_pack.py"


def spec() -> dict:
    return {
        "samples": [{"pcm": bytes(range(0, 256, 4)), "base_note": 57, "loop": True, "loop_start": 8, "loop_end": 60},
                    {"pcm": b"\x80\xff\x00" * 7, "base_note": 60}],
        "instruments": [{"sample_id": synth_id(1, cutoff=10, resonance=2), "default_volume": 200, "default_pan": -64,
                         "attack": 12, "decay": 40, "sustain": 140, "release": 90},
                        {"sample_id": 0, "default_volume": 255, "default_pan": 63},
                        {"sample_id": synth_id(3), "attack": 0, "release": 255}],
        "tracks": [{"events": [{"delta": 0, "command": "NOTE_ON", "arg0": 0, "arg1": 60},
                               {"delta": 0, "command": "NOTE_ON", "arg0": 1, "arg1": 64},
                               {"delta": 4, "command": "SET_PAN", "arg0": 1, "arg1": 200},
                               {"delta": 4, "command": "NOTE_OFF", "arg0": 0},
                               {"delta": 2, "command": "JUMP", "arg0": 0, "arg1": 0}]},
                   {"events": [{"delta": 0, "command": "PLAY_SAMPLE", "arg0": 1, "arg1": 180},
                               {"delta": 8, "command": "END"}]}],
    }


def test_the_kit_writes_what_the_sdk_writes(tmp_path):
    if not PACKER.is_file():
        if os.environ.get("PRG32_REQUIRE_SDK") == "1":
            pytest.fail(f"no PRG32 SDK at {SDK}", pytrace=False)
        pytest.skip("no PRG32 SDK checkout")
    content = spec()
    config = {"samples": [], "instruments": content["instruments"], "tracks": content["tracks"]}
    for index, sample in enumerate(content["samples"]):
        (tmp_path / f"s{index}.raw").write_bytes(sample["pcm"])
        entry = {key: value for key, value in sample.items() if key != "pcm"}
        if not entry.get("loop"):
            entry.pop("loop_start", None), entry.pop("loop_end", None)
        config["samples"].append({**entry, "file": f"s{index}.raw"})
    (tmp_path / "audio.json").write_text(json.dumps(config))
    subprocess.run([sys.executable, str(PACKER), str(tmp_path / "audio.json"), "--out", str(tmp_path / "sdk.aud")],
                   check=True, capture_output=True)
    assert pack(content) == (tmp_path / "sdk.aud").read_bytes()


def test_a_block_reads_back_as_written():
    block = pack(spec())
    again = read(block)
    assert pack(again) == block
    assert again["instruments"][0]["default_pan"] == -64 and again["tracks"][0]["events"][2]["arg1"] == 200


def test_identical_content_gives_identical_bytes():
    assert pack(spec()) == pack(json.loads(json.dumps(spec(), default=lambda b: list(b)),
                                           object_hook=lambda d: {**d, "pcm": bytes(d["pcm"])} if "pcm" in d else d))


@pytest.mark.parametrize("change, message", [
    (lambda s: s["samples"].append({"pcm": b"\x80" * (audio_block.MAX_SAMPLE_BYTES + 1)}), "bytes of 8-bit sound"),
    (lambda s: s["samples"][0].update(loop_start=50, loop_end=20), "must end after it starts"),
    (lambda s: s["samples"][0].update(loop_end=999), "loop end"),
    (lambda s: s["instruments"].append({"sample_id": 9}), "not in the block"),
    (lambda s: s["instruments"][0].update(attack=256), "attack must be"),
    (lambda s: s["instruments"][0].update(default_pan=100), "pan must be"),
    (lambda s: s["tracks"][0]["events"].append({"command": "WAIT"}), "unknown command"),
    (lambda s: s["tracks"][0]["events"].append({"command": "NOTE_ON", "arg0": 8, "arg1": 60}), "does not exist"),
    (lambda s: s["tracks"][0]["events"].append({"command": "NOTE_ON", "arg0": 6, "arg1": 60}), "not in the block"),
    (lambda s: s["tracks"][0]["events"].append({"command": "JUMP", "arg0": 50}), "past the end"),
    (lambda s: s["tracks"].append({"events": [{"delta": 0, "command": "NOTE_OFF"},
                                              {"delta": 0, "command": "JUMP", "arg0": 0}]}), "without any wait"),
    (lambda s: s["tracks"].append({"events": []}), "at least one event"),
    (lambda s: s.update(instruments=[{"sample_id": 0}] * 33), "at most 32"),
    (lambda s: s.update(tracks=[{"events": [{"command": "END"}] * 2000}] * 9), "16384 events"),
])
def test_bad_content_is_refused_with_a_message(change, message):
    content = spec()
    change(content)
    with pytest.raises(AudioBlockError, match=message):
        pack(content)


def test_damaged_blocks_are_refused_never_read_past():
    block = pack(spec())
    rng = random.Random("prg32-audio-block")
    refused = 0
    for _ in range(400):
        damaged = bytearray(block)
        for _ in range(rng.randint(1, 6)):
            damaged[rng.randrange(len(damaged))] = rng.randrange(256)
        try:
            content = read(bytes(damaged))
        except AudioBlockError:
            refused += 1
            continue
        for sample in content["samples"]:
            assert len(sample["pcm"]) <= len(block)
    assert refused > 0
    assert pytest.raises(AudioBlockError, read, block[:-4])
    assert pytest.raises(AudioBlockError, read, b"RIFF" + block[4:])


def test_validate_fills_in_the_defaults():
    clean = validate({"instruments": [{"sample_id": synth_id(0)}]})
    assert clean["instruments"][0] == {"sample_id": synth_id(0), "default_volume": 255, "default_pan": 0,
                                       "attack": 0, "decay": 0, "sustain": 255, "release": 0}
