"""Sistema visual de F1 Strategy Audit: tokens, plantilla Plotly y formato numérico.

Colores de la web de F1 (rojo #E10600, blanco, grises y negro carbono), igual que
el design system «F1 Strategy Audit» (tema claro).

Única fuente de verdad de colores y estilo: las figuras importan de aquí y no
llevan colores sueltos.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------- Superficies y tinta
SURFACE = "#F4F4F4"   # fondo de página (gris claro F1)
PANEL = "#FFFFFF"     # tarjetas y fondo de figuras
PANEL_2 = "#EDEDED"   # controles, code, hover suave
LINE = "#D0D0D2"      # bordes de tarjeta (esquina F1), ejes
GRID = "#EEEEEF"      # cuadrícula (muy tenue)
TEXT = "#15151E"      # títulos, valores (negro carbono F1)
TEXT_2 = "#38383F"    # texto normal, etiquetas de datos
MUTED = "#6C6C74"     # ticks, subtítulos, notas (4,7:1 sobre SURFACE)

CARBON = "#15151E"    # cabecera (texto blanco encima, 18:1)
ON_CARBON_MUTED = "#949498"  # subtítulo sobre CARBON (6:1)

# ---------------------------------------------------------------- Datos
PRIMARY = "#15151E"   # serie única / magnitud (carbono)
ACCENT = "#E10600"    # rojo F1: foco, selección (5,0:1 sobre blanco)
CONTEXT = "#D0D0D2"   # series en segundo plano
LOSS = ACCENT         # tiempo perdido
GAIN = "#1E7F4F"      # tiempo ganado
NEUTRAL_BAND = "#E8A317"  # SC/VSC (siempre con opacidad 0,10-0,15)

# Escala secuencial de un solo tono (Strategy Delta, mapas de calor)
SEQ_RED = [[0, "#FBEDEE"], [0.5, "#F0606A"], [1, "#8A0400"]]
# Ventana de parada: verde en el óptimo y rojo creciente al alejarse (s perdidos)
WINDOW_SCALE = [[0, "#1E7F4F"], [0.07, "#DDEFE4"], [0.25, "#FBEDEE"], [0.6, "#F0606A"], [1, "#8A0400"]]

FONT = "'Titillium Web', -apple-system, 'Segoe UI', Roboto, sans-serif"

# ---------------------------------------------------------------- Neumáticos
# Colores Pirelli adaptados a fondo blanco: el Medio y el Duro necesitan contorno
COMPOUND = {
    "SOFT": dict(fill="#DA291C", edge="#DA291C", stroke="#DA291C"),
    "MEDIUM": dict(fill="#FFD12E", edge="#B8930A", stroke="#D9A900"),
    "HARD": dict(fill="#FFFFFF", edge="#38383F", stroke="#38383F"),
    "INTERMEDIATE": dict(fill="#43B02A", edge="#43B02A", stroke="#43B02A"),
    "WET": dict(fill="#0067AD", edge="#0067AD", stroke="#0067AD"),
}
COMPOUND_ES = {"SOFT": "Blando", "MEDIUM": "Medio", "HARD": "Duro",
               "INTERMEDIATE": "Intermedio", "WET": "Lluvia"}
COMPOUND_ORDER = ["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"]


def team_color(hex_: str, for_text: bool = False) -> str:
    """Oscurece colores de equipo demasiado claros para fondo blanco."""
    h = str(hex_).lstrip("#")
    if len(h) != 6:
        return PRIMARY
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))

    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    def contrast(k):
        lum = 0.2126 * lin(r * k) + 0.7152 * lin(g * k) + 0.0722 * lin(b * k)
        return 1.05 / (lum + 0.05)

    need = 4.5 if for_text else 3.0
    k = 1.0
    while contrast(k) < need and k > 0.3:
        k -= 0.05
    if k < 1:
        return "#" + "".join(f"{int(c * k * 255):02X}" for c in (r, g, b))
    return "#" + h.upper()


def with_alpha(hex_: str, alpha: float) -> str:
    """Color hex con transparencia (rgba) para atenuar el contexto."""
    h = hex_.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{alpha})"


# ---------------------------------------------------------------- Plantilla Plotly
pio.templates["strategy_audit"] = go.layout.Template(layout=dict(
    font=dict(family=FONT, color=TEXT_2, size=13),
    paper_bgcolor=PANEL, plot_bgcolor=PANEL,
    separators=",.",                       # decimal con coma (español)
    colorway=[PRIMARY, ACCENT, MUTED, "#B4B4BA"],
    margin=dict(l=56, r=24, t=16, b=44),
    hoverlabel=dict(bgcolor=PANEL, bordercolor=LINE, font=dict(family=FONT, color=TEXT, size=13)),
    legend=dict(orientation="h", x=0, xanchor="left", y=1.02, yanchor="bottom",
                bgcolor="rgba(0,0,0,0)", font=dict(color=TEXT_2), title_text=""),
    xaxis=dict(showgrid=False, zeroline=False, showline=True, linecolor=LINE, linewidth=1,
               ticks="outside", tickcolor=LINE, ticklen=4, tickfont=dict(color=MUTED, size=12),
               title=dict(font=dict(color=MUTED, size=13), standoff=8)),
    yaxis=dict(showgrid=True, gridcolor=GRID, gridwidth=1, zeroline=False, showline=False,
               tickfont=dict(color=MUTED, size=12), title=dict(font=dict(color=MUTED, size=13), standoff=8)),
    bargap=0.3,
))

# Gráficos sin barra de herramientas
GRAPH_CONFIG = {"responsive": True, "displayModeBar": False, "locale": "es"}


# ---------------------------------------------------------------- Formato (español de España)
def fmt_s(v, dec: int = 1, signed: bool = False) -> str:
    s = f"{abs(v):.{dec}f}".replace(".", ",")
    sign = ("+" if v > 0 else "−" if v < 0 else "") if signed else ("−" if v < 0 else "")
    return f"{sign}{s} s"


def fmt_lap(v) -> str:
    """Tiempo de vuelta con 3 decimales; en formato m:ss,mmm si supera un minuto."""
    if v >= 60:
        m, sec = divmod(v, 60)
        return f"{int(m)}:{sec:06.3f}".replace(".", ",")
    return f"{v:.3f}".replace(".", ",") + " s"


def fmt_deg(v) -> str:
    sign = "+" if v >= 0 else "−"
    return f"{sign}{abs(v):.3f}".replace(".", ",") + " s/vuelta"


def fmt_num(v, dec: int = 1) -> str:
    return f"{v:.{dec}f}".replace(".", ",")


def fmt_pos(p) -> str:
    return f"P{int(p)}"


def fmt_vuelta(n) -> str:
    return f"V{int(n)}"


def fmt_pct(v) -> str:
    return f"{v * 100:.0f} %"


# ---------------------------------------------------------------- Estrategias en lenguaje normal
_INITIAL_ES = {"B": "blando", "M": "medio", "D": "duro", "I": "intermedio", "LL": "lluvia"}


def fmt_strategy(label: str) -> str:
    """«D (V34) → M» → «Duro hasta la vuelta 34 y medio hasta el final»."""
    import re
    parts = [re.match(r"\s*(\w+)(?:\s*\(V(\d+)\))?", p).groups() for p in str(label).split("→")]
    names = [_INITIAL_ES.get(c, c) for c, _ in parts]
    # Si repite compuesto, es un juego nuevo del mismo: «otro duro»
    names = [n if i == 0 or n != names[i - 1] else f"otro {n}" for i, n in enumerate(names)]
    if len(parts) == 1:
        return f"{names[0].capitalize()} toda la carrera"
    out = [f"{names[0].capitalize()} hasta la vuelta {parts[0][1]}"]
    out += [f"{n} hasta la {lap}" for n, (_, lap) in zip(names[1:-1], parts[1:-1])]
    return ", ".join(out) + f" y {names[-1]} hasta el final"
