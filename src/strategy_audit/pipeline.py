"""Pipeline completo: datos en bruto → modelo → auditoría → tablas para la app.

Lee ``data/raw`` y escribe en ``data/processed`` las tablas que consume el
dashboard. No necesita conexión a Internet.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from strategy_audit.config import PROCESSED_DIR, RAW_DIR
from strategy_audit.models.pace_model import fit_race, models_to_frames
from strategy_audit.models.pit_loss import estimate_pit_loss
from strategy_audit.processing.clean import (
    actual_stints,
    dry_rounds,
    neutralised_laps,
    prepare_laps,
    rounds_with_tyre_data,
)
from strategy_audit.simulation.audit import audit_race, validate_simulator

log = logging.getLogger(__name__)

LAP_EXPORT_COLS = ["Round", "Driver", "Team", "LapNumber", "LapTime", "Compound", "TyreLife",
                   "Stint", "IsClean", "IsPitIn", "Neutralised", "Position", "Predicted"]


def run(season: int, raw_dir: Path = RAW_DIR, out_dir: Path = PROCESSED_DIR) -> dict:
    laps_raw = pd.read_parquet(raw_dir / f"laps_{season}.parquet")
    results = pd.read_parquet(raw_dir / f"results_{season}.parquet")
    races = pd.read_parquet(raw_dir / f"races_{season}.parquet")

    tyre_ok = set(rounds_with_tyre_data(laps_raw))
    laps = prepare_laps(laps_raw, races)
    stints = actual_stints(laps)
    neutral = neutralised_laps(laps)
    all_dry = dry_rounds(laps)
    for rnd in sorted(set(all_dry) - tyre_ok):
        log.warning("R%02d descartada: faltan datos de neumáticos en FastF1", rnd)
    dry = [r for r in all_dry if r in tyre_ok]
    log.info("%d carreras, %d en seco y con datos completos", len(races), len(dry))

    models, audits, bests, validations, race_rows = [], [], [], [], []
    laps["Predicted"] = float("nan")
    for rnd in dry:
        try:
            model = fit_race(laps, rnd)
        except ValueError as exc:
            log.warning("%s", exc)
            continue
        models.append(model)
        mask = (laps["Round"] == rnd) & laps["Driver"].isin(model.driver_base) & laps["Compound"].isin(model.compound_deg)
        laps.loc[mask, "Predicted"] = model.predict(laps[mask])

        pit_loss = estimate_pit_loss(laps, model)
        n_laps = set(neutral.loc[(neutral["Round"] == rnd) & neutral["Neutralised"], "LapNumber"].astype(int))
        audit, best = audit_race(model, laps, stints, results, pit_loss, n_laps)
        audits.append(audit)
        bests.append(best)

        val_mae = float("nan")
        if not n_laps:
            val = validate_simulator(model, laps, stints, pit_loss)
            validations.append(val)
            if len(val):
                val_mae = float(val["Error"].abs().mean())
        race_rows.append({"Round": rnd, "PitLoss": pit_loss, "NeutralisedLaps": len(n_laps),
                          "SimValidationMAE": val_mae})
        log.info("R%02d MAE_cv=%.3fs pit=%.1fs auditados=%d", rnd, model.mae_cv, pit_loss, len(audit))

    drivers_df, compounds_df, summary_df = models_to_frames(models)
    race_info = races.assign(IsDry=races["Round"].isin(all_dry), TyreDataOK=races["Round"].isin(tyre_ok))
    race_info = race_info.merge(pd.DataFrame(race_rows), on="Round", how="left")
    race_info = race_info.merge(summary_df, on="Round", how="left")

    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "races": race_info,
        "laps": laps[LAP_EXPORT_COLS],
        "stints": stints,
        "neutralised": neutral[neutral["Neutralised"]],
        "results": results,
        "model_drivers": drivers_df,
        "model_compounds": compounds_df,
        "audit": pd.concat(audits, ignore_index=True) if audits else pd.DataFrame(),
        "best_stints": pd.concat(bests, ignore_index=True) if bests else pd.DataFrame(),
        "validation": pd.concat(validations, ignore_index=True) if validations else pd.DataFrame(),
    }
    for name, df in tables.items():
        df.to_parquet(out_dir / f"{name}_{season}.parquet", index=False)

    metrics = {
        "season": season,
        "races": int(len(races)),
        "dry_races_modelled": len(models),
        "pace_model_mae_cv_s": float(summary_df["MAE_cv"].mean()) if len(summary_df) else None,
        "simulator_mae_s": float(tables["validation"]["Error"].abs().mean()) if len(tables["validation"]) else None,
        "audited_driver_races": int(len(tables["audit"])),
    }
    (out_dir / f"metrics_{season}.json").write_text(json.dumps(metrics, indent=2))
    log.info("Métricas: %s", metrics)
    return metrics
