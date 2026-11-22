"""Carga de las tablas procesadas que usa el dashboard (una sola vez al arrancar)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

from strategy_audit.config import GP_ABBR, GP_ES, PROCESSED_DIR, SEASON
from strategy_audit.models.pace_model import RaceModel, model_from_frames
from strategy_audit.simulation.simulator import pit_loss_by_lap, strategy_laps
from strategy_audit.simulation.traffic import RaceTraffic, build_traffic, simulate_traffic

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

    def race_es(self, rnd: int) -> str:
        """Nombre del GP en español (p. ej. «GP de Mónaco»)."""
        name = self.race_name(rnd)
        return GP_ES.get(name, name)

    def race_abbr(self, rnd: int) -> str:
        name = self.race_name(rnd)
        return GP_ABBR.get(name, name[:3].upper())

    def race_options(self) -> list[dict]:
        return [{"label": f"R{r:02d} · {self.race_es(r)}", "value": r} for r in self.audited_rounds]

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

    def traffic(self, rnd: int) -> RaceTraffic:
        """Posición real de los rivales vuelta a vuelta, con el umbral de adelantamiento calibrado."""
        key = (id(self), rnd)
        if key not in _TRAFFIC_CACHE:
            row = self.race_row(rnd)
            delta = row.get("OvertakeDelta", float("nan"))
            _TRAFFIC_CACHE[key] = build_traffic(self.laps[self.laps["Round"] == rnd], self.neutralised_laps(rnd),
                                                None if pd.isna(delta) else float(delta))
        return _TRAFFIC_CACHE[key]

    def traffic_penalty(self, rnd: int, driver: str, first_age: int, actual: list[tuple[str, int]]):
        """Función stints → TrafficResult para un piloto (rivales fijos, como en la auditoría)."""
        model, pls, tr = self.model(rnd), self.pit_losses(rnd), self.traffic(rnd)
        _, actual_pits = strategy_laps(model, driver, actual, first_age, pls)

        def run(stints: list[tuple[str, int]], keep_cum: bool = False):
            clean, pits = strategy_laps(model, driver, stints, first_age, pls)
            return simulate_traffic(tr, driver, clean, pits, actual_pits, keep_cum=keep_cum)
        return run


def _model(store: Store, rnd: int) -> RaceModel:
    key = (id(store), rnd)
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = model_from_frames(rnd, store.model_drivers, store.model_compounds, store.races)
    return _MODEL_CACHE[key]


_MODEL_CACHE: dict = {}
_TRAFFIC_CACHE: dict = {}


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
