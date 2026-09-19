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
`-04:00` / `+00:00` clocks is a leak). Default RULE=`steam`: over
tickets ≥ 75 AND over money ≥ over tickets (public steam on the over),
then UNDER, hard-capped at 2 per slate ranked by over_tix then juice.
`blunt` restores the old ticket-cut-only finder (70 default; 80 is a
supported env). A −115 juice floor is an opt-in env — it failed month
holdout on the 2026 public window. Price: best open under among
DK/FD/MGM/WH at DK's open total (fallback DK), main total 5.5–14.5,
under American in [-200, 200]. Always UNDER.

INSERT is gated by `MLB_TOTAL_PUBLIC_FADE_PUBLISH` (default 0). This is
not an unpause of `mlb_over_under` and not `mlb_total_market`. A slate
where one side is ≥70% of BETs and n_bet ≥ 4 is suppressed in full
(`models.slate_concentration`, policy=suppress_all) before INSERT/notify.

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
DEFAULT_STEAM_TICKETS = 75.0
DEFAULT_MAX_PER_SLATE = 2
RULE_BLUNT = "blunt"
RULE_STEAM = "steam"
_UNSET = object()


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
    game_date: str | None = None


def ticket_threshold() -> float:
    """Blunt over-ticket cut. Env MLB_TOTAL_PUBLIC_FADE_TICKET_PCT, default 70."""
    return float(config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT)


def fade_rule() -> str:
    """`steam` (default) or `blunt`. Unknown values coerce to steam."""
    raw = str(getattr(config, "MLB_TOTAL_PUBLIC_FADE_RULE", RULE_STEAM)).strip().lower()
    return raw if raw in (RULE_BLUNT, RULE_STEAM) else RULE_STEAM


def steam_ticket_threshold() -> float:
    """Steam over-ticket cut. Env MLB_TOTAL_PUBLIC_FADE_STEAM_TICKETS, default 75."""
    return float(getattr(config, "MLB_TOTAL_PUBLIC_FADE_STEAM_TICKETS",
                         DEFAULT_STEAM_TICKETS))


def require_money_steam() -> bool:
    """True when steam requires over_money ≥ over_tix. Default on."""
    return bool(getattr(config, "MLB_TOTAL_PUBLIC_FADE_REQUIRE_MONEY_STEAM", True))


def min_under_price_floor() -> float | None:
    """Optional American juice floor. Default None — −115 failed holdout."""
    return getattr(config, "MLB_TOTAL_PUBLIC_FADE_MIN_UNDER_PRICE", None)


def max_bets_per_slate() -> int | None:
    """Hard cap per slate on the steam path. 0/None = unlimited. Default 2."""
    n = int(getattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE",
                    DEFAULT_MAX_PER_SLATE))
    return None if n <= 0 else n


def publish_enabled() -> bool:
    """INSERT gate. Default off: the card logs, it does not write picks."""
    return bool(config.MLB_TOTAL_PUBLIC_FADE_PUBLISH)


def is_public_steam(ticket, money) -> bool:
    """True iff over money is present and ≥ over tickets.

    Missing money fails CLOSED — a steam fade with no money split is not
    a steam fade.
    """
    t = numeric_feature_value(ticket)
    m = numeric_feature_value(money)
    if t is None or m is None:
        return False
    return float(m) >= float(t)


def grade_under(total, line, price) -> tuple[str, float]:
    """Settle one UNDER at `line`. Returns (WIN|LOSS|PUSH, units).

    Units are flat per $100: win = american payout, loss = −1, push = 0.
    Same arithmetic as `tracking.paper_tracker._compute_target` for totals.
    """
    tot = numeric_feature_value(total)
    ln = numeric_feature_value(line)
    pr = numeric_feature_value(price)
    if tot is None or ln is None or pr is None:
        raise ValueError("grade_under needs total, line and price")
    if float(tot) == float(ln):
        return "PUSH", 0.0
    if float(tot) < float(ln):
        units = (pr / 100.0) if pr > 0 else (100.0 / abs(pr))
        return "WIN", float(units)
    return "LOSS", -1.0


def juice_ok(price, floor: float | None) -> bool:
    """True when `price` clears an American juice floor (price ≥ floor).

    None floor is no floor. Missing price fails closed.
    """
    if floor is None:
        return True
    p = numeric_feature_value(price)
    if p is None:
        return False
    return float(p) >= float(floor)


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
            raw.get("over_money_pct", raw.get("public_money_pct")))
        gdate = raw.get("game_date")
        diag["bets"] += 1
        bets.append(PublicFadeBet(
            game_id=gid, book=book, line=float(line), price=float(price),
            over_ticket_pct=float(ticket),
            quote_snap=snap, public_snap=raw.get("snapshot_at"),
            over_money_pct=None if money is None else float(money),
            game_date=None if gdate is None else str(gdate)[:10],
        ))
    return bets, dict(diag)


def rank_and_cap(bets: list[PublicFadeBet], max_n: int | None,
                 ) -> list[PublicFadeBet]:
    """Keep up to `max_n` bets per slate, ranked by over_tix then juice.

    Higher over tickets first; then better (lower implied) under price.
    Games without a date share one slate. `max_n` None/≤0 is a no-op.
    """
    if not max_n or int(max_n) <= 0:
        return list(bets)
    groups: dict[str | None, list[PublicFadeBet]] = defaultdict(list)
    for b in bets:
        groups[b.game_date].append(b)
    kept: list[PublicFadeBet] = []
    k = int(max_n)
    for rows in groups.values():
        ranked = sorted(
            rows,
            key=lambda b: (
                -float(b.over_ticket_pct),
                implied(b.price) if implied(b.price) is not None else 1.0,
            ),
        )
        kept.extend(ranked[:k])
    return kept


def select_fade_bets(splits: dict[str, dict], quotes: dict,
                     min_over_tickets: float | None = None,
                     soft_books: tuple[str, ...] | None = None,
                     fallback_book: str = FALLBACK_BOOK,
                     rule: str | None = None,
                     require_steam: object = _UNSET,
                     min_under_price: object = _UNSET,
                     max_per_slate: object = _UNSET,
                     ) -> tuple[list[PublicFadeBet], dict]:
    """Configured selective finder. Default RULE=steam.

    Steam: ticket cut 75, money ≥ tickets, optional juice floor (off),
    then hard-cap max 2 per slate ranked by over_tix then juice.
    Blunt: ticket cut only (70 default). Cap is steam-only so blunt
    still relies on the concentration suppress for all-under slates.
    """
    chosen = (rule or fade_rule()).strip().lower()
    if chosen not in (RULE_BLUNT, RULE_STEAM):
        chosen = RULE_STEAM
    if chosen == RULE_STEAM:
        cut = (steam_ticket_threshold() if min_over_tickets is None
               else float(min_over_tickets))
    else:
        cut = (ticket_threshold() if min_over_tickets is None
               else float(min_over_tickets))
    bets, diag = find_fade_bets(
        splits, quotes, min_over_tickets=cut,
        soft_books=soft_books, fallback_book=fallback_book)
    diag = dict(diag)
    diag["rule"] = chosen

    want_steam = (require_money_steam() if require_steam is _UNSET
                  else bool(require_steam))
    if chosen == RULE_STEAM and want_steam:
        kept = []
        dropped = 0
        for b in bets:
            if is_public_steam(b.over_ticket_pct, b.over_money_pct):
                kept.append(b)
            else:
                dropped += 1
        bets = kept
        diag["not_steam"] = dropped

    floor = (min_under_price_floor() if min_under_price is _UNSET
             else min_under_price)
    if floor is not None:
        kept = []
        dropped = 0
        for b in bets:
            if juice_ok(b.price, float(floor)):
                kept.append(b)
            else:
                dropped += 1
        bets = kept
        diag["juice_floor"] = dropped

    if max_per_slate is _UNSET:
        cap = max_bets_per_slate() if chosen == RULE_STEAM else None
    else:
        cap = max_per_slate
    if cap:
        before = len(bets)
        bets = rank_and_cap(bets, int(cap))
        diag["capped"] = before - len(bets)
    diag["bets"] = len(bets)
    return bets, diag


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
               pb.snapshot_at, g.commence_time, g.game_date
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
            "over_money_pct": r[2],
            "game_date": None if r[5] is None else str(r[5])[:10],
        })
    return select_latest_pre_commence_over(parsed)
