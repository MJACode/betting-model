"""Top-K / holdout sweep for the MLB totals public-fade card.

WHY THIS EXISTS
---------------
The t70 all-pass card is a whole-slate UNDER when public OVER tickets are
heavy. 2026-09-19 that was 12/12. This sweep ranks the same candidate
pool and keeps top-1 / top-2 per day, and asks whether a month-holdout
EV estimate or a juice/edge floor beats all-pass.

It does not write picks, does not flip PUBLISH, and does not unpause
mlb_over_under. Measure only.

    python -m scripts.mlb_total_public_fade_topk
    python -m scripts.mlb_total_public_fade_topk --json /tmp/fade_bt.json

`--json` is a cache of the Supabase rows this session already pulled
(splits + leak-bounded opens). The worker / Matt's machine can omit it
and load from the database.

Docs: docs/mlb_total_public_fade.md.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import models.mlb_total_public_fade as fade
from models.market_relative import implied

SOFT = fade.SOFT_BOOKS


def american_units(price: float, won: bool) -> float:
    """Flat 1-unit P&L. Matches paper_tracker profit_flat / 100."""
    if not won:
        return -1.0
    if price > 0:
        return float(price) / 100.0
    return 100.0 / abs(float(price))


def grade_under(line: float, price: float, hs, aws):
    if hs is None or aws is None:
        return None, None
    total = float(hs) + float(aws)
    if total == float(line):
        return "PUSH", 0.0
    won = total < float(line)
    return ("WIN" if won else "LOSS"), american_units(price, won)


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval on a win rate. n is decided bets (no pushes)."""
    if n <= 0:
        return (float("nan"), float("nan"))
    phat = wins / n
    denom = 1.0 + z * z / n
    centre = phat + z * z / (2.0 * n)
    spread = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return (centre - spread) / denom, (centre + spread) / denom


def summarize(rows: list[dict]) -> dict:
    decided = [r for r in rows if r["result"] in ("WIN", "LOSS")]
    pushes = [r for r in rows if r["result"] == "PUSH"]
    n = len(rows)
    units = sum(r["units"] for r in rows)
    wins = sum(1 for r in decided if r["result"] == "WIN")
    n_dec = len(decided)
    wr = (wins / n_dec) if n_dec else float("nan")
    roi = (units / n) if n else float("nan")
    lo, hi = wilson(wins, n_dec)
    days = {r["game_date"] for r in rows}
    max_day = 0
    if rows:
        by = defaultdict(int)
        for r in rows:
            by[r["game_date"]] += 1
        max_day = max(by.values())
    return {
        "n": n, "n_dec": n_dec, "pushes": len(pushes),
        "wins": wins, "wr": wr, "units": units, "roi": roi,
        "wr_lo": lo, "wr_hi": hi,
        "days": len(days), "max_per_day": max_day,
    }


def _fmt(s: dict) -> str:
    if s["n"] == 0:
        return "n=0"
    wr = "n/a" if s["n_dec"] == 0 else f"{100*s['wr']:.1f}%"
    ci = ""
    if s["n_dec"] and s["wr_lo"] == s["wr_lo"]:
        ci = f"  Wilson {100*s['wr_lo']:.0f}–{100*s['wr_hi']:.0f}%"
    return (
        f"n={s['n']:<3d}  {s['units']:+6.2f}u  ROI {100*s['roi']:+6.1f}%  "
        f"WR {wr} ({s['wins']}-{s['n_dec']-s['wins']}"
        f"{f', {s["pushes"]}p' if s['pushes'] else ''})  "
        f"days={s['days']} max/day={s['max_per_day']}{ci}"
    )


def shop_quotes(quotes_by_game: dict, gid: str) -> dict:
    """{(gid, book): quote-row} for find_fade_bets."""
    out = {}
    for bk, q in (quotes_by_game.get(gid) or {}).items():
        out[(gid, bk)] = q
    return out


def build_candidates(splits: list[dict], quotes: list[dict],
                     min_over_tickets: float) -> list[dict]:
    """One graded (or unsettled) fade per game that clears the shop window."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        qmap[q["game_id"]][q["book"]] = {
            "total_line": q["line"],
            "under_price": q["under_price"],
            "snapshot_at": q.get("snapshot_at"),
        }
    split_map = {}
    meta = {}
    for s in splits:
        gid = s["game_id"]
        split_map[gid] = {
            "game_id": gid,
            "ticket": s["over_tix"],
            "public_bet_pct": s["over_tix"],
            "public_money_pct": s.get("over_money"),
            "snapshot_at": s.get("public_snap") or "2026-06-15T16:00:00-04:00",
            "commence_time": s.get("commence_time") or "2026-06-15T23:10:00+00:00",
        }
        meta[gid] = s
    quotes_flat = {}
    for gid, books in qmap.items():
        quotes_flat.update(shop_quotes(qmap, gid))
    bets, _diag = fade.find_fade_bets(
        split_map, quotes_flat, min_over_tickets=min_over_tickets)
    rows = []
    for b in bets:
        m = meta[b.game_id]
        result, units = grade_under(b.line, b.price, m.get("hs"), m.get("aws"))
        if result is None:
            continue
        rows.append({
            "game_id": b.game_id,
            "game_date": m["game_date"],
            "month": m["game_date"][:7],
            "bet": b,
            "result": result,
            "units": units,
            "over_tix": b.over_ticket_pct,
            "over_money": b.over_money_pct,
            "price": b.price,
            "line": b.line,
            "implied": implied(b.price),
        })
    return rows


def bucket_win_rates(rows: list[dict]) -> dict:
    """Under win rate per ticket bucket. Pushes excluded. Plus an 'all' key."""
    bags: dict[tuple, list[int]] = defaultdict(list)
    for r in rows:
        if r["result"] not in ("WIN", "LOSS"):
            continue
        key = fade.ticket_bucket(r["over_tix"])
        if key is None:
            continue
        bags[key].append(1 if r["result"] == "WIN" else 0)
        bags[("all", "all")].append(1 if r["result"] == "WIN" else 0)
    return {k: (sum(v) / len(v) if v else float("nan")) for k, v in bags.items()}


def take(rows: list[dict], *, kind: str, k: int,
         ev_rates: dict | None = None,
         min_edge: float = 0.0,
         price_floor: float | None = None) -> list[dict]:
    """Rank `rows` and keep top-k per game_date. k<=0 is all-pass."""
    incoming = list(rows)
    if price_floor is not None:
        incoming = [r for r in incoming if r["price"] >= price_floor]
    rates = ev_rates or {}

    def ev_of(b):
        edge = fade.estimated_edge(b, rates)
        return float("-inf") if edge is None else edge

    bets = [r["bet"] for r in incoming]
    by_id = {r["game_id"]: r for r in incoming}
    kept_bets = fade.select_top_k(
        bets,
        max_per_slate=k,
        slate_of=lambda b: by_id[b.game_id]["game_date"],
        kind=kind,
        ev_of=ev_of if kind == fade.RANK_EV else None,
        min_edge=min_edge,
        bucket_win_rate=rates if min_edge > 0 else None,
    )
    return [by_id[b.game_id] for b in kept_bets]


def lomo_rates(rows: list[dict], holdout_month: str) -> dict:
    train = [r for r in rows if r["month"] != holdout_month]
    return bucket_win_rates(train)


def holdout_take(rows: list[dict], *, kind: str, k: int,
                 min_edge: float = 0.0) -> list[dict]:
    """Leave-one-month-out: rates from other months, apply to the held month."""
    out = []
    months = sorted({r["month"] for r in rows})
    for m in months:
        rates = lomo_rates(rows, m)
        chunk = [r for r in rows if r["month"] == m]
        out.extend(take(chunk, kind=kind, k=k, ev_rates=rates,
                        min_edge=min_edge))
    return out


def suppress_all(rows: list[dict], min_bets: int = 4) -> list[dict]:
    """Replay the 2026-09-19 guard: drop any day with n ≥ 4."""
    by = defaultdict(list)
    for r in rows:
        by[r["game_date"]].append(r)
    keep = []
    for group in by.values():
        if len(group) < min_bets:
            keep.extend(group)
    return keep


def thin_slates(rows: list[dict], max_n: int = 3) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[r["game_date"]].append(r)
    keep = []
    for group in by.values():
        if len(group) <= max_n:
            keep.extend(group)
    return keep


def load_json(path: str) -> tuple[list[dict], list[dict]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return raw["splits"], raw["quotes"]


def load_db():
    from data.db import get_connection
    conn = get_connection()
    try:
        pb = conn.execute("""
            SELECT pb.game_id, pb.public_bet_pct, pb.public_money_pct,
                   pb.snapshot_at, g.commence_time, g.game_date,
                   g.home_score, g.away_score
            FROM public_betting pb
            JOIN games g ON g.game_id = pb.game_id
            WHERE pb.market = 'totals' AND pb.side = 'over'
              AND pb.book = 'consensus' AND g.sport = 'MLB'
              AND pb.snapshot_at IS NOT NULL
              AND g.commence_time IS NOT NULL
              AND pb.snapshot_at::timestamptz < g.commence_time::timestamptz
        """).fetchall()
        latest = {}
        for r in pb:
            gid = r[0]
            prev = latest.get(gid)
            if prev is None or str(r[3]) >= str(prev["public_snap"]):
                latest[gid] = {
                    "game_id": gid, "over_tix": float(r[1]),
                    "over_money": None if r[2] is None else float(r[2]),
                    "public_snap": r[3], "commence_time": r[4],
                    "game_date": r[5],
                    "hs": None if r[6] is None else float(r[6]),
                    "aws": None if r[7] is None else float(r[7]),
                }
        gids = list(latest)
        if not gids:
            return [], []
        qrows = conn.execute("""
            SELECT DISTINCT ON (o.game_id, o.bookmaker)
                   o.game_id, o.bookmaker, o.total_line, o.under_price
            FROM odds o
            JOIN games g ON g.game_id = o.game_id
            WHERE o.sport = 'MLB' AND o.market = 'totals'
              AND o.snapshot_type = 'open'
              AND o.bookmaker IN ('draftkings','fanduel','betmgm','williamhill_us')
              AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
              AND o.game_id = ANY(%s)
            ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
        """, (gids,)).fetchall()
        quotes = []
        for r in qrows:
            if r[2] is None or r[3] is None:
                continue
            quotes.append({
                "game_id": r[0], "book": r[1],
                "line": float(r[2]), "under_price": float(r[3]),
            })
        return list(latest.values()), quotes
    finally:
        conn.close()


def report(universe: list[dict], title: str) -> None:
    print(f"\n=== {title}  n_universe={len(universe)} ===")
    months = sorted({r["month"] for r in universe})
    print("months:", ", ".join(
        f"{m} n={sum(1 for r in universe if r['month']==m)}" for m in months
    ))

    print("\n-- all-pass / filters --")
    cells = [
        ("all-pass", universe),
        ("under ≥ −115", [r for r in universe if r["price"] >= -115]),
        ("t80 only", [r for r in universe if r["over_tix"] >= 80]),
        ("suppress-all (drop days n≥4)", suppress_all(universe)),
        ("thin slates only (n≤3)", thin_slates(universe, 3)),
        ("gap ≥ 5", [r for r in universe
                     if (r["over_tix"] - (r["over_money"] or r["over_tix"])) >= 5]),
        ("gap ≤ −5 (money-heavy)", [r for r in universe
                                    if (r["over_tix"] - (r["over_money"] or r["over_tix"])) <= -5]),
    ]
    for name, rows in cells:
        print(f"  {name:<34s} {_fmt(summarize(rows))}")

    print("\n-- by month, all-pass --")
    for m in months:
        chunk = [r for r in universe if r["month"] == m]
        print(f"  {m}  {_fmt(summarize(chunk))}")

    print("\n-- ticket buckets (all-pass, decided only) --")
    for lo, hi in fade.EV_TICKET_BUCKETS:
        chunk = [r for r in universe if lo <= r["over_tix"] < hi]
        print(f"  [{lo:.0f},{hi:.0f})  {_fmt(summarize(chunk))}")

    print("\n-- top-K by formula (in-sample rank, not holdout) --")
    for kind in (fade.RANK_TICKET, fade.RANK_GAP, fade.RANK_JUICE,
                 fade.RANK_COMPOSITE):
        for k in (1, 2):
            rows = take(universe, kind=kind, k=k)
            print(f"  {kind:<10s} top-{k}  {_fmt(summarize(rows))}")

    print("\n-- leave-one-month-out EV rank --")
    for k in (0, 1, 2):
        label = "all-pass+floor" if k == 0 else f"top-{k}"
        rows = holdout_take(universe, kind=fade.RANK_EV, k=k)
        print(f"  EV {label:<14s} {_fmt(summarize(rows))}")
        for floor in (0.00, 0.02, 0.03, 0.05):
            if floor == 0.0 and k == 0:
                continue
            rows_f = holdout_take(universe, kind=fade.RANK_EV, k=k,
                                  min_edge=floor)
            print(f"    edge≥{floor:.2f} {label:<10s} {_fmt(summarize(rows_f))}")

    print("\n-- LOMO EV, by held-out month (top-1) --")
    for m in months:
        rates = lomo_rates(universe, m)
        chunk = [r for r in universe if r["month"] == m]
        rows = take(chunk, kind=fade.RANK_EV, k=1, ev_rates=rates)
        print(f"  hold {m}  {_fmt(summarize(rows))}")
        print("    train buckets:",
              ", ".join(
                  f"{k} wr={v:.3f}"
                  for k, v in sorted(
                      (kv for kv in rates.items() if kv[0] != ("all", "all")),
                      key=lambda kv: kv[0],
                  )
              ))

    print("\n-- composite top-K by month --")
    for k in (1, 2):
        rows = take(universe, kind=fade.RANK_COMPOSITE, k=k)
        print(f"  composite top-{k}")
        for m in months:
            chunk = [r for r in rows if r["month"] == m]
            print(f"    {m}  {_fmt(summarize(chunk))}")

    print("\n-- ticket top-K by month --")
    for k in (1, 2):
        rows = take(universe, kind=fade.RANK_TICKET, k=k)
        print(f"  ticket top-{k}")
        for m in months:
            chunk = [r for r in rows if r["month"] == m]
            print(f"    {m}  {_fmt(summarize(chunk))}")

    print("\n-- juice top-K + under≥−115 --")
    for kind in (fade.RANK_JUICE, fade.RANK_COMPOSITE, fade.RANK_TICKET):
        for k in (1, 2):
            rows = take(universe, kind=kind, k=k, price_floor=-115)
            print(f"  {kind} top-{k} ∩ ≥−115  {_fmt(summarize(rows))}")

    print("\n-- prior signal: t75 ∩ juice≥−115 --")
    t75j = [r for r in universe if r["over_tix"] >= 75 and r["price"] >= -115]
    print(f"  all-pass                       {_fmt(summarize(t75j))}")
    print(f"  ticket top-1                   {_fmt(summarize(take(t75j, kind=fade.RANK_TICKET, k=1)))}")
    print(f"  ticket top-2                   {_fmt(summarize(take(t75j, kind=fade.RANK_TICKET, k=2)))}")
    print(f"  gap top-1                      {_fmt(summarize(take(t75j, kind=fade.RANK_GAP, k=1)))}")
    print(f"  juice top-1                    {_fmt(summarize(take(t75j, kind=fade.RANK_JUICE, k=1)))}")
    print(f"  composite top-1                {_fmt(summarize(take(t75j, kind=fade.RANK_COMPOSITE, k=1)))}")
    for m in months:
        chunk = [r for r in t75j if r["month"] == m]
        print(f"  {m} all-pass                {_fmt(summarize(chunk))}")
        print(f"  {m} ticket top-1            {_fmt(summarize(take(chunk, kind=fade.RANK_TICKET, k=1)))}")

    print("\n-- alternatives --")
    t80 = [r for r in universe if r["over_tix"] >= 80]
    t90 = [r for r in universe if r["over_tix"] >= 90]
    print(f"  t90 all-pass                   {_fmt(summarize(t90))}")
    print(f"  t80 ticket top-1               {_fmt(summarize(take(t80, kind=fade.RANK_TICKET, k=1)))}")
    print(f"  t80 ticket top-2               {_fmt(summarize(take(t80, kind=fade.RANK_TICKET, k=2)))}")
    print(f"  t90 ticket top-1               {_fmt(summarize(take(t90, kind=fade.RANK_TICKET, k=1)))}")
    print(f"  t90 ticket top-2               {_fmt(summarize(take(t90, kind=fade.RANK_TICKET, k=2)))}")
    early = [r for r in universe if r["month"] < "2026-09"]
    late = [r for r in universe if r["month"] >= "2026-09"]
    print(f"  Jun+Jul all-pass               {_fmt(summarize(early))}")
    print(f"  Jun+Jul ticket top-2           {_fmt(summarize(take(early, kind=fade.RANK_TICKET, k=2)))}")
    print(f"  Sep all-pass                   {_fmt(summarize(late))}")
    print(f"  Sep ticket top-1               {_fmt(summarize(take(late, kind=fade.RANK_TICKET, k=1)))}")
    print(f"  Sep ticket top-2               {_fmt(summarize(take(late, kind=fade.RANK_TICKET, k=2)))}")
    print(f"  Sep composite top-2            {_fmt(summarize(take(late, kind=fade.RANK_COMPOSITE, k=2)))}")


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

    for cut in (65.0, 70.0):
        uni = build_candidates(splits, quotes, min_over_tickets=cut)
        report(uni, f"candidate pool over-tickets ≥ {cut:.0f}")


if __name__ == "__main__":
    main()
