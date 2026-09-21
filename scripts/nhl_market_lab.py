"""NHL multi-market backtest, in units, at real opening prices.

The analysis protocol (.claude/rules/analysis-and-thresholds.md) applied to the
NHL: the market is the baseline, results are units and closing-line value, the
cut is a neighbourhood, the split is early / late, the folds walk forward.

PRICES. The Sportsbook Reviews Online archive (data/ingestors/nhl_sbr_archive):
consensus opening and closing moneyline and total with prices, and one puck
line with a price, 2018-19 -> 2022-11-27. The book behind it is not named.

DESIGN. Every bet is DECIDED AND GRADED AT THE OPEN — the price a bettor could
have had — and its closing-line value is the move in the no-vig probability of
the side taken from open to close. The puck line has one price, so it is graded
there and carries no CLV. Test seasons 2021, 2022 and 2023 (Oct-Nov 2022 only);
each model is trained on every season before its test season, from 2019.

MODELS are this repo's own feature lists (features/feature_engine.py) with the
fixed walk-forward parameters, NOT the registered artifacts: those trained
through 2024-25, so every priced season is inside their training set.

    python -m scripts.nhl_market_lab            # prints the tables
"""
from __future__ import annotations

import sys
from collections import defaultdict

import numpy as np
import pandas as pd
from sklearn.metrics import log_loss, roc_auc_score
from xgboost import XGBClassifier

sys.path.insert(0, ".")

from data.db import get_connection
from data.ingestors.nhl_sbr_archive import SOURCE
from features import feature_engine as fe
from features.feature_engine import build_training_dataset
from scripts.walk_forward_eval import BASELINE_PARAMS

SEASONS = [2019, 2020, 2021, 2022, 2023]
TEST_SEASONS = [2021, 2022, 2023]
EDGES = (0.02, 0.04, 0.06, 0.08, 0.10)
GOALIE = {"d_goalie_save_pct", "d_goalie_gaa", "d_goalie_gsaa"}
SHOTS_ST = {"d_corsi_for_pct", "d_power_play_pct", "d_penalty_kill_pct"}


# ── prices ───────────────────────────────────────────────────────────────────

def win_per_unit(american: float) -> float:
    return american / 100.0 if american > 0 else 100.0 / abs(american)


def implied(american: float) -> float:
    return 100.0 / (american + 100.0) if american > 0 else abs(american) / (abs(american) + 100.0)


def novig(a: float, b: float) -> float:
    """No-vig probability of the FIRST side of a two-way price."""
    pa, pb = implied(a), implied(b)
    return pa / (pa + pb)


def load_prices(conn) -> pd.DataFrame:
    rows = conn.execute("""
        SELECT o.game_id, o.market, o.snapshot_type, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price,
               g.home_score, g.away_score, g.game_date, g.season
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE o.source = ? AND g.home_score IS NOT NULL
    """, (SOURCE,)).fetchall()
    out: dict[str, dict] = defaultdict(dict)
    for gid, mk, snap, hp, ap, sh, tl, op, up, hs, as_, gd, season in rows:
        d = out[gid]
        d.update(game_id=gid, hs=float(hs), as_=float(as_), game_date=gd, season=season)
        if mk == "h2h":
            d[f"ml_home_{snap}"], d[f"ml_away_{snap}"] = hp, ap
        elif mk == "totals":
            d[f"total_{snap}"], d[f"over_{snap}"], d[f"under_{snap}"] = tl, op, up
        elif mk == "spreads":
            d["spread_home"], d["pl_home"], d["pl_away"] = sh, hp, ap
    return pd.DataFrame(out.values())


# ── grading ──────────────────────────────────────────────────────────────────

def summarise(profits: np.ndarray, clv: np.ndarray | None = None) -> dict:
    n = len(profits)
    if n == 0:
        return {"bets": 0}
    roi = profits.mean()
    se = profits.std(ddof=1) / np.sqrt(n) if n > 1 else float("nan")
    out = {"bets": n, "units": round(float(profits.sum()), 1), "roi": round(float(roi) * 100, 2),
           "ci": f"{(roi - 1.96 * se) * 100:+.1f}..{(roi + 1.96 * se) * 100:+.1f}"}
    if clv is not None and len(clv):
        out["clv_pts"] = round(float(np.nanmean(clv)) * 100, 2)
        out["beat_close"] = round(float(np.nanmean(clv > 0)) * 100, 1)
    return out


def grade_ml(df: pd.DataFrame, side_home: np.ndarray, snap: str = "open"):
    price = np.where(side_home, df[f"ml_home_{snap}"], df[f"ml_away_{snap}"]).astype(float)
    won = np.where(side_home, df.hs > df.as_, df.as_ > df.hs)
    profit = np.where(won, [win_per_unit(p) for p in price], -1.0)
    p_open = np.array([novig(h, a) for h, a in zip(df.ml_home_open, df.ml_away_open)])
    p_close = np.array([novig(h, a) for h, a in zip(df.ml_home_close, df.ml_away_close)])
    clv = np.where(side_home, p_close - p_open, p_open - p_close)
    return profit, clv


def grade_total(df: pd.DataFrame, side_over: np.ndarray):
    tot = df.hs + df.as_
    price = np.where(side_over, df.over_open, df.under_open).astype(float)
    won = np.where(side_over, tot > df.total_open, tot < df.total_open)
    push = tot == df.total_open
    profit = np.where(push, 0.0, np.where(won, [win_per_unit(p) for p in price], -1.0))
    same = df.total_open == df.total_close              # CLV only where the NUMBER held
    p_open = np.array([novig(o, u) for o, u in zip(df.over_open, df.under_open)])
    p_close = np.array([novig(o, u) for o, u in zip(df.over_close, df.under_close)])
    clv = np.where(same, np.where(side_over, p_close - p_open, p_open - p_close), np.nan)
    # a half-goal move TOWARD the side taken is value too: count it as its own number
    moved = np.where(side_over, df.total_close - df.total_open, df.total_open - df.total_close)
    return profit, clv, moved


def grade_pl(df: pd.DataFrame, side_home: np.ndarray):
    margin = df.hs - df.as_ + df.spread_home
    price = np.where(side_home, df.pl_home, df.pl_away).astype(float)
    won = np.where(side_home, margin > 0, margin < 0)
    return np.where(won, [win_per_unit(p) for p in price], -1.0)


# ── frames ───────────────────────────────────────────────────────────────────

def frames(model_id: str) -> dict[int, pd.DataFrame]:
    out = {}
    for s in SEASONS:
        f = build_training_dataset(model_id, seasons=[s])
        out[s] = f[0] if isinstance(f, tuple) else f
    return out


def walk(frames_: dict, feats: list[str], target: str = "target"):
    """Out-of-sample probability of `target` for every test-season game."""
    parts = []
    for test in TEST_SEASONS:
        tr = pd.concat([frames_[s] for s in SEASONS if s < test]).dropna(subset=feats + [target])
        te = frames_[test].dropna(subset=feats + [target]).copy()
        m = XGBClassifier(**BASELINE_PARAMS)
        m.fit(tr[feats].values.astype(float), tr[target].values.astype(int), verbose=False)
        te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
        parts.append(te)
    return pd.concat(parts)


def edge_grid(name: str, df: pd.DataFrame, p_side: np.ndarray, p_mkt: np.ndarray, grader):
    """One row per edge cut; `grader(sub_df, side_bool)` returns profit[, clv[, moved]]."""
    rows = []
    for e in EDGES:
        take_a = p_side - p_mkt >= e                    # the 'first' side (home / over)
        take_b = (1 - p_side) - (1 - p_mkt) >= e
        pick = take_a | take_b
        if pick.sum() == 0:
            rows.append({"model": name, "edge>=": e, "bets": 0})
            continue
        sub = df[pick]
        res = grader(sub, take_a[pick])
        profit = res[0] if isinstance(res, tuple) else res
        clv = res[1] if isinstance(res, tuple) and len(res) > 1 else None
        row = {"model": name, "edge>=": e, **summarise(profit, clv)}
        if isinstance(res, tuple) and len(res) > 2:
            row["line_moved_our_way"] = round(float(np.nanmean(res[2] > 0)) * 100, 1)
        order = np.argsort(sub.game_date.values, kind="stable")
        half = len(order) // 2
        row["early_roi"] = round(float(profit[order[:half]].mean()) * 100, 1) if half else None
        row["late_roi"] = round(float(profit[order[half:]].mean()) * 100, 1) if half else None
        rows.append(row)
    return rows


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    conn = get_connection()
    try:
        prices = load_prices(conn)
    finally:
        conn.close()
    test_px = prices[prices.season.isin(TEST_SEASONS)]
    print(f"priced games: {len(prices):,}; in the test seasons {TEST_SEASONS}: {len(test_px):,}")

    # ── 1. what the MARKET and blind betting do on the test seasons ──────────
    ml = test_px.dropna(subset=["ml_home_open", "ml_away_open", "ml_home_close", "ml_away_close"])
    y = (ml.hs > ml.as_).astype(int).values
    p_open = np.array([novig(h, a) for h, a in zip(ml.ml_home_open, ml.ml_away_open)])
    p_close = np.array([novig(h, a) for h, a in zip(ml.ml_home_close, ml.ml_away_close)])
    print(f"\nmoneyline, {len(ml):,} games — accuracy scores (diagnostics): "
          f"market OPEN log loss {log_loss(y, p_open):.4f} AUC {roc_auc_score(y, p_open):.4f}; "
          f"market CLOSE log loss {log_loss(y, p_close):.4f} AUC {roc_auc_score(y, p_close):.4f}; "
          f"home-win rate {y.mean():.3f} -> log loss {log_loss(y, np.full(len(y), y.mean())):.4f}")
    blind = []
    fav_home = p_open >= 0.5
    for name, side in (("always home", np.ones(len(ml), bool)), ("always away", np.zeros(len(ml), bool)),
                       ("always favourite", fav_home), ("always underdog", ~fav_home)):
        pr, clv = grade_ml(ml, side)
        blind.append({"strategy": name + " (open price)", **summarise(pr, clv)})
    tt = test_px.dropna(subset=["total_open", "over_open", "under_open", "total_close",
                                "over_close", "under_close"])
    for name, side in (("always over", np.ones(len(tt), bool)), ("always under", np.zeros(len(tt), bool))):
        pr, clv, _ = grade_total(tt, side)
        blind.append({"strategy": name + " (open line+price)", **summarise(pr, clv)})
    pl = test_px.dropna(subset=["spread_home", "pl_home", "pl_away"])
    home_fav = pl.spread_home < 0
    for name, side in (("puck line: favourite -1.5", home_fav.values), ("puck line: underdog +1.5", ~home_fav.values)):
        blind.append({"strategy": name, **summarise(grade_pl(pl, side))})
    show("Blind betting on the test seasons (the floor any model must beat)", blind)

    # ── 2. moneyline ─────────────────────────────────────────────────────────
    base = list(fe.FEATURE_MAP["nhl_moneyline"])
    fr = frames("nhl_moneyline")
    ml_rows = []
    variants = {"moneyline: repo features (22)": base,
                "  minus goalie group": [f for f in base if f not in GOALIE],
                "  minus shot-share / PP / PK group": [f for f in base if f not in SHOTS_ST]}
    for name, feats in variants.items():
        pred = walk(fr, feats).merge(ml, on="game_id", suffixes=("", "_px"))
        po = np.array([novig(h, a) for h, a in zip(pred.ml_home_open, pred.ml_away_open)])
        yy = (pred.hs > pred.as_).astype(int).values
        print(f"{name}: n={len(pred):,} model log loss {log_loss(yy, pred.p):.4f} "
              f"AUC {roc_auc_score(yy, pred.p):.4f} | market open on the same games "
              f"{log_loss(yy, po):.4f} / {roc_auc_score(yy, po):.4f}")
        ml_rows += edge_grid(name, pred, pred.p.values, po, grade_ml)
    # does the model add anything ONCE THE MARKET IS KNOWN?
    for s in SEASONS:
        f = fr[s].merge(prices[["game_id", "ml_home_open", "ml_away_open"]], on="game_id")
        f = f.dropna(subset=["ml_home_open", "ml_away_open"])
        f["mkt_open"] = [novig(h, a) for h, a in zip(f.ml_home_open, f.ml_away_open)]
        fr[s] = f
    pred = walk(fr, base + ["mkt_open"]).merge(ml, on="game_id", suffixes=("", "_px"))
    po = pred.mkt_open.values
    yy = (pred.hs > pred.as_).astype(int).values
    print(f"moneyline: repo features + the market's own open probability: n={len(pred):,} "
          f"log loss {log_loss(yy, pred.p):.4f} vs market open {log_loss(yy, po):.4f}")
    ml_rows += edge_grid("moneyline: features + market open prob", pred, pred.p.values, po, grade_ml)
    show("Moneyline — bet at the OPEN when model minus no-vig open >= edge", ml_rows)

    # ── 3. totals ────────────────────────────────────────────────────────────
    tf = frames("nhl_over_under")
    tfeats = list(fe.FEATURE_MAP["nhl_over_under"])
    for s in SEASONS:
        f = tf[s].drop(columns=["total_line", "target"], errors="ignore").merge(
            prices[["game_id", "total_open", "hs", "as_"]], on="game_id").dropna(subset=["total_open"])
        f["total_line"] = f.total_open                    # the model sees the OPENING number
        f = f[f.hs + f.as_ != f.total_open]               # a push is not a training label
        f["target"] = (f.hs + f.as_ > f.total_open).astype(int)
        tf[s] = f.drop(columns=["hs", "as_", "total_open"])
    pred = walk(tf, tfeats).merge(tt, on="game_id", suffixes=("", "_px"))
    po = np.array([novig(o, u) for o, u in zip(pred.over_open, pred.under_open)])
    yy = pred.target.values
    print(f"totals: n={len(pred):,} model log loss {log_loss(yy, pred.p):.4f} AUC "
          f"{roc_auc_score(yy, pred.p):.4f} | market open {log_loss(yy, po):.4f} / {roc_auc_score(yy, po):.4f}")
    show("Totals — bet the OPENING number and price when model minus no-vig open >= edge",
         edge_grid("totals: repo features (16)", pred, pred.p.values, po, grade_total))

    # ── 4. puck line ─────────────────────────────────────────────────────────
    pf = {}
    for s in SEASONS:
        f = fr[s].drop(columns=["target", "mkt_open", "ml_home_open", "ml_away_open"], errors="ignore").merge(
            prices[["game_id", "spread_home", "hs", "as_"]], on="game_id").dropna(subset=["spread_home"])
        f["target"] = (f.hs - f.as_ + f.spread_home > 0).astype(int)     # HOME covers
        pf[s] = f.drop(columns=["hs", "as_"])
    pred = walk(pf, base + ["spread_home"]).merge(pl, on="game_id", suffixes=("", "_px"))
    po = np.array([novig(h, a) for h, a in zip(pred.pl_home, pred.pl_away)])
    yy = pred.target.values
    print(f"puck line: n={len(pred):,} model log loss {log_loss(yy, pred.p):.4f} AUC "
          f"{roc_auc_score(yy, pred.p):.4f} | market {log_loss(yy, po):.4f} / {roc_auc_score(yy, po):.4f}")
    show("Puck line +/-1.5 — one archived price, so no closing-line value",
         edge_grid("puck line: repo features + the line", pred, pred.p.values, po, grade_pl))


if __name__ == "__main__":
    main()
