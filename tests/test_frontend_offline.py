"""The frontend is self-contained (refinement phase 1, ADR-0012): no CDN, strict CSP, static-only cache."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
PAGES = sorted([*ROOT.glob("templates/*.html"), *ROOT.glob("static/*.html")])
EXTERNAL = re.compile(r"""(?:src|href|action)\s*=\s*["'](?:https?:)?//""", re.IGNORECASE)


def test_vendored_files_match_their_recorded_hashes():
    import vendor_assets

    assert vendor_assets.check() == 0
    record = json.loads((ROOT / "static" / "vendor" / "VENDOR.json").read_text())
    names = {package["name"]: package for package in record["packages"]}
    assert set(names) == {"bootstrap", "bootstrap-icons", "jquery", "blockly", "monaco-editor"}
    for package in record["packages"]:
        assert package["license"] in {"MIT", "Apache-2.0"} and package["integrity"].startswith("sha512-")
        assert any(Path(path).name.startswith("LICENSE") for path in package["files"]), package["name"]


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_pages_load_nothing_from_other_sites(page):
    text = page.read_text()
    assert not EXTERNAL.search(text), page
    assert "cdn.jsdelivr" not in text and "unpkg.com" not in text and "code.jquery.com" not in text


@pytest.mark.parametrize("page", PAGES, ids=lambda page: page.name)
def test_pages_have_no_inline_scripts_or_styles(page):
    text = page.read_text()
    for script in re.findall(r"<script\b[^>]*>(.*?)</script>", text, re.DOTALL):
        assert not script.strip(), f"inline script in {page.name}"
    assert "<style" not in text, page.name
    assert not re.search(r"\sstyle\s*=", text), page.name
    assert not re.search(r"\son[a-z]+\s*=", text), f"inline event handler in {page.name}"


def test_javascript_builds_no_inline_styles_or_handlers():
    for script in ROOT.glob("static/js/*.js"):
        text = script.read_text()
        assert not re.search(r"""\sstyle\s*=\s*["']""", text), script.name
        assert not re.search(r"""\son(?:click|load|error)\s*=\s*["']""", text), script.name


def test_every_static_file_a_page_uses_exists():
    for page in PAGES:
        for path in re.findall(r"""["'](/static/[^"'?#]+)""", page.read_text()):
            assert (ROOT / path.lstrip("/")).is_file(), f"{page.name}: {path}"
        for path in re.findall(r"""filename=['"]([^'"]+)['"]""", page.read_text()):
            assert (ROOT / "static" / path).is_file(), f"{page.name}: {path}"


def test_service_worker_caches_every_vendored_file_the_pages_need():
    import service_worker_lock

    _name, shell = service_worker_lock.read_worker()
    assert all(path.startswith("/static/") for path in shell)
    assert all((ROOT / path.lstrip("/")).is_file() for path in shell)
    needed = set()
    for page in ("templates/base.html", "templates/editor.html", "static/offline.html", "static/offline-player.html"):
        text = (ROOT / page).read_text()
        needed |= {"/static/" + path for path in re.findall(r"""filename=['"](vendor/[^'"]+)['"]""", text)}
        needed |= set(re.findall(r"""["'](/static/vendor/[^"'?#]+)""", text))
    assert needed and needed <= set(shell), needed - set(shell)
    assert "/static/offline.html" in shell and "/static/wasm/prg32-core.wasm" in shell


def test_cached_files_never_change_without_a_new_cache_name():
    import service_worker_lock

    sys.argv = ["service_worker_lock.py", "--check"]
    assert service_worker_lock.main() == 0, "bump CACHE_NAME and run python3 tools/service_worker_lock.py"


def test_content_security_policy_is_strict(client):
    policy = client.get("/").headers["Content-Security-Policy"]
    directives = dict(item.strip().split(" ", 1) for item in policy.split(";"))
    assert directives["default-src"] == "'self'"
    assert directives["script-src"] == "'self' 'wasm-unsafe-eval'"   # no inline scripts, no eval
    assert "'unsafe-inline'" not in policy and "'unsafe-eval'" not in policy
    # Styles: the kit, this page's nonce (Monaco, Blockly via csp_nonce.js), Blockly's two hashes.
    assert re.fullmatch(r"'self' 'nonce-[\w-]{24}' 'sha256-\S+' 'sha256-\S+'", directives["style-src"])
    assert client.get("/").headers["Content-Security-Policy"] != policy  # a new nonce every time
    assert directives["object-src"] == "'none'" and directives["frame-ancestors"] == "'none'"
    assert directives["connect-src"] == "'self'" and directives["form-action"] == "'self'"
    assert "http" not in policy                                        # no other site anywhere


def test_csp_lets_single_sign_on_post_only_to_the_linked_store(tmp_path):
    from conftest import make_app

    app = make_app(tmp_path, SSO_SECRET="x" * 40, SSO_PEER_URL="https://store.school.test/path")
    policy = app.test_client().get("/").headers["Content-Security-Policy"]
    assert "form-action 'self' https://store.school.test;" in policy + ";"


def test_pages_and_api_answers_are_never_cached(client, anon):
    for path in ("/", "/player", "/api/projects", "/auth/me"):
        assert client.get(path).headers["Cache-Control"] == "no-store", path
    assert anon.get("/auth/login").headers["Cache-Control"] == "no-store"
    vendor = client.get("/static/vendor/jquery/3.7.1/jquery.min.js")
    assert "immutable" in vendor.headers["Cache-Control"]


def test_service_worker_is_served_from_the_root_without_signing_in(anon):
    response = anon.get("/service-worker.js")
    assert response.status_code == 200
    assert response.headers["Service-Worker-Allowed"] == "/"
    assert response.headers["Cache-Control"] == "no-store"
    assert "javascript" in response.headers["Content-Type"]
    app_js = (ROOT / "static" / "js" / "app.js").read_text()
    assert "register('/service-worker.js', { scope: '/' })" in app_js


def test_offline_page_holds_no_account_data(anon):
    page = anon.get("/static/offline.html")
    assert page.status_code == 200 and b"Offline" in page.data
    assert b"{{" not in page.data and b"current_user" not in page.data


def test_ide_needs_a_sign_in_and_only_it_allows_style_attributes(client, anon):
    assert anon.get("/ide/anything").status_code in (302, 401)
    page = client.get("/ide/anything")
    assert page.status_code == 200
    html = page.get_data(as_text=True)
    for landmark in ('role="tree"', 'role="tablist"', 'role="toolbar"', 'role="status"', 'role="dialog"'):
        assert landmark in html
    ide_policy = page.headers["Content-Security-Policy"]
    assert "style-src-attr 'unsafe-inline'" in ide_policy           # Monaco's line styles, IDE only
    assert re.search(r"style-src-elem 'self' 'nonce-", ide_policy)   # <style> elements stay strict
    assert "script-src 'self' 'wasm-unsafe-eval'" in ide_policy
    assert "unsafe-inline" not in client.get("/").headers["Content-Security-Policy"]
    assert 'name="csp-nonce"' in html


def test_the_assembly_grammar_knows_exactly_the_allowed_directives():
    from prg32_construction_kit.source_project import ALLOWED_ASM_DIRECTIVES

    grammar = (ROOT / "static" / "js" / "ide" / "monaco_setup.js").read_text()
    listed = set(re.findall(r"'(\.[a-z0-9]+)'", grammar.split("const DIRECTIVES = [", 1)[1].split("];", 1)[0]))
    assert listed == ALLOWED_ASM_DIRECTIVES
