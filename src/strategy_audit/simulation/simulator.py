"""Simulador de estrategias de carrera.

Una estrategia es una lista de stints ``[(compuesto, vueltas), ...]``. El tiempo
de cada vuelta se calcula con el modelo de ritmo de la carrera; cada parada suma
la pérdida en boxes (reducida si se para con SC/VSC).

Supuestos (documentados como limitaciones):
* No hay interacción entre coches (tráfico, adelantamientos, aire sucio).
* El primer stint usa la edad real del neumático de salida; los siguientes,
  neumático nuevo.
* No se extrapola más allá de la longitud de stint observada en la carrera (+10 %).
* Degradación negativa estimada (evolución de pista) se trunca a 0.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import permutations, product

import numpy as np

from strategy_audit.models.pace_model import RaceModel

MIN_STINT = 5
STINT_MARGIN = 1.10


@dataclass
class Strategy:
    stints: list[tuple[str, int]]          # (compuesto, vueltas)
    cost: float = float("nan")             # parte del tiempo que depende de la estrategia

    @property
    def stops(self) -> int:
        return len(self.stints) - 1

    def stop_laps(self) -> list[int]:
        return list(np.cumsum([n for _, n in self.stints])[:-1].astype(int))

    def label(self) -> str:
        parts = []
        lap = 0
        for i, (c, n) in enumerate(self.stints):
            lap += n
            parts.append(c[0] + (f" ({lap})" if i < len(self.stints) - 1 else ""))
        return " → ".join(parts)


def _deg(model: RaceModel, c: str) -> float:
    return max(model.compound_deg[c], 0.0)


def stint_cost(model: RaceModel, compound: str, n: int, start_age: int) -> float:
    """Suma de (offset + degradación) en un stint de ``n`` vueltas (forma cerrada)."""
    return n * model.compound_offset[compound] + _deg(model, compound) * (n * start_age + n * (n - 1) / 2)


def max_stint(model: RaceModel, compound: str) -> int:
    return int(math.ceil(model.max_stint.get(compound, 0) * STINT_MARGIN))


def pit_loss_by_lap(total_laps: int, pit_loss: float, neutralised: set[int], sc_factor: float = 0.5) -> np.ndarray:
    """Pérdida por parar al final de cada vuelta (índice = vuelta de entrada)."""
    loss = np.full(total_laps + 2, pit_loss)
    for lap in neutralised:
        for l in (lap - 1, lap):   # parar en la vuelta neutralizada o justo antes
            if 0 <= l < len(loss):
                loss[l] = pit_loss * sc_factor
    return loss


def strategy_cost(model: RaceModel, stints: list[tuple[str, int]], first_age: int,
                  pit_losses: np.ndarray) -> float:
    cost, lap = 0.0, 0
    for i, (c, n) in enumerate(stints):
        cost += stint_cost(model, c, n, first_age if i == 0 else 1)
        lap += n
        if i < len(stints) - 1:
            cost += pit_losses[lap]
    return cost


def is_feasible(model: RaceModel, stints: list[tuple[str, int]], first_age: int) -> bool:
    if len({c for c, _ in stints}) < 2:          # reglamento: dos compuestos de seco
        return False
    for i, (c, n) in enumerate(stints):
        age0 = first_age if i == 0 else 1
        if n < MIN_STINT or c not in model.compound_deg or age0 + n - 1 > max_stint(model, c):
            return False
    return True


def _stint_cost_array(model: RaceModel, compound: str, total_laps: int, start_age: int) -> np.ndarray:
    """Coste de un stint de n vueltas para n = 0..N (inf si no es factible)."""
    n = np.arange(total_laps + 1, dtype=float)
    cost = n * model.compound_offset[compound] + _deg(model, compound) * (n * start_age + n * (n - 1) / 2)
    feasible = (n >= MIN_STINT) & (start_age + n - 1 <= max_stint(model, compound))
    return np.where(feasible, cost, np.inf)


def enumerate_strategies(model: RaceModel, total_laps: int, first_age: int,
                         pit_losses: np.ndarray, max_stops: int = 2) -> list[Strategy]:
    """Mejor estrategia para cada secuencia de compuestos (1 y 2 paradas), ordenadas por coste.

    Vectorizado con numpy: para cada secuencia se evalúan a la vez todas las
    combinaciones de vueltas de parada.
    """
    N = total_laps
    compounds = sorted(model.compound_deg)
    first = {c: _stint_cost_array(model, c, N, first_age) for c in compounds}
    fresh = {c: _stint_cost_array(model, c, N, 1) for c in compounds}
    pl = pit_losses[: N + 1]
    out: list[Strategy] = []

    if max_stops >= 1:
        s = np.arange(N + 1)
        for c1, c2 in permutations(compounds, 2):
            total = first[c1][s] + fresh[c2][N - s] + pl[s]
            k = int(np.argmin(total))
            if np.isfinite(total[k]):
                out.append(Strategy([(c1, k), (c2, N - k)], float(total[k])))

    if max_stops >= 2:
        s1 = np.arange(N + 1)[:, None]
        s2 = np.arange(N + 1)[None, :]
        valid = s2 > s1
        d = np.clip(s2 - s1, 0, N)
        for c1, c2, c3 in product(compounds, repeat=3):
            if len({c1, c2, c3}) < 2:
                continue
            total = first[c1][s1] + fresh[c2][d] + fresh[c3][N - s2] + pl[s1] + pl[s2]
            total = np.where(valid, total, np.inf)
            i, j = np.unravel_index(np.argmin(total), total.shape)
            if np.isfinite(total[i, j]):
                out.append(Strategy([(c1, int(i)), (c2, int(j - i)), (c3, int(N - j))], float(total[i, j])))

    out.sort(key=lambda st: st.cost)
    return out


def best_strategy(model: RaceModel, total_laps: int, first_age: int, pit_losses: np.ndarray) -> Strategy | None:
    strategies = enumerate_strategies(model, total_laps, first_age, pit_losses)
    return strategies[0] if strategies else None


def lap_times(model: RaceModel, driver: str, stints: list[tuple[str, int]], first_age: int,
              pit_losses: np.ndarray) -> np.ndarray:
    """Tiempo simulado de cada vuelta (la parada se suma a la vuelta de entrada)."""
    times = []
    lap = 0
    base = model.driver_base[driver]
    for i, (c, n) in enumerate(stints):
        age0 = first_age if i == 0 else 1
        for k in range(n):
            lap += 1
            t = base + model.compound_offset[c] + _deg(model, c) * (age0 + k) + model.fuel * lap
            if k == n - 1 and i < len(stints) - 1:
                t += pit_losses[lap]
            times.append(t)
    return np.array(times)
