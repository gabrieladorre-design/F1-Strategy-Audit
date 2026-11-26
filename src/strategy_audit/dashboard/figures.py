"""Figuras Plotly del dashboard. Funciones puras: reciben datos, devuelven figuras.

Estilo: ver ``theme.py`` (plantilla «strategy_audit», tokens y formato en español).
El título de cada gráfico vive en la tarjeta de Dash, no dentro de la figura.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from strategy_audit.simulation.simulator import _stint_cost_array, enumerate_strategies

from strategy_audit.dashboard import theme as T
from strategy_audit.dashboard.theme import (
    ACCENT, COMPOUND, COMPOUND_ES, COMPOUND_ORDER, CONTEXT, GAIN, LOSS, MUTED, NEUTRAL_BAND,
    PANEL, PRIMARY, SEQ_RED, TEXT, fmt_deg, fmt_s, fmt_vuelta, team_color, with_alpha,
)

INITIAL = {"SOFT": "B", "MEDIUM": "M", "HARD": "D", "INTERMEDIATE": "I", "WET": "LL"}


def _base(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(template="strategy_audit", height=height)
    return fig


def empty(msg: str = "Elige una carrera y un piloto para ver su estrategia") -> go.Figure:
    fig = _base(go.Figure(), height=280)
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=MUTED, size=14),
                       x=0.5, y=0.5, xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _hbar_axes(fig: go.Figure) -> None:
    """Barras horizontales: cuadrícula solo en el eje de valores (X)."""
    fig.update_xaxes(showgrid=True, gridcolor=T.GRID)
    fig.update_yaxes(showgrid=False, automargin=True, ticks="")


# --------------------------------------------------------------------------- Carrera
def _stint_bars(fig, stints: pd.DataFrame, col: int, shown: set) -> None:
    for c in COMPOUND_ORDER:
        s = stints[stints["Compound"] == c]
        if s.empty:
            continue
        style = COMPOUND[c]
        fig.add_trace(go.Bar(
            y=s["Driver"], x=s["Laps"] - 0.3, base=s["StartLap"] - 1 + 0.15, orientation="h",
            name=COMPOUND_ES[c], legendgroup=c, showlegend=c not in shown,
            marker=dict(color=style["fill"], line=dict(color=style["edge"], width=1.2)),
            customdata=np.stack([s["StartLap"], s["EndLap"], s["Laps"]], axis=1),
            hovertemplate=(f"<b>%{{y}}</b> · {COMPOUND_ES[c]}"
                           "<br>Vueltas %{customdata[0]}–%{customdata[1]} · %{customdata[2]} vueltas<extra></extra>"),
        ), row=1, col=col)
        shown.add(c)


def stint_comparison(actual: pd.DataFrame, best: pd.DataFrame, order: list[str],
                     neutral: set[int], total_laps: int, focus: str | None = None) -> go.Figure:
    """Stints reales frente a los de la mejor estrategia simulada, por piloto."""
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=("Estrategia real", "Mejor estrategia simulada"))
    shown: set = set()
    _stint_bars(fig, actual[actual["Driver"].isin(order)], 1, shown)
    _stint_bars(fig, best[best["Driver"].isin(order)], 2, shown)

    for i, lap in enumerate(sorted(neutral)):
        for col in (1, 2):
            fig.add_vrect(x0=lap - 1, x1=lap, fillcolor=NEUTRAL_BAND, opacity=0.12, line_width=0,
                          row=1, col=col)
    # Sin etiqueta «SC/VSC» sobre la franja: chocaba con el título del panel cuando el SC
    # salía en las primeras vueltas. El subtítulo de la tarjeta ya explica las franjas.

    ticks = [f"<b>{d}</b>" if d == focus else d for d in order]
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(categoryorder="array", categoryarray=order[::-1], showgrid=False,
                     tickmode="array", tickvals=order, ticktext=ticks)
    fig.update_xaxes(range=[0, total_laps + 0.5], title_text="Vuelta")
    fig = _base(fig, height=max(380, 26 * len(order) + 110))
    fig.update_layout(margin=dict(t=84))
    for ann in fig.layout.annotations:
        if ann.text in ("Estrategia real", "Mejor estrategia simulada"):
            ann.font = dict(color=TEXT, size=13)
            ann.x = 0 if ann.text == "Estrategia real" else 0.52
            ann.xanchor = "left"
    # Leyenda en su propia línea, por encima de los títulos de los paneles (no se solapan en móvil)
    fig.update_layout(legend=dict(x=0, xanchor="left", y=0.995, yanchor="top", yref="container"))
    return fig


def _highlight_colors(values: pd.Series, keys: pd.Series, focus: str | None,
                      focus_color: str = ACCENT) -> list[str]:
    """Foco en color; sin foco, el mejor en verde y el peor en rojo; el resto atenuado."""
    dim = with_alpha(PRIMARY, 0.35)
    if focus is not None and focus in set(keys):
        return [focus_color if k == focus else dim for k in keys]
    best, worst = values.idxmin(), values.idxmax()
    return [LOSS if i == worst else GAIN if i == best else dim for i in values.index]


def delta_bars(audit: pd.DataFrame, focus: str | None = None) -> go.Figure:
    """Strategy Delta por piloto: mayor pérdida arriba."""
    a = audit.sort_values("StrategyDelta", ascending=True)
    colors = _highlight_colors(a["StrategyDelta"], a["Driver"], focus)
    names = a["FullName"] if "FullName" in a else a["Driver"]
    fig = go.Figure(go.Bar(
        x=a["StrategyDelta"], y=a["Driver"], orientation="h",
        marker=dict(color=colors, cornerradius=3),
        text=[fmt_s(v) if v >= 0.05 else "" for v in a["StrategyDelta"]],
        textposition="outside", textfont=dict(color=T.TEXT_2), cliponaxis=False,
        customdata=np.stack([names, a["Team"].fillna(""), a["ActualStrategy"].map(T.fmt_strategy), a["BestStrategy"].map(T.fmt_strategy),
                             a["AuditedPosition"], a["EstPosition"]], axis=1),
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}"
                       "<br>Strategy Delta · %{x:.1f} s"
                       "<br>Hizo · %{customdata[2]}<br>Lo mejor · %{customdata[3]}"
                       "<br>Posición · P%{customdata[4]} → P%{customdata[5]} estimada<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Segundos perdidos (s)",
                     range=[0, max(float(a["StrategyDelta"].max()), 1.0) * 1.15])
    _hbar_axes(fig)
    return _base(fig, height=max(380, 24 * len(a) + 70))


def degradation(laps: pd.DataFrame, model) -> go.Figure:
    """Vueltas limpias frente a la edad del neumático, con la recta del modelo por compuesto."""
    fig = go.Figure()
    clean = laps[laps["IsClean"] & laps["Compound"].isin(model.compound_deg)]
    # Se descuentan el ritmo del piloto y el combustible: queda solo el efecto del neumático
    corr = clean["LapTime"] - clean["Driver"].map(model.driver_base) - model.fuel * clean["LapNumber"]
    labels = []
    for c in COMPOUND_ORDER:
        m = clean["Compound"] == c
        if not m.any():
            continue
        style = COMPOUND[c]
        fig.add_trace(go.Scattergl(
            x=clean.loc[m, "TyreLife"], y=corr[m], mode="markers", name=COMPOUND_ES[c],
            legendgroup=c, showlegend=False,
            marker=dict(color=style["fill"], size=6, opacity=0.45, line=dict(color=style["edge"], width=0.5)),
            customdata=clean.loc[m, ["Driver", "LapNumber"]].to_numpy(),
            hovertemplate=(f"<b>%{{customdata[0]}}</b> · {COMPOUND_ES[c]}"
                           "<br>Vuelta %{customdata[1]} · edad %{x}<br>%{y:+.2f} s<extra></extra>"),
        ))
        if c not in model.usable_compounds:   # pocos datos: se muestran los puntos, sin recta
            continue
        x_max = int(clean.loc[m, "TyreLife"].max())
        x = np.arange(1, x_max + 1)
        y = model.compound_offset[c] + model.compound_deg[c] * x
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", legendgroup=c, showlegend=False,
            line=dict(color=style["stroke"], width=2.5),
            hovertemplate=f"<b>{COMPOUND_ES[c]}</b> · degradación {fmt_deg(model.compound_deg[c])}<extra></extra>",
        ))
        labels.append([float(y[-1]), x_max, c])

    # Etiquetas directas al final de cada recta, separadas para que no se pisen
    if labels:
        span = float(np.nanpercentile(corr, 98) - np.nanpercentile(corr, 2)) or 1.0
        gap = span * 0.09
        labels.sort()
        for i in range(1, len(labels)):
            labels[i][0] = max(labels[i][0], labels[i - 1][0] + gap)
        x_label = max(l[1] for l in labels)
        for y_lab, _, c in labels:
            fig.add_annotation(x=x_label, y=y_lab, text=f"{COMPOUND_ES[c]} {fmt_deg(model.compound_deg[c])}",
                               showarrow=False, xanchor="left", xshift=8,
                               font=dict(color=team_color(COMPOUND[c]["stroke"], for_text=True), size=12))
    fig.update_xaxes(title_text="Edad del neumático (vueltas)")
    fig.update_yaxes(title_text="Tiempo relativo (s)")
    fig = _base(fig, height=380)
    fig.update_layout(margin=dict(r=150))
    return fig


# --------------------------------------------------------------------------- ¿Y si…?
def whatif_gap(cum_gap: np.ndarray, stops_alt: list[int], stops_real: list[int]) -> go.Figure:
    """Diferencia acumulada (alternativa − real simulada) vuelta a vuelta."""
    laps = np.arange(1, len(cum_gap) + 1)
    fig = go.Figure()
    # Áreas: verde donde la alternativa va por delante, roja donde va por detrás
    fig.add_trace(go.Scatter(x=laps, y=np.minimum(cum_gap, 0), mode="lines", line=dict(width=0),
                             fill="tozeroy", fillcolor=with_alpha(GAIN, 0.10), hoverinfo="skip",
                             showlegend=False))
    fig.add_trace(go.Scatter(x=laps, y=np.maximum(cum_gap, 0), mode="lines", line=dict(width=0),
                             fill="tozeroy", fillcolor=with_alpha(LOSS, 0.10), hoverinfo="skip",
                             showlegend=False))
    fig.add_trace(go.Scatter(
        x=laps, y=cum_gap, mode="lines", line=dict(color=PRIMARY, width=2.5), showlegend=False,
        hovertemplate="<b>Vuelta %{x}</b><br>Diferencia · %{y:+.1f} s<extra></extra>",
    ))
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    for s in stops_real:
        fig.add_vline(x=s, line=dict(color=MUTED, width=1, dash="dash"))
    for s in stops_alt:
        fig.add_vline(x=s, line=dict(color=ACCENT, width=1.5))
    final = float(cum_gap[-1])
    fig.add_annotation(x=laps[-1], y=final, text=fmt_s(final, signed=True), showarrow=False,
                       xanchor="left", xshift=6,
                       font=dict(color=GAIN if final < 0 else LOSS if final > 0 else MUTED, size=13))
    fig.update_xaxes(title_text="Vuelta", range=[0, len(cum_gap) + 7])
    fig.update_yaxes(title_text="Diferencia (s)")
    return _base(fig, height=320)


def whatif_laps(real: pd.DataFrame, sim_alt: np.ndarray, sim_real: np.ndarray,
                pit_mask_alt, pit_mask_real) -> go.Figure:
    """Tiempos por vuelta: reales, modelo con la estrategia real y alternativa."""
    laps = np.arange(1, len(sim_alt) + 1)
    fig = go.Figure()
    r = real[~real["IsPitIn"] & (real["LapNumber"] > 1)]
    fig.add_trace(go.Scatter(x=r["LapNumber"], y=r["LapTime"], mode="markers", name="Tiempo real",
                             marker=dict(color=MUTED, size=6),
                             hovertemplate="<b>Vuelta %{x}</b><br>Tiempo real · %{y:.3f} s<extra></extra>"))
    y_real = np.where(pit_mask_real, np.nan, sim_real)
    y_alt = np.where(pit_mask_alt, np.nan, sim_alt)
    fig.add_trace(go.Scatter(x=laps, y=y_real, mode="lines", name="Simulación de lo que hizo",
                             line=dict(color=PRIMARY, width=2, dash="dash"),
                             hovertemplate="<b>Vuelta %{x}</b><br>Lo que hizo (simulado) · %{y:.3f} s<extra></extra>"))
    fig.add_trace(go.Scatter(x=laps, y=y_alt, mode="lines", name="Simulación de tu estrategia",
                             line=dict(color=ACCENT, width=2.5),
                             hovertemplate="<b>Vuelta %{x}</b><br>Tu estrategia (simulada) · %{y:.3f} s<extra></extra>"))
    vals = np.r_[r["LapTime"].to_numpy(), y_alt[~np.isnan(y_alt)]]
    if len(vals):
        fig.update_yaxes(range=[np.nanpercentile(vals, 1) - 0.5, np.nanpercentile(vals, 97) + 1.0])
    fig.update_yaxes(title_text="Tiempo por vuelta (s)")
    fig.update_xaxes(title_text="Vuelta")
    return _base(fig, height=320)


# --------------------------------------------------------------------------- Temporada
def _team_table(audit: pd.DataFrame) -> pd.DataFrame:
    return (audit.groupby("Team")
            .agg(Delta=("StrategyDelta", "mean"), Color=("TeamColor", "first"), N=("StrategyDelta", "size"))
            .sort_values("Delta", ascending=False))


def bootstrap_ci(values: np.ndarray, n: int = 2000, level: float = 0.95, seed: int = 0) -> tuple[float, float]:
    """Intervalo de confianza de la media por bootstrap (percentiles)."""
    v = np.asarray(values, dtype=float)
    v = v[np.isfinite(v)]
    if len(v) < 2:
        m = float(v.mean()) if len(v) else float("nan")
        return m, m
    rng = np.random.default_rng(seed)
    means = rng.choice(v, size=(n, len(v)), replace=True).mean(axis=1)
    a = (1 - level) / 2
    return float(np.quantile(means, a)), float(np.quantile(means, 1 - a))


def team_ranking(audit: pd.DataFrame, focus: str | None = None) -> go.Figure:
    """Strategy Delta por equipo: cada auditoría como punto, media con IC 95 % (bootstrap)."""
    t = _team_table(audit)
    ci = {team: bootstrap_ci(audit.loc[audit["Team"] == team, "StrategyDelta"].to_numpy()) for team in t.index}
    best, worst = t["Delta"].idxmin(), t["Delta"].idxmax()
    highlighted = {focus} if focus in t.index else {best, worst}
    order = list(t.index)[::-1]                       # peor arriba
    x_max = max(float(np.nanpercentile(audit["StrategyDelta"], 95)), max(hi for _, hi in ci.values())) * 1.15
    rng = np.random.default_rng(1)

    fig = go.Figure()
    # 1) Nube de puntos: una auditoría piloto-carrera por punto (lo extremo se pega al borde)
    for team in order:
        g = audit[audit["Team"] == team]
        col = team_color(t.loc[team, "Color"])
        x = g["StrategyDelta"].to_numpy(float)
        clipped = x > x_max
        y = np.full(len(g), order.index(team)) + rng.uniform(-0.22, 0.22, len(g))
        fig.add_trace(go.Scatter(
            x=np.minimum(x, x_max * 0.995), y=y, mode="markers", showlegend=False,
            marker=dict(size=5, color=with_alpha(col, 0.40 if team in highlighted else 0.22),
                        symbol=np.where(clipped, "triangle-right", "circle")),
            customdata=np.stack([g["FullName"], g["Round"], x], axis=1),
            hovertemplate=(f"<b>%{{customdata[0]}}</b> · {team}<br>Ronda %{{customdata[1]}}"
                           "<br>Strategy Delta · %{customdata[2]:.1f} s<extra></extra>"),
        ))
    # 2) Media + intervalo de confianza (una sola traza, encima de la nube)
    means = [t.loc[tm, "Delta"] for tm in order]
    lo = [ci[tm][0] for tm in order]
    hi = [ci[tm][1] for tm in order]
    colors = [team_color(t.loc[tm, "Color"]) if tm in highlighted else PRIMARY for tm in order]
    fig.add_trace(go.Scatter(
        x=means, y=list(range(len(order))), mode="markers+text", showlegend=False,
        marker=dict(size=11, symbol="diamond", color=colors, line=dict(color=PANEL, width=1.5)),
        error_x=dict(type="data", symmetric=False, array=np.subtract(hi, means), arrayminus=np.subtract(means, lo),
                     color=MUTED, thickness=1.5, width=0),
        text=[fmt_s(m) for m in means], textposition="top center", textfont=dict(color=T.TEXT_2, size=11),
        customdata=np.stack([order, lo, hi, [int(t.loc[tm, "N"]) for tm in order]], axis=1),
        hovertemplate=("<b>%{customdata[0]}</b><br>Media · %{x:.2f} s"
                       "<br>IC 95 % · %{customdata[1]:.2f}–%{customdata[2]:.2f} s"
                       "<br>%{customdata[3]} auditorías<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Strategy Delta (s)", range=[-0.3, x_max])
    fig.update_yaxes(tickmode="array", tickvals=list(range(len(order))), ticktext=order,
                     range=[-0.6, len(order) - 0.4])
    _hbar_axes(fig)
    return _base(fig, height=max(380, 40 * len(t) + 70))


def positions_lost(audit: pd.DataFrame, focus: str | None = None, top: int = 12) -> go.Figure:
    """Posiciones que cada piloto habría ganado con la mejor estrategia (suma de la temporada)."""
    pos = (audit.groupby("Driver")
           .agg(P=("PositionsLost", "sum"), Team=("Team", "first"), Name=("FullName", "first"))
           .query("P > 0").sort_values("P").tail(top))
    if pos.empty:
        return empty("Ningún piloto perdió posiciones por estrategia")
    colors = _highlight_colors(pos["P"], pd.Series(pos.index, index=pos.index), focus)
    if focus is None:   # en este gráfico solo tiene sentido destacar al que más perdió
        colors = [LOSS if d == pos["P"].idxmax() else with_alpha(PRIMARY, 0.35) for d in pos.index]
    fig = go.Figure(go.Bar(
        x=pos["P"], y=pos.index, orientation="h", marker=dict(color=colors, cornerradius=3),
        text=pos["P"], textposition="outside", textfont=dict(color=T.TEXT_2), cliponaxis=False,
        customdata=np.stack([pos["Name"], pos["Team"]], axis=1),
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{x} posiciones perdidas<extra></extra>",
    ))
    fig.update_xaxes(title_text="Posiciones perdidas", range=[0, float(pos["P"].max()) * 1.15])
    _hbar_axes(fig)
    return _base(fig, height=max(360, 30 * len(pos) + 70))


def season_heatmap(audit: pd.DataFrame, race_names: dict[int, str], race_abbr: dict[int, str]) -> go.Figure:
    """Mapa de calor piloto × carrera con el Strategy Delta (escala secuencial de un solo tono)."""
    pv = audit.pivot_table(index="Driver", columns="Round", values="StrategyDelta")
    pv = pv.loc[pv.mean(axis=1).sort_values(ascending=False).index]
    cols = [race_abbr.get(int(c), str(c)) for c in pv.columns]
    full = np.tile([race_names.get(int(c), str(c)) for c in pv.columns], (len(pv), 1))
    z = pv.to_numpy()
    fig = go.Figure()
    # Casillas sin datos (no corrió, abandonó o no se pudo analizar) en gris, para no confundirlas con 0 s
    fig.add_trace(go.Heatmap(z=np.where(np.isnan(z), 1.0, np.nan), x=cols, y=pv.index, xgap=2, ygap=2,
                             colorscale=[[0, "#E4E4E4"], [1, "#E4E4E4"]], showscale=False,
                             hoverinfo="skip", hoverongaps=False))
    fig.add_trace(go.Heatmap(
        z=z, x=cols, y=pv.index, xgap=2, ygap=2, customdata=full,
        colorscale=SEQ_RED, zmin=0, zmax=float(np.nanpercentile(z, 95)) if np.isfinite(z).any() else 1,
        colorbar=dict(title=dict(text="s", font=dict(color=MUTED)), tickfont=dict(color=MUTED),
                      thickness=10, outlinewidth=0),
        hovertemplate="<b>%{y}</b> · %{customdata}<br>Perdió %{z:.1f} s por su estrategia<extra></extra>",
        hoverongaps=False,
    ))
    fig.update_xaxes(showgrid=False, showline=False, ticks="", side="top")
    fig.update_yaxes(showgrid=False, autorange="reversed", ticks="")
    fig = _base(fig, height=max(420, 22 * len(pv) + 90))
    fig.update_layout(margin=dict(t=40))
    return fig


def team_evolution(audit: pd.DataFrame, race_names: dict[int, str], race_abbr: dict[int, str],
                   focus: str | None = None) -> go.Figure:
    """Segundos perdidos acumulados por equipo: foco en color, resto en gris, etiquetas directas."""
    t = (audit.groupby(["Team", "Round"])
         .agg(Delta=("StrategyDelta", "sum"), Color=("TeamColor", "first")).reset_index())
    rounds = sorted(t["Round"].unique())
    x_of = {r: i for i, r in enumerate(rounds)}
    totals = t.groupby("Team")["Delta"].sum()
    if focus in totals.index:
        focus_teams = {focus: None}
    else:
        focus_teams = {totals.idxmin(): GAIN, totals.idxmax(): LOSS}

    fig = go.Figure()
    teams = [tm for tm in totals.index if tm not in focus_teams] + list(focus_teams)  # foco encima
    for team in teams:
        g = t[t["Team"] == team].sort_values("Round")
        cum = g["Delta"].cumsum().to_numpy()
        xs = [x_of[r] for r in g["Round"]]
        names = [race_names.get(int(r), str(r)) for r in g["Round"]]
        is_focus = team in focus_teams
        color = (focus_teams[team] or team_color(g["Color"].iloc[0])) if is_focus else CONTEXT
        fig.add_trace(go.Scatter(
            x=xs, y=cum, mode="lines+markers" if is_focus else "lines", name=team, showlegend=False,
            line=dict(color=color, width=3 if is_focus else 1.5),
            marker=dict(size=8, color=color, line=dict(color=PANEL, width=1.5)),
            customdata=names,
            hovertemplate=f"<b>{team}</b> · %{{customdata}}<br>Acumulado · %{{y:.1f}} s<extra></extra>",
        ))
        if is_focus:
            fig.add_annotation(x=xs[-1], y=cum[-1], text=f"{team} · {fmt_s(cum[-1], dec=0)}",
                               showarrow=False, xanchor="left", xshift=8,
                               font=dict(color=team_color(color, for_text=True), size=12))
    fig.update_xaxes(tickmode="array", tickvals=list(range(len(rounds))),
                     ticktext=[race_abbr.get(int(r), str(r)) for r in rounds],
                     range=[-0.5, len(rounds) + 2.5])
    fig.update_yaxes(title_text="Segundos perdidos acumulados (s)")
    fig = _base(fig, height=420)
    fig.update_layout(margin=dict(r=24))
    return fig


# --------------------------------------------------------------------------- Evolución de carrera
def race_gaps(laps: pd.DataFrame, winner: str) -> pd.DataFrame:
    """Tiempo acumulado de cada piloto frente al ritmo medio constante del ganador.

    Devuelve columnas Driver, LapNumber, Gap (s; negativo = por detrás del ganador).
    Es el «race trace» clásico de los ingenieros de estrategia: la pendiente es el ritmo
    relativo y cada parada aparece como un escalón hacia abajo.
    """
    d = laps.sort_values(["Driver", "LapNumber"]).copy()
    # Vueltas sin tiempo (raras): se rellenan con la mediana del piloto para no romper la suma
    d["LapTime"] = d["LapTime"].fillna(d.groupby("Driver")["LapTime"].transform("median"))
    d["Cum"] = d.groupby("Driver")["LapTime"].cumsum()
    w = d[d["Driver"] == winner]
    ref = float(w["Cum"].iloc[-1]) / int(w["LapNumber"].iloc[-1])
    d["Gap"] = ref * d["LapNumber"] - d["Cum"]
    return d[["Driver", "Team", "LapNumber", "Gap", "Position"]]


def race_trace(laps: pd.DataFrame, audit: pd.DataFrame, stints: pd.DataFrame, neutral: set[int],
               total_laps: int, focus: str | None = None) -> go.Figure:
    """Diferencia con el ritmo medio del ganador, vuelta a vuelta, con paradas y SC/VSC."""
    a = audit.set_index("Driver")
    winner = a["AuditedPosition"].idxmin()
    g = race_gaps(laps[laps["Driver"].isin(a.index)], winner)
    if focus in a.index:
        focus_drivers = [winner, focus] if focus != winner else [winner]
    else:
        focus_drivers = [winner, a["StrategyDelta"].idxmax()]

    fig = go.Figure()
    for lap in sorted(neutral):
        fig.add_vrect(x0=lap - 1, x1=lap, fillcolor=NEUTRAL_BAND, opacity=0.12, line_width=0, layer="below")
    if neutral:
        fig.add_annotation(x=min(neutral) - 0.5, y=1.0, yref="paper", text="SC/VSC", showarrow=False,
                           font=dict(color=MUTED, size=11), yanchor="bottom")

    # Contexto: resto de la parrilla en gris, sin marcadores
    for drv in [d for d in a.index if d not in focus_drivers]:
        s = g[g["Driver"] == drv]
        fig.add_trace(go.Scatter(
            x=s["LapNumber"], y=s["Gap"], mode="lines", showlegend=False,
            line=dict(color=CONTEXT, width=1.2),
            hovertemplate=f"<b>{drv}</b> · vuelta %{{x}}<br>%{{y:+.1f}} s<extra></extra>",
        ))

    # Foco: color de equipo, paradas marcadas con el compuesto que se monta
    used: list[str] = []
    end_labels = []
    for drv in focus_drivers:
        s = g[g["Driver"] == drv]
        col = team_color(str(a.loc[drv, "TeamColor"]))
        dash = "dot" if any(_close_colors(col, u) for u in used) else "solid"
        used.append(col)
        fig.add_trace(go.Scatter(
            x=s["LapNumber"], y=s["Gap"], mode="lines", showlegend=False,
            line=dict(color=col, width=3, dash=dash),
            customdata=s["Position"],
            hovertemplate=(f"<b>{a.loc[drv, 'FullName']}</b> · vuelta %{{x}}"
                           "<br>%{y:+.1f} s · P%{customdata}<extra></extra>"),
        ))
        st = stints[stints["Driver"] == drv].sort_values("Stint")
        for (_, cur), (_, nxt) in zip(st.iloc[:-1].iterrows(), st.iloc[1:].iterrows()):
            row = s[s["LapNumber"] == cur["EndLap"]]
            if row.empty:
                continue
            style = COMPOUND.get(nxt["Compound"], COMPOUND["HARD"])
            fig.add_trace(go.Scatter(
                x=row["LapNumber"], y=row["Gap"], mode="markers", showlegend=False,
                marker=dict(size=11, color=style["fill"], line=dict(color=style["edge"], width=1.5)),
                hovertemplate=(f"<b>{drv}</b> · parada en la vuelta {int(cur['EndLap'])}"
                               f"<br>{COMPOUND_ES.get(cur['Compound'], cur['Compound'])} → "
                               f"{COMPOUND_ES.get(nxt['Compound'], nxt['Compound'])}<extra></extra>"),
            ))
        end_labels.append([float(s["Gap"].iloc[-1]), int(s["LapNumber"].iloc[-1]), drv, col])

    # Etiquetas directas al final, separadas para que no se pisen
    end_labels.sort()
    for i in range(1, len(end_labels)):
        end_labels[i][0] = max(end_labels[i][0], end_labels[i - 1][0] + 4)
    for y, x, drv, col in end_labels:
        fig.add_annotation(x=x, y=y, text=f"<b>{drv}</b>", showarrow=False, xanchor="left", xshift=8,
                           font=dict(color=team_color(col, for_text=True), size=12))

    # Escala: los doblados se salen por abajo; el foco siempre queda dentro
    last = g.sort_values("LapNumber").groupby("Driver")["Gap"].last()
    on_lead_lap = a.index[a["LapsCompleted"] == a["LapsCompleted"].max()]
    floor = min(float(last.reindex(on_lead_lap).min()),
                float(g[g["Driver"].isin(focus_drivers)]["Gap"].min()))
    top = float(g[g["LapNumber"] > 1]["Gap"].max())
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    fig.update_xaxes(title_text="Vuelta", range=[0, total_laps + 4])
    fig.update_yaxes(title_text="Diferencia con el ganador (s)", range=[floor - 8, max(top, 5) + 4])
    return _base(fig, height=420)


def _close_colors(c1: str, c2: str, tol: int = 60) -> bool:
    a = [int(c1.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    b = [int(c2.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)]
    return sum(abs(x - y) for x, y in zip(a, b)) < tol


# --------------------------------------------------------------------------- Ventana de parada
TRAFFIC_WINDOW = 25.0   # s: el tráfico se calcula donde la estrategia limpia está cerca del óptimo


def _with_traffic(tot: np.ndarray, stints_of, penalty, ref: float, window: float = TRAFFIC_WINDOW) -> np.ndarray:
    """Suma el tráfico a las celdas a menos de ``window`` s de ``ref``.

    Las celdas más lejanas quedan fuera de la escala del gráfico (tope = mínimo + 15 s) aun sin
    tráfico, porque el tráfico solo puede sumar tiempo.
    """
    if penalty is None:
        return tot
    out = tot.copy()
    for idx in zip(*np.nonzero(np.isfinite(tot) & (tot <= ref + window))):
        out[idx] = tot[idx] + penalty(stints_of(*idx)).loss
    return out


def pit_window_curves(model, laps_done: int, first_age: int, pit_losses: np.ndarray,
                      penalty=None, best_total: float | None = None) -> dict:
    """Tiempo de la estrategia frente al óptimo para cada vuelta de parada (1 parada).

    Devuelve {(c1, c2): array} con NaN donde la estrategia no es factible, y la
    referencia ``best`` = coste de la mejor estrategia de 1 o 2 paradas. Con ``penalty``
    (función stints → resultado de tráfico) cada punto incluye el tiempo perdido en tráfico
    y ``best_total`` es el óptimo con tráfico de la auditoría.
    """
    N = laps_done
    comps = model.usable_compounds
    pl = pit_losses[: N + 1]
    s = np.arange(N + 1)
    curves = {}
    for c1 in comps:
        for c2 in comps:
            if c1 == c2:
                continue
            tot = _stint_cost_array(model, c1, N, first_age)[s] + _stint_cost_array(model, c2, N, 1)[N - s] + pl[s]
            if np.isfinite(tot).any():
                ref = float(np.min(tot[np.isfinite(tot)]))
                # 1 parada: pocas vueltas posibles, se calcula el tráfico en todas
                tot = _with_traffic(tot, lambda k, a=c1, b=c2: [(a, int(k)), (b, int(N - k))], penalty, ref, np.inf)
                curves[(c1, c2)] = np.where(np.isfinite(tot), tot, np.nan)
    strategies = enumerate_strategies(model, N, first_age, pit_losses)
    best = strategies[0].cost if strategies else (np.nanmin([np.nanmin(c) for c in curves.values()]) if curves else 0.0)
    if best_total is not None:
        best = min(best_total, min((np.nanmin(c) for c in curves.values()), default=best_total))
    best2 = next((st for st in strategies if st.stops == 2), None)
    return {"curves": {k: v - best for k, v in curves.items()},
            "best2": (best2.cost - best) if best2 else None,
            "best2_label": best2.label() if best2 else None}


def window_range(curve: np.ndarray, tol: float = 1.0) -> tuple[int, int] | None:
    """Vueltas de parada a menos de ``tol`` segundos del mínimo de la curva."""
    if curve is None or not np.isfinite(curve).any():
        return None
    ok = np.where(curve <= np.nanmin(curve) + tol)[0]
    return int(ok.min()), int(ok.max())


def pit_window(win: dict, pair: tuple[str, str] | None, stop_alt: int | None,
               stop_real: int | None, tol: float = 1.0) -> go.Figure:
    """Curvas de tiempo perdido según la vuelta de parada, una por combinación de compuestos."""
    curves = win["curves"]
    if not curves:
        return empty("No hay combinaciones de 1 parada factibles en esta carrera")
    fig = go.Figure()
    sel = pair if pair in curves else min(curves, key=lambda k: np.nanmin(curves[k]))
    rng = window_range(curves[sel], tol)
    if rng:
        fig.add_vrect(x0=rng[0] - 0.5, x1=rng[1] + 0.5, fillcolor=GAIN, opacity=0.08, line_width=0, layer="below")
        fig.add_annotation(x=(rng[0] + rng[1]) / 2, y=1, yref="paper", yanchor="bottom", showarrow=False,
                           text=f"ventana ±{fmt_s(tol, dec=0)}", font=dict(color=GAIN, size=11))
    order = sorted(curves, key=lambda k: (k == sel, -np.nanmin(curves[k])))   # seleccionada encima
    for k in order:
        y = curves[k]
        x = np.arange(len(y))
        is_sel = k == sel
        name = f"{INITIAL[k[0]]} → {INITIAL[k[1]]}"
        col = COMPOUND[k[1]]["stroke"] if is_sel else CONTEXT
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", showlegend=False, connectgaps=False,
            line=dict(color=col, width=3 if is_sel else 1.5),
            hovertemplate=(f"<b>{COMPOUND_ES[k[0]]} → {COMPOUND_ES[k[1]]}</b><br>Parada en la vuelta %{{x}}"
                           "<br>+%{y:.1f} s frente al óptimo<extra></extra>"),
        ))
        i = int(np.nanargmin(y))
        fig.add_trace(go.Scatter(
            x=[i], y=[y[i]], mode="markers", showlegend=False, hoverinfo="skip",
            marker=dict(size=9 if is_sel else 6, color=COMPOUND[k[1]]["fill"] if is_sel else CONTEXT,
                        line=dict(color=COMPOUND[k[1]]["edge"] if is_sel else CONTEXT, width=1.5)),
        ))
        sel_min = int(np.nanargmin(curves[sel]))
        if is_sel or abs(i - sel_min) > 4:            # etiqueta en el mínimo, salvo si se pisa con la elegida
            fig.add_annotation(x=i, y=y[i], text=(f"<b>{name}</b> · V{i}" if is_sel else name), showarrow=False,
                               yanchor="bottom" if is_sel else "top", yshift=10 if is_sel else -8,
                               font=dict(color=TEXT if is_sel else MUTED, size=12 if is_sel else 11))
    if win.get("best2") is not None:
        txt = (f"el óptimo es a 2 paradas: {win['best2_label']}" if win["best2"] < 0.05 else
               f"mejor a 2 paradas ({win['best2_label']}) · {fmt_s(win['best2'], signed=True)}")
        fig.add_hline(y=win["best2"], line=dict(color=PRIMARY, width=1, dash="dash"),
                      annotation_text=txt,
                      annotation_position="top left", annotation_font=dict(color=MUTED, size=11))
    if stop_real:
        fig.add_vline(x=stop_real, line=dict(color=MUTED, width=1, dash="dash"),
                      annotation_text="real", annotation_position="bottom right",
                      annotation_font=dict(color=MUTED, size=11))
    if stop_alt and pair in curves and np.isfinite(curves[pair][stop_alt]):
        fig.add_trace(go.Scatter(
            x=[stop_alt], y=[curves[pair][stop_alt]], mode="markers", showlegend=False,
            marker=dict(size=13, color=ACCENT, symbol="x-thin", line=dict(color=ACCENT, width=3)),
            hovertemplate="<b>Tu parada</b> · vuelta %{x}<br>+%{y:.1f} s frente al óptimo<extra></extra>",
        ))
    n = max(len(v) for v in curves.values())
    fig.update_xaxes(title_text="Vuelta de la parada", range=[0, n + 1])
    # Eje hasta 20 s, o más si la curva elegida queda por encima (con tráfico puede pasar)
    top = 20.0
    if sel in curves and np.isfinite(curves[sel]).any():
        top = max(top, float(np.nanmin(curves[sel])) + 12)
    fig.update_yaxes(title_text="Tiempo perdido frente al óptimo (s)", range=[-2.5, top], zeroline=False)
    fig.add_hline(y=0, line=dict(color=MUTED, width=1))
    return _base(fig, height=340)


def pit_window_2stop(model, laps_done: int, first_age: int, pit_losses: np.ndarray,
                     comps: tuple[str, str, str], stops_alt: tuple[int, int] | None,
                     best_cost: float | None = None, penalty=None) -> tuple[go.Figure, dict]:
    """Mapa de calor del tiempo perdido para cada par de vueltas de parada (2 paradas)."""
    N = laps_done
    c1, c2, c3 = comps
    s1 = np.arange(N + 1)[:, None]
    s2 = np.arange(N + 1)[None, :]
    d = np.clip(s2 - s1, 0, N)
    pl = pit_losses[: N + 1]
    tot = (_stint_cost_array(model, c1, N, first_age)[s1] + _stint_cost_array(model, c2, N, 1)[d]
           + _stint_cost_array(model, c3, N, 1)[N - s2] + pl[s1] + pl[s2])
    tot = np.where(s2 > s1, tot, np.inf)
    info = {"ok": bool(np.isfinite(tot).any())}
    if not info["ok"]:
        return empty("Esta combinación de compuestos no es factible con 2 paradas"), info
    tot = _with_traffic(tot, lambda i, j: [(c1, int(i)), (c2, int(j - i)), (c3, int(N - j))], penalty,
                        float(np.min(tot[np.isfinite(tot)])))
    if best_cost is None:
        st = enumerate_strategies(model, N, first_age, pit_losses)
        best_cost = st[0].cost if st else float(np.min(tot))
    best_cost = min(best_cost, float(np.min(tot[np.isfinite(tot)])))
    z = np.where(np.isfinite(tot), tot - best_cost, np.nan)
    i, j = np.unravel_index(np.nanargmin(z), z.shape)
    info.update(best=(int(i), int(j)), loss=float(z[i, j]))
    cap = float(np.nanmin(z)) + 15
    fig = go.Figure(go.Heatmap(
        x=np.arange(N + 1), y=np.arange(N + 1), z=np.minimum(z, cap), customdata=z,
        colorscale=T.WINDOW_SCALE,
        zmin=float(np.nanmin(z)), zmax=cap, hoverongaps=False,
        colorbar=dict(title=dict(text="s", font=dict(color=MUTED)), tickfont=dict(color=MUTED),
                      thickness=10, outlinewidth=0),
        hovertemplate=("<b>Paradas en V%{y} y V%{x}</b><br>+%{customdata:.1f} s frente al óptimo"
                       "<extra></extra>"),
    ))
    # Contorno de la zona a menos de 1 s del mejor punto de esta combinación
    fig.add_trace(go.Contour(
        x=np.arange(N + 1), y=np.arange(N + 1), z=z, showscale=False, hoverinfo="skip",
        contours=dict(start=float(z[i, j]) + 1, end=float(z[i, j]) + 1, size=1, coloring="none"),
        line=dict(color=TEXT, width=1.2, dash="dot"), showlegend=False,
    ))
    fig.add_trace(go.Scatter(x=[j], y=[i], mode="markers", showlegend=False,
                             marker=dict(size=10, color=GAIN, line=dict(color=PANEL, width=2)),
                             hovertemplate="<b>Óptimo de esta combinación</b><br>V%{y} y V%{x}<extra></extra>"))
    if stops_alt:
        fig.add_trace(go.Scatter(x=[stops_alt[1]], y=[stops_alt[0]], mode="markers", showlegend=False,
                                 marker=dict(size=13, color=ACCENT, symbol="x-thin", line=dict(color=ACCENT, width=3)),
                                 hovertemplate="<b>Tu estrategia</b><br>V%{y} y V%{x}<extra></extra>"))
    rows, cols = np.where(np.isfinite(z))
    fig.update_xaxes(title_text="Vuelta de la 2.ª parada", range=[cols.min() - 1, cols.max() + 1], showgrid=False)
    fig.update_yaxes(title_text="Vuelta de la 1.ª parada", range=[rows.min() - 1, rows.max() + 1], showgrid=False)
    return _base(fig, height=380), info


# --------------------------------------------------------------------------- Validación del modelo
def model_error_by_race(races: pd.DataFrame, race_abbr: dict[int, str], race_names: dict[int, str]) -> go.Figure:
    """Error medio del modelo por carrera: en el ajuste frente a validación cruzada por stints."""
    r = races.dropna(subset=["MAE_cv"]).sort_values("MAE_cv")
    y = [race_abbr.get(int(x), str(x)) for x in r["Round"]]
    names = [race_names.get(int(x), str(x)) for x in r["Round"]]
    fig = go.Figure()
    for yy, a, b in zip(y, r["MAE_train"], r["MAE_cv"]):
        fig.add_trace(go.Scatter(x=[a, b], y=[yy, yy], mode="lines", showlegend=False, hoverinfo="skip",
                                 line=dict(color=CONTEXT, width=3)))
    fig.add_trace(go.Scatter(
        x=r["MAE_train"], y=y, mode="markers", name="Ajuste (vueltas usadas)",
        marker=dict(size=9, color=PANEL, line=dict(color=PRIMARY, width=2)), customdata=names,
        hovertemplate="<b>%{customdata}</b><br>Error en el ajuste · %{x:.2f} s/vuelta<extra></extra>"))
    fig.add_trace(go.Scatter(
        x=r["MAE_cv"], y=y, mode="markers", name="Validación cruzada (stints no vistos)",
        marker=dict(size=9, color=ACCENT), customdata=np.stack([names, r["CleanLaps"].fillna(0)], axis=1),
        hovertemplate=("<b>%{customdata[0]}</b><br>Error en validación · %{x:.2f} s/vuelta"
                       "<br>%{customdata[1]:.0f} vueltas limpias<extra></extra>")))
    med = float(r["MAE_cv"].median())
    fig.add_vline(x=med, line=dict(color=MUTED, width=1, dash="dot"),
                  annotation_text=f"mediana {fmt_s(med, dec=2)}", annotation_position="bottom right",
                  annotation_font=dict(color=MUTED, size=11))
    fig.update_xaxes(title_text="Error absoluto medio (s/vuelta)", rangemode="tozero")
    fig.update_yaxes(categoryorder="array", categoryarray=y)
    _hbar_axes(fig)
    fig = _base(fig, height=max(380, 22 * len(r) + 90))
    fig.update_layout(legend=dict(y=1.0))
    return fig


def residuals_by_compound(laps: pd.DataFrame) -> go.Figure:
    """Distribución de residuos (real − modelo) en vueltas limpias, por compuesto."""
    d = laps[laps["IsClean"] & laps["Predicted"].notna()].copy()
    d["Res"] = d["LapTime"] - d["Predicted"]
    lim = float(np.nanpercentile(d["Res"].abs(), 99))
    fig = go.Figure()
    for c in [c for c in COMPOUND_ORDER if c in set(d["Compound"])]:
        r = d.loc[d["Compound"] == c, "Res"]
        r = r[r.abs() <= lim]
        style = COMPOUND[c]
        fig.add_trace(go.Violin(
            x=r, y=[COMPOUND_ES[c]] * len(r), orientation="h", name=COMPOUND_ES[c], showlegend=False,
            line=dict(color=style["edge"], width=1.2), fillcolor=with_alpha(style["stroke"], 0.25),
            points=False, meanline=dict(visible=True, color=TEXT, width=1.5), box=dict(visible=False),
            spanmode="hard", width=0.8, hoverinfo="skip",
        ))
        fig.add_annotation(x=lim, y=COMPOUND_ES[c], xanchor="right", yshift=14, showarrow=False,
                           text=f"σ = {fmt_s(float(r.std()), dec=2)} · n = " + f"{len(r):,}".replace(",", "."),
                           font=dict(color=MUTED, size=11))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1))
    fig.update_xaxes(title_text="Residuo: real − modelo (s)", range=[-lim, lim])
    _hbar_axes(fig)
    return _base(fig, height=320)


# --------------------------------------------------------------------------- Tráfico
def overtake_threshold(races: pd.DataFrame, race_abbr: dict[int, str], race_names: dict[int, str]) -> go.Figure:
    """Ventaja de ritmo necesaria para adelantar en cada carrera (calibrada con los datos)."""
    r = races.dropna(subset=["OvertakeDelta"]).sort_values("OvertakeDelta")
    y = [race_abbr.get(int(x), str(x)) for x in r["Round"]]
    hardest = r["OvertakeDelta"].max()
    colors = [ACCENT if v == hardest else with_alpha(PRIMARY, 0.45) for v in r["OvertakeDelta"]]
    fig = go.Figure(go.Bar(
        x=r["OvertakeDelta"], y=y, orientation="h", marker=dict(color=colors, cornerradius=3),
        text=[T.fmt_s(v) for v in r["OvertakeDelta"]], textposition="outside", cliponaxis=False,
        textfont=dict(color=T.TEXT_2),
        customdata=np.stack([[race_names.get(int(x), "") for x in r["Round"]],
                             (r["PassRate"].fillna(0) * 100).round(1), r["FollowSituations"].fillna(0)], axis=1),
        hovertemplate=("<b>%{customdata[0]}</b><br>Umbral: %{x:.2f} s por vuelta"
                       "<br>%{customdata[1]} % de las situaciones a menos de 1 s acabaron en adelantamiento"
                       "<br>%{customdata[2]} situaciones<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Ventaja necesaria (s por vuelta)", range=[0, hardest * 1.18])
    _hbar_axes(fig)
    return _base(fig, height=max(380, 22 * len(r) + 80))


def traffic_validation(validation: pd.DataFrame, race_abbr: dict[int, str]) -> go.Figure:
    """Error del simulador por piloto, sin tráfico frente a con tráfico."""
    if validation.empty or "ErrorTraffic" not in validation:
        return empty("Sin carreras sin SC/VSC para validar")
    v = validation.dropna(subset=["ErrorTraffic"])
    fig = go.Figure()
    for col, name, color in [("Error", "Pista libre", with_alpha(PRIMARY, 0.4)), ("ErrorTraffic", "Con tráfico", ACCENT)]:
        fig.add_trace(go.Box(
            x=v[col].clip(-30, 30), y=[name] * len(v), name=name, orientation="h", boxpoints="all",
            jitter=0.35, pointpos=0, marker=dict(color=color, size=6, opacity=0.75),
            line=dict(color=color), fillcolor="rgba(0,0,0,0)", boxmean=True,
            hoveron="points",  # solo la etiqueta del punto, sin las estadísticas de la caja
            customdata=np.stack([v["Driver"], [race_abbr.get(int(r), "") for r in v["Round"]], v[col]], axis=1),
            hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]:+.1f} s<extra></extra>",
        ))
    fig.add_vline(x=0, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_xaxes(title_text="Simulado − real (s) · recortado a ±30 s", range=[-31, 31])
    _hbar_axes(fig)
    return _base(fig, height=300)
