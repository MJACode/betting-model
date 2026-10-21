"""NHL market lab, round two: inputs built from the per-game logs, regularised models.

Round one (scripts/nhl_market_lab.py, docs/nhl_market_lab.md) used the repo's
22 inputs with untuned trees and lost at every cut — but its ablation said WHERE
the signal is: shot share / power play / penalty kill carried it, the goalie
group carried none, and the model was badly over-confident (it "found" an edge
in 85% of games). So this round:

  * builds every input from `nhl_team_game_log` / `nhl_goalie_game_log`, as-of,
    as exponentially weighted rates over a team's PRIOR games (the carry-over
    across the summer is the prior-season blend) — in pandas, in seconds;
  * tests them as GROUPS (form, shots, special teams, goalie, schedule, rating);
  * uses a regularised logistic model and a heavily regularised tree model;
  * asks the question that matters: given the market's OPENING probability,
    do our inputs add anything? (the "market + inputs" rows);
  * tests the one market-only rule round one surfaced — openers shade against
    favourites — by price band, across ALL five priced seasons.

Bets are decided and graded at the OPEN; closing-line value is the no-vig move
toward the side taken. Walk-forward: test 2020, 2021, 2022, 2023, train on every
earlier season from 2019.

    python -m scripts.nhl_market_lab2
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

sys.path.insert(0, ".")

from data.db import get_connection
from scripts.nhl_market_lab import (EDGES, grade_ml, grade_pl, grade_total, load_prices,
                                    novig, summarise)

TEST_SEASONS = [2020, 2021, 2022, 2023]
HALF_LIFE_LONG, HALF_LIFE_SHORT = 25, 6        # games
TREE = dict(n_estimators=300, max_depth=3, learning_rate=0.03, subsample=0.8,
            colsample_bytree=0.8, min_child_weight=25, reg_lambda=8.0, gamma=1.0,
            eval_metric="logloss", random_state=42, n_jobs=-1, verbosity=0)


# ── inputs ───────────────────────────────────────────────────────────────────

def team_frame(conn) -> pd.DataFrame:
    cols = ["nhl_game_id", "game_id", "team", "opponent", "season", "game_date", "is_home",
            "goals_for", "goals_against", "shots_for", "shots_against", "sat_for_5v5",
            "sat_against_5v5", "pp_opportunities", "pp_goals", "times_shorthanded",
            "pp_goals_against", "faceoff_win_pct"]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM nhl_team_game_log").fetchall()
    t = pd.DataFrame(rows, columns=cols).sort_values(["team", "game_date", "nhl_game_id"])
    for c in cols[7:]:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    t["game_date"] = pd.to_datetime(t["game_date"])
    g = t.groupby("team", sort=False)

    def ew(col, hl):                     # rate over PRIOR games only
        return g[col].transform(lambda s: s.shift(1).ewm(halflife=hl, min_periods=5).mean())

    for hl, tag in ((HALF_LIFE_LONG, "l"), (HALF_LIFE_SHORT, "s")):
        t[f"gf_{tag}"], t[f"ga_{tag}"] = ew("goals_for", hl), ew("goals_against", hl)
    t["sf"], t["sa"] = ew("shots_for", HALF_LIFE_LONG), ew("shots_against", HALF_LIFE_LONG)
    satf, sata = ew("sat_for_5v5", HALF_LIFE_LONG), ew("sat_against_5v5", HALF_LIFE_LONG)
    t["sat_share"] = satf / (satf + sata)
    t["pp_pct"] = ew("pp_goals", 40) / ew("pp_opportunities", 40)
    t["pk_pct"] = 1 - ew("pp_goals_against", 40) / ew("times_shorthanded", 40)
    t["pp_opp"], t["pk_opp"] = ew("pp_opportunities", 40), ew("times_shorthanded", 40)
    t["fo"] = ew("faceoff_win_pct", HALF_LIFE_LONG)
    t["sh_pct"] = ew("goals_for", HALF_LIFE_LONG) / t["sf"]          # finishing, mostly luck
    prev = g["game_date"].shift(1)
    t["rest"] = (t["game_date"] - prev).dt.days.clip(upper=6).fillna(6)
    t["b2b"] = (t["rest"] == 1).astype(int)
    t["road_trip"] = g["is_home"].transform(
        lambda s: (1 - s).groupby((s != s.shift()).cumsum()).cumsum().shift(1).fillna(0))
    return t


def goalie_frame(conn) -> pd.DataFrame:
    cols = ["nhl_game_id", "game_id", "team", "player_id", "game_date", "started",
            "shots_against", "goals_against", "toi_seconds"]
    rows = conn.execute(f"SELECT {', '.join(cols)} FROM nhl_goalie_game_log").fetchall()
    gl = pd.DataFrame(rows, columns=cols).sort_values(["player_id", "game_date", "nhl_game_id"])
    for c in ("shots_against", "goals_against"):
        gl[c] = pd.to_numeric(gl[c], errors="coerce").fillna(0)
    lg = gl.goals_against.sum() / gl.shots_against.sum()              # league goals per shot
    g = gl.groupby("player_id", sort=False)
    sa = g["shots_against"].transform(lambda s: s.shift(1).ewm(halflife=30, min_periods=1).sum())
    ga = g["goals_against"].transform(lambda s: s.shift(1).ewm(halflife=30, min_periods=1).sum())
    k = 300.0                                                        # league-average shots mixed in
    gl["g_sv"] = 1 - (ga.fillna(0) + k * lg) / (sa.fillna(0) + k)
    gl["g_starts"] = g.cumcount()
    st = gl[gl.started == 1].drop_duplicates(["game_id", "team"])
    return st[["game_id", "team", "g_sv", "g_starts"]]


def add_rating(games: pd.DataFrame) -> pd.DataFrame:
    """A running goal-margin rating, updated AFTER each game (so it is as-of)."""
    rating: dict[str, float] = {}
    out_h, out_a = [], []
    for r in games.sort_values(["game_date", "game_id"]).itertuples():
        h, a = rating.get(r.home, 0.0), rating.get(r.away, 0.0)
        out_h.append(h)
        out_a.append(a)
        if pd.notna(r.hs):
            err = float(np.clip(r.hs - r.as_, -4, 4)) - (h - a + 0.18)
            rating[r.home], rating[r.away] = h + 0.02 * err, a - 0.02 * err
    g = games.sort_values(["game_date", "game_id"]).copy()
    g["rate_h"], g["rate_a"] = out_h, out_a
    return g


GROUPS = {
    "form":     ["d_gf_l", "d_ga_l", "d_gf_s", "d_ga_s"],
    "shots":    ["d_sf", "d_sa", "d_sat_share", "d_sh_pct"],
    "special":  ["d_pp_pct", "d_pk_pct", "d_pp_opp", "d_pk_opp", "d_fo"],
    "goalie":   ["d_g_sv", "h_g_starts", "a_g_starts"],
    "schedule": ["h_rest", "a_rest", "h_b2b", "a_b2b", "a_road_trip"],
    "rating":   ["d_rate"],
}
TOTAL_FEATS = ["s_gf_l", "s_ga_l", "s_gf_s", "s_sf", "s_sa", "s_pp_opp", "s_pk_opp",
               "h_g_sv", "a_g_sv", "h_b2b", "a_b2b", "total_open", "mkt_over"]


def build(conn, with_prices: bool = True) -> pd.DataFrame:
    t, gk = team_frame(conn), goalie_frame(conn)
    t = t.merge(gk, on=["game_id", "team"], how="left")
    keep = ["game_id", "gf_l", "ga_l", "gf_s", "ga_s", "sf", "sa", "sat_share", "sh_pct",
            "pp_pct", "pk_pct", "pp_opp", "pk_opp", "fo", "rest", "b2b", "road_trip",
            "g_sv", "g_starts"]
    h = t[t.is_home == 1][keep].add_prefix("h_").rename(columns={"h_game_id": "game_id"})
    a = t[t.is_home == 0][keep].add_prefix("a_").rename(columns={"a_game_id": "game_id"})
    # The archive prices are found by `odds.source`, which has no index; on a busy
    # day that scan hits the statement timeout. A caller that brings its own
    # prices (the 3-way lab) skips it.
    px = load_prices(conn) if with_prices else pd.DataFrame(columns=["game_id"])
    g = conn.execute("""SELECT game_id, game_date, season, home_team, away_team, home_score,
                               away_score FROM games WHERE sport='NHL' AND home_score IS NOT NULL
                     """).fetchall()
    games = pd.DataFrame(g, columns=["game_id", "game_date", "season", "home", "away", "hs", "as_"])
    games[["hs", "as_"]] = games[["hs", "as_"]].astype(float)
    games = add_rating(games)
    df = games.merge(h, on="game_id").merge(a, on="game_id").merge(
        px.drop(columns=["hs", "as_", "game_date", "season"], errors="ignore"),
        on="game_id", how="left")
    for c in ("gf_l", "ga_l", "gf_s", "ga_s", "sf", "sa", "sat_share", "sh_pct", "pp_pct",
              "pk_pct", "pp_opp", "pk_opp", "fo", "g_sv"):
        df[f"d_{c}"] = df[f"h_{c}"] - df[f"a_{c}"]
        df[f"s_{c}"] = df[f"h_{c}"] + df[f"a_{c}"]
    df["d_rate"] = df.rate_h - df.rate_a
    if not with_prices:
        return df
    ok = df.ml_home_open.notna() & df.ml_away_open.notna()
    df.loc[ok, "mkt_home"] = [novig(x, y) for x, y in zip(df.ml_home_open[ok], df.ml_away_open[ok])]
    ok = df.over_open.notna() & df.under_open.notna()
    df.loc[ok, "mkt_over"] = [novig(x, y) for x, y in zip(df.over_open[ok], df.under_open[ok])]
    ok = df.pl_home.notna() & df.pl_away.notna()
    df.loc[ok, "mkt_pl_home"] = [novig(x, y) for x, y in zip(df.pl_home[ok], df.pl_away[ok])]
    df["mkt_logit"] = np.log(df.mkt_home / (1 - df.mkt_home))
    return df


# ── models ───────────────────────────────────────────────────────────────────

def logistic():
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=2000))


def walk(df: pd.DataFrame, feats: list[str], target: str, maker) -> pd.DataFrame:
    parts = []
    use = df.dropna(subset=feats + [target])
    for test in TEST_SEASONS:
        tr, te = use[use.season < test], use[use.season == test].copy()
        if len(tr) < 500 or te.empty:
            continue
        m = maker()
        m.fit(tr[feats].values.astype(float), tr[target].values.astype(int))
        te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
        parts.append(te)
    return pd.concat(parts)


def grid(name: str, pred: pd.DataFrame, mkt_col: str, grader, edges=EDGES) -> list[dict]:
    rows = []
    p, pm = pred.p.values, pred[mkt_col].values
    for e in edges:
        a, b = p - pm >= e, pm - p >= e
        pick = a | b
        if pick.sum() < 30:
            rows.append({"model": name, "edge>=": e, "bets": int(pick.sum())})
            continue
        sub = pred[pick]
        res = grader(sub, a[pick])
        profit = res[0] if isinstance(res, tuple) else res
        clv = res[1] if isinstance(res, tuple) else None
        order = np.argsort(sub.game_date.values, kind="stable")
        half = len(order) // 2
        rows.append({"model": name, "edge>=": e, **summarise(profit, clv),
                     "early": round(float(profit[order[:half]].mean()) * 100, 1),
                     "late": round(float(profit[order[half:]].mean()) * 100, 1)})
    return rows


def scores(name: str, pred: pd.DataFrame, target: str, mkt_col: str) -> str:
    y = pred[target].values
    return (f"{name}: n={len(pred):,} model log loss {log_loss(y, pred.p):.4f} AUC "
            f"{roc_auc_score(y, pred.p):.4f} | market open {log_loss(y, pred[mkt_col]):.4f} "
            f"/ {roc_auc_score(y, pred[mkt_col]):.4f}")


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    conn = get_connection()
    try:
        df = build(conn)
    finally:
        conn.close()
    df = df[df.season.between(2019, 2023)]
    df["y_home"] = (df.hs > df.as_).astype(int)
    print(f"games 2019-2023 with inputs: {len(df):,}; with an opening moneyline: "
          f"{int(df.mkt_home.notna().sum()):,}")
    all_feats = [f for g in GROUPS.values() for f in g]

    # ── moneyline ────────────────────────────────────────────────────────────
    ml = df.dropna(subset=["mkt_home", "ml_home_close", "ml_away_close"])
    rows = []
    variants = {"ALL inputs, logistic": (all_feats, logistic),
                "ALL inputs, regularised trees": (all_feats, lambda: XGBClassifier(**TREE))}
    for gname in GROUPS:
        variants[f"  minus {gname}"] = ([f for f in all_feats if f not in GROUPS[gname]], logistic)
    variants["market open + ALL inputs, logistic"] = (all_feats + ["mkt_logit"], logistic)
    variants["market open ALONE, logistic (the bar)"] = (["mkt_logit"], logistic)
    for name, (feats, maker) in variants.items():
        pred = walk(ml, feats, "y_home", maker)
        print(scores(name, pred, "y_home", "mkt_home"))
        rows += grid(name, pred, "mkt_home", grade_ml)
    show("Moneyline, round two — bet at the OPEN when |model - no-vig open| >= edge", rows)

    # ── the favourite lean, market only, all five seasons ────────────────────
    fav_home = ml.mkt_home >= 0.5
    p_fav = np.where(fav_home, ml.mkt_home, 1 - ml.mkt_home)
    bands = [(0.50, 0.55), (0.55, 0.60), (0.60, 0.65), (0.65, 0.70), (0.70, 1.0)]
    rows = []
    for lo, hi in bands:
        m = (p_fav >= lo) & (p_fav < hi)
        sub = ml[m]
        pr, clv = grade_ml(sub, fav_home[m].values)
        rows.append({"favourite's no-vig open": f"{lo:.2f}-{hi:.2f}", **summarise(pr, clv),
                     **{f"roi_{s}": round(float(pr[(sub.season == s).values].mean()) * 100, 1)
                        for s in sorted(sub.season.unique())}})
    show("Blind favourite at the OPEN, by price band, all priced seasons", rows)

    # ── totals ───────────────────────────────────────────────────────────────
    tt = df.dropna(subset=["total_open", "mkt_over", "over_close", "under_close"]).copy()
    tt = tt[tt.hs + tt.as_ != tt.total_open]
    tt["y_over"] = (tt.hs + tt.as_ > tt.total_open).astype(int)
    rows = []
    for name, (feats, maker) in {
            "totals: log inputs + line + market, logistic": (TOTAL_FEATS, logistic),
            "totals: same, regularised trees": (TOTAL_FEATS, lambda: XGBClassifier(**TREE)),
            "totals: inputs WITHOUT the market's price": (
                [f for f in TOTAL_FEATS if f != "mkt_over"], logistic)}.items():
        pred = walk(tt, feats, "y_over", maker)
        print(scores(name, pred, "y_over", "mkt_over"))
        rows += grid(name, pred, "mkt_over", grade_total)
    show("Totals, round two", rows)

    # ── puck line ────────────────────────────────────────────────────────────
    pl = df.dropna(subset=["spread_home", "mkt_pl_home"]).copy()
    pl["y_cover"] = (pl.hs - pl.as_ + pl.spread_home > 0).astype(int)
    pl["pl_logit"] = np.log(pl.mkt_pl_home / (1 - pl.mkt_pl_home))
    rows = []
    for name, (feats, maker) in {
            "puck line: ALL inputs + the line, logistic": (all_feats + ["spread_home"], logistic),
            "puck line: market price + ALL inputs": (all_feats + ["spread_home", "pl_logit"], logistic),
            "puck line: same, regularised trees": (
                all_feats + ["spread_home", "pl_logit"], lambda: XGBClassifier(**TREE))}.items():
        pred = walk(pl, feats, "y_cover", maker)
        print(scores(name, pred, "y_cover", "mkt_pl_home"))
        rows += grid(name, pred, "mkt_pl_home", grade_pl)
    show("Puck line, round two (one archived price: no closing-line value)", rows)


if __name__ == "__main__":
    main()
