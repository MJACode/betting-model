"""
Per-game, per-book odds table across ALL books, prices retained.

Supersedes the 6-book version. The edge hypothesis is that value lives in
cross-book dispersion of both the line and the price, so restricting the
book universe throws away exactly the signal we want.
"""

import os
import sys

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_games():
    g = pd.read_csv("data/raw/games.csv")
    g = g[(g.season >= 2020) & (g.season <= 2025)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime)
    g["kick_utc"] = dt.dt.tz_localize(
        ZoneInfo("America/New_York"), ambiguous=True, nonexistent="shift_forward"
    ).dt.tz_convert("UTC")
    return g


def pivot_spreads(df, pfx):
    sp = df[df.market == "spreads"]
    h = sp[sp.side == "home"][["game_id", "book", "point", "price"]].rename(
        columns={"point": "pt_h", "price": f"{pfx}_px_home"})
    a = sp[sp.side == "away"][["game_id", "book", "point", "price"]].rename(
        columns={"point": "pt_a", "price": f"{pfx}_px_away"})
    m = h.merge(a, on=["game_id", "book"], how="outer")
    m[f"{pfx}_spread"] = -m.pt_h          # nflverse orientation
    return m[["game_id", "book", f"{pfx}_spread", f"{pfx}_px_home", f"{pfx}_px_away"]]


def pivot_totals(df, pfx):
    tt = df[df.market == "totals"]
    o = tt[tt.side == "Over"][["game_id", "book", "point", "price"]].rename(
        columns={"point": f"{pfx}_total", "price": f"{pfx}_px_over"})
    u = tt[tt.side == "Under"][["game_id", "book", "price"]].rename(
        columns={"price": f"{pfx}_px_under"})
    return o.merge(u, on=["game_id", "book"], how="outer")


def main():
    g = load_games()
    gk = g[["game_id", "season", "week", "home_team", "away_team", "kick_utc"]].rename(
        columns={"home_team": "home", "away_team": "away"})

    bt = pd.read_parquet("data/raw/bettime_matched.parquet")
    bett = pivot_spreads(bt, "bt").merge(pivot_totals(bt, "bt"),
                                         on=["game_id", "book"], how="outer")

    frames = []
    for path in ["data/raw/closing_raw_spreads_2020_2025.parquet",
                 "data/raw/closing_raw_totals_2023_2025.parquet"]:
        if not os.path.exists(path):
            continue
        c = pd.read_parquet(path)
        c["commence_time"] = pd.to_datetime(c.commence_time, utc=True, format="mixed")
        c["snap_req_utc"] = pd.to_datetime(c.snap_req_utc, utc=True)
        c = c.merge(gk, on=["home", "away"], how="inner")
        c = c[((c.commence_time - c.kick_utc) / pd.Timedelta(hours=1)).abs() <= 6]
        c = c[c.snap_req_utc < c.kick_utc]
        c = c.sort_values("snap_req_utc").groupby(
            ["game_id", "book", "market", "side"], as_index=False).last()
        frames.append(c)
    cl = pd.concat(frames, ignore_index=True)
    clos = pivot_spreads(cl, "cl").merge(pivot_totals(cl, "cl"),
                                         on=["game_id", "book"], how="outer")

    odds = bett.merge(clos, on=["game_id", "book"], how="outer")
    odds = odds.merge(
        g[["game_id", "season", "week", "game_type", "spread_line", "total_line",
           "home_score", "away_score"]], on="game_id", how="left")
    odds["margin"] = odds.home_score - odds.away_score
    odds["total_pts"] = odds.home_score + odds.away_score

    os.makedirs("data/processed", exist_ok=True)
    odds.to_parquet("data/processed/odds_all_books.parquet", index=False)

    print(f"rows {len(odds):,} | games {odds.game_id.nunique()} | books {odds.book.nunique()}")
    bt_ct = odds.dropna(subset=["bt_spread"]).groupby("game_id").size()
    print(f"books quoting bet-time spread per game: "
          f"median {bt_ct.median():.0f}, p10 {bt_ct.quantile(.1):.0f}, max {bt_ct.max():.0f}")
    print(f"games with >=5 bet-time books: {(bt_ct >= 5).mean():.1%}")

    # dispersion: how much do books disagree at bet time?
    d = odds.dropna(subset=["bt_spread"]).groupby("game_id").bt_spread.agg(["min", "max", "std"])
    d["range"] = d["max"] - d["min"]
    print(f"\nbet-time cross-book spread range: median {d.range.median():.2f}, "
          f"mean {d.range.mean():.2f}, p90 {d.range.quantile(.9):.2f}")
    print(f"games with range >= 1.0 pt: {(d.range >= 1.0).mean():.1%}")


if __name__ == "__main__":
    main()
