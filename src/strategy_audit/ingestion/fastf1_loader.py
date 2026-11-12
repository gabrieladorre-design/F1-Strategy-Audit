"""Descarga de carreras con FastF1 y guardado en Parquet (data/raw).

Carga incremental: solo descarga las carreras que todavía no están en los
ficheros de salida, así que se puede volver a ejecutar tras cada Gran Premio.
"""
from __future__ import annotations

import logging

import pandas as pd

from strategy_audit.config import CACHE_DIR, RAW_DIR

log = logging.getLogger(__name__)

LAP_COLUMNS = [
    "Driver", "DriverNumber", "Team", "LapNumber", "LapTime", "Stint",
    "Compound", "TyreLife", "FreshTyre", "PitInTime", "PitOutTime",
    "TrackStatus", "Position", "Time", "LapStartTime", "Deleted", "IsAccurate",
]
RESULT_COLUMNS = [
    "Abbreviation", "DriverNumber", "FullName", "TeamName", "TeamColor",
    "GridPosition", "Position", "ClassifiedPosition", "Status", "Points", "Time",
]


def _td_to_seconds(df: pd.DataFrame) -> pd.DataFrame:
    """Convierte las columnas timedelta a segundos (float) para guardarlas en Parquet."""
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_timedelta64_dtype(df[col]):
            df[col] = df[col].dt.total_seconds()
    return df


def _paths(season: int):
    return (
        RAW_DIR / f"laps_{season}.parquet",
        RAW_DIR / f"results_{season}.parquet",
        RAW_DIR / f"races_{season}.parquet",
    )


def load_race(season: int, round_number: int):
    """Descarga una carrera y devuelve (vueltas, resultados, info de la carrera)."""
    import fastf1

    session = fastf1.get_session(season, round_number, "R")
    session.load(laps=True, telemetry=False, weather=True, messages=False)

    laps = _td_to_seconds(session.laps[LAP_COLUMNS].copy())
    laps.insert(0, "Round", round_number)

    results = _td_to_seconds(session.results[RESULT_COLUMNS].copy())
    results.insert(0, "Round", round_number)

    weather = session.weather_data
    event = session.event
    race = {
        "Round": round_number,
        "EventName": event["EventName"],
        "Country": event["Country"],
        "Location": event["Location"],
        "Date": pd.Timestamp(event["EventDate"]).date().isoformat(),
        "TotalLaps": int(laps["LapNumber"].max()),
        "TrackTemp": float(weather["TrackTemp"].median()) if len(weather) else None,
        "AirTemp": float(weather["AirTemp"].median()) if len(weather) else None,
        "Rainfall": bool(weather["Rainfall"].any()) if len(weather) else False,
    }
    return laps, results, race


def download_season(season: int, force: bool = False) -> None:
    """Descarga todas las carreras ya disputadas de una temporada."""
    import fastf1

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(CACHE_DIR))

    laps_path, results_path, races_path = _paths(season)
    if laps_path.exists() and not force:
        laps_all = pd.read_parquet(laps_path)
        results_all = pd.read_parquet(results_path)
        races_all = pd.read_parquet(races_path)
    else:
        laps_all, results_all, races_all = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    done = set(races_all["Round"]) if len(races_all) else set()

    schedule = fastf1.get_event_schedule(season, include_testing=False)
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    for _, ev in schedule.iterrows():
        rnd = int(ev["RoundNumber"])
        if rnd in done or pd.Timestamp(ev["EventDate"]) > now:
            continue
        log.info("Descargando %s R%02d %s", season, rnd, ev["EventName"])
        try:
            laps, results, race = load_race(season, rnd)
        except Exception as exc:  # una carrera rota no debe parar toda la descarga
            log.warning("No se pudo cargar R%02d: %s", rnd, exc)
            continue
        laps_all = pd.concat([laps_all, laps], ignore_index=True)
        results_all = pd.concat([results_all, results], ignore_index=True)
        races_all = pd.concat([races_all, pd.DataFrame([race])], ignore_index=True)
        # Se guarda tras cada carrera para no perder progreso si algo falla
        laps_all.to_parquet(laps_path, index=False)
        results_all.to_parquet(results_path, index=False)
        races_all.sort_values("Round").to_parquet(races_path, index=False)

    log.info("Temporada %s: %d carreras, %d vueltas", season, len(races_all), len(laps_all))
