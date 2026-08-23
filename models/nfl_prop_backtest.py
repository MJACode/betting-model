"""
NFL prop backtest — the only thing that can say whether a market is BEATABLE.

The models in `config.PROP_MODELS` were assessed against OUTCOMES: is the
predictive distribution right. That is a different claim from "this beats the
number on the screen", and only this harness can make the second one.

It implements the six gates fixed in docs/nfl_props_model.md §5 BEFORE any
result existed, so they cannot be moved now:

1. Priced at the juice actually quoted. Every bet settles at the American price
   on that side, in that book's own row. There are no -110 fill-ins: a player
   with no quote is a skipped row, not a bet at an assumed price.
2. The backtest runs the deployed selection. It calls the SCORER's own
   `_nfl_prop_probs` and `_push_adjusted`, the scorer's thresholds, the feature
   engine's own pool gate, and the same normalised-name odds join. Not a copy of
   any of them — the copy is what drifts.
3. Timestamp discipline. Only snapshots strictly before kickoff are eligible,
   and the model row may only use games strictly before the target game.
4. Placebo. `--placebo` swaps the model's probability for a naive rolling-8
   projection carrying the SAME distribution and threshold. If the naive version
   reproduces the ROI, the edge is the pool and the price, not the model.
5. Walk-forward by time, per-season split reported. Each test season is fit on
   prior seasons only, reusing the artifact's tuned hyperparameters rather than
   re-tuning (tuning inside the loop is how in-sample thresholds sneak back in).
6. The benchmark is the no-vig probability implied by the price paid, not 50%.

Pushes are three-way throughout: NFL count lines are frequently whole numbers,
a push returns the stake, and EV is computed on P(win | the bet resolves).

Correlated legs are reported, not silently counted as independent: bets are
tallied per (game, team) so a slate's real exposure is visible.

Usage:
    python -m models.nfl_prop_backtest --model nfl_prop_tackles_assists
    python -m models.nfl_prop_backtest --all --seasons 2024 2025
    python -m models.nfl_prop_backtest --all --placebo
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor, XGBClassifier
from sklearn.calibration import CalibratedClassifierCV

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config
from data.db import get_connection
from data.ingestors.nfl_prop_odds_ingestor import load_nfl_prop_odds
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from features.nfl_prop_feature_engine import (
    NFL_PROP_FEATURE_MAP, build_nfl_prop_training_dataset,
)
# The deployed probability code, imported rather than reimplemented.
from models.scorer import _nfl_prop_probs, _push_adjusted
from models.trainer import load_model

try:
    from loguru import logger
except ImportError:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


MIN_BETS_FOR_A_VERDICT = 100        # §5.6
BOOTSTRAP_DRAWS = 2000


def american_to_profit(price: float) -> float:
    """Profit on a 1-unit win at American odds."""
    p = float(price)
    return p / 100.0 if p > 0 else 100.0 / abs(p)


def no_vig_pair(over_price, under_price) -> tuple[float | None, float | None]:
    """
    The two-sided no-vig probabilities, which are the benchmark a bet must beat.

    A one-sided quote has no vig to remove, so it returns the raw implied
    probability and is flagged by the caller — betting into a one-way market is
    a different proposition and should not be averaged in silently.
    """
    def imp(x):
        if x is None:
            return None
        x = float(x)
        return (100.0 / (x + 100.0)) if x > 0 else (abs(x) / (abs(x) + 100.0))
    o, u = imp(over_price), imp(under_price)
    if o is None or u is None:
        return o, u
    total = o + u
    return o / total, u / total


def _fit(model_type: str, params: dict, X: np.ndarray, y: np.ndarray):
    """Refit with the artifact's tuned hyperparameters — never re-tuned here."""
    if model_type == "logistic":
        clf = XGBClassifier(**params, eval_metric="logloss", random_state=42,
                            n_jobs=-1, verbosity=0)
        m = CalibratedClassifierCV(estimator=clf, method="sigmoid", cv=3)
        m.fit(X, (y >= 1).astype(int))
        return m
    objective = "reg:squarederror" if model_type == "gamma" else "count:poisson"
    m = XGBRegressor(**params, objective=objective, random_state=42,
                     n_jobs=-1, verbosity=0)
    m.fit(X, y)
    return m


def _dispersion(model_type: str, y: np.ndarray, mu: np.ndarray) -> dict:
    """Refit dispersion on the same fold the mean was fit on."""
    from models.trainer import _nb_dispersion, _gamma_shape
    if model_type == "nbinom":
        return {"nb_r": _nb_dispersion(y, mu)}
    if model_type == "gamma":
        p0 = float((y <= 0).mean())
        pos = y > 0
        k = _gamma_shape(y[pos], np.clip(mu[pos], 1e-6, None) / max(1 - p0, 1e-6))
        return {"zero_inflation": p0, "gamma_shape": k}
    return {}


def _bootstrap_roi_ci(profits: np.ndarray, stakes: np.ndarray) -> tuple[float, float]:
    if len(profits) < 5:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(42)
    idx = rng.integers(0, len(profits), size=(BOOTSTRAP_DRAWS, len(profits)))
    rois = profits[idx].sum(axis=1) / np.maximum(stakes[idx].sum(axis=1), 1e-9)
    return float(np.percentile(rois, 2.5) * 100), float(np.percentile(rois, 97.5) * 100)


def backtest_model(model_id: str, test_seasons: list[int],
                   placebo: bool = False, bookmaker: str = None) -> dict:
    """Walk-forward: for each test season, fit on prior seasons and bet that one."""
    sport, market, model_type, _ = config.PROP_MODELS[model_id]
    artifact = load_model(model_id)
    if artifact is None:
        # Gate 2 says the backtest must run what the deployed path runs. Fitting
        # with XGBoost defaults and reporting the ROI as if it were the deployed
        # model is exactly the "backtest measures fiction" trap, so this is loud
        # rather than quiet — and the result is stamped so it cannot be quoted
        # as a validated number.
        logger.warning(f"{model_id}: no active artifact — DEFAULT hyperparameters. "
                       "This is NOT the deployed model; train first.")
    params = dict(artifact.get("best_params") or {}) if artifact else {}
    params.pop("objective", None)
    tuned = artifact is not None
    feature_cols = NFL_PROP_FEATURE_MAP[model_id]
    min_prob = config.MODEL_PROB_THRESHOLDS.get(model_id, 0.55)
    min_edge = config.MODEL_EDGE_THRESHOLDS.get(model_id, 0.05)
    book = bookmaker or config.ODDS_API_BOOKMAKER

    first = config.NFL_MODEL_FIRST_SEASON
    all_seasons = list(range(first, max(test_seasons) + 1))
    df_all = build_nfl_prop_training_dataset(model_id, all_seasons)
    if df_all.empty:
        return {"model_id": model_id, "bets": 0, "reason": "no feature rows"}

    conn = get_connection()
    # Definitional check, independent of selection: across EVERY quoted row we
    # could have bet, how often did our computed actual land over the book's
    # line, and how often did the BOOK's own no-vig price say it would?
    #
    # The naive version of this check — "is our over-share near 50%?" — is
    # wrong, and wrong in a way that would have condemned two honest markets.
    # A book sets a yardage or reception line at the median, so 50% is right
    # there; but it pins sacks and anytime-TD at 0.5 and prices the skew, so
    # 37% and 29% are right there. The book's own de-vigged price is the only
    # benchmark that holds for every market. A gap between the two means our
    # computed actual is not the stat they grade, and any ROI built on it is
    # measuring that gap.
    universe = {"over": 0, "under": 0, "push": 0, "sum_diff": 0.0,
                "sum_fair_over": 0.0, "priced": 0}
    try:
        bets: list[dict] = []
        for season in test_seasons:
            tr = df_all[df_all["season"] < season]
            te = df_all[df_all["season"] == season]
            if len(tr) < 300 or te.empty:
                continue
            Xtr = tr[feature_cols].values.astype(float)
            ytr = tr["target"].values.astype(float)
            model = _fit(model_type, params, Xtr, ytr)

            if model_type in ("nbinom", "gamma"):
                mu_tr = np.clip(model.predict(Xtr), 1e-6, None)
                art = {"model_type": model_type, **_dispersion(model_type, ytr, mu_tr)}
            else:
                art = {"model_type": model_type}

            Xte = te[feature_cols].values.astype(float)
            preds = (model.predict_proba(Xte)[:, 1] if model_type == "logistic"
                     else np.clip(model.predict(Xte), 1e-6, None))
            # PLACEBO: same distribution, same threshold, but the projection is
            # the player's own rolling-8 rather than the model.
            if placebo:
                base = _naive_projection(model_id, te, float(np.mean(ytr)))
                preds = (np.clip(base, 0.01, 0.99) if model_type == "logistic"
                         else np.clip(base, 1e-6, None))

            kickoffs = _kickoffs(conn, sorted(te["game_id"].unique().tolist()))
            odds = load_nfl_prop_odds(conn, sorted(te["game_id"].unique().tolist()),
                                      [market], bookmaker=book)
            actuals = te["target"].values.astype(float)

            for i, (_, row) in enumerate(te.iterrows()):
                gid = row["game_id"]
                key = (gid, norm_player_name(row["player_name"]), market)
                q = odds.get(key)
                if not q or q.get("line") is None:
                    continue                      # no quote = no bet, never a fill-in
                ko = kickoffs.get(gid)
                if ko and q.get("snapshot_at") and str(q["snapshot_at"]) >= str(ko):
                    continue                      # gate 3: post-kickoff line
                line = float(q["line"])
                p_over, p_under, p_push = _nfl_prop_probs(art, float(preds[i]), line)
                actual = actuals[i]
                universe["over" if actual > line else
                         "under" if actual < line else "push"] += 1
                universe["sum_diff"] += float(actual - line)
                _fo, _fu = no_vig_pair(q.get("over_price"), q.get("under_price"))
                if _fo is not None:
                    universe["sum_fair_over"] += float(_fo)
                    universe["priced"] += 1

                for side, raw_p, price in (("over", p_over, q.get("over_price")),
                                           ("under", p_under, q.get("under_price"))):
                    if price is None:
                        continue
                    fair_over, fair_under = no_vig_pair(q.get("over_price"),
                                                        q.get("under_price"))
                    fair = fair_over if side == "over" else fair_under
                    if fair is None:
                        continue                  # one-way market: not this bet
                    p = _push_adjusted(raw_p, p_push)
                    edge = p - fair               # gate 6: vs the price paid
                    if p < min_prob or edge < min_edge:
                        continue
                    if actual == line:
                        result, profit = "PUSH", 0.0
                    else:
                        won = (actual > line) if side == "over" else (actual < line)
                        result = "WIN" if won else "LOSS"
                        profit = american_to_profit(price) if won else -1.0
                    bets.append({"season": season, "game_id": gid, "team": row["team"],
                                 "player": row["player_name"], "side": side,
                                 "line": line, "price": float(price), "fair": fair,
                                 "model_prob": p, "edge": edge, "actual": actual,
                                 "result": result, "profit": profit})
    finally:
        conn.close()
    return _summarise(model_id, bets, placebo, book, tuned, universe)


# Three targets are DERIVED and so have no rolling column of their own. Left to
# a `if col in columns` check the placebo silently passed the model's own
# predictions straight through, and the run reported the placebo reproducing the
# model exactly — which reads as "the naive baseline wins too" when it actually
# means "no placebo ran". A placebo that can quietly not happen is worse than
# none, so an unbuildable one now raises.
_NAIVE_COMPONENTS: dict[str, list[str]] = {
    "nfl_prop_rush_rec_yards":  ["rushing_yards_r8", "receiving_yards_r8"],
    "nfl_prop_tackles_assists": ["def_tackles_solo_r8", "def_tackle_assists_r8"],
    "nfl_prop_anytime_td":      ["rushing_tds_r8", "receiving_tds_r8"],
}


def _naive_projection(model_id: str, te: pd.DataFrame, fallback: float) -> np.ndarray:
    """The player's own rolling-8, summed over components for derived targets."""
    from features.nfl_prop_feature_engine import _TARGET
    cols = _NAIVE_COMPONENTS.get(model_id, [f"{_TARGET[model_id]}_r8"])
    missing = [c for c in cols if c not in te.columns]
    if missing:
        raise ValueError(
            f"{model_id}: cannot build a placebo projection — missing {missing}. "
            "Refusing to run a placebo that would silently reuse the model.")
    return te[cols].fillna(fallback / len(cols)).sum(axis=1).values.astype(float)


def _kickoffs(conn, game_ids: list[str]) -> dict:
    if not game_ids:
        return {}
    rows = conn.execute("""
        SELECT DISTINCT game_id, commence_time FROM nfl_team_game_stats
        WHERE game_id = ANY(%s) AND commence_time IS NOT NULL
    """, (list(game_ids),)).fetchall()
    return {r[0]: (r[1].isoformat() if hasattr(r[1], "isoformat") else str(r[1]))
            for r in rows}


def _summarise(model_id: str, bets: list[dict], placebo: bool, book: str,
               tuned: bool = True, universe: dict | None = None) -> dict:
    uni = _universe_summary(universe)
    if not bets:
        return {"model_id": model_id, "bets": 0, "placebo": placebo,
                "book": book, "tuned": tuned, "universe": uni}
    df = pd.DataFrame(bets)
    decided = df[df.result != "PUSH"]
    profits = df["profit"].values.astype(float)
    stakes = np.ones(len(df))
    lo, hi = _bootstrap_roi_ci(profits, stakes)
    per_season = {
        int(s): {"bets": int(len(g)), "won": int((g.result == "WIN").sum()),
                 "roi_pct": round(100 * g.profit.sum() / max(len(g), 1), 2)}
        for s, g in df.groupby("season")
    }
    legs = defaultdict(int)
    for b in bets:
        legs[(b["game_id"], b["team"])] += 1
    return {
        "model_id": model_id, "placebo": placebo, "book": book, "tuned": tuned,
        "bets": int(len(df)), "pushes": int((df.result == "PUSH").sum()),
        "won": int((df.result == "WIN").sum()),
        "win_pct": round(100 * (decided.result == "WIN").mean(), 2) if len(decided) else 0.0,
        "roi_pct": round(100 * profits.sum() / len(df), 2),
        "roi_ci": (round(lo, 2), round(hi, 2)),
        "units": round(float(profits.sum()), 2),
        "mean_edge_pp": round(100 * float(df.edge.mean()), 2),
        # An edge that lives entirely on one side is usually a definitional
        # mismatch between our actual and what the book grades, not an edge.
        "sides": {k: {"bets": int(len(g)),
                      "roi_pct": round(100 * g.profit.sum() / max(len(g), 1), 2)}
                  for k, g in df.groupby("side")},
        "universe": uni,
        "per_season": per_season,
        # correlated exposure: how many legs land on the same team in one game
        "max_legs_one_team_game": max(legs.values()),
        "verdict": (_verdict(len(df), profits.sum() / len(df), lo, per_season, uni)
                    if tuned else "UNTUNED — default hyperparameters, not the deployed model"),
    }


def _universe_summary(universe: dict | None) -> dict:
    """Our over-rate vs the book's de-vigged over-rate, across all quoted rows."""
    if not universe:
        return {}
    n = universe["over"] + universe["under"] + universe["push"]
    if not n:
        return {}
    out = {"quoted": n,
           "over_pct": round(100 * universe["over"] / n, 1),
           "push_pct": round(100 * universe["push"] / n, 1),
           "mean_actual_minus_line": round(universe["sum_diff"] / n, 2)}
    if universe.get("priced"):
        book = 100 * universe["sum_fair_over"] / universe["priced"]
        out["book_over_pct"] = round(book, 1)
        out["gap_pp"] = round(out["over_pct"] - book, 1)
    return out


# How far our over-rate may sit from the book's de-vigged over-rate before the
# result is a measurement of the gap rather than of skill. 5pp is roughly two
# standard errors on a 1,000-row universe and is far tighter than any real
# market inefficiency in a stat both sides can count.
MAX_DEFINITION_GAP_PP = 5.0


def _verdict(n: int, roi: float, ci_lo: float, per_season: dict,
             uni: dict | None = None) -> str:
    if n < MIN_BETS_FOR_A_VERDICT:
        return f"NO VERDICT — {n} bets, gate is {MIN_BETS_FOR_A_VERDICT}"
    gap = (uni or {}).get("gap_pp")
    if gap is not None and abs(gap) > MAX_DEFINITION_GAP_PP:
        return (f"DEFINITIONAL MISMATCH — our actual lands over the line "
                f"{uni['over_pct']}% of the time, the book's own de-vigged price "
                f"says {uni['book_over_pct']}%. That {gap:+.1f}pp gap is a "
                "different stat, not an edge; no ROI here is trustworthy")
    if not np.isfinite(ci_lo) or ci_lo <= 0:
        return "NOT BEATABLE — ROI confidence interval includes zero"
    tot = sum(v["bets"] * v["roi_pct"] for v in per_season.values())
    if tot and any(v["bets"] * v["roi_pct"] > 0.6 * tot for v in per_season.values()):
        return "ONE SEASON, NOT AN EDGE — >60% of the return is a single season"
    return "CLEARS THE BAR — re-check on the next season before unpausing"


def main() -> None:
    ap = argparse.ArgumentParser(description="NFL prop backtest (docs/nfl_props_model.md §5)")
    ap.add_argument("--model")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025])
    ap.add_argument("--placebo", action="store_true")
    ap.add_argument("--book", default=None)
    args = ap.parse_args()

    ids = ([m for m in config.PROP_MODELS if m.startswith("nfl_prop")]
           if args.all else [args.model])
    for mid in ids:
        try:
            r = backtest_model(mid, args.seasons, placebo=args.placebo, bookmaker=args.book)
        except Exception as exc:                       # one model must not sink the sweep
            logger.error(f"{mid}: {type(exc).__name__}: {exc}")
            continue
        if r.get("bets"):
            logger.success(
                f"{mid}{' [PLACEBO]' if args.placebo else ''}: {r['bets']} bets "
                f"({r['pushes']} push) | win {r['win_pct']}% | ROI {r['roi_pct']}% "
                f"CI{r['roi_ci']} | {r['units']}u | edge {r['mean_edge_pp']}pp | "
                f"sides {r['sides']} | universe {r['universe']} | "
                f"seasons {r['per_season']} | {r['verdict']}")
        else:
            logger.info(f"{mid}: no qualifying bets "
                        f"({r.get('reason', 'threshold or no quotes')}) | "
                        f"universe {r.get('universe')}")


if __name__ == "__main__":
    main()
