"""Two sharp references instead of one: does agreement between them pay more?

WHERE THIS COMES FROM. §5c established Pinnacle as the sharp reference and
proved it with a placebo — swapping in any retail book destroys the result. The
extended sweep then found a SECOND book that clears the same bar: betonlineag,
840 bets, +7.68%, positive in all three seasons, reproduced by no retail book.
The doc recorded it and used it only to ask whether it opens the markets
Pinnacle declines (it does not: −4.97% there).

Nobody has asked the other question. If two independent market makers BOTH
disagree with the same soft price, that is stronger evidence than one doing so —
the single-reference version cannot tell "the soft book is wrong" from "this
particular sharp book is wrong". A consensus filter should trade volume for
precision, and the whole failure mode of every model in this repo has been the
opposite: plenty of volume, no precision.

Four selections, graded identically so they are comparable:

    pinnacle        the rule as it ships today
    betonlineag     the same rule, other reference
    either          a bet if EITHER reference disagrees by the threshold
    BOTH            a bet only where BOTH do, on the same side

`both` is the hypothesis. `either` is the control that says whether any gain is
consensus or just more volume.

Everything else is the shipped rule: equal lines only, pre-game quotes, one bet
per proposition, real DraftKings-side prices, and the same 5pp starting point.

    python -m scripts.nfl_prop_two_sharps
    python -m scripts.nfl_prop_two_sharps --min-edge 0.04
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

REF_A, REF_B = "pinnacle", "betonlineag"


# The SHARED implementations, not local copies. The local ones drifted exactly
# as §1b predicts: they guarded `is None` and not NaN, so a one-way quote from
# the pandas cache produced nan probabilities, and because `nan < min_edge` is
# False this script's filter let those through as bets while the production
# path's `nan >= min_edge` correctly dropped them. Same maths, opposite
# behaviour, from two copies of four lines.
from models.market_relative import devig, implied  # noqa: E402


def profit(price, won) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def _actuals(df):
    out = {}
    for r in df.itertuples(index=False):
        out[(norm_player_name(r.player_name), r.game_id)] = r
    return out


def build(min_edge: float, snapshot: str | None = None,
          refs: tuple[str, str] = (REF_A, REF_B),
          only_games_with: str | None = None):
    """-> {selection: [(season, profit)]} plus a diagnostic count.

    `snapshot` pins the board to ONE offset. Without it the grader takes the
    newest pre-game quote of any type, and which type that is varies by season:
    2023 sharp quotes were `open` until the T-48h backfill landed, after which
    they became `t48`. That silently confounds the season split with the offset,
    so a season row answers "which year" and "measured how far out" at once.
    Pinning the offset is what makes the seasons comparable.
    """
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    act = _actuals(local_store.read_table("nfl_player_game_log"))
    ko = {r.game_id: r.commence_time for r in
          local_store.read_table("nfl_team_game_stats",
                                 columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).itertuples(index=False)}

    # newest PRE-GAME quote per (game, player, market, book, line)
    # PAIRING. Comparing two offsets across all games compares two different
    # GAME SETS as well: the production `open` series covers 868 games, the
    # T-48h backfill 433. Restricting both arms to the games that carry the
    # named series makes the offset the only thing that differs.
    if only_games_with:
        keep = set(odds.loc[odds.snapshot_type == only_games_with, "game_id"])
        odds = odds[odds.game_id.isin(keep)]

    latest = {}
    for r in odds.itertuples(index=False):
        if r.market not in mk.SHARP_MARKETS or r.line is None:
            continue
        if snapshot is not None and r.snapshot_type != snapshot:
            continue
        k_off = ko.get(r.game_id)
        if k_off is not None and str(r.snapshot_at) > str(k_off):
            continue
        key = (r.game_id, norm_player_name(r.player_name), r.market,
               float(r.line), r.bookmaker)
        prev = latest.get(key)
        if prev is None or str(r.snapshot_at) > str(prev.snapshot_at):
            latest[key] = r

    by_prop = defaultdict(dict)
    for (gid, player, market, line, book), r in latest.items():
        by_prop[(gid, player, market, line)][book] = r

    # ONE BET PER PROPOSITION, exactly as models.nfl_prop_market.best_per_prop
    # does for the live card. The same prop offered at eight books is EIGHT
    # COPIES OF ONE OPINION, and counting them separately both inflates the bet
    # count and correlates the outcomes -- the first run of this script did that
    # and reported 1,083 "bets" that were really a few hundred propositions.
    # Keyed on (game, player, market, side) and keeping the best edge.
    staged = defaultdict(dict)
    diag = defaultdict(int)
    for (gid, player, market, line), books in by_prop.items():
        stat = mk.MARKET_STAT.get(market)
        row = act.get((player, gid))
        if stat is None or row is None:
            diag["no_actual"] += 1
            continue
        actual = mk.market_actual(row, market) if hasattr(mk, "market_actual") \
            else getattr(row, stat, None)
        if actual is None or float(actual) == line:
            continue
        went_over = float(actual) > line
        season = str(gid).split("_")[1] if "_" in str(gid) else "?"

        fair = {}
        for ref in refs:
            q = books.get(ref)
            if q is None:
                continue
            fo, fu = devig(q.over_price, q.under_price)
            if fo is not None:
                fair[ref] = (fo, fu)
        if not fair:
            diag["no_sharp"] += 1
            continue

        for book, q in books.items():
            # A reference is never also a bettable book: betting into it is
            # betting into our own number, and the placebo below depends on the
            # two sets staying disjoint even when a retail book stands in.
            if book not in mk.SOFT_BOOKS or book in refs:
                continue
            so, su = devig(q.over_price, q.under_price)
            if so is None:
                continue
            for side, soft_p, price in (("over", so, q.over_price),
                                        ("under", su, q.under_price)):
                edges = {}
                for ref, (fo, fu) in fair.items():
                    ref_p = fo if side == "over" else fu
                    edges[ref] = ref_p - soft_p
                won = went_over if side == "over" else not went_over
                p = profit(price, won)
                hits = {r for r, e in edges.items() if e >= min_edge}
                prop = (gid, player, market, side)
                best_edge = max(edges.values())
                for name, qualifies in ((refs[0], refs[0] in hits),
                                        (refs[1], refs[1] in hits),
                                        ("either", bool(hits)),
                                        ("BOTH", len(hits) == 2)):
                    if not qualifies:
                        continue
                    prev = staged[name].get(prop)
                    if prev is None or best_edge > prev[0]:
                        staged[name][prop] = (best_edge, season, p)

    sel = defaultdict(list)
    for name, props in staged.items():
        for _edge, season, p in props.values():
            sel[name].append((season, p))
    return sel, diag


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-edge", type=float, default=0.05)
    ap.add_argument("--snapshot", default=None,
                    help="pin the board to one offset: open, t48, t24, t1")
    ap.add_argument("--only-games-with", default=None,
                    help="keep only games carrying this snapshot series "
                         "(pairs two offsets on one game set)")
    ap.add_argument("--refs", default=f"{REF_A},{REF_B}",
                    help="the two reference books (the placebo swaps in retail)")
    a = ap.parse_args()
    rng = np.random.default_rng(42)
    refs = tuple(x.strip() for x in a.refs.split(","))
    sel, diag = build(a.min_edge, a.snapshot, refs, a.only_games_with)

    print(f"\nNFL props — two sharp references, min edge {a.min_edge:.0%}")
    print(f"soft books: {len(mk.SOFT_BOOKS)}   markets: {len(mk.SHARP_MARKETS)}\n")
    print(f"{'selection':16s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} "
          f"{'90% CI':>18}  by season")
    print("-" * 96)
    for name in (refs[0], refs[1], "either", "BOTH"):
        rows = sel.get(name) or []
        if len(rows) < 40:
            print(f"{name:16s} {len(rows):>6}   (thin)")
            continue
        prof = np.array([p for _s, p in rows])
        idx = rng.integers(0, len(prof), (20000, len(prof)))
        roi = 100 * prof[idx].mean(axis=1)
        lo, hi = np.percentile(roi, 5), np.percentile(roi, 95)
        w = int((prof > 0).sum())
        per = []
        for s in sorted({s for s, _p in rows}):
            sub = [p for ss, p in rows if ss == s]
            per.append(f"{s}:{100*np.mean(sub):+.1f}%({len(sub)})")
        print(f"{name:16s} {len(prof):>6} {100*w/len(prof):>5.1f}% "
              f"{prof.sum():>+9.2f} {100*prof.mean():>+7.2f}% "
              f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>18}  {' '.join(per)}")


if __name__ == "__main__":
    main()
