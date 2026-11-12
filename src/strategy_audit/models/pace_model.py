"""Modelo de ritmo por carrera.

Para cada carrera (en una temporada, carrera = circuito) se ajusta por mínimos
cuadrados, solo con vueltas limpias:

    LapTime = base_piloto + offset_compuesto + deg_compuesto · TyreLife + fuel · LapNumber

* ``base_piloto``: ritmo propio del piloto/coche.
* ``offset_compuesto``: diferencia de ritmo del compuesto (referencia = el más usado).
* ``deg_compuesto``: degradación, segundos perdidos por cada vuelta de vida del neumático.
* ``fuel``: efecto del combustible (normalmente negativo: el coche se aligera).

Validación: validación cruzada por grupos (5 *folds*) dejando fuera stints
completos, de forma que se mide el error al predecir stints no usados en el ajuste.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

N_FOLDS = 5
MIN_COMPOUND_LAPS = 40   # por debajo, el compuesto no se usa en el simulador (estimación poco fiable)

# Reglas especiales de 2025 que condicionan la estrategia
RACE_RULES = {
    8: {"min_stops": 2},        # Mónaco 2025: dos paradas obligatorias
    23: {"tyre_limit": 25},     # Qatar 2025: máximo 25 vueltas por juego de neumáticos
}


@dataclass
class RaceModel:
    round: int
    driver_base: dict[str, float]
    compound_offset: dict[str, float]
    compound_deg: dict[str, float]
    fuel: float
    reference_compound: str
    mae_train: float = float("nan")
    mae_cv: float = float("nan")
    n_laps: int = 0
    max_stint: dict[str, int] = field(default_factory=dict)
    compound_laps: dict[str, int] = field(default_factory=dict)
    min_stops: int = 1
    tyre_limit: int | None = None

    @property
    def usable_compounds(self) -> list[str]:
        """Compuestos con datos suficientes para simular estrategias con ellos."""
        return sorted(c for c in self.compound_deg if self.compound_laps.get(c, 0) >= MIN_COMPOUND_LAPS)

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        base = df["Driver"].map(self.driver_base).to_numpy(dtype=float)
        off = df["Compound"].map(self.compound_offset).to_numpy(dtype=float)
        deg = df["Compound"].map(self.compound_deg).to_numpy(dtype=float)
        return base + off + deg * df["TyreLife"].to_numpy(float) + self.fuel * df["LapNumber"].to_numpy(float)


def _design(df: pd.DataFrame, drivers: list[str], compounds: list[str], ref: str) -> np.ndarray:
    cols = [(df["Driver"] == d).to_numpy(float) for d in drivers]
    cols += [(df["Compound"] == c).to_numpy(float) for c in compounds if c != ref]
    cols += [(df["Compound"] == c).to_numpy(float) * df["TyreLife"].to_numpy(float) for c in compounds]
    cols.append(df["LapNumber"].to_numpy(float))
    return np.column_stack(cols)


def _identifiable(df: pd.DataFrame) -> pd.DataFrame:
    """Quita compuestos usados por menos de 3 pilotos: su efecto se confundiría con el
    ritmo propio de esos pilotos y la regresión daría valores sin sentido."""
    n = df.groupby("Compound")["Driver"].transform("nunique")
    return df[n >= 3]


def _fit(df: pd.DataFrame) -> tuple[list[str], list[str], str, np.ndarray]:
    df = _identifiable(df)
    drivers = sorted(df["Driver"].unique())
    compounds = sorted(df["Compound"].unique())
    ref = df["Compound"].value_counts().idxmax()
    X = _design(df, drivers, compounds, ref)
    coef, *_ = np.linalg.lstsq(X, df["LapTime"].to_numpy(float), rcond=None)
    return drivers, compounds, ref, coef


def _unpack(rnd, drivers, compounds, ref, coef) -> RaceModel:
    i = 0
    base = {d: float(coef[i + k]) for k, d in enumerate(drivers)}
    i += len(drivers)
    offset = {ref: 0.0}
    for c in compounds:
        if c != ref:
            offset[c] = float(coef[i])
            i += 1
    deg = {}
    for c in compounds:
        deg[c] = float(coef[i])
        i += 1
    return RaceModel(round=rnd, driver_base=base, compound_offset=offset,
                     compound_deg=deg, fuel=float(coef[i]), reference_compound=ref)


def _cv_mae(df: pd.DataFrame) -> float:
    groups = (df["Driver"] + "_" + df["Stint"].astype(str)).to_numpy()
    uniq = np.unique(groups)
    rng = np.random.default_rng(42)
    fold_of = dict(zip(uniq, rng.integers(0, N_FOLDS, len(uniq))))
    folds = np.array([fold_of[g] for g in groups])
    errors = []
    for k in range(N_FOLDS):
        train, test = df[folds != k], df[folds == k]
        if test.empty or train.empty:
            continue
        model = _unpack(-1, *_fit(train))
        # Solo se evalúan filas cuyo piloto y compuesto se vieron en el ajuste
        # Solo se evalúan filas identificables: piloto con ≥ 10 vueltas de ajuste y compuesto
        # usado en el ajuste por ≥ 3 pilotos (si no, ritmo del piloto y del compuesto se confunden)
        fit_rows = _identifiable(train)
        drv_laps = fit_rows["Driver"].value_counts()
        ok_drv = drv_laps[drv_laps >= 10].index
        test = test[test["Driver"].isin(ok_drv) & test["Compound"].isin(fit_rows["Compound"].unique())]
        if len(test):
            errors.append(np.abs(model.predict(test) - test["LapTime"].to_numpy()))
    return float(np.concatenate(errors).mean()) if errors else float("nan")


def fit_race(clean: pd.DataFrame, rnd: int) -> RaceModel:
    """Ajusta el modelo de una carrera con sus vueltas limpias."""
    df = clean[(clean["Round"] == rnd) & clean["IsClean"]]
    if len(df) < 50:
        raise ValueError(f"Muy pocas vueltas limpias en la carrera {rnd}: {len(df)}")
    model = _unpack(rnd, *_fit(df))
    df = _identifiable(df)
    model.n_laps = len(df)
    model.mae_train = float(np.abs(model.predict(df) - df["LapTime"]).mean())
    model.mae_cv = _cv_mae(df)
    # Longitud máxima de stint observada por compuesto: el simulador no extrapola más allá
    model.max_stint = {c: int(v) for c, v in df.groupby("Compound")["TyreLife"].max().items()}
    model.compound_laps = {c: int(v) for c, v in df["Compound"].value_counts().items()}
    rules = RACE_RULES.get(rnd, {})
    model.min_stops = rules.get("min_stops", 1)
    model.tyre_limit = rules.get("tyre_limit")
    return model


def models_to_frames(models: list[RaceModel]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convierte los modelos a tablas (piloto, compuesto y resumen por carrera)."""
    drivers, compounds, summary = [], [], []
    for m in models:
        drivers += [{"Round": m.round, "Driver": d, "Base": b} for d, b in m.driver_base.items()]
        compounds += [
            {"Round": m.round, "Compound": c, "Offset": m.compound_offset[c],
             "Deg": m.compound_deg[c], "MaxStint": m.max_stint.get(c, 0),
             "CleanLaps": m.compound_laps.get(c, 0)}
            for c in m.compound_deg
        ]
        summary.append({"Round": m.round, "Fuel": m.fuel, "ReferenceCompound": m.reference_compound,
                        "MAE_train": m.mae_train, "MAE_cv": m.mae_cv, "CleanLaps": m.n_laps,
                        "MinStops": m.min_stops, "TyreLimit": m.tyre_limit if m.tyre_limit else 0})
    return pd.DataFrame(drivers), pd.DataFrame(compounds), pd.DataFrame(summary)


def model_from_frames(rnd: int, drivers: pd.DataFrame, compounds: pd.DataFrame,
                      summary: pd.DataFrame) -> RaceModel:
    """Reconstruye un modelo a partir de las tablas guardadas (lo usa la app)."""
    d = drivers[drivers["Round"] == rnd]
    c = compounds[compounds["Round"] == rnd]
    s = summary[summary["Round"] == rnd].iloc[0]
    return RaceModel(
        round=rnd,
        driver_base=dict(zip(d["Driver"], d["Base"])),
        compound_offset=dict(zip(c["Compound"], c["Offset"])),
        compound_deg=dict(zip(c["Compound"], c["Deg"])),
        fuel=float(s["Fuel"]),
        reference_compound=s["ReferenceCompound"],
        mae_train=float(s["MAE_train"]),
        mae_cv=float(s["MAE_cv"]),
        n_laps=int(s["CleanLaps"]),
        max_stint=dict(zip(c["Compound"], c["MaxStint"].astype(int))),
        compound_laps=dict(zip(c["Compound"], c["CleanLaps"].astype(int))),
        min_stops=int(s.get("MinStops", 1)),
        tyre_limit=int(s["TyreLimit"]) if s.get("TyreLimit", 0) else None,
    )
