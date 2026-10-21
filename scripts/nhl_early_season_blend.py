"""The early weeks of an NHL season, backtested: the old inputs against the blended ones.

mike, 2026-10-01, on a proposed 10-game hold: "no, this is fucking why we have
back testing and seasons worth of data frmo out data sources." So the question
is not whether to sit the early weeks out but whether the inputs carry them.

WALK-FORWARD, FIXED PARAMETERS (scripts.walk_forward_eval.BASELINE_PARAMS, so
the feature list is the only thing that differs). For each test season the
model is fit on every earlier season from 2018-19 and scores the test season:

  OLD      features.feature_engine.NHL_H2H_FEATURES -- goals and results raw
  BLENDED  NHL_H2H_FEATURES_BLENDED -- every team number through
           data.nhl_asof.TeamBook.inputs, blended toward last season

Three windows: EARLY (either team under 10 games played), the FIRST GAMES, and
the REST of the season. "FIRST GAMES" HAS A PRECISE MEANING HERE: the games the
old list drops from training because a home / road scoring split is null -- the
home team has not yet played at home this season, or the road team has not yet
played on the road. About 45 a season; a team's very first game is a subset.
Accuracy is a diagnostic; the result is units at DraftKings' first pre-game
price (`odds.source = 'odds_api_historical'`), betting any side the model has
above DraftKings' implied probability by the cut.

    python -m scripts.nhl_early_season_blend                # the three windows
    python -m scripts.nhl_early_season_blend --sweep        # how much of last season to carry
    python -m scripts.nhl_early_season_blend --first-games  # those games, scored as production scores them
"""
import sys

sys.path.insert(0, ".")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from xgboost import XGBClassifier  # noqa: E402

from data.db import get_connection  # noqa: E402
from features.feature_engine import (NHL_H2H_FEATURES, NHL_H2H_FEATURES_BLENDED,  # noqa: E402
                                     build_training_dataset)
from scripts.nhl_market_lab import implied, novig, summarise, win_per_unit  # noqa: E402
from scripts.nhl_underdog_grid import load as load_prices  # noqa: E402
from scripts.walk_forward_eval import BASELINE_PARAMS  # noqa: E402

pd.set_option("display.width", 250)
SEASONS = list(range(2019, 2027))
TEST = [2022, 2023, 2024, 2025, 2026]
CUTS = (0.02, 0.04, 0.06)


def logloss(y, p) -> float:
    p = np.clip(np.asarray(p, dtype=float), 1e-9, 1 - 1e-9)
    y = np.asarray(y, dtype=float)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def walk(frame: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    parts = []
    for test in TEST:
        tr, te = frame[frame.season < test], frame[frame.season == test].copy()
        m = XGBClassifier(**BASELINE_PARAMS)
        m.fit(tr[feats].values.astype(float), tr.target.values.astype(int), verbose=False)
        te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
        parts.append(te[["game_id", "season", "game_date", "is_early_season", "target", "p"]])
    return pd.concat(parts, ignore_index=True)


def accuracy(name: str, s: pd.DataFrame) -> dict:
    if len(s) < 30:
        return {"window": name, "games": len(s)}
    out = {"window": name, "games": len(s), "home rate": round(float(s.target.mean()), 3)}
    for col, label in (("p_old", "old"), ("p_new", "blended"), ("mkt", "DraftKings")):
        q = s.dropna(subset=[col])
        if len(q) >= 30:
            out[f"log loss {label}"] = round(logloss(q.target, q[col]), 4)
            out[f"AUC {label}"] = round(float(roc_auc_score(q.target, q[col])), 3)
    return out


def units(name: str, s: pd.DataFrame, col: str, cut: float) -> dict:
    s = s.dropna(subset=[col, "dk_home", "dk_away"])
    rows = []
    for r in s.itertuples():
        p = getattr(r, col)
        for side, ps, price, won in (("home", p, r.dk_home, r.target == 1),
                                     ("away", 1 - p, r.dk_away, r.target == 0)):
            if ps - implied(price) >= cut:
                rows.append(win_per_unit(price) if won else -1.0)
    if len(rows) < 30:
        return {"window": name, "edge>=": cut, "bets": len(rows)}
    return {"window": name, "edge>=": cut, **summarise(np.array(rows))}


def main() -> None:
    old = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES)
    new = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES_BLENDED)
    print(f"games 2018-19 -> 2025-26: old list {len(old):,}, blended list {len(new):,} "
          f"({len(new) - len(old):,} the old list drops for null inputs)")
    po = walk(old, NHL_H2H_FEATURES).rename(columns={"p": "p_old"})
    pn = walk(new, NHL_H2H_FEATURES_BLENDED).rename(columns={"p": "p_new"})
    df = pn.merge(po[["game_id", "p_old"]], on="game_id", how="left")
    conn = get_connection()
    try:
        px = load_prices(conn)[["game_id", "dk_home", "dk_away"]]
    finally:
        conn.close()
    df = df.merge(px, on="game_id", how="left")
    ok = df.dk_home.notna()
    df["mkt"] = np.nan
    df.loc[ok, "mkt"] = [novig(h, a) for h, a in zip(df.dk_home[ok], df.dk_away[ok])]
    first = df.p_old.isna()
    early = (df.is_early_season == 1) & ~first
    rest = (df.is_early_season == 0) & ~first
    print(f"test seasons {TEST[0] - 1}-{str(TEST[0])[2:]} -> {TEST[-1] - 1}-{str(TEST[-1])[2:]}: "
          f"{len(df):,} games; {int(first.sum())} first games only the blended list can score, "
          f"{int(early.sum())} other early-season games, {int(rest.sum())} the rest; "
          f"{int(ok.sum()):,} with a DraftKings price")

    print("\n### Accuracy by window (walk-forward, fixed parameters)\n")
    print(pd.DataFrame([accuracy("first games (blended only)", df[first]),
                        accuracy("early season, both lists", df[early]),
                        accuracy("rest of season", df[rest]),
                        accuracy("all games both lists score", df[~first])]).to_string(index=False))

    rows = []
    for cut in CUTS:
        rows.append({"inputs": "blended", **units("first games (blended only)", df[first], "p_new", cut)})
        for label, col in (("old", "p_old"), ("blended", "p_new")):
            rows.append({"inputs": label, **units("early season, both lists", df[early], col, cut)})
            rows.append({"inputs": label, **units("rest of season", df[rest], col, cut)})
    print("\n### Units at DraftKings' first pre-game price, by window\n")
    print(pd.DataFrame(rows).sort_values(["edge>=", "window", "inputs"]).to_string(index=False))

    rows = []
    for season in TEST:
        s = df[(df.season == season) & (early | first)]
        r = {"season": f"{season - 1}-{str(season)[2:]}", "early + first games": len(s)}
        q = s.dropna(subset=["p_old"])
        r["log loss old"] = round(logloss(q.target, q.p_old), 4) if len(q) >= 30 else None
        r["log loss blended (same games)"] = round(logloss(q.target, q.p_new), 4) if len(q) >= 30 else None
        r["log loss blended (all)"] = round(logloss(s.target, s.p_new), 4) if len(s) >= 30 else None
        rows.append(r)
    print("\n### The early window season by season\n")
    print(pd.DataFrame(rows).to_string(index=False))

    q = df[first]
    print(f"\nfirst games: the blended model's home-win probability ranges {q.p_new.min():.3f}..{q.p_new.max():.3f} "
          f"(mean {q.p_new.mean():.3f}); share at 0.70 or higher {float((q.p_new >= 0.70).mean()):.3f}")


def sweep() -> None:
    """How much of last season the goals and results columns should carry."""
    import data.nhl_asof as asof
    old = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES)
    po = walk(old, NHL_H2H_FEATURES).rename(columns={"p": "p_old"})
    rows = []
    for k in (3, 5, 10, 25, 50):
        asof.TEAM_PRIOR_GOAL_GAMES, asof.TEAM_PRIOR_LOC_GAMES = k, max(2, k // 2)
        new = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES_BLENDED)
        df = walk(new, NHL_H2H_FEATURES_BLENDED).merge(po[["game_id", "p_old"]], on="game_id", how="left")
        first = df.p_old.isna()
        early, rest = (df.is_early_season == 1) & ~first, (df.is_early_season == 0) & ~first
        rows.append({"games of last season carried": k,
                     "first games": round(logloss(df[first].target, df[first].p), 4),
                     "early": round(logloss(df[early].target, df[early].p), 4),
                     "rest": round(logloss(df[rest].target, df[rest].p), 4),
                     "all both score": round(logloss(df[~first].target, df[~first].p), 4),
                     "AUC all both score": round(float(roc_auc_score(df[~first].target, df[~first].p)), 4),
                     "share of first games at 0.70+": round(float((df[first].p >= 0.70).mean()), 3)})
    early_o, rest_o = po.is_early_season == 1, po.is_early_season == 0
    rows.append({"games of last season carried": "old list (raw)", "first games": None,
                 "early": round(logloss(po[early_o].target, po[early_o].p_old), 4),
                 "rest": round(logloss(po[rest_o].target, po[rest_o].p_old), 4),
                 "all both score": round(logloss(po.target, po.p_old), 4),
                 "AUC all both score": round(float(roc_auc_score(po.target, po.p_old)), 4)})
    print("\n### Log loss by how many games of last season the goals and results columns carry\n")
    print(pd.DataFrame(rows).to_string(index=False))


def first_games() -> None:
    """The games the old list cannot TRAIN on, scored the way production scores them.

    Before a team's first game it has no row this season, so the scoring path
    stands last season's final row in for it
    (features.feature_engine._get_nhl_team_stats) -- running totals and all.
    Training drops these games, so the walk-forward frame has nothing to say
    about them; this builds each one through the scoring path and prices it
    with the old-list model fitted for its season. The historical rows that
    path reads were written by the rebuild, not by the daily ingestor, so this
    is a replay of the scoring path, not a recording of it.
    """
    from features.feature_engine import build_features_for_game
    old = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES)
    new = build_training_dataset("nhl_moneyline", SEASONS, feature_cols=NHL_H2H_FEATURES_BLENDED)
    pn = walk(new, NHL_H2H_FEATURES_BLENDED).rename(columns={"p": "p_new"})
    held = set(old.game_id)
    first = pn[~pn.game_id.isin(held)].copy()
    conn = get_connection()
    try:
        px = load_prices(conn)[["game_id", "dk_home", "dk_away"]]
        rows = []
        for test in TEST:
            tr = old[old.season < test]
            m = XGBClassifier(**BASELINE_PARAMS)
            m.fit(tr[NHL_H2H_FEATURES].values.astype(float), tr.target.values.astype(int), verbose=False)
            for gid in first[first.season == test].game_id:
                f = build_features_for_game(conn, gid)
                x = np.array([[np.nan if f.get(c) is None else float(f.get(c)) for c in NHL_H2H_FEATURES]])
                rows.append({"game_id": gid, "p_old": float(m.predict_proba(x)[0, 1]),
                             "d_goal_differential": f.get("d_goal_differential"),
                             "nulls": sum(f.get(c) is None for c in NHL_H2H_FEATURES)})
    finally:
        conn.close()
    df = first.merge(pd.DataFrame(rows), on="game_id").merge(px, on="game_id", how="left")
    ok = df.dk_home.notna()
    df["mkt"] = np.nan
    df.loc[ok, "mkt"] = [novig(h, a) for h, a in zip(df.dk_home[ok], df.dk_away[ok])]
    print(f"{len(df)} first games, {TEST[0] - 1}-{str(TEST[0])[2:]} -> {TEST[-1] - 1}-{str(TEST[-1])[2:]}; "
          f"{int(ok.sum())} with a DraftKings price; rows with a missing old input: {int((df.nulls > 0).sum())}")
    print(f"goal-difference gap fed to the old model: {df.d_goal_differential.abs().quantile([0.5, 0.9, 1.0]).round(0).to_dict()} "
          f"(absolute, median / 90th / max)")
    out = []
    for label, col in (("old list, as production scores a first game", "p_old"), ("blended list", "p_new"),
                       ("DraftKings no-vig", "mkt")):
        q = df.dropna(subset=[col])
        out.append({"model": label, "games": len(q), "log loss": round(logloss(q.target, q[col]), 4),
                    "AUC": round(float(roc_auc_score(q.target, q[col])), 3),
                    "share at 0.70+ or 0.30-": round(float(((q[col] >= 0.70) | (q[col] <= 0.30)).mean()), 3)})
    print("\n### First games of a season: accuracy\n")
    print(pd.DataFrame(out).to_string(index=False))
    out = []
    for cut in CUTS:
        for label, col in (("old list, as production scores a first game", "p_old"), ("blended list", "p_new")):
            out.append({"model": label, **units("first games", df, col, cut)})
    print("\n### First games of a season: units at DraftKings' first pre-game price\n")
    print(pd.DataFrame(out).drop(columns=["window"]).to_string(index=False))


if __name__ == "__main__":
    if "--sweep" in sys.argv:
        sweep()
    elif "--first-games" in sys.argv:
        first_games()
    else:
        main()
