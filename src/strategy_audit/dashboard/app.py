"""Creación de la aplicación Dash."""
from __future__ import annotations

from dash import Dash

from strategy_audit.config import ROOT, SEASON
from strategy_audit.dashboard import callbacks
from strategy_audit.dashboard.data import load_store
from strategy_audit.dashboard.layout import build_layout


def create_app(season: int = SEASON) -> Dash:
    store = load_store(season)
    app = Dash(
        __name__,
        title="F1 Strategy Audit",
        assets_folder=str(ROOT / "assets"),
        suppress_callback_exceptions=True,
    )
    app.layout = build_layout(store)
    if store is not None and store.audited_rounds:
        callbacks.register(app, store)
    return app
