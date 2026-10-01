"""Fit nhl_prop_blocked_shots and (with --register) make it the live artifact.

The model is models/nhl_prop_blocked_shots.py; its evidence is
scripts/nhl_prop_blocked_shots_backtest.py. This fits it on every regular-season
skater-game from 2019-20 through the last COMPLETED season, writes the .pkl to
models/saved/, and with --register stores the bytes in Supabase and points
`model_registry` at them -- the bytes first, so the active row never names a
file nothing can produce.

    python -m scripts.nhl_prop_blocked_shots_train --through 2026            # fit, save, do not register
    python -m scripts.nhl_prop_blocked_shots_train --through 2026 --register
    python -m scripts.nhl_prop_blocked_shots_train --through 2026 --register --from-file models/saved/x.pkl

`--from-file` registers an artifact that is already on disk instead of fitting
again: the fit reads the whole skater log, and the file that was replayed and
committed is the one that should go live.
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

import models.nhl_prop_blocked_shots as bs  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.trainer import MODELS_DIR, _store_artifact  # noqa: E402

# The walk-forward record this artifact goes live on
# (scripts/nhl_prop_blocked_shots_backtest.py, 2026-10-01): three priced
# seasons, DraftKings, the model's own probability, EV >= 0.10, -200 floor.
BACKTEST = {"bets": 2054, "units": 126.8, "roi": 0.0617, "seasons": [2024, 2025, 2026]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--through", type=int, required=True,
                    help="last season to train on (ENDING year, e.g. 2026 = 2025-26)")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--from-file", default=None,
                    help="register this existing artifact instead of fitting a new one")
    a = ap.parse_args()

    conn = get_connection()
    try:
        seasons = list(range(bs.FIRST_TRAIN_SEASON, a.through + 1))
        if a.from_file:
            path = Path(a.from_file).resolve()
            with open(path, "rb") as fh:
                artifact = pickle.load(fh)
            if artifact.get("model_id") != bs.MODEL_ID or artifact.get("train_seasons") != seasons:
                raise SystemExit(f"{path.name} is not a {bs.MODEL_ID} artifact trained through {a.through}")
            version = artifact["version"]
        else:
            frame = bs.build_frame(bs.load_skaters(conn), bs.load_teams(conn))
            model, n_train = bs.fit(frame, a.through)
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            artifact = {
                "model": model, "model_id": bs.MODEL_ID, "version": version, "sport": "NHL",
                "market": bs.MARKET, "feature_cols": list(bs.FEATURES), "train_seasons": seasons,
                "trained_at": datetime.now().isoformat(), "n_train": n_train,
                "params": dict(bs.PARAMS), "backtest": dict(BACKTEST),
            }
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            path = MODELS_DIR / f"{bs.MODEL_ID}_{version}.pkl"
            with open(path, "wb") as fh:
                pickle.dump(artifact, fh)
            logger.success(f"{bs.MODEL_ID} {version}: fit on {n_train:,} skater-games "
                           f"({seasons[0]}-{seasons[-1]})")
        rel = Path(path).relative_to(MODELS_DIR.parent.parent).as_posix()
        logger.info(f"artifact: {rel}")
        if not a.register:
            logger.warning("not registered: the live artifact, if any, is untouched (--register to switch)")
            return
        _store_artifact(conn, bs.MODEL_ID, version, path)        # bytes before the row that names them
        conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_id = %s AND is_active = 1",
                     (bs.MODEL_ID,))
        conn.execute("""
            INSERT INTO model_registry (model_id, version, trained_on, train_seasons, holdout_season,
                                        holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                                        is_active, model_path, notes)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, NULL, 1, %s, %s)
        """, (bs.MODEL_ID, version, date.today().isoformat(), json.dumps(seasons), a.through,
              BACKTEST["roi"], BACKTEST["bets"], rel,
              "Poisson XGB, fixed params | walk-forward 2023-24..2025-26 at DraftKings, "
              "EV>=0.10: 2,054 bets +6.2% (scripts/nhl_prop_blocked_shots_backtest.py)"))
        conn.commit()
        logger.success(f"registered and active: {bs.MODEL_ID} {version}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
