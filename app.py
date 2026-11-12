"""Punto de entrada de la aplicación (local y Render).

Local:   python app.py            → http://127.0.0.1:8050
Render:  gunicorn app:server
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from strategy_audit.dashboard.app import create_app  # noqa: E402

app = create_app()
server = app.server  # obligatorio para gunicorn

if __name__ == "__main__":
    app.run(debug=os.environ.get("DASH_DEBUG", "1") == "1", port=int(os.environ.get("PORT", 8050)))
