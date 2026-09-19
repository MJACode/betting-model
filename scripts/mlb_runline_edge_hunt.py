"""Standing MLB runline edge hunt — public fade / Pin / RLM / steam.

WHY THIS EXISTS
---------------
`mlb_runline` stays paused. `mlb_spread_market` is Pin-de-vig vs bettable-soft
de-vig at 1.8pp with INSERT gated off (GROK Pin-vs-DK ≥2pp was −5% / ~200).
This script measures the *other* constructions: fade a public runline pile,
RLM-dog, Pin-lean vs soft implied, and steam / anti-steam.

It does not write picks, does not flip any PUBLISH env, and does not unpause
mlb_runline. Measure only.

AS-OF. Public rows need snapshot_at < commence_time (offset-aware). Odds need
snapshot_type='open' and snapshot_at <= commence_time. Public data is sparse
before late May 2026; August honest pre-commence coverage is empty (last-upsert
overwrite).

    python -m scripts.mlb_runline_edge_hunt
    python -m scripts.mlb_runline_edge_hunt --json /tmp/rl_hunt.json
    python -m scripts.mlb_runline_edge_hunt --family public --family rlm

`--json` is a sandbox cache of the rows this session pulled from Supabase
(splits + leak-bounded opens + optional pin/steam boards). The worker / Matt's
machine can omit it and load from the database.

Docs: docs/mlb_runline_edge_hunt.md.
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
FAMILIES = ("public", "rlm", "pin", "steam")


def american_units(price: float, won: bool) -> float:
    if not won:
        return -1.0
    if price > 0:
        return float(price) / 100.0
    return 100.0 / abs(float(price))


def is_runline(line) -> bool:
    if line is None:
        return False
    return abs(abs(float(line)) - 1.5) < 1e-9


def grade_rl(side: str, line: float, hs, aws):
    """Home-number ATS (§4). None = push / missing score."""
    if hs is None or aws is None:
        return None, None
    marg = float(hs) - float(aws) + float(line)
    if marg == 0:
        return "PUSH", 0.0
    home_covers = marg > 0
    won = home_covers if side == "home" else (not home_covers)
    return ("WIN" if won else "LOSS"), None  # units filled by caller with price


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
        # Month-stable: every populated month is green, and at least two
        # such months exist. A Jun+Jul print with a red September is not
        # a ship (the +1.2%/42 public top-2 peak).
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


def _sane_split(home_tix, away_tix) -> bool:
    """Drop Action Network garbage (both sides ~100, July 1)."""
    if home_tix is None or away_tix is None:
        return False
    if abs((home_tix + away_tix) - 100.0) > 15.0:
        return False
    if home_tix >= 98 and away_tix >= 50:
        return False
    if away_tix >= 98 and home_tix >= 50:
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
    key = "home_price" if side == "home" else "away_price"
    for bk in SOFT:
        q = books.get(bk)
        if not q:
            continue
        bline = _f(q.get("spread_home"))
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
    """One row per game: public split + DK line + shopped both sides."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        qmap[q["game_id"]][q["bookmaker"]] = q
    out = []
    for s in splits:
        gid = s["game_id"]
        ht, at = _f(s.get("home_tix")), _f(s.get("away_tix"))
        hm, am = _f(s.get("home_money")), _f(s.get("away_money"))
        if not _sane_split(ht, at):
            continue
        books = qmap.get(gid) or {}
        dk = books.get(FALLBACK)
        if not dk:
            continue
        line = _f(dk.get("spread_home"))
        if line is None or not is_runline(line):
            continue
        home_shop = shop_side(books, "home", line)
        away_shop = shop_side(books, "away", line)
        if home_shop is None or away_shop is None:
            continue
        hs, aws = _f(s.get("home_score")), _f(s.get("away_score"))
        fav = "home" if line < 0 else ("away" if line > 0 else None)
        dog = None if fav is None else ("away" if fav == "home" else "home")
        fav_tix = ht if fav == "home" else (at if fav == "away" else None)
        fav_money = hm if fav == "home" else (am if fav == "away" else None)
        dog_tix = at if fav == "home" else (ht if fav == "away" else None)
        home_rlm = None if (hm is None or ht is None) else (hm - ht)
        fav_rlm = None
        if fav_tix is not None and fav_money is not None:
            fav_rlm = fav_money - fav_tix
        pin = books.get("pinnacle")
        pin_line = _f(pin.get("spread_home")) if pin else None
        pin_fair_home = None
        if pin and pin_line is not None and float(pin_line) == float(line):
            pin_fair_home, _ = devig(_f(pin.get("home_price")),
                                     _f(pin.get("away_price")))
        out.append({
            "game_id": gid,
            "game_date": s["game_date"],
            "month": s["game_date"][:7],
            "hs": hs, "aws": aws,
            "line": float(line),
            "home_tix": ht, "away_tix": at,
            "home_money": hm, "away_money": am,
            "home_rlm": home_rlm,
            "fav": fav, "dog": dog,
            "fav_tix": fav_tix, "fav_money": fav_money, "fav_rlm": fav_rlm,
            "dog_tix": dog_tix,
            "home_book": home_shop[0], "home_price": home_shop[1],
            "away_book": away_shop[0], "away_price": away_shop[1],
            "pin_fair_home": pin_fair_home,
            "public_side": "home" if ht >= at else "away",
            "public_tix": max(ht, at),
        })
    return out


def bet_row(board: dict, side: str) -> dict | None:
    price = board["home_price"] if side == "home" else board["away_price"]
    book = board["home_book"] if side == "home" else board["away_book"]
    result, _ = grade_rl(side, board["line"], board["hs"], board["aws"])
    if result is None:
        return None
    units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
    tix = board["home_tix"] if side == "home" else board["away_tix"]
    fade_tix = board["away_tix"] if side == "home" else board["home_tix"]
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
        "fav_rlm": board["fav_rlm"],
        "home_rlm": board["home_rlm"],
    }


def fade_public_side(board: list[dict], *, side_key: str, cut: float
                     ) -> list[dict]:
    """Fade the named public pile (home/away/fav/public) at `cut` tickets."""
    rows = []
    for b in board:
        if side_key == "home":
            pile, bet_side = b["home_tix"], "away"
        elif side_key == "away":
            pile, bet_side = b["away_tix"], "home"
        elif side_key == "fav":
            if b["fav"] is None or b["fav_tix"] is None:
                continue
            pile, bet_side = b["fav_tix"], b["dog"]
        elif side_key == "public":
            pile, bet_side = b["public_tix"], (
                "away" if b["public_side"] == "home" else "home")
        else:
            raise ValueError(side_key)
        if pile < cut:
            continue
        row = bet_row(b, bet_side)
        if row:
            rows.append(row)
    return rows


def rlm_dog(board: list[dict], *, tix_cut: float, rlm_max: float) -> list[dict]:
    """Classic RLM: fade a ticket-heavy favorite whose money lags."""
    rows = []
    for b in board:
        if b["fav"] is None or b["fav_tix"] is None or b["fav_rlm"] is None:
            continue
        if b["fav_tix"] < tix_cut:
            continue
        if b["fav_rlm"] > rlm_max:  # rlm_max is negative (money behind)
            continue
        row = bet_row(b, b["dog"])
        if row:
            rows.append(row)
    return rows


def follow_money_dog(board: list[dict], *, tix_cut: float, rlm_min: float
                     ) -> list[dict]:
    """Money-ahead-of-tickets on the favorite — follow the dog? No: follow fav.

    Control: when money leads tickets on the favorite, bet the favorite.
    """
    rows = []
    for b in board:
        if b["fav"] is None or b["fav_tix"] is None or b["fav_rlm"] is None:
            continue
        if b["fav_tix"] < tix_cut:
            continue
        if b["fav_rlm"] < rlm_min:
            continue
        row = bet_row(b, b["fav"])
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


def report_cells(title: str, cells: list[tuple[str, list[dict]]]) -> dict:
    print(f"\n=== {title} ===")
    winners = {}
    for name, rows in cells:
        s = summarize(rows)
        print(f"  {name:<42s} {_fmt(s)}")
        if s.get("clears"):
            winners[name] = s
    return winners


# ── Pin / steam boards (full season; not public-gated) ───────────────────────


def pin_candidates(quotes: list[dict], games: dict, *, vs: str,
                   pin_lean: bool, min_edge: float) -> list[dict]:
    """One bet per game: largest Pin-vs-soft disagreement, equal ±1.5."""
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
        sline = _f(pin.get("spread_home"))
        sf, _ = devig(_f(pin.get("home_price")), _f(pin.get("away_price")))
        if sf is None or sline is None or not is_runline(sline):
            continue
        su = 1.0 - sf
        sides = (("home", sf, "home_price"), ("away", su, "away_price"))
        if pin_lean:
            sides = (max(sides, key=lambda s: s[1]),)
        best = None
        for bk in SOFT:
            q = books.get(bk)
            if not q:
                continue
            bline = _f(q.get("spread_home"))
            if bline is None or float(bline) != float(sline):
                continue
            fa, fb = devig(_f(q.get("home_price")), _f(q.get("away_price")))
            for side, fair, key in sides:
                price = _f(q.get(key))
                if price is None or implied(price) is None:
                    continue
                if not (PRICE_MIN <= price <= PRICE_MAX):
                    continue
                if vs == "implied":
                    soft_p = implied(price)
                else:
                    soft_p = fa if side == "home" else fb
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
        result, _ = grade_rl(side, line, g.get("hs"), g.get("aws"))
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
    """Bet the steamed (or faded) side when |home implied move| ≥ pp_cut."""
    rows = []
    for m in moves:
        move = _f(m.get("move_home_pp"))
        if move is None or abs(move) < pp_cut:
            continue
        steamed_home = move > 0
        if follow:
            side = "home" if steamed_home else "away"
        else:
            side = "away" if steamed_home else "home"
        price = _f(m.get("home_price" if side == "home" else "away_price"))
        line = _f(m.get("spread_home"))
        if price is None or line is None or not is_runline(line):
            continue
        if not (PRICE_MIN <= price <= PRICE_MAX):
            continue
        result, _ = grade_rl(side, line, _f(m.get("hs")), _f(m.get("aws")))
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


# ── loaders ──────────────────────────────────────────────────────────────────


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
                   aw.public_bet_pct, aw.public_money_pct
            FROM public_betting pb
            JOIN games g ON g.game_id = pb.game_id
            JOIN public_betting aw ON aw.game_id = pb.game_id
              AND aw.market='spreads' AND aw.side='away' AND aw.book='consensus'
            WHERE pb.market='spreads' AND pb.side='home' AND pb.book='consensus'
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
                "home_tix": r[5], "home_money": r[6],
                "public_snap": r[7],
                "away_tix": r[8], "away_money": r[9],
            })
        gids = [s["game_id"] for s in splits]
        quotes = []
        pin_quotes = []
        steam = []
        if gids:
            qrows = conn.execute("""
                SELECT DISTINCT ON (o.game_id, o.bookmaker)
                       o.game_id, o.bookmaker, o.spread_home,
                       o.home_price, o.away_price, o.snapshot_at
                FROM odds o
                JOIN games g ON g.game_id = o.game_id
                WHERE o.sport='MLB' AND o.market='spreads'
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
                    "spread_home": r[2], "home_price": r[3],
                    "away_price": r[4], "snapshot_at": r[5],
                })
        # Full-season latest opens for Pin family (month-chunked).
        d = date(2026, 3, 20)
        end = date.today() + timedelta(days=1)
        games = {}
        while d < end:
            nxt = date(d.year + (d.month == 12),
                       1 if d.month == 12 else d.month + 1, 1)
            start, stop = d.isoformat(), min(nxt, end).isoformat()
            qrows = conn.execute("""
                SELECT DISTINCT ON (o.game_id, o.bookmaker)
                       o.game_id, o.bookmaker, o.spread_home,
                       o.home_price, o.away_price, o.snapshot_at,
                       g.game_date, g.home_score, g.away_score
                FROM odds o
                JOIN games g ON g.game_id = o.game_id
                WHERE o.sport='MLB' AND o.market='spreads'
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
                    "spread_home": r[2], "home_price": r[3],
                    "away_price": r[4], "snapshot_at": r[5],
                })
                games[r[0]] = {
                    "game_date": r[6], "hs": r[7], "aws": r[8],
                }
            # DK open → latest implied move (steam).
            srows = conn.execute("""
                WITH dk AS (
                  SELECT o.game_id, o.home_price::float AS hp,
                         o.away_price::float AS ap, o.spread_home::float AS line,
                         o.snapshot_at, g.game_date, g.home_score, g.away_score
                  FROM odds o
                  JOIN games g ON g.game_id = o.game_id
                  WHERE o.sport='MLB' AND o.market='spreads'
                    AND o.snapshot_type='open' AND o.bookmaker='draftkings'
                    AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
                    AND g.game_date >= %s AND g.game_date < %s
                    AND g.home_score IS NOT NULL
                    AND o.home_price IS NOT NULL AND o.away_price IS NOT NULL
                ),
                first AS (
                  SELECT DISTINCT ON (game_id) * FROM dk
                  ORDER BY game_id, snapshot_at ASC
                ),
                last AS (
                  SELECT DISTINCT ON (game_id) * FROM dk
                  ORDER BY game_id, snapshot_at DESC
                )
                SELECT l.game_id, l.game_date, l.line, l.hp, l.ap,
                       l.home_score, l.away_score,
                       f.hp AS open_hp, f.ap AS open_ap
                FROM last l JOIN first f ON f.game_id = l.game_id
                WHERE l.snapshot_at <> f.snapshot_at
            """, (start, stop)).fetchall()
            for r in srows:
                def _imp(a):
                    a = float(a)
                    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)
                open_h = _imp(r[7])
                last_h = _imp(r[3])
                steam.append({
                    "game_id": r[0], "game_date": r[1],
                    "spread_home": r[2],
                    "home_price": r[3], "away_price": r[4],
                    "hs": r[5], "aws": r[6],
                    "bookmaker": "draftkings",
                    "move_home_pp": (last_h - open_h) * 100.0,
                })
            d = nxt
        return {
            "splits": splits, "quotes": quotes,
            "pin_quotes": pin_quotes, "games": games, "steam": steam,
        }
    finally:
        conn.close()


def pin_agrees(board_row: dict, side: str) -> bool:
    """True when Pinnacle no-vig leans `side` at the same ±1.5."""
    fair = board_row.get("pin_fair_home")
    if fair is None:
        return False
    return (fair >= 0.5) if side == "home" else (fair < 0.5)


def fade_public_pin_agree(board: list[dict], *, cut: float) -> list[dict]:
    """Fade the heaviest public pile only when Pin leans the faded side."""
    rows = []
    for b in board:
        pile = b["public_tix"]
        if pile < cut:
            continue
        bet_side = "away" if b["public_side"] == "home" else "home"
        if not pin_agrees(b, bet_side):
            continue
        row = bet_row(b, bet_side)
        if row:
            rows.append(row)
    return rows


def run_public(board: list[dict]) -> dict:
    winners = {}
    cells = []
    for key, label in (("public", "fade heaviest side"),
                       ("fav", "fade favorite"),
                       ("home", "fade home"),
                       ("away", "fade away")):
        for cut in (60, 65, 70, 75, 80, 85, 90):
            rows = fade_public_side(board, side_key=key, cut=float(cut))
            cells.append((f"{label} t{cut}", rows))
            for k in (1, 2):
                cells.append((
                    f"{label} t{cut} top-{k}",
                    top_k(rows, k, lambda r: r["fade_tix"]),
                ))
            if cut in (70, 80):
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
    winners.update(report_cells("public fade RL", cells))
    return winners


def run_rlm(board: list[dict]) -> dict:
    cells = []
    for tix in (55, 60, 65, 70, 75, 80):
        for gap in (-5, -10, -15, -20):
            rows = rlm_dog(board, tix_cut=float(tix), rlm_max=float(gap))
            cells.append((f"RLM dog t{tix} rlm≤{gap}", rows))
            cells.append((
                f"RLM dog t{tix} rlm≤{gap} top-2",
                top_k(rows, 2, lambda r: -(r["fav_rlm"] or 0)),
            ))
        rows_m = follow_money_dog(board, tix_cut=float(tix), rlm_min=5.0)
        cells.append((f"follow-money fav t{tix} rlm≥5", rows_m))
    winners = report_cells("RLM dog", cells)
    return winners


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
    return report_cells("steam / anti-steam", cells)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", default=None,
                    help="splits+quotes JSON (sandbox cache of Supabase)")
    ap.add_argument("--family", action="append", default=[],
                    choices=FAMILIES,
                    help="Repeatable. Default: public+rlm; pin/steam need boards")
    args = ap.parse_args()
    families = tuple(args.family) if args.family else ("public", "rlm", "pin", "steam")

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
    print(f"public intersect DK-runline board: {len(board)} games  "
          f"months={sorted({b['month'] for b in board})}")

    winners: dict = {}
    if "public" in families:
        winners.update(run_public(board))
    if "rlm" in families:
        winners.update(run_rlm(board))
    if "pin" in families:
        games = raw.get("games") or {}
        if not games:
            # Recover game meta from the public board / pin quotes if present.
            for b in board:
                games[b["game_id"]] = {
                    "game_date": b["game_date"], "hs": b["hs"], "aws": b["aws"],
                }
        winners.update(run_pin(raw.get("pin_quotes") or [], games))
    if "steam" in families:
        winners.update(run_steam(raw.get("steam") or []))

    print("\n=== cells that clear n≥40, every month green (≥2), "
          "ROI>0, max/day≤4 ===")
    if not winners:
        print("  none")
    else:
        for name, s in winners.items():
            print(f"  {name:<42s} {_fmt(s)}")


if __name__ == "__main__":
    main()
