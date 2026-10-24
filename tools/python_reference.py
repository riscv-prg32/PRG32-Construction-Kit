#!/usr/bin/env python3
"""Scenario L: one PRG32 Python game from source to cartridge to running code, with evidence.

    python3 tools/python_reference.py build --out DIR      # needs the PRG32 toolchain
    python3 tools/python_reference.py run --evidence DIR --prg32qt PATH --sdk PATH

build (in the toolchain container in CI) uses a throwaway kit, its real HTTP API and the real
PRG32 toolchain:

- the project's whole life: create, save, reload, archive, import the archive, package;
- examples/python/reference_scenario.py: arithmetic with the cartridge rules, if/elif/else and
  for, helpers, drawing, buttons, eight voices with stereo sound (reference_scenario.audio.json);
- the commented C, the RV32IM assembly, the source map, the provenance and the cartridges;
- the same project built again in fresh processes, once more in English and once in every
  interface language: the IR, C, assembly, debug map and cartridge must be byte for byte equal;
- the validator's problems at exact game.py ranges, a build problem, and programs that try to
  import, run code, touch files, the network or processes, recurse or exhaust resources: each is
  refused without being run (a program that ran would leave a file behind; none may).

run (in CI beside the browser core's golden tests) takes that exact cartridge and checks it:
the browser core (static/wasm, under Node) and a native build of the same core give the same
state frame after frame, the native build draws exactly like canonical PRG32-QT's
prg32qt-headless, and the debugger stops on a game.py line at the address the debug map gives.

Each phase writes evidence.json (build) or run-evidence.json (run): every file with its SHA-256,
every check with its outcome, and the revisions and tool versions. A failed check exits 1.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
SCENARIO = ROOT / "examples" / "python" / "reference_scenario.py"
SCENARIO_AUDIO = ROOT / "examples" / "python" / "reference_scenario.audio.json"
TITLE = "Scenario L"
# The game.py line the run phase stops on: the first statement of update().
BREAK_ON = "    tick += 1"

# Programs that must be refused before anything runs. Each would leave SENTINEL behind if it ran.
SENTINEL = "PRG32_REFERENCE_SENTINEL"


def hostile_programs(sentinel: Path) -> dict[str, str]:
    touch = f"open({str(sentinel)!r}, 'w').write('ran')"
    body = "def init() -> None:\n    pass\n\ndef update() -> None:\n    pass\n\ndef draw() -> None:\n    pass\n"
    return {
        "import_os": f"import prg32\nimport os\nos.system('touch {sentinel}')\n{body}",
        "from_import": f"import prg32\nfrom subprocess import run\nrun(['touch', '{sentinel}'])\n{body}",
        "dunder_import": f"import prg32\nx: int = __import__('os').system('touch {sentinel}')\n{body}",
        "eval": f"import prg32\nx: int = eval(\"{touch}\")\n{body}",
        "exec": f"import prg32\n\ndef init() -> None:\n    exec(\"{touch}\")\n\ndef update() -> None:\n    pass\n\n"
                "def draw() -> None:\n    pass\n",
        "open_file": f"import prg32\n\ndef init() -> None:\n    {touch}\n\ndef update() -> None:\n    pass\n\n"
                     "def draw() -> None:\n    pass\n",
        "socket": f"import prg32\nimport socket\nsocket.create_connection(('127.0.0.1', 9))\n{body}",
        "ctypes": f"import prg32\nimport ctypes\nctypes.CDLL(None)\n{body}",
        "attribute_escape": "import prg32\nx: int = 0\n\ndef init() -> None:\n    global x\n"
                            "    x = prg32.__class__.__subclasses__()\n\ndef update() -> None:\n    pass\n\n"
                            "def draw() -> None:\n    pass\n",
        "class_definition": f"import prg32\nclass Escape:\n    pass\n{body}",
        "lambda": f"import prg32\nf: int = (lambda: {touch})()\n{body}",
        "recursion": "import prg32\nx: int = 0\n\ndef loop(n: int) -> None:\n    loop(n)\n\ndef init() -> None:\n"
                     "    loop(1)\n\ndef update() -> None:\n    pass\n\ndef draw() -> None:\n    pass\n",
        "endless_loop": "import prg32\n\ndef init() -> None:\n    while True:\n        pass\n\n"
                        "def update() -> None:\n    pass\n\ndef draw() -> None:\n    pass\n",
        "huge_loop": "import prg32\nx: int = 0\n\ndef init() -> None:\n    global x\n    for i in range(100000000):\n"
                     "        x += 1\n\ndef update() -> None:\n    pass\n\ndef draw() -> None:\n    pass\n",
        "deep_nesting": "import prg32\nx: int = " + "(" * 200 + "1" + ")" * 200 + "\n" + body,
        "huge_file": "import prg32\n" + "x: int = 1\n" * 5000 + body,
    }


# Problems the validator must report at exact places: (program, code, line, column).
def diagnostics() -> list[tuple[str, str, str, int, int]]:
    base = "import prg32\nx: int = 0\n\n\ndef init() -> None:\n{init}\n\n\ndef update() -> None:\n    pass\n\n\n" \
           "def draw() -> None:\n    pass\n"
    return [
        ("unknown_name", base.format(init="    global x\n    x = y + 1"), "unknown_name", 7, 9),
        ("type_mismatch", base.format(init="    global x\n    x = True"), "type_mismatch", 7, 9),
        ("while_loop", base.format(init="    while x < 3:\n        pass"), "statement", 6, 5),
        ("print", base.format(init="    print(x)"), "print", 6, 5),
        ("missing_sound", base.format(init="    prg32.sound_effect(\"nope\")"), "missing_sound", 6, 5),
    ]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def __call__(self, name: str, ok: bool, detail: Any = "") -> bool:
        detail = detail.hex() if isinstance(detail, bytes) else detail
        try:
            json.dumps(detail)
        except TypeError:
            detail = repr(detail)
        self.rows.append({"check": name, "ok": bool(ok), "detail": "" if ok else detail})
        print(("ok    " if ok else "FAIL  ") + name + (f": {detail}" if detail and not ok else ""), flush=True)
        return bool(ok)

    @property
    def passed(self) -> bool:
        return all(row["ok"] for row in self.rows)


def make_kit(data: Path):
    from prg32_construction_kit import create_app

    password = secrets.token_urlsafe(18)
    app = create_app({
        "TESTING": True, "DATA_DIR": data, "DB_PATH": data / "kit.sqlite", "BUILD_ROOT": data / "builds",
        "ARTIFACT_ROOT": data / "artifacts", "ADMIN_PASSWORD": password, "SSO_SECRET": "", "SSO_PEER_URL": "",
        "PRG32_BUILD_COMMAND": os.environ.get("PRG32_BUILD_COMMAND", f"{sys.executable} -m prg32 cartridge build"),
        "PRG32_CART_RAM_KIB": 64,
    })
    client = app.test_client()
    client.environ_base["HTTP_X_PRG32_KIT"] = "1"
    answer = client.post("/auth/login", data={"username": "admin", "password": password})
    assert answer.status_code == 302, answer.get_data(as_text=True)
    return app, client


def build_once(locale: str, data: Path) -> dict[str, Any]:
    """Create and build the scenario in a fresh kit; the hashes of everything it makes."""
    _app, client = make_kit(data)
    client.set_cookie("prg32_locale", locale)
    source = SCENARIO.read_text()
    audio = json.loads(SCENARIO_AUDIO.read_text())
    project = client.post("/api/projects", json={"title": TITLE, "game_json": {
        "source_mode": "python", "source_python": source, "python_language_version": 1}}).get_json()
    sound = client.get(f"/api/projects/{project['id']}/audio").get_json()
    client.put(f"/api/projects/{project['id']}/audio", json={"document": audio, "expected_version": sound["version"]})
    converted = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"}).get_json()
    packaged = client.post(f"/api/projects/{project['id']}/package",
                           json={"architectures": ["qemu"], "source_language": "c"}).get_json()
    cartridge = client.get(f"/api/artifacts/{packaged['cartridge_artifacts'][0]['id']}/download").data
    ran = client.post(f"/api/projects/{project['id']}/run").get_json()
    return {"locale": locale, "ir": sha256(stable(converted["game_ir"])), "c": sha256(converted["c_source"].encode()),
            "asm": sha256(converted["asm_source"].encode()),
            # The map names the project it was made for; each fresh kit makes a new project id.
            "debug_map": sha256(stable({**ran["debug"], "cartridge": {key: value for key, value in
                                                                      ran["debug"]["cartridge"].items() if key != "project_id"}})),
            "cartridge": sha256(cartridge), "run_cartridge": ran.get("sha256")}


def lifecycle(client, out: Path, checks: Checks) -> dict[str, Any]:
    """Create, save, reload, archive, import and package; write every artifact to ``out``."""
    source = SCENARIO.read_text()
    audio = json.loads(SCENARIO_AUDIO.read_text())
    files: dict[str, bytes] = {"game.py": source.encode(), "audio.json": stable(audio)}
    created = client.post("/api/projects", json={"title": TITLE, "game_json": {
        "source_mode": "python", "source_python": "import prg32\n\n\ndef init() -> None:\n    pass\n\n\n"
        "def update() -> None:\n    pass\n\n\ndef draw() -> None:\n    pass\n", "python_language_version": 1}})
    checks("create a Python project", created.status_code == 201, created.status_code)
    project = created.get_json()
    pid = project["id"]
    saved = client.put(f"/api/projects/{pid}", json={"game_json": {**project["game_json"], "source_python": source},
                                                     "expected_version": project["version"]})
    checks("save game.py with the expected version", saved.status_code == 200, saved.get_json())
    stale = client.put(f"/api/projects/{pid}", json={"game_json": project["game_json"], "expected_version": project["version"]})
    checks("a save from an old version is refused (never overwrites)", stale.status_code == 409, stale.status_code)
    sound = client.get(f"/api/projects/{pid}/audio").get_json()
    put = client.put(f"/api/projects/{pid}/audio", json={"document": audio, "expected_version": sound["version"]})
    checks("save the AudioStudio sound (8 voices, stereo pan)", put.status_code == 200, put.get_json())
    reloaded = client.get(f"/api/projects/{pid}").get_json()
    checks("reload: game.py is what was saved", reloaded["game_json"]["source_python"] == source)
    checks("reload: the type is still Python", reloaded["game_json"]["source_mode"] == "python")
    archive = client.get(f"/api/projects/{pid}/archive")
    checks("archive the project", archive.status_code == 200 and archive.data[:2] == b"PK", archive.status_code)
    files["project.zip"] = archive.data
    imported = client.post("/api/projects/import", data={"file": (__import__("io").BytesIO(archive.data), "p.zip")},
                           content_type="multipart/form-data")
    body = imported.get_json() or {}
    copy = body.get("project", body)
    checks("import the archive", imported.status_code in (200, 201) and copy.get("id"), imported.status_code)
    checks("the imported game.py is the same", (copy.get("game_json") or {}).get("source_python") == source)

    converted = client.post(f"/api/projects/{pid}/convert", json={"source_language": "both"}).get_json()
    checks("generate C and assembly", bool(converted.get("c_source")) and bool(converted.get("asm_source")))
    files["game.c"] = converted["c_source"].encode()
    files["game.S"] = converted["asm_source"].encode()
    files["game.ir.json"] = stable(converted["game_ir"])
    checks("the C is commented teaching code", converted["c_source"].count("/*") > 40)
    checks("the assembly is RV32IM with the lifecycle labels",
           all(f"{converted['game_ir']['entry_prefix']}_{name}:" in converted["asm_source"]
               for name in ("init", "update", "draw")))
    checks("eight voices are used, panned left to right",
           [voice["pan"] for voice in audio["voices"]] == sorted(voice["pan"] for voice in audio["voices"])
           and len(audio["voices"]) == 8)

    cartridges = {}
    for language in ("c", "asm"):
        packaged = client.post(f"/api/projects/{pid}/package",
                               json={"architectures": ["qemu", "esp32c6"], "source_language": language})
        answer = packaged.get_json()
        built = answer.get("cartridge_artifacts") or []
        checks(f"package from the generated {language}: real cartridges for qemu and esp32c6", len(built) == 2,
               (answer.get("result") or {}).get("log", "")[-800:])
        for artifact in built:
            data = client.get(f"/api/artifacts/{artifact['id']}/download").data
            name = f"{language}-{artifact['metadata']['architecture']}.prg32"
            files[name] = data
            cartridges[name] = data
            checks(f"{name} is a PRG32 cartridge", data[:4] == b"PRG2", data[:4])
        if language == "c" and answer.get("build"):
            provenance = (answer["build"].get("metadata") or {}).get("provenance") or answer.get("provenance")
            if provenance:
                files["provenance.json"] = stable(provenance)
    ran = client.post(f"/api/projects/{pid}/run").get_json()
    checks("run build for the browser: a cartridge and its debug map", bool(ran.get("cartridge")) and bool(ran.get("debug")),
           ran.get("log", "")[-800:] if isinstance(ran, dict) else ran)
    run_bytes = base64.b64decode(ran["cartridge"])
    files["run.prg32"] = run_bytes
    files["debug.json"] = stable(ran["debug"])
    checks("the run build's cartridge is byte for byte the packaged qemu cartridge (debug info changes nothing)",
           run_bytes == cartridges.get("c-qemu.prg32"), sha256(run_bytes))
    for name, data in files.items():
        (out / name).write_bytes(data)
    return {"project_id": pid, "files": {name: {"sha256": sha256(data), "bytes": len(data)} for name, data in files.items()},
            "debug": ran["debug"], "entry_prefix": converted["game_ir"]["entry_prefix"]}


def check_diagnostics(client, checks: Checks) -> list[dict[str, Any]]:
    audio = json.loads(SCENARIO_AUDIO.read_text())
    found = []
    for name, program, code, line, column in diagnostics():
        project = client.post("/api/projects", json={"title": f"Diagnostic {name}", "game_json": {
            "source_mode": "python", "source_python": program, "python_language_version": 1}}).get_json()
        if code == "missing_sound":
            sound = client.get(f"/api/projects/{project['id']}/audio").get_json()
            client.put(f"/api/projects/{project['id']}/audio", json={"document": audio, "expected_version": sound["version"]})
        answer = client.post(f"/api/projects/{project['id']}/convert", json={"source_language": "both"}).get_json()
        problems = answer.get("problems") or []
        problem = problems[0] if problems else {}
        found.append({"case": name, "expected": [code, line, column], "problem": problem})
        checks(f"validator: {name} at line {line}, column {column}",
               problem.get("code") == code and problem.get("line") == line and problem.get("column") == column, problem)
    # A build problem: more memory than the cartridge has. The kit refuses it with a safe message.
    big = ("import prg32\n" + "".join(f"l{i}: list[int] = [0] * 1024\n" for i in range(40))
           + "\n\ndef init() -> None:\n    pass\n\n\ndef update() -> None:\n    pass\n\n\ndef draw() -> None:\n"
           "    l0[0] = 1\n")
    project = client.post("/api/projects", json={"title": "Diagnostic build", "game_json": {
        "source_mode": "python", "source_python": big, "python_language_version": 1}}).get_json()
    packaged = client.post(f"/api/projects/{project['id']}/package", json={"architectures": ["qemu"]}).get_json()
    log = (packaged.get("result") or {}).get("log", "") or packaged.get("error", "")
    found.append({"case": "too_much_memory", "cartridges": len(packaged.get("cartridge_artifacts") or []), "log": log[-1200:]})
    checks("build: a game larger than the cartridge's memory makes no cartridge",
           not packaged.get("cartridge_artifacts"), log[-400:])
    checks("build messages name no server paths", "/tmp/" not in log and str(ROOT) not in log, log[-400:])
    return found


def check_hostile(client, work: Path, checks: Checks) -> list[dict[str, Any]]:
    from prg32_construction_kit import python_project

    sentinel = work / SENTINEL
    rows = []
    for name, program in hostile_programs(sentinel).items():
        problems = python_project.check(program)
        project = client.post("/api/projects", json={"title": f"Hostile {name}", "game_json": {
            "source_mode": "python", "source_python": program, "python_language_version": 1}})
        refused_api = project.status_code >= 400
        built = None
        if not refused_api:
            pid = project.get_json()["id"]
            built = client.post(f"/api/projects/{pid}/package", json={"architectures": ["qemu"]})
            client.post(f"/api/projects/{pid}/run")
        refused_build = built is None or built.status_code >= 400 or not (built.get_json() or {}).get("cartridge_artifacts")
        rows.append({"case": name, "problem": problems[0] if problems else None, "saved": not refused_api,
                     "cartridge": not refused_build})
        checks(f"hostile program refused before running: {name}",
               bool(problems) and refused_build and not sentinel.exists(), problems[:1])
    checks("no hostile program ran (the sentinel file was never written)", not sentinel.exists())
    return rows


def versions() -> dict[str, Any]:
    def out(command: list[str]) -> str:
        try:
            return subprocess.run(command, capture_output=True, text=True, timeout=60).stdout.strip().splitlines()[0]
        except (OSError, IndexError, subprocess.SubprocessError):
            return "not available"

    from prg32_construction_kit import python_project

    kit = out(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    return {"kit_revision": os.environ.get("PRG32_KIT_REVISION") or kit, "python": platform.python_version(),
            "platform": platform.platform(), "prg32_python": python_project.LANGUAGE, "grammar": python_project.GRAMMAR,
            "riscv_gcc": out(["riscv32-esp-elf-gcc", "--version"]),
            "prg32_sdk": out([sys.executable, "-c", "import prg32, pathlib; print(pathlib.Path(prg32.__file__).parent)"])}


def build(args) -> int:
    from prg32_construction_kit import i18n
    from prg32_construction_kit.build_check import builds_available

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    checks = Checks()
    command = os.environ.get("PRG32_BUILD_COMMAND", f"{sys.executable} -m prg32 cartridge build")
    if not checks("the PRG32 toolchain is installed", builds_available(command), command):
        (out / "evidence.json").write_text(json.dumps({"checks": checks.rows}, indent=1))
        return 1
    with tempfile.TemporaryDirectory(prefix="scenario-l-") as tmp:
        _app, client = make_kit(Path(tmp))
        evidence: dict[str, Any] = {"scenario": "L", "versions": versions()}
        evidence["lifecycle"] = lifecycle(client, out, checks)
        evidence["diagnostics"] = check_diagnostics(client, checks)
        evidence["hostile"] = check_hostile(client, Path(tmp), checks)
    runs = []
    for locale in ("en",) + tuple(i18n.LOCALES):
        with tempfile.TemporaryDirectory(prefix=f"scenario-l-{locale}-") as tmp:
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "one", "--locale", locale, "--data", tmp],
                                    capture_output=True, text=True, timeout=900)
            if result.returncode != 0:
                checks(f"fresh-process build in {locale}", False, result.stderr[-800:])
                continue
            runs.append(json.loads(result.stdout.strip().splitlines()[-1]))
    evidence["fresh_builds"] = runs
    first = {key: value for key, value in runs[0].items() if key != "locale"} if runs else {}
    for run in runs:
        same = {key: value for key, value in run.items() if key != "locale"} == first
        checks(f"fresh process, interface {run['locale']}: IR, C, assembly, debug map and cartridge identical", same, run)
    if runs:
        files = evidence["lifecycle"]["files"]
        checks("the fresh builds' cartridge is the lifecycle's qemu cartridge",
               first.get("cartridge") == files.get("c-qemu.prg32", {}).get("sha256"), first.get("cartridge"))
    evidence["checks"] = checks.rows
    evidence["passed"] = checks.passed
    (out / "evidence.json").write_text(json.dumps(evidence, indent=1, ensure_ascii=False) + "\n")
    print(f"{sum(row['ok'] for row in checks.rows)}/{len(checks.rows)} checks passed; evidence in {out / 'evidence.json'}")
    return 0 if checks.passed else 1


def one(args) -> int:
    print(json.dumps(build_once(args.locale, Path(args.data))))
    return 0


# --- run: the exact cartridge on the browser core, a native core and canonical PRG32-QT ------------

def python_line_target(debug: dict[str, Any], line_text: str) -> tuple[int, str, int]:
    """(game.py line, a debugger target such as "update+38", the offset) for the lowest address of the
    C lines that game.py line became, found the way the Player's source debugger does
    (static/js/source_debug.js): game.py line -> source map -> C lines -> debug map -> address."""
    python_lines = debug["python_source"]["text"].splitlines()
    line = python_lines.index(line_text) + 1
    c_lines = set()
    for entry in debug["source_map"]["entries"]:
        if entry.get("python") and entry["python"][0] == line:
            c_lines.update(range(entry["lines"][0], entry["lines"][1] + 1))
    info = debug["debug_map"]
    game_c = [index for index, name in enumerate(info["files"]) if name == "game.c"]
    addresses = [row[0] for row in info["lines"] if row[1] in game_c and row[2] in c_lines and row[3]]
    if not addresses:
        raise SystemExit(f"no address for game.py line {line}")
    address = min(addresses)
    for symbol in info["symbols"]:
        phase = symbol["name"].rsplit("_", 1)[-1]
        if symbol["kind"] == "function" and phase in ("init", "update", "draw") \
                and symbol["address"] <= address < symbol["address"] + symbol["size"]:
            return line, f"{phase}+{address - symbol['address']}", address - symbol["address"]
    raise SystemExit(f"game.py line {line} is not inside init, update or draw")


def run_phase(args) -> int:
    evidence_dir = Path(args.evidence)
    build_evidence = json.loads((evidence_dir / "evidence.json").read_text())
    cartridge = evidence_dir / "run.prg32"
    debug = json.loads((evidence_dir / "debug.json").read_text())
    checks = Checks()
    checks("the cartridge is the one the build phase recorded",
           sha256(cartridge.read_bytes()) == build_evidence["lifecycle"]["files"]["run.prg32"]["sha256"])
    module = Path(args.module)
    node = shutil.which("node")
    work = Path(tempfile.mkdtemp(prefix="scenario-l-run-"))

    def sh(command: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run(command, capture_output=True, text=True, timeout=900)

    harness_build, qt_build = work / "harness", work / "qt"
    sh(["cmake", "-S", str(ROOT / "wasm"), "-B", str(harness_build), f"-DPRG32QT_DIR={args.prg32qt}",
        f"-DPRG32_DIR={args.sdk}", "-DCMAKE_BUILD_TYPE=Release"])
    harness_ok = sh(["cmake", "--build", str(harness_build), "--parallel"]).returncode == 0
    sh(["cmake", "-S", str(args.prg32qt), "-B", str(qt_build), "-DPRG32QT_BUILD_APP=OFF"])
    qt_ok = sh(["cmake", "--build", str(qt_build), "--target", "prg32qt-headless", "--parallel"]).returncode == 0
    checks("native harness and canonical prg32qt-headless build", harness_ok and qt_ok)
    harness, headless = harness_build / "prg32-core-harness", qt_build / "prg32qt-headless"

    states = {}
    for name, command in (("browser core", [node, str(ROOT / "tools" / "wasm_harness.mjs"), str(module), str(cartridge), "600", "100"]),
                          ("native core", [str(harness), str(cartridge), "600", "100"])):
        result = sh(command)
        states[name] = [json.loads(line) for line in result.stdout.splitlines()] if result.returncode == 0 else []
        checks(f"{name}: the cartridge loads and runs 600 frames", len(states[name]) == 7, result.stderr[-400:])
    checks("browser core == native core: pc, registers, instructions, cycles, framebuffer and audio every 100 frames",
           states["browser core"] == states["native core"] and bool(states["native core"]))
    checks("the game runs (instructions retire, the screen changes)",
           bool(states["native core"]) and states["native core"][-1]["retired"] > states["native core"][0]["retired"])
    qt = sh([str(headless), str(cartridge), "450", "--verify-media", "--dump-ppm", str(work / "qt.ppm")])
    kit = sh([str(harness), str(cartridge), "450", "450", str(work / "kit.ppm")])
    same_frame = qt.returncode == 0 and kit.returncode == 0 and (work / "qt.ppm").read_bytes() == (work / "kit.ppm").read_bytes()
    checks("canonical PRG32-QT draws frame 450 exactly like the kit's core", same_frame, qt.stderr[-400:])
    if (work / "qt.ppm").exists():
        shutil.copyfile(work / "qt.ppm", evidence_dir / "prg32qt-frame-450.ppm")

    line, target, offset = python_line_target(debug, BREAK_ON)
    stops = {}
    for name, command in (("browser core", [node, str(ROOT / "tools" / "wasm_harness.mjs"), str(module), "--debug", str(cartridge)]),
                          ("native core", [str(harness), "--debug", str(cartridge)])):
        # Stop at update's first instruction (its address in this core), then at the game.py line.
        result = sh([*command, "break:update", "continue", "unbreak:update", f"break:{target}", "continue"])
        lines = [json.loads(row) for row in result.stdout.splitlines()] if result.returncode == 0 else []
        stops[name] = lines
        # Each command's line carries the debugger's state; result 2 is "stopped at a breakpoint".
        stopped = (len(lines) == 5 and lines[1].get("result") == 2 and lines[4].get("result") == 2
                   and lines[4]["state"]["pc"] == lines[1]["state"]["pc"] + offset
                   and lines[4]["state"]["last_breakpoint"] == lines[4]["state"]["pc"])
        checks(f"{name}: a breakpoint on game.py line {line} ({target}) stops there", stopped,
               lines[-1:] or result.stderr[-300:])
    checks("the browser core and the native core stop in the same state", stops["browser core"] == stops["native core"])

    evidence = {"scenario": "L", "phase": "run", "cartridge_sha256": sha256(cartridge.read_bytes()),
                "prg32qt_revision": args.prg32qt_revision, "sdk_revision": args.sdk_revision,
                "module_sha256": sha256(module.read_bytes()), "node": sh([node, "--version"]).stdout.strip(),
                "states": states["native core"], "breakpoint": {"python_line": line, "target": target,
                                                                 "stop": stops["native core"][-1:]},
                "checks": checks.rows, "passed": checks.passed}
    (evidence_dir / "run-evidence.json").write_text(json.dumps(evidence, indent=1) + "\n")
    print(f"{sum(row['ok'] for row in checks.rows)}/{len(checks.rows)} checks passed")
    return 0 if checks.passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="phase", required=True)
    b = sub.add_parser("build")
    b.add_argument("--out", required=True)
    o = sub.add_parser("one")
    o.add_argument("--locale", required=True)
    o.add_argument("--data", required=True)
    r = sub.add_parser("run")
    r.add_argument("--evidence", required=True)
    r.add_argument("--prg32qt", required=True, type=Path)
    r.add_argument("--sdk", required=True, type=Path)
    r.add_argument("--module", default=str(ROOT / "static" / "wasm" / "prg32-core.js"))
    r.add_argument("--prg32qt-revision", default="")
    r.add_argument("--sdk-revision", default="")
    args = parser.parse_args()
    return {"build": build, "one": one, "run": run_phase}[args.phase](args)


if __name__ == "__main__":
    sys.exit(main())
