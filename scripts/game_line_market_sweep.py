"""The market-relative rule on GAME LINES, not props.

THE ARGUMENT FOR TRYING THIS. models/nfl_prop_market is the only construction in
this repo with a blind-tested positive result (+10.33% over 954 bets). It has
only ever been applied to PLAYER PROPS, and props are the most heavily juiced
market we touch -- measured 2026-09-07 on the live NFL board, the hold runs 5.7%
to 24.3% by market, so a bet must beat DraftKings' own de-vigged number by 3 to
12 points merely to break even. Game lines run about half that.

And the data is already bought. `odds` holds Pinnacle on 6,788 MLB games and
2,719 NCAAF games across h2h, spreads and totals -- roughly ten times the sample
the prop rule was validated on, at no additional cost.

Same construction, no changes: de-vig Pinnacle, bet a soft book where its own
de-vigged price disagrees by more than the threshold.

THE TRAPS, all three carried over deliberately.

  EQUAL LINES ONLY. Pinnacle at -1.5 against DraftKings at -2.5 is a DIFFERENT
  PROPOSITION, and calling that price gap an edge manufactures one out of thin
  air -- §5c discarded 35,107 quotes on this rule and §5b showed what happens
  when it is skipped. h2h has no line and is compared directly; spreads and
  totals must match to the point.

  PRE-GAME ONLY. Bounded on commence_time and in_play excluded. The prop version
  of this leak (#534) manufactured seven of every eight "edges".

  ONE BET PER PROPOSITION. The same game at three books is one opinion.

Grading is the game result, so there is no player-name join and no stat-mapping
question -- the two things that made the prop backtests fragile.

    python -m scripts.game_line_market_sweep
    python -m scripts.game_line_market_sweep --sport MLB --market h2h
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from data.db import get_connection

SHARP = "pinnacle"
SOFT = ("draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet",
        "betrivers", "hardrockbet", "bovada")


def implied(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def devig(a, b):
    """Proportional de-vig. None if either side is missing."""
    if a is None or b is None:
        return None, None
    ia, ib = implied(a), implied(b)
    t = ia + ib
    if t <= 0:
        return None, None
    return ia / t, ib / t


def profit(price, won):
    if won is None:
        return 0.0                      # push
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def load(conn, sport: str, market: str):
    """Latest PRE-GAME quote per (game, book) plus the game's result."""
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.bookmaker)
               o.game_id, o.bookmaker, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price,
               g.home_score, g.away_score, g.game_date, o.snapshot_at
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = %s AND o.market = %s
          AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL
          AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
          AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
        ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
    """, (sport, market)).fetchall()
    by_game = defaultdict(dict)
    meta = {}
    for (gid, bk, hp, ap, sh, tl, op, up, hs, as_, gd, snap) in rows:
        by_game[gid][bk] = dict(home=hp, away=ap, spread=sh, total=tl,
                                over=op, under=up, snap=snap)
        meta[gid] = (float(hs), float(as_), str(gd))
    return by_game, meta


def _gap_seconds(a, b) -> float | None:
    """|a - b| in seconds for two stored timestamps, or None if unparseable."""
    from features.feature_engine import _parse_iso_ts
    ta, tb = _parse_iso_ts(a), _parse_iso_ts(b)
    if ta is None or tb is None:
        return None
    return abs((ta - tb).total_seconds())


def grade(market, side, m, line):
    """True/False/None(push) for a side, given the final score."""
    hs, as_, _gd = m
    if market == "h2h":
        if hs == as_:
            return None
        return (hs > as_) if side == "home" else (as_ > hs)
    if market == "spreads":
        marg = hs - as_ + float(line)          # line is the HOME number (§4)
        if marg == 0:
            return None
        return marg > 0 if side == "home" else marg < 0
    total = hs + as_
    if total == float(line):
        return None
    return total > float(line) if side == "over" else total < float(line)


def sweep(conn, sport: str, market: str, edges, max_gap_s: float | None = 300):
    by_game, meta = load(conn, sport, market)
    picks = []
    diag = defaultdict(int)
    for gid, books in by_game.items():
        sharp = books.get(SHARP)
        if not sharp:
            diag["no_sharp"] += 1
            continue
        if market == "h2h":
            sf, _ = devig(sharp["home"], sharp["away"])
            su = 1 - sf if sf is not None else None
            sline = None
            sides = (("home", sf, "home"), ("away", su, "away"))
        elif market == "spreads":
            sline = sharp["spread"]
            sf, _ = devig(sharp["home"], sharp["away"])
            su = 1 - sf if sf is not None else None
            sides = (("home", sf, "home"), ("away", su, "away"))
        else:
            sline = sharp["total"]
            sf, _ = devig(sharp["over"], sharp["under"])
            su = 1 - sf if sf is not None else None
            sides = (("over", sf, "over"), ("under", su, "under"))
        if sf is None:
            diag["sharp_one_way"] += 1
            continue

        best = None
        for bk, q in books.items():
            if bk not in SOFT:
                continue
            bline = q["spread"] if market == "spreads" else (
                q["total"] if market == "totals" else None)
            if sline is not None and (bline is None or float(bline) != float(sline)):
                diag["line_mismatch"] += 1
                continue
            # SIMULTANEOUS OR IT IS NOT A DISAGREEMENT. §5c established the
            # prop rule on paired quotes 98.9% within five minutes, precisely so
            # the result could not be stale-vs-fresh. Game lines are stored per
            # book on independent cadences, so the latest pre-game quote from
            # two books can be hours apart -- and a STALE SHARP price against a
            # current soft one manufactures edge in the direction the rule bets.
            # Measured on MLB h2h: median gap 0s, but only 77% inside 5 minutes.
            if max_gap_s is not None:
                gap = _gap_seconds(sharp.get("snap"), q.get("snap"))
                if gap is None or gap > max_gap_s:
                    diag["not_simultaneous"] += 1
                    continue
            if market == "totals":
                a, b = q["over"], q["under"]
            else:
                a, b = q["home"], q["away"]
            fa, fb = devig(a, b)
            if fa is None:
                diag["soft_one_way"] += 1
                continue
            for side, sharp_p, _k in sides:
                soft_fair = fa if side in ("home", "over") else fb
                price = (a if side in ("home", "over") else b)
                edge = sharp_p - soft_fair
                if best is None or edge > best[0]:
                    best = (edge, side, price, bk, sline)
            diag["compared"] += 1
        if best is None:
            continue
        edge, side, price, bk, line = best
        won = grade(market, side, meta[gid], line)
        picks.append((meta[gid][2], edge, price, won, bk))

    out = []
    for e in edges:
        sel = [p for p in picks if p[1] >= e and p[3] is not None]
        if len(sel) < 40:
            out.append((e, len(sel), None, None, None))
            continue
        prof = [profit(p[2], p[3]) for p in sel]
        u = sum(prof)
        w = sum(1 for x in prof if x > 0)
        rng = np.random.default_rng(42)
        a = np.array(prof)
        idx = rng.integers(0, len(a), (10000, len(a)))
        roi = 100 * a[idx].mean(axis=1)
        out.append((e, len(sel), 100 * w / len(sel), 100 * u / len(sel),
                    (np.percentile(roi, 5), np.percentile(roi, 95))))
    return out, diag, picks


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", nargs="+", default=["MLB", "NCAAF"])
    ap.add_argument("--market", nargs="+", default=["h2h", "spreads", "totals"])
    a = ap.parse_args()
    edges = (0.01, 0.02, 0.03, 0.04, 0.05, 0.07)
    conn = get_connection()
    for sport in a.sport:
        for market in a.market:
            res, diag, picks = sweep(conn, sport, market, edges)
            print(f"\n=== {sport} {market} — sharp {SHARP}, {len(SOFT)} soft books")
            print(f"    compared {diag['compared']}, line_mismatch "
                  f"{diag['line_mismatch']}, no_sharp {diag['no_sharp']}, "
                  f"graded props {len(picks)}")
            print(f"    {'min_edge':>8} {'bets':>6} {'win%':>6} {'ROI':>8} {'90% CI':>18}")
            for e, n, w, roi, ci in res:
                if roi is None:
                    print(f"    {e:>7.0%} {n:>6}   (thin)")
                    continue
                print(f"    {e:>7.0%} {n:>6} {w:>5.1f}% {roi:>+7.2f}% "
                      f"{'('+format(ci[0],'+.1f')+', '+format(ci[1],'+.1f')+')':>18}")
    conn.close()


if __name__ == "__main__":
    main()
