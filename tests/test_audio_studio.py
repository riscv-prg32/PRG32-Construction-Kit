"""AudioStudio (docs/audio_studio.md): documents, the API, generated code and packaging."""

from __future__ import annotations

import copy
import io
import json
import re
import struct
import wave
from types import SimpleNamespace

import pytest

from prg32_construction_kit import audio_block, audio_studio
from prg32_construction_kit.asm_generator import blocks_to_asm
from prg32_construction_kit.audio_studio import AudioStudioError
from prg32_construction_kit.generator import blocks_to_c, blocks_to_ir
from prg32_construction_kit.sample_data import default_blocks

from test_asm_generator import program, stmt
from test_auth import make_student, student_client


def wav(frames: list[int], rate: int = 22050, width: int = 2, channels: int = 1) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(width)
        target.setframerate(rate)
        if width == 2:
            target.writeframes(b"".join(struct.pack("<h", value) * channels for value in frames))
        else:
            target.writeframes(bytes((value & 0xFF) for value in frames for _ in range(channels)))
    return out.getvalue()


def song_document() -> dict:
    document = audio_studio.default_document()
    document["effects"].append({"name": "Jump", "instrument": audio_studio.instrument("Jump", "pulse", attack=0),
                                "note": 72, "duration_ms": 150, "volume": 240, "voice": 7})
    document["effects"].append({"name": "Coin", "instrument": audio_studio.instrument("Coin", "saw"),
                                "note": 84, "duration_ms": 90, "volume": 200, "voice": 6})
    rows = [[None] * 8 for _ in range(8)]
    rows[0][0], rows[0][4], rows[0][6] = 48, 55, "off"
    rows[1][2] = 64
    document["soundtracks"].append({"name": "Theme", "tempo": 140, "steps": 8, "loop": False, "rows": rows})
    return document


# --- documents ------------------------------------------------------------------------------

def test_the_default_document_is_valid_and_packs():
    document = audio_studio.validate_document(audio_studio.default_document())
    block = audio_studio.pack_document(document, {})
    assert block[:4] == b"AUD0"
    assert len(audio_block.read(block)["instruments"]) == 8


@pytest.mark.parametrize("change, message", [
    (lambda d: d.update(schema="other"), "not an AudioStudio document"),
    (lambda d: d["voices"].pop(), "exactly 8 voices"),
    (lambda d: d["voices"][0].update(attack=256), "attack"),
    (lambda d: d["voices"][0].update(pan=64), "pan"),
    (lambda d: d["voices"][0].update(sound="buzzer"), "sound must be one of"),
    (lambda d: d["voices"][0].update(sound="sample", sample="Missing"), "not in this project"),
    (lambda d: d["effects"][0].update(name="bad;name"), "needs a name"),
    (lambda d: d["effects"].append(copy.deepcopy(d["effects"][0])), "two sound effects"),
    (lambda d: d["soundtracks"][0]["rows"][0].append(1), "must have 8 steps"),
    (lambda d: d["soundtracks"][0]["rows"][1].__setitem__(0, 128), "step 1"),
    (lambda d: d["soundtracks"][0]["rows"][1].__setitem__(0, "loud"), "step 1"),
    (lambda d: d["soundtracks"][0].update(tempo=10), "tempo"),
    (lambda d: d["effects"].extend({"name": f"E{n}", "instrument": audio_studio.instrument("E")} for n in range(30)),
     "at most 24 sound effects"),
])
def test_bad_documents_are_refused_with_a_reason(change, message):
    document = song_document()
    change(document)
    with pytest.raises(AudioStudioError, match=message):
        audio_studio.validate_document(document)


def test_compiling_gives_fixed_instrument_and_track_numbers():
    document = song_document()
    spec = audio_studio.compile_document(document, {})
    assert len(spec["instruments"]) == 10                       # 8 voices, then the effects
    jump = spec["instruments"][8]
    assert jump["sample_id"] == audio_block.synth_id(2, 8, 15, 0) and jump["attack"] == 0
    events = spec["tracks"][0]["events"]
    assert events[0] == {"delta": 0, "command": "SET_TEMPO", "arg0": 140, "arg1": 0}
    steps = [(e["command"], e["arg0"], e["arg1"]) for e in events[1:]]
    assert steps == [("NOTE_ON", 0, 48), ("NOTE_ON", 1, 64), ("NOTE_ON", 0, 55), ("NOTE_OFF", 0, 0),
                     ("NOTE_OFF", 1, 0), ("END", 0, 0)]
    # The tracker runs an event, then waits its delta: notes at steps 0, 2, 4, off at 6, end at 8.
    assert [e["delta"] for e in events[1:]] == [2, 2, 2, 2, 0, 0]


def test_a_soundtrack_starting_late_waits_on_set_tempo_and_loops_back_to_it():
    document = song_document()
    track = document["soundtracks"][0]
    track["rows"] = [[None] * 8 for _ in range(8)]
    track["rows"][2][3], track["loop"] = 70, True
    events = audio_studio.compile_document(document, {})["tracks"][0]["events"]
    assert [(e["command"], e["delta"]) for e in events] == [("SET_TEMPO", 3), ("NOTE_ON", 5), ("JUMP", 0)]
    assert events[-1]["arg0"] == 0 and events[-1]["arg1"] == 0


def test_a_looping_soundtrack_jumps_back_and_muted_rows_are_left_out():
    document = song_document()
    document["soundtracks"][0]["loop"] = True
    events = audio_studio.compile_document(document, {}, muted={1})["tracks"][0]["events"]
    assert all(e["arg0"] != 1 for e in events if e["command"] in ("NOTE_ON", "NOTE_OFF"))
    assert events[-1]["command"] == "JUMP" and events[-1]["arg0"] == 0


def test_packing_is_deterministic():
    document = song_document()
    assert audio_studio.pack_document(document, {}) == audio_studio.pack_document(copy.deepcopy(document), {})
    louder = copy.deepcopy(document)
    louder["effects"][0]["instrument"]["volume"] = 255
    assert audio_studio.pack_document(louder, {}) != audio_studio.pack_document(document, {})


def test_wav_files_become_8_bit_22050_hz_mono():
    sound = audio_studio.wav_to_sample(wav([0, 32767, -32768, 0] * 100))
    assert len(sound) == 400 and set(sound[:4]) <= {0, 128, 255}
    stereo_low_rate = audio_studio.wav_to_sample(wav([1000] * 11025, rate=11025, channels=2))
    assert abs(len(stereo_low_rate) - 22050) <= 2
    eight_bit = audio_studio.wav_to_sample(wav([128, 255, 0], width=1))
    assert eight_bit == bytes([128, 255, 0])


@pytest.mark.parametrize("data, message", [
    (b"not a wav file", "WAV"),
    (b"RIFF" + b"\x00" * 40, "WAV"),
    (b"x" * (audio_studio.MAX_WAV_BYTES + 1), "too big"),
])
def test_bad_sound_files_are_refused(data, message):
    with pytest.raises(AudioStudioError, match=message):
        audio_studio.wav_to_sample(data)


def test_export_and_import_keep_the_sound():
    document = song_document()
    document["samples"].append({"name": "Drum", "artifact_id": "a1", "base_note": 60, "loop": False,
                                "loop_start": 0, "loop_end": 0})
    document["voices"][6] = audio_studio.instrument("Drums", "sample", sample="Drum")
    exported = audio_studio.export_document(document, {"a1": bytes(range(200))})
    again, sounds = audio_studio.read_export(json.loads(json.dumps(exported)))
    assert again["voices"] == document["voices"] and again["soundtracks"] == document["soundtracks"]
    assert list(sounds.values()) == [bytes(range(200))]
    with pytest.raises(AudioStudioError):
        audio_studio.read_export({"schema": "something else"})


# --- the API --------------------------------------------------------------------------------

def new_project(client, title="Song game"):
    response = client.post("/api/projects", json={"title": title, "blocks_json": default_blocks()})
    assert response.status_code == 201
    return response.get_json()


def test_a_project_starts_with_the_default_sound(client):
    project = new_project(client)
    answer = client.get(f"/api/projects/{project['id']}/audio").get_json()
    assert answer["version"] == 0 and answer["asset_id"] is None
    assert answer["document"] == audio_studio.default_document()


def test_saving_names_the_version_and_never_overwrites_a_newer_one(client):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio"
    first = client.put(url, json={"document": song_document(), "expected_version": 0}).get_json()
    assert first["version"] >= 1
    assert first["ids"]["effects"]["Jump"] == {"instrument": 8, "voice": 7, "note": 72}
    assert first["ids"]["soundtracks"] == {"Theme": 0}
    changed = song_document()
    changed["soundtracks"][0]["tempo"] = 90
    second = client.put(url, json={"document": changed, "expected_version": first["version"]}).get_json()
    assert second["version"] > first["version"]
    stale = client.put(url, json={"document": song_document(), "expected_version": first["version"]})
    assert stale.status_code == 409 and stale.get_json()["code"] == "audio_version_conflict"
    assert stale.get_json()["current"]["version"] == second["version"]
    assert client.get(url).get_json()["document"]["soundtracks"][0]["tempo"] == 90


def test_a_new_document_in_another_window_conflicts_too(client):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio"
    assert client.put(url, json={"document": song_document(), "expected_version": 0}).status_code == 200
    assert client.put(url, json={"document": song_document(), "expected_version": 0}).status_code == 409


def test_invalid_documents_are_refused(client):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio"
    bad = song_document()
    bad["voices"][0]["volume"] = 999
    refused = client.put(url, json={"document": bad, "expected_version": 0})
    assert refused.status_code == 400 and refused.get_json()["code"] == "audio_invalid"
    assert client.put(url, json={"document": song_document(), "expected_version": "1"}).status_code == 400
    assert client.get(url).get_json()["version"] == 0


def test_only_the_owner_changes_a_projects_sound(app, client):
    make_student(client, "ada")
    make_student(client, "bob")
    ada, bob = student_client(app, "ada"), student_client(app, "bob")
    project = new_project(ada)
    url = f"/api/projects/{project['id']}/audio"
    assert ada.put(url, json={"document": song_document(), "expected_version": 0}).status_code == 200
    assert bob.get(url).status_code == 404
    assert bob.put(url, json={"document": song_document(), "expected_version": 1}).status_code == 404
    assert bob.post(f"{url}/preview", json={}).status_code == 404
    assert bob.get(f"{url}/export").status_code == 404
    assert bob.get(f"/audio-studio/{project['id']}").status_code == 302          # AudioStudio is an IDE tab now
    assert 'id="canEdit" value="no"' in bob.get(f"/ide/{project['id']}").get_data(as_text=True)
    upload = bob.post(f"{url}/samples", data={"file": (io.BytesIO(wav([0] * 100)), "a.wav")})
    assert upload.status_code == 404
    # The administrator may read (and change) any project.
    assert client.get(url).status_code == 200


def test_shared_projects_sound_is_read_only_for_students(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    shared = new_project(client, "Shared starter")
    client.put(f"/api/projects/{shared['id']}", json={"owner_id": None})
    url = f"/api/projects/{shared['id']}/audio"
    assert ada.get(url).status_code == 200         # a shared project is readable...
    refused = ada.put(url, json={"document": song_document(), "expected_version": 0})
    assert refused.status_code == 403              # ...but not changeable


def test_preview_gives_the_audio_block_of_the_unsaved_document(client):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio/preview"
    response = client.post(url, json={"document": song_document(), "muted": [1]})
    assert response.status_code == 200 and response.mimetype == "application/octet-stream"
    assert response.data == audio_studio.pack_document(song_document(), {}, {1})
    assert client.post(url, json={"muted": [9]}).status_code == 400
    assert client.post(url, json={"muted": "all"}).status_code == 400
    assert client.post(url, json={}).data == audio_studio.pack_document(audio_studio.default_document(), {})


def test_samples_are_uploaded_converted_and_played(client, app):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio"
    upload = client.post(f"{url}/samples", data={"file": (io.BytesIO(wav([0, 16000, -16000] * 300)), "drum.wav"),
                                                 "name": "Drum"})
    assert upload.status_code == 201
    sample = upload.get_json()
    assert sample["frames"] == 900 and sample["name"] == "Drum"
    artifact = client.get(f"/api/artifacts/{sample['artifact_id']}").get_json()
    assert artifact["kind"] == "audio_sample"
    document = song_document()
    document["samples"].append({"name": "Drum", "artifact_id": sample["artifact_id"], "base_note": 60,
                                "loop": False, "loop_start": 0, "loop_end": 0})
    document["voices"][6] = audio_studio.instrument("Drums", "sample", sample="Drum")
    saved = client.put(url, json={"document": document, "expected_version": 0}).get_json()
    assert saved["missing_samples"] == []
    block = client.post(f"{url}/preview", json={}).data
    assert len(audio_block.read(block)["samples"][0]["pcm"]) == 900
    # Bad uploads are refused and store nothing.
    assert client.post(f"{url}/samples", data={"file": (io.BytesIO(b"nope"), "x.wav")}).status_code == 400
    assert client.post(f"{url}/samples", data={}).status_code == 400


def test_a_sample_whose_sound_is_gone_is_reported_and_blocks_building(client, monkeypatch):
    project = new_project(client)
    url = f"/api/projects/{project['id']}/audio"
    document = song_document()
    document["samples"].append({"name": "Ghost", "artifact_id": "doesnotexist", "base_note": 60,
                                "loop": False, "loop_start": 0, "loop_end": 0})
    saved = client.put(url, json={"document": document, "expected_version": 0}).get_json()
    assert saved["missing_samples"] == ["Ghost"]
    refused = client.post(f"{url}/preview", json={})
    assert refused.status_code == 400 and refused.get_json()["missing"] == ["Ghost"]
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    build = client.post(f"/api/projects/{project['id']}/package", json={})
    assert build.status_code == 400 and build.get_json().get("code") == "audio_missing_samples"


def test_a_samples_sound_from_another_account_is_not_used(app, client):
    make_student(client, "ada")
    make_student(client, "bob")
    ada, bob = student_client(app, "ada"), student_client(app, "bob")
    bob_project = new_project(bob)
    bob_sample = bob.post(f"/api/projects/{bob_project['id']}/audio/samples",
                          data={"file": (io.BytesIO(wav([0] * 50)), "b.wav")}).get_json()
    project = new_project(ada)
    document = song_document()
    document["samples"].append({"name": "Stolen", "artifact_id": bob_sample["artifact_id"], "base_note": 60,
                                "loop": False, "loop_start": 0, "loop_end": 0})
    saved = ada.put(f"/api/projects/{project['id']}/audio", json={"document": document, "expected_version": 0})
    assert saved.get_json()["missing_samples"] == ["Stolen"]


def test_export_then_import_into_another_project(client):
    source = new_project(client, "Source")
    url = f"/api/projects/{source['id']}/audio"
    sample = client.post(f"{url}/samples", data={"file": (io.BytesIO(wav([500] * 64)), "s.wav"),
                                                 "name": "Blip"}).get_json()
    document = song_document()
    document["samples"].append({"name": "Blip", "artifact_id": sample["artifact_id"], "base_note": 72,
                                "loop": True, "loop_start": 0, "loop_end": 0})
    client.put(url, json={"document": document, "expected_version": 0})
    exported = client.get(f"{url}/export")
    assert exported.headers["Content-Disposition"].startswith("attachment")
    target = new_project(client, "Target")
    imported = client.post(f"/api/projects/{target['id']}/audio/import",
                           json={"export": exported.get_json(), "expected_version": 0}).get_json()
    assert imported["missing_samples"] == []
    copied = imported["document"]["samples"][0]
    assert copied["name"] == "Blip" and copied["artifact_id"] != sample["artifact_id"]
    assert client.post(f"/api/projects/{target['id']}/audio/preview", json={}).data == \
        client.post(f"{url}/preview", json={}).data
    assert client.post(f"/api/projects/{target['id']}/audio/import",
                       json={"export": {"schema": "x"}, "expected_version": 1}).status_code == 400


def test_sound_counts_against_the_storage_quota(app, client):
    make_student(client, "ada")
    ada = student_client(app, "ada")
    project = ada.post("/api/projects", json={"title": "Full", "description": "x" * 900_000}).get_json()
    app.config["PRG32_KIT_QUOTA_MB"] = 1
    url = f"/api/projects/{project['id']}/audio"
    refused = ada.post(f"{url}/samples", data={"file": (io.BytesIO(wav([0] * 200_000)), "big.wav")})
    assert refused.status_code == 413 and refused.get_json()["code"] == "quota_exceeded"
    assert ada.post(f"{url}/samples", data={"file": (io.BytesIO(wav([0] * 1000)), "small.wav")}).status_code == 201


def test_the_audio_studio_opens_as_a_tab_of_the_ide(client):
    project = new_project(client)
    old = client.get(f"/audio-studio/{project['id']}")
    assert old.status_code == 302 and old.headers["Location"].endswith(f"/ide/{project['id']}#sound")
    html = client.get(f"/ide/{project['id']}").get_data(as_text=True)
    assert "audio_studio.js" in html and 'id="audioStudio"' in html and 'id="canEdit" value="yes"' in html
    assert "<script>" not in html.replace("<script src", "")


# --- generated code and packaging -------------------------------------------------------------

def sound_program():
    return program(start=[stmt("prg32_soundtrack_play", TRACK="Theme")],
                   update=[stmt("prg32_sound_effect", EFFECT="Jump"), stmt("prg32_sound_effect", EFFECT="Coin"),
                           stmt("prg32_soundtrack_stop"), stmt("prg32_sound_stop_all")])


def test_generated_c_and_assembly_use_the_documents_numbers():
    project = {"audio_studio": song_document()}
    ir = blocks_to_ir(sound_program(), project)
    assert not ir["warnings"]
    _ir, c_source = blocks_to_c(sound_program(), project)
    assert "prg32_audio_play_track(0);" in c_source
    assert "prg32_audio_note(7, 8, 72, 240, 150);" in c_source
    assert "prg32_audio_note(6, 9, 84, 200, 90);" in c_source
    assert "prg32_audio_stop_track();" in c_source and "prg32_audio_stop_all();" in c_source
    _ir, asm = blocks_to_asm(sound_program(), project)
    for name in ("prg32_audio_play_track", "prg32_audio_note", "prg32_audio_stop_track", "prg32_audio_stop_all"):
        assert re.search(rf"call\s+{name}\b", asm), name
    assert blocks_to_c(sound_program(), project) == blocks_to_c(sound_program(), copy.deepcopy(project))


def test_a_name_that_is_not_in_audio_studio_is_a_warning_not_a_guess():
    ir = blocks_to_ir(program(update=[stmt("prg32_sound_effect", EFFECT="Nope")]), {"audio_studio": song_document()})
    assert any("Nope" in warning for warning in ir["warnings"])
    _ir, c_source = blocks_to_c(program(update=[stmt("prg32_sound_effect", EFFECT="Nope")]), {})
    assert "skipped: no sound effect named Nope" in c_source


def test_the_cartridge_build_gets_the_audio_block(client, monkeypatch):
    seen = {}

    def fake_builder(command, **_kwargs):
        if "--audio-block" in command:
            with open(command[command.index("--audio-block") + 1], "rb") as block:
                seen.setdefault("blocks", []).append(block.read())
        with open(command[command.index("--out") + 1], "wb") as cartridge:
            cartridge.write(b"PRG2" + b"\x00" * 60)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("prg32_construction_kit.packager.subprocess.run", fake_builder)
    monkeypatch.setattr("prg32_construction_kit.routes.toolchain_present", lambda _command: True)
    project = client.post("/api/projects", json={"title": "Loud", "blocks_json": sound_program()}).get_json()
    client.put(f"/api/projects/{project['id']}/audio", json={"document": song_document(), "expected_version": 0})
    first = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]})
    assert first.status_code == 200, first.get_json()
    expected = audio_studio.pack_document(song_document(), {})
    assert seen["blocks"] and all(block == expected for block in seen["blocks"])
    c_source = client.post(f"/api/projects/{project['id']}/convert", json={}).get_json()["c_source"]
    assert "prg32_audio_note(7, 8, 72, 240, 150);" in c_source
    client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]})
    assert seen["blocks"][-1] == seen["blocks"][0]       # the same inputs give the same bytes


# --- archives, copies and old databases ------------------------------------------------------

def project_with_sample(client, title="Drums", shared=False):
    project = new_project(client, title)
    if shared:                                     # a shared classroom project, like the starter games
        client.put(f"/api/projects/{project['id']}", json={"owner_id": None})
    url = f"/api/projects/{project['id']}/audio"
    sample = client.post(f"{url}/samples", data={"file": (io.BytesIO(wav([9000, -9000] * 100)), "d.wav"),
                                                 "name": "Drum"}).get_json()
    document = song_document()
    document["samples"].append({"name": "Drum", "artifact_id": sample["artifact_id"], "base_note": 60,
                                "loop": False, "loop_start": 0, "loop_end": 0})
    document["voices"][6] = audio_studio.instrument("Drums", "sample", sample="Drum")
    assert client.put(url, json={"document": document, "expected_version": 0}).status_code == 200
    return project, sample


def test_the_project_archive_carries_the_sound_and_imports_again(client):
    import zipfile

    project, sample = project_with_sample(client)
    archive = client.get(f"/api/projects/{project['id']}/archive").data
    names = zipfile.ZipFile(io.BytesIO(archive)).namelist()
    assert "audio/samples/01-drum.u8" in names
    imported = client.post("/api/projects/import", data={"file": (io.BytesIO(archive), "p.zip")})
    assert imported.status_code == 201, imported.get_json()
    copy_id = imported.get_json()["id"]
    answer = client.get(f"/api/projects/{copy_id}/audio").get_json()
    assert answer["missing_samples"] == []
    assert answer["document"]["samples"][0]["artifact_id"] != sample["artifact_id"]
    assert client.post(f"/api/projects/{copy_id}/audio/preview", json={}).data == \
        client.post(f"/api/projects/{project['id']}/audio/preview", json={}).data
    # The archive of the copy is the same archive: nothing depends on ids or times.
    again = client.get(f"/api/projects/{copy_id}/archive").data
    original = zipfile.ZipFile(io.BytesIO(archive))
    copied = zipfile.ZipFile(io.BytesIO(again))
    assert original.read("audio/samples/01-drum.u8") == copied.read("audio/samples/01-drum.u8")


def test_a_students_copy_of_a_shared_project_owns_its_samples(app, client):
    project, _sample = project_with_sample(client, "Shared song", shared=True)
    make_student(client, "ada")
    ada = reader = student_client(app, "ada")
    copy_response = ada.post(f"/api/projects/{project['id']}/duplicate", json={})
    assert copy_response.status_code == 201
    copy_id = copy_response.get_json()["id"]
    answer = reader.get(f"/api/projects/{copy_id}/audio").get_json()
    assert answer["missing_samples"] == [] and len(answer["document"]["samples"]) == 1
    artifact = reader.get(f"/api/artifacts/{answer['document']['samples'][0]['artifact_id']}").get_json()
    assert artifact["owner_id"] == reader.get(f"/api/projects/{copy_id}").get_json()["owner_id"]


def test_an_archive_cannot_smuggle_files_as_samples():
    from prg32_construction_kit import project_format

    project = {"title": "x", "blocks_json": {}, "game_json": {}}
    files = project_format.project_files(project, [], [], [{"artifact_id": "a", "name": "s", "pcm": b"\x80" * 10}])
    manifest = json.loads(files["prg32.project.json"])
    for path in ("../etc/passwd", "audio/samples/../../x.u8", "src/game.c", "audio/samples/01-x.wav"):
        bad = copy.deepcopy(manifest)
        bad["audio_samples"][0]["path"] = path
        with pytest.raises(project_format.ProjectFormatError):
            project_format.contents_from_files({**files, "prg32.project.json": json.dumps(bad).encode()})
    too_long = {**files, manifest["audio_samples"][0]["path"]: b"\x80" * (audio_block.MAX_SAMPLE_BYTES + 1)}
    with pytest.raises(project_format.ProjectFormatError):
        project_format.contents_from_files(too_long)
    # Archives without sound stay exactly as they were.
    plain = project_format.project_files(project, [], [])
    assert "audio_samples" not in json.loads(plain["prg32.project.json"])


def test_an_old_database_gets_the_asset_version_column(tmp_path):
    import sqlite3

    from conftest import make_app

    database = tmp_path / "test.sqlite"
    make_app(tmp_path)
    with sqlite3.connect(database) as connection:
        connection.execute("ALTER TABLE assets DROP COLUMN version")
        assert "version" not in [row[1] for row in connection.execute("PRAGMA table_info(assets)")]
    make_app(tmp_path)
    make_app(tmp_path)                             # idempotent
    with sqlite3.connect(database) as connection:
        assert "version" in [row[1] for row in connection.execute("PRAGMA table_info(assets)")]


def test_deleting_an_account_with_its_items_removes_its_sample_sounds(app, client):
    from pathlib import Path

    student = make_student(client, "ada")
    ada = student_client(app, "ada")
    project = new_project(ada)
    sample = ada.post(f"/api/projects/{project['id']}/audio/samples",
                      data={"file": (io.BytesIO(wav([1234] * 80)), "s.wav")}).get_json()
    assert sample["frames"] == 80
    path = Path(app.config["ARTIFACT_ROOT"]) / "audio" / str(student["id"])
    assert len(list(path.glob("*.u8"))) == 1        # the sound file, named by its SHA-256
    client.delete(f"/api/users/{student['id']}", query_string={"with_items": 1})
    assert not path.exists()


def test_the_generic_asset_routes_apply_audio_studio_rules(client):
    project = new_project(client)
    bad = client.post("/api/assets", json={"project_id": project["id"], "name": "AudioStudio", "kind": "audio_studio",
                                           "data": {"schema": "prg32-kit-audio-1", "voices": []}})
    assert bad.status_code == 400 and bad.get_json()["code"] == "audio_invalid"
    good = client.post("/api/assets", json={"project_id": project["id"], "name": "AudioStudio", "kind": "audio_studio",
                                            "data": song_document()})
    assert good.status_code == 201
    asset = good.get_json()
    louder = song_document()
    louder["voices"][0]["volume"] = 255
    saved = client.put(f"/api/assets/{asset['id']}", json={"data": louder, "expected_version": asset["version"]})
    assert saved.status_code == 200 and saved.get_json()["version"] == asset["version"] + 1
    stale = client.put(f"/api/assets/{asset['id']}", json={"data": louder, "expected_version": asset["version"]})
    assert stale.status_code == 409 and stale.get_json()["code"] == "version_conflict"
    assert client.put(f"/api/assets/{asset['id']}", json={"data": {"schema": "x"}}).status_code == 400


def test_the_engine_plays_each_note_on_its_step(tmp_path):
    """Through the real PRG32 engine (the browser core): every note starts exactly on its grid step."""
    import shutil
    import subprocess

    from pathlib import Path

    if shutil.which("node") is None:
        pytest.skip("Node.js is not installed")
    root = Path(__file__).resolve().parent.parent
    document = audio_studio.default_document()
    rows = [[None] * 12 for _ in range(8)]
    starts = {0: 0, 1: 3, 2: 5, 7: 9}
    for voice, step in starts.items():
        rows[voice][step] = 60 + voice
    rows[1][7] = "off"
    for voice in range(8):
        document["voices"][voice].update(attack=0, release=0)
    document["soundtracks"].append({"name": "Steps", "tempo": 120, "steps": 12, "loop": False, "rows": rows})
    block = tmp_path / "steps.aud"
    block.write_bytes(audio_studio.pack_document(document, {}))
    script = f"""
const core = await require({json.dumps(str(root / "static" / "wasm" / "prg32-core.js"))})();
const bytes = require('fs').readFileSync({json.dumps(str(block))});
core._prg32_preview_start();
const at = core._malloc(bytes.length); core.HEAPU8.set(bytes, at);
if (!core._prg32_preview_load(at, bytes.length)) process.exit(3);
core._prg32_preview_play_track(0);
const buffer = core._malloc(24), out = [];
for (let tick = 0; tick < 12; tick += 1) {{
  core._prg32_preview_advance(tick === 0 ? 20 : 125);   // 20 ms into each 125 ms step
  core._prg32_audio_take();
  const row = [];
  for (let v = 0; v < 8; v += 1) {{ core._prg32_audio_voice(v, buffer); row.push(core.HEAP32[buffer >> 2]); }}
  out.push(row);
}}
console.log(JSON.stringify(out));
"""
    result = subprocess.run(["node", "--input-type=module", "-e",
                             "import {createRequire} from 'module'; const require = createRequire(import.meta.url);" + script],
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr
    active = json.loads(result.stdout)
    for voice, step in starts.items():
        first = next(tick for tick, row in enumerate(active) if row[voice])
        assert first == step, (voice, first, step)
    assert active[6][1] and not active[8][1]          # voice 1 released at step 7
