"""Does an ANCHORED LADDER price better than a single sharp line?

THE QUESTION. `models/nfl_prop_market` compares a de-vigged sharp price against
a soft price at the SAME line, and discards everything else -- 63,676 NFL
propositions. `scripts/alt_ladder_probe` measured that the alternate lines we
already store would recover 19.3% of the live soft board. This asks the only
question that matters after coverage: are the recovered bets any good?

HOW THE FAIR VALUE IS BUILT, and why it is not just "read the alternate":

  1. The sharp book's ALTERNATE quotes are ONE-SIDED (every one of the 98,036
     `player_reception_yds_alternate` rows has an over price and no under), so
     their implied probabilities carry the book's margin. They give SHAPE.
  2. The same book's STANDARD market IS two-way, so de-vigging it gives one
     honest probability at one line. That gives LEVEL.
  3. `Ladder.anchored` shifts the vigged ladder in logit space onto that point.

So a fair value exists wherever the sharp book quotes a two-way standard line
AND an alternate ladder that brackets the soft book's number.

PINNACLE POSTS NO ALTERNATES, measured 2026-09-08. The ladder reference is
betonlineag alone, which is a materially narrower base than the shipped
two-reference rule and may well be what limits the result. Stated here so a
weak number is read as "one book" rather than "the idea does not work".

HELD TO THE SAME BAR AS §5c, because a construction that changes what gets bet
has to clear it: a plateau across cuts rather than one cell, positive in every
season, an interval excluding zero, and a placebo where a retail book stands in
as the reference. Anything less and this stays a coverage statistic.

    python -m scripts.nfl_prop_ladder_grade
    python -m scripts.nfl_prop_ladder_grade --ref betonlineag --min-edge 0.05
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
from models.prop_ladder import from_one_sided_overs


def base_market(m: str) -> str:
    return m[: -len("_alternate")] if m.endswith("_alternate") else m


def profit(price, won: bool) -> float:
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def _nn(v):
    """None for a NaN. The pandas cache hands back float('nan') where psycopg2
    hands back None, and `nan >= cut` is False while `nan` also passes an
    `is not None` test -- the drift that once let one-way quotes through."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if f != f else f


def build(min_edge: float, ref: str, soft_books: tuple[str, ...],
          snapshot: str = "open"):
    local_store.activate()
    odds = local_store.read_table("nfl_prop_odds")
    act = {(norm_player_name(r.player_name), r.game_id): r
           for r in local_store.read_table("nfl_player_game_log").itertuples(index=False)}
    ko = {r.game_id: r.commence_time for r in
          local_store.read_table("nfl_team_game_stats",
                                 columns=["game_id", "commence_time"])
          .dropna(subset=["commence_time"]).itertuples(index=False)}

    # Newest PRE-GAME quote per (prop, line, book, market-kind).
    latest: dict = {}
    for r in odds.itertuples(index=False):
        if r.snapshot_type != snapshot or r.line is None:
            continue
        bm = base_market(r.market)
        if bm not in mk.SHARP_MARKETS:
            continue
        s, k = _parse_iso_ts(r.snapshot_at), _parse_iso_ts(ko.get(r.game_id))
        if s is not None and k is not None and s > k:
            continue
        key = (r.game_id, norm_player_name(r.player_name), bm,
               r.market.endswith("_alternate"), float(r.line), r.bookmaker)
        prev = latest.get(key)
        if prev is None or s > _parse_iso_ts(prev.snapshot_at):
            latest[key] = r

    # Regroup per proposition.
    sharp_std: dict = {}                       # (prop) -> (line, fair_over)
    sharp_alt: dict = defaultdict(list)        # (prop) -> [(strike, over_price)]
    soft: dict = defaultdict(list)             # (prop) -> [(line, book, op, up)]
    for (gid, player, bm, is_alt, line, book), r in latest.items():
        op, up = _nn(r.over_price), _nn(r.under_price)
        prop = (gid, player, bm)
        if book == ref:
            if is_alt:
                if op is not None:
                    sharp_alt[prop].append((line, op))
            elif op is not None and up is not None:
                fo, _fu = devig(op, up)
                if fo is not None:
                    # THE TIGHTEST standard quote anchors the ladder, measured by
                    # its own overround. A book can hang several standard lines
                    # on one prop; the anchor is the single point where we claim
                    # to know the truth, so it should be the one where the book
                    # is charging least to tell us. Taking whichever arrived
                    # first -- as this did until the comment was checked against
                    # the code -- makes the fair value depend on dict ordering.
                    io, iu = implied(op), implied(up)
                    vig = (io + iu) if io is not None and iu is not None else 9.9
                    prev = sharp_std.get(prop)
                    if prev is None or vig < prev[2]:
                        sharp_std[prop] = (line, fo, vig)
        elif book in soft_books and not is_alt and op is not None and up is not None:
            soft[prop].append((line, book, op, up))

    staged: dict = {}
    diag = defaultdict(int)
    for prop, quotes in soft.items():
        gid, player, bm = prop
        anchor = sharp_std.get(prop)
        rungs = sharp_alt.get(prop)
        if anchor is None:
            diag["no_anchor"] += 1
            continue
        if not rungs:
            diag["no_ladder"] += 1
            continue
        lad = from_one_sided_overs(rungs)
        if not lad.usable:
            diag["thin_ladder"] += 1
            continue
        anc = lad.anchored(anchor[0], anchor[1])
        if anc is None:
            diag["anchor_outside"] += 1
            continue

        stat = mk.MARKET_STAT.get(bm)
        row = act.get((player, gid))
        if stat is None or row is None:
            diag["no_actual"] += 1
            continue
        actual = getattr(row, stat, None)
        if actual is None:
            diag["no_actual"] += 1
            continue
        season = str(gid).split("_")[1] if "_" in str(gid) else "?"

        for line, book, op, up in quotes:
            if float(actual) == line:
                continue                       # push
            fair_over = anc.p_over(line)
            if fair_over is None:
                diag["outside_ladder"] += 1
                continue
            diag["priced"] += 1
            went_over = float(actual) > line
            for side, fair, price in (("over", fair_over, op),
                                      ("under", 1.0 - fair_over, up)):
                imp = implied(price)
                if imp is None:
                    continue
                edge = fair - imp
                if edge < min_edge:
                    continue
                won = went_over if side == "over" else not went_over
                # ONE BET PER PROPOSITION, as models.nfl_prop_market.best_per_prop
                # does: the same prop at six books is six copies of one opinion.
                k = (gid, player, bm, side)
                p = profit(price, won)
                if k not in staged or edge > staged[k][0]:
                    staged[k] = (edge, season, p)

    return [(s, p) for _e, s, p in staged.values()], diag


def grade(rows, rng, label):
    if len(rows) < 40:
        print(f"{label:24s} {len(rows):>6}   (thin)")
        return
    prof = np.array([p for _s, p in rows])
    idx = rng.integers(0, len(prof), (20000, len(prof)))
    roi = 100 * prof[idx].mean(axis=1)
    lo, hi = np.percentile(roi, 5), np.percentile(roi, 95)
    per = []
    for s in sorted({s for s, _p in rows}):
        sub = [p for ss, p in rows if ss == s]
        per.append(f"{s}:{100*np.mean(sub):+.1f}%({len(sub)})")
    print(f"{label:24s} {len(prof):>6} {100*(prof>0).mean():>5.1f}% "
          f"{prof.sum():>+9.2f} {100*prof.mean():>+7.2f}% "
          f"{'('+format(lo,'+.1f')+', '+format(hi,'+.1f')+')':>18}  {' '.join(per)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", default="betonlineag")
    ap.add_argument("--min-edge", type=float, default=None)
    ap.add_argument("--placebo", action="store_true",
                    help="stand a retail book in as the ladder reference")
    a = ap.parse_args()
    rng = np.random.default_rng(42)

    print(f"\nNFL props — ANCHORED LADDER off {a.ref} (alternates give shape, "
          f"the standard two-way gives level)")
    print(f"{'cut':24s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} "
          f"{'90% CI':>18}  by season")
    print("-" * 104)

    cuts = [a.min_edge] if a.min_edge is not None else [0.03, 0.04, 0.05, 0.06]
    for cut in cuts:
        soft = tuple(b for b in mk.SOFT_BOOKS if b != a.ref)
        rows, diag = build(cut, a.ref, soft)
        grade(rows, rng, f"cut {cut:.0%}")
    print(f"\n  diagnostics: {dict(diag)}")

    if a.placebo:
        print("\nTHE PLACEBO — a retail book as the ladder reference")
        print(f"{'reference':24s} {'bets':>6} {'win%':>6} {'units':>9} {'ROI':>8} "
              f"{'90% CI':>18}  by season")
        print("-" * 104)
        for stand_in in ("draftkings", "fanduel", "espnbet", "hardrockbet"):
            soft = tuple(b for b in mk.SOFT_BOOKS if b != stand_in)
            rows, _d = build(0.05, stand_in, soft)
            grade(rows, rng, stand_in)


if __name__ == "__main__":
    main()
