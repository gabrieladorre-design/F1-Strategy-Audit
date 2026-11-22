"""Creación de la aplicación Dash."""
from __future__ import annotations

from dash import Dash

from strategy_audit.config import ROOT, SEASON
from strategy_audit.dashboard import callbacks
from strategy_audit.dashboard.data import load_store
from strategy_audit.dashboard.layout import build_layout

APP_URL = "https://f1-strategy-audit.onrender.com/"
DESCRIPTION = ("¿Ganó o perdió tiempo cada piloto por su estrategia? Auditoría de paradas y neumáticos "
               "de la temporada 2025 de Fórmula 1 con un modelo de ritmo y un simulador de estrategias.")

# Plantilla HTML: página en español (el navegador no ofrece traducirla), icono propio y
# metadatos Open Graph para que el enlace se vea con imagen al compartirlo en LinkedIn o WhatsApp.
INDEX = f"""<!DOCTYPE html>
<html lang="es">
    <head>
        {{%metas%}}
        <title>{{%title%}}</title>
        <link rel="icon" type="image/svg+xml" href="/assets/favicon.svg">
        <meta name="description" content="{DESCRIPTION}">
        <meta name="theme-color" content="#C8102E">
        <meta property="og:type" content="website">
        <meta property="og:title" content="F1 Strategy Audit">
        <meta property="og:description" content="{DESCRIPTION}">
        <meta property="og:url" content="{APP_URL}">
        <meta property="og:image" content="{APP_URL}assets/preview.png">
        <meta property="og:image:width" content="1200">
        <meta property="og:image:height" content="630">
        <meta property="og:locale" content="es_ES">
        <meta name="twitter:card" content="summary_large_image">
        {{%css%}}
    </head>
    <body>
        {{%app_entry%}}
        <footer>
            {{%config%}}
            {{%scripts%}}
            {{%renderer%}}
        </footer>
    </body>
</html>"""


def create_app(season: int = SEASON) -> Dash:
    store = load_store(season)
    app = Dash(
        __name__,
        title="F1 Strategy Audit",
        assets_folder=str(ROOT / "assets"),
        suppress_callback_exceptions=True,
        index_string=INDEX,
    )
    app.layout = build_layout(store)
    if store is not None and store.audited_rounds:
        callbacks.register(app, store)
    return app
