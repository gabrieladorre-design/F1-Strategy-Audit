"""Enlaces que abren la app en una vista concreta.

Ejemplo: ``/?vista=carrera&gp=MON&piloto=VER`` abre el análisis del GP de Mónaco con
Verstappen destacado. Sirve para compartir un hallazgo o para ir directo a un gráfico
durante una presentación.
"""
from __future__ import annotations

from urllib.parse import parse_qs, urlencode

from strategy_audit.dashboard.data import Store

# Nombre de la pestaña en la URL (en español) ↔ valor interno de dcc.Tabs
TABS = {"carrera": "race", "ysi": "whatif", "temporada": "season", "metodologia": "method"}
TABS_INV = {v: k for k, v in TABS.items()}


def _round_from(value: str, store: Store) -> int | None:
    """Acepta la abreviatura del GP (``MON``) o el número de ronda (``8``)."""
    value = value.strip().upper()
    for rnd in store.audited_rounds:
        if store.race_abbr(rnd) == value or str(rnd) == value:
            return rnd
    return None


def parse_query(search: str | None, store: Store) -> dict:
    """Lee la URL y devuelve solo los parámetros válidos para estos datos."""
    if not search:
        return {}
    q = {k: v[0] for k, v in parse_qs(search.lstrip("?")).items() if v}
    out: dict = {}
    if q.get("vista", "").lower() in TABS:
        out["tab"] = TABS[q["vista"].lower()]
    if "gp" in q:
        rnd = _round_from(q["gp"], store)
        if rnd is not None:
            out["round"] = rnd
    if "piloto" in q and "round" in out:
        drv = q["piloto"].strip().upper()
        a = store.audit
        if ((a["Round"] == out["round"]) & (a["Driver"] == drv)).any():
            out["driver"] = drv
    if "equipo" in q:
        teams = {str(t).lower(): t for t in store.audit["Team"].dropna().unique()}
        team = teams.get(q["equipo"].strip().lower())
        if team:
            out["team"] = team
    return out


def build_query(store: Store, tab: str | None, rnd: int | None = None, driver: str | None = None,
                team: str | None = None) -> str:
    """Construye la parte ``?…`` del enlace para la vista actual."""
    params = {"vista": TABS_INV.get(tab or "race", "carrera")}
    if tab in ("race", "whatif") and rnd is not None:
        params["gp"] = store.race_abbr(rnd)
        if driver:
            params["piloto"] = driver
    if tab == "season" and team:
        params["equipo"] = team
    return "?" + urlencode(params)
