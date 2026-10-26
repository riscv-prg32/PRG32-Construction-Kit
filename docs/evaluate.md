# Evaluate: how fast is a PRG32?

**Evaluate** (in the menu of an open project) measures how fast a target runs the **PRG32
Evaluation** cartridge. The target can be the class's PRG32 console, PRG32-QT or QEMU on the
kit's server. Every target gets the same cartridge, built from the same source and with the
same bytes, and the same steps, repeated. Every number is kept: you can download it, check it
and draw it again.

> **Emulators are not consoles.** Times measured in PRG32-QT or QEMU depend on the computer that
> runs them. They are not the times of a PRG32 console, and a faster or slower emulator says
> nothing about the console. Compare emulators with emulators, and a console with a console.
> The page, the files and every chart say which kind each run was.

## For students and teachers

1. Press **Make the evaluation cartridge**. The kit makes a project called *PRG32 Evaluation*
   from the protocol's own source and compiles it. Its SHA-256 (a fingerprint of the bytes) is
   shown next to it.
2. Choose the **target**, press **Look at it**, choose a slot and confirm it, as in
   [Deploy](deploy.md). The cartridge replaces what is in that slot.
3. Choose how many **measured runs** (1 to 20, default 5) and **warm-up runs** (0 to 3,
   default 1), then press **Run the evaluation**. Each run starts the cartridge again. It draws
   five scenes ("cases") for 60 frames each, and the target's own clock times every frame.
   Warm-up runs are recorded but not counted.
4. When it is done you see, for each case:

| Column | Meaning |
| --- | --- |
| n | how many measured runs gave a value |
| Mean | the average of those values |
| SD | the standard deviation: how far the runs are from each other |
| 95% CI | the range where the true mean most likely is (95% Student t interval) |
| Median, Range | the middle value; the smallest and largest |

The chart shows the same numbers. Each bar is a mean and each black line its 95% interval, and
every measured run is a point, so nothing is hidden. Choose another **Measure** to see draw time,
present time, frames per second and so on.

**Compare** several evaluations, for example the same cartridge on QEMU and on PRG32-QT, by
ticking them under *Your evaluations*. Only evaluations of the same cartridge (same SHA-256) and
the same protocol version share a chart; any others are listed with the reason.

### What the five cases do

| Case | What it draws |
| --- | --- |
| clear-fill | clears the screen and fills large rectangles |
| text-overlay | lines of 8×8 text |
| sprite-storm | 36 moving sprite-sized rectangles |
| scrolling | scrolling pixels and stripes |
| mixed-gameplay | text, sprites and scrolling together |

Each frame has three parts, each timed: **update** (the game logic), **draw** (the scene) and
**present** (sending the picture to the screen). The cartridge's source is
[examples/evaluation/prg32_evaluation.c](../examples/evaluation/prg32_evaluation.c), with a
comment on every step.

## The protocol

[`contracts/prg32-evaluation-protocol-1.json`](../contracts/prg32-evaluation-protocol-1.json) is
version 1 of the protocol. It holds:

- the cartridge source and its SHA-256, the cases and their frame counts;
- the bounds on runs and warm-up runs;
- how each kind of target restarts the cartridge for a run, and how the result is read. A
  console and PRG32-QT are read with `GET /api/performance.json` every 2 seconds. QEMU is read
  once through its GDB stub, 30 seconds after the cartridge starts. The firmware is never
  stopped during the suite: a run still going at that moment is refused, and the next one waits
  longer;
- each target's timing source: the console's microsecond timer, PRG32-QT's clock (the host's
  time), QEMU's emulated timer (which follows the host's clock);
- the metrics and their units, and the statistics.

Anything that would change a number needs a new protocol version. Version 1 of the PRG32
performance broker (`prg32_metrics.h`) keeps one summary per case, not every frame. So a run
gives one value per case and metric, and the statistics are over runs.

## The files

| File | What it is |
| --- | --- |
| Raw data (CSV) | one row per run, case and metric: `evaluation_id, target_kind, target_name, evidence, firmware_version, cartridge_sha256, repetition, role, run_id, case, metric, value, unit`. `role` is `warm-up`, `measured` or `failed` (a run that gave no result is a row too). Numbers use a dot for decimals in every interface language |
| Raw data and provenance (JSON) | the same rows, plus the protocol, the target's identity and ABI, the cartridge, each run's details (run id, duration, memory) and the kit version |
| Chart (SVG, PDF) | the chart of the chosen measure. The SVG has a title, a description of every value and its provenance in `<metadata>`; the PDF has it in its document information |

Charts are made only from the dataset, and the same dataset always gives the same bytes. To make
them again offline, for example for a paper:

```bash
python3 tools/evaluation_charts.py dataset.json --metric frame_us_p95 --out charts/
```

Give several datasets to draw a comparison. The colours (Okabe-Ito) stay distinguishable with
colour-vision deficiencies, and each target also has its own point shape.

## Recorded runs

`tools/evaluation_evidence.py` runs the protocol on a real target through the kit's API and keeps
the dataset, the charts and a record (kit and SDK commits, the host computer for emulators):

```bash
python3 tools/evaluation_evidence.py --prg32qt http://127.0.0.1:8080 --slot cart3 --out docs/evidence/evaluate/DATE-prg32qt
```

See [evidence/evaluate/](evidence/evaluate/) for the recorded runs. No PRG32 console was
available, so there is no physical-device evaluation yet.
