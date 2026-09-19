"""
Paper MLB totals: fade a public OVER pile, bet UNDER.

WHY THIS EXISTS
---------------
`mlb_over_under` stays paused. `mlb_total_market` is a different paper lane
(Pin fair − soft implied). This file is the public-ticket fade that cleared a
small 2026 window: when Action Network consensus OVER tickets are heavy,
take the under at a bettable soft open.

THE CONSTRUCTION
----------------
Source: `public_betting` consensus totals, last snapshot with
`snapshot_at < commence_time` (offset-aware; text compare on mixed
`-04:00` / `+00:00` clocks is a leak). Trigger: over tickets ≥ the
configured cut (70 default; 80 is a supported env). Price: best open
under among DK/FD/MGM/WH at DK's open total (fallback DK), main total
5.5–14.5, under American in [-200, 200]. Always UNDER. One bet per game.

INSERT is gated by `MLB_TOTAL_PUBLIC_FADE_PUBLISH` (default 0). This is
not an unpause of `mlb_over_under` and not `mlb_total_market`. The card
never floods a slate: `MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE` is clamped
to 1 or 2 (default 2), ranked by over-ticket % before the slate guard.
A slate where one side is ≥70% of BETs and n_bet ≥ 4 is then
suppressed in full (`models.slate_concentration`, policy=suppress_all)
— with the cap that backstop does not fire on a normal day.

CAVEAT. `public_betting` is 2026-05-31→present only, UNIQUE last-upsert.
Honest pre-commence totals-over coverage measured 2026-09-16: 99 games.
Hourly refresh historically overwrote the pre-game split; those games
cannot be recovered. Backtest n is the intersection, not a season.

Docs: docs/mlb_total_public_fade.md.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import config
from features.feature_engine import _parse_iso_ts, numeric_feature_value
from models.market_relative import implied
from models.slate_concentration import (
    POLICY_SUPPRESS_ALL,
    SlateConcentration,
    apply_slate_concentration_guard,
)

MODEL_ID = "mlb_total_public_fade"
SPORT = "MLB"
MARKET = "totals"
SIDE = "under"
FALLBACK_BOOK = "draftkings"
# The four books the card was measured on. Not BEST_LINE (that includes
# more retail). A book named here must be fetched — pinned in
# tests/test_every_named_book_is_fetched.py.
SOFT_BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us")
LINE_MIN = 5.5
LINE_MAX = 14.5
PRICE_MIN = -200.0
PRICE_MAX = 200.0
DEFAULT_OVER_TICKETS = 70.0
# Hard cap. The card must never write a whole-slate UNDER pile
# (2026-09-19 was 12/12). 0 in the env is not all-pass.
SLATE_CAP_MIN = 1
SLATE_CAP_MAX = 2
DEFAULT_MAX_PER_SLATE = 2

# Ranking kinds the top-K selector understands. `ev` needs a bucket
# under-win-rate lookup (month-holdout or a frozen table). The others
# are slate-local: ticket pile, ticket−money gap, under juice, or a
# juice-adjusted composite. The 2026-09-19 holdout winner was `ticket`
# (see docs/mlb_total_public_fade.md).
RANK_TICKET = "ticket"
RANK_GAP = "gap"
RANK_JUICE = "juice"
RANK_COMPOSITE = "composite"
RANK_EV = "ev"
RANK_KINDS = (RANK_TICKET, RANK_GAP, RANK_JUICE, RANK_COMPOSITE, RANK_EV)

# Ticket buckets for holdout EV. Edges are [lo, hi). 100 sits in the last.
EV_TICKET_BUCKETS: tuple[tuple[float, float], ...] = (
    (65.0, 75.0),
    (75.0, 85.0),
    (85.0, 95.0),
    (95.0, 101.0),
)


@dataclass(frozen=True)
class PublicFadeBet:
    game_id: str
    book: str
    line: float
    price: float
    over_ticket_pct: float
    quote_snap: str | None = None
    public_snap: str | None = None
    over_money_pct: float | None = None


def ticket_threshold() -> float:
    """Over-ticket cut. Env MLB_TOTAL_PUBLIC_FADE_TICKET_PCT, default 70."""
    return float(config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT)


def publish_enabled() -> bool:
    """INSERT gate. Default off: the card logs, it does not write picks."""
    return bool(config.MLB_TOTAL_PUBLIC_FADE_PUBLISH)


def max_per_slate() -> int:
    """Bets per slate. Always 1 or 2. Env MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE.

    0 / negative / >2 clamp to 2. The sweep may still pass 0 into
    `select_top_k` for an all-pass cell; the card never does.
    """
    raw = int(config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE)
    if raw < SLATE_CAP_MIN or raw > SLATE_CAP_MAX:
        return DEFAULT_MAX_PER_SLATE
    return raw


def rank_kind() -> str:
    """Ranking formula. Env MLB_TOTAL_PUBLIC_FADE_RANK, default ticket."""
    raw = str(config.MLB_TOTAL_PUBLIC_FADE_RANK).strip().lower()
    return raw if raw in RANK_KINDS else RANK_TICKET


def edge_floor() -> float:
    """Minimum estimated edge after juice. 0 = no floor. Env MLB_TOTAL_PUBLIC_FADE_EDGE_FLOOR."""
    return float(config.MLB_TOTAL_PUBLIC_FADE_EDGE_FLOOR)


def is_pre_commence(snapshot_at, commence_time) -> bool:
    """True iff snapshot_at is strictly before commence_time.

    Offset-aware. Missing or unparseable clocks fail CLOSED — a fade with
    no as-of is not a fade. `<=` is not this bound; a snapshot stamped at
    first pitch is in-play.
    """
    snap = _parse_iso_ts(snapshot_at)
    start = _parse_iso_ts(commence_time)
    if snap is None or start is None:
        return False
    return snap < start


def select_latest_pre_commence_over(rows: list[dict]) -> dict[str, dict]:
    """Last consensus OVER split per game with snapshot_at < commence_time.

    `rows` items need: game_id, snapshot_at, commence_time, ticket /
    public_bet_pct. Side/market/book filters are the caller's.
    """
    surviving: dict[str, dict] = {}
    for raw in rows or []:
        gid = raw.get("game_id")
        if not gid:
            continue
        if not is_pre_commence(raw.get("snapshot_at"), raw.get("commence_time")):
            continue
        ticket = numeric_feature_value(
            raw.get("ticket", raw.get("public_bet_pct")))
        if ticket is None:
            continue
        prev = surviving.get(gid)
        if prev is None:
            surviving[gid] = raw
            continue
        new_ts = _parse_iso_ts(raw.get("snapshot_at"))
        old_ts = _parse_iso_ts(prev.get("snapshot_at"))
        if new_ts is not None and (old_ts is None or new_ts >= old_ts):
            surviving[gid] = raw
    return surviving


def _price_in_window(price) -> bool:
    p = numeric_feature_value(price)
    if p is None:
        return False
    return PRICE_MIN <= p <= PRICE_MAX


def _line_in_window(line) -> bool:
    x = numeric_feature_value(line)
    if x is None:
        return False
    return LINE_MIN <= x <= LINE_MAX


def _better_under(candidate: float, incumbent: float | None) -> bool:
    """True when `candidate` is a better take for the bettor than incumbent.

    Lower juiced implied = better American. Missing incumbent always loses.
    """
    ic = implied(candidate)
    if ic is None:
        return False
    if incumbent is None:
        return True
    ii = implied(incumbent)
    if ii is None:
        return True
    return ic < ii


def shop_under(books: dict, *, line: float,
               soft_books: tuple[str, ...] = SOFT_BOOKS
               ) -> tuple[str, float, str | None] | None:
    """Best same-line open under among `soft_books`. None if nothing qualifies."""
    best_book = None
    best_price = None
    best_snap = None
    for bk in soft_books:
        q = books.get(bk)
        if not q:
            continue
        bline = numeric_feature_value(q.get("total_line"))
        if bline is None or float(bline) != float(line):
            continue
        price = numeric_feature_value(q.get("under_price"))
        if price is None or not _price_in_window(price):
            continue
        if _better_under(price, best_price):
            best_book = bk
            best_price = price
            best_snap = q.get("snapshot_at")
    if best_book is None or best_price is None:
        return None
    return best_book, float(best_price), best_snap


def ticket_money_gap(bet: PublicFadeBet) -> float:
    """over tickets − over money. Positive = ticket-heavy public pile."""
    money = numeric_feature_value(bet.over_money_pct)
    if money is None:
        return 0.0
    return float(bet.over_ticket_pct) - float(money)


def ticket_bucket(over_ticket_pct: float) -> tuple[float, float] | None:
    """Which EV_TICKET_BUCKETS cell `over_ticket_pct` falls in."""
    x = float(over_ticket_pct)
    for lo, hi in EV_TICKET_BUCKETS:
        if lo <= x < hi:
            return (lo, hi)
    return None


def composite_score(bet: PublicFadeBet) -> float:
    """ticket + gap − 100×implied. Higher = heavier fade at a better take.

    Juice is subtracted so a 96% pile at −130 does not outrank a 90% pile
    at +100. Missing implied is unrankable (sent to the bottom).
    """
    imp = implied(bet.price)
    if imp is None:
        return float("-inf")
    return float(bet.over_ticket_pct) + ticket_money_gap(bet) - (100.0 * imp)


def rank_score(bet: PublicFadeBet, kind: str,
               ev_of=None) -> float:
    """Higher is a stronger fade. Empty kind is composite; unknown is ticket.

    RANK=ev without `ev_of` is ticket — the card does not load a bucket
    table, so ev/edge_floor are sweep-only until one is passed in.
    """
    k = (kind or RANK_COMPOSITE).strip().lower()
    if k == RANK_TICKET:
        return float(bet.over_ticket_pct)
    if k == RANK_GAP:
        return ticket_money_gap(bet)
    if k == RANK_JUICE:
        imp = implied(bet.price)
        return float("-inf") if imp is None else -imp
    if k == RANK_COMPOSITE:
        return composite_score(bet)
    if k == RANK_EV:
        if ev_of is None:
            return float(bet.over_ticket_pct)
        val = ev_of(bet)
        try:
            return float(val)
        except (TypeError, ValueError):
            return float("-inf")
    return float(bet.over_ticket_pct)


def estimated_edge(bet: PublicFadeBet,
                   bucket_win_rate: dict[tuple[float, float], float],
                   ) -> float | None:
    """Holdout bucket under-win-rate minus juiced implied. None if unpriced."""
    imp = implied(bet.price)
    if imp is None:
        return None
    key = ticket_bucket(bet.over_ticket_pct)
    wr = bucket_win_rate.get(key) if key is not None else None
    if wr is None:
        wr = bucket_win_rate.get(("all", "all"))
    if wr is None:
        return None
    return float(wr) - float(imp)


def select_top_k(
    bets: list[PublicFadeBet],
    *,
    max_per_slate: int,
    slate_of,
    kind: str = RANK_COMPOSITE,
    ev_of=None,
    min_edge: float = 0.0,
    bucket_win_rate: dict | None = None,
) -> list[PublicFadeBet]:
    """Keep the top `max_per_slate` bets per slate, optionally behind an edge floor.

    `max_per_slate <= 0` is all-pass (the current card). `min_edge` drops
    a bet whose estimated_edge is below the floor when `bucket_win_rate`
    is provided; without rates the floor is ignored (nothing to measure).
    Ties break on game_id so a re-run is deterministic.
    """
    incoming = list(bets or [])
    if min_edge > 0 and bucket_win_rate:
        kept = []
        for b in incoming:
            edge = estimated_edge(b, bucket_win_rate)
            if edge is None or edge < min_edge:
                continue
            kept.append(b)
        incoming = kept
    if max_per_slate <= 0:
        return incoming

    def _key(b: PublicFadeBet) -> tuple[float, str]:
        return (rank_score(b, kind, ev_of=ev_of), b.game_id)

    by_slate: dict = defaultdict(list)
    for b in incoming:
        by_slate[slate_of(b)].append(b)
    out: list[PublicFadeBet] = []
    k = max(0, int(max_per_slate))
    for group in by_slate.values():
        ranked = sorted(group, key=_key, reverse=True)
        out.extend(ranked[:k])
    return out


def find_fade_bets(splits: dict[str, dict], quotes: dict,
                   min_over_tickets: float | None = None,
                   soft_books: tuple[str, ...] | None = None,
                   fallback_book: str = FALLBACK_BOOK,
                   ) -> tuple[list[PublicFadeBet], dict]:
    """One UNDER per game when pre-commence over tickets clear the cut.

    `splits` is {game_id: raw over-split row} from
    `select_latest_pre_commence_over`. `quotes` is {(game_id, book): row}
    from `models.mlb_game_market.load_latest_quotes` (OPEN, leak-bounded).
    DK open is required (the measured universe is public ∩ DK open). Other
    books may improve the under price at the same total.
    """
    cut = (DEFAULT_OVER_TICKETS if min_over_tickets is None
           else float(min_over_tickets))
    books_order = tuple(soft_books) if soft_books is not None else SOFT_BOOKS
    diag: dict[str, int] = defaultdict(int)
    by_game: dict[str, dict] = defaultdict(dict)
    for (gid, bk), q in quotes.items():
        by_game[gid][bk] = q

    bets: list[PublicFadeBet] = []
    for gid, raw in splits.items():
        ticket = numeric_feature_value(
            raw.get("ticket", raw.get("public_bet_pct")))
        if ticket is None:
            diag["no_ticket"] += 1
            continue
        if ticket < cut:
            diag["below_cut"] += 1
            continue
        books = by_game.get(gid) or {}
        dk = books.get(fallback_book)
        if not dk:
            diag["no_dk"] += 1
            continue
        line = numeric_feature_value(dk.get("total_line"))
        if line is None or not _line_in_window(line):
            diag["line_out"] += 1
            continue
        shopped = shop_under(books, line=float(line), soft_books=books_order)
        if shopped is None:
            diag["no_price"] += 1
            continue
        book, price, snap = shopped
        money = numeric_feature_value(
            raw.get("public_money_pct", raw.get("over_money_pct")))
        diag["bets"] += 1
        bets.append(PublicFadeBet(
            game_id=gid, book=book, line=float(line), price=float(price),
            over_ticket_pct=float(ticket),
            quote_snap=snap, public_snap=raw.get("snapshot_at"),
            over_money_pct=None if money is None else float(money),
        ))
    return bets, dict(diag)


def apply_slate_guard(
    candidates,
    *,
    model_id: str = MODEL_ID,
    log: bool = True,
) -> tuple[list, SlateConcentration]:
    """Suppress an all-under (or otherwise concentrated) fade slate.

    Always `suppress_all`. This card only produces UNDER, so any slate of
    4+ flags is 100% one side and is dropped in full. Mixed-side callers
    (other game-market cards) should call
    `apply_slate_concentration_guard` directly.
    """
    return apply_slate_concentration_guard(
        candidates,
        policy=POLICY_SUPPRESS_ALL,
        side_of=lambda b: getattr(b, "side", None)
        or (b.get("pick_side") if isinstance(b, dict) else None)
        or SIDE,
        edge_of=lambda b: (
            b.get("edge") if isinstance(b, dict)
            else (b.over_ticket_pct - 50.0) / 100.0
        ),
        model_id=model_id,
        log=log,
    )


def load_public_over_splits(conn, game_ids: list[str]) -> dict[str, dict]:
    """Consensus totals OVER rows for `game_ids`, as-of filtered in Python."""
    if not game_ids:
        return {}
    rows = conn.execute("""
        SELECT pb.game_id, pb.public_bet_pct, pb.public_money_pct,
               pb.snapshot_at, g.commence_time
        FROM public_betting pb
        JOIN games g ON g.game_id = pb.game_id
        WHERE pb.game_id = ANY(%s)
          AND pb.market = 'totals'
          AND pb.side = 'over'
          AND pb.book = 'consensus'
    """, (game_ids,)).fetchall()
    parsed = []
    for r in rows:
        parsed.append({
            "game_id": r[0],
            "public_bet_pct": r[1],
            "public_money_pct": r[2],
            "snapshot_at": r[3],
            "commence_time": r[4],
            "ticket": r[1],
        })
    return select_latest_pre_commence_over(parsed)
