"""
NCAAF snapshot look-ahead audit.

Verifies the invariant that `ncaaf_team_stats` snapshots must satisfy:

    a snapshot's games_played must never exceed the number of games the team
    had actually played before that snapshot's as_of_date

Violations mean the snapshot contains information from the future, which
`features/ncaaf_feature_engine.py` then feeds into training via
`as_of_date <= game_date`.

History: on 2026-08-25 this reported 32.7% of 40,194 snapshots (2014-2025)
as look-ahead, stable at 30-36% in every season. Root cause was CFBD
restarting week numbering for the postseason -- every bowl/playoff game is
season_type='postseason', week=1 -- while the snapshot builder filtered with
`week < wk`, so the entire postseason leaked into every in-season snapshot
from week 2 onward. Ohio State's 2024-09-04 snapshot reported games_played=5:
their Aug 31 opener plus four playoff games from that December and January.

Run after any change to the snapshot builder:
    python -m scripts.ncaaf_search.audit_snapshots
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def audit(seasons: list[int] | None = None, conn=None) -> pd.DataFrame:
    from data.db import get_connection

    owned = conn is None
    conn = conn or get_connection()
    try:
        where = ""
        params: dict = {}
        if seasons:
            where = "AND season = ANY(%(s)s)"
            params["s"] = list(seasons)
        st = pd.DataFrame(conn.execute(f"""
            SELECT team, season, as_of_date, games_played
            FROM ncaaf_team_stats
            WHERE games_played IS NOT NULL {where}
        """, params).fetchall(), columns=["team", "season", "as_of", "gp"])
        gm = pd.DataFrame(conn.execute(f"""
            SELECT season, game_date, home_team, away_team
            FROM games
            WHERE sport = 'NCAAF' AND home_score IS NOT NULL
              {where.replace('season', 'season')}
        """, params).fetchall(),
            columns=["season", "date", "home_team", "away_team"])
    finally:
        if owned:
            conn.close()

    if st.empty or gm.empty:
        return pd.DataFrame()

    st["as_of"] = pd.to_datetime(st["as_of"])
    st["gp"] = pd.to_numeric(st["gp"], errors="coerce")
    gm["date"] = pd.to_datetime(gm["date"])

    long = pd.concat([
        gm[["season", "date", "home_team"]].rename(columns={"home_team": "team"}),
        gm[["season", "date", "away_team"]].rename(columns={"away_team": "team"}),
    ], ignore_index=True)
    idx = long.groupby(["season", "team"])["date"].apply(
        lambda s: np.sort(s.values)).to_dict()

    st["actual_before"] = [
        int(np.searchsorted(idx[(r.season, r.team)], np.datetime64(r.as_of)))
        if (r.season, r.team) in idx else np.nan
        for r in st.itertuples()
    ]
    st = st.dropna(subset=["actual_before"])
    st["offset"] = st["gp"] - st["actual_before"]
    st["ahead"] = st["offset"] > 0
    return st


def main() -> int:
    st = audit()
    if st.empty:
        print("no snapshots found")
        return 1

    rate = float(st["ahead"].mean())
    print("=" * 70)
    print("NCAAF SNAPSHOT LOOK-AHEAD AUDIT")
    print("invariant: snapshot games_played <= games played before as_of_date")
    print("=" * 70)
    print(st.groupby("season")["ahead"].agg(["mean", "size"]).round(4).to_string())
    print(f"\noverall look-ahead rate: {rate:.4f} of {len(st)} snapshots")
    print("\noffset distribution (snapshot gp minus true prior games):")
    print(st["offset"].value_counts().sort_index().head(12).to_string())

    worst = st[st["ahead"]].nlargest(5, "offset")[
        ["team", "season", "as_of", "gp", "actual_before", "offset"]]
    if len(worst):
        print("\nworst offenders:")
        print(worst.to_string(index=False))

    print()
    if rate < 0.005:
        print("PASS — snapshots are honest.")
        return 0
    print(f"FAIL — {rate:.1%} of snapshots contain future information.")
    print("Re-run: python -m data.ingestors.cfbd_ingestor --season <year>")
    return 1


if __name__ == "__main__":
    sys.exit(main())
