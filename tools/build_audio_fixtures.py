"""Build the audio conformance fixtures (ADR-0021) with the real PRG32 toolchain.

    python3 tools/build_audio_fixtures.py           # write tests/fixtures/audio/*.prg32, *.aud and BUILD.json
    python3 tools/build_audio_fixtures.py --check   # fail if the committed files differ

- conformance.prg32: tests/fixtures/audio/conformance.c with the audio block below:
  instruments 0..7 (one per voice, as the tracker plays instrument N on voice N), each
  a different SID-like sound and ADSR envelope; instrument 8 a plain square for the
  clipping test; one sample; one soundtrack. tests/test_audio_conformance.py runs it.
- legacy_buzzer.prg32: an old cartridge calling the obsolete buzzer, built with the SDK
  directly (the kit refuses to build it), for the "old cartridges stay silent" test.

The cartridges are committed, so the audio tests run without a RISC-V toolchain; with
one, --check proves they are what the toolchain makes from these sources.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from prg32_construction_kit import audio_block  # noqa: E402
from prg32_construction_kit.audio_block import synth_id  # noqa: E402
from prg32_construction_kit.build_check import toolchain_present  # noqa: E402
from prg32_construction_kit.config import Config  # noqa: E402
from prg32_construction_kit.packager import run_prg32_build  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "audio"
RECORD = FIXTURES / "BUILD.json"
TRIANGLE, SAW, PULSE, NOISE = 0, 1, 2, 3


def sample_tone() -> bytes:
    """Half a second of a fading 441 Hz tone, unsigned 8-bit at 22050 Hz (deterministic)."""
    out = bytearray()
    for n in range(11025):
        level = 1.0 - n / 11025
        out.append(128 + int(round(110 * level * math.sin(2 * math.pi * 441 * n / 22050))))
    return bytes(out)


def conformance_block() -> dict:
    def instrument(sound, attack, decay, sustain, release, volume=255, pan=0):
        return {"sample_id": sound, "default_volume": volume, "default_pan": pan, "attack": attack, "decay": decay,
                "sustain": sustain, "release": release}

    instruments = [
        instrument(synth_id(TRIANGLE, cutoff=15), 20, 60, 160, 80),
        instrument(synth_id(SAW, cutoff=10, resonance=1), 0, 40, 200, 40),
        instrument(synth_id(PULSE, pulse_width=3, cutoff=12), 60, 30, 120, 120),
        instrument(synth_id(NOISE, cutoff=8, resonance=2), 5, 90, 60, 30),
        instrument(synth_id(TRIANGLE, cutoff=6, resonance=3), 100, 0, 255, 200),
        instrument(synth_id(SAW, cutoff=15), 30, 120, 80, 60),
        instrument(synth_id(PULSE, pulse_width=12, cutoff=9, resonance=1), 10, 10, 230, 10),
        instrument(synth_id(PULSE, pulse_width=8, cutoff=15), 0, 0, 255, 50),
        instrument(synth_id(PULSE, pulse_width=8, cutoff=15), 0, 0, 255, 0),
    ]

    def ev(delta, command, arg0=0, arg1=0):
        return {"delta": delta, "command": command, "arg0": arg0, "arg1": arg1}

    track = [ev(0, "SET_TEMPO", 150), ev(0, "NOTE_ON", 0, 60), ev(0, "NOTE_ON", 1, 64), ev(0, "NOTE_ON", 2, 67),
             ev(0, "SET_PAN", 1, 0xC0), ev(4, "NOTE_ON", 4, 72), ev(4, "NOTE_OFF", 0), ev(0, "NOTE_ON", 5, 74),
             ev(4, "SET_VOLUME", 4, 100), ev(0, "NOTE_ON", 6, 76), ev(4, "NOTE_ON", 7, 79),
             ev(4, "NOTE_OFF", 1), ev(0, "NOTE_OFF", 2), ev(0, "NOTE_OFF", 4), ev(0, "NOTE_OFF", 5),
             ev(0, "NOTE_OFF", 6), ev(0, "NOTE_OFF", 7), ev(2, "END")]
    return {"samples": [{"pcm": sample_tone(), "base_note": 69}], "instruments": instruments,
            "tracks": [{"events": track}]}


# name -> (source, entry prefix, audio block spec or None)
JOBS = {"conformance": ("conformance.c", "aconf", conformance_block),
        "legacy_buzzer": ("legacy_buzzer.c", "legacy", None)}


def inputs() -> dict[str, str]:
    from build_debug_fixtures import inputs as toolchain_inputs

    return toolchain_inputs()


def build(name: str, work: Path) -> dict[str, bytes]:
    source, prefix, block_spec = JOBS[name]
    work.mkdir(parents=True)
    copy = work / "game.c"
    shutil.copyfile(FIXTURES / source, copy)
    extra = []
    out = {}
    if block_spec:
        block = audio_block.pack(block_spec())
        (work / "audio.aud").write_bytes(block)
        extra = ["--audio-block", str(work / "audio.aud")]
        out[f"{name}.aud"] = block
    cartridge = work / f"{name}.prg32"
    ok, log = run_prg32_build(Config.PRG32_BUILD_COMMAND, copy, cartridge, prefix, name, "qemu", 64, [], 120, None,
                              extra)
    if not ok:
        raise SystemExit(f"{source} did not build:\n{log}")
    out[f"{name}.prg32"] = cartridge.read_bytes()
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if not toolchain_present(Config.PRG32_BUILD_COMMAND):
        print("the PRG32 toolchain is not installed", file=sys.stderr)
        return 2
    sys.path.insert(0, str(ROOT / "tools"))
    stale = []
    with tempfile.TemporaryDirectory() as tmp:
        for name in JOBS:
            for filename, data in build(name, Path(tmp) / name).items():
                path = FIXTURES / filename
                if args.check:
                    if not path.is_file() or path.read_bytes() != data:
                        stale.append(filename)
                else:
                    path.write_bytes(data)
                    print(f"Wrote {path.relative_to(ROOT)}")
    record = json.dumps(inputs(), indent=1, sort_keys=True) + "\n"
    if args.check:
        if not RECORD.is_file() or RECORD.read_text() != record:
            stale.append(RECORD.name)
        if stale:
            print("out of date: " + ", ".join(stale) + " (run python3 tools/build_audio_fixtures.py)", file=sys.stderr)
            return 1
        print("audio fixtures are up to date")
        return 0
    RECORD.write_text(record)
    print(f"Wrote {RECORD.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
