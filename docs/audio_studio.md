# AudioStudio

AudioStudio is where a project gets its sound, the way Sprite Lab is where it gets its
pictures. Open it from the **AudioStudio** menu (choose a game; the last one you opened is
offered first), from a project (**AudioStudio** button) or from the dashboard (**Sound**). What you hear there is the PRG32 console's own sound engine
(`audio_engine.md`).

## For students

AudioStudio has four tabs.

| Tab | What you make | How a game uses it |
|---|---|---|
| **Voices** | the 8 instruments of your soundtracks: voice 0 plays instrument 0, voice 1 instrument 1, … | soundtracks |
| **Sound effects** | short sounds with their own instrument, like *Jump* or *Coin* | the **play sound effect** block |
| **Soundtracks** | music on a grid: one row per voice, one column per step | the **play soundtrack** block |
| **Samples** | recorded sounds from WAV files (a drum, a voice) | instruments whose sound is *sample* |

An instrument has a **sound** (triangle, saw, pulse, noise or a sample), a filter
(**cutoff** and **resonance**), a **volume**, a **pan** (left or right) and an
**envelope**: **A**ttack, **D**ecay, **S**ustain, **R**elease. The picture of the
envelope changes while you move the sliders. **Try it** plays the instrument.

In the soundtrack grid, type a note in a step: `C4` is middle C, `F#5` is higher, a number
from 0 to 127 also works (60 is C4). Type `off` to end a note; leave a step empty to let the
note ring on. The arrow keys move around the grid, Enter goes down. **Solo** and **Mute**
change only what you hear in AudioStudio, never the game. **Escape** or **Stop sound**
silences everything.

AudioStudio saves by itself a moment after every change. If the same project is open in
two windows and both change the sound, the second save stops and asks you what to keep:
your sound as a copy (it is downloaded), the saved one, or yours over it. Nothing is lost
without you choosing.

## In Blocks

The **Sound** category has these blocks:

| Block | What it does | Generated C |
|---|---|---|
| `play sound effect Jump` | plays the sound effect | `prg32_audio_note(voice, instrument, note, volume, ms);` |
| `play soundtrack Theme` | starts the soundtrack | `prg32_audio_play_track(track);` |
| `stop soundtrack` | stops it | `prg32_audio_stop_track();` |
| `stop all sounds` | silences every voice | `prg32_audio_stop_all();` |

The names are turned into fixed numbers: sound effect *k* in the list is instrument
`8 + k`, soundtrack *k* is track *k*. The card **What the code says** at the bottom of
AudioStudio shows the exact lines, and the generated C and assembly say which sound each
number is. If a block names a sound that is not in AudioStudio (it was renamed or deleted),
the code generator warns you and leaves the block out; it never guesses another sound.

## For teachers

- One AudioStudio document per project, saved as the project's asset of kind
  `audio_studio` with a version (ADR-0017 rules: `expected_version`, `409` on conflict,
  quotas). Samples are artifacts of kind `audio_sample` (8-bit, 22050 Hz, at most
  256 KiB each), owned by the project's owner.
- Building a cartridge packs the document into the PRG32 audio block (`AUD0`) and passes it
  to the PRG32 toolchain (`--audio-block`). The same document and samples always give the
  same bytes; the build records the block's SHA-256 (`audio_block_sha256`) and puts the
  document in the bundle as `source/audio.json`.
- The project archive and **Make my copy** carry the samples (`audio/samples/*.u8`), so a
  copy owns its own sounds. Export/Import moves the sound alone between projects.
- A teacher supervising a class can listen but not change a student's sound. A shared
  starter project's sound is read-only for students until they make their copy.
- Uploaded sound is only read as numbers: WAV files are decoded (uncompressed 8- or 16-bit,
  mono or stereo, at most 8 MB and 30 s) and converted; nothing uploaded is ever run.

## The API

```text
GET  /audio-studio/<project_id>                 the page
GET  /api/projects/<id>/audio                   {document, version, asset_id, missing_samples, ids}
PUT  /api/projects/<id>/audio                   {document, expected_version}  -> saved, or 409 audio_version_conflict
POST /api/projects/<id>/audio/preview           {document?, muted?} -> the AUD0 block (bytes)
POST /api/projects/<id>/audio/samples           WAV file in "file", optional "name" -> the sample
GET  /api/projects/<id>/audio/export            the document with its sounds
POST /api/projects/<id>/audio/import            {export, expected_version}
```

The document format is described at the top of `prg32_construction_kit/audio_studio.py`.

## How it is checked

| Check | Where |
|---|---|
| Documents validated with reasons; fixed instrument and track numbers; looping and muted soundtracks; deterministic packing; WAV conversion; export/import | `tests/test_audio_studio.py` |
| Saving with versions and conflicts, ownership and supervision, quotas, preview, samples (missing, foreign, bad files), archive and copy with samples, old databases | `tests/test_audio_studio.py` |
| Generated C and assembly use the document's numbers; the cartridge build gets the audio block, byte-identical from the same inputs | `tests/test_audio_studio.py` |
| The page in a real browser: preview through the engine, keyboard grid, save, reload, export, import, conflict choices, accessibility (axe), no CSP violation | `tests/test_audio_browser.py` |
