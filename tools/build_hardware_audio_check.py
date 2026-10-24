"""Build the console audio check: an AudioStudio project made into real PRG32 cartridges (docs/hardware_audio_check.md).

    python3 tools/build_hardware_audio_check.py           # write tests/fixtures/audio/hardware/
    python3 tools/build_hardware_audio_check.py --check   # fail if the committed files differ
    python3 tools/build_hardware_audio_check.py --check-if-comparable --out DIR
        # CI (toolchain container): check only when the SDK and compiler match BUILD.json,
        # keep what was built in DIR; without Node.js the reference recording is not re-made

It goes through the kit like a student would: a Blocks project, its AudioStudio
document and a WAV sample through the AudioStudio API, then the package route with the
real PRG32 toolchain. The game repeats a programme of 330 frames (a PRG32 frame is
33 ms, PRG32_FRAME_MS in the firmware, so about 10.9 s); soundtrack times are in
milliseconds, sound-effect times in frames:

    0.00 s  8 voices at once: 8 instruments, pans from hard left to hard right, 8 envelopes
    2.00 s  all notes released; from 2.50 s exact silence
    3.00 s  voice 0 alone, hard left           (until 4.00 s)
    4.25 s  voice 7 alone, hard right          (until 5.25 s)
    6.60 s  the sound effect "Drum" (a recorded sample)          frame 200
    7.59 s  the sound effect "Long" (a held note), cut by ...    frame 230
    8.09 s  "stop all sounds"; silence until the programme repeats  frame 245 .. 330

The browser core's recording of the same cartridge is the reference that
tools/hardware_audio_compare.py compares the console's line-out recording with.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import secrets
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from prg32_construction_kit import audio_studio  # noqa: E402
from prg32_construction_kit.build_check import toolchain_present  # noqa: E402
from prg32_construction_kit.config import Config  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "audio" / "hardware"
TITLE = "Audio Check"
FRAME_MS = 33           # PRG32_FRAME_MS in the firmware (and the browser core's frame)
FRAMES = 330            # one programme
DRUM, LONG, STOP = 200, 230, 245
MASTER_VOLUME = 160     # set by the game, so the console's own volume setting cannot change the check
TIMELINE = {"chord": (0.0, 2.0), "silence_after_chord": (2.45, 2.85), "left_only": (3.05, 3.95),
            "right_only": (4.3, 5.25), "drum": (DRUM * FRAME_MS / 1000, DRUM * FRAME_MS / 1000 + 0.3),
            "long": (LONG * FRAME_MS / 1000, STOP * FRAME_MS / 1000),
            "silence_after_stop": (STOP * FRAME_MS / 1000 + 0.1, FRAMES * FRAME_MS / 1000 - 0.1)}


def drum_wav() -> bytes:
    """A deterministic 0.3 s drum-like sound: a falling tone with a noisy start, 16-bit mono 22050 Hz WAV."""
    import io
    import struct
    import wave

    frames = []
    seed = 12345
    for n in range(6615):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        noise = (seed >> 16) / 32768 - 0.5 if n < 800 else 0
        level = math.exp(-n / 1500)
        frames.append(int(26000 * level * (math.sin(2 * math.pi * (180 - n / 100) * n / 22050) + noise)))
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(22050)
        target.writeframes(b"".join(struct.pack("<h", max(-32768, min(32767, value))) for value in frames))
    return out.getvalue()


def document(drum_id: str) -> dict:
    sounds = ["triangle", "saw", "pulse", "noise", "triangle", "saw", "pulse", "triangle"]
    pans = [-64, -46, -27, -9, 9, 27, 45, 63]
    envelopes = [(0, 40, 200, 60), (10, 60, 160, 40), (30, 20, 220, 80), (0, 90, 60, 30),
                 (60, 0, 255, 100), (20, 100, 120, 50), (5, 10, 230, 20), (0, 30, 180, 70)]
    voices = [audio_studio.instrument(f"Voice {n}", sounds[n], pan=pans[n], volume=150, pulse_width=4 + n,
                                      cutoff=15 - (n % 4), attack=a, decay=d, sustain=s, release=r)
              for n, (a, d, s, r) in enumerate(envelopes)]
    rows = [[None] * 48 for _ in range(8)]
    for voice, note in enumerate([48, 55, 60, 64, 67, 72, 76, 84]):
        rows[voice][0], rows[voice][16] = note, "off"
    rows[0][24], rows[0][32] = 60, "off"
    rows[7][34], rows[7][42] = 72, "off"
    return {"schema": audio_studio.SCHEMA, "voices": voices,
            "effects": [{"name": "Drum", "instrument": audio_studio.instrument("Drum", "sample", sample="Drum", volume=220,
                                                                               attack=0, decay=0, sustain=255, release=20),
                         "note": 60, "duration_ms": 300, "volume": 255, "voice": 6},
                        {"name": "Long", "instrument": audio_studio.instrument("Long", "saw", volume=200, attack=0,
                                                                               decay=0, sustain=255, release=0),
                         "note": 57, "duration_ms": 5000, "volume": 255, "voice": 3}],
            "soundtracks": [{"name": "Check", "tempo": 120, "steps": 48, "loop": False, "rows": rows}],
            "samples": [{"name": "Drum", "artifact_id": drum_id, "base_note": 60, "loop": False,
                         "loop_start": 0, "loop_end": 0}]}


def blocks() -> dict:
    def block(kind, inner=None, **fields):
        item = {"type": kind, "fields": fields}
        if inner:
            item["inputs"] = {"DO": {"block": chain(*inner)}}
        return item

    def chain(*items):
        for here, after in zip(items, items[1:]):
            here["next"] = {"block": after}
        return items[0] if items else None

    def at(frame, *inner):
        return block("prg32_if", list(inner), COND=f"t == {frame}")

    # The master volume is the console's setting (its setup menu) unless the game sets it.
    start = [block("prg32_set_state", VAR="t", VALUE="0"), block("prg32_audio_volume", VOLUME=str(MASTER_VOLUME))]
    update = [at(0, block("prg32_soundtrack_play", TRACK="Check")),
              at(DRUM, block("prg32_sound_effect", EFFECT="Drum")),
              at(LONG, block("prg32_sound_effect", EFFECT="Long")),
              at(STOP, block("prg32_sound_stop_all")),
              block("prg32_change_state", VAR="t", DELTA="1"),
              at(FRAMES, block("prg32_set_state", VAR="t", VALUE="0"))]
    draw = [block("prg32_clear_screen", COLOR="BLACK"),
            block("prg32_draw_text", X="8", Y="8", TEXT="PRG32 AUDIO CHECK", FG="WHITE", BG="BLACK"),
            block("prg32_draw_number", VALUE="t", X="8", Y="24", FG="YELLOW", BG="BLACK")]
    tops = []
    for kind, items in (("prg32_on_start", start), ("prg32_update", update), ("prg32_draw", draw)):
        tops.append({"type": kind, "inputs": {"DO": {"block": chain(*items)}}})
    return {"blocks": {"languageVersion": 0, "blocks": tops}}


def build() -> dict[str, bytes]:
    """Everything the check needs, made through the kit's own API with the real toolchain."""
    from flask.testing import FlaskClient

    from prg32_construction_kit import create_app

    password = secrets.token_urlsafe(16)
    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp)
        app = create_app({"TESTING": True, "DATA_DIR": data, "DB_PATH": data / "kit.sqlite", "BUILD_ROOT": data / "builds",
                          "ARTIFACT_ROOT": data / "artifacts", "ADMIN_PASSWORD": password, "SSO_SECRET": "",
                          "SSO_PEER_URL": ""})
        client: FlaskClient = app.test_client()
        client.environ_base["HTTP_X_PRG32_KIT"] = "1"
        assert client.post("/auth/login", data={"username": "admin", "password": password}).status_code == 302

        def ok(response, status=200):
            if response.status_code != status:
                raise SystemExit(f"{response.request.path}: {response.status_code} {response.get_data(as_text=True)[:2000]}")
            return response

        project = ok(client.post("/api/projects", json={"title": TITLE, "blocks_json": blocks()}), 201).get_json()
        url = f"/api/projects/{project['id']}/audio"
        import io

        sample = ok(client.post(f"{url}/samples", data={"file": (io.BytesIO(drum_wav()), "drum.wav"), "name": "Drum"}),
                    201).get_json()
        doc = document(sample["artifact_id"])
        ok(client.put(url, json={"document": doc, "expected_version": 0}))
        block = ok(client.post(f"{url}/preview", json={})).data
        built = ok(client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["esp32c6", "qemu"]})).get_json()
        if not built.get("cartridge_artifacts"):
            raise SystemExit("the PRG32 toolchain did not build the cartridge:\n" + (built["build"].get("log") or ""))
        out = {"audio_check.aud": block, "audio_studio.json": (json.dumps(
            {**doc, "samples": [{**doc["samples"][0], "artifact_id": "drum"}]}, indent=1, sort_keys=True) + "\n").encode()}
        for artifact in built["cartridge_artifacts"]:
            architecture = artifact["metadata"]["architecture"]
            out[f"audio_check-{architecture}.prg32"] = ok(client.get(f"/api/artifacts/{artifact['id']}/download")).data
        source = ok(client.post(f"/api/projects/{project['id']}/convert", json={})).get_json()["c_source"]
        out["audio_check.c"] = source.encode()
        return out


def reference(cartridge: Path, wav: Path | None = None) -> dict:
    """The browser core's recording of the cartridge: one programme, as tools/audio_capture.mjs prints it."""
    command = ["node", str(ROOT / "tools" / "audio_capture.mjs"), str(cartridge), str(FRAMES), *([str(wav)] if wav else [])]
    result = subprocess.run(command, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise SystemExit("the browser core did not run the cartridge:\n" + result.stderr)
    return json.loads(result.stdout)


def record(files: dict[str, bytes]) -> dict:
    import shutil

    from build_audio_fixtures import inputs

    if shutil.which("node"):
        with tempfile.TemporaryDirectory() as tmp:
            cartridge = Path(tmp) / "c.prg32"
            cartridge.write_bytes(files["audio_check-esp32c6.prg32"])
            run = reference(cartridge)
        heard = {"reference_pcm_fnv1a": run["pcm_fnv1a"], "reference_samples": run["samples"],
                 "buzzer_calls": run.get("buzzer_calls", 0)}
    else:       # no browser core here: keep the committed recording's numbers, and say so
        print("Node.js is not installed: the reference recording is not made again", file=sys.stderr)
        committed = json.loads((OUT / "BUILD.json").read_text())
        heard = {key: committed[key] for key in ("reference_pcm_fnv1a", "reference_samples", "buzzer_calls")}
    return {**inputs(), "frames": FRAMES, "timeline_seconds": TIMELINE,
            "sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}, **heard}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--check-if-comparable", action="store_true",
                        help="like --check, but only when the SDK and compiler match BUILD.json")
    parser.add_argument("--out", type=Path, help="also write what was built here (CI evidence)")
    args = parser.parse_args()
    if not toolchain_present(Config.PRG32_BUILD_COMMAND):
        print("the PRG32 toolchain is not installed", file=sys.stderr)
        return 2
    if args.check_if_comparable:
        from build_audio_fixtures import inputs

        recorded = json.loads((OUT / "BUILD.json").read_text())
        here = inputs()
        if {key: recorded.get(key) for key in here} != here:
            print(f"not comparable: built with {recorded.get('prg32_sdk')} / {recorded.get('compiler')}; this machine has {here}")
            if not args.out:
                return 0
        else:
            args.check = True
    files = build()
    files["BUILD.json"] = (json.dumps(record(files), indent=1, sort_keys=True) + "\n").encode()
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (args.out / name).write_bytes(data)
    if args.check_if_comparable and not args.check:
        print("built for the record only (inputs differ from BUILD.json); nothing compared")
        return 0
    stale = [name for name, data in files.items() if not (OUT / name).is_file() or (OUT / name).read_bytes() != data]
    if args.check:
        if stale:
            print("out of date: " + ", ".join(stale) + " (run python3 tools/build_hardware_audio_check.py)",
                  file=sys.stderr)
            return 1
        print("hardware audio check files are up to date")
        return 0
    OUT.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (OUT / name).write_bytes(data)
        print(f"Wrote {(OUT / name).relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
