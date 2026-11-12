"""Callbacks: conectan los controles con las figuras."""
from __future__ import annotations

import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, State, ctx, html, no_update

from strategy_audit.dashboard import figures as F
from strategy_audit.dashboard.data import Store
from strategy_audit.dashboard.layout import kpi
from strategy_audit.simulation.audit import driver_actual_strategy
from strategy_audit.simulation.simulator import is_feasible, lap_times, max_stint


def _fmt_delta(s: float) -> str:
    return f"{s:+.1f} s"


def register(app, store: Store) -> None:
    race_names = {r: store.race_name(r) for r in store.audited_rounds}

    # ------------------------------------------------------------------ Carrera
    @app.callback(
        Output("race-kpis", "children"), Output("race-stints", "figure"),
        Output("race-delta", "figure"), Output("race-deg", "figure"),
        Input("race-dd", "value"),
    )
    def update_race(rnd):
        if rnd is None:
            return [], F.empty(), F.empty(), F.empty()
        row = store.race_row(rnd)
        audit = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
        order = list(audit["Driver"])
        actual = store.stints[store.stints["Round"] == rnd]
        best = store.best_stints[store.best_stints["Round"] == rnd]
        neutral = store.neutralised_laps(rnd)
        model = store.model(rnd)
        worst = audit.loc[audit["StrategyDelta"].idxmax()]
        optimal_share = (audit["StrategyDelta"] < 1.0).mean()

        kpis = [
            kpi("Pérdida en boxes", f"{row['PitLoss']:.1f} s", "parada con bandera verde"),
            kpi("Vueltas con SC/VSC", f"{len(neutral)}", f"de {int(row['TotalLaps'])}"),
            kpi("Mayor pérdida", f"{worst['Driver']} · {worst['StrategyDelta']:.1f} s", worst["Team"] or ""),
            kpi("Estrategias casi óptimas", f"{optimal_share:.0%}", "pilotos a menos de 1 s de la mejor"),
        ]
        laps = store.laps[store.laps["Round"] == rnd]
        return (kpis,
                F.stint_comparison(actual, best, order, neutral, int(row["TotalLaps"])),
                F.delta_bars(audit), F.degradation(laps, model))

    # ------------------------------------------------------------------ ¿Y si…?
    @app.callback(
        Output("wi-driver", "options"), Output("wi-driver", "value"),
        Input("wi-race", "value"), State("wi-driver", "value"),
    )
    def update_drivers(rnd, current):
        a = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
        opts = [{"label": f"P{int(p)} · {d} ({t})", "value": d}
                for d, t, p in zip(a["Driver"], a["Team"], a["AuditedPosition"])]
        drivers = list(a["Driver"])
        if current in drivers:
            return opts, current
        # Por defecto, el piloto al que más le costó la estrategia: el caso más interesante
        return opts, a.loc[a["StrategyDelta"].idxmax(), "Driver"] if len(a) else None

    @app.callback(
        Output("wi-stops", "value"), Output("wi-c1", "value"), Output("wi-c2", "value"),
        Output("wi-c3", "value"), Output("wi-s1", "value"), Output("wi-s2", "value"),
        Output("wi-s1", "max"), Output("wi-s2", "max"),
        Input("wi-driver", "value"), Input("wi-reset", "n_clicks"), Input("wi-best", "n_clicks"),
        State("wi-race", "value"),
    )
    def load_strategy(driver, _reset, _best, rnd):
        if driver is None or rnd is None:
            return (no_update,) * 8
        total = int(store.race_row(rnd)["TotalLaps"])
        if ctx.triggered_id == "wi-best":
            b = store.best_stints
            b = b[(b["Round"] == rnd) & (b["Driver"] == driver)].sort_values("Stint")
            stints = list(zip(b["Compound"], b["Laps"].astype(int)))
        else:
            stints, _ = driver_actual_strategy(store.stints, rnd, driver)
        stints = stints[:3] if len(stints) <= 3 else stints[:2] + [(stints[2][0], sum(n for _, n in stints[2:]))]
        stops = min(max(len(stints) - 1, 1), 2)
        comps = [c for c, _ in stints] + ["HARD"] * 3
        cuts = list(np.cumsum([n for _, n in stints])[:-1]) + [total - 10]
        s1 = int(cuts[0])
        s2 = int(cuts[1]) if stops == 2 else min(s1 + 15, total - 5)
        return stops, comps[0], comps[1], comps[2] if stops == 2 else "MEDIUM", s1, s2, total - 1, total - 1

    @app.callback(
        Output("wi-c3-wrap", "style"), Output("wi-s2-wrap", "style"), Input("wi-stops", "value"),
    )
    def toggle_second_stop(stops):
        style = {} if stops == 2 else {"display": "none"}
        return style, style

    @app.callback(
        Output("wi-kpis", "children"), Output("wi-gap", "figure"), Output("wi-laps", "figure"),
        Output("wi-warning", "children"),
        Input("wi-stops", "value"), Input("wi-c1", "value"), Input("wi-c2", "value"), Input("wi-c3", "value"),
        Input("wi-s1", "value"), Input("wi-s2", "value"),
        State("wi-race", "value"), State("wi-driver", "value"),
    )
    def simulate(stops, c1, c2, c3, s1, s2, rnd, driver):
        if None in (rnd, driver, c1, c2, s1):
            return [], F.empty(), F.empty(), ""
        model = store.model(rnd)
        total = int(store.race_row(rnd)["TotalLaps"])
        pls = store.pit_losses(rnd)
        actual, first_age = driver_actual_strategy(store.stints, rnd, driver)

        if stops == 2:
            if s2 is None or s2 <= s1:
                return [], F.empty("La 2ª parada debe ser posterior a la 1ª"), F.empty(), \
                    "La 2ª parada debe ser posterior a la 1ª."
            alt = [(c1, s1), (c2, s2 - s1), (c3, total - s2)]
        else:
            alt = [(c1, s1), (c2, total - s1)]

        warnings = []
        if any(c not in model.compound_deg for c, _ in alt):
            missing = [c for c, _ in alt if c not in model.compound_deg]
            return [], F.empty("Compuesto no usado en esta carrera"), F.empty(), \
                f"Nadie usó {', '.join(missing).lower()} en esta carrera: no hay datos para modelarlo."
        if not is_feasible(model, alt, first_age):
            if len({c for c, _ in alt}) < 2:
                warnings.append("El reglamento obliga a usar al menos dos compuestos de seco.")
            for i, (c, n) in enumerate(alt):
                age0 = first_age if i == 0 else 1
                if age0 + n - 1 > max_stint(model, c):
                    warnings.append(f"Stint {i + 1}: {n} vueltas con {c.lower()} supera lo observado en carrera "
                                    f"({max_stint(model, c)}); el modelo extrapola.")
                if n < 5:
                    warnings.append(f"Stint {i + 1} demasiado corto ({n} vueltas).")

        sim_alt = lap_times(model, driver, alt, first_age, pls)
        sim_real = lap_times(model, driver, actual, first_age, pls)
        gap = np.cumsum(sim_alt - sim_real)
        diff = float(gap[-1])

        a = store.audit[(store.audit["Round"] == rnd)]
        me = a[a["Driver"] == driver].iloc[0]
        t = me["FinishTime"] + diff
        est = int((a.loc[a["Driver"] != driver, "FinishTime"] < t).sum()) + 1
        real_pos = int(me["AuditedPosition"])
        pos_txt = f"P{real_pos} → P{est}"

        kpis = [
            kpi("Alternativa frente a la real", _fmt_delta(diff),
                "más rápida" if diff < 0 else ("más lenta" if diff > 0 else "igual")),
            kpi("Posición estimada", pos_txt, "frente a los tiempos reales de los rivales"),
            kpi("Strategy Delta del piloto", f"{me['StrategyDelta']:.1f} s", f"mejor: {me['BestStrategy']}"),
        ]
        stops_alt = list(np.cumsum([n for _, n in alt])[:-1])
        stops_real = list(np.cumsum([n for _, n in actual])[:-1])
        real_laps = store.laps[(store.laps["Round"] == rnd) & (store.laps["Driver"] == driver)]
        mask_alt = np.isin(np.arange(1, total + 1), stops_alt)
        mask_real = np.isin(np.arange(1, total + 1), stops_real)
        warn = html.Ul([html.Li(w) for w in warnings]) if warnings else ""
        return (kpis, F.whatif_gap(gap, stops_alt, stops_real),
                F.whatif_laps(real_laps, sim_alt, sim_real, mask_alt, mask_real), warn)

    # ------------------------------------------------------------------ Temporada
    @app.callback(
        Output("season-teams", "figure"), Output("season-positions", "figure"),
        Output("season-evolution", "figure"), Output("season-heatmap", "figure"),
        Input("tabs", "value"),
    )
    def update_season(tab):
        if tab != "season":
            return (no_update,) * 4
        a = store.audit
        pos = (a.groupby("Driver").agg(P=("PositionsLost", "sum"), Team=("Team", "first"))
               .query("P > 0").sort_values("P").tail(12))
        fig_pos = go.Figure(go.Bar(
            x=pos["P"], y=pos.index, orientation="h", marker=dict(color=F.ACCENT, cornerradius=4),
            text=pos["P"], textposition="outside", textfont=dict(color=F.TEXT_2), customdata=pos["Team"],
            hovertemplate="<b>%{y}</b> · %{customdata}<br>%{x} posiciones<extra></extra>",
        ))
        fig_pos.update_xaxes(title_text="Posiciones perdidas por estrategia (temporada)")
        fig_pos = F._base(fig_pos, height=max(360, 30 * len(pos) + 80))
        return (F.team_ranking(a), fig_pos, F.team_evolution(a, race_names), F.season_heatmap(a, race_names))
