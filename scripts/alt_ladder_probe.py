"""What do the alternate lines we already store actually buy us?

`docs/odds_sources.md` found 1.48M alternate-line rows sitting in
`player_prop_odds` that nothing reads. Before wiring them into the rule, this
measures the only thing that matters: how many soft-book propositions become
priceable that are discarded today.

THE COMPLICATION, measured before designing around it: alternate quotes are
ONE-SIDED. Every one of the 98,036 `player_reception_yds_alternate` rows carries
an over price and no under, so `devig()` cannot touch them and a rung is not a
fair probability on its own. A ladder of over prices IS a survival function, but
a VIGGED one -- reading it as truth would inflate every probability and bias the
rule toward overs, which is the exact failure `docs/prop_market_research.md`
records Peabody correcting for.

So the ladder gives SHAPE and the standard two-way quote gives LEVEL: de-vig the
sharp book's standard market at its own line to get one honest anchor point,
then scale the ladder to pass through it. That is a single-parameter correction
and it is an assumption -- stated here rather than buried, and worth only as
much as the measurement below.

Three ways a soft quote can be priced, counted separately:

    exact standard   a sharp book quotes two-way at the SAME line (today)
    exact alt        a sharp book quotes an ALTERNATE at the same line
    bracketed        the line falls inside the sharp book's alternate ladder

    python -m scripts.alt_ladder_probe
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from loguru import logger

import models.nfl_prop_market as mk
from data.db import get_connection
from data.ingestors.nfl_props_data_ingestor import norm_player_name


def base_market(m: str) -> str:
    return m[: -len("_alternate")] if m.endswith("_alternate") else m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    a = ap.parse_args()

    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT ON (o.game_id, o.player_name, o.market, o.bookmaker, o.line)
               o.game_id, o.player_name, o.market, o.bookmaker,
               o.line, o.over_price, o.under_price
        FROM player_prop_odds o
        WHERE o.game_id LIKE 'NFL%%'
          AND o.line IS NOT NULL
          AND o.game_date::date >= CURRENT_DATE
          AND o.game_date::date <= CURRENT_DATE + %s
        ORDER BY o.game_id, o.player_name, o.market, o.bookmaker, o.line,
                 o.snapshot_at DESC
    """, (a.days,)).fetchall()
    conn.close()
    logger.info(f"{len(rows):,} board quotes")

    # What each SHARP book offers per proposition.
    std_two_way = defaultdict(set)     # exact lines with a real two-way quote
    alt_lines = defaultdict(set)       # every alternate strike (one-sided overs)
    for gid, player, market, book, line, op, up in rows:
        if book not in mk.SHARP_BOOKS:
            continue
        key = (gid, norm_player_name(player), base_market(market))
        line = float(line)
        if market.endswith("_alternate"):
            if op is not None:
                alt_lines[key].add(line)
        elif op is not None and up is not None:
            std_two_way[key].add(line)

    tally = defaultdict(int)
    by_market = defaultdict(lambda: defaultdict(int))
    for gid, player, market, book, line, op, up in rows:
        # The SOFT side we could actually bet: a real two-way standard quote.
        if book not in mk.SOFT_BOOKS or market.endswith("_alternate"):
            continue
        if op is None or up is None:
            continue
        key = (gid, norm_player_name(player), base_market(market))
        line = float(line)
        alts = alt_lines.get(key, set())
        stds = std_two_way.get(key, set())

        tally["soft"] += 1
        by_market[base_market(market)]["soft"] += 1
        exact_std = line in stds
        exact_alt = line in alts
        # A ladder can only be LEVELLED where a standard two-way anchor exists.
        bracketed = bool(alts) and bool(stds) and min(alts) <= line <= max(alts)

        for name, hit in (("exact_std", exact_std),
                          ("exact_alt", exact_alt),
                          ("bracketed", bracketed)):
            if hit:
                tally[name] += 1
                by_market[base_market(market)][name] += 1
        if (exact_alt or bracketed) and not exact_std:
            tally["recovered"] += 1
            by_market[base_market(market)]["recovered"] += 1

    n = tally["soft"] or 1
    print("\nAlternate-line coverage on the live NFL board")
    print(f"\n  {'soft two-way quotes':26s} {tally['soft']:>7,}")
    print(f"  {'priced today (exact std)':26s} {tally['exact_std']:>7,}  "
          f"{100*tally['exact_std']/n:>5.1f}%")
    print(f"  {'exact ALT line':26s} {tally['exact_alt']:>7,}  "
          f"{100*tally['exact_alt']/n:>5.1f}%")
    print(f"  {'inside the alt ladder':26s} {tally['bracketed']:>7,}  "
          f"{100*tally['bracketed']/n:>5.1f}%")
    print(f"  {'RECOVERED':26s} {tally['recovered']:>7,}  "
          f"{100*tally['recovered']/n:>5.1f}%   <- new")

    print(f"\n  {'market':28s} {'soft':>7s} {'today':>7s} {'alt=':>7s} "
          f"{'in ladder':>10s} {'recovered':>10s}")
    for m, d in sorted(by_market.items(), key=lambda kv: -kv[1]["soft"]):
        print(f"  {m:28s} {d['soft']:>7,} {d['exact_std']:>7,} "
              f"{d['exact_alt']:>7,} {d['bracketed']:>10,} {d['recovered']:>10,}")
    print("\n  Coverage only. An alternate rung is ONE-SIDED, so it gives the "
          "ladder's\n  SHAPE; the standard two-way quote is what levels it.\n")


if __name__ == "__main__":
    main()
