"""Standing MLB totals edge hunt — public / Pin / RLM / steam.

WHY THIS EXISTS
---------------
`mlb_over_under` stays paused. `mlb_total_market` is Pin-fair minus bettable
soft implied at 2pp with INSERT gated off (Pin-de-vig vs soft-de-vig May–Jun
2pp was −11.13% / 79). `mlb_total_public_fade` / I24 is a separate paper
lane (tickets≥80, under [−110, −100], max 2/slate) and is NOT recut here.

This script measures the *other* constructions: fade a public OVER or UNDER
pile (tickets or money), RLM, Pin-lean vs soft implied / de-vig, steam /
anti-steam, and public × steam overlays.

It does not write picks, does not flip any PUBLISH env, does not unpause
mlb_over_under, and does not edit I24 guards. Measure only.

AS-OF. Public rows need snapshot_at < commence_time (offset-aware). Odds need
snapshot_type='open' and snapshot_at <= commence_time. Public data is sparse
before late May 2026; August honest pre-commence coverage is empty (last-upsert
overwrite).

    python -m scripts.mlb_over_under_edge_hunt
    python -m scripts.mlb_over_under_edge_hunt --json /tmp/ou_hunt.json
    python -m scripts.mlb_over_under_edge_hunt --family public --family rlm

`--json` is a sandbox cache of the rows this session pulled from Supabase
(splits + leak-bounded opens + optional pin/steam boards). The worker / Matt's
machine can omit it and load from the database.

Docs: docs/mlb_over_under_edge_hunt.md.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.market_relative import devig, implied

SOFT = ("draftkings", "fanduel", "betmgm", "williamhill_us")
FALLBACK = "draftkings"
PRICE_MIN = -200.0
PRICE_MAX = 200.0
LINE_MIN = 5.5
LINE_MAX = 14.5
FAMILIES = ("public", "rlm", "pin", "steam", "overlay")


def american_units(price: float, won: bool) -> float:
    if not won:
        return -1.0
    if price > 0:
        return float(price) / 100.0
    return 100.0 / abs(float(price))


def is_main_total(line) -> bool:
    if line is None:
        return False
    x = float(line)
    return LINE_MIN <= x <= LINE_MAX


def grade_ou(side: str, line: float, hs, aws):
    """Over / under vs the posted total. None = push / missing score."""
    if hs is None or aws is None:
        return None, None
    total = float(hs) + float(aws)
    if total == float(line):
        return "PUSH", 0.0
    went_over = total > float(line)
    won = went_over if side == "over" else (not went_over)
    return ("WIN" if won else "LOSS"), None


def wilson(wins: int, n: int, z: float = 1.96) -> tuple[float, float]:
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
    months = sorted({r["game_date"][:7] for r in rows})
    month_roi = {}
    for m in months:
        chunk = [r for r in rows if r["game_date"][:7] == m]
        nu = sum(x["units"] for x in chunk)
        month_roi[m] = {
            "n": len(chunk),
            "units": nu,
            "roi": (nu / len(chunk)) if chunk else float("nan"),
        }
    green_months = sum(1 for v in month_roi.values() if v["n"] and v["roi"] > 0)
    red_months = sum(1 for v in month_roi.values() if v["n"] and v["roi"] <= 0)
    return {
        "n": n, "n_dec": n_dec, "pushes": len(pushes),
        "wins": wins, "wr": wr, "units": units, "roi": roi,
        "wr_lo": lo, "wr_hi": hi,
        "days": len(days), "max_per_day": max_day,
        "months": month_roi, "green_months": green_months,
        "red_months": red_months,
        # Same ship bar as the runline hunt: n≥40, every populated month
        # green, ≥2 such months, ROI>0, max/day≤4. A Jun+Jul print with a
        # red September is not a ship.
        "clears": bool(n >= 40 and green_months >= 2 and red_months == 0
                       and roi > 0 and max_day <= 4),
    }


def _fmt(s: dict) -> str:
    if s["n"] == 0:
        return "n=0"
    wr = "n/a" if s["n_dec"] == 0 else f"{100*s['wr']:.1f}%"
    flag = "  CLEAR" if s.get("clears") else ""
    months = "  ".join(
        f"{m} {100*v['roi']:+.1f}%/{v['n']}"
        for m, v in s.get("months", {}).items()
    )
    return (
        f"n={s['n']:<3d}  {s['units']:+7.2f}u  ROI {100*s['roi']:+6.1f}%  "
        f"WR {wr} ({s['wins']}-{s['n_dec']-s['wins']}"
        f"{(', ' + str(s['pushes']) + 'p') if s['pushes'] else ''})  "
        f"max/day={s['max_per_day']}  green_mo={s['green_months']}"
        f"{flag}\n           {months}"
    )


def _f(x):
    if x is None or x == "":
        return None
    return float(x)


def _sane_split(over_tix, under_tix) -> bool:
    """Drop Action Network garbage (both sides ~100, or sum far from 100)."""
    if over_tix is None or under_tix is None:
        return False
    if abs((over_tix + under_tix) - 100.0) > 15.0:
        return False
    if over_tix >= 98 and under_tix >= 50:
        return False
    if under_tix >= 98 and over_tix >= 50:
        return False
    return True


def _better(candidate: float, incumbent: float | None) -> bool:
    ic = implied(candidate)
    if ic is None:
        return False
    if incumbent is None:
        return True
    ii = implied(incumbent)
    if ii is None:
        return True
    return ic < ii


def shop_side(books: dict, side: str, line: float) -> tuple[str, float] | None:
    """Best same-line open price among SOFT for `side` in the juice window."""
    best_book = None
    best_price = None
    key = "over_price" if side == "over" else "under_price"
    for bk in SOFT:
        q = books.get(bk)
        if not q:
            continue
        bline = _f(q.get("total_line"))
        if bline is None or float(bline) != float(line):
            continue
        price = _f(q.get(key))
        if price is None or not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        if _better(price, best_price):
            best_book = bk
            best_price = price
    if best_book is None or best_price is None:
        return None
    return best_book, float(best_price)


def top_k(rows: list[dict], k: int, score_of) -> list[dict]:
    if k <= 0:
        return list(rows)
    by = defaultdict(list)
    for r in rows:
        by[r["game_date"]].append(r)
    out = []
    for group in by.values():
        ranked = sorted(group, key=lambda r: (score_of(r), r["game_id"]),
                        reverse=True)
        out.extend(ranked[:k])
    return out


def attach_board(splits: list[dict], quotes: list[dict]) -> list[dict]:
    """One row per game: public split + DK total + shopped both sides."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        qmap[q["game_id"]][q["bookmaker"]] = q
    out = []
    for s in splits:
        gid = s["game_id"]
        ot, ut = _f(s.get("over_tix")), _f(s.get("under_tix"))
        om, um = _f(s.get("over_money")), _f(s.get("under_money"))
        if not _sane_split(ot, ut):
            continue
        books = qmap.get(gid) or {}
        dk = books.get(FALLBACK)
        if not dk:
            continue
        line = _f(dk.get("total_line"))
        if line is None or not is_main_total(line):
            continue
        over_shop = shop_side(books, "over", line)
        under_shop = shop_side(books, "under", line)
        if over_shop is None or under_shop is None:
            continue
        hs, aws = _f(s.get("home_score") or s.get("hs")), _f(
            s.get("away_score") or s.get("aws"))
        pin = books.get("pinnacle")
        pin_line = _f(pin.get("total_line")) if pin else None
        pin_fair_over = None
        if pin and pin_line is not None and float(pin_line) == float(line):
            pin_fair_over, _ = devig(_f(pin.get("over_price")),
                                     _f(pin.get("under_price")))
        public_side = "over" if ot >= ut else "under"
        out.append({
            "game_id": gid,
            "game_date": s["game_date"],
            "month": s["game_date"][:7],
            "hs": hs, "aws": aws,
            "line": float(line),
            "over_tix": ot, "under_tix": ut,
            "over_money": om, "under_money": um,
            "over_rlm": None if (om is None or ot is None) else (om - ot),
            "under_rlm": None if (um is None or ut is None) else (um - ut),
            "over_book": over_shop[0], "over_price": over_shop[1],
            "under_book": under_shop[0], "under_price": under_shop[1],
            "pin_fair_over": pin_fair_over,
            "public_side": public_side,
            "public_tix": max(ot, ut),
        })
    return out


def bet_row(board: dict, side: str) -> dict | None:
    price = board["over_price"] if side == "over" else board["under_price"]
    book = board["over_book"] if side == "over" else board["under_book"]
    result, _ = grade_ou(side, board["line"], board["hs"], board["aws"])
    if result is None:
        return None
    units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
    tix = board["over_tix"] if side == "over" else board["under_tix"]
    fade_tix = board["under_tix"] if side == "over" else board["over_tix"]
    return {
        "game_id": board["game_id"],
        "game_date": board["game_date"],
        "side": side,
        "price": price,
        "book": book,
        "line": board["line"],
        "result": result,
        "units": units,
        "tix": tix,
        "fade_tix": fade_tix,
        "over_rlm": board.get("over_rlm"),
        "under_rlm": board.get("under_rlm"),
    }


def fade_public_side(board: list[dict], *, side_key: str, cut: float
                     ) -> list[dict]:
    """Fade the named public pile (over/under/public) at `cut` tickets."""
    rows = []
    for b in board:
        if side_key == "over":
            pile, bet_side = b["over_tix"], "under"
        elif side_key == "under":
            pile, bet_side = b["under_tix"], "over"
        elif side_key == "public":
            pile, bet_side = b["public_tix"], (
                "under" if b["public_side"] == "over" else "over")
        else:
            raise ValueError(side_key)
        if pile < cut:
            continue
        row = bet_row(b, bet_side)
        if row:
            rows.append(row)
    return rows


def fade_money_side(board: list[dict], *, cut: float) -> list[dict]:
    """Fade the money-heavier totals side when that pile ≥ cut."""
    rows = []
    for b in board:
        om, um = b.get("over_money"), b.get("under_money")
        if om is None or um is None:
            continue
        if om >= um:
            pile, bet_side = om, "under"
        else:
            pile, bet_side = um, "over"
        if pile < cut:
            continue
        row = bet_row(b, bet_side)
        if row:
            row["fade_tix"] = pile
            rows.append(row)
    return rows


def rlm_fade_over(board: list[dict], *, tix_cut: float, rlm_max: float
                  ) -> list[dict]:
    """Classic totals RLM: fade a ticket-heavy OVER whose money lags."""
    rows = []
    for b in board:
        if b["over_tix"] is None or b.get("over_rlm") is None:
            continue
        if b["over_tix"] < tix_cut:
            continue
        if b["over_rlm"] > rlm_max:
            continue
        row = bet_row(b, "under")
        if row:
            rows.append(row)
    return rows


def follow_money_over(board: list[dict], *, tix_cut: float, rlm_min: float
                      ) -> list[dict]:
    """Money-ahead-of-tickets on OVER — follow OVER."""
    rows = []
    for b in board:
        if b["over_tix"] is None or b.get("over_rlm") is None:
            continue
        if b["over_tix"] < tix_cut:
            continue
        if b["over_rlm"] < rlm_min:
            continue
        row = bet_row(b, "over")
        if row:
            rows.append(row)
    return rows


def juice_band(rows: list[dict], lo: float, hi: float) -> list[dict]:
    keep = []
    for r in rows:
        ip = implied(r["price"])
        ilo, ihi = implied(lo), implied(hi)
        if ip is None or ilo is None or ihi is None:
            continue
        if ip <= ilo and ip >= ihi:
            keep.append(r)
    return keep


def pin_agrees(board_row: dict, side: str) -> bool:
    fair = board_row.get("pin_fair_over")
    if fair is None:
        return False
    return (fair >= 0.5) if side == "over" else (fair < 0.5)


def fade_public_pin_agree(board: list[dict], *, cut: float) -> list[dict]:
    rows = []
    for b in board:
        pile = b["public_tix"]
        if pile < cut:
            continue
        bet_side = "under" if b["public_side"] == "over" else "over"
        if not pin_agrees(b, bet_side):
            continue
        row = bet_row(b, bet_side)
        if row:
            rows.append(row)
    return rows


def report_cells(title: str, cells: list[tuple[str, list[dict]]]) -> dict:
    print(f"\n=== {title} ===")
    winners = {}
    for name, rows in cells:
        s = summarize(rows)
        print(f"  {name:<48s} {_fmt(s)}")
        if s.get("clears"):
            winners[name] = s
    return winners


def overlay_public_steam(board: list[dict], *, tix_cut: float, pp_cut: float,
                         mode: str, follow_steam: bool) -> list[dict]:
    """Public pile × DK steam. `mode` is oppose / agree / any.

    Prices stay the public-board shop. Steam is only a direction / magnitude
    filter — move_over_pp from DK open→latest juiced over-implied.
    """
    if mode not in ("oppose", "agree", "any"):
        raise ValueError(mode)
    rows = []
    for b in board:
        move = b.get("move_over_pp")
        if move is None or abs(move) < pp_cut:
            continue
        if b["public_tix"] < tix_cut:
            continue
        public_over = b["public_side"] == "over"
        steam_over = move > 0
        oppose = public_over != steam_over
        if mode == "oppose" and not oppose:
            continue
        if mode == "agree" and oppose:
            continue
        if follow_steam:
            bet_side = "over" if steam_over else "under"
        else:
            bet_side = "under" if public_over else "over"
        row = bet_row(b, bet_side)
        if row:
            row["move"] = move
            row["fade_tix"] = b["public_tix"]
            rows.append(row)
    return rows


def pin_candidates(quotes: list[dict], games: dict, *, vs: str,
                   pin_lean: bool, min_edge: float) -> list[dict]:
    """One bet per game: largest Pin-vs-soft disagreement, equal total."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        qmap[q["game_id"]][q["bookmaker"]] = q
    rows = []
    for gid, books in qmap.items():
        g = games.get(gid)
        if not g:
            continue
        pin = books.get("pinnacle")
        if not pin:
            continue
        sline = _f(pin.get("total_line"))
        sf, _ = devig(_f(pin.get("over_price")), _f(pin.get("under_price")))
        if sf is None or sline is None or not is_main_total(sline):
            continue
        su = 1.0 - sf
        sides = (("over", sf, "over_price"), ("under", su, "under_price"))
        if pin_lean:
            sides = (max(sides, key=lambda s: s[1]),)
        best = None
        for bk in SOFT:
            q = books.get(bk)
            if not q:
                continue
            bline = _f(q.get("total_line"))
            if bline is None or float(bline) != float(sline):
                continue
            fa, fb = devig(_f(q.get("over_price")), _f(q.get("under_price")))
            for side, fair, key in sides:
                price = _f(q.get(key))
                if price is None or implied(price) is None:
                    continue
                if not (PRICE_MIN <= price <= PRICE_MAX):
                    continue
                if vs == "implied":
                    soft_p = implied(price)
                else:
                    soft_p = fa if side == "over" else fb
                    if soft_p is None:
                        continue
                edge = fair - soft_p
                if edge < min_edge:
                    continue
                cand = (edge, side, price, bk, float(sline))
                if best is None or cand[0] > best[0]:
                    best = cand
        if best is None:
            continue
        edge, side, price, bk, line = best
        result, _ = grade_ou(side, line, g.get("hs"), g.get("aws"))
        if result is None:
            continue
        units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
        rows.append({
            "game_id": gid, "game_date": g["game_date"],
            "side": side, "price": price, "book": bk, "line": line,
            "result": result, "units": units, "edge": edge,
        })
    return rows


def steam_candidates(moves: list[dict], *, pp_cut: float, follow: bool
                     ) -> list[dict]:
    """Bet the steamed (or faded) totals side when |over implied move| ≥ pp."""
    rows = []
    for m in moves:
        move = _f(m.get("move_over_pp"))
        if move is None or abs(move) < pp_cut:
            continue
        steamed_over = move > 0
        if follow:
            side = "over" if steamed_over else "under"
        else:
            side = "under" if steamed_over else "over"
        price = _f(m.get("over_price" if side == "over" else "under_price"))
        line = _f(m.get("total_line"))
        if price is None or line is None or not is_main_total(line):
            continue
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        result, _ = grade_ou(side, line, _f(m.get("hs")), _f(m.get("aws")))
        if result is None:
            continue
        units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
        rows.append({
            "game_id": m["game_id"], "game_date": m["game_date"],
            "side": side, "price": price, "book": m.get("bookmaker", FALLBACK),
            "line": line, "result": result, "units": units,
            "move": move,
        })
    return rows


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_db() -> dict:
    from data.db import get_connection
    conn = get_connection()
    try:
        pb = conn.execute("""
            SELECT pb.game_id, g.game_date, g.home_score, g.away_score,
                   g.commence_time, pb.public_bet_pct, pb.public_money_pct,
                   pb.snapshot_at,
                   un.public_bet_pct, un.public_money_pct
            FROM public_betting pb
            JOIN games g ON g.game_id = pb.game_id
            JOIN public_betting un ON un.game_id = pb.game_id
              AND un.market='totals' AND un.side='under' AND un.book='consensus'
            WHERE pb.market='totals' AND pb.side='over' AND pb.book='consensus'
              AND g.sport='MLB'
              AND pb.snapshot_at IS NOT NULL AND g.commence_time IS NOT NULL
              AND pb.snapshot_at::timestamptz < g.commence_time::timestamptz
              AND g.home_score IS NOT NULL
        """).fetchall()
        splits = []
        for r in pb:
            splits.append({
                "game_id": r[0], "game_date": r[1],
                "home_score": r[2], "away_score": r[3],
                "commence_time": r[4],
                "over_tix": r[5], "over_money": r[6],
                "public_snap": r[7],
                "under_tix": r[8], "under_money": r[9],
            })
        gids = [s["game_id"] for s in splits]
        quotes = []
        if gids:
            qrows = conn.execute("""
                SELECT DISTINCT ON (o.game_id, o.bookmaker)
                       o.game_id, o.bookmaker, o.total_line,
                       o.over_price, o.under_price, o.snapshot_at
                FROM odds o
                JOIN games g ON g.game_id = o.game_id
                WHERE o.sport='MLB' AND o.market='totals'
                  AND o.snapshot_type='open'
                  AND o.bookmaker IN ('draftkings','fanduel','betmgm',
                                      'williamhill_us','pinnacle')
                  AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
                  AND o.game_id = ANY(%s)
                ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
            """, (gids,)).fetchall()
            for r in qrows:
                quotes.append({
                    "game_id": r[0], "bookmaker": r[1],
                    "total_line": r[2], "over_price": r[3],
                    "under_price": r[4], "snapshot_at": r[5],
                })
        pin_quotes = []
        steam = []
        games = {}
        d = date(2026, 3, 20)
        end = date.today() + timedelta(days=1)
        while d < end:
            nxt = date(d.year + (d.month == 12),
                       1 if d.month == 12 else d.month + 1, 1)
            start, stop = d.isoformat(), min(nxt, end).isoformat()
            qrows = conn.execute("""
                SELECT DISTINCT ON (o.game_id, o.bookmaker)
                       o.game_id, o.bookmaker, o.total_line,
                       o.over_price, o.under_price, o.snapshot_at,
                       g.game_date, g.home_score, g.away_score
                FROM odds o
                JOIN games g ON g.game_id = o.game_id
                WHERE o.sport='MLB' AND o.market='totals'
                  AND o.snapshot_type='open'
                  AND o.bookmaker IN ('draftkings','fanduel','betmgm',
                                      'williamhill_us','pinnacle')
                  AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
                  AND g.game_date >= %s AND g.game_date < %s
                  AND g.home_score IS NOT NULL
                ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
            """, (start, stop)).fetchall()
            for r in qrows:
                pin_quotes.append({
                    "game_id": r[0], "bookmaker": r[1],
                    "total_line": r[2], "over_price": r[3],
                    "under_price": r[4], "snapshot_at": r[5],
                })
                games[r[0]] = {
                    "game_date": r[6], "hs": r[7], "aws": r[8],
                }
            srows = conn.execute("""
                WITH dk AS (
                  SELECT o.game_id, o.over_price::float AS op,
                         o.under_price::float AS up, o.total_line::float AS line,
                         o.snapshot_at, g.game_date, g.home_score, g.away_score
                  FROM odds o
                  JOIN games g ON g.game_id = o.game_id
                  WHERE o.sport='MLB' AND o.market='totals'
                    AND o.snapshot_type='open' AND o.bookmaker='draftkings'
                    AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
                    AND g.game_date >= %s AND g.game_date < %s
                    AND g.home_score IS NOT NULL
                    AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
                ),
                first AS (
                  SELECT DISTINCT ON (game_id) * FROM dk
                  ORDER BY game_id, snapshot_at ASC
                ),
                last AS (
                  SELECT DISTINCT ON (game_id) * FROM dk
                  ORDER BY game_id, snapshot_at DESC
                )
                SELECT l.game_id, l.game_date, l.line, l.op, l.up,
                       l.home_score, l.away_score,
                       f.op AS open_op, f.up AS open_up
                FROM last l JOIN first f ON f.game_id = l.game_id
                WHERE l.snapshot_at <> f.snapshot_at
            """, (start, stop)).fetchall()
            for r in srows:
                def _imp(a):
                    a = float(a)
                    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)
                open_o = _imp(r[7])
                last_o = _imp(r[3])
                steam.append({
                    "game_id": r[0], "game_date": r[1],
                    "total_line": r[2],
                    "over_price": r[3], "under_price": r[4],
                    "hs": r[5], "aws": r[6],
                    "bookmaker": "draftkings",
                    "move_over_pp": (last_o - open_o) * 100.0,
                })
            d = nxt
        return {
            "splits": splits, "quotes": quotes,
            "pin_quotes": pin_quotes, "games": games, "steam": steam,
        }
    finally:
        conn.close()


def attach_steam(board: list[dict], steam_rows: list[dict]) -> list[dict]:
    smap = {}
    for m in steam_rows:
        gid = m.get("game_id")
        if gid:
            smap[gid] = _f(m.get("move_over_pp"))
    for b in board:
        b["move_over_pp"] = smap.get(b["game_id"])
    return board


def run_public(board: list[dict]) -> dict:
    winners = {}
    cells = []
    for key, label in (("public", "fade heaviest side"),
                       ("over", "fade over pile"),
                       ("under", "fade under pile")):
        for cut in (60, 65, 70, 75, 80, 85, 90):
            rows = fade_public_side(board, side_key=key, cut=float(cut))
            cells.append((f"{label} t{cut}", rows))
            for k in (1, 2, 3):
                cells.append((
                    f"{label} t{cut} top-{k}",
                    top_k(rows, k, lambda r: r["fade_tix"]),
                ))
            if cut in (70, 80) and key in ("public", "over"):
                cells.append((
                    f"{label} t{cut} juice[-110,-100]",
                    juice_band(rows, -110, -100),
                ))
                cells.append((
                    f"{label} t{cut} top-2 juice[-110,-100]",
                    juice_band(top_k(rows, 2, lambda r: r["fade_tix"]),
                               -110, -100),
                ))
    for cut in (65, 70, 75, 80):
        rows = fade_public_pin_agree(board, cut=float(cut))
        cells.append((f"fade public ∩ Pin-agree t{cut}", rows))
        cells.append((
            f"fade public ∩ Pin-agree t{cut} top-2",
            top_k(rows, 2, lambda r: r["fade_tix"]),
        ))
    for cut in (60, 65, 70, 75, 80, 85, 90):
        rows = fade_money_side(board, cut=float(cut))
        cells.append((f"fade money-heavy m{cut}", rows))
        for k in (2, 3, 4):
            cells.append((
                f"fade money-heavy m{cut} top-{k}",
                top_k(rows, k, lambda r: r["fade_tix"]),
            ))
    winners.update(report_cells("public fade totals", cells))
    return winners


def run_overlay(board: list[dict]) -> dict:
    n_move = sum(1 for b in board if b.get("move_over_pp") is not None)
    print(f"\n=== public × steam overlay ===\n  "
          f"board rows with move_pp: {n_move}/{len(board)}")
    if n_move == 0:
        print("  (no steam attached — pass steam rows in --json)")
        return {}
    cells = []
    for follow in (False, True):
        verb = "follow-steam" if follow else "fade-public"
        for mode in ("oppose", "agree", "any"):
            for tix in (60, 65, 70, 75, 80):
                for pp in (1.0, 2.0, 3.0):
                    rows = overlay_public_steam(
                        board, tix_cut=float(tix), pp_cut=pp,
                        mode=mode, follow_steam=follow)
                    tag = f"{verb} {mode} t{tix} ≥{pp:.0f}pp"
                    cells.append((tag, rows))
                    for k in (1, 2, 3, 4):
                        cells.append((
                            f"{tag} top-{k}",
                            top_k(rows, k, lambda r: r["fade_tix"]),
                        ))
    return report_cells("public × steam overlay", cells)


def run_rlm(board: list[dict]) -> dict:
    cells = []
    for tix in (55, 60, 65, 70, 75, 80):
        for gap in (-5, -10, -15, -20):
            rows = rlm_fade_over(board, tix_cut=float(tix), rlm_max=float(gap))
            cells.append((f"RLM fade-over t{tix} rlm≤{gap}", rows))
            cells.append((
                f"RLM fade-over t{tix} rlm≤{gap} top-2",
                top_k(rows, 2, lambda r: -(r.get("over_rlm") or 0)),
            ))
        rows_m = follow_money_over(board, tix_cut=float(tix), rlm_min=5.0)
        cells.append((f"follow-money over t{tix} rlm≥5", rows_m))
    return report_cells("RLM fade-over", cells)


def run_pin(pin_quotes: list[dict], games: dict) -> dict:
    if not pin_quotes or not games:
        print("\n=== Pin-vs-soft ===\n  (no pin board in this cache)")
        return {}
    cells = []
    for vs in ("implied", "devig"):
        for lean in (True, False):
            for cut in (0.015, 0.018, 0.020, 0.025, 0.030):
                rows = pin_candidates(
                    pin_quotes, games, vs=vs, pin_lean=lean, min_edge=cut)
                tag = f"pin-{vs}{' lean' if lean else ''} ≥{cut*100:.1f}pp"
                cells.append((tag, rows))
                cells.append((f"{tag} top-2",
                              top_k(rows, 2, lambda r: r.get("edge", 0))))
    return report_cells("Pin-vs-soft", cells)


def run_steam(moves: list[dict]) -> dict:
    if not moves:
        print("\n=== steam ===\n  (no steam board in this cache)")
        return {}
    cells = []
    for follow in (True, False):
        verb = "follow" if follow else "fade"
        for cut in (1.0, 2.0, 3.0, 4.0, 5.0):
            rows = steam_candidates(moves, pp_cut=cut, follow=follow)
            cells.append((f"steam {verb} ≥{cut:.0f}pp", rows))
            cells.append((
                f"steam {verb} ≥{cut:.0f}pp top-2",
                top_k(rows, 2, lambda r: abs(r.get("move") or 0)),
            ))
    winners = report_cells("steam / anti-steam", cells)
    print(
        "  note: a public-board steam CLEAR is not a ship if the same "
        "follow cut on the full DK month is red (2026-07 follow ≥1pp "
        "was −118.50u / 197 on the full book)."
    )
    return winners


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", default=None,
                    help="splits+quotes JSON (sandbox cache of Supabase)")
    ap.add_argument("--family", action="append", default=[],
                    choices=FAMILIES,
                    help="Repeatable. Default: all families present in the cache")
    args = ap.parse_args()
    families = tuple(args.family) if args.family else (
        "public", "rlm", "pin", "steam", "overlay")

    if args.json:
        raw = load_json(args.json)
        print(f"loaded --json {args.json}: "
              f"{len(raw.get('splits') or [])} splits, "
              f"{len(raw.get('quotes') or [])} quotes, "
              f"{len(raw.get('pin_quotes') or [])} pin quotes, "
              f"{len(raw.get('steam') or [])} steam rows")
    else:
        raw = load_db()
        print(f"loaded DB: {len(raw['splits'])} splits, "
              f"{len(raw['quotes'])} quotes, "
              f"{len(raw['pin_quotes'])} pin quotes, "
              f"{len(raw['steam'])} steam rows")

    board = attach_board(raw.get("splits") or [], raw.get("quotes") or [])
    attach_steam(board, raw.get("steam") or [])
    print(f"public intersect DK-total board: {len(board)} games  "
          f"months={sorted({b['month'] for b in board})}  "
          f"with_move={sum(1 for b in board if b.get('move_over_pp') is not None)}")

    winners: dict = {}
    if "public" in families:
        winners.update(run_public(board))
    if "rlm" in families:
        winners.update(run_rlm(board))
    if "pin" in families:
        games = raw.get("games") or {}
        if not games:
            for b in board:
                games[b["game_id"]] = {
                    "game_date": b["game_date"], "hs": b["hs"], "aws": b["aws"],
                }
        winners.update(run_pin(raw.get("pin_quotes") or [], games))
    if "steam" in families:
        winners.update(run_steam(raw.get("steam") or []))
    if "overlay" in families:
        winners.update(run_overlay(board))

    print("\n=== cells that clear n≥40, every month green (≥2), "
          "ROI>0, max/day≤4 ===")
    if not winners:
        print("  none")
    else:
        for name, s in winners.items():
            print(f"  {name:<48s} {_fmt(s)}")


if __name__ == "__main__":
    main()
