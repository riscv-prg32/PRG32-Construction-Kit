from __future__ import annotations

import os

from prg32_construction_kit import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", os.environ.get("PRG32_KIT_PORT", "5090")))
    app.run(host="0.0.0.0", port=port, debug=os.environ.get("FLASK_DEBUG", "0") == "1")
