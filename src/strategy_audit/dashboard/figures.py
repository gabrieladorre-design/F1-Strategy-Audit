"""Figuras Plotly del dashboard. Funciones puras: reciben datos, devuelven figuras.

Estilo: ver ``theme.py`` (plantilla «strategy_audit», tokens y formato en español).
El título de cada gráfico vive en la tarjeta de Dash, no dentro de la figura.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from strategy_audit.dashboard import theme as T
from strategy_audit.dashboard.theme import (
    ACCENT, COMPOUND, COMPOUND_ES, COMPOUND_ORDER, CONTEXT, GAIN, LOSS, MUTED, NEUTRAL_BAND,
    PANEL, PRIMARY, SEQ_RED, TEXT, fmt_deg, fmt_s, team_color, with_alpha,
)


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
    if neutral:
        first = min(neutral)
        fig.add_annotation(x=first - 0.5, y=1.0, yref="paper", text="SC/VSC", showarrow=False,
                           font=dict(color=MUTED, size=10), yanchor="bottom", xref="x")

    ticks = [f"<b>{d}</b>" if d == focus else d for d in order]
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(categoryorder="array", categoryarray=order[::-1], showgrid=False,
                     tickmode="array", tickvals=order, ticktext=ticks)
    fig.update_xaxes(range=[0, total_laps + 0.5], title_text="Vuelta")
    fig = _base(fig, height=max(380, 26 * len(order) + 110))
    fig.update_layout(margin=dict(t=56))
    for ann in fig.layout.annotations:
        if ann.text in ("Estrategia real", "Mejor estrategia simulada"):
            ann.font = dict(color=TEXT, size=13)
            ann.x = 0 if ann.text == "Estrategia real" else 0.52
            ann.xanchor = "left"
    fig.update_layout(legend=dict(x=1, xanchor="right", y=1.08))
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
        customdata=np.stack([names, a["Team"].fillna(""), a["ActualStrategy"], a["BestStrategy"],
                             a["AuditedPosition"], a["EstPosition"]], axis=1),
        hovertemplate=("<b>%{customdata[0]}</b> · %{customdata[1]}"
                       "<br>Strategy Delta · %{x:.1f} s"
                       "<br>Real · %{customdata[2]}<br>Óptima · %{customdata[3]}"
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
                               font=dict(color=team_color(COMPOUND[c]["stroke"], for_text=True), size=11))
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
    fig.add_trace(go.Scatter(x=r["LapNumber"], y=r["LapTime"], mode="markers", name="Real",
                             marker=dict(color=MUTED, size=6),
                             hovertemplate="<b>Vuelta %{x}</b><br>Real · %{y:.3f} s<extra></extra>"))
    y_real = np.where(pit_mask_real, np.nan, sim_real)
    y_alt = np.where(pit_mask_alt, np.nan, sim_alt)
    fig.add_trace(go.Scatter(x=laps, y=y_real, mode="lines", name="Modelo · estrategia real",
                             line=dict(color=PRIMARY, width=2, dash="dash"),
                             hovertemplate="<b>Vuelta %{x}</b><br>Modelo real · %{y:.3f} s<extra></extra>"))
    fig.add_trace(go.Scatter(x=laps, y=y_alt, mode="lines", name="Modelo · alternativa",
                             line=dict(color=ACCENT, width=2.5),
                             hovertemplate="<b>Vuelta %{x}</b><br>Alternativa · %{y:.3f} s<extra></extra>"))
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


def team_ranking(audit: pd.DataFrame, focus: str | None = None) -> go.Figure:
    """Segundos perdidos por estrategia de media por piloto y carrera, por equipo."""
    t = _team_table(audit)
    best, worst = t["Delta"].idxmin(), t["Delta"].idxmax()
    highlighted = {focus} if focus in t.index else {best, worst}
    colors = [team_color(c) if team in highlighted else with_alpha(team_color(c), 0.35)
              for team, c in zip(t.index, t["Color"])]
    fig = go.Figure(go.Bar(
        x=t["Delta"], y=t.index, orientation="h", marker=dict(color=colors, cornerradius=3),
        text=[fmt_s(v) for v in t["Delta"]], textposition="outside", textfont=dict(color=T.TEXT_2),
        cliponaxis=False, customdata=t["N"],
        hovertemplate="<b>%{y}</b><br>Strategy Delta medio · %{x:.2f} s<br>%{customdata} auditorías<extra></extra>",
    ))
    fig.update_xaxes(title_text="Strategy Delta medio (s)", range=[0, float(t["Delta"].max()) * 1.18])
    fig.update_yaxes(categoryorder="array", categoryarray=list(t.index))
    _hbar_axes(fig)
    return _base(fig, height=max(360, 34 * len(t) + 70))


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
    fig = go.Figure(go.Heatmap(
        z=z, x=cols, y=pv.index, xgap=2, ygap=2, customdata=full,
        colorscale=SEQ_RED, zmin=0, zmax=float(np.nanpercentile(z, 95)) if np.isfinite(z).any() else 1,
        colorbar=dict(title=dict(text="s", font=dict(color=MUTED)), tickfont=dict(color=MUTED),
                      thickness=10, outlinewidth=0),
        hovertemplate="<b>%{y}</b> · %{customdata}<br>Strategy Delta · %{z:.1f} s<extra></extra>",
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
