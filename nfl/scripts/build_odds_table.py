"""
Consolidate raw snapshots into one per-game odds table.

Sign conventions (normalized here, once):
  * spread_home  = the home-team handicap as quoted (negative = home favored)
  * We convert to nflverse orientation: spread_line = -spread_home
    so positive = home favored = expected home margin. This matches
    games.csv spread_line and the model target.
"""

import os
import sys

import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BOOKS_KEEP = ["pinnacle", "draftkings", "fanduel", "betmgm", "caesars", "bovada"]


def load_games() -> pd.DataFrame:
    g = pd.read_csv("data/raw/games.csv")
    g = g[(g.season >= 2020) & (g.season <= 2025)].copy()
    dt = pd.to_datetime(g.gameday + " " + g.gametime)
    g["kick_utc"] = (
        dt.dt.tz_localize(
            ZoneInfo("America/New_York"), ambiguous=True, nonexistent="shift_forward"
        ).dt.tz_convert("UTC")
    )
    return g


def wide_spreads(df: pd.DataFrame, value_prefix: str) -> pd.DataFrame:
    """Pivot spread rows to one row per (game_id, book) with home handicap + prices."""
    sp = df[df.market == "spreads"]
    home = sp[sp.side == "home"][["game_id", "book", "point", "price"]].rename(
        columns={"point": "pt_home", "price": "px_home"}
    )
    away = sp[sp.side == "away"][["game_id", "book", "point", "price"]].rename(
        columns={"point": "pt_away", "price": "px_away"}
    )
    m = home.merge(away, on=["game_id", "book"], how="outer")
    # nflverse orientation: positive = home favored
    m[f"{value_prefix}_spread"] = -m.pt_home
    m[f"{value_prefix}_spread_px_home"] = m.px_home
    m[f"{value_prefix}_spread_px_away"] = m.px_away
    return m[
        [
            "game_id", "book",
            f"{value_prefix}_spread",
            f"{value_prefix}_spread_px_home",
            f"{value_prefix}_spread_px_away",
        ]
    ]


def wide_totals(df: pd.DataFrame, value_prefix: str) -> pd.DataFrame:
    tt = df[df.market == "totals"]
    over = tt[tt.side == "Over"][["game_id", "book", "point", "price"]].rename(
        columns={"point": f"{value_prefix}_total", "price": f"{value_prefix}_total_px_over"}
    )
    under = tt[tt.side == "Under"][["game_id", "book", "price"]].rename(
        columns={"price": f"{value_prefix}_total_px_under"}
    )
    return over.merge(under, on=["game_id", "book"], how="outer")


def main():
    g = load_games()
    gk = g[["game_id", "season", "week", "home_team", "away_team", "kick_utc"]].rename(
        columns={"home_team": "home", "away_team": "away"}
    )

    # ---------- bet-time ----------
    bt = pd.read_parquet("data/raw/bettime_matched.parquet")
    bt = bt[bt.book.isin(BOOKS_KEEP)]
    bt_sp = wide_spreads(bt, "bt")
    bt_tt = wide_totals(bt, "bt")
    bett = bt_sp.merge(bt_tt, on=["game_id", "book"], how="outer")

    # ---------- closing ----------
    close_frames = []
    for path, mkt in [
        ("data/raw/closing_raw_spreads_2020_2025.parquet", "spreads"),
        ("data/raw/closing_raw_totals_2023_2025.parquet", "totals"),
    ]:
        if not os.path.exists(path):
            continue
        c = pd.read_parquet(path)
        c = c[c.book.isin(BOOKS_KEEP)]
        c["commence_time"] = pd.to_datetime(c.commence_time, utc=True, format="mixed")
        c["snap_req_utc"] = pd.to_datetime(c.snap_req_utc, utc=True)
        c = c.merge(gk, on=["home", "away"], how="inner")
        # event must be the same game: kickoff within 6h of quoted commence_time
        c = c[((c.commence_time - c.kick_utc) / pd.Timedelta(hours=1)).abs() <= 6]
        # closing quote = latest snapshot strictly before that game's kickoff
        c = c[c.snap_req_utc < c.kick_utc]
        c = c.sort_values("snap_req_utc").groupby(
            ["game_id", "book", "market", "side"], as_index=False
        ).last()
        c["_lead_min"] = (c.kick_utc - c.snap_req_utc) / pd.Timedelta(minutes=1)
        close_frames.append(c)

    cl = pd.concat(close_frames, ignore_index=True)
    lead = cl.groupby("game_id")._lead_min.min()
    print("closing snapshot lead time before kickoff (minutes):")
    print(lead.describe().round(1))

    cl_sp = wide_spreads(cl, "cl")
    cl_tt = wide_totals(cl, "cl")
    clos = cl_sp.merge(cl_tt, on=["game_id", "book"], how="outer")

    odds = bett.merge(clos, on=["game_id", "book"], how="outer")
    odds = odds.merge(
        g[["game_id", "season", "week", "game_type", "spread_line", "total_line",
           "result", "total", "home_score", "away_score"]],
        on="game_id", how="left",
    )
    odds.to_parquet("data/processed/odds_by_game_book.parquet", index=False)

    print(f"\nrows: {len(odds):,} | games: {odds.game_id.nunique()}")
    for b in BOOKS_KEEP:
        s = odds[odds.book == b]
        print(
            f"{b:12s} bt_spread {s.bt_spread.notna().sum():4d} | "
            f"cl_spread {s.cl_spread.notna().sum():4d} | "
            f"bt_total {s.bt_total.notna().sum():4d} | "
            f"cl_total {s.cl_total.notna().sum():4d}"
        )

    # sanity: Pinnacle closing spread vs nflverse consensus closing spread
    p = odds[(odds.book == "pinnacle")].dropna(subset=["cl_spread", "spread_line"])
    d = p.cl_spread - p.spread_line
    print(f"\nPinnacle close vs nflverse spread_line: n={len(p)} "
          f"mean_diff={d.mean():.3f} sd={d.std():.3f} "
          f"within_0.5={np.mean(d.abs() <= 0.5):.1%} corr={p.cl_spread.corr(p.spread_line):.4f}")


if __name__ == "__main__":
    os.makedirs("data/processed", exist_ok=True)
    main()
