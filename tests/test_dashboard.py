"""Pruebas de humo del dashboard: la app arranca y las figuras se generan."""
import pytest

from synthetic import make_season


@pytest.fixture(scope="module")
def store(tmp_path_factory, monkeypatch_module):
    from strategy_audit.dashboard import data
    from strategy_audit.pipeline import run

    base = tmp_path_factory.mktemp("data")
    make_season(base / "raw")
    run(2025, raw_dir=base / "raw", out_dir=base / "processed")
    monkeypatch_module.setattr(data, "PROCESSED_DIR", base / "processed")
    data.load_store.cache_clear()
    return data.load_store(2025)


@pytest.fixture(scope="module")
def monkeypatch_module():
    mp = pytest.MonkeyPatch()
    yield mp
    mp.undo()


def test_store_loads(store):
    assert store is not None
    assert store.audited_rounds == [1, 2]
    assert store.neutralised_laps(2) == {30, 31, 32}


def test_figures(store):
    from strategy_audit.dashboard import figures as F

    rnd = 1
    audit = store.audit[store.audit["Round"] == rnd]
    fig = F.stint_comparison(store.stints[store.stints["Round"] == rnd],
                             store.best_stints[store.best_stints["Round"] == rnd],
                             list(audit["Driver"]), set(), 60)
    assert len(fig.data) > 0
    assert len(F.delta_bars(audit).data) == 1
    assert len(F.degradation(store.laps[store.laps["Round"] == rnd], store.model(rnd)).data) >= 5
    assert len(F.team_ranking(store.audit).data) >= 2
    assert len(F.team_ranking(store.audit, focus="Ferrari").data) >= 2
    names = {r: f"GP {r}" for r in store.audited_rounds}
    assert len(F.team_evolution(store.audit, names, names).data) > 0
    assert len(F.season_heatmap(store.audit, names, names).data) == 1
    assert len(F.positions_lost(store.audit).data) == 1
    laps = store.laps[store.laps["Round"] == rnd]
    assert len(F.race_trace(laps, audit, store.stints[store.stints["Round"] == rnd], set(), 60).data) > 0
    assert len(F.residuals_by_compound(store.laps).data) >= 1
    assert len(F.model_error_by_race(store.races, names, names).data) > 0


def test_pit_window(store):
    import numpy as np
    from strategy_audit.dashboard import figures as F
    from strategy_audit.simulation.audit import driver_actual_strategy

    rnd = 1
    model = store.model(rnd)
    driver = store.audit[store.audit["Round"] == rnd]["Driver"].iloc[0]
    _, first_age = driver_actual_strategy(store.stints, rnd, driver)
    win = F.pit_window_curves(model, 60, first_age, store.pit_losses(rnd))
    assert win["curves"], "debe haber al menos una combinación de 1 parada factible"
    # El mínimo global de las curvas nunca es mejor que el óptimo (la referencia es 0)
    assert min(np.nanmin(c) for c in win["curves"].values()) >= -1e-9
    assert len(F.pit_window(win, next(iter(win["curves"])), 20, None).data) > 0
    comps = tuple(model.usable_compounds[:2]) + (model.usable_compounds[0],)
    fig, info = F.pit_window_2stop(model, 60, first_age, store.pit_losses(rnd), comps, (15, 35))
    assert len(fig.data) > 0


def test_bootstrap_ci():
    import numpy as np
    from strategy_audit.dashboard.figures import bootstrap_ci

    v = np.arange(100, dtype=float)
    lo, hi = bootstrap_ci(v)
    assert lo < v.mean() < hi
    assert bootstrap_ci(np.array([3.0])) == (3.0, 3.0)


def test_theme_format():
    from strategy_audit.dashboard.theme import fmt_deg, fmt_lap, fmt_s, team_color

    assert fmt_s(8.43) == "8,4 s"
    assert fmt_s(-2.0, signed=True) == "−2,0 s"
    assert fmt_lap(92.481) == "1:32,481"
    assert fmt_deg(0.085) == "+0,085 s/vuelta"
    # Un color muy claro se oscurece para que contraste sobre blanco
    assert team_color("#FFFFFF") != "#FFFFFF"
    assert team_color("#E8002D") == "#E8002D"


def test_app_builds(store):
    from strategy_audit.dashboard.app import create_app

    app = create_app(2025)
    assert app.layout is not None
    assert len(app.callback_map) >= 5
