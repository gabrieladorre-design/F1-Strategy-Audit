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
    assert len(F.degradation(store.laps[store.laps["Round"] == rnd], store.model(rnd)).data) == 6
    assert len(F.team_ranking(store.audit).data) == 1


def test_app_builds(store):
    from strategy_audit.dashboard.app import create_app

    app = create_app(2025)
    assert app.layout is not None
    assert len(app.callback_map) >= 5
