"""
mlb_prop_market_sweep.py — does the market-relative rule work on MLB?

WHY THIS EXISTS. models/mlb_prop_market.py has been in the repo since #366 and
has never produced a bet: no card script, no wiring, no config entry, and no
settlement mapping. So the construction that measured +10.33% on NFL props has
never been graded on baseball at all, and the file says so itself — it ships no
default threshold because "there is nothing to pre-commit against here yet."

This grades it, so the threshold is measured rather than borrowed from NFL.

WHAT IT DOES NOT CLAIM. Pinnacle MLB prop coverage in player_prop_odds starts
2026-08-27. That is a very short window, it is one slice of one season, and it
is IN-SAMPLE in the only sense that matters here: it is the same period anyone
would eyeball before choosing a number. Read the output as "is there anything
here at all", not as a validated cut. §7's rules apply in full — report the
PLATEAU not the peak, split by time, and say when the grid is negative
everywhere rather than shipping the least-bad cell.

    python -m scripts.mlb_prop_market_sweep
    python -m scripts.mlb_prop_market_sweep --start 2026-08-27 --end 2026-09-05
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger  # noqa: E402

import models.mlb_prop_market as mk  # noqa: E402
from data.db import get_connection  # noqa: E402

# market -> (player_type, column in player_game_log). COMPUTE_OUTS mirrors
# tracking/paper_tracker's special case: innings_pitched is baseball notation,
# 5.2 meaning five innings and two outs, so it is 3*whole + fraction*10.
MARKET_STAT = {
    "batter_total_bases":   ("batter",  "total_bases"),
    "batter_home_runs":     ("batter",  "home_runs"),
    "pitcher_strikeouts":   ("pitcher", "p_strikeouts"),
    "pitcher_hits_allowed": ("pitcher", "p_hits_allowed"),
    "pitcher_outs":         ("pitcher", "COMPUTE_OUTS"),
}


def norm(name: str) -> str:
    """Loose join key. The odds feed and the game log disagree on accents,
    suffixes and punctuation; a strict join silently drops rows and a sweep
    that drops rows reports a number about coverage, not about edge."""
    import unicodedata
    s = unicodedata.normalize("NFKD", str(name or ""))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    for junk in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(junk):
            s = s[: -len(junk)]
    return "".join(c for c in s if c.isalnum())


def outs_from_ip(ip) -> float | None:
    if ip is None:
        return None
    ip = float(ip)
    whole = int(ip)
    frac = round(ip - whole, 1)
    return whole * 3 + int(round(frac * 10))


def actuals(conn, game_date: str) -> dict:
    """{(norm_name, game_id): row} for one date."""
    rows = conn.execute("""
        SELECT player_name, game_id, player_type, innings_pitched,
               p_strikeouts, p_hits_allowed, hits, total_bases, home_runs
        FROM player_game_log WHERE game_date = %s
    """, (game_date,)).fetchall()
    cols = ["player_name", "game_id", "player_type", "innings_pitched",
            "p_strikeouts", "p_hits_allowed", "hits", "total_bases", "home_runs"]
    out = {}
    for r in rows:
        d = dict(zip(cols, r))
        out[(norm(d["player_name"]), d["game_id"])] = d
    return out


def profit(price: float, won: bool) -> float:
    """1u flat. American price."""
    if not won:
        return -1.0
    return price / 100.0 if price > 0 else 100.0 / abs(price)


def grade_day(conn, game_date: str, min_edge: float):
    """-> (list of (market, side, price, edge, result), diagnostic)"""
    bets, diag = mk.card(conn, game_date, min_edge=min_edge)
    act = actuals(conn, game_date)
    graded, unmatched = [], 0
    for b in bets:
        stat = MARKET_STAT.get(b.market)
        row = act.get((norm(b.player), b.game_id))
        if stat is None or row is None:
            unmatched += 1
            continue
        _, col = stat
        val = outs_from_ip(row["innings_pitched"]) if col == "COMPUTE_OUTS" else row[col]
        if val is None:
            unmatched += 1
            continue
        val = float(val)
        if val == b.line:
            continue                      # push — returns the stake, no result
        won = (val > b.line) if b.side == "over" else (val < b.line)
        graded.append((b.market, b.side, b.price, b.edge, profit(b.price, won)))
    diag["unmatched"] = unmatched
    return graded, diag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08-27")
    ap.add_argument("--end",   default="2026-09-05")
    a = ap.parse_args()

    conn = get_connection()
    days = []
    d0 = date.fromisoformat(a.start)
    d1 = date.fromisoformat(a.end)
    while d0 <= d1:
        days.append(d0.isoformat())
        d0 += timedelta(days=1)

    print(f"\nMLB market-relative sweep — sharp {mk.SHARP_BOOK}, "
          f"soft {list(mk.SOFT_BOOKS)}, {len(days)} dates {a.start}..{a.end}")
    print(f"markets: {', '.join(mk.SHARP_MARKETS)}\n")

    print(f"{'min_edge':>9} {'bets':>6} {'win%':>7} {'units':>9} {'ROI':>8}   per-market")
    print("-" * 92)
    grid = {}
    for pp in (0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08):
        allg, unmatched = [], 0
        for gd in days:
            g, diag = grade_day(conn, gd, pp)
            allg += g
            unmatched += diag.get("unmatched", 0)
        grid[pp] = allg
        if not allg:
            print(f"{pp:>8.0%} {0:>6}      —         —        —   (no bets)")
            continue
        u = sum(x[4] for x in allg)
        w = sum(1 for x in allg if x[4] > 0)
        by = defaultdict(list)
        for m, _s, _p, _e, r in allg:
            by[m].append(r)
        per = "  ".join(f"{m.replace('batter_','b_').replace('pitcher_','p_')}"
                        f" {len(v)}/{sum(v):+.1f}u" for m, v in sorted(by.items()))
        print(f"{pp:>8.0%} {len(allg):>6} {100*w/len(allg):>6.1f}% "
              f"{u:>+8.2f} {100*u/len(allg):>+7.2f}%   {per}")
        if unmatched:
            print(f"{'':>9} (unmatched to a game log: {unmatched})")

    # Time split — §7: every situational edge that looked strong pooled
    # collapsed when split early/late, so the split is part of the method.
    mid = days[len(days) // 2]
    print(f"\ntime split at {mid}")
    print(f"{'min_edge':>9} {'early bets':>11} {'early ROI':>10} "
          f"{'late bets':>10} {'late ROI':>9}")
    print("-" * 56)
    for pp in (0.03, 0.04, 0.05, 0.06):
        early, late = [], []
        for gd in days:
            g, _ = grade_day(conn, gd, pp)
            (early if gd < mid else late).append(g)
        e = [x for g in early for x in g]
        l = [x for g in late for x in g]
        er = f"{100*sum(x[4] for x in e)/len(e):+.2f}%" if e else "—"
        lr = f"{100*sum(x[4] for x in l)/len(l):+.2f}%" if l else "—"
        print(f"{pp:>8.0%} {len(e):>11} {er:>10} {len(l):>10} {lr:>9}")

    conn.close()


if __name__ == "__main__":
    main()
