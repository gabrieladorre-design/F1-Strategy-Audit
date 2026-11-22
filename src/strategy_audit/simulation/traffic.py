"""Tráfico: qué pasa al salir de boxes detrás de otros coches.

Idea: los rivales se quedan exactamente como corrieron de verdad (sus tiempos
reales vuelta a vuelta) y solo se mueve el piloto que se estudia, con los tiempos
que da el simulador para la estrategia que se prueba.

Vuelta a vuelta se comparan los tiempos acumulados. Si con su ritmo el piloto fuese
a pasar a un coche que tenía delante, solo lo consigue si es claramente más rápido
que él esa vuelta (más que el *umbral de adelantamiento* del circuito). Si no, se
queda detrás y pierde el tiempo que no puede aprovechar. Ese tiempo perdido es la
**penalización por tráfico** de la estrategia.

El umbral se calibra con la propia carrera: se miran todas las veces que un coche
fue a menos de 1 s de otro y cuántas acabaron en adelantamiento. Donde casi no se
adelanta (Mónaco, Singapur) el umbral sale alto; donde se adelanta mucho, bajo.

Simplificaciones: los rivales no reaccionan a la estrategia del piloto (no paran
para cubrirle ni se ven frenados por él); solo cuenta el tráfico de coches en su
misma vuelta (los doblados ceden con banderas azules); bajo SC/VSC el piloto conserva
su vuelta real (todos van en fila) y no se cuenta tráfico.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

FOLLOW_GAP = 1.0      # s: a menos de 1 s va «pegado» (rango de DRS)
MIN_GAP = 0.2         # s: hueco mínimo detrás de un coche al que no puede adelantar
DELTA_MIN, DELTA_MAX, DELTA_DEFAULT = 0.2, 3.0, 1.0
MIN_SITUATIONS = 30   # situaciones mínimas para calibrar el umbral con la carrera


@dataclass
class RaceTraffic:
    """Posición en pista de todos los coches de una carrera, vuelta a vuelta."""
    drivers: list[str]
    cum: np.ndarray            # (pilotos, vueltas+1): tiempo acumulado al final de cada vuelta (NaN si no la dio)
    lap_time: np.ndarray       # (pilotos, vueltas+1): tiempo de cada vuelta
    field_lap: np.ndarray      # (vueltas+1,): mediana de la vuelta en el pelotón, sin vueltas de boxes
    pit: np.ndarray            # (pilotos, vueltas+1): vuelta de entrada o salida de boxes
    neutral: set[int]
    overtake_delta: float      # s más rápido que el de delante necesarios para adelantarle
    pass_rate: float = float("nan")
    situations: int = 0

    def index(self, driver: str) -> int:
        return self.drivers.index(driver)

    def others_by_lap(self, me: int) -> tuple[list[int], list[list[float]], list[list[float]]]:
        """Tiempos acumulados y por vuelta de los rivales, como listas por vuelta (con caché)."""
        cache = self.__dict__.setdefault("_by_lap", {})
        if me not in cache:
            others = [i for i in range(len(self.drivers)) if i != me]
            cache[me] = (others, self.cum[others].T.tolist(), self.lap_time[others].T.tolist())
        return cache[me]


@dataclass
class TrafficResult:
    loss: float                                  # s perdidos detrás de otros coches
    held_laps: int                               # vueltas en las que no pudo ir a su ritmo
    rejoins: list[tuple[int, list[str], float]] = field(default_factory=list)  # (vuelta, coches delante, hueco)
    cum: np.ndarray | None = None                # tiempo acumulado del piloto con tráfico
    lost_by_lap: np.ndarray | None = None        # s perdidos en tráfico en cada vuelta (índice 0 = vuelta 1)


def _cumulative(race_laps: pd.DataFrame) -> tuple[list[str], np.ndarray, np.ndarray, np.ndarray]:
    total = int(race_laps["LapNumber"].max())
    drivers = sorted(race_laps["Driver"].unique())
    lt = np.full((len(drivers), total + 1), np.nan)
    pit = np.zeros(lt.shape, dtype=bool)
    for i, (drv, d) in enumerate(race_laps.groupby("Driver", sort=True)):
        t = d.set_index("LapNumber")["LapTime"]
        t = t.fillna(t.median())             # vueltas sueltas sin tiempo: mediana del piloto
        lt[i, t.index.astype(int)] = t.to_numpy()
        pin = d.loc[d["IsPitIn"].fillna(False).astype(bool), "LapNumber"].astype(int).to_numpy()
        pit[i, pin] = True
        pit[i, np.clip(pin + 1, 0, total)] = True      # vuelta de salida
    lt[:, 0] = 0.0
    cum = np.cumsum(lt, axis=1)              # NaN a partir de la retirada
    return drivers, lt, cum, pit


def calibrate_overtaking(race_laps: pd.DataFrame, drivers: list[str], lt: np.ndarray,
                         cum: np.ndarray, pit: np.ndarray, neutral: set[int]) -> tuple[float, float, int]:
    """Umbral de adelantamiento que reproduce la tasa real de adelantamientos de la carrera.

    Situación: al final de la vuelta L-1 el coche A va a menos de 1 s del B, en bandera
    verde y sin que ninguno entre o salga de boxes. Ventaja de ritmo de A = vuelta real
    de B − vuelta que el modelo predice para A. Si en la carrera se resolvieron con
    adelantamiento el p % de las situaciones, el umbral es el percentil (100 − p) de esa
    ventaja: el modelo adelanta en la misma proporción de casos que la realidad.
    """
    total = lt.shape[1] - 1
    idx = {d: i for i, d in enumerate(drivers)}
    pred = np.full_like(lt, np.nan)
    for drv, d in race_laps.groupby("Driver"):
        col = "PredictedFree" if "PredictedFree" in d else "Predicted"   # ritmo en aire limpio
        pred[idx[drv], d["LapNumber"].astype(int).to_numpy()] = d[col].to_numpy(float)
    advs, passed = [], []
    for L in range(3, total + 1):
        if L in neutral or (L - 1) in neutral:
            continue
        prev, now = cum[:, L - 1], cum[:, L]
        ok = ~np.isnan(prev) & ~np.isnan(now) & ~pit[:, L] & ~pit[:, L - 1] & ~np.isnan(pred[:, L])
        gap = prev[:, None] - prev[None, :]                   # gap[a, b] > 0: A va detrás de B
        close = (gap > 0) & (gap <= FOLLOW_GAP) & ok[:, None] & ok[None, :]
        for a, b in zip(*np.nonzero(close)):
            advs.append(lt[b, L] - pred[a, L])
            passed.append(now[a] < now[b])
    n = len(advs)
    if n < MIN_SITUATIONS:
        return DELTA_DEFAULT, float("nan"), n
    rate = float(np.mean(passed))
    delta = float(np.quantile(advs, 1 - rate)) if rate > 0 else DELTA_MAX
    return float(np.clip(delta, DELTA_MIN, DELTA_MAX)), rate, n


def build_traffic(race_laps: pd.DataFrame, neutral: set[int], overtake_delta: float | None = None) -> RaceTraffic:
    """Prepara el tráfico de una carrera. Sin ``overtake_delta``, lo calibra con los datos."""
    drivers, lt, cum, pit = _cumulative(race_laps)
    with np.errstate(all="ignore"):
        field_lap = np.nanmedian(np.where(pit, np.nan, lt), axis=0)
    rate, n = float("nan"), 0
    if overtake_delta is None:
        overtake_delta, rate, n = calibrate_overtaking(race_laps, drivers, lt, cum, pit, neutral)
    return RaceTraffic(drivers, cum, lt, field_lap, pit, set(neutral), float(overtake_delta), rate, n)


def simulate_traffic(tr: RaceTraffic, driver: str, clean_laps: np.ndarray, pit_add: np.ndarray,
                     actual_pit_add: np.ndarray | None = None, keep_cum: bool = False) -> TrafficResult:
    """Coloca al piloto entre los rivales reales y mide el tiempo que pierde en tráfico.

    ``clean_laps[k]`` es el tiempo simulado de la vuelta k+1 sin parada y ``pit_add[k]``
    lo que suma la parada si entra a boxes al final de esa vuelta (0 si no para).
    La vuelta 1 (salida) es la real del piloto, igual para todas las estrategias.
    ``actual_pit_add`` es lo mismo para la estrategia real: bajo SC/VSC se parte de la
    vuelta real y solo se corrige la diferencia de paradas entre ambas estrategias.
    """
    me = tr.index(driver)
    n = len(clean_laps)
    if actual_pit_add is None:
        actual_pit_add = np.zeros(n)
    # Listas de Python por vuelta: con ~20 coches es más rápido que operar con arrays de numpy
    others, cum_by_lap, lt_by_lap = tr.others_by_lap(me)
    clean_l, pit_l, act_l = clean_laps.tolist(), pit_add.tolist(), actual_pit_add.tolist()
    my_lt, field_lap = tr.lap_time[me].tolist(), tr.field_lap.tolist()
    delta = tr.overtake_delta
    V = float(tr.cum[me, 1])
    path = [0.0, V]
    loss, held = 0.0, 0
    lost_by_lap = np.zeros(n)
    rejoins: list[tuple[int, list[str], float]] = []
    for L in range(2, n + 1):
        if L in tr.neutral:
            # Bajo SC/VSC todos van en fila: vuelta real del piloto, corregida por la diferencia
            # de paradas con su estrategia real, y sin tráfico
            real = my_lt[L]
            base = field_lap[L] if real != real else real - act_l[L - 1]      # real != real: NaN
            V += base + pit_l[L - 1]
            path.append(V)
            continue
        own = clean_l[L - 1] + pit_l[L - 1]
        cand = V + own
        prev_o, now_o, lt_o = cum_by_lap[L - 1], cum_by_lap[L], lt_by_lap[L]
        if pit_l[L - 1] > 0:
            # Vuelta de entrada a boxes: va por el pit lane, no hay pelea en pista
            V = cand
            path.append(V)
            if L < n:
                near = sorted((V - c, i) for i, c in enumerate(now_o) if c == c and 0 < V - c < 2 * FOLLOW_GAP)
                if near:
                    rejoins.append((L, [tr.drivers[others[i]] for _, i in near], float(near[0][0])))
            continue
        # Coches que tenía delante y a los que alcanzaría esta vuelta, del más cercano al más lejano
        ahead = sorted(((p, i) for i, p in enumerate(prev_o)
                        if p == p and now_o[i] == now_o[i] and p < V and now_o[i] + MIN_GAP > cand), reverse=True)
        for _, i in ahead:
            if lt_o[i] - own <= delta:                    # no tiene ritmo para adelantarle
                cand = max(cand, now_o[i] + MIN_GAP)
                break
        lost = cand - (V + own)
        if lost > 1e-9:
            loss += lost
            held += 1
            lost_by_lap[L - 1] = lost
        V = cand
        path.append(V)
    return TrafficResult(loss, held, rejoins, np.array(path) if keep_cum else None, lost_by_lap)
