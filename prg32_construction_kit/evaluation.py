"""Evaluate: run the PRG32 performance protocol on a target and keep every measurement (EVAL-01).

The protocol is ``contracts/prg32-evaluation-protocol-1.json``: one fixed cartridge
(examples/evaluation/prg32_evaluation.c, built by the kit, its SHA-256 recorded), sent to a
target with Deploy's checks (deploy.check_and_upload), then started again for each run: first
the warm-up runs, then the measured ones. After each run the performance broker's summary is
read from the target, and every number in it becomes one row of the dataset, with its unit,
the run, the target and the cartridge. A run that gives no result is kept as a failed row.

From the dataset alone come the statistics (mean, standard deviation, 95 % Student t interval,
median, range; over the measured runs only), the CSV and JSON downloads and the charts
(charts.py): nothing is computed from anything else, so the same dataset always gives the same
numbers and the same chart bytes, also offline (tools/evaluation_charts.py).

Runs on different targets are compared only when they used the same protocol version and a
cartridge with the same SHA-256. Every answer says what kind of target it was: emulator times
are not console times.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import statistics
import threading
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column

from . import charts, deploy
from .db import db, get_resource, new_id, utcnow
from .messages import body as message_body, fields as message_fields, text as say

bp = Blueprint("evaluation", __name__)

ROOT = Path(__file__).resolve().parent.parent
PROTOCOL_FILE = ROOT / "contracts" / "prg32-evaluation-protocol-1.json"
RUNNING = ("queued", "checking", "uploading", "measuring")
FINAL = ("complete", "refused", "failed", "cancelled")
RUN_TIMEOUT = 240.0           # seconds for one run's result
# Two-sided 95 % Student t critical values, 1 to 30 degrees of freedom (beyond: the normal 1.960).
T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131,
       2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)


def protocol() -> dict[str, Any]:
    return json.loads(PROTOCOL_FILE.read_text())


def metric_named(name: str) -> dict[str, str] | None:
    return next((item for item in protocol()["metrics"] if item["name"] == name), None)


class Evaluation(db.Model):
    """One evaluation: where it ran, how, its progress and log; the dataset itself is a file."""
    __tablename__ = "evaluations"
    id: Mapped[str] = mapped_column(db.Text, primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(db.Integer, index=True)
    project_id: Mapped[str | None] = mapped_column(db.Text)
    artifact_id: Mapped[str] = mapped_column(db.Text, nullable=False)
    target: Mapped[str] = mapped_column(db.Text, nullable=False)
    target_kind: Mapped[str] = mapped_column(db.Text, nullable=False)
    target_name: Mapped[str] = mapped_column(db.Text, nullable=False, default="")
    slot: Mapped[str] = mapped_column(db.Text, nullable=False)
    repetitions: Mapped[int] = mapped_column(db.Integer, nullable=False)
    warm_up: Mapped[int] = mapped_column(db.Integer, nullable=False)
    status: Mapped[str] = mapped_column(db.Text, nullable=False, default="queued")
    progress: Mapped[int] = mapped_column(db.Integer, nullable=False, default=0)
    cancel_requested: Mapped[bool] = mapped_column(db.Boolean, nullable=False, default=False)
    log: Mapped[str] = mapped_column(db.Text, nullable=False, default="[]")
    result: Mapped[str] = mapped_column(db.Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)
    updated_at: Mapped[str] = mapped_column(db.Text, nullable=False, default=utcnow)


# --- statistics ------------------------------------------------------------------------

def describe(values: list[float]) -> dict[str, Any]:
    """n, mean, sd, sem, the 95 % t interval, median, min, max and cv of measured values."""
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": None, "sd": None, "sem": None, "ci95_low": None, "ci95_high": None,
                "median": None, "min": None, "max": None, "cv": None}
    mean = statistics.fmean(values)
    sd = statistics.stdev(values) if n > 1 else None
    sem = sd / math.sqrt(n) if sd is not None else None
    half = (T95[n - 2] if n - 1 <= len(T95) else 1.960) * sem if sem is not None else None
    return {"n": n, "mean": mean, "sd": sd, "sem": sem,
            "ci95_low": mean - half if half is not None else None, "ci95_high": mean + half if half is not None else None,
            "median": statistics.median(values), "min": min(values), "max": max(values),
            "cv": sd / mean if sd is not None and mean else None}


def summary(dataset: dict[str, Any], metric: str) -> dict[str, dict[str, Any]]:
    """Per case: the measured values of ``metric`` (in run order) and their description."""
    out: dict[str, dict[str, Any]] = {}
    for case in [item["name"] for item in dataset["protocol"]["cases"]]:
        values = [row["value"] for row in dataset["rows"]
                  if row["case"] == case and row["metric"] == metric and row["role"] == "measured"]
        out[case] = {"values": values, **describe(values)}
    return out


# --- the dataset -----------------------------------------------------------------------

def rows_of_run(answer: dict[str, Any], repetition: int, role: str) -> list[dict[str, Any]]:
    """One row per case and metric of a broker result (schema 2, screen_summaries)."""
    rows = []
    for case in answer.get("screen_summaries") or []:
        for metric in protocol()["metrics"]:
            if isinstance(case.get(metric["name"]), (int, float)):
                rows.append({"repetition": repetition, "role": role, "run_id": str(answer.get("run_id") or ""),
                             "case": str(case.get("screen_name") or ""), "metric": metric["name"],
                             "value": float(case[metric["name"]]), "unit": metric["unit"]})
    return rows


def dataset_path(evaluation_id: str) -> Path:
    return Path(current_app.config["DATA_DIR"]) / "evaluations" / evaluation_id / "dataset.json"


def load_dataset(evaluation_id: str) -> dict[str, Any] | None:
    path = dataset_path(evaluation_id)
    return json.loads(path.read_text()) if path.is_file() else None


def csv_of(datasets: list[dict[str, Any]]) -> bytes:
    """Every row of the datasets; numbers with a dot and no grouping, whatever the reader's language."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    columns = protocol()["dataset"]["csv_columns"]
    writer.writerow(columns)
    for dataset in datasets:
        about = dataset["about"]
        for row in dataset["rows"]:
            value = "" if row.get("value") is None else repr(float(row["value"]))
            writer.writerow([about["evaluation_id"], about["target_kind"], about["target_name"], about["evidence"],
                             about["firmware_version"], about["cartridge_sha256"], row["repetition"], row["role"],
                             row.get("run_id", ""), row.get("case", ""), row.get("metric", ""), value, row.get("unit", "")])
    return out.getvalue().encode("utf-8")


# --- charts -------------------------------------------------------------------------------

def comparable(datasets: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The datasets that can share a chart with the first one, and why the others cannot."""
    if not datasets:
        return [], []
    first = datasets[0]["about"]
    keep, left_out = [datasets[0]], []
    for dataset in datasets[1:]:
        about = dataset["about"]
        if about["protocol_version"] != first["protocol_version"]:
            left_out.append({"evaluation_id": about["evaluation_id"], "code": "protocol", "reason": "another protocol version"})
        elif about["cartridge_sha256"] != first["cartridge_sha256"]:
            left_out.append({"evaluation_id": about["evaluation_id"], "code": "cartridge",
                             "reason": "another cartridge (different SHA-256)"})
        else:
            keep.append(dataset)
    return keep, left_out


def chart(datasets: list[dict[str, Any]], metric_name: str) -> tuple[charts.Canvas, str, str, dict[str, Any]]:
    """The bar chart of ``metric_name`` for comparable datasets, with its title, description and provenance."""
    metric = metric_named(metric_name) or metric_named("frame_us_mean")
    keep, left_out = comparable(datasets)
    cases = [item["name"] for item in keep[0]["protocol"]["cases"]] if keep else []
    series = [{"name": dataset["about"]["target_name"], "evidence": dataset["about"]["evidence"],
               "cases": summary(dataset, metric["name"])} for dataset in keep]
    sha = keep[0]["about"]["cartridge_sha256"] if keep else ""
    counts = ", ".join(f"{item['name']}: n={max([case['n'] for case in item['cases'].values()] or [0])}" for item in series)
    title = f"PRG32 evaluation: {metric['label']}"
    caption = [f"Protocol prg32-evaluation-protocol-{keep[0]['about']['protocol_version'] if keep else '?'}; cartridge SHA-256 {sha[:16]}.",
               f"Measured runs per target: {counts}; warm-up runs excluded.",
               "Error bars: two-sided 95% Student t interval of the mean of the runs. Every measured run is a point.",
               "Emulator times (PRG32-QT, QEMU) depend on the host computer: they are not PRG32 console times."]
    description = (f"{title}, in {metric['unit']}, for the cases {', '.join(cases)}. " + " ".join(
        f"{item['name']} ({item['evidence']}): " + "; ".join(
            f"{case} mean {data['mean']:.1f}" + (f" (95% CI {data['ci95_low']:.1f} to {data['ci95_high']:.1f})"
                                                 if data["ci95_low"] is not None else "") + f", n={data['n']}"
            if data["n"] else f"{case} no data" for case, data in item["cases"].items()) + "."
        for item in series))
    provenance = {"protocol": f"prg32-evaluation-protocol-{keep[0]['about']['protocol_version']}" if keep else None,
                  "metric": metric["name"], "unit": metric["unit"], "cartridge_sha256": sha,
                  "evaluations": [{key: dataset["about"][key] for key in ("evaluation_id", "target_kind", "target_name",
                                                                         "evidence", "firmware_version", "finished_at",
                                                                         "kit_version")} for dataset in keep],
                  "left_out": left_out, "made_by": "prg32_construction_kit/charts.py"}
    return charts.bar_chart(series, cases, metric, title, caption, provenance), title, description, provenance


def chart_bytes(datasets: list[dict[str, Any]], metric_name: str, kind: str) -> bytes:
    canvas, title, description, provenance = chart(datasets, metric_name)
    return canvas.svg(title, description, provenance) if kind == "svg" else canvas.pdf(title, description, provenance)


# --- one evaluation, step by step ---------------------------------------------------------

def evaluation_cartridge(artifact_id: str, principal) -> tuple[dict[str, Any], bytes]:
    """Deploy's cartridge checks, and: it is the protocol's cartridge, built from its exact source."""
    artifact, data = deploy.cartridge_for(artifact_id, principal)
    project = get_resource("projects", str(artifact.get("project_id") or ""))
    source = ((project or {}).get("game_json") or {}).get("source_c") or ""
    if hashlib.sha256(source.encode("utf-8")).hexdigest() != protocol()["cartridge"]["source_sha256"]:
        raise deploy.DeployProblem("not_the_protocol_cartridge", say("evaluate", "Evaluate runs only the PRG32 Evaluation "
                                   "cartridge, built from the protocol's own source: press Make the evaluation cartridge."))
    return artifact, data


def run_evaluation(evaluation_id: str, target: dict[str, Any], data: bytes, expect: dict[str, Any]) -> None:
    """Send the cartridge (Deploy's checks), then warm-up and measured runs; the dataset is written as it grows."""
    job = deploy.Job(evaluation_id, Evaluation)
    row = db.session.get(Evaluation, evaluation_id)
    slot, total = row.slot, row.warm_up + row.repetitions
    work = Path(current_app.config["DATA_DIR"]) / "evaluations" / evaluation_id
    work.mkdir(parents=True, exist_ok=True)
    header = deploy.cartridge_header(data)
    the_protocol = protocol()
    result: dict[str, Any] = {"evidence": deploy.EVIDENCE[target["kind"]], "physical_device": target["kind"] == "prg32",
                              "cartridge": header, "protocol_version": the_protocol["version"], "runs": []}
    dataset: dict[str, Any] = {"format": the_protocol["dataset"]["format"], "protocol": the_protocol["cartridge"] | {
        "version": the_protocol["version"], "timing_source": the_protocol["timing_source"][target["kind"]],
        "retrieval": the_protocol["retrieval"][target["kind"]], "repetition": the_protocol["repetition"][target["kind"]],
        "granularity": the_protocol["granularity"], "caveat": the_protocol["caveat"]}, "rows": []}
    adapter = None

    def wait(seconds: float) -> None:
        if job.cancelled():
            raise deploy.Cancelled()
        import time

        time.sleep(seconds)

    def save(finished: bool = False) -> None:
        identity = (result.get("target") or {}).get("identity") or {}
        from . import KIT_VERSION

        dataset["about"] = {"evaluation_id": evaluation_id, "protocol_version": the_protocol["version"],
                            "target_kind": target["kind"], "target_name": target["name"],
                            "evidence": deploy.EVIDENCE[target["kind"]], "physical_device": target["kind"] == "prg32",
                            "firmware_version": identity.get("firmware_version", ""), "host": identity.get("host", ""),
                            "target": result.get("target"), "cartridge_sha256": header["sha256"],
                            "cartridge_bytes": header["bytes"], "repetitions": row.repetitions, "warm_up": row.warm_up,
                            "started_at": row.created_at, "finished_at": utcnow() if finished else None,
                            "kit_version": KIT_VERSION, "runs": result["runs"]}
        dataset_path(evaluation_id).write_text(json.dumps(dataset, indent=1, sort_keys=True) + "\n")

    try:
        job.step("checking", 5, say("deploy", "Asking {target} who it is", target=target["name"]))
        adapter = deploy.adapter_for(target, work)
        deploy.check_and_upload(job, adapter, target, data, slot, expect, result, wait)
        for number in range(1, total + 1):
            role = "warm-up" if number <= row.warm_up else "measured"
            job.step("measuring", 10 + int(85 * (number - 1) / total),
                     say("evaluate", "Run {number} of {total} (warm-up)", number=number, total=total) if role == "warm-up"
                     else say("evaluate", "Run {number} of {total} (measured)", number=number, total=total))
            previous = (adapter.performance() or {}).get("run_id")
            try:
                if target["kind"] == "qemu" and number > 1:
                    adapter.restart()
                adapter.launch(slot)
                answer = adapter.collect_performance(previous, wait, RUN_TIMEOUT)
            except (deploy.DeployProblem, ConnectionError) as problem:
                if isinstance(problem, deploy.DeployProblem) and problem.code == "target_busy":
                    raise
                result["runs"].append({"repetition": number, "role": role, "status": "failed", "reason": str(problem)[:300]})
                dataset["rows"].append({"repetition": number, "role": "failed", "run_id": "", "case": "", "metric": "",
                                        "value": None, "unit": ""})
                job.say(say("evaluate", "Run {number} gave no result: {reason}", number=number, reason=str(problem)[:200]))
                save()
                continue
            rows = rows_of_run(answer, number, role)
            dataset["rows"].extend(rows)
            result["runs"].append({"repetition": number, "role": role, "status": "ok", "run_id": answer.get("run_id"),
                                   "duration_us": answer.get("duration_us"), "target": answer.get("target"),
                                   "display_backend": answer.get("display_backend"), "memory": answer.get("memory"),
                                   "cases": len(answer.get("screen_summaries") or [])})
            save()
        measured = [run for run in result["runs"] if run["role"] == "measured" and run["status"] == "ok"]
        save(finished=True)
        status = "complete" if measured else "failed"
        if not measured:
            result.update({"code": "no_result", "error": str(say("evaluate", "No measured run gave a result."))})
        job.say(say("evaluate", "{count} measured runs on {target} ({evidence})", count=len(measured),
                    target=target["name"], evidence=deploy.EVIDENCE[target["kind"]]))
        job.finish(status, result)
    except deploy.Cancelled:
        save(finished=True)
        job.say(say("deploy", "Cancelled"))
        job.finish("cancelled", result)
    except deploy.DeployProblem as problem:
        result.update({"code": problem.code, "error": str(problem), **message_fields(problem), "left": str(problem.left)})
        job.say(problem.args[0])
        job.finish(problem.final, result)
    except Exception as error:   # noqa: BLE001 - the record must end, whatever happened
        current_app.logger.exception("Evaluation %s failed", evaluation_id)
        result.update({"code": "failed", "error": str(error)[:300]})
        job.finish("failed", result)
    finally:
        if adapter is not None:
            adapter.close()


def as_dict(item: Evaluation) -> dict[str, Any]:
    return {"id": item.id, "project_id": item.project_id, "artifact_id": item.artifact_id, "target": item.target,
            "target_kind": item.target_kind, "target_name": item.target_name, "slot": item.slot,
            "repetitions": item.repetitions, "warm_up": item.warm_up, "status": item.status, "progress": item.progress,
            "cancel_requested": item.cancel_requested, "log": json.loads(item.log or "[]"),
            "result": json.loads(item.result or "{}"), "evidence": deploy.EVIDENCE[item.target_kind],
            "physical_device": item.target_kind == "prg32", "created_at": item.created_at, "updated_at": item.updated_at}


# --- the API --------------------------------------------------------------------------------

def _principal():
    from .auth import current_principal

    return current_principal()


def _own(evaluation_id: str) -> Evaluation | None:
    principal = _principal()
    item = db.session.get(Evaluation, evaluation_id)
    if item is None or not (principal.is_admin or item.owner_id == principal.id):
        return None
    return item


def _not_found():
    return jsonify({**message_body(say("evaluate", "Evaluation not found."))}), 404


def _bounded(payload: dict[str, Any], key: str, limits: dict[str, int]) -> int | None:
    value = payload.get(key, limits["default"])
    if isinstance(value, bool) or not isinstance(value, int) or not limits["min"] <= value <= limits["max"]:
        return None
    return value


@bp.get("/evaluate")
def evaluate_page():
    from flask import render_template

    from .routes import open_project

    the_protocol = protocol()
    return render_template("evaluate.html", nav_project=open_project(request.args.get("project")), protocol=the_protocol,
                           units={metric["name"]: metric["unit"] for metric in the_protocol["metrics"]})


@bp.get("/api/evaluation/protocol")
def api_protocol():
    """The protocol and its cartridge's source (the Evaluate page makes the project from it)."""
    the_protocol = protocol()
    return jsonify({**the_protocol, "cartridge": {**the_protocol["cartridge"],
                                                 "source_text": (ROOT / the_protocol["cartridge"]["source"]).read_text()}})


@bp.get("/api/evaluations")
def api_evaluations():
    principal = _principal()
    query = select(Evaluation).order_by(Evaluation.created_at.desc()).limit(50)
    if not principal.is_admin:
        query = query.where(Evaluation.owner_id == principal.id)
    items = [_settled(item) for item in db.session.scalars(query)]
    return jsonify([as_dict(item) for item in items])


def _settled(item: Evaluation) -> Evaluation:
    if item.status in RUNNING and deploy.interrupted(item):
        item.status, item.progress = "failed", 100
        result = json.loads(item.result or "{}")
        result.update({"code": "interrupted", "error": str(say("deploy", "The server stopped during this deployment."))})
        item.result = json.dumps(result, sort_keys=True)
        db.session.commit()
    return item


@bp.post("/api/evaluations")
def api_evaluate():
    """Start an evaluation: Deploy's {"artifact_id", "target", "slot", "expect", "confirm"} and
    {"repetitions", "warm_up"} within the protocol's bounds."""
    principal = _principal()
    payload = request.get_json(silent=True) or {}
    the_protocol = protocol()
    repetitions = _bounded(payload, "repetitions", the_protocol["repetitions"])
    warm_up = _bounded(payload, "warm_up", the_protocol["warm_up"])
    if repetitions is None or warm_up is None:
        return jsonify({**message_body(say("evaluate", "Runs: {low} to {high} measured, {warm_low} to {warm_high} warm-up.",
                                           low=the_protocol["repetitions"]["min"], high=the_protocol["repetitions"]["max"],
                                           warm_low=the_protocol["warm_up"]["min"], warm_high=the_protocol["warm_up"]["max"])),
                        "code": "bad_runs"}), 400
    target = deploy.target_named(str(payload.get("target") or ""))
    slot = str(payload.get("slot") or "")
    if target is None:
        return jsonify({**message_body(say("deploy", "Target not found.")), "code": "target_unknown"}), 404
    if not deploy.SLOT_NAME.match(slot):
        return jsonify({**message_body(say("deploy", "Choose the slot to use: nothing is replaced without a name.")),
                        "code": "slot_unknown"}), 400
    expect = payload.get("expect") if isinstance(payload.get("expect"), dict) else {}
    if payload.get("confirm") is not True or not expect.get("fingerprint") or not isinstance(expect.get("slot_content"), dict):
        return jsonify({**message_body(say("deploy", "Look at the target first, then confirm which slot to replace.")),
                        "code": "not_confirmed"}), 400
    try:
        artifact, data = evaluation_cartridge(str(payload.get("artifact_id") or ""), principal)
        architecture = (artifact.get("metadata") or {}).get("architecture")
        if architecture not in deploy.ARCHITECTURES[target["kind"]]:
            raise deploy.DeployProblem("wrong_architecture", say("deploy", "{target} runs {wanted} cartridges; this one is {architecture}.",
                                       target=target["name"], wanted=" or ".join(deploy.ARCHITECTURES[target["kind"]]),
                                       architecture=architecture or "?"))
    except deploy.DeployProblem as problem:
        return jsonify({**message_body(problem.args[0]), "code": problem.code}), 404 if problem.code == "not_found" else 409
    busy = [item for item in db.session.scalars(select(Evaluation).where(Evaluation.target == target["id"],
                                                                        Evaluation.status.in_(RUNNING)))
            if not deploy.interrupted(item)]
    busy += [item for item in db.session.scalars(select(deploy.Deployment).where(
        deploy.Deployment.target == target["id"], deploy.Deployment.status.in_(deploy.RUNNING))) if not deploy.interrupted(item)]
    if busy:
        return jsonify({**message_body(say("deploy", "Somebody is deploying to this target right now. Try again in a minute.")),
                        "code": "target_busy"}), 409
    item = Evaluation(id=new_id("eval"), owner_id=principal.id, project_id=artifact.get("project_id"),
                      artifact_id=artifact["id"], target=target["id"], target_kind=target["kind"], target_name=target["name"],
                      slot=slot, repetitions=repetitions, warm_up=warm_up)
    db.session.add(item)
    db.session.commit()
    app = current_app._get_current_object()

    def background():
        with app.app_context():
            run_evaluation(item.id, target, data, expect)

    if current_app.config.get("DEPLOY_INLINE"):
        background()
        db.session.expire_all()
    else:
        threading.Thread(target=background, name=f"evaluate-{item.id}", daemon=True).start()
    return jsonify(as_dict(db.session.get(Evaluation, item.id))), 202


@bp.get("/api/evaluations/<evaluation_id>")
def api_evaluation(evaluation_id: str):
    item = _own(evaluation_id)
    if item is None:
        return _not_found()
    answer = as_dict(_settled(item))
    dataset = load_dataset(evaluation_id)
    if dataset:
        metric = request.args.get("metric", "frame_us_mean")
        answer["statistics"] = {"metric": metric_named(metric) or metric_named("frame_us_mean"),
                                "cases": summary(dataset, metric if metric_named(metric) else "frame_us_mean")}
    return jsonify(answer)


@bp.post("/api/evaluations/<evaluation_id>/cancel")
def api_cancel(evaluation_id: str):
    item = _own(evaluation_id)
    if item is None:
        return _not_found()
    if item.status in RUNNING:
        item.cancel_requested = True
        db.session.commit()
    return jsonify(as_dict(item))


def _datasets(ids: list[str]) -> list[dict[str, Any]] | None:
    found = []
    for evaluation_id in ids[:6]:
        if _own(evaluation_id) is None:
            return None
        dataset = load_dataset(evaluation_id)
        if dataset is None:
            return None
        found.append(dataset)
    return found


def _download(datasets: list[dict[str, Any]], kind: str, name: str):
    metric = request.args.get("metric", "frame_us_mean")
    if kind == "json":
        body, mimetype = (json.dumps(datasets[0] if len(datasets) == 1 else {"datasets": datasets}, indent=1, sort_keys=True)
                          + "\n").encode(), "application/json"
    elif kind == "csv":
        body, mimetype = csv_of(datasets), "text/csv"
    else:
        body, mimetype = chart_bytes(datasets, metric, kind), "image/svg+xml" if kind == "svg" else "application/pdf"
    disposition = "inline" if kind == "svg" and request.args.get("inline") else "attachment"
    return Response(body, mimetype=mimetype, headers={"Content-Disposition": f'{disposition}; filename="{name}.{kind}"'})


@bp.get("/api/evaluations/<evaluation_id>/dataset.<kind>")
def api_dataset(evaluation_id: str, kind: str):
    datasets = _datasets([evaluation_id])
    if datasets is None or kind not in ("json", "csv"):
        return _not_found()
    return _download(datasets, kind, f"{evaluation_id}-dataset")


@bp.get("/api/evaluations/<evaluation_id>/chart.<kind>")
def api_chart(evaluation_id: str, kind: str):
    datasets = _datasets([evaluation_id])
    if datasets is None or kind not in ("svg", "pdf"):
        return _not_found()
    return _download(datasets, kind, f"{evaluation_id}-{request.args.get('metric', 'frame_us_mean')}")


@bp.get("/api/evaluations/compare.<kind>")
def api_compare(kind: str):
    """Several evaluations on one chart or in one file (?ids=a,b,c); the JSON says which could not be compared."""
    ids = [item for item in request.args.get("ids", "").split(",") if item]
    datasets = _datasets(ids)
    if not ids or datasets is None or kind not in ("json", "csv", "svg", "pdf"):
        return _not_found()
    if kind == "json":
        keep, left_out = comparable(datasets)
        metric = request.args.get("metric", "frame_us_mean")
        metric = metric if metric_named(metric) else "frame_us_mean"
        return jsonify({"metric": metric_named(metric), "left_out": left_out,
                        "targets": [{**{key: dataset["about"][key] for key in ("evaluation_id", "target_name", "target_kind",
                                                                               "evidence", "physical_device")},
                                     # A list, in the protocol's order of cases (a JSON object would be sorted).
                                     "cases": [{"case": case, **data} for case, data in summary(dataset, metric).items()]}
                                    for dataset in keep]})
    return _download(datasets, kind, "prg32-evaluation-comparison")


def delete_evaluations_of(user_id: int) -> int:
    """Erasure (privacy.erase_account): the person's evaluations and their datasets."""
    import shutil

    rows = db.session.scalars(select(Evaluation).where(Evaluation.owner_id == user_id)).all()
    for row in rows:
        shutil.rmtree(Path(current_app.config["DATA_DIR"]) / "evaluations" / row.id, ignore_errors=True)
        db.session.delete(row)
    db.session.commit()
    return len(rows)


def init_app(app) -> None:
    app.register_blueprint(bp)

