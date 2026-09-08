"""Does the market-relative rule beat the closing number?

WHY THIS IS WORTH MORE THAN ANOTHER ROI NUMBER. The rule's record rests on
~2,000 graded bets, and at that size a real +6.89% and a lucky +6.89% look
identical. Closing line value is the independent check: it asks whether the
price was WRONG when we took it, and the answer does not depend on whether the
bet won. A strategy with genuine edge beats the close; one riding variance does
not. §5c's placebo answered "is the signal real"; this answers "was the number
actually good", and those are different questions.

WHY LINE CLV AND NOT PRICE CLV, learned by getting it wrong twice:

  * Holding the LINE fixed and differencing prices is correct for a market whose
    number does not move. Props are not that market -- of 253 qualifying bets
    only FIVE still had a quote at the same line by kickoff. The number moves,
    so the proposition we bet stops existing and there is nothing to difference.
  * Before that, "the latest quote per key" resolved to the bet's own row
    whenever nothing later existed, so the script differenced each price against
    itself and reported a median CLV of exactly +0.00pp across 99.6% of bets. A
    measurement that returns zero by construction is worse than no measurement,
    because it reads as a finding.

So this measures what picks.line_clv_pts already measures: did the NUMBER move
our way? For an over at 4.5, a close of 3.5 is +1.0 points of value (the bet got
easier); 5.5 is -1.0. The sign is flipped for unders. Where the line did not
move, the price difference is reported separately -- that is real CLV too, just
rarer.

Positive means the market moved TOWARD us after we bet.

    python -m scripts.nfl_prop_clv
    python -m scripts.nfl_prop_clv --min-edge 0.04
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

import models.nfl_prop_market as mk
from data import local_store
from data.ingestors.nfl_props_data_ingestor import norm_player_name
from features.feature_engine import _parse_iso_ts
from models.market_relative import devig, implied


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-edge", type=float, default=0.05)
    a = ap.parse_args()

    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    ko = {r.game_id: r.commence_time for r in
          local_store.read_table("nfl_team_game_stats",
                                 columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).itertuples(index=False)}

    # at_bet keys on the LINE (a proposition is a number as well as a player).
    # later keys WITHOUT it, because the line moving is the thing being measured.
    at_bet: dict = {}
    later: dict = defaultdict(list)
    for r in odds.itertuples(index=False):
        if r.market not in mk.SHARP_MARKETS or r.line is None:
            continue
        # PARSED, NOT STRING-COMPARED. snapshot_at renders as
        # '2024-09-21T16:55:38Z' and commence_time as
        # '2024-09-22 17:00:00+00:00'; at position 10 that is 'T' (84) against
        # ' ' (32), so EVERY same-day quote compares as greater and was dropped
        # as post-kickoff. That silently deleted exactly the closing quotes and
        # left 5 of 253 bets with anything to close against -- the §7 trap
        # ("parse timestamps before comparing them"), walked into in the one
        # script whose whole job is comparing two timestamps.
        snap_dt = _parse_iso_ts(r.snapshot_at)
        kick_dt = _parse_iso_ts(ko.get(r.game_id))
        if snap_dt is not None and kick_dt is not None and snap_dt > kick_dt:
            continue                        # post-kickoff quote is not a price
        player = norm_player_name(r.player_name)
        if r.snapshot_type == "t24":
            k = (r.game_id, player, r.market, float(r.line), r.bookmaker)
            prev = at_bet.get(k)
            if prev is None or snap_dt > _parse_iso_ts(prev.snapshot_at):
                at_bet[k] = r
        later[(r.game_id, player, r.market, r.bookmaker)].append(r)

    by_prop = defaultdict(dict)
    for (gid, player, market, line, book), r in at_bet.items():
        by_prop[(gid, player, market, line)][book] = r

    rows = []
    no_close = 0
    for (gid, player, market, line), books in by_prop.items():
        fair = {}
        for ref in mk.SHARP_BOOKS:
            q = books.get(ref)
            if q is None:
                continue
            fo, fu = devig(q.over_price, q.under_price)
            if fo is not None:
                fair[ref] = (fo, fu)
        if not fair:
            continue
        for book, q in books.items():
            if book not in mk.SOFT_BOOKS:
                continue
            so, su = devig(q.over_price, q.under_price)
            if so is None:
                continue
            for side, soft_p, price in (("over", so, q.over_price),
                                        ("under", su, q.under_price)):
                edge = max((f[0] if side == "over" else f[1]) - soft_p
                           for f in fair.values())
                if edge < a.min_edge:
                    continue
                taken_at = _parse_iso_ts(q.snapshot_at)
                after = [x for x in later[(gid, player, market, book)]
                         if x.line is not None
                         and (_parse_iso_ts(x.snapshot_at) or taken_at) > taken_at]
                if not after:
                    no_close += 1
                    continue
                close = max(after, key=lambda x: _parse_iso_ts(x.snapshot_at))
                # SIGN: positive means WE got the better number. An OVER
                # taken at 4.5 that closes at 5.5 is +1.0 -- anyone betting the
                # over at the close needs a bigger number than we do. An UNDER
                # is the mirror. The first version had this inverted and read
                # the market correcting TOWARD us as evidence against the rule.
                move = float(close.line) - float(line)
                pts = move if side == "over" else -move
                dprice = None
                if float(close.line) == float(line):
                    cp = close.over_price if side == "over" else close.under_price
                    ic, it = implied(cp), implied(price)
                    if ic is not None and it is not None:
                        dprice = ic - it
                rows.append((str(gid).split("_")[1], market, pts, dprice))

    if not rows:
        print("no bets with a later quote to close against")
        return

    pts = np.array([r[2] for r in rows])
    rng = np.random.default_rng(42)
    idx = rng.integers(0, len(pts), (20000, len(pts)))
    boot = pts[idx].mean(axis=1)
    same = np.array([r[3] for r in rows if r[3] is not None])

    print(f"\nNFL prop rule — closing LINE value at {a.min_edge:.0%}")
    print(f"  {len(rows)} bets with a later quote ({no_close} without)")
    print(f"  mean line move   {pts.mean():+.3f} pts   "
          f"90% CI ({np.percentile(boot, 5):+.3f}, {np.percentile(boot, 95):+.3f})")
    print(f"  median           {np.median(pts):+.3f} pts")
    print(f"  moved our way    {100*(pts > 0).mean():.1f}%  |  "
          f"against {100*(pts < 0).mean():.1f}%  |  "
          f"unchanged {100*(pts == 0).mean():.1f}%")
    if len(same):
        print(f"  where the line held ({len(same)} bets): price CLV "
              f"{100*same.mean():+.2f}pp, beat close {100*(same > 0).mean():.1f}%")
    print("\n  Positive = the market moved TOWARD us after we bet.\n")

    print(f"{'season':>8} {'bets':>6} {'mean pts':>10} {'our way':>10}")
    for s in sorted({r[0] for r in rows}):
        sub = np.array([r[2] for r in rows if r[0] == s])
        print(f"{s:>8} {len(sub):>6} {sub.mean():>+10.3f} "
              f"{100*(sub > 0).mean():>9.1f}%")

    print(f"\n{'market':>26} {'bets':>6} {'mean pts':>10} {'our way':>10}")
    for m in sorted({r[1] for r in rows}):
        sub = np.array([r[2] for r in rows if r[1] == m])
        if len(sub) < 20:
            continue
        print(f"{m:>26} {len(sub):>6} {sub.mean():>+10.3f} "
              f"{100*(sub > 0).mean():>9.1f}%")


if __name__ == "__main__":
    main()
