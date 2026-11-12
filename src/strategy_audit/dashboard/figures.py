"""Figuras Plotly del dashboard. Funciones puras: reciben datos, devuelven figuras."""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from strategy_audit.config import COMPOUND_COLORS

# Tema oscuro (superficie, tintas y acento)
SURFACE = "#15151c"
PANEL = "#1d1d26"
GRID = "#2c2c38"
TEXT = "#f0efec"
TEXT_2 = "#c3c2b7"
MUTED = "#8a897f"
ACCENT = "#3987e5"     # serie única / magnitud
LOSS = "#e66767"       # tiempo perdido
GAIN = "#199e70"       # tiempo ganado
FONT = "Inter, -apple-system, Segoe UI, Roboto, sans-serif"

COMPOUND_SHORT = {"SOFT": "Blando", "MEDIUM": "Medio", "HARD": "Duro"}


def _base(fig: go.Figure, height: int = 420, title: str | None = None) -> go.Figure:
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(family=FONT, color=TEXT_2, size=12),
        height=height,
        margin=dict(l=60, r=20, t=50 if title else 20, b=40),
        title=dict(text=title, font=dict(color=TEXT, size=15), x=0.01) if title else None,
        hoverlabel=dict(bgcolor=SURFACE, bordercolor=GRID, font=dict(color=TEXT, family=FONT)),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, bgcolor="rgba(0,0,0,0)"),
    )
    fig.update_xaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    fig.update_yaxes(gridcolor=GRID, zerolinecolor=GRID, linecolor=GRID, tickfont=dict(color=MUTED))
    return fig


def empty(msg: str = "Sin datos") -> go.Figure:
    fig = _base(go.Figure(), height=300)
    fig.add_annotation(text=msg, showarrow=False, font=dict(color=MUTED, size=14), x=0.5, y=0.5,
                       xref="paper", yref="paper")
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def _stint_bars(fig, stints: pd.DataFrame, order: list[str], col: int, shown: set):
    for c in ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]:
        s = stints[stints["Compound"] == c]
        if s.empty:
            continue
        fig.add_trace(go.Bar(
            y=s["Driver"], x=s["Laps"], base=s["StartLap"] - 1, orientation="h",
            name=COMPOUND_SHORT.get(c, c.title()), legendgroup=c, showlegend=c not in shown,
            marker=dict(color=COMPOUND_COLORS[c], line=dict(color=PANEL, width=2)),
            customdata=np.stack([s["StartLap"], s["EndLap"], s["Laps"]], axis=1),
            hovertemplate="<b>%{y}</b> · " + COMPOUND_SHORT.get(c, c) +
                          "<br>Vueltas %{customdata[0]}–%{customdata[1]} (%{customdata[2]})<extra></extra>",
        ), row=1, col=col)
        shown.add(c)


def stint_comparison(actual: pd.DataFrame, best: pd.DataFrame, order: list[str],
                     neutral: set[int], total_laps: int) -> go.Figure:
    """Stints reales frente a los de la mejor estrategia simulada, por piloto."""
    fig = make_subplots(rows=1, cols=2, shared_yaxes=True, horizontal_spacing=0.04,
                        subplot_titles=("Estrategia real", "Mejor estrategia simulada"))
    shown: set = set()
    _stint_bars(fig, actual[actual["Driver"].isin(order)], order, 1, shown)
    _stint_bars(fig, best[best["Driver"].isin(order)], order, 2, shown)
    for lap in sorted(neutral):
        for col in (1, 2):
            fig.add_vrect(x0=lap - 1, x1=lap, fillcolor="#eda100", opacity=0.12, line_width=0, row=1, col=col)
    fig.update_layout(barmode="overlay", bargap=0.35)
    fig.update_yaxes(categoryorder="array", categoryarray=order[::-1])
    fig.update_xaxes(range=[0, total_laps], title_text="Vuelta")
    fig = _base(fig, height=max(380, 26 * len(order) + 120))
    for ann in fig.layout.annotations:
        ann.font = dict(color=TEXT, size=13)
    return fig


def delta_bars(audit: pd.DataFrame) -> go.Figure:
    """Strategy Delta por piloto (segundos perdidos frente a la mejor estrategia)."""
    a = audit.sort_values("StrategyDelta")
    fig = go.Figure(go.Bar(
        x=a["StrategyDelta"], y=a["Driver"], orientation="h",
        marker=dict(color=ACCENT, cornerradius=4),
        text=[f"{v:.1f} s" if v >= 0.5 else "" for v in a["StrategyDelta"]],
        textposition="outside", textfont=dict(color=TEXT_2), cliponaxis=False,
        customdata=np.stack([a["Team"].fillna(""), a["ActualStrategy"], a["BestStrategy"],
                             a["AuditedPosition"], a["EstPosition"]], axis=1),
        hovertemplate=("<b>%{y}</b> · %{customdata[0]}<br>Strategy Delta: <b>%{x:.1f} s</b>"
                       "<br>Real: %{customdata[1]}<br>Óptima: %{customdata[2]}"
                       "<br>Posición: P%{customdata[3]} → P%{customdata[4]} estimada<extra></extra>"),
    ))
    fig.update_xaxes(title_text="Segundos perdidos por la estrategia",
                     range=[0, max(float(a["StrategyDelta"].max()), 1.0) * 1.12])
    return _base(fig, height=max(380, 24 * len(a) + 80))


def degradation(laps: pd.DataFrame, model) -> go.Figure:
    """Vueltas limpias frente a la edad del neumático, con la recta del modelo por compuesto."""
    fig = go.Figure()
    clean = laps[laps["IsClean"]]
    # Se corrige el ritmo de cada piloto y el combustible para comparar solo el efecto del neumático
    corr = clean["LapTime"] - clean["Driver"].map(model.driver_base) - model.fuel * clean["LapNumber"]
    for c in ["SOFT", "MEDIUM", "HARD"]:
        m = clean["Compound"] == c
        if not m.any() or c not in model.compound_deg:
            continue
        fig.add_trace(go.Scattergl(
            x=clean.loc[m, "TyreLife"], y=corr[m], mode="markers", name=COMPOUND_SHORT[c], legendgroup=c,
            marker=dict(color=COMPOUND_COLORS[c], size=6, opacity=0.35),
            customdata=clean.loc[m, ["Driver", "LapNumber"]].to_numpy(),
            hovertemplate="%{customdata[0]} · vuelta %{customdata[1]}<br>Edad %{x} · %{y:+.2f} s<extra></extra>",
        ))
        x = np.arange(1, int(clean.loc[m, "TyreLife"].max()) + 1)
        y = model.compound_offset[c] + model.compound_deg[c] * x
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines", legendgroup=c, showlegend=False,
            line=dict(color=COMPOUND_COLORS[c], width=2.5),
            hovertemplate=f"{COMPOUND_SHORT[c]}: {model.compound_deg[c]:+.3f} s/vuelta<extra></extra>",
        ))
    fig.update_xaxes(title_text="Edad del neumático (vueltas)")
    fig.update_yaxes(title_text="Tiempo relativo (s)")
    return _base(fig, height=380)


def whatif_gap(cum_gap: np.ndarray, stops_alt: list[int], stops_real: list[int]) -> go.Figure:
    """Diferencia acumulada (alternativa − real simulada) vuelta a vuelta."""
    laps = np.arange(1, len(cum_gap) + 1)
    fig = go.Figure()
    fig.add_hline(y=0, line=dict(color=MUTED, width=1, dash="dot"))
    fig.add_trace(go.Scatter(
        x=laps, y=cum_gap, mode="lines", line=dict(color=ACCENT, width=2.5), name="Alternativa − real",
        hovertemplate="Vuelta %{x}<br>%{y:+.1f} s<extra></extra>", showlegend=False,
    ))
    for s in stops_real:
        fig.add_vline(x=s, line=dict(color=MUTED, width=1, dash="dash"))
    for s in stops_alt:
        fig.add_vline(x=s, line=dict(color=ACCENT, width=1))
    final = cum_gap[-1]
    fig.add_annotation(x=laps[-1], y=final, text=f"{final:+.1f} s", showarrow=False, xanchor="left",
                       xshift=6, font=dict(color=GAIN if final < 0 else LOSS, size=13))
    fig.update_xaxes(title_text="Vuelta", range=[0, len(cum_gap) + 6])
    fig.update_yaxes(title_text="s (negativo = alternativa más rápida)")
    return _base(fig, height=340)


def whatif_laps(real: pd.DataFrame, sim_alt: np.ndarray, sim_real: np.ndarray, pit_mask_alt, pit_mask_real) -> go.Figure:
    """Tiempos por vuelta: reales, modelo con la estrategia real y alternativa."""
    laps = np.arange(1, len(sim_alt) + 1)
    fig = go.Figure()
    r = real[~real["IsPitIn"] & (real["LapNumber"] > 1)]
    fig.add_trace(go.Scatter(x=r["LapNumber"], y=r["LapTime"], mode="markers", name="Real",
                             marker=dict(color=MUTED, size=6),
                             hovertemplate="Vuelta %{x}<br>Real %{y:.3f} s<extra></extra>"))
    y_real = np.where(pit_mask_real, np.nan, sim_real)
    y_alt = np.where(pit_mask_alt, np.nan, sim_alt)
    fig.add_trace(go.Scatter(x=laps, y=y_real, mode="lines", name="Modelo · estrategia real",
                             line=dict(color=TEXT_2, width=2, dash="dash"),
                             hovertemplate="Vuelta %{x}<br>%{y:.3f} s<extra></extra>"))
    fig.add_trace(go.Scatter(x=laps, y=y_alt, mode="lines", name="Modelo · alternativa",
                             line=dict(color=ACCENT, width=2.5),
                             hovertemplate="Vuelta %{x}<br>%{y:.3f} s<extra></extra>"))
    lo = np.nanpercentile(np.r_[r["LapTime"].to_numpy(), y_alt[~np.isnan(y_alt)]], 1) - 0.5
    hi = np.nanpercentile(np.r_[r["LapTime"].to_numpy(), y_alt[~np.isnan(y_alt)]], 97) + 1.0
    fig.update_yaxes(range=[lo, hi], title_text="Tiempo por vuelta (s)")
    fig.update_xaxes(title_text="Vuelta")
    return _base(fig, height=340)


def team_ranking(audit: pd.DataFrame) -> go.Figure:
    """Segundos perdidos por estrategia de media por carrera, por equipo."""
    t = (audit.groupby("Team").agg(Delta=("StrategyDelta", "mean"), Color=("TeamColor", "first"),
                                   N=("StrategyDelta", "size")).sort_values("Delta", ascending=False))
    fig = go.Figure(go.Bar(
        x=t["Delta"], y=t.index, orientation="h", marker=dict(color=t["Color"], cornerradius=4),
        text=[f"{v:.1f} s" for v in t["Delta"]], textposition="outside", textfont=dict(color=TEXT_2),
        cliponaxis=False,
        customdata=t["N"],
        hovertemplate="<b>%{y}</b><br>%{x:.2f} s por piloto y carrera<br>%{customdata} auditorías<extra></extra>",
    ))
    fig.update_xaxes(title_text="Strategy Delta medio (s) — menos es mejor",
                     range=[0, max(float(t["Delta"].max()), 1.0) * 1.15])
    fig.update_yaxes(categoryorder="array", categoryarray=list(t.index))
    return _base(fig, height=max(360, 34 * len(t) + 80))


def season_heatmap(audit: pd.DataFrame, race_names: dict[int, str]) -> go.Figure:
    """Mapa de calor piloto × carrera con el Strategy Delta (escala secuencial de un solo tono)."""
    pv = audit.pivot_table(index="Driver", columns="Round", values="StrategyDelta")
    pv = pv.loc[pv.mean(axis=1).sort_values().index]
    cols = [race_names.get(int(c), str(c)) for c in pv.columns]
    fig = go.Figure(go.Heatmap(
        z=pv.to_numpy(), x=cols, y=pv.index, xgap=2, ygap=2,
        colorscale=[[0, "#1d2a3d"], [0.5, "#2f6fb8"], [1, "#a9cdf5"]], zmin=0,
        zmax=float(np.nanpercentile(pv.to_numpy(), 95)) if pv.size else 1,
        colorbar=dict(title=dict(text="s", font=dict(color=TEXT_2)), tickfont=dict(color=MUTED)),
        hovertemplate="<b>%{y}</b> · %{x}<br>%{z:.1f} s<extra></extra>", hoverongaps=False,
    ))
    fig.update_xaxes(tickangle=-45, showgrid=False)
    fig.update_yaxes(showgrid=False)
    return _base(fig, height=max(420, 22 * len(pv) + 140))


def team_evolution(audit: pd.DataFrame, race_names: dict[int, str]) -> go.Figure:
    """Segundos perdidos acumulados por equipo a lo largo de la temporada."""
    t = audit.groupby(["Team", "Round"]).agg(Delta=("StrategyDelta", "sum"), Color=("TeamColor", "first")).reset_index()
    fig = go.Figure()
    for team, g in t.groupby("Team"):
        g = g.sort_values("Round")
        cum = g["Delta"].cumsum()
        fig.add_trace(go.Scatter(
            x=[race_names.get(int(r), str(r)) for r in g["Round"]], y=cum, mode="lines+markers", name=team,
            line=dict(color=g["Color"].iloc[0], width=2), marker=dict(size=8, line=dict(color=PANEL, width=2)),
            hovertemplate=f"<b>{team}</b><br>%{{x}}<br>Acumulado: %{{y:.1f}} s<extra></extra>",
        ))
    fig.update_xaxes(tickangle=-45)
    fig.update_yaxes(title_text="Segundos perdidos acumulados")
    fig.update_layout(legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"))
    fig = _base(fig, height=460)
    fig.update_layout(legend=dict(orientation="v", x=1.02, y=1, xanchor="left", yanchor="top"),
                      margin=dict(r=160))
    return fig
