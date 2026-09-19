"""Ticket × juice × holdout grid for the MLB public-OVER fade.

Rebuilds the candidate universe the card uses: last pre-commence consensus
totals OVER ∩ best same-line open under among DK/FD/MGM/WH at DK's open
total (5.5–14.5, American in [-200, 200]). Then grades every cell in

    over_tickets ∈ {65, 70, 75, 80, 85, 90}
    juice        ∈ {any, ge_m115, ge_m110, ge_m105, plus}
    slate cap    ∈ {None, 2, 3, 4, 5}

THIS IS MEASUREMENT. It does not INSERT picks, does not set
MLB_TOTAL_PUBLIC_FADE_PUBLISH, and does not unpause mlb_over_under.

    python -m scripts.mlb_total_public_fade_grid
    python -m scripts.mlb_total_public_fade_grid --from-json /tmp/fade_universe.json

Docs: docs/mlb_total_public_fade_selective.md
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Juice / shop math is duplicated here so --from-json runs with stdlib
# only. The card's copy lives in models.mlb_total_public_fade and is
# what production uses. Tests pin they agree.
TICKETS = (65, 70, 75, 80, 85, 90)
JUICES = ("any", "ge_m115", "ge_m110", "ge_m105", "plus")
SLATE_CAPS = (None, 2, 3, 4, 5)
SOFT = ("draftkings", "fanduel", "betmgm", "williamhill_us")
LINE_MIN, LINE_MAX = 5.5, 14.5
PRICE_MIN, PRICE_MAX = -200.0, 200.0
CONC_REJECT = 0.50
TRAIN_MONTHS = {6, 7}          # May has 0 honest pre-commence rows
HOLD_MONTHS = {8, 9}           # August is empty; September is the hold
OOS_N_PREF = 40
OOS_ROI_PREF = 0.05


def implied(american: float) -> float:
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def juice_allows(price: float, spec: str = "any") -> bool:
    if spec == "any":
        return True
    p = float(price)
    if spec == "plus":
        return p > 0
    floors = {"ge_m115": -115.0, "ge_m110": -110.0, "ge_m105": -105.0}
    return p >= floors[spec]


def shop_under(books: dict, *, line: float
               ) -> tuple[str, float] | None:
    best_book, best_price, best_imp = None, None, None
    for bk in SOFT:
        q = books.get(bk)
        if not q:
            continue
        bline = q.get("total_line")
        if bline is None or float(bline) != float(line):
            continue
        price = q.get("under_price")
        if price is None:
            continue
        price = float(price)
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        imp = implied(price)
        if best_imp is None or imp < best_imp:
            best_book, best_price, best_imp = bk, price, imp
    if best_book is None:
        return None
    return best_book, best_price


def profit_units(price: float, won: bool | None) -> float:
    if won is None:
        return 0.0
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def grade_under(home: float, away: float, line: float) -> bool | None:
    total = float(home) + float(away)
    if total == float(line):
        return None
    return total < float(line)


def wilson_low(wins: int, n: int, z: float = 1.96) -> float | None:
    """Lower Wilson bound on a win rate. None when n=0."""
    if n <= 0:
        return None
    p = wins / n
    z2 = z * z
    denom = 1.0 + z2 / n
    centre = p + z2 / (2 * n)
    spread = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))
    return (centre - spread) / denom


def shop_row(quotes_by_book: dict) -> dict | None:
    """DK-line shop, same as fade.shop_under. None if the card would skip."""
    dk = quotes_by_book.get("draftkings")
    if not dk:
        return None
    line = dk.get("total_line")
    if line is None:
        return None
    line = float(line)
    if not (LINE_MIN <= line <= LINE_MAX):
        return None
    shopped = shop_under(quotes_by_book, line=line)
    if shopped is None:
        return None
    book, price = shopped
    return {"book": book, "line": line, "price": float(price)}


def attach_shop(games: list[dict], quotes: dict) -> list[dict]:
    """games + quotes -> one candidate row per game the card could price."""
    by_game: dict[str, dict] = defaultdict(dict)
    for (gid, bk), q in quotes.items():
        by_game[gid][bk] = q
    out = []
    for g in games:
        shopped = shop_row(by_game.get(g["game_id"]) or {})
        if shopped is None:
            continue
        row = dict(g)
        row.update(shopped)
        hs, aws = row.get("home_score"), row.get("away_score")
        if hs is not None and aws is not None:
            won = grade_under(float(hs), float(aws), row["line"])
            row["won"] = won
            row["units"] = profit_units(row["price"], won)
        else:
            row["won"] = "unscored"
            row["units"] = None
        out.append(row)
    return out


def _month(gd: str) -> int:
    return int(str(gd)[5:7])


def cell_rows(cands: list[dict], ticket: float, juice: str,
              cap: int | None) -> list[dict]:
    hits = [c for c in cands
            if c["over_tix"] >= ticket and juice_allows(c["price"], juice)]
    if cap is None:
        return hits
    groups: dict[str, list[dict]] = defaultdict(list)
    for c in hits:
        groups[c["game_date"]].append(c)
    keep = []
    for rows in groups.values():
        ranked = sorted(rows, key=lambda r: (-r["over_tix"], -r["price"],
                                             r["game_id"]))
        keep.extend(ranked[:int(cap)])
    return keep


def summarize(rows: list[dict], slates: dict[str, int],
              label: str = "") -> dict:
    graded = [r for r in rows if r["won"] != "unscored"]
    wins = sum(1 for r in graded if r["won"] is True)
    losses = sum(1 for r in graded if r["won"] is False)
    pushes = sum(1 for r in graded if r["won"] is None)
    n = len(graded)
    units = sum(float(r["units"]) for r in graded)
    decided = wins + losses
    by_date: dict[str, int] = defaultdict(int)
    for r in rows:
        by_date[r["game_date"]] += 1
    concs = []
    for d, n_bets in by_date.items():
        slate = slates.get(d)
        if slate and slate > 0:
            concs.append(n_bets / slate)
    mean_conc = sum(concs) / len(concs) if concs else 0.0
    max_conc = max(concs) if concs else 0.0
    days_over = sum(1 for x in concs if x > CONC_REJECT)
    by_month: dict[str, dict] = {}
    months = sorted({r["game_date"][:7] for r in graded})
    for ym in months:
        sub = [r for r in graded if r["game_date"][:7] == ym]
        w = sum(1 for r in sub if r["won"] is True)
        l = sum(1 for r in sub if r["won"] is False)
        u = sum(float(r["units"]) for r in sub)
        by_month[ym] = {
            "n": len(sub), "wins": w, "losses": l,
            "units": round(u, 3),
            "roi": round(u / len(sub), 4) if sub else None,
        }
    return {
        "label": label,
        "n": n,
        "unscored": sum(1 for r in rows if r["won"] == "unscored"),
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "units": round(units, 3),
        "roi": round(units / n, 4) if n else None,
        "win_pct": round(wins / decided, 4) if decided else None,
        "wilson_lo": (round(wilson_low(wins, decided), 4)
                      if decided else None),
        "mean_conc": round(mean_conc, 3),
        "max_conc": round(max_conc, 3),
        "days": len(concs),
        "days_over_50": days_over,
        "conc_reject": mean_conc > CONC_REJECT,
        "monthly": by_month,
    }


def split_holdout(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    train = [r for r in rows if _month(r["game_date"]) in TRAIN_MONTHS]
    hold = [r for r in rows if _month(r["game_date"]) in HOLD_MONTHS]
    return train, hold


def lomo(rows: list[dict]) -> dict[str, list[dict]]:
    months = sorted({r["game_date"][:7] for r in rows})
    return {ym: [r for r in rows if r["game_date"][:7] == ym] for ym in months}


def grid(cands: list[dict], slates: dict[str, int],
         caps: tuple = SLATE_CAPS) -> list[dict]:
    cells = []
    for t in TICKETS:
        for juice in JUICES:
            for cap in caps:
                rows = cell_rows(cands, t, juice, cap)
                tagged = (f"t{t:.0f}/{juice}"
                          + (f"/cap{cap}" if cap else "/uncapped"))
                full = summarize(rows, slates, tagged)
                train_rows, hold_rows = split_holdout(rows)
                train = summarize(train_rows, slates, "train")
                hold = summarize(hold_rows, slates, "hold")
                lomo_s = {ym: summarize(rs, slates, ym)
                          for ym, rs in lomo(rows).items()}
                cells.append({
                    "ticket": t,
                    "juice": juice,
                    "cap": cap,
                    "tag": tagged,
                    "full": full,
                    "train": train,
                    "hold": hold,
                    "lomo": lomo_s,
                })
    return cells


def rank_cells(cells: list[dict]) -> list[dict]:
    """Prefer hold n/ROI, then not-one-month, then full ROI. Reject conc."""
    scored = []
    for c in cells:
        hold, train, full = c["hold"], c["train"], c["full"]
        if full["conc_reject"]:
            c["rank_reason"] = "conc>50%"
            c["score"] = -999
            scored.append(c)
            continue
        hold_n = hold["n"]
        hold_roi = hold["roi"] if hold["roi"] is not None else -9
        train_roi = train["roi"] if train["roi"] is not None else -9
        # One-month dependent: hold + and train −, or a single LOMO month
        # carries all the units.
        lomo_rois = [m["roi"] for m in c["lomo"].values()
                     if m["n"] >= 8 and m["roi"] is not None]
        n_pos = sum(1 for r in lomo_rois if r > 0)
        one_month = (hold_roi > 0 and train_roi < 0) or (
            len(lomo_rois) >= 2 and n_pos <= 1)
        c["one_month"] = one_month
        c["score"] = (
            (2.0 if hold_n >= OOS_N_PREF else hold_n / OOS_N_PREF)
            + (2.0 if hold_roi >= OOS_ROI_PREF else max(hold_roi, -1))
            + (1.0 if train_roi > 0 else -0.5)
            + (0.5 if not one_month else -1.0)
            + (0.25 if not full["conc_reject"] else 0)
            + (full["roi"] or 0)
        )
        c["rank_reason"] = (
            f"hold n={hold_n} roi={hold_roi} train_roi={train_roi} "
            f"one_month={one_month} conc={full['mean_conc']}"
        )
        scored.append(c)
    return sorted(scored, key=lambda c: c["score"], reverse=True)


def load_from_json(path: str) -> tuple[list[dict], dict, dict[str, int]]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    games = raw["games"]
    slates = {str(k): int(v) for k, v in raw["slates"].items()}
    quotes = {}
    for q in raw["quotes"]:
        quotes[(q["game_id"], q["book"])] = {
            "total_line": q["total_line"],
            "under_price": q["under_price"],
            "over_price": q.get("over_price"),
            "snapshot_at": q.get("snapshot_at"),
        }
    return games, quotes, slates


def _iter_months(date_from: str, date_to: str):
    d = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    d = d.replace(day=1)
    while d < end:
        nxt = date(d.year + (d.month == 12),
                   1 if d.month == 12 else d.month + 1, 1)
        start = max(d, date.fromisoformat(date_from)).isoformat()
        stop = min(nxt, end).isoformat()
        if start < stop:
            yield start, stop
        d = nxt


def load_from_db(date_from: str, date_to: str
                 ) -> tuple[list[dict], dict, dict[str, int]]:
    import models.mlb_game_market as mk
    from data.db import get_connection
    conn = get_connection()
    try:
        games_rows = conn.execute("""
            SELECT pb.game_id, g.game_date, g.home_score, g.away_score,
                   pb.public_bet_pct, pb.public_money_pct
            FROM public_betting pb
            JOIN games g ON g.game_id = pb.game_id
            WHERE pb.market = 'totals' AND pb.side = 'over'
              AND pb.book = 'consensus' AND g.sport = 'MLB'
              AND g.game_date >= %s AND g.game_date < %s
              AND pb.snapshot_at::timestamptz < g.commence_time::timestamptz
            ORDER BY g.game_date, pb.game_id
        """, (date_from, date_to)).fetchall()
        games = [{
            "game_id": r[0], "game_date": str(r[1])[:10],
            "home_score": float(r[2]) if r[2] is not None else None,
            "away_score": float(r[3]) if r[3] is not None else None,
            "over_tix": float(r[4]),
            "over_money": float(r[5]) if r[5] is not None else None,
        } for r in games_rows]
        gids = [g["game_id"] for g in games]
        quotes: dict = {}
        for start, stop in _iter_months(date_from, date_to):
            pad = (date.fromisoformat(start) - timedelta(days=14)).isoformat()
            chunk_ids = [g["game_id"] for g in games
                         if start <= g["game_date"] < stop]
            if not chunk_ids:
                continue
            qrows = conn.execute("""
                SELECT DISTINCT ON (o.game_id, o.bookmaker)
                       o.game_id, o.bookmaker, o.total_line,
                       o.over_price, o.under_price, o.snapshot_at
                FROM odds o
                JOIN games g ON g.game_id = o.game_id
                WHERE o.sport = 'MLB' AND o.market = 'totals'
                  AND o.bookmaker = ANY(%s)
                  AND o.snapshot_type = 'open'
                  AND o.game_id = ANY(%s)
                  AND g.game_date >= %s AND g.game_date < %s
                  AND o.snapshot_at >= %s AND o.snapshot_at < %s
                  AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
                ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
            """, (list(SOFT), chunk_ids, start, stop, pad, stop)).fetchall()
            for gid, bk, tl, op, up, snap in qrows:
                quotes[(gid, bk)] = {
                    "total_line": tl, "over_price": op,
                    "under_price": up, "snapshot_at": snap,
                }
        # Also pull via the card helper as a coverage check.
        extra = mk.load_latest_quotes(conn, "MLB", "totals", gids)
        for key, q in extra.items():
            quotes.setdefault(key, q)
        slate_rows = conn.execute("""
            SELECT g.game_date, COUNT(*)
            FROM games g
            WHERE g.sport = 'MLB'
              AND g.game_date >= %s AND g.game_date < %s
            GROUP BY g.game_date
        """, (date_from, date_to)).fetchall()
        slates = {str(d)[:10]: int(n) for d, n in slate_rows}
        return games, quotes, slates
    finally:
        conn.close()


def render(cells: list[dict], top: int = 12) -> str:
    ranked = rank_cells(cells)
    lines = [
        "MLB totals public-fade selective grid",
        f"cells={len(ranked)}  conc-reject={sum(1 for c in ranked if c['full']['conc_reject'])}",
        "",
        f"{'tag':<28} {'n':>4} {'roi':>7} {'u':>7} {'W-L':>7} "
        f"{'conc':>5} {'hold_n':>6} {'hold_roi':>8} {'trn_roi':>7}  why",
    ]
    shown = 0
    for c in ranked:
        f, h, t = c["full"], c["hold"], c["train"]
        if f["n"] == 0:
            continue
        lines.append(
            f"{c['tag']:<28} {f['n']:4d} "
            f"{(f['roi'] if f['roi'] is not None else 0):+7.1%} "
            f"{f['units']:+7.2f} "
            f"{f['wins']}-{f['losses']:<3d} "
            f"{f['mean_conc']:5.2f} "
            f"{h['n']:6d} "
            f"{(h['roi'] if h['roi'] is not None else 0):+8.1%} "
            f"{(t['roi'] if t['roi'] is not None else 0):+7.1%}  "
            f"{c['rank_reason']}"
        )
        shown += 1
        if shown >= top:
            break
    return "\n".join(lines)


def run(date_from: str = "2026-05-31", date_to: str = "2026-09-20",
        from_json: str | None = None, caps: tuple = SLATE_CAPS) -> dict:
    if from_json:
        games, quotes, slates = load_from_json(from_json)
    else:
        games, quotes, slates = load_from_db(date_from, date_to)
    cands = attach_shop(games, quotes)
    cells = grid(cands, slates, caps=caps)
    ranked = rank_cells(cells)
    print(render(ranked, top=25))
    print(f"\nuniverse games={len(games)} shopped={len(cands)} "
          f"scored={sum(1 for c in cands if c['won'] != 'unscored')}")
    return {
        "n_games": len(games),
        "n_shopped": len(cands),
        "n_scored": sum(1 for c in cands if c["won"] != "unscored"),
        "cells": ranked,
        "candidates": cands,
        "slates": slates,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--from-json", default=None)
    ap.add_argument("--from", dest="date_from", default="2026-05-31")
    ap.add_argument("--to", dest="date_to", default="2026-09-20")
    ap.add_argument("--dump-json", default=None,
                    help="Write ranked cells (no candidate rows) to this path")
    args = ap.parse_args()
    result = run(args.date_from, args.date_to, from_json=args.from_json)
    if args.dump_json:
        slim = [{k: v for k, v in c.items() if k != "score"}
                for c in result["cells"]]
        Path(args.dump_json).write_text(
            json.dumps(slim, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
