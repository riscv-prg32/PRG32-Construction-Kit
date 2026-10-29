"""AudioStudio documents: a project's instruments, sound effects and soundtracks (docs/audio_studio.md).

One document per project, kept as the project's asset of kind "audio_studio", in a format
a student can read:

    {"schema": "prg32-kit-audio-1",
     "voices": [8 instruments: voice N plays instrument N in a soundtrack],
     "effects": [{"name": "Jump", "instrument": {...}, "note": 72, "duration_ms": 200,
                  "volume": 255, "voice": 7}, ...],
     "soundtracks": [{"name": "Theme", "tempo": 120, "steps": 16, "loop": false,
                      "rows": [8 rows of steps: null (nothing), a note 0..127, or "off"]}],
     "samples": [{"name": "Drum", "artifact_id": "...", "base_note": 60, "loop": false,
                  "loop_start": 0, "loop_end": 0}]}

    instrument: {"name": "Bass", "sound": "triangle" | "saw" | "pulse" | "noise" | "sample",
                 "sample": "Drum" (for "sample"), "pulse_width": 0..15, "cutoff": 0..15,
                 "resonance": 0..3, "volume": 0..255, "pan": -64..63,
                 "attack": 0..255, "decay": 0..255, "sustain": 0..255, "release": 0..255}

compile_document turns it into the PRG32 audio block (audio_block.py): instruments 0..7 are
the voices, 8.. the effects (effect k is instrument 8 + k); soundtrack k is track k. The
same document and samples always give the same bytes.
"""

from __future__ import annotations

import copy
import io
import re
import struct
import wave
from typing import Any

from . import audio_block
from .messages import text as say

SCHEMA = "prg32-kit-audio-1"
EXPORT_SCHEMA = "prg32-kit-audio-export-1"
SOUNDS = ("triangle", "saw", "pulse", "noise", "sample")
WAVEFORM = {"triangle": 0, "saw": 1, "pulse": 2, "noise": 3}
VOICES = 8
MAX_EFFECTS = audio_block.MAX_INSTRUMENTS - VOICES      # instruments 8..31
MAX_SOUNDTRACKS = audio_block.MAX_TRACKS
MAX_SAMPLES = 32
MAX_STEPS = 128
FIRST_EFFECT_INSTRUMENT = VOICES
NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _.\-]{0,31}$")
MAX_DOCUMENT_BYTES = 256 * 1024


class AudioStudioError(ValueError):
    """Something in an AudioStudio document a student must fix; the message says what."""


def instrument(name: str = "Voice", sound: str = "triangle", **values: Any) -> dict[str, Any]:
    base = {"name": name, "sound": sound, "pulse_width": 8, "cutoff": 15, "resonance": 0, "volume": 200, "pan": 0,
            "attack": 10, "decay": 40, "sustain": 180, "release": 60}
    return {**base, **values}


def default_document() -> dict[str, Any]:
    sounds = ("triangle", "saw", "pulse", "triangle", "saw", "pulse", "noise", "triangle")
    return {"schema": SCHEMA,
            "voices": [instrument(f"Voice {number}", sound) for number, sound in enumerate(sounds)],
            "effects": [], "soundtracks": [], "samples": []}


def _int(value: Any, where: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise AudioStudioError(say("audio", "{where} must be a whole number from {low} to {high}", where=where, low=low, high=high))
    return value


def _name(value: Any, where: str) -> str:
    if not isinstance(value, str) or not NAME.match(value):
        raise AudioStudioError(say("audio", "{where} needs a name of 1 to 32 letters, digits, spaces, '.', '_' or '-'", where=where))
    return value


def _instrument(value: Any, where: str, sample_names: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AudioStudioError(say("audio", "{where} must be an instrument", where=where))
    sound = value.get("sound", "triangle")
    if sound not in SOUNDS:
        raise AudioStudioError(say("audio", "{where}: the sound must be one of {value}", where=where, value=', '.join(SOUNDS)))
    clean = {"name": _name(value.get("name", "Instrument"), where), "sound": sound,
             "pulse_width": _int(value.get("pulse_width", 8), f"{where} pulse width", 0, 15),
             "cutoff": _int(value.get("cutoff", 15), f"{where} cutoff", 0, 15),
             "resonance": _int(value.get("resonance", 0), f"{where} resonance", 0, 3),
             "volume": _int(value.get("volume", 200), f"{where} volume", 0, 255),
             "pan": _int(value.get("pan", 0), f"{where} pan", -64, 63),
             **{key: _int(value.get(key, 180 if key == "sustain" else 0), f"{where} {key}", 0, 255)
                for key in ("attack", "decay", "sustain", "release")}}
    if sound == "sample":
        sample = value.get("sample")
        if sample not in sample_names:
            raise AudioStudioError(say("audio", "{where} plays the sample {sample}, which is not in this project", where=where, sample=repr(sample)))
        clean["sample"] = sample
    return clean


def validate_document(document: Any) -> dict[str, Any]:
    """A clean copy of the document, or AudioStudioError with a student-readable message."""
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise AudioStudioError(say("audio", "not an AudioStudio document ({schema})", schema=SCHEMA))
    samples, voices = document.get("samples", []), document.get("voices")
    effects, soundtracks = document.get("effects", []), document.get("soundtracks", [])
    if not isinstance(samples, list) or len(samples) > MAX_SAMPLES:
        raise AudioStudioError(say("audio", "a project can have at most {max_samples} samples", max_samples=MAX_SAMPLES))
    clean: dict[str, Any] = {"schema": SCHEMA, "voices": [], "effects": [], "soundtracks": [], "samples": []}
    names: set[str] = set()
    for index, sample in enumerate(samples):
        where = f"sample {index + 1}"
        if not isinstance(sample, dict):
            raise AudioStudioError(say("audio", "{where} must be an object", where=where))
        name = _name(sample.get("name"), where)
        if name in names:
            raise AudioStudioError(say("audio", "two samples are called {name}", name=repr(name)))
        names.add(name)
        artifact_id = sample.get("artifact_id")
        if not isinstance(artifact_id, str) or not re.fullmatch(r"[A-Za-z0-9_\-]{1,64}", artifact_id):
            raise AudioStudioError(say("audio", "{where} has no saved sound", where=where))
        clean["samples"].append({"name": name, "artifact_id": artifact_id,
                                 "base_note": _int(sample.get("base_note", 60), f"{where} base note", 0, 127),
                                 "loop": bool(sample.get("loop", False)),
                                 "loop_start": _int(sample.get("loop_start", 0), f"{where} loop start", 0,
                                                    audio_block.MAX_SAMPLE_BYTES),
                                 "loop_end": _int(sample.get("loop_end", 0), f"{where} loop end", 0,
                                                  audio_block.MAX_SAMPLE_BYTES)})
    if not isinstance(voices, list) or len(voices) != VOICES:
        raise AudioStudioError(say("audio", "an AudioStudio document has exactly 8 voices"))
    clean["voices"] = [_instrument(item, f"voice {number}", names) for number, item in enumerate(voices)]
    if not isinstance(effects, list) or len(effects) > MAX_EFFECTS:
        raise AudioStudioError(say("audio", "a project can have at most {max_effects} sound effects", max_effects=MAX_EFFECTS))
    effect_names: set[str] = set()
    for index, effect in enumerate(effects):
        where = f"sound effect {index + 1}"
        if not isinstance(effect, dict):
            raise AudioStudioError(say("audio", "{where} must be an object", where=where))
        name = _name(effect.get("name"), where)
        if name in effect_names:
            raise AudioStudioError(say("audio", "two sound effects are called {name}", name=repr(name)))
        effect_names.add(name)
        clean["effects"].append({"name": name, "instrument": _instrument(effect.get("instrument"), f"{where}", names),
                                 "note": _int(effect.get("note", 72), f"{where} note", 0, 127),
                                 "duration_ms": _int(effect.get("duration_ms", 200), f"{where} length", 1, 10000),
                                 "volume": _int(effect.get("volume", 255), f"{where} volume", 0, 255),
                                 "voice": _int(effect.get("voice", 7), f"{where} voice", 0, VOICES - 1)})
    if not isinstance(soundtracks, list) or len(soundtracks) > MAX_SOUNDTRACKS:
        raise AudioStudioError(say("audio", "a project can have at most {max_soundtracks} soundtracks", max_soundtracks=MAX_SOUNDTRACKS))
    track_names: set[str] = set()
    for index, track in enumerate(soundtracks):
        where = f"soundtrack {index + 1}"
        if not isinstance(track, dict):
            raise AudioStudioError(say("audio", "{where} must be an object", where=where))
        name = _name(track.get("name"), where)
        if name in track_names:
            raise AudioStudioError(say("audio", "two soundtracks are called {name}", name=repr(name)))
        track_names.add(name)
        steps = _int(track.get("steps", 16), f"{where} steps", 1, MAX_STEPS)
        rows = track.get("rows")
        if not isinstance(rows, list) or len(rows) != VOICES:
            raise AudioStudioError(say("audio", "{where} needs one row per voice (8)", where=where))
        clean_rows = []
        for voice, row in enumerate(rows):
            if not isinstance(row, list) or len(row) != steps:
                raise AudioStudioError(say("audio", "{where}, voice {voice}: the row must have {steps} steps", where=where, voice=voice, steps=steps))
            clean_row = []
            for step, cell in enumerate(row):
                if cell is None or cell == "off":
                    clean_row.append(cell)
                else:
                    clean_row.append(_int(cell, f"{where}, voice {voice}, step {step + 1}", 0, 127))
            clean_rows.append(clean_row)
        clean["soundtracks"].append({"name": name, "tempo": _int(track.get("tempo", 120), f"{where} tempo", 30, 255),
                                     "steps": steps, "loop": bool(track.get("loop", False)), "rows": clean_rows})
    return clean


def effect_index(document: dict[str, Any], name: str) -> int | None:
    return next((index for index, effect in enumerate(document.get("effects", [])) if effect["name"] == name), None)


def soundtrack_index(document: dict[str, Any], name: str) -> int | None:
    return next((index for index, track in enumerate(document.get("soundtracks", [])) if track["name"] == name), None)


def _sound_id(item: dict[str, Any], sample_index: dict[str, int]) -> int:
    if item["sound"] == "sample":
        return sample_index[item["sample"]]
    return audio_block.synth_id(WAVEFORM[item["sound"]], item["pulse_width"], item["cutoff"], item["resonance"])


def _block_instrument(item: dict[str, Any], sample_index: dict[str, int]) -> dict[str, Any]:
    return {"sample_id": _sound_id(item, sample_index), "default_volume": item["volume"], "default_pan": item["pan"],
            "attack": item["attack"], "decay": item["decay"], "sustain": item["sustain"], "release": item["release"]}


def _track_events(track: dict[str, Any], muted: set[int]) -> list[dict[str, Any]]:
    """A soundtrack's grid as tracker events: a note plays until the next note or "off" in its row.

    The PRG32 tracker runs an event and then waits its delta (in steps) before the next one
    (audio_tracker.c; contract "tracker.delta"), so each event's delta is the number of steps
    until the event after it, and SET_TEMPO's delta is the wait before the first note. A muted
    voice's row is left out (AudioStudio's preview). A looping soundtrack jumps back to SET_TEMPO
    after its last step; otherwise the notes still playing are released and the track ends.
    """
    timed: list[tuple[int, dict[str, Any]]] = [(0, {"command": "SET_TEMPO", "arg0": track["tempo"], "arg1": 0})]
    sounding: set[int] = set()
    for step in range(track["steps"]):
        for voice in range(VOICES):
            cell = track["rows"][voice][step]
            if cell is None or voice in muted:
                continue
            if cell == "off":
                if voice in sounding:
                    timed.append((step, {"command": "NOTE_OFF", "arg0": voice, "arg1": 0}))
                    sounding.discard(voice)
            else:
                timed.append((step, {"command": "NOTE_ON", "arg0": voice, "arg1": cell}))
                sounding.add(voice)
    end = track["steps"]
    if track["loop"] and len(timed) > 1:
        timed.append((end, {"command": "JUMP", "arg0": 0, "arg1": 0}))      # back to SET_TEMPO
    else:
        timed += [(end, {"command": "NOTE_OFF", "arg0": voice, "arg1": 0}) for voice in sorted(sounding)]
        timed.append((end, {"command": "END", "arg0": 0, "arg1": 0}))
    events = []
    for index, (step, event) in enumerate(timed):
        following = timed[index + 1][0] if index + 1 < len(timed) else step
        events.append({"delta": following - step, **event})
    return events


def compile_document(document: dict[str, Any], samples: dict[str, bytes], muted: set[int] | None = None) -> dict:
    """The audio block spec for a (validated) document; ``samples`` maps artifact id -> 8-bit sound."""
    document = validate_document(document)
    sample_index = {sample["name"]: index for index, sample in enumerate(document["samples"])}
    spec: dict[str, Any] = {"samples": [], "instruments": [], "tracks": []}
    for sample in document["samples"]:
        pcm = samples.get(sample["artifact_id"])
        if pcm is None:
            raise AudioStudioError(say("audio", "the sound of the sample {sample} is missing", sample=repr(sample['name'])))
        spec["samples"].append({"pcm": pcm, "base_note": sample["base_note"], "loop": sample["loop"],
                                "loop_start": sample["loop_start"],
                                "loop_end": sample["loop_end"] or (len(pcm) if sample["loop"] else 0)})
    spec["instruments"] = [_block_instrument(item, sample_index) for item in document["voices"]]
    spec["instruments"] += [_block_instrument(effect["instrument"], sample_index) for effect in document["effects"]]
    spec["tracks"] = [{"events": _track_events(track, muted or set())} for track in document["soundtracks"]]
    try:
        audio_block.validate(spec)
    except audio_block.AudioBlockError as error:
        raise AudioStudioError(str(error)) from error
    return spec


def pack_document(document: dict[str, Any], samples: dict[str, bytes], muted: set[int] | None = None) -> bytes:
    try:
        return audio_block.pack(compile_document(document, samples, muted))
    except audio_block.AudioBlockError as error:
        raise AudioStudioError(str(error)) from error


# --- samples from WAV files ------------------------------------------------------------

MAX_WAV_BYTES = 8 * 1024 * 1024


def wav_to_sample(data: bytes) -> bytes:
    """A WAV file (8- or 16-bit PCM, mono or stereo, any rate) as 8-bit unsigned 22050 Hz mono."""
    if len(data) > MAX_WAV_BYTES:
        raise AudioStudioError(say("audio", "the sound file is too big (8 MB at most)"))
    try:
        with wave.open(io.BytesIO(data)) as source:
            channels, width, rate = source.getnchannels(), source.getsampwidth(), source.getframerate()
            if source.getcomptype() != "NONE" or width not in (1, 2) or channels not in (1, 2) \
                    or not 4000 <= rate <= 96000:
                raise AudioStudioError(say("audio", "use an uncompressed 8- or 16-bit WAV file (mono or stereo)"))
            frames = source.readframes(min(source.getnframes(), rate * 30))
    except (wave.Error, EOFError, struct.error) as error:
        raise AudioStudioError(say("audio", "this is not a WAV file the kit can read")) from error
    count = len(frames) // (width * channels)
    values = []
    for index in range(count):
        total = 0
        for channel in range(channels):
            at = (index * channels + channel) * width
            total += (frames[at] - 128) * 256 if width == 1 else struct.unpack_from("<h", frames, at)[0]
        values.append(total // channels)
    out = bytearray()
    length = count * 22050 // rate
    for index in range(min(length, audio_block.MAX_SAMPLE_BYTES)):
        value = values[min(count - 1, index * rate // 22050)] if count else 0
        out.append(max(0, min(255, 128 + (value >> 8))))
    if not out:
        raise AudioStudioError(say("audio", "the sound file has no sound in it"))
    return bytes(out)


def export_document(document: dict[str, Any], samples: dict[str, bytes]) -> dict[str, Any]:
    """A self-contained export: the document with every sample's sound (hex), for another project."""
    document = validate_document(document)
    return {"schema": EXPORT_SCHEMA, "document": document,
            "sounds": {sample["artifact_id"]: samples[sample["artifact_id"]].hex() for sample in document["samples"]
                       if sample["artifact_id"] in samples}}


def read_export(export: Any) -> tuple[dict[str, Any], dict[str, bytes]]:
    """(document, artifact id -> sound) from an export, checked; or AudioStudioError."""
    if not isinstance(export, dict) or export.get("schema") != EXPORT_SCHEMA:
        raise AudioStudioError(say("audio", "not an AudioStudio export ({export_schema})", export_schema=EXPORT_SCHEMA))
    document = validate_document(copy.deepcopy(export.get("document")))
    sounds = export.get("sounds") or {}
    if not isinstance(sounds, dict):
        raise AudioStudioError(say("audio", "the export's sounds are damaged"))
    out = {}
    for sample in document["samples"]:
        text = sounds.get(sample["artifact_id"])
        try:
            pcm = bytes.fromhex(text) if isinstance(text, str) else b""
        except ValueError:
            pcm = b""
        if not 1 <= len(pcm) <= audio_block.MAX_SAMPLE_BYTES:
            raise AudioStudioError(say("audio", "the export has no usable sound for the sample {sample}", sample=repr(sample['name'])))
        out[sample["artifact_id"]] = pcm
    return document, out
