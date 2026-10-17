"""Fit the anchored nhl_moneyline and (with --register) make it the live artifact.

The model is models/nhl_moneyline_anchored.py; its evidence is
scripts/nhl_moneyline_anchored_backtest.py (docs/nhl_moneyline_rebuild.md). This
fits it on every priced game from 2020-21 through the last COMPLETED season,
writes the .pkl to models/saved/, and with --register stores the bytes in
Supabase and points `model_registry` at them -- the bytes first, so the active
row never names a file nothing can produce.

ORDER MATTERS. --register switches production: the worker can only score this
artifact once the code that reads `kind = "anchored_logit"` is deployed. Merge,
let the worker redeploy, THEN register.

    python -m scripts.nhl_moneyline_anchored_train --through 2026            # fit, save, do not register
    python -m scripts.nhl_moneyline_anchored_train --through 2026 --register --from-file models/saved/x.pkl
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

import models.nhl_moneyline_anchored as m  # noqa: E402
from data.db import get_connection  # noqa: E402
from models.trainer import MODELS_DIR, _store_artifact  # noqa: E402

# The walk-forward record this artifact goes live on
# (scripts/nhl_moneyline_anchored_backtest.py, 2026-10-13): 2021-22 .. 2025-26,
# best bettable price in DraftKings' first game-day snapshot, the model's own
# probability, EV >= 0.06, the -200 price floor.
BACKTEST = {"bets": 1326, "units": 83.2, "roi": 0.0628, "ev_floor": 0.06,
            "seasons": [2022, 2023, 2024, 2025, 2026]}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--through", type=int, required=True,
                    help="last season to train on (ENDING year, e.g. 2026 = 2025-26)")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--from-file", default=None,
                    help="register this existing artifact instead of fitting a new one")
    a = ap.parse_args()
    seasons = list(range(m.FIRST_PRICED_SEASON, a.through + 1))

    conn = get_connection()
    try:
        if a.from_file:
            path = Path(a.from_file).resolve()
            with open(path, "rb") as fh:
                artifact = pickle.load(fh)
            if artifact.get("model_id") != m.MODEL_ID or artifact.get("kind") != m.KIND \
                    or artifact.get("train_seasons") != seasons:
                raise SystemExit(f"{path.name} is not a {m.MODEL_ID} {m.KIND} artifact trained through {a.through}")
            version = artifact["version"]
        else:
            from scripts.nhl_moneyline_anchored_backtest import module_frame
            df = module_frame()
            train = df[df.season.isin(seasons)]
            model, C = m.fit(train)
            n_train = int(train.dropna(subset=m.FEATURES + ["mkt_logit", "y"]).shape[0])
            version = datetime.now().strftime("%Y%m%d_%H%M%S")
            artifact = {
                "model": model, "kind": m.KIND, "model_id": m.MODEL_ID, "version": version,
                "sport": "NHL", "market": m.MARKET, "feature_cols": list(m.FEATURES),
                "train_seasons": seasons, "trained_at": datetime.now().isoformat(),
                "n_train": n_train, "C": C, "backtest": dict(BACKTEST),
            }
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            path = MODELS_DIR / f"{m.MODEL_ID}_{version}.pkl"
            with open(path, "wb") as fh:
                pickle.dump(artifact, fh)
            logger.success(f"{m.MODEL_ID} {version}: fit on {n_train:,} priced games "
                           f"({seasons[0]}-{seasons[-1]}), C={C}")
        rel = Path(path).relative_to(MODELS_DIR.parent.parent).as_posix()
        logger.info(f"artifact: {rel}")
        if not a.register:
            logger.warning("not registered: the live artifact is untouched (--register to switch)")
            return
        _store_artifact(conn, m.MODEL_ID, version, path)        # bytes before the row that names them
        conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_id = %s AND is_active = 1",
                     (m.MODEL_ID,))
        conn.execute("""
            INSERT INTO model_registry (model_id, version, trained_on, train_seasons, holdout_season,
                                        holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                                        is_active, model_path, notes)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, NULL, 1, %s, %s)
        """, (m.MODEL_ID, version, date.today().isoformat(), json.dumps(seasons), a.through,
              BACKTEST["roi"], BACKTEST["bets"], rel,
              "anchored on DraftKings' game-day price (offset logistic) | walk-forward 2021-22..2025-26, "
              "best price, EV>=0.06, -200 floor: 1,326 bets +6.3% (scripts/nhl_moneyline_anchored_backtest.py)"))
        conn.commit()
        logger.success(f"registered and active: {m.MODEL_ID} {version}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
