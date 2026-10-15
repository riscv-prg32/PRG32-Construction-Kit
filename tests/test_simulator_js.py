"""Check that the browser simulator evaluates expressions like the generated C."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

SIMULATOR = Path(__file__).resolve().parent.parent / "static" / "js" / "simulator.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is not installed")
def test_simulator_uses_c_integer_rules_and_no_eval():
    cases = ["7/2", "-7/2", "-7%3", "x*2+1", "1<2&&3", "!0", "X + 1", "1/0", "0x10", "alert(1)", "x.y", "1 /* c"]
    script = (
        "global.window = {};"
        f"eval(require('fs').readFileSync({json.dumps(str(SIMULATOR))}, 'utf8'));"
        "const S = window.PRG32Simulator;"
        f"console.log(JSON.stringify({json.dumps(cases)}.map(e => S.evalExpr(S.saneExpr(e, 0), {{ x: 10 }}))));"
    )
    output = subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True).stdout
    assert json.loads(output) == [3, -3, -1, 21, 1, 1, 11, 0, 16, 0, 0, 0]
