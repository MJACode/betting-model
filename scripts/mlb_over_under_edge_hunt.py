"""Standing MLB totals edge hunt — public fade / under-fade / Pin / steam / RLM.

WHY THIS EXISTS
---------------
`mlb_over_under` stays paused. I24 (`mlb_total_public_fade` at tickets≥80,
under American [-110, -100], max 2 / RANK=ticket) already ships and is
NOT recut here. This script measures the *other* constructions: public-over
fade variants beyond I24, public-under fade, ticket×juice bands, top-K by
ticket, Pin-vs-soft (300s time-aligned only), steam / RLM on totals.

It does not write picks, does not flip any PUBLISH env, does not unpause
mlb_over_under, and does not weaken I24. Measure only.

AS-OF. Public rows need snapshot_at < commence_time (offset-aware). Odds need
snapshot_type='open' and snapshot_at <= commence_time. Pin-vs-soft refuses a
pair more than 300s apart (look-ahead on latest-per-book manufactured the
earlier ≥2pp print). Public data is sparse before late May 2026; August
honest pre-commence coverage is empty (last-upsert overwrite).

    python -m scripts.mlb_over_under_edge_hunt
    python -m scripts.mlb_over_under_edge_hunt --json /tmp/ou_hunt.json
    python -m scripts.mlb_over_under_edge_hunt --family public --family juice

`--json` is a sandbox cache of the rows this session pulled from Supabase
(splits + leak-bounded opens + optional pin/steam boards). The worker /
Matt's machine can omit it and load from the database.

Docs: docs/mlb_over_under_edge_hunt.md.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from models.market_relative import devig, implied

# Same constants as models.mlb_total_public_fade — inlined so --json
# measure does not import feature_engine / config / dotenv.
SOFT = ("draftkings", "fanduel", "betmgm", "williamhill_us")
FALLBACK = "draftkings"
PRICE_MIN = -200.0
PRICE_MAX = 200.0
LINE_MIN = 5.5
LINE_MAX = 14.5
MAX_GAP_S = 300.0
FAMILIES = ("public", "under", "juice", "rlm", "pin", "steam", "overlay")


def _parse_iso_ts(value):
    """UTC-aware parse. Offset-aware compare; text compare is a leak."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if not text:
            return None
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def under_in_odds_band(price, lo=None, hi=None) -> bool:
    """Inclusive American band via juiced implied (same as fade.under_in_odds_band)."""
    if lo is None and hi is None:
        return True
    p = _f(price)
    if p is None:
        return False
    ip = implied(p)
    if ip is None:
        return False
    if lo is not None:
        ilo = implied(float(lo))
        if ilo is None or ip > ilo:
            return False
    if hi is not None:
        ihi = implied(float(hi))
        if ihi is None or ip < ihi:
            return False
    return True

# Same mechanical bar as scripts/mlb_runline_edge_hunt.summarize (#757).
CLEAR_N = 40
CLEAR_MAX_DAY = 4


def american_units(price: float, won: bool) -> float:
    if not won:
        return -1.0
    if price > 0:
        return float(price) / 100.0
    return 100.0 / abs(float(price))


def grade_total(side: str, line: float, hs, aws):
    """Over/under vs the posted total. None = missing score (not a push)."""
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
        # Month-stable: every populated month is green, and at least two
        # such months exist. A Jun+Jul print with a red September is not
        # a ship (the #757 +1.2%/42 public top-2 peak).
        "clears": bool(n >= CLEAR_N and green_months >= 2 and red_months == 0
                       and roi > 0 and max_day <= CLEAR_MAX_DAY),
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


def _line_ok(line) -> bool:
    x = _f(line)
    if x is None:
        return False
    return LINE_MIN <= x <= LINE_MAX


def _price_ok(price) -> bool:
    p = _f(price)
    if p is None:
        return False
    return PRICE_MIN <= p <= PRICE_MAX


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


def _gap_seconds(a, b) -> float | None:
    ta, tb = _parse_iso_ts(a), _parse_iso_ts(b)
    if ta is None or tb is None:
        return None
    return abs((ta - tb).total_seconds())


def shop_side(books: dict, side: str, line: float) -> tuple[str, float] | None:
    """Best same-line open price among SOFT for over/under in the juice window."""
    best_book = None
    best_price = None
    key = "over_price" if side == "over" else "under_price"
    for bk in SOFT:
        q = books.get(bk)
        if not q:
            continue
        bline = _f(q.get("total_line", q.get("line")))
        if bline is None or float(bline) != float(line):
            continue
        price = _f(q.get(key))
        if price is None or not _price_ok(price):
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


def juice_band(rows: list[dict], lo: float, hi: float) -> list[dict]:
    """Inclusive American band via juiced implied (same as fade.under_in_odds_band)."""
    keep = []
    for r in rows:
        if under_in_odds_band(r["price"], lo, hi):
            keep.append(r)
    return keep


def is_i24_row(row: dict) -> bool:
    """True when a fade-under row is inside the live I24 window."""
    if row.get("side") != "under":
        return False
    tix = _f(row.get("fade_tix", row.get("over_tix")))
    if tix is None or tix < 80.0:
        return False
    return under_in_odds_band(row["price"], -110.0, -100.0)


def attach_board(splits: list[dict], quotes: list[dict]) -> list[dict]:
    """One row per game: public totals split + DK line + shopped both sides."""
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        bk = q.get("bookmaker") or q.get("book")
        qmap[q["game_id"]][bk] = q
    out = []
    for s in splits:
        gid = s["game_id"]
        ot, ut = _f(s.get("over_tix")), _f(s.get("under_tix"))
        om, um = _f(s.get("over_money")), _f(s.get("under_money"))
        if ot is None:
            continue
        if ut is None:
            ut = 100.0 - ot
        books = qmap.get(gid) or {}
        dk = books.get(FALLBACK)
        if not dk:
            continue
        line = _f(dk.get("total_line", dk.get("line")))
        if line is None or not _line_ok(line):
            continue
        under_shop = shop_side(books, "under", line)
        over_shop = shop_side(books, "over", line)
        if under_shop is None:
            continue
        hs, aws = _f(s.get("home_score", s.get("hs"))), _f(s.get("away_score", s.get("aws")))
        pin = books.get("pinnacle")
        pin_line = _f(pin.get("total_line", pin.get("line"))) if pin else None
        pin_fair_over = None
        pin_gap_s = None
        if pin and pin_line is not None and float(pin_line) == float(line):
            pin_fair_over, _ = devig(_f(pin.get("over_price")),
                                     _f(pin.get("under_price")))
            pin_gap_s = _gap_seconds(pin.get("snapshot_at"),
                                     dk.get("snapshot_at"))
        over_rlm = None if (om is None or ot is None) else (om - ot)
        out.append({
            "game_id": gid,
            "game_date": s["game_date"],
            "month": s["game_date"][:7],
            "hs": hs, "aws": aws,
            "line": float(line),
            "over_tix": ot, "under_tix": ut,
            "over_money": om, "under_money": um,
            "over_rlm": over_rlm,
            "under_book": under_shop[0], "under_price": under_shop[1],
            "over_book": None if over_shop is None else over_shop[0],
            "over_price": None if over_shop is None else over_shop[1],
            "pin_fair_over": pin_fair_over,
            "pin_gap_s": pin_gap_s,
            "public_side": "over" if ot >= ut else "under",
            "public_tix": max(ot, ut),
        })
    return out


def bet_row(board: dict, side: str) -> dict | None:
    price = board["over_price"] if side == "over" else board["under_price"]
    book = board["over_book"] if side == "over" else board["under_book"]
    if price is None or book is None:
        return None
    result, _ = grade_total(side, board["line"], board["hs"], board["aws"])
    if result is None:
        return None
    units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
    return {
        "game_id": board["game_id"],
        "game_date": board["game_date"],
        "side": side,
        "price": price,
        "book": book,
        "line": board["line"],
        "result": result,
        "units": units,
        "over_tix": board["over_tix"],
        "under_tix": board["under_tix"],
        "over_money": board["over_money"],
        "over_rlm": board["over_rlm"],
        "fade_tix": board["over_tix"] if side == "under" else board["under_tix"],
    }


def fade_over_tickets(board: list[dict], *, cut: float) -> list[dict]:
    """I24 family: fade a public OVER pile, bet UNDER."""
    rows = []
    for b in board:
        if b["over_tix"] < cut:
            continue
        row = bet_row(b, "under")
        if row:
            rows.append(row)
    return rows


def fade_under_tickets(board: list[dict], *, cut: float) -> list[dict]:
    """Fade a public UNDER pile, bet OVER. Coverage is thin (max under tix 59)."""
    rows = []
    for b in board:
        if b["under_tix"] is None or b["under_tix"] < cut:
            continue
        row = bet_row(b, "over")
        if row:
            rows.append(row)
    return rows


def fade_over_money(board: list[dict], *, cut: float) -> list[dict]:
    """Fade the OVER money pile (not tickets), bet UNDER."""
    rows = []
    for b in board:
        money = b.get("over_money")
        if money is None or money < cut:
            continue
        row = bet_row(b, "under")
        if row:
            row["fade_tix"] = money
            rows.append(row)
    return rows


def rlm_fade_over(board: list[dict], *, tix_cut: float, rlm_max: float
                  ) -> list[dict]:
    """Ticket-heavy OVER whose money lags (rlm = money − tickets ≤ rlm_max)."""
    rows = []
    for b in board:
        if b["over_rlm"] is None:
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
    """Money-ahead-of-tickets on OVER — follow the over (control)."""
    rows = []
    for b in board:
        if b["over_rlm"] is None:
            continue
        if b["over_tix"] < tix_cut:
            continue
        if b["over_rlm"] < rlm_min:
            continue
        row = bet_row(b, "over")
        if row:
            rows.append(row)
    return rows


def fade_over_pin_agree(board: list[dict], *, cut: float,
                        max_gap_s: float = MAX_GAP_S) -> list[dict]:
    """Fade OVER tickets only when time-aligned Pin no-vig leans UNDER."""
    rows = []
    for b in board:
        if b["over_tix"] < cut:
            continue
        fair = b.get("pin_fair_over")
        gap = b.get("pin_gap_s")
        if fair is None or gap is None or gap > max_gap_s:
            continue
        if fair >= 0.5:  # Pin leans over — do not fade
            continue
        row = bet_row(b, "under")
        if row:
            rows.append(row)
    return rows


def overlay_public_steam(board: list[dict], *, tix_cut: float, pp_cut: float,
                         mode: str, follow_steam: bool) -> list[dict]:
    """Public OVER pile × DK total steam. `mode` is oppose / agree / any.

    Prices stay the public-board shop (same as fade_over_tickets). Steam is
    only a direction / magnitude filter — move_over_pp from DK open→latest
    juiced over-implied, equal line only. A line change is not this overlay
    (that is the steam-number family).
    """
    if mode not in ("oppose", "agree", "any"):
        raise ValueError(mode)
    rows = []
    for b in board:
        move = b.get("move_over_pp")
        if move is None or abs(move) < pp_cut:
            continue
        if b["over_tix"] < tix_cut:
            continue
        steam_over = move > 0
        public_over = True  # this overlay is the OVER-pile family
        oppose = public_over != steam_over
        if mode == "oppose" and not oppose:
            continue
        if mode == "agree" and oppose:
            continue
        if follow_steam:
            bet_side = "over" if steam_over else "under"
        else:
            bet_side = "under"
        row = bet_row(b, bet_side)
        if row:
            row["move"] = move
            row["fade_tix"] = b["over_tix"]
            rows.append(row)
    return rows


def attach_steam(board: list[dict], steam_rows: list[dict]) -> list[dict]:
    """Copy DK open→latest over-implied move (equal line) onto the public board."""
    smap = {}
    for m in steam_rows:
        gid = m.get("game_id")
        if not gid:
            continue
        smap[gid] = {
            "move_over_pp": _f(m.get("move_over_pp")),
            "total_move": _f(m.get("total_move")),
        }
    for b in board:
        extra = smap.get(b["game_id"]) or {}
        b["move_over_pp"] = extra.get("move_over_pp")
        b["total_move"] = extra.get("total_move")
    return board


def report_cells(title: str, cells: list[tuple[str, list[dict]]]) -> dict:
    print(f"\n=== {title} ===")
    winners = {}
    for name, rows in cells:
        s = summarize(rows)
        print(f"  {name:<46s} {_fmt(s)}")
        if s.get("clears"):
            winners[name] = s
    return winners


def pin_candidates(quotes: list[dict], games: dict, *, vs: str,
                   pin_lean: bool, min_edge: float,
                   max_gap_s: float = MAX_GAP_S) -> list[dict]:
    """One bet per game: largest time-aligned Pin-vs-soft disagreement.

    EQUAL total_line only. Pair refused when |pin.snap − soft.snap| > 300s.
    That look-ahead (latest DK hours after Pin) manufactured the earlier ≥2pp.
    """
    qmap: dict[str, dict] = defaultdict(dict)
    for q in quotes:
        bk = q.get("bookmaker") or q.get("book")
        qmap[q["game_id"]][bk] = q
    rows = []
    for gid, books in qmap.items():
        g = games.get(gid)
        if not g:
            continue
        pin = books.get("pinnacle")
        if not pin:
            continue
        sline = _f(pin.get("total_line", pin.get("line")))
        sf, _ = devig(_f(pin.get("over_price")), _f(pin.get("under_price")))
        if sf is None or sline is None or not _line_ok(sline):
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
            bline = _f(q.get("total_line", q.get("line")))
            if bline is None or float(bline) != float(sline):
                continue
            gap = _gap_seconds(pin.get("snapshot_at"), q.get("snapshot_at"))
            if gap is None or gap > max_gap_s:
                continue
            fa, fb = devig(_f(q.get("over_price")), _f(q.get("under_price")))
            for side, fair, key in sides:
                price = _f(q.get(key))
                if price is None or implied(price) is None:
                    continue
                if not _price_ok(price):
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
        result, _ = grade_total(side, line, g.get("hs"), g.get("aws"))
        if result is None:
            continue
        units = 0.0 if result == "PUSH" else american_units(price, result == "WIN")
        rows.append({
            "game_id": gid, "game_date": g["game_date"],
            "side": side, "price": price, "book": bk, "line": line,
            "result": result, "units": units, "edge": edge,
        })
    return rows


def steam_candidates(moves: list[dict], *, pp_cut: float, follow: bool,
                     kind: str = "juice") -> list[dict]:
    """Bet steamed (or faded) totals side.

    kind='juice': |move_over_pp| ≥ pp_cut at an equal line.
    kind='number': |total_move| ≥ pp_cut (pp_cut is runs, e.g. 0.5).
    Prices are the *open* shop (first DK open) so steam is not look-ahead.
    """
    rows = []
    for m in moves:
        if kind == "number":
            move = _f(m.get("total_move"))
            line = _f(m.get("open_line", m.get("line")))
            over_p = _f(m.get("open_over", m.get("over_price")))
            under_p = _f(m.get("open_under", m.get("under_price")))
        else:
            move = _f(m.get("move_over_pp"))
            line = _f(m.get("open_line", m.get("line")))
            over_p = _f(m.get("open_over", m.get("over_price")))
            under_p = _f(m.get("open_under", m.get("under_price")))
        if move is None or abs(move) < pp_cut:
            continue
        if line is None or not _line_ok(line):
            continue
        steamed_over = move > 0
        if follow:
            side = "over" if steamed_over else "under"
        else:
            side = "under" if steamed_over else "over"
        price = over_p if side == "over" else under_p
        if price is None or not _price_ok(price):
            continue
        result, _ = grade_total(side, line, _f(m.get("hs")), _f(m.get("aws")))
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


def enrich_steam_rows(raw: list[dict]) -> list[dict]:
    """Add move_over_pp / total_move when the cache only has first+last prices."""
    out = []
    for m in raw:
        row = dict(m)
        open_line = _f(m.get("open_line"))
        last_line = _f(m.get("last_line", m.get("line")))
        if open_line is not None and last_line is not None:
            row["total_move"] = last_line - open_line
        open_over = _f(m.get("open_over"))
        last_over = _f(m.get("last_over"))
        # Juice steam only when the number did not move — otherwise the
        # implied gap is a different proposition (the look-ahead trap).
        if (open_line is not None and last_line is not None
                and float(open_line) == float(last_line)
                and open_over is not None and last_over is not None):
            io, il = implied(open_over), implied(last_over)
            if io is not None and il is not None:
                row["move_over_pp"] = (il - io) * 100.0
        if "game_date" in row and hasattr(row["game_date"], "isoformat"):
            row["game_date"] = row["game_date"]
        out.append(row)
    return out


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
                "game_id": r[0], "game_date": str(r[1])[:10],
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
        games = {}
        steam = []
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
                    "game_date": str(r[6])[:10], "hs": r[7], "aws": r[8],
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
                       f.line AS open_line, f.op AS open_over, f.up AS open_under
                FROM last l JOIN first f ON f.game_id = l.game_id
                WHERE l.snapshot_at <> f.snapshot_at
            """, (start, stop)).fetchall()
            for r in srows:
                steam.append({
                    "game_id": r[0], "game_date": str(r[1])[:10],
                    "last_line": r[2], "last_over": r[3], "last_under": r[4],
                    "hs": r[5], "aws": r[6],
                    "open_line": r[7], "open_over": r[8], "open_under": r[9],
                    "bookmaker": "draftkings",
                })
            d = nxt
        return {
            "splits": splits, "quotes": quotes,
            "pin_quotes": pin_quotes, "games": games,
            "steam": enrich_steam_rows(steam),
        }
    finally:
        conn.close()


def run_public(board: list[dict]) -> dict:
    cells = []
    for cut in (65, 70, 75, 80, 85, 90):
        rows = fade_over_tickets(board, cut=float(cut))
        cells.append((f"fade-over t{cut} all-pass", rows))
        for k in (1, 2, 3):
            cells.append((
                f"fade-over t{cut} ticket top-{k}",
                top_k(rows, k, lambda r: r["fade_tix"]),
            ))
    # I24 as a labelled cell — already live; not a new construction.
    i24 = juice_band(
        top_k(fade_over_tickets(board, cut=80.0), 2, lambda r: r["fade_tix"]),
        -110, -100)
    cells.append(("I24 t80 + [-110,-100] top-2 (live, not new)", i24))
    for cut in (70, 75, 80, 85):
        rows = fade_over_money(board, cut=float(cut))
        cells.append((f"fade-over-money m{cut} all-pass", rows))
        for k in (2, 3):
            cells.append((
                f"fade-over-money m{cut} top-{k}",
                top_k(rows, k, lambda r: r["fade_tix"]),
            ))
    for cut in (70, 80):
        rows = fade_over_pin_agree(board, cut=float(cut))
        cells.append((f"fade-over ∩ Pin-under t{cut} (300s)", rows))
        cells.append((
            f"fade-over ∩ Pin-under t{cut} top-2",
            top_k(rows, 2, lambda r: r["fade_tix"]),
        ))
    return report_cells("public-over fade (beyond I24)", cells)


def run_under(board: list[dict]) -> dict:
    cells = []
    for cut in (40, 45, 50, 55):
        rows = fade_under_tickets(board, cut=float(cut))
        cells.append((f"fade-under t{cut} all-pass (bet OVER)", rows))
        for k in (1, 2):
            cells.append((
                f"fade-under t{cut} ticket top-{k}",
                top_k(rows, k, lambda r: r["fade_tix"]),
            ))
        cells.append((
            f"fade-under t{cut} juice[-110,-100]",
            juice_band(rows, -110, -100),
        ))
    return report_cells("public-under fade (bet OVER)", cells)


def run_juice(board: list[dict]) -> dict:
    cells = []
    bands = (
        (-110, -100, "I24-band"),
        (-115, -100, "[-115,-100]"),
        (-120, -100, "[-120,-100]"),
        (-110, -105, "[-110,-105]"),
        (-105, -100, "[-105,-100]"),
        (100, 130, "plus-money"),
    )
    for cut in (70, 75, 80, 85, 90):
        base = fade_over_tickets(board, cut=float(cut))
        for lo, hi, label in bands:
            banded = juice_band(base, lo, hi)
            cells.append((f"t{cut} {label} all-pass", banded))
            cells.append((
                f"t{cut} {label} top-2",
                top_k(banded, 2, lambda r: r["fade_tix"]),
            ))
    return report_cells("ticket × juice bands", cells)


def run_rlm(board: list[dict]) -> dict:
    cells = []
    for tix in (70, 75, 80, 85):
        for gap in (-5, -10, -15):
            rows = rlm_fade_over(board, tix_cut=float(tix), rlm_max=float(gap))
            cells.append((f"RLM fade-over t{tix} rlm≤{gap}", rows))
            cells.append((
                f"RLM fade-over t{tix} rlm≤{gap} top-2",
                top_k(rows, 2, lambda r: r["fade_tix"]),
            ))
        rows_m = follow_money_over(board, tix_cut=float(tix), rlm_min=5.0)
        cells.append((f"follow-money over t{tix} rlm≥5", rows_m))
    return report_cells("RLM on totals", cells)


def run_pin(pin_quotes: list[dict], games: dict) -> dict:
    if not pin_quotes or not games:
        print("\n=== Pin-vs-soft (300s) ===\n  (no pin board in this cache)")
        return {}
    cells = []
    for vs in ("implied", "devig"):
        for lean in (True, False):
            for cut in (0.015, 0.018, 0.020, 0.025, 0.030):
                rows = pin_candidates(
                    pin_quotes, games, vs=vs, pin_lean=lean, min_edge=cut)
                tag = f"pin-{vs}{' lean' if lean else ''} ≥{cut*100:.1f}pp 300s"
                cells.append((tag, rows))
                cells.append((f"{tag} top-2",
                              top_k(rows, 2, lambda r: r.get("edge", 0))))
    return report_cells("Pin-vs-soft (time-aligned 300s)", cells)


def run_steam(moves: list[dict]) -> dict:
    if not moves:
        print("\n=== steam ===\n  (no steam board in this cache)")
        return {}
    cells = []
    for follow in (True, False):
        verb = "follow" if follow else "fade"
        for cut in (1.0, 2.0, 3.0):
            rows = steam_candidates(moves, pp_cut=cut, follow=follow, kind="juice")
            cells.append((f"steam-juice {verb} ≥{cut:.0f}pp (equal line)", rows))
            cells.append((
                f"steam-juice {verb} ≥{cut:.0f}pp top-2",
                top_k(rows, 2, lambda r: abs(r.get("move") or 0)),
            ))
        for cut in (0.5, 1.0, 1.5):
            rows = steam_candidates(moves, pp_cut=cut, follow=follow, kind="number")
            cells.append((f"steam-number {verb} ≥{cut} runs", rows))
            cells.append((
                f"steam-number {verb} ≥{cut} top-2",
                top_k(rows, 2, lambda r: abs(r.get("move") or 0)),
            ))
    return report_cells("steam / anti-steam", cells)


def run_overlay(board: list[dict]) -> dict:
    n_move = sum(1 for b in board if b.get("move_over_pp") is not None)
    print(f"\n=== public × steam overlay ===\n  "
          f"board rows with equal-line move_over_pp: {n_move}/{len(board)}")
    if n_move == 0:
        print("  (no juice-steam attached — pass steam rows in --json)")
        return {}
    cells = []
    for follow in (False, True):
        verb = "follow-steam" if follow else "fade-public"
        for mode in ("oppose", "agree", "any"):
            for tix in (70, 75, 80):
                for pp in (1.0, 2.0, 3.0):
                    rows = overlay_public_steam(
                        board, tix_cut=float(tix), pp_cut=pp,
                        mode=mode, follow_steam=follow)
                    tag = f"{verb} {mode} t{tix} ≥{pp:.0f}pp"
                    cells.append((tag, rows))
                    cells.append((
                        f"{tag} top-2",
                        top_k(rows, 2, lambda r: r["fade_tix"]),
                    ))
    return report_cells("public × steam overlay", cells)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--json", default=None,
                    help="splits+quotes JSON (sandbox cache of Supabase)")
    ap.add_argument("--family", action="append", default=[],
                    choices=FAMILIES,
                    help="Repeatable. Default: all families present in the cache")
    args = ap.parse_args()
    families = tuple(args.family) if args.family else FAMILIES

    if args.json:
        raw = load_json(args.json)
        raw["steam"] = enrich_steam_rows(raw.get("steam") or [])
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
    print(f"public ∩ DK-total board: {len(board)} games  "
          f"months={sorted({b['month'] for b in board})}  "
          f"with_juice_move={sum(1 for b in board if b.get('move_over_pp') is not None)}  "
          f"with_number_move={sum(1 for b in board if b.get('total_move') not in (None, 0))}")

    winners: dict = {}
    if "public" in families:
        winners.update(run_public(board))
    if "under" in families:
        winners.update(run_under(board))
    if "juice" in families:
        winners.update(run_juice(board))
    if "rlm" in families:
        winners.update(run_rlm(board))
    if "pin" in families:
        games = raw.get("games") or {}
        pin_q = raw.get("pin_quotes") or raw.get("quotes") or []
        if not games:
            for b in board:
                games[b["game_id"]] = {
                    "game_date": b["game_date"], "hs": b["hs"], "aws": b["aws"],
                }
        winners.update(run_pin(pin_q, games))
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
            print(f"  {name:<46s} {_fmt(s)}")
        print("\n  I24 is already live and is not a new construction. "
              "A CLEAR cell that is I24, or a K/ticket peak whose "
              "neighbours go red, is not shipped.")


if __name__ == "__main__":
    main()
