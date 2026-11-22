"""Estructura visual (HTML + componentes Dash) de la aplicación."""
from __future__ import annotations

import os

from dash import dcc, html

from strategy_audit.dashboard.data import Store
from strategy_audit.dashboard.theme import ACCENT, GRAPH_CONFIG, fmt_num, fmt_s

# Commit desplegado (Render lo expone en RENDER_GIT_COMMIT): permite comprobar qué versión está en línea
APP_VERSION = os.environ.get("RENDER_GIT_COMMIT", "")[:7]

COMPOUND_OPTIONS = [{"label": "Blando", "value": "SOFT"},
                    {"label": "Medio", "value": "MEDIUM"},
                    {"label": "Duro", "value": "HARD"}]


def kpi(label: str, value: str, hint: str = "", tone: str | None = None) -> html.Div:
    """Tarjeta KPI. ``tone`` = "loss" o "gain" colorea solo el valor."""
    value_cls = "kpi-value" + (f" kpi-{tone}" if tone else "")
    return html.Div(className="kpi", children=[
        html.Div(label, className="kpi-label"),
        html.Div(value, className=value_cls),
        html.Div(hint, className="kpi-hint"),
    ])


def card(title, children, subtitle: str | None = None, id_: str | None = None,
         class_name: str = "") -> html.Div:
    """Tarjeta: el título es la conclusión (dinámico si se da ``id_``) y el subtítulo explica la medida."""
    t_kw = {"id": f"{id_}-title"} if id_ else {}
    s_kw = {"id": f"{id_}-sub"} if id_ else {}
    head = [html.H3(title, **t_kw), html.P(subtitle or "", className="card-sub", **s_kw)]
    return html.Div(className=f"card {class_name}", children=[html.Div(head, className="card-head"), *children])


def graph(id_: str) -> html.Div:
    # En el móvil el contenedor se desplaza en horizontal: el gráfico conserva un ancho legible
    config = {**GRAPH_CONFIG, "toImageButtonOptions": {
        **GRAPH_CONFIG["toImageButtonOptions"], "filename": f"f1-strategy-audit-{id_}"}}
    return html.Div(dcc.Loading(dcc.Graph(id=id_, config=config), type="dot", color=ACCENT),
                    className="graph-scroll")


def header(store: Store) -> html.Div:
    m = store.metrics
    total_lost = store.audit["StrategyDelta"].sum()
    return html.Div(className="header", children=[
        html.Div(className="brand", children=[
            html.Div("F1", className="logo"),
            html.Div([html.H1("Strategy Audit"),
                      html.P(f"¿Ganó o perdió tiempo cada piloto por su estrategia? · Temporada {store.season}")]),
        ]),
        html.Div(className="kpis", children=[
            kpi("Carreras auditadas", f"{len(store.audited_rounds)}", f"de {m.get('races', '—')} disputadas (en seco)"),
            kpi("Error del modelo de ritmo", fmt_s(m.get("pace_model_mae_cv_s", float("nan")), dec=2),
                "por vuelta, en stints no usados en el ajuste"),
            kpi("Error del simulador", fmt_s(m.get("simulator_median_abs_s", float("nan"))),
                "típico (mediana) en el tiempo total de carrera, con tráfico"),
            kpi("Tiempo perdido por estrategia", f"{fmt_num(total_lost / 60, 0)} min",
                "suma de toda la parrilla", tone="loss"),
        ]),
    ])


def race_tab(store: Store) -> html.Div:
    rounds = store.audited_rounds
    return html.Div(className="tab-body", children=[
        html.Div(className="controls", children=[
            html.Div([html.Label("Gran Premio"),
                      dcc.Dropdown(id="race-dd", options=store.race_options(),
                                   value=rounds[-1] if rounds else None, clearable=False, className="dd")]),
            html.Div([html.Label("Destacar piloto"),
                      dcc.Dropdown(id="race-focus", placeholder="Ninguno: mejor y peor", className="dd")]),
            html.Div(className="controls-action", children=[
                html.Button("Descargar CSV", id="race-csv", className="btn",
                            title="Auditoría de esta carrera: estrategia real, óptima y Strategy Delta por piloto"),
                dcc.Download(id="race-download"),
            ]),
        ]),
        html.Div(id="race-kpis", className="kpis kpis-small"),
        card("", [graph("race-stints")], id_="race-stints-card"),
        card("", [graph("race-trace")], id_="race-trace-card"),
        html.Div(className="grid-2", children=[
            card("", [graph("race-delta")], id_="race-delta-card"),
            card("", [graph("race-deg")], id_="race-deg-card"),
        ]),
    ])


def whatif_tab(store: Store) -> html.Div:
    rounds = store.audited_rounds
    return html.Div(className="tab-body", children=[
        html.Div(className="whatif", children=[
            html.Div(className="card panel", children=[
                html.H3("Diseña tu estrategia"),
                html.P("Cambia neumáticos y vueltas de parada y compara con lo que hizo el piloto.",
                       className="card-sub"),
                html.Label("Gran Premio"),
                dcc.Dropdown(id="wi-race", options=store.race_options(), value=rounds[-1] if rounds else None,
                             clearable=False, className="dd"),
                html.Label("Piloto"),
                dcc.Dropdown(id="wi-driver", clearable=False, className="dd"),
                html.Label("Número de paradas"),
                dcc.RadioItems(id="wi-stops", options=[{"label": " 1 parada", "value": 1},
                                                       {"label": " 2 paradas", "value": 2}],
                               value=1, inline=True, className="radio"),
                html.Div(className="stint-row", children=[
                    html.Div([html.Label("Stint 1"), dcc.Dropdown(id="wi-c1", options=COMPOUND_OPTIONS, clearable=False)]),
                    html.Div([html.Label("Stint 2"), dcc.Dropdown(id="wi-c2", options=COMPOUND_OPTIONS, clearable=False)]),
                    html.Div(id="wi-c3-wrap", children=[html.Label("Stint 3"),
                                                        dcc.Dropdown(id="wi-c3", options=COMPOUND_OPTIONS, clearable=False)]),
                ]),
                html.Label("Vuelta de la 1.ª parada"),
                dcc.Slider(id="wi-s1", min=1, max=60, step=1, value=20, marks=None,
                           tooltip={"placement": "top"}),
                html.Div(id="wi-s2-wrap", children=[
                    html.Label("Vuelta de la 2.ª parada"),
                    dcc.Slider(id="wi-s2", min=1, max=60, step=1, value=40, marks=None,
                               tooltip={"placement": "top"}),
                ]),
                html.Div(className="buttons", children=[
                    html.Button("Estrategia real", id="wi-reset", className="btn"),
                    html.Button("Mejor simulada", id="wi-best", className="btn btn-primary"),
                ]),
                html.Div(id="wi-warning"),
            ]),
            html.Div(className="whatif-results", children=[
                html.Div(id="wi-kpis", className="kpis kpis-small"),
                card("", [graph("wi-gap")], id_="wi-gap-card"),
                card("", [graph("wi-window")], id_="wi-window-card"),
                card("Ritmo vuelta a vuelta: real frente al modelo", [graph("wi-laps")],
                     "Tiempo por vuelta (s) · puntos = real, discontinua = modelo con la estrategia real, "
                     "roja = alternativa"),
            ]),
        ]),
    ])


def season_tab(store: Store) -> html.Div:
    teams = sorted(store.audit["Team"].dropna().unique())
    return html.Div(className="tab-body", children=[
        html.Div(className="controls", children=[
            html.Div([html.Label("Destacar equipo"),
                      dcc.Dropdown(id="season-focus", options=[{"label": t, "value": t} for t in teams],
                                   placeholder="Ninguno: mejor y peor", className="dd")]),
        ]),
        html.Div(className="grid-2", children=[
            card("", [graph("season-teams")], id_="season-teams-card"),
            card("", [graph("season-positions")], id_="season-positions-card"),
        ]),
        card("", [graph("season-evolution")], id_="season-evolution-card"),
        card("", [graph("season-heatmap")], id_="season-heatmap-card"),
    ])


def validation_cards(store: Store) -> html.Div:
    """Gráficos de validación del modelo (estáticos: se calculan una vez al arrancar)."""
    from strategy_audit.dashboard import figures as F

    rounds = store.audited_rounds
    names = {r: store.race_es(r) for r in rounds}
    abbr = {r: store.race_abbr(r) for r in rounds}
    r = store.races.dropna(subset=["MAE_cv"])
    worst = r.loc[r["MAE_cv"].idxmax()]
    gap = float((r["MAE_cv"] - r["MAE_train"]).median())
    res = store.laps[store.laps["IsClean"] & store.laps["Predicted"].notna()]
    bias = float((res["LapTime"] - res["Predicted"]).median())
    def static(fig):   # figura fija: con «responsive» necesita una altura explícita en el contenedor
        return dcc.Graph(figure=fig, config=GRAPH_CONFIG, style={"height": f"{fig.layout.height}px"})

    m = store.metrics
    bias0, bias1 = m.get("simulator_bias_clean_s", float("nan")), m.get("simulator_bias_s", float("nan"))
    tr = store.races.dropna(subset=["OvertakeDelta"]) if "OvertakeDelta" in store.races else store.races.iloc[0:0]
    hardest = tr.loc[tr["OvertakeDelta"].idxmax()] if len(tr) else None
    easiest = tr.loc[tr["OvertakeDelta"].idxmin()] if len(tr) else None
    traffic_cards = [] if hardest is None else [
        card(f"Sin tráfico el simulador iba {fmt_s(-bias0)} por delante de la realidad; "
             f"con tráfico, {fmt_s(abs(bias1))} de media",
             [static(F.traffic_validation(store.validation, abbr))],
             "Tiempo total simulado − real con la estrategia real (s), por piloto, en carreras sin SC/VSC · "
             "gris: pista libre, rojo: con tráfico"),
        card(f"Adelantar en el {names.get(int(hardest['Round']), '')} exigía ir "
             f"{fmt_s(hardest['OvertakeDelta'])} por vuelta más rápido; en el "
             f"{names.get(int(easiest['Round']), '')}, {fmt_s(easiest['OvertakeDelta'])}",
             [static(F.overtake_threshold(tr, abbr, names))],
             "Ventaja de ritmo por vuelta necesaria para adelantar (s), calibrada con los adelantamientos "
             "reales de cada carrera · más alto = más difícil"),
    ]
    return html.Div(className="grid-2 method-wide", children=[
        *traffic_cards,
        card(f"El error solo sube {fmt_s(gap, dec=2)} por vuelta al validar con stints no vistos; "
             f"el {names.get(int(worst['Round']), '')} es la excepción",
             [static(F.model_error_by_race(store.races, abbr, names))],
             "Error absoluto medio por vuelta (s) · círculo: vueltas del ajuste, rojo: validación cruzada "
             "dejando fuera stints completos"),
        card(f"Los residuos están centrados en cero en todos los compuestos (mediana {fmt_s(bias, dec=2, signed=True)})",
             [static(F.residuals_by_compound(store.laps))],
             "Real − modelo en vueltas limpias (s) · línea discontinua: media · sin sesgo por compuesto"),
    ])


def method_tab(store: Store) -> html.Div:
    m = store.metrics
    mae = fmt_s(m.get("pace_model_mae_cv_s", float("nan")), dec=2)
    sim = fmt_s(m.get("simulator_median_abs_s", float("nan")))
    bias0 = fmt_s(-m.get("simulator_bias_clean_s", float("nan")))
    bias1 = fmt_s(m.get("simulator_bias_s", float("nan")), signed=True)
    coef = fmt_s(m.get("traffic_coef_s", float("nan")), dec=2)
    return html.Div(className="tab-body method", children=[
        validation_cards(store),
        card("Cómo se audita cada estrategia", [dcc.Markdown(f"""
**1 · Datos.** Tiempos por vuelta, neumáticos, paradas y estado de pista de cada carrera de {store.season}
con [FastF1](https://docs.fastf1.dev/). Se excluyen la vuelta 1, las vueltas de entrada y salida de boxes,
las vueltas con SC/VSC y los valores atípicos. Las carreras con lluvia o con datos de neumáticos
incompletos quedan fuera. Cada vuelta se marca «en tráfico» si empezó con otro coche a menos de 1,5 s.

**2 · Modelo de ritmo.** Para cada carrera, una regresión lineal por mínimos cuadrados:

`tiempo = ritmo del piloto + efecto del compuesto + degradación × edad del neumático + combustible × vuelta + coste de ir en tráfico`

Así el ritmo de cada piloto es el de **aire limpio**: ir detrás de otro coche cuesta de media **{coef}
por vuelta**. Validación cruzada dejando fuera stints completos: **error medio de {mae} por vuelta**.

**3 · Pérdida en boxes.** Mediana, por carrera, del tiempo extra de las vueltas de entrada y salida
frente al ritmo del modelo, en paradas con bandera verde. Con SC/VSC se cuenta la mitad.

**4 · Tráfico.** Los rivales se quedan exactamente como corrieron de verdad y solo se mueve el piloto
estudiado. Vuelta a vuelta se compara su tiempo acumulado con el de los demás: si va a alcanzar a un
coche, solo lo adelanta si esa vuelta es más rápido que él por encima de un **umbral** propio de cada
circuito; si no, se queda detrás y pierde el tiempo que no puede aprovechar. El umbral se calibra con la
carrera: entre todas las veces que un coche fue a menos de 1 s de otro, el modelo adelanta en la misma
proporción que hubo adelantamientos reales. Bajo SC/VSC no hay adelantamientos.

**5 · Simulador.** Tiempo de cada vuelta según el modelo, más las paradas, más el tráfico, para todas las
combinaciones de 1 y 2 paradas que cumplen el reglamento (dos compuestos de seco) y no superan la
longitud de stint observada. Con la estrategia real y sin tráfico, el simulador iba **{bias0} por delante**
de la realidad; con tráfico el sesgo es **{bias1}** y el error típico, **{sim}** en el tiempo total.

**6 · Strategy Delta.** Tiempo simulado con la estrategia real − tiempo simulado con la mejor
estrategia, ambos con tráfico. La mejor se busca recorriendo las estrategias de más rápida a más lenta en
pista libre y parando cuando ninguna restante puede mejorar (el tráfico solo suma tiempo). Al comparar dos
simulaciones del mismo modelo, el error del modelo se cancela en gran parte. La posición estimada compara
el tiempo real menos el delta con los tiempos reales de los rivales.
""")], "Método, validación y unidades"),
        card("Qué no tiene en cuenta", [dcc.Markdown("""
- Los rivales no reaccionan: si el piloto hubiera parado antes, ellos habrían corrido igual (no le
  cubren ni se ven frenados por él). Tampoco se cuentan los doblados, que ceden con banderas azules.
- El adelantamiento es todo o nada: si tiene ritmo suficiente pasa, si no se queda detrás.
- Es una auditoría *a posteriori*: la mejor estrategia «sabe» cuándo hubo SC/VSC.
- Se asume neumático nuevo en cada parada (no se sabe qué juegos le quedaban a cada piloto).
- Degradación lineal; una degradación estimada negativa (pista que mejora) se trunca a 0.
- No se modelan el calentamiento del neumático ni la salida: el modelo tiende a preferir empezar con duro.
- Incidencias que ningún modelo prevé (averías, toques, problemas de frenos) explican los errores más grandes.
- Reglas especiales de 2025 incluidas: dos paradas obligatorias en Mónaco y máximo de 25 vueltas por juego en Qatar.
- El GP de Miami queda fuera: FastF1 no trae los neumáticos de las primeras 24 vueltas de casi toda
  la parrilla y los stints posteriores llegan desalineados, así que la auditoría no sería fiable.
""")], "Limitaciones conocidas del modelo"),
    ])


def build_layout(store: Store | None) -> html.Div:
    if store is None or not store.audited_rounds:
        return html.Div(className="app", children=[html.Div(className="card", children=[
            html.H1("F1 Strategy Audit"),
            html.P("Todavía no hay datos procesados. Ejecuta scripts/download_data.py y "
                   "scripts/build_dataset.py y vuelve a arrancar la aplicación."),
        ])])
    return html.Div(className="app", children=[
        dcc.Location(id="url", refresh=False),
        dcc.Store(id="url-params"),
        header(store),
        html.Div(className="share", children=[
            dcc.Clipboard(id="share-copy", title="Copiar enlace a esta vista", className="share-icon"),
            html.Span("Copiar enlace a esta vista", className="share-label"),
        ]),
        dcc.Tabs(id="tabs", value="race", className="tabs", mobile_breakpoint=0, children=[
            dcc.Tab(label="Análisis de carrera", value="race", children=race_tab(store),
                    className="tab", selected_className="tab--selected"),
            dcc.Tab(label="¿Y si…?", value="whatif", children=whatif_tab(store),
                    className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Temporada", value="season", children=season_tab(store),
                    className="tab", selected_className="tab--selected"),
            dcc.Tab(label="Metodología", value="method", children=method_tab(store),
                    className="tab", selected_className="tab--selected"),
        ]),
        html.Footer([
            "Proyecto de Desarrollo de Aplicaciones para la Visualización de Datos · ICAI-ICADE · ",
            html.A("Código en GitHub", href="https://github.com/gabrieladorre-design/F1-Strategy-Audit", target="_blank"),
            " · Datos: FastF1. Proyecto no oficial, sin relación con la Fórmula 1.",
            html.Span(f" · Versión {APP_VERSION}", className="version") if APP_VERSION else None,
        ]),
    ])
