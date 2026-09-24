"""Round three: the frozen game-line candidates on seasons they have never seen.

Round two (docs/nhl_market_lab.md) froze two candidates on the 2018-19 ->
2022-23 archive: the regularised logistic moneyline model on the per-game-log
inputs (bet at the open when |model - no-vig open| >= 0.04..0.08) and the same
model on the puck line (+ the line as an input, 0.06..0.08). Totals lost. The
verdict was "test on 2023-24 -> 2025-26 when those prices arrive". This is
that test, on the feed's bought game lines (`odds.source =
'odds_api_historical'`: DraftKings, Pinnacle and eight books; the 16:00Z
snapshot on game day and one at the start hour; scripts/nhl_odds_history_backfill.py).

WHAT IS HELD FIXED. The inputs (`nhl_market_lab2.build`), the model
(`logistic`: standardised, C=0.05), the feature list, the edge cuts. For test
season S the model is fit on every season before S that has inputs (round two
fit on the priced games of those seasons; the targets need no price, so this
uses all of them). Nothing is tuned here.

WHAT DIFFERS. The archive's "open" was an unnamed consensus; here the decision
is made against a NAMED book's first pre-game quote of the day and the bet is
graded at THAT book's price, so this is closer to what a bettor gets. Two
references are reported: DraftKings (the book we bet at) and Pinnacle (the
sharp open). CLV is against Pinnacle's LAST pre-game quote, no-vig.

    python -m scripts.nhl_market_lab3 --seasons 2023 2024 2025 2026
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

sys.path.insert(0, ".")

from data.db import get_connection                                   # noqa: E402
from scripts.nhl_market_lab import (EDGES, novig, summarise,          # noqa: E402
                                    win_per_unit)
from scripts.nhl_market_lab2 import GROUPS, build, logistic          # noqa: E402

FEED = "odds_api_historical"
BOOKS = ("draftkings", "pinnacle")


def _ts(v) -> datetime | None:
    if v is None:
        return None
    return datetime.fromisoformat(str(v).replace("Z", "+00:00")).astimezone(timezone.utc)


def feed_prices(conn, seasons: list[int]) -> pd.DataFrame:
    """One row per game: each book's FIRST and LAST pre-game quote per market."""
    games = conn.execute(
        "SELECT game_id, commence_time FROM games WHERE sport = 'NHL' AND season = ANY(%s) "
        "AND home_score IS NOT NULL AND commence_time IS NOT NULL", (seasons,)).fetchall()
    start = {g: _ts(t) for g, t in games}
    ids = list(start)
    rows = []
    for i in range(0, len(ids), 300):                # by game id: the table is indexed on it
        rows += conn.execute(
            "SELECT game_id, bookmaker, market, snapshot_at, home_price, away_price, "
            "spread_home, total_line, over_price, under_price FROM odds "
            "WHERE game_id = ANY(%s) AND source = %s AND snapshot_type = 'open' "
            "AND bookmaker = ANY(%s) AND market IN ('h2h', 'spreads', 'totals')",
            (ids[i:i + 300], FEED, list(BOOKS))).fetchall()
    px = pd.DataFrame(rows, columns=["game_id", "book", "market", "snap", "hp", "ap",
                                     "sh", "tl", "op", "up"])
    px["snap"] = px.snap.map(_ts)
    px = px[[s <= start[g] for g, s in zip(px.game_id, px.snap)]]       # pre-game only
    px = px.sort_values(["game_id", "book", "market", "snap"])
    out: dict[str, dict] = {}
    for (gid, book, mk), g in px.groupby(["game_id", "book", "market"], sort=False):
        d = out.setdefault(gid, {"game_id": gid})
        b = book[:3]                                                     # dra / pin
        first, last = g.iloc[0], g.iloc[-1]
        if mk == "h2h":
            d[f"{b}_ml_home_open"], d[f"{b}_ml_away_open"] = first.hp, first.ap
            d[f"{b}_ml_home_close"], d[f"{b}_ml_away_close"] = last.hp, last.ap
        elif mk == "spreads":
            d[f"{b}_spread"], d[f"{b}_pl_home"], d[f"{b}_pl_away"] = first.sh, first.hp, first.ap
        elif mk == "totals":
            d[f"{b}_total_open"], d[f"{b}_over_open"], d[f"{b}_under_open"] = first.tl, first.op, first.up
            d[f"{b}_total_close"], d[f"{b}_over_close"], d[f"{b}_under_close"] = last.tl, last.op, last.up
    f = pd.DataFrame(out.values())
    for c in f.columns:
        if c != "game_id":
            f[c] = pd.to_numeric(f[c], errors="coerce")
    return f


def _nv(df, a, b):
    ok = df[a].notna() & df[b].notna()
    v = pd.Series(np.nan, index=df.index)
    v[ok] = [novig(x, y) for x, y in zip(df.loc[ok, a], df.loc[ok, b])]
    return v


def fit_predict(df: pd.DataFrame, feats: list[str], target: str, test: int) -> pd.DataFrame:
    use = df.dropna(subset=feats + [target])
    tr, te = use[use.season < test], use[use.season == test].copy()
    m = logistic().fit(tr[feats].values.astype(float), tr[target].values.astype(int))
    te["p"] = m.predict_proba(te[feats].values.astype(float))[:, 1]
    te["n_train"] = len(tr)
    return te


def ml_grid(name: str, te: pd.DataFrame, ref: str) -> list[dict]:
    """Decide against `ref`'s no-vig open, bet at DraftKings' open price."""
    te = te.dropna(subset=[f"{ref}_mkt_home", "dra_ml_home_open", "dra_ml_away_open"])
    rows = []
    for e in EDGES:
        home, away = te.p - te[f"{ref}_mkt_home"] >= e, te[f"{ref}_mkt_home"] - te.p >= e
        pick = home | away
        if pick.sum() < 30:
            rows.append({"model": name, "edge>=": e, "bets": int(pick.sum())})
            continue
        s, h = te[pick], home[pick].values
        price = np.where(h, s.dra_ml_home_open, s.dra_ml_away_open).astype(float)
        won = np.where(h, s.hs > s.as_, s.as_ > s.hs)
        profit = np.where(won, [win_per_unit(p) for p in price], -1.0)
        clv = np.where(h, s.pin_close_home - s.pin_mkt_home, s.pin_mkt_home - s.pin_close_home)
        order = np.argsort(s.game_date.values, kind="stable")
        half = len(order) // 2
        rows.append({"model": name, "edge>=": e, **summarise(profit, clv),
                     "fav share": round(float(np.mean(np.where(h, s.dra_mkt_home, 1 - s.dra_mkt_home) > 0.5)), 2),
                     "early": round(float(profit[order[:half]].mean()) * 100, 1),
                     "late": round(float(profit[order[half:]].mean()) * 100, 1)})
    return rows


def pl_grid(name: str, te: pd.DataFrame, ref: str) -> list[dict]:
    te = te.dropna(subset=[f"{ref}_mkt_pl_home", "dra_pl_home", "dra_pl_away", "dra_spread"])
    rows = []
    for e in EDGES:
        home, away = te.p - te[f"{ref}_mkt_pl_home"] >= e, te[f"{ref}_mkt_pl_home"] - te.p >= e
        pick = home | away
        if pick.sum() < 30:
            rows.append({"model": name, "edge>=": e, "bets": int(pick.sum())})
            continue
        s, h = te[pick], home[pick].values
        margin = s.hs - s.as_ + s.dra_spread
        price = np.where(h, s.dra_pl_home, s.dra_pl_away).astype(float)
        won = np.where(h, margin > 0, margin < 0)
        profit = np.where(won, [win_per_unit(p) for p in price], -1.0)
        order = np.argsort(s.game_date.values, kind="stable")
        half = len(order) // 2
        rows.append({"model": name, "edge>=": e, **summarise(profit),
                     "early": round(float(profit[order[:half]].mean()) * 100, 1),
                     "late": round(float(profit[order[half:]].mean()) * 100, 1)})
    return rows


def tot_grid(name: str, te: pd.DataFrame, ref: str) -> list[dict]:
    te = te.dropna(subset=[f"{ref}_mkt_over", "dra_total_open", "dra_over_open", "dra_under_open"])
    te = te[te.hs + te.as_ != te.dra_total_open]
    rows = []
    for e in EDGES:
        over, under = te.p - te[f"{ref}_mkt_over"] >= e, te[f"{ref}_mkt_over"] - te.p >= e
        pick = over | under
        if pick.sum() < 30:
            rows.append({"model": name, "edge>=": e, "bets": int(pick.sum())})
            continue
        s, o = te[pick], over[pick].values
        tot = s.hs + s.as_
        price = np.where(o, s.dra_over_open, s.dra_under_open).astype(float)
        won = np.where(o, tot > s.dra_total_open, tot < s.dra_total_open)
        profit = np.where(won, [win_per_unit(p) for p in price], -1.0)
        rows.append({"model": name, "edge>=": e, **summarise(profit),
                     "over share": round(float(o.mean()), 2)})
    return rows


def show(title: str, rows: list[dict]) -> None:
    print(f"\n### {title}\n")
    pd.set_option("display.width", 220)
    print(pd.DataFrame(rows).to_string(index=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seasons", nargs="+", type=int, default=[2024, 2025, 2026])
    a = ap.parse_args()
    conn = get_connection()
    try:
        df = build(conn, with_prices=False)
        # every bought season, not just the test ones: the puck-line and totals
        # models take the line as an input, so their TRAINING rows need one too
        px = feed_prices(conn, list(range(2021, max(a.seasons) + 1)))
    finally:
        conn.close()
    df = df.merge(px, on="game_id", how="left")
    df["y_home"] = (df.hs > df.as_).astype(int)
    for b in ("dra", "pin"):
        df[f"{b}_mkt_home"] = _nv(df, f"{b}_ml_home_open", f"{b}_ml_away_open")
        df[f"{b}_mkt_pl_home"] = _nv(df, f"{b}_pl_home", f"{b}_pl_away")
        df[f"{b}_mkt_over"] = _nv(df, f"{b}_over_open", f"{b}_under_open")
    df["pin_close_home"] = _nv(df, "pin_ml_home_close", "pin_ml_away_close")
    all_feats = [f for g in GROUPS.values() for f in g]

    for test in a.seasons:
        priced = df[(df.season == test) & df.dra_mkt_home.notna()]
        print(f"\n===== test season {test} ({test - 1}-{str(test)[2:]}): {int((df.season == test).sum()):,} "
              f"games with inputs, {len(priced):,} with a DraftKings open, "
              f"{int(priced.pin_mkt_home.notna().sum()):,} with a Pinnacle open =====")
        if priced.empty:
            print("no feed prices stored for this season yet")
            continue
        te = fit_predict(df, all_feats, "y_home", test)
        print(f"moneyline, ALL inputs, logistic: fit on {int(te.n_train.iloc[0]):,} games")
        rows = []
        for ref, label in (("dra", "vs DraftKings open"), ("pin", "vs Pinnacle open")):
            rows += ml_grid(f"moneyline {label}", te, ref)
        # the bar: DraftKings' own open against Pinnacle's, market only
        bar = te.dropna(subset=["pin_mkt_home"]).copy()
        bar["p"] = bar.pin_mkt_home
        rows += ml_grid("Pinnacle open vs DraftKings open (no model)", bar, "dra")
        show(f"Moneyline {test}: bet at the DraftKings OPEN price", rows)

        pl = df.dropna(subset=["dra_spread"]).copy()
        pl["spread_home"] = pl.dra_spread
        pl["y_cover"] = (pl.hs - pl.as_ + pl.spread_home > 0).astype(int)
        te = fit_predict(pl, all_feats + ["spread_home"], "y_cover", test)
        rows = []
        for ref, label in (("dra", "vs DraftKings open"), ("pin", "vs Pinnacle open")):
            rows += pl_grid(f"puck line {label}", te, ref)
        show(f"Puck line {test}: bet at the DraftKings OPEN price", rows)

        tt = df.dropna(subset=["dra_total_open"]).copy()
        tt = tt[tt.hs + tt.as_ != tt.dra_total_open]
        tt["total_open"], tt["mkt_over"] = tt.dra_total_open, tt.dra_mkt_over
        tt["y_over"] = (tt.hs + tt.as_ > tt.total_open).astype(int)
        feats = ["s_gf_l", "s_ga_l", "s_gf_s", "s_sf", "s_sa", "s_pp_opp", "s_pk_opp",
                 "h_g_sv", "a_g_sv", "h_b2b", "a_b2b", "total_open"]
        te = fit_predict(tt, feats, "y_over", test)
        show(f"Totals {test}: inputs without the market's price, bet at the DraftKings OPEN",
             tot_grid("totals vs DraftKings open", te, "dra"))


if __name__ == "__main__":
    main()
