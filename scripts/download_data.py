"""Paso 1 del pipeline: descarga de datos (requiere conexión a las APIs de F1).

Uso:
    python scripts/download_data.py --season 2025
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy_audit.ingestion.fastf1_loader import download_season  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Descarga carreras con FastF1")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--force", action="store_true", help="Volver a descargar todo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("fastf1").setLevel(logging.WARNING)
    download_season(args.season, force=args.force)
