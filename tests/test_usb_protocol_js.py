"""Run the browser USB client's behaviour tests (tests/js/*.test.mjs) under Node.

The client in static/js/prg32_usb_protocol.js is the one the Deploy page loads;
tests/js/fake_prg32_serial.js pretends to be a PRG32 behind Web Serial.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_browser_usb_client_behaviour():
    # The files by name: Node 22+ reads a folder argument as a module to load, not a folder to search.
    tests = sorted(str(path.relative_to(ROOT)) for path in (ROOT / "tests" / "js").glob("*.test.mjs"))
    assert tests
    result = subprocess.run(
        ["node", "--test", *tests],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr
