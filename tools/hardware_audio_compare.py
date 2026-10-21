"""Compare a PRG32 console's line-out recording of the audio check with the browser core (docs/hardware_audio_check.md).

    python3 tools/hardware_audio_compare.py capture.wav --digital [--out report.json]   # I2S capture
    python3 tools/hardware_audio_compare.py recording.wav [--out report.json]           # microphones

The console drives speaker amplifiers (MAX98357A) and has no line-out, so there are two ways
to record it, both stereo WAV files of at least two programmes (about 22 s) of
tests/fixtures/audio/hardware/audio_check-esp32c6.prg32:

- --digital: the I2S data the ESP32-C6 sends to the amplifiers, decoded by a logic analyser
  (sigrok's i2s decoder writes a WAV file). These are the console's own samples, so the
  checks are strict: digital silence, no sample at all on the other channel for a hard-panned
  voice, and single-voice stretches found sample for sample in the browser core's recording.
- otherwise: two microphones, one at each speaker (any sample rate, 16/24/32-bit); only the
  loudness checks apply, with a separation limit a room allows.

The reference is the browser core's recording of the same cartridge (tools/audio_capture.mjs).
Both modes compare loudness envelopes (20 ms windows), per channel, after finding where a
programme starts in the recording:

- shape:      the left and right envelopes follow the reference (correlation >= 0.85);
- chord:      the 8-voice chord sounds on both channels;
- silence:    the silent stretches are quiet (40 dB under the chord) - a buzzer, hum or
              leftover voice would show here;
- separation: the hard-left voice is 20 dB louder on the left, the hard-right one on the right;
- drum:       the recorded-sample sound effect is heard;
- stop:       "stop all sounds" silences the held note at once.

The report (JSON) has each value, its limit and the outcome, the recording's SHA-256
and the reference hashes; the exit code is 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECK = ROOT / "tests" / "fixtures" / "audio" / "hardware"
WINDOW_S = 0.02
LIMITS = {"shape": 0.85, "chord_db": -20.0, "silence_db": -40.0, "separation_db": 20.0, "drum_db": 20.0,
          "stop_db": -40.0}
MICROPHONE_SEPARATION_DB = 6.0      # two microphones in a room hear both speakers
DIGITAL = {"shape": 0.98, "silence_db": -120.0, "separation_db": 120.0}
EXACT_SAMPLES = 4096                # a stretch of one voice that must appear unchanged in the capture


def read_wav(path: Path) -> tuple[int, list[array.array]]:
    """Sample rate and two channels of floats (-1..1); mono is refused (the check is about stereo)."""
    with wave.open(str(path)) as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        if source.getcomptype() != "NONE" or width not in (2, 3, 4):
            raise SystemExit(f"{path}: use an uncompressed 16-, 24- or 32-bit PCM WAV file")
        if channels != 2:
            raise SystemExit(f"{path}: the recording must be stereo (it has {channels} channel(s))")
        data = source.readframes(source.getnframes())
    if width == 3:
        data = b"".join(b"\x00" + data[i:i + 3] for i in range(0, len(data), 3))   # 24-bit -> 32-bit
        width = 4
    values = array.array("h" if width == 2 else "i")
    values.frombytes(data)
    if sys.byteorder == "big":
        values.byteswap()
    scale = float(1 << (8 * width - 1))
    left = array.array("d", (value / scale for value in values[0::2]))
    right = array.array("d", (value / scale for value in values[1::2]))
    return rate, [left, right]


def read_pcm16(path: Path) -> tuple[int, array.array, array.array]:
    """An I2S capture as signed 16-bit samples per channel (32-bit slots holding 16-bit data are shifted)."""
    with wave.open(str(path)) as source:
        channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
        data = source.readframes(source.getnframes())
    if channels != 2 or width not in (2, 4):
        raise SystemExit(f"{path}: an I2S capture must be a stereo 16- or 32-bit WAV file")
    values = array.array("h" if width == 2 else "i")
    values.frombytes(data)
    if sys.byteorder == "big":
        values.byteswap()
    if width == 4:
        if any(value & 0xFFFF for value in values):
            raise SystemExit(f"{path}: 32-bit slots with more than 16 bits of data; PRG32 sends 16-bit samples")
        values = array.array("h", (value >> 16 for value in values))
    return rate, array.array("h", values[0::2]), array.array("h", values[1::2])


def found_exactly(reference: array.array, capture: array.array, start: int) -> bool:
    """Does this stretch of the reference appear, sample for sample, somewhere in the capture?"""
    piece = reference[start:start + EXACT_SAMPLES]
    if len(piece) < EXACT_SAMPLES or not any(piece):
        return False
    needle, haystack = piece.tobytes(), capture.tobytes()
    at = haystack.find(needle)
    while at >= 0 and at % 2:                  # only matches that start on a whole sample count
        at = haystack.find(needle, at + 1)
    return at >= 0


def envelope(rate: int, channel: array.array) -> list[float]:
    """RMS loudness in 20 ms windows."""
    size = max(1, int(rate * WINDOW_S))
    out = []
    for start in range(0, len(channel) - size + 1, size):
        total = 0.0
        for value in channel[start:start + size]:
            total += value * value
        out.append(math.sqrt(total / size))
    return out


def db(ratio: float) -> float:
    return 20 * math.log10(max(ratio, 1e-12))


def correlation(a: list[float], b: list[float]) -> float:
    n = min(len(a), len(b))
    if n < 2:
        return 0.0
    ma, mb = sum(a[:n]) / n, sum(b[:n]) / n
    num = sum((a[i] - ma) * (b[i] - mb) for i in range(n))
    den = math.sqrt(sum((a[i] - ma) ** 2 for i in range(n)) * sum((b[i] - mb) ** 2 for i in range(n)))
    return num / den if den else 0.0


def reference_wav(out: Path) -> Path:
    build = json.loads((CHECK / "BUILD.json").read_text())
    command = ["node", str(ROOT / "tools" / "audio_capture.mjs"), str(CHECK / "audio_check-esp32c6.prg32"),
               str(build["frames"]), str(out)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise SystemExit("the browser core did not run the audio check:\n" + result.stderr)
    if json.loads(result.stdout)["pcm_fnv1a"] != build["reference_pcm_fnv1a"]:
        raise SystemExit("the browser core no longer plays the recorded reference (BUILD.json): rebuild the check")
    return out


def best_start(reference: list[float], recording: list[float]) -> tuple[int, float]:
    """The window where a whole programme in the recording best matches the reference."""
    best, best_score = 0, -2.0
    for start in range(0, max(1, len(recording) - len(reference) + 1)):
        score = correlation(reference, recording[start:start + len(reference)])
        if score > best_score + 1e-6:          # the first of equally good programmes
            best, best_score = start, score
    return best, best_score


def compare(recording: Path, reference: Path | None = None, digital: bool = False) -> dict:
    timeline = json.loads((CHECK / "BUILD.json").read_text())["timeline_seconds"]
    with tempfile.TemporaryDirectory() as tmp:
        reference = reference or reference_wav(Path(tmp) / "reference.wav")
        ref_rate, ref = read_wav(reference)
        rec_rate, rec = read_wav(recording)
        exact = {}
        if digital:
            _rate, ref_left, ref_right = read_pcm16(reference)
            cap_rate, cap_left, cap_right = read_pcm16(recording)
            if cap_rate != 22050:
                return {"outcome": "failed", "reason": f"an I2S capture runs at 22050 Hz, this one at {cap_rate} Hz"}
            timeline_now = json.loads((CHECK / "BUILD.json").read_text())["timeline_seconds"]
            for name, ref_channel, cap_channel in (("left_only", ref_left, cap_left), ("right_only", ref_right, cap_right)):
                start = int((timeline_now[name][0] + 0.2) * 22050)
                exact[name] = found_exactly(ref_channel, cap_channel, start)
    ref_env = [envelope(ref_rate, channel) for channel in ref]
    rec_env = [envelope(rec_rate, channel) for channel in rec]
    if len(rec_env[0]) < len(ref_env[0]):
        return {"outcome": "failed", "reason": "the recording is shorter than one programme of the audio check"}
    mix_ref = [a + b for a, b in zip(*ref_env)]
    mix_rec = [a + b for a, b in zip(*rec_env)]
    start, match = best_start(mix_ref, mix_rec)
    length = len(mix_ref)
    left, right = (channel[start:start + length] for channel in rec_env)

    def level(channel: list[float], name: str, margin: float = 0.0) -> float:
        first, last = timeline[name]
        first, last = int((first + margin) / WINDOW_S), int(last / WINDOW_S)
        part = channel[first:last]
        return math.sqrt(sum(value * value for value in part) / len(part)) if part else 0.0

    chord = max(level(left, "chord"), level(right, "chord"), 1e-9)
    peak = max(max(left), max(right), 1e-9)
    checks = {
        "programme_found": {"value": round(match, 3), "limit": 0.5, "ok": match >= 0.5},
        "shape_left": {"value": round(correlation(ref_env[0], left), 3), "limit": LIMITS["shape"]},
        "shape_right": {"value": round(correlation(ref_env[1], right), 3), "limit": LIMITS["shape"]},
        "chord_left_db": {"value": round(db(level(left, "chord") / peak), 1), "limit": LIMITS["chord_db"]},
        "chord_right_db": {"value": round(db(level(right, "chord") / peak), 1), "limit": LIMITS["chord_db"]},
        "silence_after_chord_db": {"value": round(db(max(level(left, "silence_after_chord"),
                                                         level(right, "silence_after_chord")) / chord), 1),
                                   "limit": LIMITS["silence_db"], "below": True},
        "silence_after_stop_db": {"value": round(db(max(level(left, "silence_after_stop"),
                                                        level(right, "silence_after_stop")) / chord), 1),
                                  "limit": LIMITS["silence_db"], "below": True},
        "separation_left_db": {"value": round(db(level(left, "left_only") / max(level(right, "left_only"), 1e-9)), 1),
                               "limit": LIMITS["separation_db"]},
        "separation_right_db": {"value": round(db(level(right, "right_only") / max(level(left, "right_only"), 1e-9)), 1),
                                "limit": LIMITS["separation_db"]},
        "drum_db": {"value": round(db(max(level(left, "drum"), level(right, "drum"))
                                      / max(level(left, "silence_after_stop"), level(right, "silence_after_stop"), 1e-9)), 1),
                    "limit": LIMITS["drum_db"]},
    }
    stop_at = timeline["long"][1]
    stop_window = (int((stop_at + 0.06) / WINDOW_S), int((stop_at + 0.3) / WINDOW_S))
    after_stop = max(max(left[stop_window[0]:stop_window[1]] or [0]), max(right[stop_window[0]:stop_window[1]] or [0]))
    checks["stop_db"] = {"value": round(db(after_stop / max(level(left, "long"), level(right, "long"), 1e-9)), 1),
                         "limit": LIMITS["stop_db"], "below": True}
    if digital:
        for name in ("shape_left", "shape_right"):
            checks[name]["limit"] = DIGITAL["shape"]
        for name in ("silence_after_chord_db", "silence_after_stop_db"):
            checks[name]["limit"] = DIGITAL["silence_db"]
        for name in ("separation_left_db", "separation_right_db"):
            checks[name]["limit"] = DIGITAL["separation_db"]
        for name, ok in exact.items():
            checks[f"bit_exact_{name}"] = {"value": ok, "limit": True, "ok": ok}
    else:
        for name in ("separation_left_db", "separation_right_db"):
            checks[name]["limit"] = MICROPHONE_SEPARATION_DB
    for check in checks.values():
        if "ok" not in check:
            check["ok"] = check["value"] <= check["limit"] if check.get("below") else check["value"] >= check["limit"]
    clipped = sum(1 for channel in rec for value in channel if abs(value) >= 0.999) / max(1, 2 * len(rec[0]))
    return {"outcome": "passed" if all(check["ok"] for check in checks.values()) else "failed",
            "mode": "digital (I2S capture)" if digital else "microphones",
            "recording": {"file": recording.name, "sha256": hashlib.sha256(recording.read_bytes()).hexdigest(),
                          "sample_rate": rec_rate, "seconds": round(len(rec[0]) / rec_rate, 2),
                          "clipped_fraction": round(clipped, 6),
                          "programme_starts_at_s": round(start * WINDOW_S, 2)},
            "reference": {key: value for key, value in json.loads((CHECK / "BUILD.json").read_text()).items()
                          if key in ("reference_pcm_fnv1a", "sha256", "prg32_sdk", "compiler")},
            "checks": checks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("recording", type=Path)
    parser.add_argument("--reference", type=Path, help="a reference WAV instead of running the browser core")
    parser.add_argument("--digital", action="store_true", help="the recording is the console's I2S data (strict checks)")
    parser.add_argument("--out", type=Path, help="write the report here as well")
    args = parser.parse_args()
    report = compare(args.recording, args.reference, args.digital)
    text = json.dumps(report, indent=1, sort_keys=True)
    print(text)
    if args.out:
        args.out.write_text(text + "\n")
    return 0 if report["outcome"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
