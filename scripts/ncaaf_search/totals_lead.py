"""
NCAAF totals rule at earlier leads — does the ±8 rule survive Tuesday's line?

Session 252. `ncaaf_over_under` fires only within NCAAF_TOTALS_MAX_LEAD_DAYS
(=1) of kickoff, because the rule was validated on the archive's closing
number and nothing earlier had ever been measured. The 2023-2025 DraftKings
backfill (14:00Z and 23:00Z snapshots, source='odds_api_historical') is what
measures it. The model's prediction is fundamentals-only and does not change
with lead, so the question is purely: graded at the line DK posted d days
out, does the rule still clear?

DEFINITIONS (fixed before any number was looked at)
- Prediction: `ncaaf_margin_eval.walk_forward_totals` shape — for each test
  season fit on every earlier frame season (2020 excluded), predict the
  held-out season once. TOTAL_FEATURES, the shipped XGB params.
- Lead d (d = 0..5): DraftKings' total AS OF 14:00Z on the calendar day d
  days before the kickoff's ET date — the latest DK totals row whose
  snapshot_at <= that instant. snapshot_at is the market's last_update, so
  a line that has not moved since the previous pull is still "the line at
  14:00Z". Pre-game rows only (snapshot_type <> 'in_play', snapshot_at <
  commence_time). One row per (game, d); games not yet listed at that
  instant are absent at that lead.
- Close: DK's last pre-kick snapshot in the backfill — same book as the
  leads. The backfill holds 14:00Z and 23:00Z pulls only, so "close" is
  the last of those before kickoff, up to ~10 hours early for a noon game. `archive` = the frame's `_total_line` (CFBD archive, Bovada
  priority), the number the published 55.9% was measured on; reported so
  the new table is anchored to the old one.
- Grading: at the lead's line — the number you would have bet. d =
  pred − line, |d| ≥ gate, sign picks over/under; pushes excluded.
- Gate: the shipped 8.0, plus 6/7/9/10 so a plateau is visible.
- Move toward model: (close − lead line) × sign(pick), in points. Positive
  = the market moved the way the model leaned by kickoff (CLV in points).
- First cross: scans the 14:00Z snapshots only, then the close. Production
  passes run more often, so this is a proxy for the §1c first-signal lock.
- Join: odds game ids are the ingestor's (ET-dated) ids; night games carry a
  second CFBD (UTC-dated) row that holds the score. Odds rows are matched to
  frame rows on (season, home_team, away_team) with game_date within ±1 day.
  Matched / unmatched counts are printed per season.

Power: ~116 rule bets a season at the close in the published sweep. Three
seasons ≈ 350 bets; a Wilson CI on 350 at 56% is ≈ ±5pp, and each half of
the time split is wider. A null here means "not separable at ~5pp", not
"no effect".

    python scripts/ncaaf_search/totals_lead.py
    python scripts/ncaaf_search/totals_lead.py --test 2024 2025 --csv out.csv
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ncaaf_margin_eval import (  # noqa: E402
    BREAKEVEN, TOTAL_FEATURES, _fit, _matrix, build_frames)

LEADS = [0, 1, 2, 3, 4, 5]
GATES = [6.0, 7.0, 8.0, 9.0, 10.0]
SHIPPED_GATE = 8.0
SNAP_HOUR_UTC = 14
DEFAULT_SEASONS = [2015, 2016, 2017, 2018, 2019, 2021, 2022, 2023, 2024, 2025]
DEFAULT_TEST = [2023, 2024, 2025]
ET = dt.timezone(dt.timedelta(hours=-4))   # kickoff ET date; DST-exact enough for a date


def wilson(w: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (float("nan"), float("nan"))
    ph = w / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


# ---------------------------------------------------------------- predictions
def oos_predictions(frame: pd.DataFrame, test_seasons: list[int]) -> pd.DataFrame:
    parts = []
    for s in test_seasons:
        train = frame[frame["_season"] < s]
        test = frame[frame["_season"] == s]
        Xtr, cols = _matrix(train, TOTAL_FEATURES)
        Xte, _ = _matrix(test, TOTAL_FEATURES)
        if Xtr.empty or Xte.empty:
            print(f"  season {s}: empty train/test after dropna — skipped")
            continue
        model = _fit(Xtr[cols], Xtr["_total"])
        out = Xte[["_game_id", "_season", "_total", "_total_line"]].copy()
        out["pred"] = model.predict(Xte[cols])
        print(f"  season {s}: trained on {len(Xtr)} rows "
              f"({sorted(Xtr['_season'].unique().tolist())}), predicted {len(out)}")
        parts.append(out)
    return pd.concat(parts, ignore_index=True)


# ------------------------------------------------------------------- backfill
def load_backfill(conn, seasons: list[int]) -> tuple[pd.DataFrame, pd.DataFrame]:
    ph = ",".join(["%s"] * len(seasons))
    odds = conn.execute(f"""
        SELECT o.game_id, g.season, g.home_team, g.away_team, g.game_date,
               g.commence_time::timestamptz AS commence_time, o.snapshot_at::timestamptz AS snapshot_at,
               o.total_line
        FROM odds o JOIN games g ON g.game_id = o.game_id
        WHERE o.source = 'odds_api_historical'
          AND o.bookmaker = 'draftkings' AND o.market = 'totals'
          AND g.sport = 'NCAAF' AND g.season IN ({ph})
          AND o.total_line IS NOT NULL
          AND COALESCE(o.snapshot_type, 'open') <> 'in_play'
          AND o.snapshot_at::timestamptz < g.commence_time::timestamptz
    """, seasons).fetchall()
    odds = pd.DataFrame(odds, columns=["game_id", "season", "home_team", "away_team",
                                       "game_date", "commence_time", "snapshot_at",
                                       "total_line"])
    odds["snapshot_at"] = pd.to_datetime(odds["snapshot_at"], utc=True)
    odds["commence_time"] = pd.to_datetime(odds["commence_time"], utc=True)
    odds["total_line"] = odds["total_line"].astype(float)
    games = conn.execute(f"""
        SELECT game_id, season, home_team, away_team, game_date
        FROM games WHERE sport = 'NCAAF' AND season IN ({ph})
    """, seasons).fetchall()
    games = pd.DataFrame(games, columns=["game_id", "season", "home_team",
                                         "away_team", "game_date"])
    return odds, games


def match_frame_to_odds(pred: pd.DataFrame, games: pd.DataFrame,
                        odds: pd.DataFrame) -> pd.DataFrame:
    """Frame game -> odds game_id by (season, home, away, date ±1)."""
    fg = pred.merge(games, left_on="_game_id", right_on="game_id", how="left")
    og = (odds[["game_id", "season", "home_team", "away_team", "game_date"]]
          .drop_duplicates("game_id")
          .rename(columns={"game_id": "odds_game_id", "game_date": "odds_date"}))
    cand = fg.merge(og, on=["season", "home_team", "away_team"], how="left")
    cand["_dd"] = (pd.to_datetime(cand["odds_date"]) - pd.to_datetime(cand["game_date"])).dt.days.abs()
    cand = cand[cand["_dd"].le(1) | cand["odds_game_id"].isna()]
    cand = cand.sort_values("_dd").drop_duplicates("_game_id", keep="first")
    return cand


# ---------------------------------------------------------------------- leads
def line_as_of(odds_g: pd.DataFrame, instant: pd.Timestamp) -> float | None:
    sub = odds_g[odds_g["snapshot_at"] <= instant]
    if sub.empty:
        return None
    return float(sub.sort_values("snapshot_at").iloc[-1]["total_line"])


def build_lead_table(matched: pd.DataFrame, odds: pd.DataFrame) -> pd.DataFrame:
    by_game = {gid: grp.sort_values("snapshot_at") for gid, grp in odds.groupby("game_id")}
    rows = []
    for r in matched.to_dict("records"):
        gid = r["odds_game_id"]
        if pd.isna(gid) or gid not in by_game:
            continue
        og = by_game[gid]
        kick = og["commence_time"].iloc[0]
        kick_et_date = kick.astimezone(ET).date()
        close = float(og.iloc[-1]["total_line"])
        archive = r["_total_line"]
        base = dict(game_id=r["_game_id"], season=r["_season"], actual=r["_total"],
                    pred=r["pred"], close=close, archive=archive,
                    kick=kick, week_date=kick_et_date)
        rows.append({**base, "lead": "close", "line": close})
        rows.append({**base, "lead": "archive",
                     "line": archive if not pd.isna(archive) else None})
        for d in LEADS:
            instant = pd.Timestamp(dt.datetime.combine(
                kick_et_date - dt.timedelta(days=d), dt.time(SNAP_HOUR_UTC, 0),
                tzinfo=dt.timezone.utc))
            if instant >= kick:
                continue
            ln = line_as_of(og, instant)
            rows.append({**base, "lead": str(d), "line": ln})
    t = pd.DataFrame(rows)
    t = t.dropna(subset=["line"])
    t["d"] = t["pred"] - t["line"]
    t["pick"] = np.sign(t["d"])
    t["res"] = np.sign(t["actual"] - t["line"])
    t["move"] = (t["close"] - t["line"]) * t["pick"]
    return t


def first_cross(t: pd.DataFrame, limit: int, gate: float) -> pd.DataFrame:
    """One row per game: the first lead (from `limit` down to 0, then close)
    at which |pred-line| >= gate; games that never cross keep their close row
    (so they count as games, not bets)."""
    order = {str(d): i for i, d in enumerate(range(limit, -1, -1))}
    order["close"] = len(order)
    sub = t[t["lead"].isin(order)].copy()
    sub["_o"] = sub["lead"].map(order)
    sub = sub.sort_values(["game_id", "_o"])
    crossed = sub[sub["d"].abs() >= gate].drop_duplicates("game_id", keep="first")
    rest = sub[~sub["game_id"].isin(crossed["game_id"]) & (sub["lead"] == "close")]
    return pd.concat([crossed, rest], ignore_index=True)


# --------------------------------------------------------------------- report
def grade(sub: pd.DataFrame, gate: float) -> dict:
    sel = sub[sub["d"].abs() >= gate]
    dec = sel[sel["res"] != 0]
    n = len(dec)
    w = int((dec["pick"] == dec["res"]).sum())
    lo, hi = wilson(w, n)
    return dict(bets=n, wins=w, pushes=int(len(sel) - n),
                win_rate=(w / n) if n else float("nan"), lo=lo, hi=hi,
                move=float(sel["move"].mean()) if len(sel) else float("nan"),
                games=int(sub["game_id"].nunique()))


def fmt(g: dict) -> str:
    wr = f"{g['win_rate']:.3f}" if g["bets"] else "  n/a"
    ci = f"[{g['lo']:.3f},{g['hi']:.3f}]" if g["bets"] else "             "
    flag = "" if not g["bets"] else (" +" if g["lo"] > BREAKEVEN else ("  " if g["hi"] > BREAKEVEN else " -"))
    return (f"{g['games']:5d} {g['bets']:5d} {g['wins']:5d} {wr} {ci}{flag} "
            f"move {g['move']:+.2f}")


def report(t: pd.DataFrame, test_seasons: list[int]) -> None:
    order = [str(d) for d in LEADS] + ["close", "archive"]
    hdr = f"{'lead':>8} {'games':>5} {'bets':>5} {'wins':>5} {'win%':>5} {'Wilson 95%':>15}   (+ clears {BREAKEVEN}, - below)"

    print("\n=== Shipped gate 8.0, pooled over", test_seasons, "===")
    print(hdr)
    for lead in order:
        print(f"{lead:>8} " + fmt(grade(t[t['lead'] == lead], SHIPPED_GATE)))

    print("\n=== Shipped gate 8.0, per season ===")
    for s in test_seasons:
        print(f"-- {s}")
        for lead in order:
            print(f"{lead:>8} " + fmt(grade(t[(t['lead'] == lead) & (t['season'] == s)], SHIPPED_GATE)))

    print("\n=== Shipped gate 8.0, time split (first half / second half of each season by kickoff date) ===")
    halves = []
    for s in test_seasons:
        ts = t[t["season"] == s]
        dates = sorted(ts["week_date"].unique())
        if not dates:
            continue
        mid = dates[len(dates) // 2]
        halves.append((s, mid))
    early = pd.concat([t[(t["season"] == s) & (t["week_date"] < mid)] for s, mid in halves])
    late = pd.concat([t[(t["season"] == s) & (t["week_date"] >= mid)] for s, mid in halves])
    for name, sub in (("early", early), ("late", late)):
        print(f"-- {name}")
        for lead in order:
            print(f"{lead:>8} " + fmt(grade(sub[sub['lead'] == lead], SHIPPED_GATE)))

    print("\n=== Gate sweep, pooled: win% (bets) ===")
    print(f"{'lead':>8} " + " ".join(f"{g:>13}" for g in GATES))
    for lead in order:
        cells = []
        for g in GATES:
            r = grade(t[t["lead"] == lead], g)
            cells.append(f"{r['win_rate']:.3f} ({r['bets']:4d})" if r["bets"] else "   n/a       ")
        print(f"{lead:>8} " + " ".join(f"{c:>13}" for c in cells))

    print("\n=== FIRST CROSS — what shipping a limit of L does (§1c lock at the first pass that clears 8.0) ===")
    print("    scan leads L, L-1, ..., 0, then close; bet the first line with |pred-line| >= 8; graded at that line")
    for L in LEADS:
        fc = first_cross(t, L, SHIPPED_GATE)
        g = grade(fc, SHIPPED_GATE)
        bets = fc[fc["d"].abs() >= SHIPPED_GATE]
        early = (bets["lead"] != "close").mean() if len(bets) else float("nan")
        print(f"{L:>8} " + fmt(g) + f"   {100 * early:.0f}% locked before close")
        for s_ in test_seasons:
            print(f"{'':>8}   {s_} " + fmt(grade(fc[fc["season"] == s_], SHIPPED_GATE)))

    print("\n=== Lead line vs close (all matched games, not just bets) ===")
    for lead in [str(d) for d in LEADS]:
        sub = t[t["lead"] == lead]
        diff = (sub["close"] - sub["line"]).abs()
        print(f"{lead:>8} games {len(sub):5d}  mean |close-line| {diff.mean():.2f}  "
              f"moved>=1 {100 * (diff >= 1).mean():.1f}%  moved>=3 {100 * (diff >= 3).mean():.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seasons", nargs="+", type=int, default=DEFAULT_SEASONS)
    ap.add_argument("--test", nargs="+", type=int, default=DEFAULT_TEST)
    ap.add_argument("--csv", default=None, help="write the per-(game, lead) table")
    args = ap.parse_args()

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from data.db import get_connection

    print("building frame …")
    frame = build_frames(args.seasons)
    print("walk-forward predictions …")
    pred = oos_predictions(frame, args.test)

    conn = get_connection()
    try:
        odds, games = load_backfill(conn, args.test)
    finally:
        conn.close()
    print(f"backfill: {len(odds)} DK pre-kick totals rows across {odds['game_id'].nunique()} games")

    matched = match_frame_to_odds(pred, games, odds)
    for s in args.test:
        ms = matched[matched["_season"] == s]
        hit = ms["odds_game_id"].notna()
        same = (ms.loc[hit, "_dd"] == 0).sum()
        print(f"  {s}: frame games {len(ms)}, matched to DK backfill {int(hit.sum())} "
              f"(same-date {int(same)}, ±1-day alias {int(hit.sum() - same)}), unmatched {int((~hit).sum())}")

    t = build_lead_table(matched, odds)
    if args.csv:
        t.to_csv(args.csv, index=False)
        print(f"wrote {args.csv}")
    report(t, args.test)


if __name__ == "__main__":
    main()
