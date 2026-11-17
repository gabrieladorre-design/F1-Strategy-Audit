import numpy as np
import pandas as pd
import pytest

from strategy_audit.models.pace_model import fit_race, model_from_frames, models_to_frames
from strategy_audit.processing.clean import (
    actual_stints,
    dry_rounds,
    is_neutralised,
    prepare_laps,
    rounds_with_tyre_data,
)
from strategy_audit.simulation.simulator import (
    enumerate_strategies,
    is_feasible,
    lap_times,
    pit_loss_by_lap,
    strategy_cost,
)
from synthetic import TRUE_DEG, TRUE_FUEL, make_race, make_season


@pytest.fixture(scope="module")
def race1():
    laps, results, race = make_race(1)
    prepared = prepare_laps(laps, pd.DataFrame([race]))
    return prepared, results, race


def test_track_status():
    assert is_neutralised("14")
    assert is_neutralised("6")
    assert not is_neutralised("12")
    assert not is_neutralised(None)


def test_clean_excludes_lap1_and_pit_laps(race1):
    laps, _, _ = race1
    clean = laps[laps["IsClean"]]
    assert (clean["LapNumber"] > 1).all()
    assert not clean["IsPitIn"].any() and not clean["IsPitOut"].any()


def test_dry_rounds():
    laps, _, _ = make_race(1)
    wet = laps.copy()
    wet["Round"] = 2
    wet["Compound"] = "INTERMEDIATE"
    assert dry_rounds(pd.concat([laps, wet])) == [1]


def test_rounds_with_missing_tyre_data_are_dropped():
    laps, _, _ = make_race(1)
    broken = laps.copy()
    broken["Round"] = 2
    broken.loc[broken["LapNumber"] <= 20, "Compound"] = None   # como Miami 2025
    assert rounds_with_tyre_data(pd.concat([laps, broken])) == [1]


def test_pace_model_recovers_parameters(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    for c, d in TRUE_DEG.items():
        assert model.compound_deg[c] == pytest.approx(d, abs=0.02)
    assert model.fuel == pytest.approx(TRUE_FUEL, abs=0.01)
    assert model.mae_cv < 0.3


def test_model_roundtrip(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    rebuilt = model_from_frames(1, *models_to_frames([model]))
    assert rebuilt.compound_deg == pytest.approx(model.compound_deg)
    assert rebuilt.driver_base == pytest.approx(model.driver_base)


def test_strategy_rules(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    assert not is_feasible(model, [("HARD", 30), ("HARD", 30)], 1)   # un solo compuesto
    assert not is_feasible(model, [("SOFT", 3), ("HARD", 57)], 1)    # stint demasiado corto


def test_best_strategy_is_not_worse_than_actual(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    pls = pit_loss_by_lap(60, 21.0, set())
    best = enumerate_strategies(model, 60, 3, pls)[0]
    actual = strategy_cost(model, [("MEDIUM", 25), ("HARD", 35)], 3, pls)
    assert best.cost <= actual + 1e-9
    assert sum(n for _, n in best.stints) == 60


def test_lap_times_include_pit_loss(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    pls = pit_loss_by_lap(60, 21.0, set())
    t = lap_times(model, "VER", [("MEDIUM", 25), ("HARD", 35)], 3, pls)
    assert len(t) == 60
    assert t[24] - t[23] > 15


def test_sc_makes_stop_cheaper():
    pls = pit_loss_by_lap(60, 20.0, {30})
    assert pls[30] == pytest.approx(10.0)
    assert pls[10] == pytest.approx(20.0)


def test_actual_stints(race1):
    laps, _, _ = race1
    s = actual_stints(laps)
    ver = s[s["Driver"] == "VER"]
    assert list(ver["Laps"]) == [25, 35]
    assert ver["StartAge"].iloc[0] == 3


def test_full_pipeline(tmp_path):
    from strategy_audit.pipeline import run

    raw, out = tmp_path / "raw", tmp_path / "processed"
    make_season(raw)
    metrics = run(2025, raw_dir=raw, out_dir=out)
    assert metrics["dry_races_modelled"] == 2
    audit = pd.read_parquet(out / "audit_2025.parquet")
    assert len(audit) > 0
    assert (audit["StrategyDelta"] >= 0).all()
    assert np.isfinite(metrics["simulator_mae_s"])


def test_false_pit_stops_do_not_split_stints():
    """FastF1 a veces marca paradas falsas bajo SC al final: no deben crear stints nuevos."""
    laps, _, race = make_race(1)
    last = laps.index[(laps["Driver"] == "VER") & (laps["LapNumber"] >= 58)]
    laps.loc[last, "PitInTime"] = 1.0
    laps.loc[last, "PitOutTime"] = 1.0
    prepared = prepare_laps(laps, pd.DataFrame([race]))
    ver = actual_stints(prepared)
    assert list(ver.loc[ver["Driver"] == "VER", "Laps"]) == [25, 35]


def test_min_stops_rule(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    model.min_stops = 2
    pls = pit_loss_by_lap(60, 21.0, set())
    assert all(s.stops >= 2 for s in enumerate_strategies(model, 60, 3, pls))


def test_tyre_limit_rule(race1):
    laps, _, _ = race1
    model = fit_race(laps, 1)
    model.tyre_limit = 25
    pls = pit_loss_by_lap(60, 21.0, set())
    for s in enumerate_strategies(model, 60, 3, pls):
        ages = [(3 if i == 0 else 1) + n - 1 for i, (_, n) in enumerate(s.stints)]
        assert max(ages) <= 25
