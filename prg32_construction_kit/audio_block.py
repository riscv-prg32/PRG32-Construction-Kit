"""PRG32 audio blocks (AUD0): check, pack and read them (contracts/prg32-audio-contract-1.json "block").

An audio block is what a PRG32 cartridge carries after its code: samples, instruments
and tracks for the eight-voice engine. This module writes exactly the bytes the PRG32
SDK's tools/prg32audio_pack.py writes for the same content (tests/test_audio_block.py
proves it), but takes the content as data instead of files, and refuses anything the
firmware would refuse, or that could make it read past the block or loop for ever.

A block spec is plain data:

    {"samples": [{"pcm": bytes (unsigned 8-bit), "base_note": 60, "loop": False,
                  "loop_start": 0, "loop_end": 0}],
     "instruments": [{"sample_id": 0 or a synth id, "default_volume": 255, "default_pan": 0,
                      "attack": 0, "decay": 0, "sustain": 255, "release": 0}],
     "tracks": [{"events": [{"delta": 0, "command": "NOTE_ON", "arg0": 0, "arg1": 60}, ...]}]}
"""

from __future__ import annotations

import struct
from typing import Any

MAGIC = b"AUD0"
VERSION = 1
HEADER = struct.Struct("<4sHHHHHHIIIIII")
SAMPLE_DESC = struct.Struct("<IIIIHBB")
INSTRUMENT_DESC = struct.Struct("<HBBBBBB")
TRACK_DESC = struct.Struct("<II")
EVENT = struct.Struct("<BBBB")
COMMANDS = {"NOTE_ON": 1, "NOTE_OFF": 2, "SET_VOLUME": 3, "SET_PAN": 4, "SET_TEMPO": 5, "PLAY_SAMPLE": 6,
            "JUMP": 7, "END": 255}
MAX_SAMPLES, MAX_INSTRUMENTS, MAX_TRACKS = 64, 32, 16
MAX_SAMPLE_BYTES = 256 * 1024        # one sample (about 12 s at 22050 Hz)
MAX_BLOCK_BYTES = 1024 * 1024        # the whole block
MAX_EVENTS = 16384                   # all tracks together
SYNTH_MARKER = 0x8000
VOICES = 8
PAN_LEFT, PAN_RIGHT = -64, 63


class AudioBlockError(ValueError):
    """A block (or spec) the kit refuses, with a message for students."""


def synth_id(waveform: int, pulse_width: int = 8, cutoff: int = 15, resonance: int = 0) -> int:
    """PRG32_AUDIO_SYNTH_ID: waveform 0 triangle, 1 saw, 2 pulse, 3 noise; the others 0..15, 0..15, 0..3."""
    return SYNTH_MARKER | (resonance & 3) << 10 | (cutoff & 15) << 6 | (pulse_width & 15) << 2 | (waveform & 3)


def _int(value: Any, where: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise AudioBlockError(f"{where} must be a whole number from {low} to {high}")
    return value


def validate(spec: dict[str, Any]) -> dict[str, Any]:
    """The spec with defaults filled in, or AudioBlockError saying what is wrong."""
    if not isinstance(spec, dict):
        raise AudioBlockError("an audio block must be an object")
    samples, instruments, tracks = spec.get("samples", []), spec.get("instruments", []), spec.get("tracks", [])
    for name, items, limit in (("samples", samples, MAX_SAMPLES), ("instruments", instruments, MAX_INSTRUMENTS),
                               ("tracks", tracks, MAX_TRACKS)):
        if not isinstance(items, list) or len(items) > limit:
            raise AudioBlockError(f"{name} must be a list of at most {limit}")
    clean: dict[str, Any] = {"samples": [], "instruments": [], "tracks": []}
    for index, sample in enumerate(samples):
        where = f"sample {index}"
        pcm = sample.get("pcm") if isinstance(sample, dict) else None
        if not isinstance(pcm, (bytes, bytearray)) or not 1 <= len(pcm) <= MAX_SAMPLE_BYTES:
            raise AudioBlockError(f"{where} needs 1 to {MAX_SAMPLE_BYTES} bytes of 8-bit sound")
        loop = bool(sample.get("loop", False))
        loop_start = _int(sample.get("loop_start", 0), f"{where} loop start", 0, len(pcm))
        loop_end = _int(sample.get("loop_end", len(pcm) if loop else 0), f"{where} loop end", 0, len(pcm))
        if loop and loop_end <= loop_start:
            raise AudioBlockError(f"{where}: a loop must end after it starts")
        clean["samples"].append({"pcm": bytes(pcm), "base_note": _int(sample.get("base_note", 60), f"{where} base note",
                                                                      0, 127),
                                 "loop": loop, "loop_start": loop_start, "loop_end": loop_end})
    for index, instrument in enumerate(instruments):
        where = f"instrument {index}"
        if not isinstance(instrument, dict):
            raise AudioBlockError(f"{where} must be an object")
        sample_id = _int(instrument.get("sample_id", 0), f"{where} sound", 0, 0xFFFF)
        if not sample_id & SYNTH_MARKER and sample_id >= len(clean["samples"]) and sample_id != 62:
            raise AudioBlockError(f"{where} plays sample {sample_id}, which is not in the block")
        if sample_id & SYNTH_MARKER and sample_id & 0x7000:
            raise AudioBlockError(f"{where} has an invalid synth sound id")
        clean["instruments"].append({
            "sample_id": sample_id,
            "default_volume": _int(instrument.get("default_volume", 255), f"{where} volume", 0, 255),
            "default_pan": _int(instrument.get("default_pan", 0), f"{where} pan", PAN_LEFT, PAN_RIGHT),
            **{key: _int(instrument.get(key, 255 if key == "sustain" else 0), f"{where} {key}", 0, 255)
               for key in ("attack", "decay", "sustain", "release")}})
    total = 0
    for index, track in enumerate(tracks):
        where = f"track {index}"
        events = track.get("events") if isinstance(track, dict) else None
        if not isinstance(events, list) or not events:
            raise AudioBlockError(f"{where} needs at least one event")
        total += len(events)
        if total > MAX_EVENTS:
            raise AudioBlockError(f"the tracks may have at most {MAX_EVENTS} events in all")
        clean_events = []
        for number, event in enumerate(events):
            at = f"{where} event {number}"
            if not isinstance(event, dict):
                raise AudioBlockError(f"{at} must be an object")
            command = event.get("command", "END")
            code = COMMANDS.get(command) if isinstance(command, str) else command
            if code not in COMMANDS.values():
                raise AudioBlockError(f"{at}: unknown command {command!r}")
            arg0 = _int(event.get("arg0", 0), f"{at} first value", 0, 255)
            arg1 = _int(event.get("arg1", 0), f"{at} second value", 0, 255)
            if code in (COMMANDS["NOTE_ON"], COMMANDS["NOTE_OFF"], COMMANDS["SET_VOLUME"], COMMANDS["SET_PAN"]) \
                    and arg0 >= VOICES:
                raise AudioBlockError(f"{at}: voice {arg0} does not exist (0 to 7)")
            if code == COMMANDS["NOTE_ON"] and arg1 > 127:
                raise AudioBlockError(f"{at}: note {arg1} is above 127")
            if code == COMMANDS["NOTE_ON"] and arg0 >= len(clean["instruments"]) and arg0 not in (0,):
                raise AudioBlockError(f"{at}: voice {arg0} plays instrument {arg0}, which is not in the block")
            if code == COMMANDS["JUMP"] and (arg1 << 8 | arg0) >= len(events):
                raise AudioBlockError(f"{at}: jumps past the end of the track")
            clean_events.append({"delta": _int(event.get("delta", 0), f"{at} wait", 0, 255), "command": code,
                                 "arg0": arg0, "arg1": arg1})
        _refuse_silent_loops(clean_events, where)
        clean["tracks"].append({"events": clean_events})
    return clean


def _refuse_silent_loops(events: list[dict[str, int]], where: str) -> None:
    """A JUMP back over events that all wait 0 ticks would repeat for ever without time passing."""
    for index, event in enumerate(events):
        if event["command"] == COMMANDS["JUMP"]:
            target = event["arg1"] << 8 | event["arg0"]
            if target <= index and all(item["delta"] == 0 for item in events[target:index + 1]):
                raise AudioBlockError(f"{where}: the jump at event {index} loops without any wait")


def _align4(data: bytearray) -> None:
    while len(data) % 4:
        data.append(0)


def pack(spec: dict[str, Any]) -> bytes:
    """The AUD0 block for a spec: the same bytes as the SDK's tools/prg32audio_pack.py."""
    spec = validate(spec)
    payload, sample_descs = bytearray(), bytearray()
    for sample in spec["samples"]:
        offset = len(payload)
        payload.extend(sample["pcm"])
        flags = 1 if sample["loop"] else 0
        sample_descs.extend(SAMPLE_DESC.pack(offset, len(sample["pcm"]), sample["loop_start"],
                                             sample["loop_end"] if flags else 0, sample["base_note"], flags, 0))
    instrument_descs = bytearray()
    for instrument in spec["instruments"]:
        instrument_descs.extend(INSTRUMENT_DESC.pack(instrument["sample_id"], instrument["default_volume"],
                                                     instrument["default_pan"] & 0xFF, instrument["attack"],
                                                     instrument["decay"], instrument["sustain"],
                                                     instrument["release"]))
    events, track_descs = bytearray(), bytearray()
    for track in spec["tracks"]:
        track_descs.extend(TRACK_DESC.pack(len(events) // EVENT.size, len(track["events"])))
        for event in track["events"]:
            events.extend(EVENT.pack(event["delta"], event["command"], event["arg0"], event["arg1"]))
    block = bytearray(HEADER.size)
    offsets = []
    for part in (sample_descs, instrument_descs, track_descs, events, payload):
        offsets.append(len(block))
        block.extend(part)
        _align4(block)
    if len(block) > MAX_BLOCK_BYTES:
        raise AudioBlockError(f"the audio is {len(block)} bytes; a cartridge may carry at most {MAX_BLOCK_BYTES}")
    block[:HEADER.size] = HEADER.pack(MAGIC, VERSION, HEADER.size, len(spec["samples"]), len(spec["instruments"]),
                                      len(spec["tracks"]), 0, *offsets, len(block))
    return bytes(block)


def read(block: bytes) -> dict[str, Any]:
    """A block back as a spec, checked as the firmware checks it (audio_assets.c), or AudioBlockError."""
    if len(block) < HEADER.size or len(block) > MAX_BLOCK_BYTES:
        raise AudioBlockError("not a PRG32 audio block (wrong size)")
    (magic, version, header_size, sample_count, instrument_count, track_count, _reserved, samples_offset,
     instruments_offset, tracks_offset, events_offset, data_offset, block_size) = HEADER.unpack_from(block)
    if magic != MAGIC or version != VERSION or header_size < HEADER.size or block_size != len(block):
        raise AudioBlockError("not a PRG32 audio block (wrong header)")
    if sample_count > MAX_SAMPLES or instrument_count > MAX_INSTRUMENTS or track_count > MAX_TRACKS:
        raise AudioBlockError("the audio block has too many samples, instruments or tracks")

    def table(offset: int, count: int, item: struct.Struct) -> list[tuple]:
        if offset + count * item.size > block_size:
            raise AudioBlockError("the audio block points outside itself")
        return [item.unpack_from(block, offset + index * item.size) for index in range(count)]

    if data_offset > block_size or events_offset > data_offset:
        raise AudioBlockError("the audio block points outside itself")
    data = block[data_offset:block_size]
    spec: dict[str, Any] = {"samples": [], "instruments": [], "tracks": []}
    for offset, length, loop_start, loop_end, base_note, flags, _ in table(samples_offset, sample_count, SAMPLE_DESC):
        if offset + length > len(data):
            raise AudioBlockError("a sample points outside the audio block")
        spec["samples"].append({"pcm": bytes(data[offset:offset + length]), "base_note": base_note,
                                "loop": bool(flags & 1), "loop_start": loop_start, "loop_end": loop_end})
    for sample_id, volume, pan, attack, decay, sustain, release in table(instruments_offset, instrument_count,
                                                                          INSTRUMENT_DESC):
        spec["instruments"].append({"sample_id": sample_id, "default_volume": volume,
                                    "default_pan": pan - 256 if pan > 127 else pan, "attack": attack, "decay": decay,
                                    "sustain": sustain, "release": release})
    capacity = (data_offset - events_offset) // EVENT.size
    for first, count in table(tracks_offset, track_count, TRACK_DESC):
        if first > capacity or count > capacity - first:
            raise AudioBlockError("a track points outside the audio block")
        spec["tracks"].append({"events": [
            {"delta": delta, "command": next((name for name, code in COMMANDS.items() if code == command), command),
             "arg0": arg0, "arg1": arg1}
            for delta, command, arg0, arg1 in table(events_offset + first * EVENT.size, count, EVENT)]})
    return spec
