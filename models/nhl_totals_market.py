"""
NHL full-game total goals: Pinnacle's no-vig price, bet a bettable book that lags it.

This is `nhl_over_under`. It is a frozen rule with no trained artifact (mike,
2026-10-08: live, not paper). The card that writes its picks is
scripts/nhl_totals_card.py.

THE RULE, per unstarted game, on every refresh pass:
  1. Take the newest stored fetch that holds Pinnacle's two-way total
     (snapshot_type 'open', both timestamps at or before the game's start).
     Skip the game this pass if a newer fetch exists without Pinnacle in it
     ("pinnacle_withdrawn"): Pinnacle took its number down, so the soft prices
     in the older fetch are stale too.
  2. De-vig Pinnacle proportionally. Its overround must be strictly between
     1.0 and 1.15.
  3. Price every bettable book IN THAT SAME FETCH that hangs the same number:
     EV = p x decimal - 1, over and under, at -200 or better.
  4. Bet the best EV if it is at least the model's own floor (0.01,
     config.MODEL_OWN_EV_FLOOR). One bet a game. A tie goes to the earlier
     book in SOFT_BOOKS (DraftKings first), then over before under.

ONE FETCH, NOT ONE MINUTE. Every book written by one refresh-pass fetch shares
`odds.created_at` (the transaction's now()); `snapshot_at` is each book's own
last update. The evidence below paired quotes on created_at, and comparing
prices from two different fetches is what manufactured the NHL moneyline
"edge" of 2026-10-01 (scripts/nhl_totals_lab.py header). So the soft quotes are
the rows whose created_at text equals Pinnacle's. There is no snapshot_at gap
limit, because the evidence had none: the first hits' Pinnacle-to-soft gap was
p90 153 s, at most 784 s.

THE EVIDENCE (six seasons, 2020-21 to 2025-26, odds_api_historical; the
SHARP-VS-SOFT section of scripts/nhl_totals_lab.py re-graded on the bettable
books, i.e. its SOFT list without Bovada; graded by the 2026-10-08 design
session's own queries, not re-run in this change). The first fetch in which a
game qualifies, one bet a game, flat units at the price taken:

    EV floor   bets    units    return   EV at Pinnacle's close
    0.000      2,768   +35.7    +1.29%   +0.35%
    0.005      1,859   +41.2    +2.22%   +0.82%
    0.010      1,276   +60.2    +4.72%   +1.32%   <- live
    0.015        819   +58.9    +7.19%   +1.80%
    0.020        548    +0.7    +0.14%   +2.36%

0.010 sits on a units plateau with 0.015. The return is not established
(normal-approximation interval -0.6% to +10.1%; 2023-24 lost 6.94%); the case
for going live is closing-line value, which is positive at every cut and rises
with it. The cut was chosen on the same seasons it is graded on.

THE TABLE IS THE LAB'S SELECTION, NOT EXACTLY THIS RULE'S. The lab takes the
first soft quote by its own snapshot time; this rule takes the best EV across
the books in the first qualifying fetch. The 2026-10-08 review replicated both
read-only on two seasons. 2025-26: 197 of 210 games the same bet, 13 the same
fetch at another book or side, 0 from another fetch, +3.89u lab vs +3.95u
rule. 2024-25: 161 of 176, 15, 0, +12.18u vs +12.22u.

THE WINDOW is every pre-game Pinnacle quote, not game day only. The first
qualifying fetch by hours before puck drop, at 0.01:

    0-3 h      501 bets   -9.41u
    3-6 h       98 bets   +4.08u
    6-12 h     340 bets  +21.06u
    12-20 h     28 bets   +2.60u
    20-32 h    294 bets  +34.86u
    over 32 h   15 bets   +7.03u

The prior-day bucket carries +34.86u of the +60.22u, so a game-day-only card
would throw most of it away. The negative 0-3 h bucket is an in-sample split,
reported here, not a cut (mike, 2026-10-08: no change).

WHOLE NUMBERS. The de-vigged two-way at 6.0 ignores the push, so the stated
EV is too high by the push share: true EV = (1 - p_push) x stated EV, same
sign. The lab used the same arithmetic.

SETTLEMENT is totals against the stored final, which includes the shootout
goal (tracking/paper_tracker._RULE_MODEL_MARKETS). The model decides on its
own probability (config.MODELS_ON_OWN_PROBABILITY): the promoted pooled map
turns every Pinnacle price between about 0.435 and 0.565 into 0.500.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

import config
from models.market_relative import devig, implied

MODEL_ID = "nhl_over_under"
SHARP_BOOK = "pinnacle"
# The book whose own price fills the dk_* columns (the scorer's convention).
REFERENCE_BOOK = "draftkings"
# The books a member can bet. Pinnacle is the reference; Bovada and espnbet
# are fetched and are not bettable (config.BEST_LINE_BOOKMAKERS).
SOFT_BOOKS = tuple(b for b in config.BEST_LINE_BOOKMAKERS if b != SHARP_BOOK)
# Implied over + implied under must sit strictly inside this range for a quote
# to be read as a price (nhl_totals_lab.py:123).
COHERENT = (1.0, 1.15)

DIAG_KEYS = ("games", "no_sharp", "pinnacle_withdrawn", "stale_fetch",
             "sharp_incoherent",
             "no_pair", "soft_incoherent", "line_mismatch", "below_price_floor",
             "below_ev_floor", "compared", "bets")


@dataclass(frozen=True)
class NhlTotalBet:
    game_id: str
    side: str                       # "over" | "under"
    book: str                       # the book the bet is taken at
    line: float                     # the total
    price: float                    # that book's American price on `side`
    fair: float                     # Pinnacle's no-vig probability of `side`
    ev: float                       # fair x decimal(price) - 1
    sharp_over: float               # Pinnacle's two prices in the same fetch
    sharp_under: float
    created_at: str                 # the fetch (odds.created_at text)
    soft_snapshot_at: str | None
    sharp_snapshot_at: str | None
    link: str | None                # the taken book's betslip link
    dk_price: float | None          # DraftKings' price on `side` at this number
    dk_link: str | None             # in this fetch, or None


def _ts(row: dict, key: str):
    from features.feature_engine import _parse_iso_ts
    return _parse_iso_ts(row.get(key))


def _fetch_ts(row: dict):
    """The fetch time: the SQL's timestamptz when present, else the text."""
    from features.feature_engine import _parse_iso_ts
    return _parse_iso_ts(row.get("created_ts") or row.get("created_at"))


def _two_way(row: dict) -> bool:
    return (row.get("total_line") is not None
            and implied(row.get("over_price")) is not None
            and implied(row.get("under_price")) is not None)


def _coherent(row: dict) -> bool:
    s = implied(row["over_price"]) + implied(row["under_price"])
    return COHERENT[0] < s < COHERENT[1]


def load_fetch_quotes(conn, games) -> list[dict]:
    """The rows find_bets needs for each slate game, in ONE statement.

    Per game: Pinnacle's newest complete pre-game totals row (P); the newest
    pre-game row from any book other than DraftKings, so find_bets can see a
    later fetch that lacks Pinnacle; and every bettable book's newest row in
    P's own fetch (created_at text equal to P's). Every read is bounded on
    games.commence_time, by snapshot_at AND by created_at: in-play NHL totals
    are stored as 'open' too.
    """
    game_ids = list(games)
    if not game_ids:
        return []
    books = list(SOFT_BOOKS)
    if REFERENCE_BOOK not in books:
        books.append(REFERENCE_BOOK)
    rows = conn.execute("""
        WITH g AS (
            SELECT game_id, commence_time::timestamptz AS ct
            FROM games
            WHERE game_id = ANY(%s) AND commence_time IS NOT NULL
        ),
        p AS (
            SELECT DISTINCT ON (o.game_id)
                   o.game_id, o.bookmaker, o.created_at,
                   o.created_at::timestamptz AS created_ts, o.snapshot_at,
                   o.total_line, o.over_price, o.under_price,
                   o.over_link, o.under_link
            FROM odds o
            JOIN g ON g.game_id = o.game_id
            WHERE o.market = 'totals' AND o.bookmaker = %s
              AND o.snapshot_type = 'open'
              AND o.snapshot_at::timestamptz <= g.ct
              AND o.created_at::timestamptz <= g.ct
              AND o.total_line IS NOT NULL
              AND o.over_price IS NOT NULL AND o.under_price IS NOT NULL
            ORDER BY o.game_id, o.created_at::timestamptz DESC,
                     o.snapshot_at::timestamptz DESC
        ),
        newest AS (
            SELECT DISTINCT ON (o.game_id)
                   o.game_id, o.bookmaker, o.created_at,
                   o.created_at::timestamptz AS created_ts, o.snapshot_at,
                   o.total_line, o.over_price, o.under_price,
                   o.over_link, o.under_link
            FROM odds o
            JOIN g ON g.game_id = o.game_id
            WHERE o.market = 'totals' AND o.bookmaker <> 'draftkings'
              AND o.snapshot_type = 'open'
              AND o.snapshot_at::timestamptz <= g.ct
              AND o.created_at::timestamptz <= g.ct
            ORDER BY o.game_id, o.created_at::timestamptz DESC
        ),
        soft AS (
            SELECT DISTINCT ON (o.game_id, o.bookmaker)
                   o.game_id, o.bookmaker, o.created_at,
                   o.created_at::timestamptz AS created_ts, o.snapshot_at,
                   o.total_line, o.over_price, o.under_price,
                   o.over_link, o.under_link
            FROM odds o
            JOIN p ON p.game_id = o.game_id AND o.created_at = p.created_at
            JOIN g ON g.game_id = o.game_id
            WHERE o.market = 'totals' AND o.bookmaker = ANY(%s)
              AND o.snapshot_type = 'open'
              AND o.snapshot_at::timestamptz <= g.ct
            ORDER BY o.game_id, o.bookmaker, o.snapshot_at::timestamptz DESC
        )
        SELECT * FROM p
        UNION ALL SELECT * FROM newest
        UNION ALL SELECT * FROM soft
    """, (game_ids, SHARP_BOOK, books)).fetchall()
    cols = ("game_id", "book", "created_at", "created_ts", "snapshot_at",
            "total_line", "over_price", "under_price", "over_link", "under_link")
    out = []
    for r in rows:
        q = dict(zip(cols, r))
        # NUMERIC arrives as Decimal: cast once, before any comparison.
        for k in ("total_line", "over_price", "under_price"):
            if q[k] is not None:
                q[k] = float(q[k])
        out.append(q)
    return out


def find_bets(quotes, soft_books: tuple[str, ...] | None = None,
              min_ev: float | None = None, min_odds: float | None = None,
              now=None) -> tuple[list[NhlTotalBet], dict]:
    """At most one bet a game from `quotes` (rows shaped as load_fetch_quotes
    returns them; any superset of those rows gives the same answer, because the
    fetch selection is re-applied here).

    The diagnostic is logged on every pass, so an empty card can be told apart
    from a broken one: `no_sharp` counts games with no Pinnacle quote, and if
    that is every game, Pinnacle has left the fetched books.

    `now` (the card passes its clock) refuses a game whose newest Pinnacle
    fetch is older than config.PREGAME_PRICE_MAX_AGE_MIN: `stale_fetch`.
    "pinnacle_withdrawn" only catches a NEWER fetch without Pinnacle; when the
    odds step stops altogether (it failed on every pass 2026-09-27 to 10-01)
    there is no newer fetch, and the card would bet hours- or days-old prices.
    The fetch time is odds.created_at, the clock this rule already pairs on.
    None (the replay and unit-test callers) applies no age check.
    """
    soft = tuple(soft_books) if soft_books is not None else SOFT_BOOKS
    floor_ev = config.min_ev_for(MODEL_ID) if min_ev is None else float(min_ev)
    floor_odds = config.min_odds_for(MODEL_ID) if min_odds is None else min_odds
    oldest_fetch = (None if now is None else
                    now - timedelta(minutes=config.PREGAME_PRICE_MAX_AGE_MIN))
    diag = dict.fromkeys(DIAG_KEYS, 0)

    by_game: dict[str, list[dict]] = defaultdict(list)
    for q in quotes:
        by_game[q["game_id"]].append(q)

    bets: list[NhlTotalBet] = []
    for gid in sorted(by_game):
        rows = by_game[gid]
        diag["games"] += 1
        pins = [r for r in rows if r["book"] == SHARP_BOOK and _two_way(r)
                and _fetch_ts(r) is not None]
        if not pins:
            diag["no_sharp"] += 1
            continue
        sharp = max(pins, key=lambda r: (_fetch_ts(r), _ts(r, "snapshot_at")
                                         or _fetch_ts(r)))
        fetched = _fetch_ts(sharp)
        newest = max((_fetch_ts(r) for r in rows
                      if r["book"] != REFERENCE_BOOK and _fetch_ts(r) is not None),
                     default=fetched)
        if newest > fetched:
            diag["pinnacle_withdrawn"] += 1
            continue
        if oldest_fetch is not None and fetched < oldest_fetch:
            diag["stale_fetch"] += 1
            continue
        if not _coherent(sharp):
            diag["sharp_incoherent"] += 1
            continue
        p_over, p_under = devig(sharp["over_price"], sharp["under_price"])
        line = float(sharp["total_line"])

        # The rest of Pinnacle's fetch: the newest row per book in it.
        same: dict[str, dict] = {}
        for r in rows:
            if (r["book"] == SHARP_BOOK or r["created_at"] != sharp["created_at"]
                    or not _two_way(r)):
                continue
            prev = same.get(r["book"])
            if prev is None or ((_ts(r, "snapshot_at") or fetched)
                                > (_ts(prev, "snapshot_at") or fetched)):
                same[r["book"]] = r
        if not any(b in same for b in soft):
            diag["no_pair"] += 1
            continue

        # DraftKings' own price fills the dk_* columns only when it is a price:
        # the same number AND a coherent two-way, the test every compared book
        # passes. A quote the rule refuses as a candidate must not become the
        # reference either, or Discord (which headlines dk_odds when it is no
        # worse than best_odds) would show a price the bet was not taken at.
        dk = same.get(REFERENCE_BOOK)
        if dk is not None and (float(dk["total_line"]) != line
                               or not _coherent(dk)):
            dk = None

        best: NhlTotalBet | None = None
        for bk in soft:
            q = same.get(bk)
            if q is None:
                continue
            if not _coherent(q):
                diag["soft_incoherent"] += 1
                continue
            if float(q["total_line"]) != line:
                diag["line_mismatch"] += 1
                continue
            diag["compared"] += 1
            for side, p in (("over", p_over), ("under", p_under)):
                price = float(q[f"{side}_price"])
                if floor_odds is not None and price < floor_odds:
                    diag["below_price_floor"] += 1
                    continue
                ev = config.expected_value(p, price)
                if ev is None or ev < floor_ev:
                    diag["below_ev_floor"] += 1
                    continue
                cand = NhlTotalBet(
                    game_id=gid, side=side, book=bk, line=line, price=price,
                    fair=float(p), ev=float(ev),
                    sharp_over=float(sharp["over_price"]),
                    sharp_under=float(sharp["under_price"]),
                    created_at=sharp["created_at"],
                    soft_snapshot_at=q.get("snapshot_at"),
                    sharp_snapshot_at=sharp.get("snapshot_at"),
                    link=q.get(f"{side}_link"),
                    dk_price=float(dk[f"{side}_price"]) if dk is not None else None,
                    dk_link=dk.get(f"{side}_link") if dk is not None else None,
                )
                # Strictly greater: on a tie the earlier book, then over, wins.
                if best is None or cand.ev > best.ev:
                    best = cand
        if best is not None:
            bets.append(best)
            diag["bets"] += 1
    return bets, diag
