"""Limpieza de vueltas y generación de variables.

Marca qué vueltas son representativas del ritmo (``IsClean``) para ajustar el
modelo. Se excluyen:

* la vuelta 1 (salida),
* vueltas de entrada y salida de boxes,
* vueltas con Safety Car, VSC o bandera roja,
* vueltas sin tiempo, borradas o con compuesto de lluvia,
* valores atípicos (más de un 5 % por encima de la mediana del piloto).
"""
from __future__ import annotations

import pandas as pd

from strategy_audit.config import DRY_COMPOUNDS, WET_COMPOUNDS

# Códigos de TrackStatus de FastF1: 1 verde, 2 amarilla, 4 SC, 5 roja, 6 VSC, 7 fin de VSC
NEUTRALISED_CODES = set("4567")
OUTLIER_FACTOR = 1.05
WET_SHARE_LIMIT = 0.05


def is_neutralised(track_status) -> bool:
    """True si durante la vuelta hubo SC, VSC o bandera roja."""
    if pd.isna(track_status):
        return False
    return bool(set(str(track_status)) & NEUTRALISED_CODES)


def dry_rounds(laps: pd.DataFrame) -> list[int]:
    """Carreras en seco: menos de un 5 % de vueltas con intermedios o lluvia."""
    share = laps.assign(wet=laps["Compound"].isin(WET_COMPOUNDS)).groupby("Round")["wet"].mean()
    return sorted(share[share < WET_SHARE_LIMIT].index.astype(int))


def prepare_laps(laps: pd.DataFrame, races: pd.DataFrame) -> pd.DataFrame:
    """Añade variables y la marca ``IsClean`` a la tabla de vueltas en bruto."""
    df = laps.merge(races[["Round", "TotalLaps"]], on="Round", how="left").copy()
    df = df.sort_values(["Round", "Driver", "LapNumber"]).reset_index(drop=True)

    df["LapNumber"] = df["LapNumber"].astype(int)
    df["LapsRemaining"] = df["TotalLaps"] - df["LapNumber"]
    df["IsPitIn"] = df["PitInTime"].notna()
    df["IsPitOut"] = df["PitOutTime"].notna()
    df["Neutralised"] = df["TrackStatus"].map(is_neutralised)
    deleted = df["Deleted"].fillna(False).astype(bool) if "Deleted" in df else False

    candidate = (
        (df["LapNumber"] > 1)
        & ~df["IsPitIn"]
        & ~df["IsPitOut"]
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
