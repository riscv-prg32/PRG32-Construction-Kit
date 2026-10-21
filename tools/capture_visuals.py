"""Take the documentation screenshots again from a throwaway kit with synthetic data (DOC-02).

    python3 tools/capture_visuals.py                 # every screenshot below
    python3 tools/capture_visuals.py ide-hero        # one of them

The kit starts in a temporary folder with only its own sample projects, which have no real
author, and two synthetic accounts. Chrome (or Playwright's Chromium) opens each page at a
fixed size, light theme and English locale, and the picture is written into docs/figures/.
Each capture updates its entry in docs/figures/manifest.json:

- the recipe;
- the viewport, browser, theme, locale and seed;
- the commit the screenshot shows, and the date.

Then a person looks at the pictures and records the review: tools/check_docs.py fails until
the entry has a reviewer and a review date not older than the capture.
"""

from __future__ import annotations

import datetime
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MANIFEST = ROOT / "docs" / "figures" / "manifest.json"
VIEWPORT = {"width": 1440, "height": 900}
ADMIN_PASSWORD = "capture-admin-password-1"
TEACHER = ("teacher1", "capture-teacher-password-1")
GAMES = {"pong": "Pong", "breakout": "Breakout", "space_invaders": "Space Invaders", "asteroids": "Asteroids",
         "snake": "Snake"}

# name -> (file, page, what the reader should see)
RECIPES = {"ide-hero": ("docs/figures/PRG32-Construction-Kit_01.png", "ide:Pong",
                        "The IDE with the Pong project: project tree, Blocks editor, generated C, Problems and Run panels")}
for key, title in GAMES.items():
    RECIPES[f"{key}-editor"] = (f"docs/figures/games/{key}-editor.jpg", f"editor:{title}",
                                f"The {title} project in the Blocks editor, with its preview")


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True).stdout.strip()


def start_kit(folder: Path):
    from werkzeug.serving import make_server

    from prg32_construction_kit import create_app

    app = create_app({"DATA_DIR": folder, "DB_PATH": folder / "kit.sqlite", "BUILD_ROOT": folder / "builds",
                      "ARTIFACT_ROOT": folder / "artifacts", "ADMIN_PASSWORD": ADMIN_PASSWORD,
                      "SSO_SECRET": "", "SSO_PEER_URL": ""})
    server = make_server("127.0.0.1", 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    client = app.test_client()
    client.post("/auth/login", data={"username": "admin", "password": ADMIN_PASSWORD})
    client.post("/api/users", json={"username": TEACHER[0], "email": "teacher1@example.test", "password": TEACHER[1],
                                    "kit_role": "teacher"}, headers={"X-PRG32-Kit": "1"})
    return server, f"http://127.0.0.1:{server.server_port}"


def project_id(page, title: str) -> str:
    return page.evaluate("t => fetch('/api/projects', {headers: {'X-PRG32-Kit': '1'}}).then(r => r.json())"
                         ".then(d => d.projects.find(p => p.title === t).id)", title)


def capture(names: list[str]) -> list[str]:
    from playwright.sync_api import sync_playwright

    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.is_file() else {"visuals": {}}
    commit = git("rev-parse", "HEAD")
    today = datetime.date.today().isoformat()
    written = []
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as playwright:
        server, origin = start_kit(Path(folder))
        browser = None
        for options in ({"channel": "chrome"}, {}):
            try:
                browser = playwright.chromium.launch(headless=True, **options)
                break
            except Exception:   # noqa: BLE001 - try Playwright's own Chromium next
                continue
        if browser is None:
            raise SystemExit("needs Chrome or Playwright's Chromium (python3 -m playwright install chromium)")
        context = browser.new_context(viewport=VIEWPORT, color_scheme="light", locale="en-US", device_scale_factor=1)
        # The storage note (base.html) is read once per browser: mark it read, so it is not in the pictures.
        notices = json.loads((ROOT / "prg32_construction_kit" / "privacy_notices.json").read_text())["notices"]
        version = next(item["version"] for item in notices if item["id"] == "storage")
        context.add_init_script(f"try {{ localStorage.setItem('prg32-kit-storage-notice', '{version}'); }} catch (e) {{}}")
        page = context.new_page()
        page.goto(origin + "/auth/login")
        page.fill("#username", TEACHER[0])
        page.fill("#password", TEACHER[1])
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")
        for name in names:
            file, where, purpose = RECIPES[name]
            kind, title = where.split(":", 1)
            pid = project_id(page, title)
            if kind == "ide":
                page.goto(f"{origin}/ide/{pid}")
                page.wait_for_function("document.getElementById('ide').dataset.ready === 'true'", timeout=30000)
            else:
                page.goto(f"{origin}/projects/{pid}")
                page.wait_for_function("!!document.querySelector('.blocklySvg')", timeout=30000)
            page.wait_for_timeout(1500)                     # let Blockly, Monaco and the preview settle
            target = ROOT / file
            page.screenshot(path=str(target), type="jpeg" if file.endswith(".jpg") else "png",
                            **({"quality": 85} if file.endswith(".jpg") else {}))
            entry = manifest["visuals"].get(file, {})
            entry.update({"purpose": purpose, "kind": "screenshot", "recipe": f"python3 tools/capture_visuals.py {name}",
                          "viewport": f"{VIEWPORT['width']}x{VIEWPORT['height']}",
                          "browser": f"{browser.browser_type.name} {browser.version} (headless)", "theme": "light",
                          "locale": "en-US", "seed": "sample_data.seed_if_empty (sample projects, no real author); "
                                                    "synthetic accounts admin, teacher1@example.test",
                          "product_commit": commit, "captured": today, "reviewed": None, "reviewer": None,
                          "watch": entry.get("watch") or (["templates/ide.html", "static/js/ide/", "static/css/"]
                                                          if kind == "ide" else
                                                          ["templates/editor.html", "static/js/editor.js", "static/css/"])})
            manifest["visuals"][file] = entry
            written.append(file)
            print(f"captured {file}")
        browser.close()
        server.shutdown()
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return written


def main() -> int:
    names = sys.argv[1:] or list(RECIPES)
    unknown = [name for name in names if name not in RECIPES]
    if unknown:
        print("unknown: " + ", ".join(unknown) + "; known: " + ", ".join(RECIPES), file=sys.stderr)
        return 2
    capture(names)
    print("Now look at each picture and record the review in docs/figures/manifest.json (reviewed, reviewer).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
