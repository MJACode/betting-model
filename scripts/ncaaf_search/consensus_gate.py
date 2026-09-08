"""
The totals rule anchored on the 13-book consensus instead of DraftKings, and
conditioned on how much the books disagree.

Session 252 (2026-09-08). The shipped rule fires when the model's total sits
8+ points from DRAFTKINGS' total (56% at the close, 2023-2025 walk-forward,
totals_lead.py). Two questions the 13-book backfill can answer for the first
time:

  1. CONSENSUS ANCHOR. Gate on |pred - median total across all books| >= 8
     and bet at DK's line. If the win rate holds, the edge is model-side. If
     it only survives where DK sits off consensus, it is PR #581's shape
     (soft book off the sharp number) wearing a different name.
  2. DISPERSION. Does the DK-anchored rule do better when the books disagree
     (max - min total across books >= 1.5)?

DEFINITIONS
- Prediction: the shipped walk-forward (fit on every earlier frame season,
  predict the held-out one), via totals_lead.oos_predictions.
- Close: each book's last pre-kick stored total in the backfill (14:00Z /
  23:00Z pulls only). DK close, median across every book with a close,
  dispersion = max - min, n_books.
- Grade at DK's close, side = sign(pred - anchor); pushes excluded.
- Per season, Wilson vs 0.5238, time split.

    python scripts/ncaaf_search/consensus_gate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ncaaf_margin_eval import build_frames  # noqa: E402
from scripts.ncaaf_search.totals_lead import (  # noqa: E402
    DEFAULT_SEASONS, DEFAULT_TEST, BREAKEVEN, oos_predictions, wilson)

GATE = 8.0


def load_closes(conn, seasons):
    ph = ",".join(["%s"] * len(seasons))
    rows = conn.execute(f"""
        WITH last AS (
          SELECT o.game_id, o.bookmaker, o.total_line,
                 ROW_NUMBER() OVER (PARTITION BY o.game_id, o.bookmaker
                                    ORDER BY o.snapshot_at::timestamptz DESC) rn
          FROM odds o JOIN games g ON g.game_id = o.game_id
          WHERE g.sport = 'NCAAF' AND g.season IN ({ph})
            AND o.source = 'odds_api_historical' AND o.market = 'totals'
            AND o.total_line IS NOT NULL
            AND COALESCE(o.snapshot_type, 'open') <> 'in_play'
            AND o.snapshot_at::timestamptz < g.commence_time::timestamptz)
        SELECT l.game_id, g.season, g.home_team, g.away_team, g.game_date,
               l.bookmaker, l.total_line
        FROM last l JOIN games g ON g.game_id = l.game_id WHERE rn = 1
    """, seasons).fetchall()
    df = pd.DataFrame(rows, columns=["game_id", "season", "home_team", "away_team",
                                     "game_date", "bookmaker", "total"])
    df["total"] = df["total"].astype(float)
    per_game = df.groupby(["game_id", "season", "home_team", "away_team", "game_date"]).agg(
        median=("total", "median"), lo=("total", "min"), hi=("total", "max"),
        n_books=("total", "size")).reset_index()
    dk = df[df["bookmaker"] == "draftkings"][["game_id", "total"]].rename(columns={"total": "dk"})
    pin = df[df["bookmaker"] == "pinnacle"][["game_id", "total"]].rename(columns={"total": "pin"})
    per_game = per_game.merge(dk, on="game_id", how="inner").merge(pin, on="game_id", how="left")
    per_game["disp"] = per_game["hi"] - per_game["lo"]
    return per_game


def match(pred: pd.DataFrame, games_all: pd.DataFrame, closes: pd.DataFrame) -> pd.DataFrame:
    fg = pred.merge(games_all, left_on="_game_id", right_on="game_id", how="left")
    cand = fg.merge(closes.rename(columns={"game_id": "odds_game_id", "game_date": "odds_date"}),
                    on=["season", "home_team", "away_team"], how="inner")
    cand["_dd"] = (pd.to_datetime(cand["odds_date"]) - pd.to_datetime(cand["game_date"])).dt.days.abs()
    cand = cand[cand["_dd"].le(1)].sort_values("_dd").drop_duplicates("_game_id", keep="first")
    return cand


def grade(sub: pd.DataFrame, anchor: str) -> dict:
    d = sub["pred"] - sub[anchor]
    sel = sub[d.abs() >= GATE].copy()
    sel["side"] = np.sign(sel["pred"] - sel[anchor])
    sel["res"] = np.sign(sel["_total"] - sel["dk"])
    dec = sel[sel["res"] != 0]
    n = len(dec); w = int((dec["side"] == dec["res"]).sum())
    lo, hi = wilson(w, n)
    return dict(n=n, w=w, wr=(w / n) if n else float("nan"), lo=lo, hi=hi)


def fmt(g):
    if not g["n"]:
        return f"{0:5d}   n/a"
    flag = " +" if g["lo"] > BREAKEVEN else ("  " if g["hi"] > BREAKEVEN else " -")
    return f"{g['n']:5d} {g['wr']:.3f} [{g['lo']:.3f},{g['hi']:.3f}]{flag}"


def main():
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
    from data.db import get_connection

    frame = build_frames(DEFAULT_SEASONS)
    pred = oos_predictions(frame, DEFAULT_TEST)
    conn = get_connection()
    try:
        closes = load_closes(conn, DEFAULT_TEST)
        ph = ",".join(["%s"] * len(DEFAULT_TEST))
        games_all = pd.DataFrame(conn.execute(f"""
            SELECT game_id, season, home_team, away_team, game_date FROM games
            WHERE sport = 'NCAAF' AND season IN ({ph})""", DEFAULT_TEST).fetchall(),
            columns=["game_id", "season", "home_team", "away_team", "game_date"])
    finally:
        conn.close()
    t = match(pred, games_all, closes)
    print(f"matched games with a DK close and a 13-book consensus: {len(t)}; "
          f"median n_books {t['n_books'].median():.0f}; DK-vs-median |diff| mean {(t['dk'] - t['median']).abs().mean():.2f}; "
          f"dispersion mean {t['disp'].mean():.2f}, >=1.5 in {100 * (t['disp'] >= 1.5).mean():.0f}% of games")

    mids = {}
    for s in DEFAULT_TEST:
        ds = sorted(t.loc[t["season"] == s, "game_date"].unique())
        mids[s] = ds[len(ds) // 2]
    t["half"] = np.where(t["game_date"] < t["season"].map(mids), "early", "late")

    print(f"\n=== gate |pred - anchor| >= {GATE:g}, bet at DK's close ===")
    print(f"{'anchor':>28} {'bets':>5} {'win%':>5} {'Wilson 95%':>15}")
    for anchor, label in (("dk", "DraftKings (shipped)"), ("median", "13-book median"), ("pin", "Pinnacle")):
        sub = t.dropna(subset=[anchor])
        print(f"{label:>28} " + fmt(grade(sub, anchor)))
        for s in DEFAULT_TEST:
            print(f"{'':>28}   {s}  " + fmt(grade(sub[sub['season'] == s], anchor)))
        for h in ("early", "late"):
            print(f"{'':>28}   {h:<5} " + fmt(grade(sub[sub['half'] == h], anchor)))

    print(f"\n=== DK-anchored rule, split by where DK sits vs consensus (relative to the model's side) ===")
    d = t["pred"] - t["dk"]
    side = np.sign(d)
    dk_off = (t["dk"] - t["median"]) * side          # >0: DK already sits on the model's side of consensus
    for name, mask in (("DK on model's side of median (>= 0.5)", dk_off >= 0.5),
                       ("DK at consensus (|off| < 0.5)", dk_off.abs() < 0.5),
                       ("DK on the other side (<= -0.5)", dk_off <= -0.5)):
        print(f"{name:>45} " + fmt(grade(t[mask], "dk")))

    print(f"\n=== DK-anchored rule, split by dispersion across books ===")
    for name, mask in (("dispersion >= 1.5", t["disp"] >= 1.5), ("dispersion < 1.5", t["disp"] < 1.5),
                       ("dispersion >= 2.5", t["disp"] >= 2.5)):
        print(f"{name:>45} " + fmt(grade(t[mask], "dk")))


if __name__ == "__main__":
    main()
