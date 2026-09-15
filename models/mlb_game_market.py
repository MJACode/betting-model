"""
Market-relative MLB GAME LINES: de-vig Pinnacle, bet a bettable soft outlier.

WHY THIS EXISTS
---------------
`mlb_runline` and `mlb_over_under` are paused. The predictive artifacts do
not print money on leak-repaired stats (walk-forward AUC 0.555 / 0.507;
honest-era RL −6.93%; O/U 11-26 −16.08u on the live artifact). A losing
model is an assessment to run, not a model to pause (CLAUDE.md §1b). This
file is the construction that DID clear the standards for spreads.

THE CONSTRUCTION. Same as models/nfl_prop_market, pointed at game lines:
de-vig Pinnacle, bet a soft book where its own de-vigged price disagrees
by more than the threshold, equal lines only, pre-game only, simultaneous
quotes (5 min), one bet per game (best edge).

THE CUT. 1.8pp, measured 2026-09-15 on 2026 settled MLB spreads, Pinnacle
vs config.BEST_LINE_BOOKMAKERS (pinnacle/bovada/espnbet excluded — those
are not a price a US bettor can take):

    min_edge   n     ROI     early (to 06-30)    late (from 07-01)
    0.015    622   +2.22%   −1.55% / 361        +7.44% / 261
    0.018    367   +4.80%   +1.52% / 214        +9.38% / 153
    0.020    233   +7.28%   −0.05% / 139       +18.12% / 94

0.018 is the only cell in that neighbourhood with both time halves
positive, n >> 25, and pooled neighbours (0.015, 0.020) also positive.
Monthly at 0.018: Apr +0.45 / May −2.15 / Jun +9.69 / Jul +9.10 /
Aug +8.68 / Sep +11.19 (5 of 6 months positive). Both sides positive
(away +3.25% / 175, home +7.19% / 192). Every matching line in the
sample is the run line (±1.5).

TOTALS. The paper publisher IS GROK's measured construction, not a
generalisation of it: Pin OPEN no-vig lean minus DraftKings OPEN
juiced implied, equal total, ≥2pp, DK-only. GROK Apr–Jul ~+11%
n≈103. Shopping BEST_LINE or de-vigging the soft book is a different
population (May–Jun Pin-de-vig vs bettable-soft-de-vig 2pp −11.13% /
79). Accidental callers of find_total_bets still hit MIN_EDGE_TOTALS
= 1.0 (a wall). INSERT stays off until `MLB_TOTAL_MARKET_PUBLISH=1`
AND the worker GROK job confirms the same construction.
`mlb_over_under` stays paused.

PUBLISH. Both cards default to log-only. This PR does not go live.
Spreads: GROK Pin-vs-DK ≥2pp ~−5% n≈200 — do not INSERT.
`MLB_SPREAD_MARKET_PUBLISH` / `MLB_TOTAL_MARKET_PUBLISH` (default 0).

Soft books are BEST_LINE_BOOKMAKERS, not LINE_SHOP. Betting Bovada or
Pinnacle manufactured the 1pp plateau that disappeared once the
unbettable books were dropped (docs/mlb_runline_ou_edge_search.md).
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import config
from models.market_relative import devig, implied

SHARP_BOOK = "pinnacle"
MAX_GAP_S = 300.0
# The measured cut. Do not chase a neighbour; 2.0pp fails the early half.
MIN_EDGE_SPREADS = 0.018
# Totals: accidental callers must not fire. The paper card passes
# MIN_EDGE_TOTALS_PAPER (0.02) explicitly. GROK Pin-vs-DK ≥2pp Apr–Jul
# ~+11% n≈103 is the candidate; worker sweep must confirm.
MIN_EDGE_TOTALS = 1.0
MIN_EDGE_TOTALS_PAPER = 0.02

# Bettable retail books. Pinnacle is the reference; Bovada and espnbet
# are in LINE_SHOP on purpose and out of BEST_LINE on purpose.
SOFT_BOOKS = tuple(
    b for b in config.BEST_LINE_BOOKMAKERS
    if b != SHARP_BOOK
)
# GROK totals construction is DraftKings only. Pin no-vig lean minus
# DK's juiced implied. Shopping BEST_LINE here would INSERT a different
# population than the Apr–Jul ~+11% n≈103 sample. Sweeps that want
# other books pass soft_books explicitly.
TOTALS_SOFT_BOOKS = ("draftkings",)


@dataclass(frozen=True)
class GameMarketBet:
    game_id: str
    market: str          # "spreads" | "totals"
    side: str            # "home" | "away" | "over" | "under"
    book: str
    line: float          # HOME spread, or the total
    price: float         # soft book's American price on `side`
    fair: float          # Pinnacle de-vigged probability of `side`
    edge: float          # spreads: fair − soft de-vig; totals: fair − soft implied
    sharp_price: float
    snap: str | None = None


def _gap_seconds(a, b) -> float | None:
    from features.feature_engine import _parse_iso_ts
    ta, tb = _parse_iso_ts(a), _parse_iso_ts(b)
    if ta is None or tb is None:
        return None
    return abs((ta - tb).total_seconds())


def _is_runline(line) -> bool:
    if line is None:
        return False
    return abs(abs(float(line)) - 1.5) < 1e-9


def publish_enabled(market: str) -> bool:
    """INSERT gate. Default off: cards log, they do not write picks."""
    if market == "spreads":
        return bool(config.MLB_SPREAD_MARKET_PUBLISH)
    if market == "totals":
        return bool(config.MLB_TOTAL_MARKET_PUBLISH)
    return False


def load_latest_quotes(conn, sport: str, market: str, game_ids: list[str],
                       as_of=None) -> dict:
    """Latest OPEN quote per (game, book) for the given games.

    `odds.snapshot_type` is open|in_play|close. `odds` has no commence_time
    — that lives on `games`. We still leak-bound snapshot_at <= commence_time
    because the evening refresh has written post-start rows as open.
    """
    if not game_ids:
        return {}
    params: list = [sport, market, game_ids]
    extra = ""
    if as_of is not None:
        extra = " AND o.snapshot_at::timestamptz <= %s::timestamptz"
        params.append(str(as_of))
    rows = conn.execute(f"""
        SELECT DISTINCT ON (o.game_id, o.bookmaker)
               o.game_id, o.bookmaker, o.home_price, o.away_price,
               o.spread_home, o.total_line, o.over_price, o.under_price,
               o.snapshot_at, o.home_link, o.away_link, o.over_link, o.under_link
        FROM odds o
        JOIN games g ON g.game_id = o.game_id
        WHERE o.sport = %s AND o.market = %s
          AND o.game_id = ANY(%s)
          AND o.snapshot_type = 'open'
          AND o.snapshot_at::timestamptz <= g.commence_time::timestamptz
          {extra}
        ORDER BY o.game_id, o.bookmaker, o.snapshot_at DESC
    """, tuple(params)).fetchall()
    out = {}
    for r in rows:
        (gid, bk, hp, ap, sh, tl, op, up, snap,
         hl, al, ol, ul) = r
        out[(gid, bk)] = {
            "home_price": hp, "away_price": ap,
            "spread_home": sh, "total_line": tl,
            "over_price": op, "under_price": up,
            "snapshot_at": snap,
            "home_link": hl, "away_link": al,
            "over_link": ol, "under_link": ul,
            "book": bk, "game_id": gid,
        }
    return out


def find_spread_bets(quotes: dict, min_edge: float = MIN_EDGE_SPREADS,
                     soft_books: tuple[str, ...] | None = None,
                     max_gap_s: float = MAX_GAP_S,
                     runline_only: bool = True
                     ) -> tuple[list[GameMarketBet], dict]:
    """One spread bet per game: the largest Pinnacle-vs-soft disagreement.

    EQUAL LINES ONLY. A Pinnacle −1.5 against a soft −2.5 is a different
    proposition. PRE-GAME / SIMULTANEOUS: the caller loads quotes; we still
    refuse a pair whose snapshots are more than `max_gap_s` apart.
    """
    soft = tuple(soft_books) if soft_books is not None else SOFT_BOOKS
    diag = defaultdict(int)
    by_game: dict[str, dict] = defaultdict(dict)
    for (gid, bk), q in quotes.items():
        by_game[gid][bk] = q

    bets: list[GameMarketBet] = []
    for gid, books in by_game.items():
        sharp = books.get(SHARP_BOOK)
        if not sharp:
            diag["no_sharp"] += 1
            continue
        sline = sharp.get("spread_home")
        sf, _ = devig(sharp.get("home_price"), sharp.get("away_price"))
        if sf is None or sline is None:
            diag["sharp_one_way"] += 1
            continue
        if runline_only and not _is_runline(sline):
            diag["not_runline"] += 1
            continue
        su = 1.0 - sf
        best: GameMarketBet | None = None
        for bk in soft:
            q = books.get(bk)
            if not q:
                continue
            bline = q.get("spread_home")
            if bline is None or float(bline) != float(sline):
                diag["line_mismatch"] += 1
                continue
            gap = _gap_seconds(sharp.get("snapshot_at"), q.get("snapshot_at"))
            if gap is None or gap > max_gap_s:
                diag["not_simultaneous"] += 1
                continue
            fa, fb = devig(q.get("home_price"), q.get("away_price"))
            if fa is None:
                diag["soft_one_way"] += 1
                continue
            diag["compared"] += 1
            for side, fair, book_p, price, sharp_p in (
                ("home", sf, fa, q.get("home_price"), sharp.get("home_price")),
                ("away", su, fb, q.get("away_price"), sharp.get("away_price")),
            ):
                if price is None or implied(price) is None:
                    continue
                edge = fair - book_p
                if edge < min_edge:
                    continue
                cand = GameMarketBet(
                    game_id=gid, market="spreads", side=side, book=bk,
                    line=float(sline), price=float(price), fair=float(fair),
                    edge=float(edge), sharp_price=float(sharp_p)
                    if sharp_p is not None else float(price),
                    snap=q.get("snapshot_at"),
                )
                if best is None or cand.edge > best.edge:
                    best = cand
        if best is not None:
            bets.append(best)
            diag["bets"] += 1
    return bets, dict(diag)


def find_total_bets(quotes: dict, min_edge: float = MIN_EDGE_TOTALS,
                    soft_books: tuple[str, ...] | None = None,
                    max_gap_s: float = MAX_GAP_S,
                    vs: str = "implied",
                    pin_lean: bool = True,
                    ) -> tuple[list[GameMarketBet], dict]:
    """Totals: Pin no-vig lean vs DraftKings juiced implied, equal total.

    GROK_BOT 2026-09-15 measured Pin OPEN fair − DK OPEN implied ≥2pp,
    pin-lean, Apr–Jul ~+11% n≈103. The paper card fires that population
    (TOTALS_SOFT_BOOKS = draftkings). Default min_edge is a wall so an
    accidental caller cannot fire; the paper card passes 0.02.

    vs='implied' is the measured construction. vs='devig' is the May–Jun
    loser (−11.13% / 79 at 2pp) and is kept only so a sweep can name it.
    pin_lean=True bets only the side Pinnacle's no-vig prefers.
    Passing other soft_books is for sweeps, not for INSERT.
    """
    if vs not in ("implied", "devig"):
        raise ValueError(f"vs must be implied|devig, got {vs!r}")
    soft = tuple(soft_books) if soft_books is not None else TOTALS_SOFT_BOOKS
    diag = defaultdict(int)
    by_game: dict[str, dict] = defaultdict(dict)
    for (gid, bk), q in quotes.items():
        by_game[gid][bk] = q

    bets: list[GameMarketBet] = []
    for gid, books in by_game.items():
        sharp = books.get(SHARP_BOOK)
        if not sharp:
            diag["no_sharp"] += 1
            continue
        sline = sharp.get("total_line")
        sf, _ = devig(sharp.get("over_price"), sharp.get("under_price"))
        if sf is None or sline is None:
            diag["sharp_one_way"] += 1
            continue
        su = 1.0 - sf
        sides = (("over", sf, "over_price"), ("under", su, "under_price"))
        if pin_lean:
            sides = (max(sides, key=lambda s: s[1]),)
        best: GameMarketBet | None = None
        for bk in soft:
            q = books.get(bk)
            if not q:
                continue
            bline = q.get("total_line")
            if bline is None or float(bline) != float(sline):
                diag["line_mismatch"] += 1
                continue
            gap = _gap_seconds(sharp.get("snapshot_at"), q.get("snapshot_at"))
            if gap is None or gap > max_gap_s:
                diag["not_simultaneous"] += 1
                continue
            fa, fb = devig(q.get("over_price"), q.get("under_price"))
            if vs == "devig" and fa is None:
                diag["soft_one_way"] += 1
                continue
            diag["compared"] += 1
            for side, fair, price_key in sides:
                price = q.get(price_key)
                sharp_p = sharp.get(price_key)
                if price is None or implied(price) is None:
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
                cand = GameMarketBet(
                    game_id=gid, market="totals", side=side, book=bk,
                    line=float(sline), price=float(price), fair=float(fair),
                    edge=float(edge), sharp_price=float(sharp_p)
                    if sharp_p is not None else float(price),
                    snap=q.get("snapshot_at"),
                )
                if best is None or cand.edge > best.edge:
                    best = cand
        if best is not None:
            bets.append(best)
            diag["bets"] += 1
    return bets, dict(diag)
