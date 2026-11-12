"""Carga de las tablas procesadas que usa el dashboard (una sola vez al arrancar)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from strategy_audit.config import PROCESSED_DIR, SEASON
from strategy_audit.models.pace_model import RaceModel, model_from_frames
from strategy_audit.simulation.simulator import pit_loss_by_lap

TABLES = ["races", "laps", "stints", "neutralised", "results", "model_drivers",
          "model_compounds", "audit", "best_stints", "validation"]


@dataclass
class Store:
    season: int
    races: pd.DataFrame
    laps: pd.DataFrame
    stints: pd.DataFrame
    neutralised: pd.DataFrame
    results: pd.DataFrame
    model_drivers: pd.DataFrame
    model_compounds: pd.DataFrame
    audit: pd.DataFrame
    best_stints: pd.DataFrame
    validation: pd.DataFrame
    metrics: dict

    @property
    def audited_rounds(self) -> list[int]:
        return sorted(self.audit["Round"].unique().astype(int)) if len(self.audit) else []

    def race_name(self, rnd: int) -> str:
        r = self.races[self.races["Round"] == rnd]
        return str(r["EventName"].iloc[0]) if len(r) else f"Ronda {rnd}"

    def race_options(self) -> list[dict]:
        return [{"label": f"R{r:02d} · {self.race_name(r)}", "value": r} for r in self.audited_rounds]

    def race_row(self, rnd: int) -> pd.Series:
        return self.races[self.races["Round"] == rnd].iloc[0]

    def model(self, rnd: int) -> RaceModel:
        return _model(self, rnd)

    def neutralised_laps(self, rnd: int) -> set[int]:
        n = self.neutralised
        return set(n.loc[n["Round"] == rnd, "LapNumber"].astype(int))

    def pit_losses(self, rnd: int) -> np.ndarray:
        row = self.race_row(rnd)
        return pit_loss_by_lap(int(row["TotalLaps"]), float(row["PitLoss"]), self.neutralised_laps(rnd))


def _model(store: Store, rnd: int) -> RaceModel:
    key = (id(store), rnd)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = model_from_frames(rnd, store.model_drivers, store.model_compounds, store.races)
    return _MODEL_CACHE[key]


_MODEL_CACHE: dict = {}


@lru_cache(maxsize=1)
def load_store(season: int = SEASON) -> Store | None:
    """Devuelve las tablas procesadas, o None si todavía no se ha ejecutado el pipeline."""
    paths = {t: PROCESSED_DIR / f"{t}_{season}.parquet" for t in TABLES}
    if not all(p.exists() for p in paths.values()):
        return None
    frames = {t: pd.read_parquet(p) for t, p in paths.items()}
    metrics_path = PROCESSED_DIR / f"metrics_{season}.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else {}
    return Store(season=season, metrics=metrics, **frames)
