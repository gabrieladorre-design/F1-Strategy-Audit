"""Paso 2 del pipeline: limpieza, modelo, simulación y auditoría (sin conexión).

Uso:
    python scripts/build_dataset.py --season 2025
"""
import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from strategy_audit.pipeline import run  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Construye las tablas procesadas para la app")
    parser.add_argument("--season", type=int, default=2025)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run(args.season)
