"""Auditoría de estrategias: Strategy Delta por piloto y carrera.

Strategy Delta = tiempo simulado con la estrategia real − tiempo simulado con la
mejor estrategia encontrada (segundos, ≥ 0). Se comparan dos simulaciones con el
mismo modelo, de modo que el error del modelo afecta por igual a ambas y el delta
mide solo el efecto de la decisión estratégica.

Es una auditoría «a posteriori»: la mejor estrategia conoce cuándo hubo Safety Car.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategy_audit.models.pace_model import RaceModel
from strategy_audit.simulation.simulator import (
    Strategy,
    enumerate_strategies,
    pit_loss_by_lap,
    strategy_cost,
)


def driver_actual_strategy(stints: pd.DataFrame, rnd: int, driver: str) -> tuple[list[tuple[str, int]], int]:
    s = stints[(stints["Round"] == rnd) & (stints["Driver"] == driver)].sort_values("Stint")
    return list(zip(s["Compound"], s["Laps"].astype(int))), int(s["StartAge"].iloc[0])


def audit_race(model: RaceModel, laps: pd.DataFrame, stints: pd.DataFrame, results: pd.DataFrame,
               pit_loss: float, neutralised: set[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (auditoría por piloto, stints óptimos) de una carrera."""
    rnd = model.round
    race_laps = laps[laps["Round"] == rnd]
    total_laps = int(race_laps["LapNumber"].max())
    pls = pit_loss_by_lap(total_laps, pit_loss, neutralised)
    res = results[results["Round"] == rnd].set_index("Abbreviation")

    # Instante en que cada piloto cruza la meta (tiempo de sesión de su última vuelta)
    finish = race_laps.groupby("Driver").agg(LastLap=("LapNumber", "max"), Finish=("Time", "max"))

    rows, best_rows = [], []
    for drv in model.driver_base:
        if drv not in finish.index:
            continue
        status = str(res.loc[drv, "Status"]) if drv in res.index else ""
        driver_laps = int(finish.loc[drv, "LastLap"])
        # Pilotos clasificados: en la distancia completa o doblados («+1 Lap», «Lapped»)
        finished = status == "Finished" or "Lap" in status
        if not finished or driver_laps < total_laps - 3:
            continue
        actual, first_age = driver_actual_strategy(stints, rnd, drv)
        if any(c not in model.compound_deg for c, _ in actual) or sum(n for _, n in actual) != driver_laps:
            continue
        candidates = enumerate_strategies(model, driver_laps, first_age, pls)
        if not candidates:
            continue
        best = candidates[0]
        act = Strategy(actual, strategy_cost(model, actual, first_age, pls))
        delta = max(act.cost - best.cost, 0.0)

        r = res.loc[drv] if drv in res.index else None
        rows.append({
            "Round": rnd, "Driver": drv,
            "FullName": r["FullName"] if r is not None else drv,
            "Team": r["TeamName"] if r is not None else None,
            "TeamColor": ("#" + str(r["TeamColor"])) if r is not None and pd.notna(r["TeamColor"]) else "#888888",
            "GridPosition": r["GridPosition"] if r is not None else np.nan,
            "Position": r["Position"] if r is not None else np.nan,
            "ActualStrategy": act.label(), "ActualStops": act.stops,
            "BestStrategy": best.label(), "BestStops": best.stops,
            "StrategyDelta": round(delta, 2),
            "FinishTime": float(finish.loc[drv, "Finish"]),
            "LapsCompleted": driver_laps,
            "FirstAge": first_age,
        })
        lap = 0
        for i, (c, n) in enumerate(best.stints):
            best_rows.append({"Round": rnd, "Driver": drv, "Stint": i + 1, "Compound": c,
                              "StartLap": lap + 1, "EndLap": lap + n, "Laps": n})
            lap += n

    audit = pd.DataFrame(rows)
    if not audit.empty:
        audit = _estimate_positions(audit)
    return audit, pd.DataFrame(best_rows)


def _estimate_positions(audit: pd.DataFrame) -> pd.DataFrame:
    """Posición estimada con la mejor estrategia frente a los tiempos reales de los rivales."""
    audit = audit.copy()
    # Orden de llegada: más vueltas primero y, a igualdad de vueltas, menor tiempo
    key = list(zip(-audit["LapsCompleted"], audit["FinishTime"]))
    est = []
    for i, row in audit.iterrows():
        mine = (-row["LapsCompleted"], row["FinishTime"] - row["StrategyDelta"])
        ahead = sum(1 for j, k in zip(audit.index, key) if j != i and k < mine)
        est.append(ahead + 1)
    audit["EstPosition"] = est
    # Posición real entre los pilotos auditados (mismo universo que la estimada)
    audit["AuditedPosition"] = [sum(1 for k2 in key if k2 < k) + 1 for k in key]
    audit["PositionsLost"] = audit["AuditedPosition"] - audit["EstPosition"]
    return audit


def validate_simulator(model: RaceModel, laps: pd.DataFrame, stints: pd.DataFrame,
                       pit_loss: float) -> pd.DataFrame:
    """Compara el tiempo total simulado con la estrategia real frente al real.

    Solo se usa en carreras sin neutralizaciones. La vuelta 1 (salida) no se
    modela, así que se toma la real en ambos lados.
    """
    rnd = model.round
    race = laps[laps["Round"] == rnd]
    total_laps = int(race["LapNumber"].max())
    pls = pit_loss_by_lap(total_laps, pit_loss, set())
    out = []
    for drv in model.driver_base:
        dl = race[race["Driver"] == drv].sort_values("LapNumber")
        if len(dl) < total_laps or dl["LapTime"].isna().any():
            continue
        s = stints[(stints["Round"] == rnd) & (stints["Driver"] == drv)].sort_values("Stint")
        if any(c not in model.compound_deg for c in s["Compound"]):
            continue
        # Respeta la edad real de inicio de cada stint
        sim = _sim_actual_total(model, drv, s, pls)
        sim += dl["LapTime"].iloc[0] - _pred_lap(model, drv, s.iloc[0]["Compound"], int(s.iloc[0]["StartAge"]), 1)
        real = dl["LapTime"].sum()
        out.append({"Round": rnd, "Driver": drv, "SimTotal": sim, "RealTotal": real, "Error": sim - real})
    return pd.DataFrame(out)


def _pred_lap(model: RaceModel, drv: str, c: str, age: int, lap: int) -> float:
    return (model.driver_base[drv] + model.compound_offset[c]
            + max(model.compound_deg[c], 0.0) * age + model.fuel * lap)


def _sim_actual_total(model: RaceModel, drv: str, s: pd.DataFrame, pls: np.ndarray) -> float:
    total, lap = 0.0, 0
    for i, st in enumerate(s.itertuples()):
        for k in range(int(st.Laps)):
            lap += 1
            total += _pred_lap(model, drv, st.Compound, int(st.StartAge) + k, lap)
        if i < len(s) - 1:
            total += pls[lap]
    return total
