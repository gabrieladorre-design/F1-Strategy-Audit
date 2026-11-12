"""Estimación empírica del tiempo perdido en una parada con bandera verde.

Para cada parada: (vuelta de entrada + vuelta de salida) − ritmo predicho por el
modelo para esas dos vueltas. Se toma la mediana de las paradas con bandera
verde de la carrera, que es robusta a paradas lentas o problemas puntuales.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_audit.models.pace_model import RaceModel

DEFAULT_PIT_LOSS = 22.0      # s, valor de respaldo si no hay paradas válidas
SC_PIT_LOSS_FACTOR = 0.5     # con SC/VSC se pierde aproximadamente la mitad
MIN_PIT_LOSS, MAX_PIT_LOSS = 12.0, 40.0


def estimate_pit_loss(laps: pd.DataFrame, model: RaceModel) -> float:
    rnd = model.round
    df = laps[(laps["Round"] == rnd) & laps["Driver"].isin(model.driver_base)].copy()
    df = df[df["Compound"].isin(model.compound_deg) & df["TyreLife"].notna()]
    df["Pred"] = model.predict(df)
    df = df.set_index(["Driver", "LapNumber"])

    losses = []
    for (drv, lap), row in df[df["IsPitIn"]].iterrows():
        out_key = (drv, lap + 1)
        if out_key not in df.index:
            continue
        out = df.loc[out_key]
        if row["Neutralised"] or out["Neutralised"] or pd.isna(row["LapTime"]) or pd.isna(out["LapTime"]):
            continue
        # El ritmo esperado de la vuelta de salida se calcula como si fuera con neumático nuevo
        loss = (row["LapTime"] - row["Pred"]) + (out["LapTime"] - out["Pred"])
        if MIN_PIT_LOSS <= loss <= MAX_PIT_LOSS:
            losses.append(loss)
    return float(np.median(losses)) if losses else DEFAULT_PIT_LOSS
