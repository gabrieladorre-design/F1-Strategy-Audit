"""Generador de carreras sintéticas con el mismo esquema que FastF1.

Permite probar el pipeline sin conexión y con parámetros conocidos.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

TRUE_DEG = {"SOFT": 0.12, "MEDIUM": 0.06, "HARD": 0.03}
TRUE_OFFSET = {"SOFT": -0.6, "MEDIUM": 0.0, "HARD": 0.4}
TRUE_FUEL = -0.05
PIT_LOSS = 21.0

DRIVERS = {
    "VER": ("Red Bull Racing", 90.0, [("MEDIUM", 25), ("HARD", 35)]),
    "NOR": ("McLaren", 90.1, [("MEDIUM", 22), ("HARD", 38)]),
    "LEC": ("Ferrari", 90.3, [("SOFT", 15), ("HARD", 25), ("MEDIUM", 20)]),
    "HAM": ("Ferrari", 90.4, [("HARD", 35), ("MEDIUM", 25)]),
    "RUS": ("Mercedes", 90.35, [("MEDIUM", 30), ("HARD", 30)]),
    "ALO": ("Aston Martin", 90.9, [("SOFT", 10), ("HARD", 50)]),
}


def make_race(rnd: int, total_laps: int = 60, sc_laps: tuple = (), seed: int = 0):
    rng = np.random.default_rng(seed + rnd)
    rows = []
    finish = {}
    for drv, (team, base, strat) in DRIVERS.items():
        # Ajusta el último stint a la distancia de la carrera
        strat = strat[:-1] + [(strat[-1][0], total_laps - sum(n for _, n in strat[:-1]))]
        t, lap = 0.0, 0
        for stint_i, (comp, n) in enumerate(strat, start=1):
            age0 = 3 if stint_i == 1 else 1
            for k in range(n):
                lap += 1
                lt = base + TRUE_OFFSET[comp] + TRUE_DEG[comp] * (age0 + k) + TRUE_FUEL * lap
                lt += rng.normal(0, 0.15)
                status = "1"
                if lap in sc_laps:
                    lt += 25
                    status = "4"
                if lap == 1:
                    lt += 5
                pit_in = k == n - 1 and stint_i < len(strat)
                pit_out = k == 0 and stint_i > 1
                if pit_in:
                    lt += PIT_LOSS * (0.5 if lap in sc_laps else 0.4)
                if pit_out:
                    lt += PIT_LOSS * (0.5 if lap - 1 in sc_laps else 0.6)
                t += lt
                rows.append({
                    "Round": rnd, "Driver": drv, "DriverNumber": "1", "Team": team,
                    "LapNumber": float(lap), "LapTime": lt, "Stint": float(stint_i),
                    "Compound": comp, "TyreLife": float(age0 + k), "FreshTyre": stint_i > 1,
                    "PitInTime": 1.0 if pit_in else np.nan, "PitOutTime": 1.0 if pit_out else np.nan,
                    "TrackStatus": status, "Position": np.nan, "Time": t, "LapStartTime": t - lt,
                    "Deleted": False, "IsAccurate": True,
                })
        finish[drv] = t
    laps = pd.DataFrame(rows)
    order = sorted(finish, key=finish.get)
    results = pd.DataFrame([{
        "Round": rnd, "Abbreviation": d, "DriverNumber": "1", "FullName": d,
        "TeamName": DRIVERS[d][0], "TeamColor": "3671C6", "GridPosition": float(i + 1),
        "Position": float(order.index(d) + 1), "ClassifiedPosition": str(order.index(d) + 1),
        "Status": "Finished", "Points": 0.0, "Time": finish[d],
    } for i, d in enumerate(DRIVERS)])
    race = {"Round": rnd, "EventName": f"Test GP {rnd}", "Country": "Testland", "Location": "Test",
            "Date": f"2025-0{rnd}-01", "TotalLaps": total_laps, "TrackTemp": 35.0, "AirTemp": 25.0,
            "Rainfall": False}
    return laps, results, race


def make_season(tmp_path, season: int = 2025):
    parts = [make_race(1), make_race(2, sc_laps=(30, 31, 32))]
    laps = pd.concat([p[0] for p in parts], ignore_index=True)
    results = pd.concat([p[1] for p in parts], ignore_index=True)
    races = pd.DataFrame([p[2] for p in parts])
    tmp_path.mkdir(parents=True, exist_ok=True)
    laps.to_parquet(tmp_path / f"laps_{season}.parquet", index=False)
    results.to_parquet(tmp_path / f"results_{season}.parquet", index=False)
    races.to_parquet(tmp_path / f"races_{season}.parquet", index=False)
    return laps, results, races
