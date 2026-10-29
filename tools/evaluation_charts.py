"""Make the charts of PRG32 evaluations again from their downloaded datasets, offline (EVAL-01).

    python3 tools/evaluation_charts.py dataset.json [more.json ...] --metric frame_us_mean --out DIR

One dataset gives that evaluation's chart; several give the comparison chart (only those with
the same protocol and cartridge are drawn together; the others are named). The files,
<metric>.svg and <metric>.pdf, are byte for byte the ones the kit serves for the same data:
the chart is made from the dataset only (prg32_construction_kit/charts.py).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("datasets", nargs="+", type=Path)
    parser.add_argument("--metric", default="frame_us_mean")
    parser.add_argument("--out", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    from prg32_construction_kit import evaluation

    if evaluation.metric_named(args.metric) is None:
        parser.error("unknown metric; one of: " + ", ".join(item["name"] for item in evaluation.protocol()["metrics"]))
    datasets = []
    for path in args.datasets:
        document = json.loads(path.read_text())
        datasets += document["datasets"] if "datasets" in document else [document]
    keep, left_out = evaluation.comparable(datasets)
    for item in left_out:
        print(f"left out {item['evaluation_id']}: {item['reason']}", file=sys.stderr)
    args.out.mkdir(parents=True, exist_ok=True)
    for kind in ("svg", "pdf"):
        (args.out / f"{args.metric}.{kind}").write_bytes(evaluation.chart_bytes(datasets, args.metric, kind))
    print(f"Wrote {args.out / (args.metric + '.svg')} and .pdf ({len(keep)} evaluation(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
