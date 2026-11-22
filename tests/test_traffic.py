"""Modelo de tráfico: atasco detrás de un coche lento según lo difícil que sea adelantar."""
import numpy as np
import pandas as pd

from strategy_audit.simulation.traffic import DELTA_DEFAULT, build_traffic, simulate_traffic


def _race(n=20):
    """SLO va siempre a 90 s; FAS (el estudiado) sale 1 s detrás tras la vuelta 1."""
    rows = []
    for lap in range(1, n + 1):
        rows.append({"Driver": "SLO", "LapNumber": lap, "LapTime": 90.0, "IsPitIn": False, "Predicted": 90.0})
        rows.append({"Driver": "FAS", "LapNumber": lap, "LapTime": 91.0 if lap == 1 else 90.0,
                     "IsPitIn": False, "Predicted": 89.0})
    return pd.DataFrame(rows)


def test_stuck_behind_slower_car_when_overtaking_is_hard():
    laps = _race()
    clean = np.full(20, 89.0)            # FAS es 1 s/vuelta más rápido en aire limpio
    no_pit = np.zeros(20)
    hard = build_traffic(laps, set(), overtake_delta=2.0)     # hace falta 2 s/vuelta: no puede pasar
    easy = build_traffic(laps, set(), overtake_delta=0.5)     # con 0,5 s le basta
    stuck = simulate_traffic(hard, "FAS", clean, no_pit)
    free = simulate_traffic(easy, "FAS", clean, no_pit)
    assert stuck.loss > 15 and stuck.held_laps >= 18          # pierde ~1 s en cada vuelta
    assert free.loss < 1.0                                    # adelanta y va a su ritmo


def test_no_traffic_under_safety_car_and_rejoin_info():
    laps = _race()
    clean = np.full(20, 89.0)
    pit = np.zeros(20)
    pit[9] = 22.0                                             # para al final de la vuelta 10
    tr = build_traffic(laps, set(range(2, 21)), overtake_delta=2.0)   # toda la carrera neutralizada
    assert simulate_traffic(tr, "FAS", clean, pit).loss == 0
    tr = build_traffic(laps, set(), overtake_delta=2.0)
    res = simulate_traffic(tr, "FAS", clean, pit)
    assert res.lost_by_lap.sum() == res.loss


def test_calibration_falls_back_with_few_situations():
    tr = build_traffic(_race(), set())
    assert tr.overtake_delta == DELTA_DEFAULT and tr.situations < 30
