"""Limpieza de vueltas y generación de variables.

Marca qué vueltas son representativas del ritmo (``IsClean``) para ajustar el
modelo. Se excluyen:

* la vuelta 1 (salida),
* vueltas de entrada y salida de boxes,
* vueltas con Safety Car, VSC o bandera roja,
* vueltas sin tiempo, borradas o con compuesto de lluvia,
* valores atípicos (más de un 5 % por encima de la mediana del piloto),

Las vueltas con otro coche a menos de 1,5 s delante se marcan con ``InTraffic``: el
modelo estima aparte lo que cuestan, de modo que el ritmo de cada piloto es el de
aire limpio y el simulador añade el tráfico solo cuando la estrategia lo provoca.

Además se descartan carreras enteras con lluvia o con datos de neumáticos incompletos.
"""
from __future__ import annotations

import pandas as pd

from strategy_audit.config import DRY_COMPOUNDS, WET_COMPOUNDS

# Códigos de TrackStatus de FastF1: 1 verde, 2 amarilla, 4 SC, 5 roja, 6 VSC, 7 fin de VSC
NEUTRALISED_CODES = set("4567")
OUTLIER_FACTOR = 1.05
WET_SHARE_LIMIT = 0.05
MISSING_TYRE_LIMIT = 0.05
FREE_AIR_GAP = 1.5   # s: con un coche a menos de esto delante, la vuelta no mide el ritmo propio   # máximo de vueltas sin compuesto conocido para auditar una carrera


def is_neutralised(track_status) -> bool:
    """True si durante la vuelta hubo SC, VSC o bandera roja."""
    if pd.isna(track_status):
        return False
    return bool(set(str(track_status)) & NEUTRALISED_CODES)


def dry_rounds(laps: pd.DataFrame) -> list[int]:
    """Carreras en seco: menos de un 5 % de vueltas con intermedios o lluvia."""
    share = laps.assign(wet=laps["Compound"].isin(WET_COMPOUNDS)).groupby("Round")["wet"].mean()
    return sorted(share[share < WET_SHARE_LIMIT].index.astype(int))


def rounds_with_tyre_data(laps: pd.DataFrame, limit: float = MISSING_TYRE_LIMIT) -> list[int]:
    """Carreras en las que FastF1 trae el compuesto de casi todas las vueltas.

    En Miami 2025 faltan los neumáticos de las primeras ~24 vueltas de casi toda la
    parrilla y los stints posteriores llegan desalineados: con esos datos el modelo
    y la auditoría no son fiables, así que la carrera se descarta entera.
    """
    known = laps["Compound"].isin(DRY_COMPOUNDS + WET_COMPOUNDS)
    missing = (~known).groupby(laps["Round"]).mean()
    return sorted(missing[missing <= limit].index.astype(int))


def prepare_laps(laps: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """Añade variables y la marca ``IsClean`` a la tabla de vueltas en bruto."""
    df = laps.merge(races[["Round", "TotalLaps"]], on="Round", how="left").copy()
    df = df.sort_values(["Round", "Driver", "LapNumber"]).reset_index(drop=True)

    df["LapNumber"] = df["LapNumber"].astype(int)
    # Compuestos desconocidos ('nan', None…): huecos a mitad de stint se rellenan con el
    # anterior; si se desconoce desde el inicio, queda como UNKNOWN y ese piloto no se audita
    known = df["Compound"].where(df["Compound"].isin(DRY_COMPOUNDS + WET_COMPOUNDS))
    df["Compound"] = known.groupby([df["Round"], df["Driver"]]).ffill().fillna("UNKNOWN")
    df["LapsRemaining"] = df["TotalLaps"] - df["LapNumber"]
    raw_pit_in = df["PitInTime"].notna()
    raw_pit_out = df["PitOutTime"].notna()
    df["Neutralised"] = df["TrackStatus"].map(is_neutralised)
    deleted = df["Deleted"].astype("boolean").fillna(False).astype(bool) if "Deleted" in df else False

    # Stints reconstruidos: FastF1 a veces marca «paradas» falsas (p. ej. vueltas tras
    # la bandera a cuadros bajo SC). Un stint nuevo solo empieza si cambia el compuesto
    # o la edad del neumático se reinicia.
    g = df.groupby(["Round", "Driver"])
    new_stint = (
        (df["Compound"] != g["Compound"].shift())
        | (df["TyreLife"] < g["TyreLife"].shift())
    )
    df["Stint"] = new_stint.astype(int).groupby([df["Round"], df["Driver"]]).cumsum()
    next_new = new_stint.groupby([df["Round"], df["Driver"]]).shift(-1).astype("boolean").fillna(False).astype(bool)
    df["IsPitIn"] = raw_pit_in & next_new
    df["IsPitOut"] = raw_pit_out & new_stint & (df["LapNumber"] > 1)

    df["GapAhead"] = _gap_ahead(df)
    # En tráfico durante la vuelta L si al empezarla (final de L-1) tenía un coche a ≤ 1,5 s
    df["InTraffic"] = (df.groupby(["Round", "Driver"])["GapAhead"].shift() <= FREE_AIR_GAP).astype(float)

    candidate = (
        (df["LapNumber"] > 1)
        & ~raw_pit_in
        & ~raw_pit_out
        & ~df["Neutralised"]
        & df["LapTime"].notna()
        & df["TyreLife"].notna()
        & df["Compound"].isin(DRY_COMPOUNDS)
        & ~deleted
    )
    median = df[candidate].groupby(["Round", "Driver"])["LapTime"].transform("median")
    df["IsClean"] = False
    df.loc[candidate, "IsClean"] = df.loc[candidate, "LapTime"] <= OUTLIER_FACTOR * median
    return df


def _gap_ahead(df: pd.DataFrame) -> pd.Series:
    """Segundos con el coche de delante (en la misma vuelta) al cruzar la meta en cada vuelta."""
    t = df["LapTime"].fillna(df.groupby(["Round", "Driver"])["LapTime"].transform("median"))
    cum = t.groupby([df["Round"], df["Driver"]]).cumsum()
    order = pd.DataFrame({"Round": df["Round"], "Lap": df["LapNumber"], "Cum": cum}).sort_values(["Round", "Lap", "Cum"])
    gap = order.groupby(["Round", "Lap"])["Cum"].diff()
    return gap.reindex(df.index)


def neutralised_laps(laps: pd.DataFrame) -> pd.DataFrame:
    """Por carrera y vuelta, indica si la vuelta estuvo neutralizada (SC/VSC/roja).

    Se usa la mayoría de los pilotos en pista para evitar ruido de un solo coche.
    """
    flags = laps.assign(N=laps["TrackStatus"].map(is_neutralised))
    out = flags.groupby(["Round", "LapNumber"])["N"].mean().gt(0.5).rename("Neutralised")
    return out.reset_index()


def actual_stints(laps: pd.DataFrame) -> pd.DataFrame:
    """Stints reales de cada piloto: compuesto, vuelta inicial/final y edad inicial."""
    g = laps.dropna(subset=["Stint"]).groupby(["Round", "Driver", "Stint"])
    stints = g.agg(
        Compound=("Compound", "first"),
        StartLap=("LapNumber", "min"),
        EndLap=("LapNumber", "max"),
        StartAge=("TyreLife", "min"),
    ).reset_index()
    stints["Laps"] = stints["EndLap"] - stints["StartLap"] + 1
    stints["StartAge"] = stints["StartAge"].fillna(1).astype(int)
    return stints
