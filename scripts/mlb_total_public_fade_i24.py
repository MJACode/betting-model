"""I24 remesure + tighten-only sweep on the fade-finder as-of.

WHY THIS EXISTS
---------------
The documented I24 cell (docs/mlb_total_public_fade.md) claimed n=38
+9.51u +25% on t80 + shopped under in [−110, −100]. The mlb_over_under
hunt (PR #758) then printed an I24-shaped juice cell at n=37 −34.2% on
a *different* shop (latest-open both-sides at the latest equal DK line).
Those are not the same board. This script remesures I24 on the **fade
finder** (`find_fade_bets`: DK open total, shop DK/FD/MGM/WH, leak-
bounded `snapshot_type='open'` AND `snapshot_at <= commence_time`) and
asks whether any **tighten-only** neighbour beats the live card.

Live I24 (Railway, PUBLISH=1 — do not weaken from this file):
  TICKET_PCT=80, UNDER_ODDS_MIN=-110, UNDER_ODDS_MAX=-100,
  MAX_PER_SLATE=2, RANK=ticket, slate concentration suppress-all.

A proposed upgrade must be strictly tighter (higher ticket, narrower
juice, smaller K, or a concentration that fires on fewer slates),
month-stable +ROI, n≥40, low max/day. Exploratory cards stay
PUBLISH=0. This script writes nothing to `picks`.

    python -m scripts.mlb_total_public_fade_i24
    python -m scripts.mlb_total_public_fade_i24 --json /tmp/fade_bt.json

`--json` is a sandbox cache of the Supabase pull (splits + leak-bounded
opens). Same shape as `scripts.mlb_total_public_fade_topk`.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.mlb_total_public_fade as fade
from models.market_relative import implied
from scripts.mlb_total_public_fade_topk import (
    american_units,
    grade_under,
    load_db,
    load_json,
    shop_quotes,
    summarize,
    take,
    _fmt,
)

# Live I24. Do not widen any of these from a cell in this file.
LIVE_TICKET = 80.0
LIVE_ODDS_MIN = -110.0
LIVE_ODDS_MAX = -100.0
LIVE_K = 2
LIVE_RANK = fade.RANK_TICKET


def build_finder_candidates(
    splits: list[dict],
    quotes: list[dict],
    *,
    min_over_tickets: float,
    under_odds_min: float | None,
    under_odds_max: float | None,
    include_unsettled: bool = False,
) -> tuple[list[dict], dict]:
    """Grade finder bets. Band is passed into `find_fade_bets`, not invented here."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        qmap[q["game_id"]][q["book"]] = {
            "total_line": q["line"],
            "under_price": q["under_price"],
            "over_price": q.get("over_price"),
            "snapshot_at": q.get("snapshot_at"),
        }
    split_map = {}
    meta = {}
    for s in splits:
        gid = s["game_id"]
        split_map[gid] = {
            "game_id": gid,
            "ticket": float(s["over_tix"]),
            "public_bet_pct": float(s["over_tix"]),
            "public_money_pct": (
                None if s.get("over_money") is None else float(s["over_money"])
            ),
            "snapshot_at": s.get("public_snap") or "2026-06-15T16:00:00-04:00",
            "commence_time": s.get("commence_time") or "2026-06-15T23:10:00+00:00",
        }
        meta[gid] = s
    quotes_flat = {}
    for gid, books in qmap.items():
        quotes_flat.update(shop_quotes(qmap, gid))
    bets, diag = fade.find_fade_bets(
        split_map,
        quotes_flat,
        min_over_tickets=min_over_tickets,
        under_odds_min=under_odds_min,
        under_odds_max=under_odds_max,
    )
    rows = []
    n_unsettled = 0
    for b in bets:
        m = meta[b.game_id]
        result, units = grade_under(b.line, b.price, m.get("hs"), m.get("aws"))
        if result is None:
            n_unsettled += 1
            if not include_unsettled:
                continue
            result, units = "UNSETTLED", 0.0
        rows.append({
            "game_id": b.game_id,
            "game_date": m["game_date"],
            "month": str(m["game_date"])[:7],
            "bet": b,
            "result": result,
            "units": units,
            "over_tix": b.over_ticket_pct,
            "over_money": b.over_money_pct,
            "price": b.price,
            "line": b.line,
            "book": b.book,
            "implied": implied(b.price),
            "has_over": _has_over_on_book(qmap, b.game_id, b.book, b.line),
        })
    diag = dict(diag)
    diag["unsettled"] = n_unsettled
    return rows, diag


def _has_over_on_book(qmap: dict, gid: str, book: str, line: float) -> bool:
    """True when the shopped book also posts an over at the same total.

    The PR #758 I24-shaped cell required both sides. The fade finder
    does not — it shops the under only. This flag lets the remesure
    name the intersection difference without inventing a new shop.
    """
    q = (qmap.get(gid) or {}).get(book) or {}
    over = q.get("over_price")
    qline = q.get("total_line")
    if over is None or qline is None:
        return False
    try:
        return float(qline) == float(line) and float(over) == float(over)
    except (TypeError, ValueError):
        return False


def numeric_band(rows: list[dict], lo: float, hi: float) -> list[dict]:
    """American numeric compare `lo <= price <= hi`. Drops +100 when hi=-100.

    The finder band is implied-space; this is the shop-replay filter that
    treats +100 as outside [−110, −100]. Used only to reconcile boards.
    """
    return [r for r in rows if lo <= float(r["price"]) <= hi]


def apply_live_card(rows: list[dict], *, k: int = LIVE_K) -> list[dict]:
    """ticket top-K then suppress-all. After K=2 the n≥4 guard is a no-op."""
    ranked = take(rows, kind=LIVE_RANK, k=k)
    return fade_suppress_all(ranked)


def fade_suppress_all(rows: list[dict], min_bets: int = 4) -> list[dict]:
    """Replay `apply_slate_guard` policy=suppress_all (one-side ≥70% & n≥min).

    This card is always UNDER, so the side% test is always 100%. The live
    helper uses min_bets=4. After ticket top-2, n_bet ≤ 2 and the guard
    never fires — measured here so a remesure does not invent a cut.
    """
    by = defaultdict(list)
    for r in rows:
        by[r["game_date"]].append(r)
    keep = []
    for group in by.values():
        if len(group) >= min_bets:
            continue
        keep.extend(group)
    return keep


def month_print(rows: list[dict]) -> str:
    months = sorted({r["month"] for r in rows})
    parts = []
    for m in months:
        s = summarize([r for r in rows if r["month"] == m])
        if s["n"] == 0:
            parts.append(f"{m} n=0")
        else:
            parts.append(f"{m} {100*s['roi']:+.1f}%/{s['n']}")
    return ", ".join(parts) if parts else "n/a"


def is_tighter(
    *,
    ticket: float,
    odds_min: float,
    odds_max: float,
    k: int,
    conc_min: int,
) -> bool:
    """True when every live guard is at least as tight and one is tighter.

    Juice tightness is implied-space: a higher (less juicy) min or a
    lower (more juicy / less plus) max is tighter. K smaller is tighter.
    Concentration min_bets smaller fires more often (tighter).
    """
    if ticket < LIVE_TICKET:
        return False
    if implied(odds_min) is None or implied(LIVE_ODDS_MIN) is None:
        return False
    if implied(odds_min) > implied(LIVE_ODDS_MIN):
        return False
    if implied(odds_max) is None or implied(LIVE_ODDS_MAX) is None:
        return False
    if implied(odds_max) < implied(LIVE_ODDS_MAX):
        return False
    if k <= 0 or k > LIVE_K:
        return False
    if conc_min > 4 or conc_min < 1:
        return False
    tighter = (
        ticket > LIVE_TICKET
        or implied(odds_min) < implied(LIVE_ODDS_MIN)
        or implied(odds_max) > implied(LIVE_ODDS_MAX)
        or k < LIVE_K
        or conc_min < 4
    )
    return tighter


def cell_clears(s: dict, rows: list[dict]) -> bool:
    """Upgrade bar: n≥40, ROI>0, every populated month green, max/day≤2."""
    if s["n"] < 40:
        return False
    if not (s["roi"] == s["roi"]) or s["roi"] <= 0:
        return False
    if s["max_per_day"] > 2:
        return False
    months = sorted({r["month"] for r in rows})
    populated = 0
    for m in months:
        chunk = [r for r in rows if r["month"] == m]
        ms = summarize(chunk)
        if ms["n"] == 0:
            continue
        populated += 1
        if ms["roi"] <= 0:
            return False
    return populated >= 2


def report(splits: list[dict], quotes: list[dict]) -> dict:
    settled_splits = [s for s in splits if s.get("hs") is not None and s.get("aws") is not None]
    print("=== coverage ===")
    print(f"pre-commence splits: {len(splits)}  settled: {len(settled_splits)}  "
          f"quotes: {len(quotes)}  games-with-quote: {len({q['game_id'] for q in quotes})}")
    by_m = defaultdict(lambda: [0, 0])
    for s in splits:
        m = str(s["game_date"])[:7]
        by_m[m][0] += 1
        if s.get("hs") is not None:
            by_m[m][1] += 1
    for m in sorted(by_m):
        print(f"  {m}  pre={by_m[m][0]} settled={by_m[m][1]}")
    print("  August public: empty (last-upsert overwrite). May: empty.")

    # Finder universe at t80, no band — the pool I24 cuts from.
    t80_any, d80 = build_finder_candidates(
        settled_splits, quotes, min_over_tickets=80.0,
        under_odds_min=None, under_odds_max=None)
    print(f"\n=== finder t80 any-juice (diag {d80}) ===")
    print(f"  all-pass  {_fmt(summarize(t80_any))}  {month_print(t80_any)}")

    # Documented I24 claim: t80 + implied band, all-pass (no top-K in the table).
    claimed, d_i24 = build_finder_candidates(
        settled_splits, quotes, min_over_tickets=LIVE_TICKET,
        under_odds_min=LIVE_ODDS_MIN, under_odds_max=LIVE_ODDS_MAX)
    print(f"\n=== documented I24 cell (t80 + implied band, all-pass) ===")
    print(f"  finder implied-band  {_fmt(summarize(claimed))}  {month_print(claimed)}")
    print(f"  diag {d_i24}")

    numeric = numeric_band(t80_any, LIVE_ODDS_MIN, LIVE_ODDS_MAX)
    print(f"  numeric lo<=price<=hi (drops +100)  {_fmt(summarize(numeric))}  {month_print(numeric)}")
    both = [r for r in claimed if r["has_over"]]
    print(f"  finder band ∩ shopped-book has over  {_fmt(summarize(both))}  {month_print(both)}")
    plus = [r for r in claimed if r["price"] > 0]
    print(f"  of implied-band, plus-money (+100)   {_fmt(summarize(plus))}")

    live = apply_live_card(claimed, k=LIVE_K)
    print(f"\n=== live I24 card (band then ticket top-2 then suppress-all n≥4) ===")
    print(f"  LIVE  {_fmt(summarize(live))}  {month_print(live)}")
    live_top2_only = take(claimed, kind=LIVE_RANK, k=2)
    print(f"  top-2 no guard (same; guard is no-op at K=2)  {_fmt(summarize(live_top2_only))}")

    print("\n=== tighten-only neighbours ===")
    grid = []
    tickets = (80.0, 85.0, 90.0, 95.0)
    bands = (
        (-110.0, -100.0, "live[-110,-100]"),
        (-110.0, -105.0, "[-110,-105]"),
        (-110.0, -102.0, "[-110,-102]"),
        (-108.0, -100.0, "[-108,-100]"),
        (-105.0, -100.0, "[-105,-100]"),
    )
    ks = (1, 2)
    concs = (4, 3, 2)
    seen = set()
    for ticket in tickets:
        for lo, hi, blabel in bands:
            pool, _ = build_finder_candidates(
                settled_splits, quotes, min_over_tickets=ticket,
                under_odds_min=lo, under_odds_max=hi)
            for k in ks:
                ranked = take(pool, kind=LIVE_RANK, k=k)
                for cmin in concs:
                    # A conc floor above K never fires — do not count it
                    # as tighter than the live K=2 / n≥4 guard.
                    effective_conc = cmin if cmin <= k else 4
                    if not is_tighter(ticket=ticket, odds_min=lo, odds_max=hi,
                                      k=k, conc_min=effective_conc):
                        continue
                    key = (ticket, lo, hi, k, effective_conc)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows = fade_suppress_all(ranked, min_bets=cmin) if cmin <= k else ranked
                    s = summarize(rows)
                    label = f"t{ticket:.0f} {blabel} top-{k}"
                    if cmin <= k:
                        label += f" conc≥{cmin}"
                    clears = cell_clears(s, rows)
                    grid.append((label, s, rows, clears, ticket, lo, hi, k, cmin))
                    flag = "CLEAR" if clears else "miss"
                    print(f"  {flag:<5s} {label:<42s} {_fmt(s)}  {month_print(rows)}")

    print("\n=== live I24 by day (settled) ===")
    by = defaultdict(list)
    for r in live:
        by[r["game_date"]].append(r)
    for d in sorted(by):
        print(f"  {d}  {_fmt(summarize(by[d]))}  " +
              ", ".join(f"{x['game_id'][-7:]}@{x['price']:+.0f} t{x['over_tix']:.0f} {x['result']}"
                        for x in sorted(by[d], key=lambda z: -z["over_tix"])))

    clears = [g for g in grid if g[3]]
    print(f"\n=== upgrade verdict ===")
    print(f"tighten cells measured: {len(grid)}  clearing bar: {len(clears)}")
    if not clears:
        print("no tighten-only upgrade clears n≥40 + month-stable +ROI + max/day≤2.")
        print("do not recut live I24. do not flip PUBLISH. pause this family until new public.")
    else:
        for label, s, rows, *_ in clears:
            print(f"  CANDIDATE {label}  {_fmt(s)}  {month_print(rows)}")
        print("any candidate stays PUBLISH=0 until Michael approves.")
    return {
        "claimed": summarize(claimed),
        "live": summarize(live),
        "numeric": summarize(numeric),
        "n_clears": len(clears),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", default=None,
                    help="splits+quotes JSON (sandbox cache of Supabase)")
    args = ap.parse_args()
    if args.json:
        splits, quotes = load_json(args.json)
        print(f"loaded --json {args.json}: {len(splits)} splits, "
              f"{len(quotes)} quotes")
    else:
        splits, quotes = load_db()
        print(f"loaded DB: {len(splits)} splits, {len(quotes)} quotes")
    report(splits, quotes)


if __name__ == "__main__":
    main()
