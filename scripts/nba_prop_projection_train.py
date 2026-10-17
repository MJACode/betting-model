"""Fit the NBA projection model (models/nba_prop_projection.py) and, with --register, make it live.

The evidence is docs/nba_models_2026.md section 5 (scripts/nba_prop_model_lab.py,
scripts/nba_prop_model_verify.py, scripts/nba_prop_projection_lab.py). This fits
the artifact the live card reads, on the worker's inputs only, the same way each
walk-forward fold was fitted:

  * the minutes model and one per-minute rate model per base stat the card's
    markets sum, on every usable played row from 2018-19 through --through;
  * each market's negative-binomial width, fitted on season --through as
    predicted by the fold that never saw it (trained through --through - 1),
    as each graded season's width was fitted on the season before it;
  * each market's calibration map, fitted on the main-line (claimed, outcome)
    pairs of every graded season (the lab's calib_pairs_main.parquet), as
    2025-26's map was fitted on 2023-24 and 2024-25.

    python -m scripts.nba_prop_projection_train --through 2026 --pairs PATH           # fit, save, check
    python -m scripts.nba_prop_projection_train --through 2026 --pairs PATH --register
    python -m scripts.nba_prop_projection_train --register --from-file models/saved/x.pkl

`--from-file` registers an artifact already on disk: the file that was checked
and committed is the one that goes live. `--check-frame PATH` compares this
script's frame with the worker re-fit's stored frame, input by input, and
`--check-pred PATH` the fold --through predictions with the stored ones.
Reads the research cache (scripts/nba_research_cache.py writes it from
Supabase); no Odds API call.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger  # noqa: E402

import models.nba_prop_projection as pj  # noqa: E402
import models.nba_props as nb  # noqa: E402

# Props on or after this date are the live 2026-27 collection, not the archive
# (scripts/nba_prop_model_lab.LAST_RESEARCH_DATE).
LAST_RESEARCH_DATE = "2026-10-20"

# The graded record the artifact goes live on (docs/nba_models_2026.md section 5):
# the six cells at the best of the eight bettable books, -200 floor, 2023-24..2025-26.
BACKTEST = {"bets": 83360, "roi": 0.0412, "seasons": [2024, 2025, 2026]}


def research_inputs(cache: Path) -> tuple[dict, pd.DataFrame]:
    """The worker's inputs over the bought history, and the research's decision times."""
    raw = nb.load_cache(cache, with_props=True, with_lines=False)
    props = raw["nba_props"]
    decisions = nb.decisions_for(raw, props[props.game_date < LAST_RESEARCH_DATE])
    report = pj.compact_report(pj.collapse_official(raw["nba_injury_report"]), decisions)
    data = pj.worker_data(raw["nba_games"], raw["nba_schedule"], raw["nba_player_game_log"],
                          report, decisions)
    return data, decisions


def fit_fold(fr: pd.DataFrame, through: int) -> dict:
    """The minutes model and the card's rate models, on usable played rows of 2019..`through`."""
    use = nb.usable(fr)
    tr = fr[use & fr.played & fr.season.between(nb.FIRST_TRAIN_SEASON, through)]
    logger.info(f"fold through {through}: {len(tr):,} training rows")
    out = {"minutes": nb.fit_minutes(tr, cols=pj.minutes_cols()), "rates": {}, "n_train": int(len(tr))}
    for s in pj.STATS:
        out["rates"][s] = nb.fit_rate(tr, s, cols=pj.rate_cols(s))
    return out


def widths(fr: pd.DataFrame, fold: dict, season: int) -> tuple[dict, pd.DataFrame]:
    """Each card market's negative-binomial width on `season`, as predicted by `fold` (which never saw it)."""
    te = fr[nb.usable(fr) & (fr.season == season) & fr.played]
    means = pj.predict_means(fold, te)
    out = {}
    for m in pj.MARKETS:
        y = nb.settle_value(nb.BY_MARKET[m], te).values
        mu = means[f"mu_{m}"].values
        ok = np.isfinite(y) & np.isfinite(mu)
        out[m] = nb.fit_alpha(y[ok], mu[ok])
    return out, te[["game_id", "player_id"]].assign(**{c: means[c].values for c in means.columns})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--through", type=int, default=2026, help="last season fitted on (ENDING year)")
    ap.add_argument("--cache", default=str(nb.CACHE))
    ap.add_argument("--pairs", help="the lab's calib_pairs_main.parquet")
    ap.add_argument("--check-frame", help="the worker re-fit's frame.parquet, to compare inputs with")
    ap.add_argument("--check-pred", help="the worker re-fit's pred_wk_<through>.parquet")
    ap.add_argument("--register", action="store_true")
    ap.add_argument("--from-file")
    a = ap.parse_args()

    from models.trainer import MODELS_DIR
    if a.from_file:
        path = Path(a.from_file).resolve()
        with open(path, "rb") as fh:
            artifact = pickle.load(fh)
        if artifact.get("model_id") != pj.MODEL_ID:
            raise SystemExit(f"{path.name} is not a {pj.MODEL_ID} artifact")
    else:
        if not a.pairs and not a.check_frame:
            raise SystemExit("--pairs is required to fit (the calibration maps are fitted on them)")
        data, decisions = research_inputs(Path(a.cache))
        fr = nb.build_frame(data, decisions, with_lines=False)
        logger.info(f"frame {fr.shape}")
        if a.check_frame:
            ref = pd.read_parquet(a.check_frame)
            k = ["game_id", "player_id"]
            x, y = fr.set_index(k), ref.set_index(k)
            common = x.index.intersection(y.index)
            moved = {}
            for c in sorted(set(pj.minutes_cols()) | {c for s in pj.STATS for c in pj.rate_cols(s)}):
                u, v = x.loc[common, c].astype(float), y.loc[common, c].astype(float)
                d = int((~np.isclose(u, v, equal_nan=True, rtol=1e-9, atol=1e-9)).sum())
                if d:
                    moved[c] = d
            logger.info(f"frame check: {len(x):,} rows here, {len(y):,} stored, {len(common):,} common; "
                        f"inputs that differ: {moved or 'none'}")
            # 20 (game, player) keys appear twice in both frames: a player traded between the two
            # sides, on the pre-game roster of each, on a game he did not play
            if moved or len(common) != y.index.nunique():
                raise SystemExit("the frame does not reproduce the worker re-fit's")
            if not a.pairs:
                return
        prior = fit_fold(fr, a.through - 1)
        alphas, pred = widths(fr, prior, a.through)
        if a.check_pred:
            # each market's mean against the stored fold's per-stat means
            ref = pd.read_parquet(a.check_pred)
            m = pred.merge(ref, on=["game_id", "player_id"])
            for mk in pj.MARKETS:
                want = np.clip(sum(m[f"mu2_{s}"].values for s in nb.BY_MARKET[mk].parts), pj.MU_FLOOR, None)
                diff = float(np.max(np.abs(m[f"mu_{mk}"].values - want)))
                logger.info(f"pred check {mk}: max |difference| {diff:.2e} on {len(m):,} rows")
        fold = fit_fold(fr, a.through)
        pairs = pd.read_parquet(a.pairs)
        pairs = pairs[pairs.market.isin(pj.MARKETS)]
        cal = nb.fit_calibration(pairs, a.through + 1)
        version = datetime.now().strftime("%Y%m%d_%H%M%S")
        artifact = {
            "model_id": pj.MODEL_ID, "version": version, "sport": pj.SPORT, "kind": "nba_prop_projection",
            "minutes": fold["minutes"], "rates": fold["rates"],
            "alphas": {m: float(alphas[m]) for m in pj.MARKETS},
            "calibration": {m: tuple(float(x) for x in cal[m]) for m in pj.MARKETS},
            "card": {m: [list(v[0]), v[1]] for m, v in pj.CARD.items()},
            "minutes_cols": pj.minutes_cols(), "rate_cols": {s: pj.rate_cols(s) for s in pj.STATS},
            "train_seasons": list(range(nb.FIRST_TRAIN_SEASON, a.through + 1)),
            "n_train": fold["n_train"], "trained_at": datetime.now().isoformat(),
            "calibration_pairs": {"seasons": sorted(int(s) for s in pairs.season.unique()),
                                  "n": int(len(pairs)),
                                  "sha256": hashlib.sha256(pd.util.hash_pandas_object(
                                      pairs[["season", "market", "p", "y"]], index=False).values.tobytes()
                                  ).hexdigest()},
            "backtest": dict(BACKTEST),
        }
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        path = MODELS_DIR / f"{pj.MODEL_ID}_{version}.pkl"
        with open(path, "wb") as fh:
            pickle.dump(artifact, fh)
        logger.success(f"{pj.MODEL_ID} {version}: {fold['n_train']:,} rows; widths "
                       f"{json.dumps({m: round(v, 4) for m, v in artifact['alphas'].items()})}; maps "
                       f"{json.dumps({m: [round(x, 3) for x in v] for m, v in artifact['calibration'].items()})}")
    rel = Path(path).relative_to(MODELS_DIR.parent.parent).as_posix()
    logger.info(f"artifact: {rel}")
    if not a.register:
        logger.warning("not registered: the live artifact, if any, is untouched (--register to switch)")
        return
    from data.db import get_connection
    from models.trainer import _store_artifact
    conn = get_connection()
    try:
        _store_artifact(conn, pj.MODEL_ID, artifact["version"], path)   # bytes before the row naming them
        conn.execute("UPDATE model_registry SET is_active = 0 WHERE model_id = %s AND is_active = 1",
                     (pj.MODEL_ID,))
        conn.execute("""
            INSERT INTO model_registry (model_id, version, trained_on, train_seasons, holdout_season,
                                        holdout_accuracy, holdout_roi, holdout_picks, calibration_score,
                                        is_active, model_path, notes)
            VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, NULL, 1, %s, %s)
        """, (pj.MODEL_ID, artifact["version"], date.today().isoformat(),
              json.dumps(artifact["train_seasons"]), artifact["train_seasons"][-1],
              BACKTEST["roi"], BACKTEST["bets"], rel,
              "two-stage XGB (minutes x rate), NB widths, per-market Platt maps | walk-forward "
              "2023-24..2025-26, six cells, best bettable price, -200 floor: "
              f"{BACKTEST['bets']:,} bets {BACKTEST['roi'] * 100:+.2f}% (docs/nba_models_2026.md 5)"))
        conn.commit()
        logger.success(f"registered and active: {pj.MODEL_ID} {artifact['version']}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
