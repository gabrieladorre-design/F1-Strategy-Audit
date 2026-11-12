"""Estructura visual (HTML + componentes Dash) de la aplicación."""
from __future__ import annotations

from dash import dcc, html

from strategy_audit.dashboard.data import Store

COMPOUND_OPTIONS = [{"label": "Blando", "value": "SOFT"},
                    {"label": "Medio", "value": "MEDIUM"},
                    {"label": "Duro", "value": "HARD"}]
GRAPH_CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}


def kpi(label: str, value: str, hint: str = "", id_: str | None = None) -> html.Div:
    kw = {"id": id_} if id_ else {}
    return html.Div(className="kpi", children=[
        html.Div(label, className="kpi-label"),
        html.Div(value, className="kpi-value", **kw),
        html.Div(hint, className="kpi-hint"),
    ])


def card(title: str, children, subtitle: str | None = None, class_name: str = "") -> html.Div:
    head = [html.H3(title)]
    if subtitle:
        head.append(html.P(subtitle, className="card-sub"))
    return html.Div(className=f"card {class_name}", children=[html.Div(head, className="card-head"), *children])


def graph(id_: str) -> dcc.Loading:
    return dcc.Loading(dcc.Graph(id=id_, config=GRAPH_CONFIG), type="dot", color="#3987e5")


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
            kpi("Error del modelo de ritmo", f"{m.get('pace_model_mae_cv_s', float('nan')):.2f} s",
                "MAE por vuelta en stints no vistos"),
            kpi("Error del simulador", f"{m.get('simulator_mae_s', float('nan')):.1f} s",
                "tiempo total, carreras sin SC"),
            kpi("Tiempo perdido por estrategia", f"{total_lost / 60:.0f} min", "suma de toda la parrilla"),
        ]),
    ])


def race_tab(store: Store) -> html.Div:
    rounds = store.audited_rounds
    return html.Div(className="tab-body", children=[
        html.Div(className="controls", children=[
            html.Label("Gran Premio"),
            dcc.Dropdown(id="race-dd", options=store.race_options(), value=rounds[-1] if rounds else None,
                         clearable=False, className="dd"),
        ]),
        html.Div(id="race-kpis", className="kpis kpis-small"),
        card("Estrategia real frente a la mejor simulada", [graph("race-stints")],
             "Ordenado por posición final. Las franjas amarillas marcan vueltas con Safety Car o VSC."),
        html.Div(className="grid-2", children=[
            card("Strategy Delta por piloto", [graph("race-delta")],
                 "Segundos que la estrategia elegida costó frente a la mejor alternativa simulada."),
            card("Degradación de neumáticos (modelo)", [graph("race-deg")],
                 "Vueltas limpias corregidas por piloto y combustible; la recta es la degradación estimada."),
        ]),
    ])


def whatif_tab(store: Store) -> html.Div:
    rounds = store.audited_rounds
    return html.Div(className="tab-body", children=[
        html.Div(className="whatif", children=[
            html.Div(className="card panel", children=[
                html.H3("Diseña tu estrategia"),
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
                html.Label("Vuelta de la 1ª parada"),
                dcc.Slider(id="wi-s1", min=1, max=60, step=1, value=20, marks=None,
                           tooltip={"placement": "top"}),
                html.Div(id="wi-s2-wrap", children=[
                    html.Label("Vuelta de la 2ª parada"),
                    dcc.Slider(id="wi-s2", min=1, max=60, step=1, value=40, marks=None,
                               tooltip={"placement": "top"}),
                ]),
                html.Div(className="buttons", children=[
                    html.Button("Estrategia real", id="wi-reset", className="btn"),
                    html.Button("Mejor simulada", id="wi-best", className="btn btn-primary"),
                ]),
                html.Div(id="wi-warning", className="warning"),
            ]),
            html.Div(className="whatif-results", children=[
                html.Div(id="wi-kpis", className="kpis kpis-small"),
                card("Diferencia acumulada frente a la estrategia real", [graph("wi-gap")],
                     "Por debajo de 0, la alternativa va por delante. Líneas: paradas (gris = real, azul = alternativa)."),
                card("Tiempo por vuelta", [graph("wi-laps")]),
            ]),
        ]),
    ])


def season_tab(store: Store) -> html.Div:
    return html.Div(className="tab-body", children=[
        html.Div(className="grid-2", children=[
            card("Ranking de equipos", [graph("season-teams")],
                 "Media de segundos perdidos por estrategia, por piloto y carrera."),
            card("Pilotos que más posiciones perdieron", [graph("season-positions")],
                 "Posiciones que habrían ganado con la mejor estrategia (suma de la temporada)."),
        ]),
        card("Evolución por equipo", [graph("season-evolution")],
             "Segundos perdidos acumulados carrera a carrera (suma de sus dos pilotos)."),
        card("Mapa de calor piloto × carrera", [graph("season-heatmap")],
             "Cuanto más claro, más tiempo costó la estrategia. Huecos: carrera no auditada (lluvia o abandono)."),
    ])


def method_tab(store: Store) -> html.Div:
    m = store.metrics
    return html.Div(className="tab-body method", children=[
        card("Cómo funciona", [dcc.Markdown(f"""
**1 · Datos.** Tiempos por vuelta, neumáticos, paradas y estado de pista de cada carrera de {store.season}
con [FastF1](https://docs.fastf1.dev/). Se excluyen la vuelta 1, las vueltas de entrada y salida de boxes,
las vueltas con Safety Car/VSC y los valores atípicos. Las carreras con lluvia quedan fuera.

**2 · Modelo de ritmo.** Para cada carrera, una regresión lineal por mínimos cuadrados:

`tiempo = ritmo del piloto + efecto del compuesto + degradación × edad del neumático + combustible × vuelta`

Validación cruzada dejando fuera stints completos: **error medio de {m.get('pace_model_mae_cv_s', float('nan')):.2f} s por vuelta**.

**3 · Pérdida en boxes.** Mediana, por carrera, del tiempo extra de las vueltas de entrada y salida
frente al ritmo del modelo, en paradas con bandera verde. Con SC/VSC se cuenta la mitad.

**4 · Simulador.** Suma el tiempo de cada vuelta según el modelo más las paradas, para todas las
combinaciones de 1 y 2 paradas y compuestos que cumplen el reglamento (dos compuestos de seco) y
no superan la longitud de stint observada en la carrera. Con la estrategia real, el tiempo total
simulado se desvía **{m.get('simulator_mae_s', float('nan')):.1f} s** de media del real (carreras sin SC).

**5 · Strategy Delta.** Tiempo simulado con la estrategia real − tiempo simulado con la mejor
estrategia. Al comparar dos simulaciones del mismo modelo, el error del modelo se cancela en gran parte.
La posición estimada compara el tiempo real menos el delta con los tiempos reales de los rivales.
"""), ]),
        card("Limitaciones", [dcc.Markdown("""
- No se modela la interacción entre coches (tráfico, aire sucio, adelantamientos): parar antes puede ser
  más rápido en el modelo pero dejarte detrás de otro coche.
- Es una auditoría *a posteriori*: la mejor estrategia «sabe» cuándo hubo Safety Car.
- Se asume neumático nuevo en cada parada (no se sabe qué juegos le quedaban a cada piloto).
- Degradación lineal; una degradación estimada negativa (pista que mejora) se trunca a 0.
- No se modelan el calentamiento del neumático ni la salida: el modelo tiende a preferir empezar con duro.
- En circuitos sin adelantamientos (Mónaco, Singapur) el ritmo está limitado por el tráfico y el error es mayor.
- Reglas especiales de 2025 incluidas: dos paradas obligatorias en Mónaco y máximo de 25 vueltas por juego en Qatar.
- Pilotos sin datos de compuesto en parte de la carrera (p. ej. Miami) no se auditan.
""")]),
    ])


def build_layout(store: Store | None) -> html.Div:
    if store is None or not store.audited_rounds:
        return html.Div(className="app", children=[html.Div(className="card", children=[
            html.H1("F1 Strategy Audit"),
            html.P("Todavía no hay datos procesados. Ejecuta scripts/download_data.py y scripts/build_dataset.py."),
        ])])
    return html.Div(className="app", children=[
        header(store),
        dcc.Tabs(id="tabs", value="race", className="tabs", children=[
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
        ]),
    ])
