"""Callbacks: conectan los controles con las figuras y generan los títulos-conclusión."""
from __future__ import annotations

import numpy as np
from dash import Input, Output, State, ctx, dcc, html, no_update

from strategy_audit.dashboard import figures as F
from strategy_audit.dashboard.data import Store
from strategy_audit.dashboard.layout import kpi
from strategy_audit.dashboard.links import build_query, parse_query
from strategy_audit.dashboard.theme import COMPOUND_ES, fmt_deg, fmt_pct, fmt_pos, fmt_s
from strategy_audit.simulation.audit import driver_actual_strategy
from strategy_audit.simulation.simulator import is_feasible, lap_times, max_stint, strategy_cost


def _surname(full_name: str) -> str:
    parts = str(full_name).split()
    return parts[-1] if parts else str(full_name)


def _warning(items: list[str]):
    if not items:
        return ""
    return html.Div(className="warning", children=html.Ul([html.Li(w) for w in items]))


def _trace_texts(audit, laps, focus, gp) -> tuple[str, str]:
    """Título-conclusión y subtítulo del gráfico de evolución de carrera."""
    a = audit.set_index("Driver")
    winner = a["AuditedPosition"].idxmin()
    lead = a[a["LapsCompleted"] == a["LapsCompleted"].max()].sort_values("FinishTime")
    if focus in a.index and focus != winner:
        me = a.loc[focus]
        if me["LapsCompleted"] < a.loc[winner, "LapsCompleted"]:
            behind = int(a.loc[winner, "LapsCompleted"] - me["LapsCompleted"])
            title = (f"{_surname(me['FullName'])} acabó {fmt_pos(me['AuditedPosition'])}, "
                     f"a {behind} vuelta{'s' if behind > 1 else ''} del ganador")
        else:
            title = (f"{_surname(me['FullName'])} acabó {fmt_pos(me['AuditedPosition'])}, "
                     f"a {fmt_s(me['FinishTime'] - a.loc[winner, 'FinishTime'])} de "
                     f"{_surname(a.loc[winner, 'FullName'])}")
    elif len(lead) > 1:
        margin = float(lead["FinishTime"].iloc[1] - lead["FinishTime"].iloc[0])
        title = (f"{_surname(a.loc[winner, 'FullName'])} ganó el {gp} con {fmt_s(margin)} "
                 f"sobre {_surname(lead['FullName'].iloc[1])}")
    else:
        title = f"{_surname(a.loc[winner, 'FullName'])} ganó el {gp}"
    sub = ("Diferencia con el ritmo medio del ganador (s) · subir = más rápido que él, "
           "cada escalón es una parada (círculo = neumático montado)")
    return title, sub


def _window(model, laps_done, first_age, pls, alt, actual, penalty=None, best_total=None):
    """Ventana de parada: curvas (1 parada) o mapa de calor (2 paradas) para los compuestos elegidos.

    Con ``penalty`` cada punto incluye el tiempo perdido en tráfico al salir de boxes.
    """
    tol = 1.0
    if len(alt) == 2:
        win = F.pit_window_curves(model, laps_done, first_age, pls, penalty, best_total)
        pair = (alt[0][0], alt[1][0])
        real_stop = actual[0][1] if len(actual) == 2 else None
        fig = F.pit_window(win, pair, alt[0][1], real_stop, tol)
        curve = win["curves"].get(pair)
        rng = F.window_range(curve, tol)
        label = f"{COMPOUND_ES[pair[0]]} → {COMPOUND_ES[pair[1]]}".lower().capitalize()
        if rng is None:
            title = f"{label} no es una estrategia factible a 1 parada en esta carrera"
        else:
            best_lap = int(np.nanargmin(curve))
            title = (f"{label}: parar entre las vueltas {rng[0]} y {rng[1]} cuesta menos de "
                     f"{fmt_s(tol, dec=0)} más que hacerlo en la {best_lap}")
        sub = ("Tiempo perdido frente a la mejor estrategia simulada (s) según la vuelta de parada, "
               "con el tráfico al salir de boxes · una curva por combinación de compuestos · ✕ = tu parada")
        return fig, title, sub
    comps = tuple(c for c, _ in alt)
    stops = tuple(int(x) for x in np.cumsum([n for _, n in alt])[:-1])
    fig, info = F.pit_window_2stop(model, laps_done, first_age, pls, comps, stops, best_total, penalty)
    label = " → ".join(COMPOUND_ES[c] for c in comps).lower().capitalize()
    if not info["ok"]:
        return fig, f"{label} no es factible a 2 paradas en esta carrera", ""
    i, j = info["best"]
    title = (f"Con {label.lower()}, lo mejor era parar en las vueltas {i} y {j} "
             f"({fmt_s(info['loss'], signed=True)} frente al óptimo global)")
    sub = ("Tiempo perdido frente a la mejor estrategia simulada (s) para cada par de vueltas de parada, "
           "con el tráfico al salir de boxes · contorno: a menos de 1 s de ese mínimo · ✕ = tu estrategia")
    return fig, title, sub


def _traffic_note(alt, real) -> str:
    """Detrás de quién sale tras la primera parada que le deja en tráfico, y comparación con la real."""
    parts = []
    if alt.rejoins:
        lap, cars, gap = alt.rejoins[0]
        who = ", ".join(cars[:3])
        parts.append(f"tras parar en la V{lap} sale detrás de {who} (a {fmt_s(gap)})")
    parts.append(f"real: {fmt_s(real.loss)}")
    return " · ".join(parts)


def _from_link(params, tab, rnd, drivers):
    """Piloto indicado en el enlace compartido, si corresponde a esta pestaña y carrera."""
    p = params or {}
    if p.get("tab", "race") == tab and p.get("round") == rnd and p.get("driver") in drivers:
        return p["driver"]
    return None


CSV_COLUMNS = {
    "Driver": "Piloto", "FullName": "Nombre", "Team": "Equipo", "GridPosition": "Parrilla",
    "Position": "Posición oficial", "AuditedPosition": "Posición entre auditados",
    "EstPosition": "Posición con la mejor estrategia", "PositionsLost": "Posiciones perdidas",
    "ActualStrategy": "Estrategia real", "BestStrategy": "Mejor estrategia simulada",
    "ActualStops": "Paradas reales", "BestStops": "Paradas óptimas",
    "StrategyDelta": "Strategy Delta (s)", "LapsCompleted": "Vueltas",
}


def race_csv(store: Store, rnd: int):
    """Tabla de auditoría de una carrera, con columnas en español, para descargar."""
    a = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
    out = a[list(CSV_COLUMNS)].copy()
    for col in ("GridPosition", "Position"):
        out[col] = out[col].astype("Int64")
    out = out.rename(columns=CSV_COLUMNS)
    out.insert(0, "Gran Premio", store.race_es(rnd))
    return out


def register(app, store: Store) -> None:
    race_names = {r: store.race_es(r) for r in store.audited_rounds}
    race_abbr = {r: store.race_abbr(r) for r in store.audited_rounds}

    # ------------------------------------------------------------------ Enlaces y descarga
    @app.callback(
        Output("url-params", "data"), Output("tabs", "value"), Output("race-dd", "value"),
        Output("wi-race", "value"), Output("season-focus", "value"),
        Input("url", "search"),
    )
    def apply_url(search):
        """Al abrir un enlace compartido, coloca la app en la vista que indica la URL."""
        p = parse_query(search, store)
        if not p:
            return {}, no_update, no_update, no_update, no_update
        rnd = p.get("round", no_update)
        return (p, p.get("tab", no_update), rnd if p.get("tab", "race") == "race" else no_update,
                rnd if p.get("tab") == "whatif" else no_update, p.get("team", no_update))

    @app.callback(
        Output("share-copy", "content"), Input("share-copy", "n_clicks"),
        State("url", "href"), State("tabs", "value"), State("race-dd", "value"),
        State("race-focus", "value"), State("wi-race", "value"), State("wi-driver", "value"),
        State("season-focus", "value"), prevent_initial_call=True,
    )
    def share_link(_, href, tab, race, focus, wi_race, wi_driver, team):
        base = (href or "").split("?")[0]
        if tab == "whatif":
            return base + build_query(store, tab, wi_race, wi_driver)
        return base + build_query(store, tab, race, focus, team)

    @app.callback(Output("race-download", "data"), Input("race-csv", "n_clicks"),
                  State("race-dd", "value"), prevent_initial_call=True)
    def download_race(_, rnd):
        if rnd is None:
            return no_update
        df = race_csv(store, rnd)
        name = f"strategy_audit_{store.season}_R{rnd:02d}_{store.race_abbr(rnd)}.csv"
        # Separador «;», coma decimal y BOM UTF-8: se abre bien (con tildes) en Excel en español
        return dcc.send_string("\ufeff" + df.to_csv(index=False, sep=";", decimal=","), name)

    # ------------------------------------------------------------------ Carrera
    @app.callback(Output("race-focus", "options"), Output("race-focus", "value"),
                  Input("race-dd", "value"), State("race-focus", "value"), State("url-params", "data"))
    def race_focus_options(rnd, current, params):
        a = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
        opts = [{"label": f"{fmt_pos(p)} · {n}", "value": d}
                for d, n, p in zip(a["Driver"], a["FullName"], a["AuditedPosition"])]
        drivers = set(a["Driver"])
        if current in drivers:
            return opts, current
        return opts, _from_link(params, "race", rnd, drivers)

    @app.callback(
        Output("race-kpis", "children"),
        Output("race-stints", "figure"), Output("race-stints-card-title", "children"),
        Output("race-stints-card-sub", "children"),
        Output("race-delta", "figure"), Output("race-delta-card-title", "children"),
        Output("race-delta-card-sub", "children"),
        Output("race-deg", "figure"), Output("race-deg-card-title", "children"),
        Output("race-deg-card-sub", "children"),
        Output("race-trace", "figure"), Output("race-trace-card-title", "children"),
        Output("race-trace-card-sub", "children"),
        Input("race-dd", "value"), Input("race-focus", "value"),
    )
    def update_race(rnd, focus):
        if rnd is None:
            msg = "Elige un Gran Premio para ver su auditoría"
            return [], F.empty(msg), "", "", F.empty(msg), "", "", F.empty(msg), "", "", F.empty(msg), "", ""
        row = store.race_row(rnd)
        gp = store.race_es(rnd)
        audit = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
        order = list(audit["Driver"])
        actual = store.stints[store.stints["Round"] == rnd]
        best = store.best_stints[store.best_stints["Round"] == rnd]
        neutral = store.neutralised_laps(rnd)
        model = store.model(rnd)
        worst = audit.loc[audit["StrategyDelta"].idxmax()]
        near_opt = audit["StrategyDelta"] < 1.0

        kpis = [
            kpi("Pérdida en boxes", fmt_s(row["PitLoss"]), "por parada con bandera verde"),
            kpi("Vueltas con SC/VSC", f"{len(neutral)}", f"de {int(row['TotalLaps'])}"),
            kpi("Para adelantar", fmt_s(row.get("OvertakeDelta", float("nan"))),
                "más rápido por vuelta que el de delante"),
            kpi("Tiempo en tráfico", fmt_s(audit["ActualTraffic"].mean()),
                f"de media por piloto · con la mejor estrategia, {fmt_s(audit['BestTraffic'].mean())}"),
            kpi("Mayor pérdida", f"{worst['Driver']} · {fmt_s(worst['StrategyDelta'])}",
                worst["Team"] or "", tone="loss"),
            kpi("Estrategias casi óptimas", fmt_pct(near_opt.mean()), "a menos de 1 s de la mejor simulada"),
        ]

        top_best = audit["BestStrategy"].value_counts().index[0]
        stints_title = (f"En el {gp}, la mejor estrategia simulada era {top_best}; "
                        f"{int(near_opt.sum())} de {len(audit)} pilotos se quedaron a menos de 1 s")
        stints_sub = ("Stints por piloto, ordenados por posición final · izquierda: real, derecha: óptima"
                      + (" · franjas: vueltas con SC/VSC" if neutral else ""))

        subject = audit[audit["Driver"] == focus].iloc[0] if focus in set(order) else worst
        if subject["StrategyDelta"] < 0.05:
            delta_title = f"{_surname(subject['FullName'])} acertó con la estrategia óptima ({subject['ActualStrategy']})"
        else:
            delta_title = (f"{_surname(subject['FullName'])} perdió {fmt_s(subject['StrategyDelta'])} "
                           f"con {subject['ActualStrategy']} frente a {subject['BestStrategy']}")
        delta_sub = "Segundos perdidos frente a la mejor estrategia simulada (s) · menos es mejor"

        usable = {c: d for c, d in model.compound_deg.items() if c in model.usable_compounds}
        if usable:
            c_max = max(usable, key=usable.get)
            deg_title = f"El {COMPOUND_ES[c_max].lower()} fue el que más se degradó: {fmt_deg(usable[c_max])}"
        else:
            deg_title = "Degradación estimada por compuesto"
        deg_sub = "Vueltas limpias corregidas por piloto y combustible · recta = degradación del modelo"

        laps = store.laps[store.laps["Round"] == rnd]
        trace_title, trace_sub = _trace_texts(audit, laps, focus, gp)
        return (kpis,
                F.stint_comparison(actual, best, order, neutral, int(row["TotalLaps"]), focus), stints_title, stints_sub,
                F.delta_bars(audit, focus), delta_title, delta_sub,
                F.degradation(laps, model), deg_title, deg_sub,
                F.race_trace(laps, audit, actual, neutral, int(row["TotalLaps"]), focus), trace_title, trace_sub)

    # ------------------------------------------------------------------ ¿Y si…?
    @app.callback(
        Output("wi-driver", "options"), Output("wi-driver", "value"),
        Input("wi-race", "value"), State("wi-driver", "value"), State("url-params", "data"),
    )
    def update_drivers(rnd, current, params):
        a = store.audit[store.audit["Round"] == rnd].sort_values("AuditedPosition")
        opts = [{"label": f"{fmt_pos(p)} · {n} ({t})", "value": d}
                for d, n, t, p in zip(a["Driver"], a["FullName"], a["Team"], a["AuditedPosition"])]
        if current in set(a["Driver"]):
            return opts, current
        linked = _from_link(params, "whatif", rnd, set(a["Driver"]))
        if linked:
            return opts, linked
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
        if len(stints) > 3:   # más de 2 paradas: se agrupan las últimas en el tercer stint
            stints = stints[:2] + [(stints[2][0], sum(n for _, n in stints[2:]))]
        stops = min(max(len(stints) - 1, 1), 2)
        comps = [c for c, _ in stints] + ["HARD"] * 3
        cuts = list(np.cumsum([n for _, n in stints])[:-1]) + [total - 10]
        s1 = int(cuts[0])
        s2 = int(cuts[1]) if stops == 2 else min(s1 + 15, total - 5)
        return stops, comps[0], comps[1], comps[2] if stops == 2 else "MEDIUM", s1, s2, total - 1, total - 1

    @app.callback(Output("wi-c3-wrap", "style"), Output("wi-s2-wrap", "style"), Input("wi-stops", "value"))
    def toggle_second_stop(stops):
        style = {} if stops == 2 else {"display": "none"}
        return style, style

    @app.callback(
        Output("wi-kpis", "children"), Output("wi-gap", "figure"), Output("wi-laps", "figure"),
        Output("wi-warning", "children"),
        Output("wi-gap-card-title", "children"), Output("wi-gap-card-sub", "children"),
        Output("wi-window", "figure"), Output("wi-window-card-title", "children"),
        Output("wi-window-card-sub", "children"),
        Input("wi-stops", "value"), Input("wi-c1", "value"), Input("wi-c2", "value"), Input("wi-c3", "value"),
        Input("wi-s1", "value"), Input("wi-s2", "value"),
        State("wi-race", "value"), State("wi-driver", "value"),
    )
    def simulate(stops, c1, c2, c3, s1, s2, rnd, driver):
        sub = "Diferencia acumulada frente a la estrategia real (s) · por debajo de 0, la alternativa va por delante"
        if None in (rnd, driver, c1, c2, s1):
            msg = "Elige un Gran Premio y un piloto para simular"
            return [], F.empty(msg), F.empty(msg), "", "Diseña una estrategia alternativa", sub, F.empty(msg), "", ""
        model = store.model(rnd)
        total = int(store.race_row(rnd)["TotalLaps"])
        pls = store.pit_losses(rnd)
        actual, first_age = driver_actual_strategy(store.stints, rnd, driver)
        a = store.audit[store.audit["Round"] == rnd]
        me = a[a["Driver"] == driver].iloc[0]
        laps_done = int(me["LapsCompleted"])
        name = _surname(me["FullName"])

        if stops == 2:
            if s2 is None or s2 <= s1:
                msg = "Mueve la 2.ª parada a una vuelta posterior a la 1.ª"
                return [], F.empty(msg), F.empty(msg), _warning([msg]), "Revisa las vueltas de parada", sub, F.empty(msg), "", ""
            alt = [(c1, s1), (c2, s2 - s1), (c3, laps_done - s2)]
        else:
            alt = [(c1, s1), (c2, laps_done - s1)]
        if alt[-1][1] < 1:
            msg = "La última parada no puede ser después de la última vuelta del piloto"
            return [], F.empty(msg), F.empty(msg), _warning([msg]), "Revisa las vueltas de parada", sub, F.empty(msg), "", ""

        missing = [c for c, _ in alt if c not in model.compound_deg]
        if missing:
            msg = (f"Nadie usó {', '.join(COMPOUND_ES[c].lower() for c in missing)} en esta carrera: "
                   "elige otro compuesto")
            return [], F.empty(msg), F.empty(msg), _warning([msg]), "Compuesto sin datos en esta carrera", sub, F.empty(msg), "", ""

        warnings = []
        if not is_feasible(model, alt, first_age):
            if len({c for c, _ in alt}) < 2:
                warnings.append("El reglamento obliga a usar al menos dos compuestos de seco.")
            if len(alt) - 1 < model.min_stops:
                warnings.append(f"En esta carrera eran obligatorias {model.min_stops} paradas.")
            for i, (c, n) in enumerate(alt):
                age0 = first_age if i == 0 else 1
                if age0 + n - 1 > max_stint(model, c):
                    warnings.append(f"Stint {i + 1}: {n} vueltas con {COMPOUND_ES[c].lower()} supera lo observado "
                                    f"en carrera ({max_stint(model, c)}); el modelo extrapola.")
                if n < 5:
                    warnings.append(f"Stint {i + 1} demasiado corto ({n} vueltas).")
                if c not in model.usable_compounds:
                    warnings.append(f"Hay pocas vueltas con {COMPOUND_ES[c].lower()}: estimación poco fiable.")

        # Tiempo limpio de cada vuelta + lo que pierde en tráfico con los rivales en su sitio real
        penalty = store.traffic_penalty(rnd, driver, first_age, actual)
        tr_alt, tr_real = penalty(alt), penalty(actual)
        sim_alt = lap_times(model, driver, alt, first_age, pls) + tr_alt.lost_by_lap
        sim_real = lap_times(model, driver, actual, first_age, pls) + tr_real.lost_by_lap
        gap = np.cumsum(sim_alt - sim_real)
        diff = float(gap[-1])

        # Orden de llegada: más vueltas primero; a igualdad de vueltas, menor tiempo
        mine = (-laps_done, me["FinishTime"] + diff)
        rivals = a[a["Driver"] != driver]
        est = 1 + sum(1 for lp, t in zip(rivals["LapsCompleted"], rivals["FinishTime"]) if (-lp, t) < mine)
        real_pos = int(me["AuditedPosition"])
        tone = "gain" if diff < -0.05 else "loss" if diff > 0.05 else None

        kpis = [
            kpi("Alternativa frente a la real", fmt_s(diff, signed=True),
                "más rápida" if diff < -0.05 else ("más lenta" if diff > 0.05 else "igual"), tone=tone),
            kpi("Posición estimada", f"{fmt_pos(real_pos)} → {fmt_pos(est)}",
                "frente a los tiempos reales de los rivales",
                tone="gain" if est < real_pos else "loss" if est > real_pos else None),
            kpi("Tiempo perdido en tráfico", fmt_s(tr_alt.loss), _traffic_note(tr_alt, tr_real)),
            kpi("Strategy Delta del piloto", fmt_s(me["StrategyDelta"]), f"mejor: {me['BestStrategy']}"),
        ]
        if diff < -0.05:
            title = f"Con esta estrategia, {name} habría ganado {fmt_s(-diff)}" + \
                    (f" y acabado {fmt_pos(est)}" if est != real_pos else "")
        elif diff > 0.05:
            title = f"Con esta estrategia, {name} habría perdido {fmt_s(diff)}" + \
                    (f" y acabado {fmt_pos(est)}" if est != real_pos else "")
        else:
            title = f"Esta es la estrategia que eligió {name}: cambia una parada o un compuesto"

        stops_alt = list(np.cumsum([n for _, n in alt])[:-1])
        stops_real = list(np.cumsum([n for _, n in actual])[:-1])
        real_laps = store.laps[(store.laps["Round"] == rnd) & (store.laps["Driver"] == driver)]
        idx = np.arange(1, laps_done + 1)
        best_rows = store.best_stints[(store.best_stints["Round"] == rnd) & (store.best_stints["Driver"] == driver)]
        best_stints = list(zip(best_rows.sort_values("Stint")["Compound"], best_rows.sort_values("Stint")["Laps"].astype(int)))
        best_total = (strategy_cost(model, best_stints, first_age, pls) + float(me.get("BestTraffic", 0.0))
                      if best_stints else None)
        win_fig, win_title, win_sub = _window(model, laps_done, first_age, pls, alt, actual, penalty, best_total)
        return (kpis, F.whatif_gap(gap, stops_alt, stops_real),
                F.whatif_laps(real_laps, sim_alt, sim_real, np.isin(idx, stops_alt), np.isin(idx, stops_real)),
                _warning(warnings), title, sub, win_fig, win_title, win_sub)

    # ------------------------------------------------------------------ Temporada
    @app.callback(
        Output("season-teams", "figure"), Output("season-teams-card-title", "children"),
        Output("season-teams-card-sub", "children"),
        Output("season-positions", "figure"), Output("season-positions-card-title", "children"),
        Output("season-positions-card-sub", "children"),
        Output("season-evolution", "figure"), Output("season-evolution-card-title", "children"),
        Output("season-evolution-card-sub", "children"),
        Output("season-heatmap", "figure"), Output("season-heatmap-card-title", "children"),
        Output("season-heatmap-card-sub", "children"),
        Input("tabs", "value"), Input("season-focus", "value"),
    )
    def update_season(tab, focus):
        if tab != "season":
            return (no_update,) * 12
        a = store.audit
        teams = a.groupby("Team")["StrategyDelta"].mean().sort_values()
        if focus in teams.index:
            rank = list(teams.index).index(focus) + 1
            teams_title = f"{focus} fue {rank}.º de {len(teams)} en acierto estratégico ({fmt_s(teams[focus])} de media)"
        else:
            teams_title = f"{teams.index[0]} fue el equipo que mejor acertó con la estrategia ({fmt_s(teams.iloc[0])} de media)"
        teams_sub = ("Cada punto es un piloto en una carrera · rombo: media con intervalo de confianza del 95 % "
                     "(bootstrap) · menos es mejor")

        pos = a.groupby("Driver").agg(P=("PositionsLost", "sum"), Name=("FullName", "first"), Team=("Team", "first"))
        top = pos.sort_values("P").iloc[-1]
        focus_driver = None
        pos_title = f"{_surname(top['Name'])} fue quien más posiciones perdió por estrategia: {int(top['P'])} en la temporada"
        if focus in teams.index:
            team_pos = pos[pos["Team"] == focus]
            pos_title = f"Los pilotos de {focus} perdieron {int(team_pos['P'].sum())} posiciones por estrategia"
            focus_driver = team_pos["P"].idxmax() if len(team_pos) else None
        pos_sub = "Posiciones que habrían ganado con la mejor estrategia (suma de la temporada) · 12 pilotos con más pérdidas"

        totals = a.groupby("Team")["StrategyDelta"].sum()
        if focus in totals.index:
            evo_title = f"{focus} acumuló {fmt_s(totals[focus], dec=0)} perdidos por estrategia en la temporada"
        else:
            evo_title = (f"{totals.idxmax()} fue el que más tiempo perdió ({fmt_s(totals.max(), dec=0)}); "
                         f"{totals.idxmin()}, el que menos ({fmt_s(totals.min(), dec=0)})")
        evo_sub = "Segundos perdidos acumulados carrera a carrera, suma de sus dos pilotos (s)"

        by_race = a.groupby("Round")["StrategyDelta"].mean()
        hardest = int(by_race.idxmax())
        heat_title = f"La carrera más difícil de acertar fue el {race_names[hardest]}: {fmt_s(by_race.max())} perdidos de media"
        heat_sub = "Strategy Delta por piloto y carrera (s) · más oscuro = más tiempo perdido · huecos: no auditado"

        return (F.team_ranking(a, focus), teams_title, teams_sub,
                F.positions_lost(a, focus_driver), pos_title, pos_sub,
                F.team_evolution(a, race_names, race_abbr, focus), evo_title, evo_sub,
                F.season_heatmap(a, race_names, race_abbr), heat_title, heat_sub)
