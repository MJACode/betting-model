"""The market-relative rule on GAME LINES, not props.

THE ARGUMENT FOR TRYING THIS. models/nfl_prop_market is the only construction in
this repo with a blind-tested positive result (+10.33% over 954 bets). It has
only ever been applied to PLAYER PROPS, and props are the most heavily juiced
market we touch -- measured 2026-09-07 on the live NFL board, the hold runs 5.7%
to 24.3% by market, so a bet must beat DraftKings' own de-vigged number by 3 to
12 points merely to break even. Game lines run about half that.

And the data is already bought. `odds` holds Pinnacle on 6,788 MLB games and
2,719 NCAAF games across h2h, spreads and totals -- roughly ten times the sample
the prop rule was validated on, at no additional cost.

Same construction, no changes: de-vig Pinnacle, bet a soft book where its own
de-vigged price disagrees by more than the threshold.

THE TRAPS, all three carried over deliberately.

  EQUAL LINES ONLY. Pinnacle at -1.5 against DraftKings at -2.5 is a DIFFERENT
  PROPOSITION, and calling that price gap an edge manufactures one out of thin
  air -- §5c discarded 35,107 quotes on this rule and §5b showed what happens
  when it is skipped. h2h has no line and is compared directly; spreads and
  totals must match to the point.

PRE-GAME ONLY. `odds.snapshot_type` is `open` | `in_play` | `close`
  (some rows NULL). `odds` has no commence_time — that column lives on
  `games`. This sweep reads `snapshot_type = 'open'` and `snapshot_at`,
  and still leak-bounds `snapshot_at <= games.commence_time` because the
  evening refresh has written post-start rows as `open` (session 106).
  `close` is CLV; `in_play` is live. The prop version of this leak (#534)
  manufactured seven of every eight "edges".

  ONE BET PER PROPOSITION. The same game at three books is one opinion.

Grading is the game result, so there is no player-name join and no stat-mapping
question -- the two things that made the prop backtests fragile.

Thin cells still print (Error Handler 2026-09-15: document ROI at 2/3/4pp even
when n is small). A cell with n < 25 is labelled thin; it is not dropped.

    python -m scripts.game_line_market_sweep
    python -m scripts.game_line_market_sweep --sport MLB --market totals --bettable --edges 0.02 0.03 0.04 --by-month
    python -m scripts.game_line_market_sweep --sport MLB --market spreads --bettable --edges 0.02 0.03 0.04 --by-month
    python -m scripts.game_line_market_sweep --sport MLB --market totals --soft-books draftkings --vs implied --pin-lean --edges 0.02 0.03 0.04 --by-month
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np

from data.db import get_connection

SHARP = "pinnacle"
SOFT = ("draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet",
        "betrivers", "hardrockbet", "bovada")
SNAPSHOT_TYPES = ("open", "in_play", "close")
QUOTE_ORDERS = ("latest", "earliest")
VS_MODES = ("devig", "implied")
DEFAULT_EDGES = (0.02, 0.03, 0.04)
# First-five quotes grade on games.home_score_f5 / away_score_f5, never the
# full-game score. Mixing those manufactured a spread-move feature in the
# handicap block; it would also invent a fake F5 result here.
F5_MARKETS = {
    "h2h_1st_5_innings": "h2h",
    "spreads_1st_5_innings": "spreads",
    "totals_1st_5_innings": "totals",
}
BASE_MARKETS = ("h2h", "spreads", "totals")
# Unbounded odds scans time out on MCP. Month windows keep each SELECT inside
# an index-friendly range. Pad snapshot_at 14 days before the game_date window
# so an opener posted in March for an April game is not dropped.
SNAPSHOT_PAD_DAYS = 14
THIN_N = 25


def implied(a):
    a = float(a)
    return 100.0 / (a + 100.0) if a > 0 else abs(a) / (abs(a) + 100.0)


def devig(a, b):
    """Proportional de-vig. None if either side is missing."""
    if a is None or b is None:
        return None, None
    ia, ib = implied(a), implied(b)
    t = ia + ib
    if t <= 0:
        return None, None
    return ia / t, ib / t


def profit(price, won):
    if won is None:
        return 0.0                      # push
    p = float(price)
    return (p / 100.0 if p > 0 else 100.0 / abs(p)) if won else -1.0


def iter_months(date_from: str, date_to: str):
    """Half-open [start, end) month windows covering [date_from, date_to)."""
    d = date.fromisoformat(date_from)
    end = date.fromisoformat(date_to)
    if d >= end:
        return
    d = d.replace(day=1)
    while d < end:
        nxt = date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
        start = max(d, date.fromisoformat(date_from)).isoformat()
        stop = min(nxt, end).isoformat()
        if start < stop:
            yield start, stop
        d = nxt


def base_market(market: str) -> str:
    """Map an odds.market key onto h2h / spreads / totals for matching + grading."""
    return F5_MARKETS.get(market, market)


def load(conn, sport: str, market: str, snapshot_type: str = "open",
         date_from: str | None = None, date_to: str | None = None,
         quote: str = "latest"):
    """One pre-game quote per (game, book) plus the game's result.

    `quote='latest'` (default) is the card: last OPEN before commence.
    `quote='earliest'` is the opener. Pairing earliest Pin with earliest
    soft *without* a 5-minute gap is look-ahead — measured 2026-09-16,
    the +33% totals 2pp cell is the 14-hour tail; aligned-first is n=1.
    """
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"snapshot_type must be one of {SNAPSHOT_TYPES}, "
                         f"got {snapshot_type!r}")
    if quote not in QUOTE_ORDERS:
        raise ValueError(f"quote must be one of {QUOTE_ORDERS}, got {quote!r}")
    bm = base_market(market)
    if bm not in BASE_MARKETS:
        raise ValueError(f"market must be h2h/spreads/totals or an F5 key, "
                         f"got {market!r}")
    extra = []
    params: list = [sport, market, snapshot_type]
    if date_from:
        extra.append("AND g.game_date >= %s")
        params.append(date_from)
        pad = (date.fromisoformat(date_from[:10])
               - timedelta(days=SNAPSHOT_PAD_DAYS)).isoformat()
        extra.append("AND o.snapshot_at >= %s")
        params.append(pad)
    if date_to:
        extra.append("AND g.game_date < %s")
        params.append(date_to)
        extra.append("AND o.snapshot_at < %s")
        params.append(date_to)
    extra_sql = "\n          ".join(extra)
    f5 = market in F5_MARKETS
    score_sql = ("g.home_score_f5, g.away_score_f5" if f5
                 else "g.home_score, g.away_score")
    score_bound = ("AND g.home_score_f5 IS NOT NULL AND g.away_score_f5 IS NOT NULL"
                   if f5 else
                   "AND g.home_score IS NOT NULL AND g.away_score IS NOT NULL")
    order = "ASC" if quote == "earliest" else "DESC"
    rows = conn.execute(f"""
        SELECT DISTINCT ON (o.game_id, o.bookmaker)
               o.game_id, o.bookmaker, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price,
               {score_sql}, g.game_date, o.snapshot_at
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = %s AND o.market = %s
          {score_bound}
          AND o.snapshot_type = %s
          AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
          {extra_sql}
        ORDER BY o.game_id, o.bookmaker, o.snapshot_at {order}
    """, tuple(params)).fetchall()
    by_game = defaultdict(dict)
    meta = {}
    for (gid, bk, hp, ap, sh, tl, op, up, hs, as_, gd, snap) in rows:
        by_game[gid][bk] = dict(home=hp, away=ap, spread=sh, total=tl,
                                over=op, under=up, snap=snap)
        meta[gid] = (float(hs), float(as_), str(gd)[:10])
    return by_game, meta


def load_chunked(conn, sport: str, market: str, snapshot_type: str = "open",
                 date_from: str | None = None, date_to: str | None = None,
                 quote: str = "latest"):
    """Month-chunked load so a full-season scan does not time out."""
    if not date_from or not date_to:
        return load(conn, sport, market, snapshot_type, date_from, date_to,
                    quote=quote)
    by_game: dict = defaultdict(dict)
    meta: dict = {}
    for start, stop in iter_months(date_from, date_to):
        chunk_g, chunk_m = load(conn, sport, market, snapshot_type, start, stop,
                                quote=quote)
        for gid, books in chunk_g.items():
            by_game[gid].update(books)
        meta.update(chunk_m)
    return by_game, meta


def _gap_seconds(a, b) -> float | None:
    """|a - b| in seconds for two stored timestamps, or None if unparseable."""
    from features.feature_engine import _parse_iso_ts
    ta, tb = _parse_iso_ts(a), _parse_iso_ts(b)
    if ta is None or tb is None:
        return None
    return abs((ta - tb).total_seconds())


def grade(market, side, m, line):
    """True/False/None(push) for a side, given the final score."""
    hs, as_, _gd = m
    if market == "h2h":
        if hs == as_:
            return None
        return (hs > as_) if side == "home" else (as_ > hs)
    if market == "spreads":
        marg = hs - as_ + float(line)          # line is the HOME number (§4)
        if marg == 0:
            return None
        return marg > 0 if side == "home" else marg < 0
    total = hs + as_
    if total == float(line):
        return None
    return total > float(line) if side == "over" else total < float(line)


def collect_picks(by_game, meta, market: str, max_gap_s: float | None = 300,
                  vs: str = "devig", pin_lean: bool = False,
                  soft_books=None, juice_abs_max: float | None = None,
                  min_line: float | None = None, max_line: float | None = None):
    """One candidate per game: largest Pin-vs-soft disagreement on an equal line.

    vs='devig'   — Pin de-vig minus the soft book's own de-vig (nfl_prop_market).
    vs='implied' — Pin de-vig minus the soft book's juiced implied (GROK Pin-lean).
    pin_lean     — only the side Pinnacle's no-vig prefers (max sharp_p).
    `market` may be an F5 key; matching and grading use the base market.
    juice_abs_max — drop a bet whose American |price| exceeds this (Mike's −200..200).
    min_line / max_line — totals `total_line` floor/ceiling (Mike's 5.5–14.5).
    """
    if vs not in VS_MODES:
        raise ValueError(f"vs must be one of {VS_MODES}, got {vs!r}")
    bm = base_market(market)
    if bm not in BASE_MARKETS:
        raise ValueError(f"market must be h2h/spreads/totals or an F5 key, "
                         f"got {market!r}")
    soft = tuple(soft_books) if soft_books is not None else SOFT
    picks = []
    diag = defaultdict(int)
    for gid, books in by_game.items():
        sharp = books.get(SHARP)
        if not sharp:
            diag["no_sharp"] += 1
            continue
        if bm == "h2h":
            sf, _ = devig(sharp["home"], sharp["away"])
            su = 1 - sf if sf is not None else None
            sline = None
            sides = (("home", sf, "home"), ("away", su, "away"))
        elif bm == "spreads":
            sline = sharp["spread"]
            sf, _ = devig(sharp["home"], sharp["away"])
            su = 1 - sf if sf is not None else None
            sides = (("home", sf, "home"), ("away", su, "away"))
        else:
            sline = sharp["total"]
            sf, _ = devig(sharp["over"], sharp["under"])
            su = 1 - sf if sf is not None else None
            sides = (("over", sf, "over"), ("under", su, "under"))
        if sf is None:
            diag["sharp_one_way"] += 1
            continue
        if bm in ("totals", "spreads") and sline is not None:
            sl = float(sline)
            if min_line is not None and sl < float(min_line):
                diag["line_range"] += 1
                continue
            if max_line is not None and sl > float(max_line):
                diag["line_range"] += 1
                continue
        if pin_lean:
            sides = (max(sides, key=lambda s: (s[1] is not None, s[1] or 0.0)),)

        best = None
        for bk, q in books.items():
            if bk not in soft:
                continue
            bline = q["spread"] if bm == "spreads" else (
                q["total"] if bm == "totals" else None)
            if sline is not None and (bline is None or float(bline) != float(sline)):
                diag["line_mismatch"] += 1
                continue
            # SIMULTANEOUS OR IT IS NOT A DISAGREEMENT. §5c established the
            # prop rule on paired quotes 98.9% within five minutes, precisely so
            # the result could not be stale-vs-fresh. Game lines are stored per
            # book on independent cadences, so the latest pre-game quote from
            # two books can be hours apart -- and a STALE SHARP price against a
            # current soft one manufactures edge in the direction the rule bets.
            # Measured on MLB h2h: median gap 0s, but only 77% inside 5 minutes.
            if max_gap_s is not None:
                gap = _gap_seconds(sharp.get("snap"), q.get("snap"))
                if gap is None or gap > max_gap_s:
                    diag["not_simultaneous"] += 1
                    continue
            if bm == "totals":
                a, b = q["over"], q["under"]
            else:
                a, b = q["home"], q["away"]
            fa, fb = devig(a, b)
            if vs == "devig" and fa is None:
                diag["soft_one_way"] += 1
                continue
            for side, sharp_p, _k in sides:
                price = (a if side in ("home", "over") else b)
                if price is None or sharp_p is None:
                    continue
                if juice_abs_max is not None and abs(float(price)) > float(juice_abs_max):
                    diag["juice"] += 1
                    continue
                if vs == "implied":
                    try:
                        soft_p = implied(price)
                    except (TypeError, ValueError):
                        continue
                else:
                    soft_p = fa if side in ("home", "over") else fb
                    if soft_p is None:
                        continue
                edge = sharp_p - soft_p
                if best is None or edge > best[0]:
                    best = (edge, side, price, bk, sline)
            diag["compared"] += 1
        if best is None:
            continue
        edge, side, price, bk, line = best
        won = grade(bm, side, meta[gid], line)
        picks.append((meta[gid][2], edge, price, won, bk))
    return picks, diag


def _summarize(picks, edges) -> list[dict]:
    """ROI at each edge. Thin cells still report; they are labelled, not dropped."""
    out = []
    for e in edges:
        sel = [p for p in picks if p[1] >= e and p[3] is not None]
        n = len(sel)
        row = {"min_edge": float(e), "n": n, "thin": n < THIN_N,
               "win_pct": None, "roi_pct": None, "units": None,
               "ci90": None}
        if n == 0:
            out.append(row)
            continue
        prof = [profit(p[2], p[3]) for p in sel]
        u = float(sum(prof))
        w = sum(1 for x in prof if x > 0)
        row["win_pct"] = 100.0 * w / n
        row["roi_pct"] = 100.0 * u / n
        row["units"] = u
        if n >= 2:
            rng = np.random.default_rng(42)
            a = np.array(prof)
            idx = rng.integers(0, len(a), (10000, len(a)))
            roi = 100 * a[idx].mean(axis=1)
            row["ci90"] = [float(np.percentile(roi, 5)),
                           float(np.percentile(roi, 95))]
        out.append(row)
    return out


def _split_halves(picks, edges, split_date: str = "2026-07-01"):
    early = [p for p in picks if p[0] < split_date]
    late = [p for p in picks if p[0] >= split_date]
    return {
        "split_date": split_date,
        "early": _summarize(early, edges),
        "late": _summarize(late, edges),
    }


def _by_month(picks, edges) -> dict:
    buckets: dict[str, list] = defaultdict(list)
    for p in picks:
        buckets[p[0][:7]].append(p)
    return {m: _summarize(buckets[m], edges) for m in sorted(buckets)}


def sweep(conn, sport: str, market: str, edges,
          max_gap_s: float | None = 300,
          snapshot_type: str = "open",
          date_from: str | None = None, date_to: str | None = None,
          vs: str = "devig", pin_lean: bool = False,
          soft_books=None, by_month: bool = False,
          quote: str = "latest", juice_abs_max: float | None = None,
          min_line: float | None = None, max_line: float | None = None):
    by_game, meta = load_chunked(
        conn, sport, market, snapshot_type=snapshot_type,
        date_from=date_from, date_to=date_to, quote=quote)
    picks, diag = collect_picks(
        by_game, meta, market, max_gap_s=max_gap_s, vs=vs,
        pin_lean=pin_lean, soft_books=soft_books,
        juice_abs_max=juice_abs_max, min_line=min_line, max_line=max_line)
    # Legacy tuple so existing callers that unpacked (e, n, w, roi, ci) still
    # work: ROI is always filled when n>0 (thin is no longer a silent drop).
    legacy = []
    for row in _summarize(picks, edges):
        ci = tuple(row["ci90"]) if row["ci90"] is not None else None
        legacy.append((row["min_edge"], row["n"], row["win_pct"],
                       row["roi_pct"], ci))
    extra = {}
    if by_month:
        extra["by_month"] = _by_month(picks, edges)
        extra["halves"] = _split_halves(picks, edges)
    return legacy, diag, picks, extra


def _print_table(res, indent="    "):
    print(f"{indent}{'min_edge':>8} {'bets':>6} {'win%':>6} {'ROI':>8} "
          f"{'units':>8} {'90% CI':>18}")
    for e, n, w, roi, ci in res:
        tag = " (thin)" if n < THIN_N else ""
        if n == 0 or roi is None:
            print(f"{indent}{e:>7.0%} {n:>6}{tag}")
            continue
        ci_s = ""
        if ci is not None:
            ci_s = f"({ci[0]:+.1f}, {ci[1]:+.1f})"
        units = n * roi / 100.0
        print(f"{indent}{e:>7.0%} {n:>6} {w:>5.1f}% {roi:>+7.2f}% "
              f"{units:>+7.2f}u {ci_s:>18}{tag}")


def run(sport: str = "MLB", markets=None, edges=None,
        snapshot_type: str = "open", bettable: bool = True,
        by_month: bool = True, vs: str = "devig", pin_lean: bool = False,
        date_from: str | None = "2026-03-20", date_to: str | None = None,
        soft_books=None, max_gap_s: float | None = 300,
        quote: str = "latest", juice_abs_max: float | None = None,
        min_line: float | None = None, max_line: float | None = None) -> dict:
    """Worker-job entry: JSON-serializable grid. Does not publish anything."""
    markets = list(markets or ["spreads", "totals"])
    edges = [float(e) for e in (edges or DEFAULT_EDGES)]
    if date_to is None:
        date_to = (date.today() + timedelta(days=1)).isoformat()
    if quote not in QUOTE_ORDERS:
        raise ValueError(f"quote must be one of {QUOTE_ORDERS}, got {quote!r}")
    soft = tuple(soft_books) if soft_books else None
    if soft is None and bettable:
        import config as cfg
        soft = tuple(b for b in cfg.BEST_LINE_BOOKMAKERS if b != SHARP)
    conn = get_connection()
    try:
        out = {
            "sport": sport,
            "snapshot_type": snapshot_type,
            "quote": quote,
            "vs": vs,
            "pin_lean": bool(pin_lean),
            "bettable": bool(bettable),
            "soft_books": list(soft) if soft is not None else list(SOFT),
            "date_from": date_from,
            "date_to": date_to,
            "edges": edges,
            "max_gap_s": max_gap_s,
            "juice_abs_max": juice_abs_max,
            "min_line": min_line,
            "max_line": max_line,
            "markets": {},
        }
        for market in markets:
            res, diag, picks, extra = sweep(
                conn, sport, market, edges, max_gap_s=max_gap_s,
                snapshot_type=snapshot_type, date_from=date_from,
                date_to=date_to, vs=vs, pin_lean=pin_lean,
                soft_books=soft, by_month=by_month, quote=quote,
                juice_abs_max=juice_abs_max, min_line=min_line,
                max_line=max_line)
            block = {
                "diag": dict(diag),
                "n_candidates": len(picks),
                "pooled": _summarize(picks, edges),
            }
            if by_month:
                block["by_month"] = extra.get("by_month") or {}
                block["halves"] = extra.get("halves") or {}
            out["markets"][market] = block
            print(f"\n=== {sport} {market} — snapshot_type={snapshot_type} "
                  f"quote={quote} vs={vs} pin_lean={pin_lean}  "
                  f"sharp {SHARP}, {len(soft or SOFT)} soft books")
            print(f"    compared {diag['compared']}, line_mismatch "
                  f"{diag['line_mismatch']}, no_sharp {diag['no_sharp']}, "
                  f"graded {len(picks)}")
            _print_table(res)
            if by_month and extra.get("by_month"):
                for month, rows in extra["by_month"].items():
                    print(f"    -- {month}")
                    legacy = [(r["min_edge"], r["n"], r["win_pct"],
                               r["roi_pct"],
                               tuple(r["ci90"]) if r["ci90"] else None)
                              for r in rows]
                    _print_table(legacy, indent="      ")
            if by_month and extra.get("halves"):
                for label in ("early", "late"):
                    rows = extra["halves"][label]
                    print(f"    -- {label} (split "
                          f"{extra['halves']['split_date']})")
                    legacy = [(r["min_edge"], r["n"], r["win_pct"],
                               r["roi_pct"],
                               tuple(r["ci90"]) if r["ci90"] else None)
                              for r in rows]
                    _print_table(legacy, indent="      ")
        return out
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", nargs="+", default=["MLB"])
    ap.add_argument("--market", nargs="+", default=["spreads", "totals"])
    ap.add_argument("--edges", nargs="+", type=float, default=list(DEFAULT_EDGES),
                    help="min-edge floors to report (default 0.02 0.03 0.04)")
    ap.add_argument("--snapshot-type", default="open", choices=SNAPSHOT_TYPES,
                    help="odds.snapshot_type; commence_time is on games")
    ap.add_argument("--date-from", default="2026-03-20")
    ap.add_argument("--date-to", default=None)
    ap.add_argument("--bettable", action="store_true",
                    help="restrict soft books to BEST_LINE_BOOKMAKERS "
                         "(drop pinnacle/bovada/espnbet as a price to take)")
    ap.add_argument("--soft-books", nargs="+", default=None,
                    help="explicit soft-book list (overrides --bettable)")
    ap.add_argument("--vs", default="devig", choices=VS_MODES,
                    help="devig = Pin de-vig vs soft de-vig; "
                         "implied = Pin de-vig vs soft juiced implied")
    ap.add_argument("--pin-lean", action="store_true",
                    help="only the side Pinnacle's no-vig prefers")
    ap.add_argument("--by-month", action="store_true")
    ap.add_argument("--max-gap-s", type=float, default=300.0,
                    help="pair Pin/soft quotes only if |snap| <= this; "
                         "negative means unaligned (look-ahead measure)")
    ap.add_argument("--quote", default="latest", choices=list(QUOTE_ORDERS),
                    help="latest (card) or earliest (opener). Earliest without "
                         "a 5-minute gap is look-ahead on totals.")
    ap.add_argument("--juice-abs-max", type=float, default=None,
                    help="drop bets whose |American price| exceeds this")
    ap.add_argument("--min-line", type=float, default=None)
    ap.add_argument("--max-line", type=float, default=None)
    a = ap.parse_args()
    global SOFT
    if a.soft_books:
        SOFT = tuple(a.soft_books)
    elif a.bettable:
        import config as cfg
        SOFT = tuple(b for b in cfg.BEST_LINE_BOOKMAKERS if b != SHARP)
    gap = None if a.max_gap_s is not None and a.max_gap_s < 0 else a.max_gap_s
    for sport in a.sport:
        run(sport=sport, markets=a.market, edges=a.edges,
            snapshot_type=a.snapshot_type, bettable=a.bettable or bool(a.soft_books),
            by_month=a.by_month, vs=a.vs, pin_lean=a.pin_lean,
            date_from=a.date_from, date_to=a.date_to,
            soft_books=SOFT, max_gap_s=gap, quote=a.quote,
            juice_abs_max=a.juice_abs_max, min_line=a.min_line,
            max_line=a.max_line)


if __name__ == "__main__":
    main()
