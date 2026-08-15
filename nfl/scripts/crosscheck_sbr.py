"""
Cross-check The Odds API backfill against the SportsBookReview archive
over the 2020-2021 overlap window.

Join strategy: (season, date, home_final, away_final). Team names in the SBR
archive are ambiguous and inconsistent (Fortyniners / KCChiefs / Kansas /
Tampa / Washingtom), so names are used only as a post-hoc validation of the
score-based join, never as the key.

Orientation: SBR quotes home_open_spread as a handicap (negative = home
favored). nflverse spread_line is positive = home favored. We convert SBR to
nflverse orientation throughout so every number below is comparable.
"""

import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NICK = {
    "Cardinals": "ARI", "Falcons": "ATL", "Ravens": "BAL", "Bills": "BUF",
    "Panthers": "CAR", "Bears": "CHI", "Bengals": "CIN", "Browns": "CLE",
    "Cowboys": "DAL", "Broncos": "DEN", "Lions": "DET", "Packers": "GB",
    "Texans": "HOU", "Colts": "IND", "Jaguars": "JAX",
    "Chiefs": "KC", "KCChiefs": "KC", "Kansas": "KC",
    "Raiders": "LV", "LVRaiders": "LV",
    "Chargers": "LAC", "Rams": "LA", "Dolphins": "MIA", "Vikings": "MIN",
    "Patriots": "NE", "Saints": "NO", "Giants": "NYG", "Jets": "NYJ",
    "Eagles": "PHI", "Steelers": "PIT",
    "Fortyniners": "SF", "49ers": "SF",
    "Seahawks": "SEA", "Buccaneers": "TB", "Tampa": "TB", "Texans2": "HOU",
    "Titans": "TEN",
    "Commanders": "WAS", "Washingtom": "WAS", "Washington": "WAS",
    "Redskins": "WAS", "FootballTeam": "WAS",
}


def main():
    sbr = pd.DataFrame(json.load(open("data/raw/sbr_nfl.json")))
    sbr = sbr[sbr.season.isin([2020, 2021])].copy()
    n_raw = len(sbr)

    for c in ["home_final", "away_final", "home_open_spread", "home_close_spread",
              "open_over_under", "close_over_under", "date"]:
        sbr[c] = pd.to_numeric(sbr[c], errors="coerce")

    # drop structurally corrupt rows (the garbled Super Bowl record)
    corrupt = sbr.home_team.map(lambda x: not isinstance(x, str)) | \
              sbr.away_team.map(lambda x: not isinstance(x, str)) | \
              sbr.date.isna()
    print(f"SBR 2020-21 rows: {n_raw} | structurally corrupt dropped: {corrupt.sum()}")
    sbr = sbr[~corrupt].copy()

    sbr["gameday"] = pd.to_datetime(
        sbr.date.astype(int).astype(str), format="%Y%m%d"
    ).dt.strftime("%Y-%m-%d")
    sbr["sbr_home"] = sbr.home_team.map(NICK)
    sbr["sbr_away"] = sbr.away_team.map(NICK)
    unmapped = set(sbr[sbr.sbr_home.isna()].home_team) | set(sbr[sbr.sbr_away.isna()].away_team)
    print(f"unmapped nicknames: {unmapped or 'none'}")

    # nflverse orientation: positive = home favored
    sbr["sbr_open_spread"] = -sbr.home_open_spread
    sbr["sbr_close_spread"] = -sbr.home_close_spread
    sbr["sbr_open_total"] = sbr.open_over_under
    sbr["sbr_close_total"] = sbr.close_over_under

    g = pd.read_csv("data/raw/games.csv")
    g = g[g.season.isin([2020, 2021])].copy()

    # ---- score+date join (name-independent) ----
    key = ["season", "gameday", "home_score", "away_score"]
    sbr_j = sbr.rename(columns={"home_final": "home_score", "away_final": "away_score"})
    m = g.merge(sbr_j, on=key, how="inner", suffixes=("", "_sbr"))
    dupes = m.game_id.duplicated().sum()
    m = m.drop_duplicates("game_id")
    print(f"\nscore+date join: {len(m)} of {len(g)} nflverse games matched "
          f"({len(m)/len(g):.1%}); ambiguous dupes dropped: {dupes}")

    agree = (m.home_team == m.sbr_home) & (m.away_team == m.sbr_away)
    print(f"join validation: nickname agreement on matched rows = {agree.mean():.1%} "
          f"({(~agree).sum()} disagreements)")
    if (~agree).sum():
        print(m.loc[~agree, ["game_id", "home_team", "sbr_home", "away_team", "sbr_away"]].head(10).to_string(index=False))

    # ---- column-swap defect scan ----
    print("\n=== SBR column integrity ===")
    for c in ["sbr_open_spread", "sbr_close_spread", "sbr_open_total", "sbr_close_total"]:
        v = m[c]
        print(f"{c:20s} null={v.isna().sum():3d} zeros={int((v==0).sum()):3d} "
              f"min={v.min():7.1f} max={v.max():7.1f}")
    swap = (m.sbr_open_spread.abs() > 25) | (m.sbr_open_total < 25)
    print(f"rows with spread/total magnitude swap signature: {int(swap.sum())}")

    # ---- comparison vs our backfill ----
    odds = pd.read_parquet("data/processed/odds_by_game_book.parquet")
    pin = odds[odds.book == "pinnacle"][["game_id", "bt_spread", "cl_spread", "bt_total", "cl_total"]]
    dk = odds[odds.book == "draftkings"][["game_id", "bt_spread", "bt_total"]].rename(
        columns={"bt_spread": "dk_bt_spread", "bt_total": "dk_bt_total"})
    m = m.merge(pin, on="game_id", how="left").merge(dk, on="game_id", how="left")

    def cmp(a, b, label):
        d = (m[a] - m[b]).dropna()
        if len(d) == 0:
            print(f"{label:44s} n=0")
            return
        print(f"{label:44s} n={len(d):4d} mean={d.mean():+6.3f} sd={d.std():5.3f} "
              f"med={d.median():+5.2f} |d|<=0.5={np.mean(d.abs()<=0.5):5.1%} "
              f"|d|<=1={np.mean(d.abs()<=1.0):5.1%} r={m[a].corr(m[b]):.4f}")

    print("\n=== SPREADS (nflverse orientation, positive = home favored) ===")
    cmp("sbr_close_spread", "spread_line", "SBR close vs nflverse close")
    cmp("cl_spread", "spread_line", "Pinnacle close vs nflverse close")
    cmp("cl_spread", "sbr_close_spread", "Pinnacle close vs SBR close")
    cmp("bt_spread", "sbr_open_spread", "Pinnacle Tue bet-time vs SBR OPEN")
    cmp("dk_bt_spread", "sbr_open_spread", "DK Tue bet-time vs SBR OPEN")
    cmp("sbr_close_spread", "sbr_open_spread", "SBR close vs SBR open (true open-close move)")
    cmp("cl_spread", "bt_spread", "Pinnacle close vs Pinnacle Tue (our move)")

    print("\n=== TOTALS ===")
    cmp("sbr_close_total", "total_line", "SBR close vs nflverse close")
    cmp("bt_total", "sbr_open_total", "Pinnacle Tue bet-time vs SBR OPEN")
    cmp("sbr_close_total", "sbr_open_total", "SBR close vs SBR open")

    m.to_parquet("data/processed/sbr_crosscheck.parquet", index=False)


if __name__ == "__main__":
    main()
