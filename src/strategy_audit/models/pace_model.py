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


def _fit(df: pd.DataFrame) -> tuple[list[str], list[str], str, np.ndarray]:
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
        test = test[test["Driver"].isin(model.driver_base) & test["Compound"].isin(model.compound_deg)]
        if len(test):
            errors.append(np.abs(model.predict(test) - test["LapTime"].to_numpy()))
    return float(np.concatenate(errors).mean()) if errors else float("nan")


def fit_race(clean: pd.DataFrame, rnd: int) -> RaceModel:
    """Ajusta el modelo de una carrera con sus vueltas limpias."""
    df = clean[(clean["Round"] == rnd) & clean["IsClean"]]
    if len(df) < 50:
        raise ValueError(f"Muy pocas vueltas limpias en la carrera {rnd}: {len(df)}")
    model = _unpack(rnd, *_fit(df))
    model.n_laps = len(df)
    model.mae_train = float(np.abs(model.predict(df) - df["LapTime"]).mean())
    model.mae_cv = _cv_mae(df)
    # Longitud máxima de stint observada por compuesto: el simulador no extrapola más allá
    model.max_stint = {c: int(v) for c, v in df.groupby("Compound")["TyreLife"].max().items()}
    return model


def models_to_frames(models: list[RaceModel]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convierte los modelos a tablas (piloto, compuesto y resumen por carrera)."""
    drivers, compounds, summary = [], [], []
    for m in models:
        drivers += [{"Round": m.round, "Driver": d, "Base": b} for d, b in m.driver_base.items()]
        compounds += [
            {"Round": m.round, "Compound": c, "Offset": m.compound_offset[c],
             "Deg": m.compound_deg[c], "MaxStint": m.max_stint.get(c, 0)}
            for c in m.compound_deg
        ]
        summary.append({"Round": m.round, "Fuel": m.fuel, "ReferenceCompound": m.reference_compound,
                        "MAE_train": m.mae_train, "MAE_cv": m.mae_cv, "CleanLaps": m.n_laps})
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
    )
