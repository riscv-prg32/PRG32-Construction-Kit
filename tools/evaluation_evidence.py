"""Run the PRG32 evaluation protocol on a real target through the kit's own Evaluate API, and keep it all.

    python3 tools/evaluation_evidence.py --qemu-firmware data/qemu-firmware --slot cart0 --out docs/evidence/evaluate/DATE-qemu
    python3 tools/evaluation_evidence.py --prg32qt http://127.0.0.1:8080 --slot cart3 --out docs/evidence/evaluate/DATE-prg32qt
    python3 tools/evaluation_evidence.py --console http://192.168.4.1 --slot cart7 --out docs/evidence/evaluate/DATE-console

A fresh kit (its own temporary data folder) builds the protocol's cartridge from
examples/evaluation/prg32_evaluation.c with the real PRG32 toolchain, looks at the target and
runs the protocol (default 1 warm-up and 5 measured runs) through the same API routes as the
Evaluate page. The folder gets the dataset (JSON and CSV), the chart of every metric (SVG and
PDF) and ``record.json``: the checks, the cartridge's SHA-256, the target's identity, the kit and
SDK commits, the host computer (for emulators) and what the numbers are evidence of.

    python3 tools/evaluation_evidence.py --compare DIR DIR ... --out docs/evidence/evaluate/DATE-comparison

draws the recorded datasets on one chart per metric (only those with the same protocol and
cartridge).
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import platform
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))


def host() -> dict:
    """The computer an emulator ran on (its times depend on it)."""
    return {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "processor": platform.processor(), "python": platform.python_version(), "cpus": os.cpu_count()}


def compare(directories: list[Path], out: Path) -> int:
    from prg32_construction_kit import evaluation

    datasets = [json.loads((folder / "dataset.json").read_text()) for folder in directories]
    keep, left_out = evaluation.comparable(datasets)
    out.mkdir(parents=True, exist_ok=True)
    for metric in evaluation.protocol()["metrics"]:
        for kind in ("svg", "pdf"):
            (out / f"{metric['name']}.{kind}").write_bytes(evaluation.chart_bytes(datasets, metric["name"], kind))
    (out / "comparison.csv").write_bytes(evaluation.csv_of(keep))
    (out / "comparison.json").write_text(json.dumps({
        "compared": [{key: dataset["about"][key] for key in ("evaluation_id", "target_kind", "target_name", "evidence",
                                                             "cartridge_sha256", "firmware_version")} for dataset in keep],
        "left_out": left_out, "sources": [str(folder.relative_to(ROOT)) if folder.is_relative_to(ROOT) else str(folder)
                                          for folder in directories]}, indent=2) + "\n")
    print(f"compared {len(keep)} evaluation(s), left out {len(left_out)}: {out}")
    return 0 if keep and not left_out else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--console")
    where.add_argument("--prg32qt")
    where.add_argument("--qemu-firmware", type=Path)
    where.add_argument("--compare", type=Path, nargs="+")
    parser.add_argument("--slot")
    parser.add_argument("--repetitions", type=int, default=5)
    parser.add_argument("--warm-up", type=int, default=1)
    parser.add_argument("--notes", default="")
    parser.add_argument("--keep-data", type=Path, help="keep the kit's data folder here (logs of each run) instead of a temporary one")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.compare:
        return compare([folder.resolve() for folder in args.compare], args.out)
    if not args.slot:
        parser.error("--slot is required: what is in it is replaced")
    from deploy_evidence import commit, make_kit
    from prg32_construction_kit import deploy, evaluation

    checks: list[dict] = []

    def check(name: str, ok: bool, detail: object = "") -> bool:
        checks.append({"check": name, "ok": bool(ok), "detail": "" if ok else str(detail)[:500]})
        print(("ok    " if ok else "FAIL  ") + name + ("" if ok else f": {detail}"), flush=True)
        return bool(ok)

    args.out.mkdir(parents=True, exist_ok=True)
    kind = "prg32" if args.console else "prg32qt" if args.prg32qt else "qemu"
    item, dataset = {}, None
    with tempfile.TemporaryDirectory() as temp:
        data = Path(temp)
        if args.keep_data:
            args.keep_data.mkdir(parents=True, exist_ok=True)
            data = args.keep_data
        app, client = make_kit(data, args.qemu_firmware.resolve() if args.qemu_firmware else None)
        if kind == "qemu":
            target = next((entry for entry in client.get("/api/deploy/targets").get_json() if entry["id"] == "qemu"), None)
        else:
            target = client.post("/api/admin/deploy_targets", json={
                "name": "PRG32 console" if kind == "prg32" else "PRG32-QT", "kind": kind,
                "address": args.console or args.prg32qt}).get_json()
        if not check("the target is there", bool(target and target.get("id")), target):
            return 1
        the_protocol = client.get("/api/evaluation/protocol").get_json()
        project = client.post("/api/projects", json={"title": the_protocol["cartridge"]["title"], "game_json": {
            "source_mode": "c", "source_c": the_protocol["cartridge"]["source_text"],
            "required_features": the_protocol["cartridge"]["required_features"]}}).get_json()
        packaged = client.post(f"/api/projects/{project['id']}/package", json={}).get_json()
        cartridges = {entry["metadata"]["architecture"]: entry for entry in packaged.get("cartridge_artifacts", [])}
        if not check("the toolchain built the protocol's cartridge", bool(cartridges), packaged.get("build", {}).get("log", "")[-500:]):
            return 1
        cartridge = cartridges["esp32c6" if kind == "prg32" else "qemu"]
        probe = client.post(f"/api/deploy/targets/{target['id']}/probe", json={"artifact_id": cartridge["id"]}).get_json()
        seen = next((slot for slot in probe.get("slots", []) if slot["slot"] == args.slot), None)
        if not check(f"the target has {args.slot} and accepts the cartridge",
                     seen is not None and not seen.get("problems") and not probe.get("abi_problems"), probe):
            return 1
        answer = client.post("/api/evaluations", json={
            "artifact_id": cartridge["id"], "target": target["id"], "slot": args.slot, "confirm": True,
            "repetitions": args.repetitions, "warm_up": args.warm_up,
            "expect": {"fingerprint": probe["fingerprint"], "slot_content": deploy.slot_content(seen)}})
        item = client.get(f"/api/evaluations/{answer.get_json()['id']}").get_json()
        check("the evaluation completed", item["status"] == "complete", item.get("result"))
        runs = item["result"].get("runs", [])
        check("every run gave a result", all(run["status"] == "ok" for run in runs) and len(runs) == args.repetitions + args.warm_up,
              runs)
        dataset = client.get(f"/api/evaluations/{item['id']}/dataset.json").get_json()
        measured = [row for row in dataset["rows"] if row["role"] == "measured"]
        cases = len(the_protocol["cartridge"]["cases"])
        check("each measured run has a value for each case and metric",
              len(measured) == args.repetitions * cases * len(the_protocol["metrics"]), len(measured))
        check("the dataset names the cartridge that ran", dataset["about"]["cartridge_sha256"] == cartridge["metadata"]["sha256"])
        (args.out / "dataset.json").write_bytes(client.get(f"/api/evaluations/{item['id']}/dataset.json").data)
        (args.out / "dataset.csv").write_bytes(client.get(f"/api/evaluations/{item['id']}/dataset.csv").data)
        for metric in the_protocol["metrics"]:
            for chart in ("svg", "pdf"):
                served = client.get(f"/api/evaluations/{item['id']}/chart.{chart}?metric={metric['name']}").data
                (args.out / f"{metric['name']}.{chart}").write_bytes(served)
        again = evaluation.chart_bytes([json.loads((args.out / "dataset.json").read_text())], "frame_us_mean", "svg")
        check("the chart is made again from the saved dataset, byte for byte", again == (args.out / "frame_us_mean.svg").read_bytes())
    sdk = Path(os.environ.get("PRG32_SOURCE") or ROOT.parent / "PRG32")
    record = {
        "tool": "tools/evaluation_evidence.py",
        "date": datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat(),
        "kit_commit": commit(ROOT), "prg32_sdk_commit": commit(sdk), "protocol": "prg32-evaluation-protocol-1",
        "target_kind": kind, "evidence": deploy.EVIDENCE[kind], "physical_device": kind == "prg32",
        "address": args.console or args.prg32qt or "qemu", "slot": args.slot,
        "repetitions": args.repetitions, "warm_up": args.warm_up, "host": host() if kind != "prg32" else None,
        "target": (dataset or {}).get("about", {}).get("target"), "cartridge_sha256": (dataset or {}).get("about", {}).get("cartridge_sha256"),
        "files": {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(args.out.iterdir())
                  if path.name != "record.json"},
        "notes": args.notes, "checks": checks, "passed": all(row["ok"] for row in checks),
    }
    (args.out / "record.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(f"{'PASS' if record['passed'] else 'FAIL'}: {args.out / 'record.json'}")
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
