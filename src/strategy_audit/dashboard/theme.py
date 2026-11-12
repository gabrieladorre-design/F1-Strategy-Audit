"""Sistema visual de F1 Strategy Audit: tokens, plantilla Plotly y formato numérico.

Única fuente de verdad de colores y estilo: las figuras importan de aquí y no
llevan colores sueltos.
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

# ---------------------------------------------------------------- Superficies y tinta
SURFACE = "#F7F7F5"   # fondo de página
PANEL = "#FFFFFF"     # tarjetas y fondo de figuras
PANEL_2 = "#F1F1EE"   # controles, code, hover suave
LINE = "#E4E3DF"      # bordes de tarjeta, ejes
GRID = "#EEEDE9"      # cuadrícula (muy tenue)
TEXT = "#1A1A1F"      # títulos, valores
TEXT_2 = "#44444C"    # texto normal, etiquetas de datos
MUTED = "#76767F"     # ticks, subtítulos, notas

# ---------------------------------------------------------------- Datos
PRIMARY = "#2B2F3A"   # serie única / magnitud (carbón)
ACCENT = "#C8102E"    # rojo F1 sobrio: foco, selección
CONTEXT = "#D2D2D7"   # series en segundo plano
LOSS = "#C8102E"      # tiempo perdido
GAIN = "#1E7F4F"      # tiempo ganado
NEUTRAL_BAND = "#E8A317"  # SC/VSC (siempre con opacidad 0,10-0,15)

# Escala secuencial de un solo tono (Strategy Delta, mapas de calor)
SEQ_RED = [[0, "#FBEDEE"], [0.5, "#E0566A"], [1, "#7A0A1C"]]

FONT = "'Titillium Web', -apple-system, 'Segoe UI', Roboto, sans-serif"

# ---------------------------------------------------------------- Neumáticos
# Colores Pirelli adaptados a fondo blanco: el Medio y el Duro necesitan contorno
COMPOUND = {
    "SOFT": dict(fill="#DA291C", edge="#DA291C", stroke="#DA291C"),
    "MEDIUM": dict(fill="#FFD12E", edge="#B8930A", stroke="#D9A900"),
    "HARD": dict(fill="#FFFFFF", edge="#3A3A40", stroke="#3A3A40"),
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
    colorway=[PRIMARY, ACCENT, "#6B7280", "#9CA3AF"],
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

GRAPH_CONFIG = {"displayModeBar": False, "responsive": True}


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
