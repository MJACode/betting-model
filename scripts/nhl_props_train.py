"""Fit one of the models in models/nhl_props.py and (with --register) make it the live artifact.

The evidence is scripts/nhl_prop_backtest.py. This fits the model on every
regular-season row from 2019-20 through the last COMPLETED season, writes the
.pkl to models/saved/, and with --register stores the bytes in Supabase and
points `model_registry` at them -- the bytes first, so the active row never
names a file nothing can produce.

    python -m scripts.nhl_props_train --model nhl_prop_saves --through 2026            # fit, save, do not register
    python -m scripts.nhl_props_train --model nhl_prop_saves --through 2026 --register
    python -m scripts.nhl_props_train --model nhl_prop_saves --through 2026 --register --from-file models/saved/x.pkl

`--from-file` registers an artifact that is already on disk instead of fitting
again: the file that was replayed and committed is the one that should go live.
`--cache DIR` fits from a local copy of the logs (the same folder
scripts/nhl_prop_backtest.py --cache reads) instead of reading them again.
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, ".")

from loguru import logger  # noqa: E402

import models.nhl_props as np_  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.trainer import MODELS_DIR, _store_artifact  # noqa: E402

# The walk-forward record each artifact goes live on (scripts/nhl_prop_backtest.py,
# 2026-10-01): three priced seasons, the best price among the bettable books,
# unders only, the model's own probability, the EV floor in
# config.MODEL_OWN_EV_FLOOR, the -200 price floor.
BACKTEST = {
    "nhl_prop_saves": {"bets": 1755, "units": 136.5, "roi": 0.0777, "seasons": [2024, 2025, 2026]},
    "nhl_prop_shots_on_goal": {"bets": 4707, "units": 270.3, "roi": 0.0574, "seasons": [2024, 2025, 2026]},
    "nhl_prop_assists": {"bets": 1063, "units": 115.8, "roi": 0.1090, "seasons": [2024, 2025, 2026]},
}


def _fit(spec: np_.Spec, through: int, cache: str | None, conn) -> dict:
    if cache:
        from scripts.nhl_prop_backtest import load
        data = load(cache)
        players, teams = data[spec.kind], data["teams"]
    else:
        players, teams = np_.load_players(conn, spec.kind), np_.load_teams(conn)
    return np_.fit(spec, np_.build_frame(spec, players, teams), through)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True, choices=[s.model_id for s in np_.LIVE])
    ap.add_argument("--through", type=int, required=True,
                    help="last season to train on (ENDING year, e.g. 2026 = 2025-26)")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--from-file", default=None,
                    help="register this existing artifact instead of fitting a new one")
    ap.add_argument("--cache", default=None, help="fit from this folder of pickles, not the database")
    a = ap.parse_args()
    spec = np_.SPECS[a.model]
    record = BACKTEST[spec.model_id]

    conn = get_connection()
    try:
        seasons = list(range(np_.FIRST_TRAIN_SEASON, a.through + 1))
        if a.from_file:
            path = Path(a.from_file).resolve()
            with open(path, "rb") as fh:
                artifact = pickle.load(fh)
            if (artifact.get("model_id") != spec.model_id or artifact.get("train_seasons") != seasons
                    or artifact.get("feature_cols") != list(spec.features)):
                raise SystemExit(f"{path.name} is not a {spec.model_id} artifact trained through {a.through} "
                                 f"on this Spec's inputs")
            version = artifact["version"]
        else:
            fitted = _fit(spec, a.through, a.cache, conn)
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            artifact = {
                "model": fitted["model"], "dispersion": fitted["dispersion"],
                "model_id": spec.model_id, "version": version, "sport": "NHL",
                "market": spec.market, "feature_cols": list(spec.features), "sides": list(spec.sides),
                "train_seasons": seasons, "trained_at": datetime.now().isoformat(),
                "n_train": fitted["n_train"], "params": dict(np_.PARAMS), "backtest": dict(record),
            }
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            path = MODELS_DIR / f"{spec.model_id}_{version}.pkl"
            with open(path, "wb") as fh:
                pickle.dump(artifact, fh)
            logger.success(f"{spec.model_id} {version}: fit on {fitted['n_train']:,} rows "
                           f"({seasons[0]}-{seasons[-1]}), excess variance {fitted['dispersion']:.4f}")
        rel = Path(path).relative_to(MODELS_DIR.parent.parent).as_posix()
        logger.info(f"artifact: {rel}")
        if not a.register:
            logger.warning("not registered: the live artifact, if any, is untouched (--register to switch)")
            return
        _store_artifact(conn, spec.model_id, version, path)        # bytes before the row that names them
        conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_id = %s AND is_active = 1",
                     (spec.model_id,))
        conn.execute("""
            INSERT INTO model_registry (model_id, version, trained_on, train_seasons, holdout_season,
                                        holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                                        is_active, model_path, notes)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, NULL, 1, %s, %s)
        """, (spec.model_id, version, date.today().isoformat(), json.dumps(seasons), a.through,
              record["roi"], record["bets"], rel,
              f"Poisson XGB, fixed params | walk-forward 2023-24..2025-26 at the best bettable price, unders, "
              f"own probability: {record['bets']:,} bets {record['roi'] * 100:+.1f}% (scripts/nhl_prop_backtest.py)"))
        conn.commit()
        logger.success(f"registered and active: {spec.model_id} {version}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
