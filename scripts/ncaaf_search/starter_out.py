"""
NCAAF search -- does the market under-adjust when the STARTING QB is out?

WHAT THIS MEASURES, AND WHAT IT CANNOT
--------------------------------------
This is the perfect-information UPPER BOUND for the availability-report spike
approved by Matt on 2026-09-07. The QB harness (`qb.py`) tested CONTINUITY --
what a bettor knows from completed games -- and found nothing. The version
that could matter, "the established starter is OUT this week", was untestable
because the project had no availability feed. Conference availability reports
now exist (SEC, Big Ten, Big 12, ACC and four G5 leagues publish them, and
SportsDataIO monitors those wires), so a feed can be bought.

Before buying one: if the market already prices a starter's absence fully,
no feed helps. So this script asks the question with HINDSIGHT -- the starter
is known absent because the box score has no row for him -- and grades the
closing line. That is deliberately leaky as a MODEL, and that is the point:

    * A NULL here is decisive. If betting for or against a team at the close
      is breakeven even when we KNOW the starter sat, no availability feed can
      make it profitable, and there is nothing to buy.
    * A POSITIVE here is an upper bound, not an edge estimate. "Absent from
      the box score" mixes announced absences the market priced with
      game-time decisions it did not; a real feed only ever sees the first
      group. The size of the effect here is the MOST a feed could deliver.

Nothing in this file is scoreable. `qb.py`'s leak discipline still governs
production: only a genuine pre-kickoff feed could make a "starter out" feature
legitimate.

DEFINITIONS -- fixed before the numbers were looked at (house rule)
----------------------------------------------------------------
    established starter, team T entering game G:
        the passer who was `is_primary` in at least 2 of T's last 3 completed
        SAME-SEASON games; with exactly 2 prior games, primary in both. Fewer
        than 2 prior same-season games -> no starter defined, game excluded.
        `is_primary` is "most attempts", which a blowout hands to a backup, so
        a single prior game is not evidence of who starts.
    starter out:
        that passer has NO row at all in game G (zero attempts). A starter who
        played but was not primary (benched, hurt in-game) is a different
        event and is EXCLUDED from both arms, not counted as "in".
    sample:
        one row per TEAM-game where a starter is defined. A game where BOTH
        teams' starters are out is excluded (the two effects cancel and it
        cannot be graded as one bet).
    grading:
        at the CLOSING line from `dataset.build_label_set` (Bovada-priority,
        pushes excluded) -- the best proxy for "after the market absorbed the
        news", and the only line that answers whether anything is LEFT to
        bet. Seasons 2021-2025 (the portal era, and the seasons the QB log
        covers with a same-season prior).
    arms:
        FADE  -- bet AGAINST the team whose starter is out, at the close
        BACK  -- bet FOR that team (the market over-reacted)
        UNDER -- the game total, under
        Per the opener harness's rule, a signal that shows up in BOTH
        directions is a red flag, not a doubling.
    verdict bar:
        Wilson 95% CI vs 0.5238 (breakeven at -110), per season, and a
        TIME SPLIT at the sample's median date that must hold in both halves.

POWER, stated before the result
-------------------------------
About 700 team-games qualify across 2021-2025. At 55% the Wilson interval
over 700 bets is roughly [0.513, 0.587]; each half of the time split is
wider. A null here means "no edge above ~4pp is detectable", not "no edge".

Run:
    python -m scripts.ncaaf_search.starter_out
    python -m scripts.ncaaf_search.starter_out --seasons 2021 2022 2023 2024 2025
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

BREAKEVEN = 0.5238
SEASONS = [2021, 2022, 2023, 2024, 2025]
LOOKBACK = 3          # completed same-season games that define the starter
MIN_PRIOR = 2         # fewer prior games -> no starter defined


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def load_qb_log(conn, seasons: list[int]) -> pd.DataFrame:
    ph = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        SELECT game_id, team, season, game_date, player_id, is_primary, attempts
        FROM ncaaf_qb_game
        WHERE season IN ({ph})
    """, seasons).fetchall()
    return pd.DataFrame(rows, columns=["game_id", "team", "season", "game_date",
                                       "player_id", "is_primary", "attempts"])


def starter_status(qb: pd.DataFrame) -> pd.DataFrame:
    """
    One row per (season, team, game): the established starter entering the
    game (or None) and whether he was OUT (no row) / PLAYED / DEMOTED.
    """
    qb = qb.sort_values(["season", "team", "game_date", "game_id"])
    out = []
    for (season, team), g in qb.groupby(["season", "team"], sort=False):
        games = (g.groupby(["game_date", "game_id"], sort=True))
        history: list[tuple[str, set]] = []   # (primary, players) per game
        for (gdate, gid), rows in games:
            prim = rows.loc[rows["is_primary"] == 1, "player_id"]
            primary = str(prim.iloc[0]) if len(prim) else None
            played = set(rows["player_id"].astype(str))

            starter = None
            if len(history) >= MIN_PRIOR:
                recent = [p for p, _ in history[-LOOKBACK:]]
                need = 2 if len(recent) >= 2 else 1
                counts = pd.Series([p for p in recent if p]).value_counts()
                if len(counts) and counts.iloc[0] >= need:
                    starter = str(counts.index[0])

            status = None
            if starter is not None:
                if starter not in played:
                    status = "OUT"
                elif primary == starter:
                    status = "PLAYED"
                else:
                    status = "DEMOTED"

            out.append({"season": season, "team": team, "game_id": gid,
                        "game_date": gdate, "starter": starter,
                        "status": status})
            history.append((primary, played))
    return pd.DataFrame(out)


def build_sample(seasons: list[int]) -> pd.DataFrame:
    from data.db import get_connection
    from scripts.ncaaf_search.dataset import build_label_set

    conn = get_connection()
    try:
        qb = load_qb_log(conn, seasons)
        labels = build_label_set(seasons=seasons, conn=conn).games
    finally:
        conn.close()

    st = starter_status(qb)
    st = st[st["starter"].notna()]

    home = st.rename(columns={"team": "home_team", "status": "home_status",
                              "starter": "home_starter"}) \
             .drop(columns=["season", "game_date"])
    away = st.rename(columns={"team": "away_team", "status": "away_status",
                              "starter": "away_starter"}) \
             .drop(columns=["season", "game_date"])

    df = labels.merge(home, on=["game_id", "home_team"], how="left") \
               .merge(away, on=["game_id", "away_team"], how="left")

    # One row per TEAM-game where a starter is defined.
    rows = []
    for side, other in (("home", "away"), ("away", "home")):
        d = df[df[f"{side}_status"].notna()].copy()
        d["side"] = side
        d["status"] = d[f"{side}_status"]
        d["other_status"] = d[f"{other}_status"]
        rows.append(d)
    sample = pd.concat(rows, ignore_index=True)

    # Both starters out cancels; a demoted starter is a different event.
    sample = sample[~((sample["status"] == "OUT") &
                      (sample["other_status"] == "OUT"))]
    sample = sample[sample["status"] != "DEMOTED"]
    return sample


def grade(sample: pd.DataFrame) -> pd.DataFrame:
    """Add per-arm win columns (NaN where the line is missing or a push)."""
    s = sample.copy()
    # home_covers is 1/0/NaN (NaN = no line or push).
    team_covers = np.where(s["side"] == "home", s["home_covers"],
                           1.0 - s["home_covers"])
    s["team_covers"] = team_covers
    s["fade_win"] = 1.0 - s["team_covers"]
    s["back_win"] = s["team_covers"]
    s["under_win"] = 1.0 - s["went_over"]
    return s


def _line(label: str, wins: pd.Series) -> str:
    w = wins.dropna()
    n = len(w)
    k = int(w.sum())
    lo, hi = wilson(k, n)
    pct = k / n if n else float("nan")
    flag = "  <- clears" if lo > BREAKEVEN else ""
    return (f"  {label:<34} n={n:4d}  {pct:6.1%}  "
            f"CI [{lo:.3f},{hi:.3f}]{flag}")


def report(s: pd.DataFrame) -> None:
    out = s[s["status"] == "OUT"]
    inn = s[s["status"] == "PLAYED"]
    print(f"team-games with a defined starter: {len(s)}  "
          f"(starter OUT: {len(out)}, PLAYED: {len(inn)})")
    print(f"seasons: {sorted(s['season'].unique().tolist())}")
    print(f"\nPOWER: at 55% over n={len(out)} the Wilson CI is "
          f"[{wilson(int(0.55*len(out)), len(out))[0]:.3f},"
          f"{wilson(int(0.55*len(out)), len(out))[1]:.3f}]; "
          f"a null means no edge above ~4pp is detectable.\n")

    for arm, col in (("FADE the team (starter out)", "fade_win"),
                     ("BACK the team (starter out)", "back_win"),
                     ("UNDER the total (starter out)", "under_win")):
        print(f"== {arm}")
        print(_line("pooled", out[col]))
        print(_line("control: same arm, starter PLAYED", inn[col]))
        for season, g in out.groupby("season"):
            print(_line(f"  {season}", g[col]))
        # game_date is an ISO string; the median is the middle date once sorted.
        med = sorted(out["game_date"].astype(str))[len(out) // 2]
        early = out[out["game_date"] <= med]
        late = out[out["game_date"] > med]
        print(_line(f"  time split early (<= {med})", early[col]))
        print(_line(f"  time split late  (>  {med})", late[col]))
        print()

    # Where does the market put these teams? Descriptive, not a verdict.
    fav = out[(out["side"] == "home") & (out["spread_home"] < 0) |
              (out["side"] == "away") & (out["spread_home"] > 0)]
    print(f"descriptive: starter-out team is the favourite in "
          f"{len(fav)} of {len(out)} ({len(fav)/max(len(out),1):.0%})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", nargs="*", type=int, default=SEASONS)
    args = ap.parse_args()
    sample = build_sample(args.seasons)
    report(grade(sample))


if __name__ == "__main__":
    main()
