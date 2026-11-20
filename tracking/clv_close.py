"""The final close of a pre-game bet: one rule for every model (issue #1470).

mike, 2026-11-19: *"yes I want it to be accurate please correct"*, and in-play
bets stay unmeasured by design (*"don't need clv for in play bets"*).

THE CLOSE. The bet book's quote at the exact number we bet, in that book's last
poll before the start, fetched AFTER the bet:

  * the main market, when its number in that last poll is ours;
  * otherwise the book's alternate ladder, from its newest poll, when that poll
    is no more than ALT_WINDOW older than the last main poll;
  * otherwise there is no closing price for our bet. The main line's move is
    still recorded (line_clv_pts) when a post-bet poll exists.

"Fetched" is the row's `created_at`, the instant we pulled it, and it must be
after the pick's `created_at` and at or before the start. The book's own
`snapshot_at` (its last change) is not the fetch time: a row whose price last
changed before the bet but that was pulled after it is a valid close, and a
row pulled before the bet is not, whatever it says. That is the hole the two
earlier writers had (a bet placed after the book's last pull was compared with
a price from before the bet, stored as 0.00).

No other book, no quote from before the bet, no in-play quote, no made-up 0.00.

THE LISTED START AND THE FIRST PLAY (v2, 2026-11-19). The start is the listed
one. A bet placed in the last minutes before it can have no pull of its book
between the bet and that listed start, and an NHL puck drops 8 to 18 minutes
after the listed time (ESPN wall clocks, the 11 such bets measured that day).
For that bet only, the close is the book's last price before the game actually
began: the first play's wall clock (`game_first_play`) less FIRST_PLAY_MARGIN.
A bet placed at or after the first play is not a pre-game bet and has no close.
The worker's stage measures bets placed before the listed start and has no
first plays of its own; `scripts/clv_close_history.py first-play` and
`buy-late` store the first play and buy that last price for the rest.

WHERE THE QUOTES COME FROM. Our own stored rows (`odds`, `player_prop_odds`)
for games from STORED_FROM, when nothing was being deleted; for older games,
the quotes bought from the feed's history into `clv_close_quotes`
(scripts/clv_close_history.py), together with whatever stored rows survived.
Tennis is the exception: its prices are only in `tennis_odds_quotes`
(scripts/tennis_moneyline_card.py), stored change-only, so a pull is read
from the card's own poll ledger (tennis_quotes, below). Until 2026-11-20 this
module read none of them, and every tennis bet was stamped with no close.

HOW IT IS WRITTEN. The earlier writers (paper_tracker._capture_clv and the
recompute in clv_standard_v2_2026_10_14.sql) still stamp a bet first; this
stage runs after them in the same settle pass and is the last word: it writes
the bet's closing-line columns once, stamps them `standard_v2`, and records
what it found, and what the row held before, in `clv_close_measurements`.
Neither earlier writer revisits a row stamped `standard_v2`, so nothing
overwrites it. Pinnacle's market-edge columns are not touched.
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone

from loguru import logger

from tracking.clv_math import same_book_clv

RULE = "fetched_after_bet_v2"
# Games starting on or after this were stored in full: the odds prune stopped
# on 2026-11-14 (docs/data_archive.md), so every pull of them is still there.
STORED_FROM = "2026-11-15T00:00:00+00:00"
# Rows of one poll share a fetch instant; two minutes groups a poll.
POLL_TOLERANCE = timedelta(minutes=2)
# An alternate ladder older than the last main poll by more than this is not
# the close: the main line may have moved again since.
ALT_WINDOW = timedelta(minutes=15)
# A started game is measured this long after its start, so the last pre-start
# pull has landed.
SETTLE_AFTER = timedelta(minutes=10)
# A price this close to the first play may already be the book's in-play one.
FIRST_PLAY_MARGIN = timedelta(seconds=60)
BATCH = 400

_FULL_GAME_ALT = {"spreads": "alternate_spreads", "totals": "alternate_totals"}
_ROW_MARKET_MODELS = ("nfl_prop_market", "wnba_prop_market", "nba_prop_market", "nba_prop_projection")
_PLAYER_RE = re.compile(r"^(.+?)\s+(?:Over|Under)\s+")
_SIDE_COL = {"home": "home_price", "away": "away_price", "draw": "draw_price",
             "over": "over_price", "under": "under_price"}


def alternate_market(market: str | None) -> str | None:
    """The stored name of a market's alternate ladder, or None (moneylines
    and method markets have no ladder). Full-game spreads and totals are
    `alternate_spreads` / `alternate_totals`; every other market (first half,
    quarter, team totals, player props) files its ladder under
    `<market>_alternate` (data/ingestors/ncaab_first_half_odds.py,
    the prop ingestors)."""
    if not market or market.startswith("h2h") or market == "method":
        return None
    return _FULL_GAME_ALT.get(market, f"{market}_alternate")


def _utc(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        t = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00").replace(" ", "T", 1))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _f(v) -> float | None:
    return None if v is None else float(v)


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv"}


def player_key(name: str | None) -> str:
    """A player's name as the feeds can disagree on it: accents, case,
    punctuation and Jr./III dropped. The feed's history spells "Jose Soriano"
    and "Walbert Urena" where our labels, written from the live feed, carry
    "José Soriano" and "Walbert Ureña" (measured 2026-11-19)."""
    if not name:
        return ""
    plain = unicodedata.normalize("NFKD", name)
    plain = "".join(ch for ch in plain if not unicodedata.combining(ch))
    words = re.sub(r"[^a-z0-9 ]+", " ", plain.lower()).split()
    return " ".join(w for w in words if w not in _SUFFIXES)


@dataclass
class Bet:
    pick_id: int
    model_id: str
    game_id: str
    pick_side: str
    number: float | None          # scored_line: the HOME number for spreads
    kind: str                     # 'game' or 'prop'
    market: str | None
    player: str | None
    created_at: datetime
    bound: datetime | None        # the earliest known start
    bet_price: float | None
    bet_book: str | None
    prop_market: str | None
    before: dict = field(default_factory=dict)
    first_play: datetime | None = None   # the game's first play (game_first_play)

    @property
    def alt(self) -> str | None:
        return alternate_market(self.market)


@dataclass
class Quote:
    market: str
    fetched_at: datetime
    number: float | None
    prices: dict
    source: str


@dataclass
class Close:
    source: str                   # 'feed', 'history' or 'none'
    market: str | None = None
    fetched_at: datetime | None = None
    odds: float | None = None
    line: float | None = None
    line_pts: float | None = None
    last_poll: datetime | None = None
    note: str = ""


# ── reading the bet ──────────────────────────────────────────────────────────

_BET_SQL = """
    SELECT p.pick_id, p.model_id, p.game_id, p.pick_side, p.scored_line, p.pick_label,
           p.prop_market, p.dk_odds, p.decision_odds, p.decision_book, p.created_at,
           p.game_time, g.commence_time, g.game_date, g.home_team, g.away_team,
           public.clv_game_market(p.model_id) AS game_market,
           public.clv_prop_key(p.model_id) AS prop_key,
           CASE WHEN split_part(p.game_id, '_', 1) = 'NBA' THEN (
             SELECT min(ns.commence_time::timestamptz) FROM public.nba_schedule ns
              WHERE ns.game_id IN (p.game_id, 'NBA_' || g.game_date || '_' || g.home_team || '_' || g.away_team)
                AND ns.commence_time IS NOT NULL) END AS nba_tip,
           p.closing_dk_odds, p.closing_line, p.clv_pct, p.clv_pp, p.line_clv_pts,
           p.clv_beat_close, p.clv_captured_at, p.clv_method, p.clv_close_book, p.clv_bet_book,
           (SELECT fp.first_play_at FROM public.game_first_play fp WHERE fp.game_id = p.game_id) AS first_play
      FROM public.picks p
      JOIN public.games g ON g.game_id = p.game_id
"""
_BET_COLS = ("pick_id", "model_id", "game_id", "pick_side", "scored_line", "pick_label",
             "prop_market", "dk_odds", "decision_odds", "decision_book", "created_at",
             "game_time", "commence_time", "game_date", "home_team", "away_team",
             "game_market", "prop_key", "nba_tip",
             "closing_dk_odds", "closing_line", "clv_pct", "clv_pp", "line_clv_pts",
             "clv_beat_close", "clv_captured_at", "clv_method", "clv_close_book", "clv_bet_book",
             "first_play")
_BEFORE = ("closing_dk_odds", "closing_line", "clv_pct", "clv_pp", "line_clv_pts",
           "clv_beat_close", "clv_captured_at", "clv_method", "clv_close_book", "clv_bet_book")


def _jsonable(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    return str(v)


def bet_from_row(row: dict) -> Bet | None:
    """A Bet from one _BET_SQL row, or None when it cannot be measured at all
    (no price, no start)."""
    from tracking.paper_tracker import _bet_price_and_book
    price, book = _bet_price_and_book(row["model_id"], row["dk_odds"], row["decision_odds"],
                                      row["decision_book"], row["pick_label"])
    created = _utc(row["created_at"])
    commence = _utc(row["commence_time"])
    if price is None or not book or created is None or commence is None:
        return None
    bound = commence
    game_time = _utc(row["game_time"])
    if game_time is not None and game_time < bound:
        bound = game_time
    if row["game_id"].split("_", 1)[0] == "NBA":
        tip = _utc(row["nba_tip"])
        # An NBA bet whose only start is the feed's has no bound we trust
        # (docs/clv.md, first paragraph): unmeasured.
        bound = min(bound, tip) if tip is not None else None
    if row["model_id"] in _ROW_MARKET_MODELS:
        kind, market = "prop", row["prop_market"]
    elif row["prop_key"]:
        kind, market = "prop", row["prop_key"]
    else:
        kind, market = "game", row["game_market"]
    m = _PLAYER_RE.match(row["pick_label"] or "")
    return Bet(
        pick_id=int(row["pick_id"]), model_id=row["model_id"], game_id=row["game_id"],
        pick_side=(row["pick_side"] or "").lower(), number=_f(row["scored_line"]),
        kind=kind, market=market, player=m.group(1) if (kind == "prop" and m) else None,
        created_at=created, bound=bound, bet_price=float(price), bet_book=book.strip().lower(),
        prop_market=row["prop_market"] if kind == "prop" else None,
        before={k: _jsonable(row[k]) for k in _BEFORE},
        first_play=_utc(row.get("first_play")),
    )


def load_bets(conn, where: str, params: tuple = ()) -> list[Bet]:
    rows = conn.execute(_BET_SQL + " WHERE " + where, params).fetchall()
    conn.commit()
    out = []
    for r in rows:
        b = bet_from_row(dict(zip(_BET_COLS, r)))
        if b is not None:
            out.append(b)
    return out


# ── the quotes ───────────────────────────────────────────────────────────────

def _markets(bet: Bet) -> list[str]:
    return [m for m in (bet.market, bet.alt) if m]


def feed_quotes(conn, bet: Bet) -> list[Quote]:
    """The bet book's stored rows for this bet, pulled after the bet and at or
    before the start."""
    if bet.bound is None or not bet.market:
        return []
    if bet.kind == "prop":
        if not bet.player:
            return []
        rows = conn.execute("""
            SELECT market, created_at::timestamptz, line, over_price, under_price, player_name
              FROM public.player_prop_odds
             WHERE game_id = %s AND bookmaker = %s AND market = ANY(%s)
               AND created_at IS NOT NULL
               AND created_at::timestamptz > %s AND created_at::timestamptz <= %s
        """, (bet.game_id, bet.bet_book, _markets(bet), bet.created_at, bet.bound)).fetchall()
        conn.commit()
        want = player_key(bet.player)
        return [Quote(r[0], _utc(r[1]), _f(r[2]), {"over_price": _f(r[3]), "under_price": _f(r[4])}, "feed")
                for r in rows if player_key(r[5]) == want]
    rows = conn.execute("""
        SELECT market, created_at::timestamptz, spread_home, total_line,
               home_price, away_price, draw_price, over_price, under_price
          FROM public.odds
         WHERE game_id = %s AND bookmaker = %s AND market = ANY(%s)
           AND snapshot_type <> 'in_play'
           AND created_at IS NOT NULL
           AND created_at::timestamptz > %s AND created_at::timestamptz <= %s
    """, (bet.game_id, bet.bet_book, _markets(bet), bet.created_at, bet.bound)).fetchall()
    conn.commit()
    return [_game_quote(r[0], _utc(r[1]), r[2:], "feed", bet) for r in rows]


def history_quotes(conn, bet: Bet) -> list[Quote]:
    """Quotes in clv_close_quotes, same bounds: bought from the feed's history
    (scripts/clv_close_history.py) or pulled live just before the start
    (data/ingestors/clv_closing_pull.py). Both carry the instant they were
    pulled as fetched_at."""
    if bet.bound is None or not bet.market:
        return []
    rows = conn.execute("""
        SELECT market, fetched_at, spread_home, total_line, home_price, away_price,
               draw_price, over_price, under_price, line, player_name
          FROM public.clv_close_quotes
         WHERE game_id = %s AND bookmaker = %s AND market = ANY(%s)
           AND fetched_at > %s AND fetched_at <= %s
    """, (bet.game_id, bet.bet_book, _markets(bet), bet.created_at, bet.bound)).fetchall()
    conn.commit()
    out = []
    for r in rows:
        if bet.kind == "prop":
            if player_key(r[10]) != player_key(bet.player):
                continue
            out.append(Quote(r[0], _utc(r[1]), _f(r[9]),
                             {"over_price": _f(r[7]), "under_price": _f(r[8])}, "history"))
        else:
            out.append(_game_quote(r[0], _utc(r[1]), r[2:9], "history", bet))
    return out


_TENNIS_TOURS = ("ATP", "WTA")
_TENNIS_TABLES = ("tennis_moneyline_decisions", "tennis_odds_fetches", "tennis_odds_quotes")


def _tennis_ready(conn) -> bool:
    row = conn.execute("SELECT " + " AND ".join(
        f"to_regclass('public.{t}') IS NOT NULL" for t in _TENNIS_TABLES)).fetchone()
    conn.commit()
    return bool(row and row[0])


def tennis_quotes(conn, bet: Bet) -> list[Quote]:
    """The bet book's tennis match-winner quote at each of the card's polls
    after the bet and at or before the start.

    `tennis_odds_quotes` holds a row only when a book's quote CHANGED, and its
    `snapshot_ts` is the poll that saw the change. So a row after the bet is
    not the test of a pull after the bet: a book whose price held still has no
    row then. The pulls are the card's live polls in `tennis_odds_fetches`
    (one per book group, `snapshot_ts` the poll instant, `events` > 0 when the
    feed answered with matches), and the book's quote at a pull is its newest
    row at or before it. The match is the feed event the card decided
    (`tennis_moneyline_decisions`, by game id); pick_side home is the feed's
    home player, as the card wrote it."""
    if (bet.bound is None or bet.market != "h2h"
            or bet.game_id.split("_", 1)[0] not in _TENNIS_TOURS or not _tennis_ready(conn)):
        return []
    rows = conn.execute("""
        WITH ev AS (
            SELECT DISTINCT event_id, sport_key FROM public.tennis_moneyline_decisions
             WHERE game_id = %s),
        polls AS (
            SELECT DISTINCT ev.event_id, f.snapshot_ts AS pulled_at
              FROM ev JOIN public.tennis_odds_fetches f
                ON f.sport_key = ev.sport_key AND f.endpoint = 'live' AND f.events > 0
               AND f.snapshot_ts > %s AND f.snapshot_ts <= %s)
        SELECT p.pulled_at, q.home_price, q.away_price
          FROM polls p
          CROSS JOIN LATERAL (
               SELECT t.home_price, t.away_price FROM public.tennis_odds_quotes t
                WHERE t.event_id = p.event_id AND t.bookmaker = %s AND t.market = 'h2h'
                  AND t.snapshot_ts <= p.pulled_at
                ORDER BY t.snapshot_ts DESC LIMIT 1) q
    """, (bet.game_id, bet.created_at, bet.bound, bet.bet_book)).fetchall()
    conn.commit()
    return [Quote("h2h", _utc(r[0]), None, {"home_price": _f(r[1]), "away_price": _f(r[2])}, "feed")
            for r in rows]


def _game_quote(market, fetched, vals, source, bet: Bet) -> Quote:
    spread, total, home, away, draw, over, under = vals
    number = _f(spread) if "spreads" in market else (_f(total) if "totals" in market else None)
    return Quote(market, fetched, number,
                 {"home_price": _f(home), "away_price": _f(away), "draw_price": _f(draw),
                  "over_price": _f(over), "under_price": _f(under)}, source)


# ── the rule ─────────────────────────────────────────────────────────────────

def _ours(q: Quote, bet: Bet) -> float | None:
    """Our side's price in this quote when it is at our exact number."""
    has_number = bet.kind == "prop" or "spreads" in q.market or "totals" in q.market
    if has_number:
        if q.number is None or bet.number is None or abs(q.number - bet.number) > 1e-9:
            return None
    col = _SIDE_COL.get(bet.pick_side)
    return q.prices.get(col) if col else None


def _line_pts(bet: Bet, main_number: float | None) -> float | None:
    from tracking.paper_tracker import _line_clv_pts
    if main_number is None or bet.number is None:
        return None
    # A prop's line move reads its own market when picks.prop_market is empty
    # (the single-market prop models leave it empty): without it the move was
    # never recorded, and a moved prop line showed as "no closing price".
    return _line_clv_pts(bet.market or "", (bet.prop_market or bet.market) if bet.kind == "prop" else None,
                         bet.pick_side, bet.number, main_number)


def _last_poll(quotes: list[Quote]) -> tuple[datetime | None, list[Quote]]:
    if not quotes:
        return None, []
    last = max(q.fetched_at for q in quotes)
    return last, [q for q in quotes if q.fetched_at >= last - POLL_TOLERANCE]


def choose_close(bet: Bet, quotes: list[Quote]) -> Close:
    """The close under the rule in the module docstring. Pure: no database."""
    if bet.bound is None:
        return Close("none", note="no start we can bound on")
    main_t, main_poll = _last_poll([q for q in quotes if q.market == bet.market])
    alt_t, alt_poll = _last_poll([q for q in quotes if bet.alt and q.market == bet.alt])
    last = max(t for t in (main_t, alt_t, None) if t is not None) if (main_t or alt_t) else None
    if last is None:
        return Close("none", note="no pull of this book after the bet and before the start")
    line_pts = None
    main_number = None
    if main_poll:
        newest = max(main_poll, key=lambda q: q.fetched_at)
        main_number = newest.number
        for q in sorted(main_poll, key=lambda q: q.fetched_at, reverse=True):
            price = _ours(q, bet)
            if price is not None:
                return Close(q.source, q.market, q.fetched_at, price,
                             bet.number if q.number is not None else None,
                             _line_pts(bet, q.number) if q.number is not None else None,
                             last, "main line")
        line_pts = _line_pts(bet, main_number)
    if alt_poll and (main_t is None or alt_t >= main_t - ALT_WINDOW):
        for q in sorted(alt_poll, key=lambda q: q.fetched_at, reverse=True):
            price = _ours(q, bet)
            if price is not None:
                return Close(q.source, q.market, q.fetched_at, price, bet.number,
                             line_pts, last, "alternate ladder")
    note = ("the book's last pull did not price our number"
            if main_poll or alt_poll else "no pull after the bet")
    return Close("none", None, None, None, main_number, line_pts, last, note)


def late_bet(bet: Bet) -> Bet | None:
    """The bet bounded on its game's first play, when that is later than the
    listed start; None otherwise."""
    if bet.first_play is None or bet.bound is None:
        return None
    late = bet.first_play - FIRST_PLAY_MARGIN
    return replace(bet, bound=late) if late > bet.bound else None


def choose_final(bet: Bet, quotes: list[Quote]) -> Close:
    """The close at the listed start; for a bet with no pull between it and the
    listed start, the close before the first play. Pure: no database. `quotes`
    may run to the first-play bound (quotes_for)."""
    if bet.first_play is not None and bet.created_at >= bet.first_play:
        return Close("none", note=(f"placed after the game began (first play "
                                   f"{bet.first_play:%Y-%m-%d %H:%M:%S}Z): not a pre-game bet"))
    quotes = [q for q in quotes if q.fetched_at > bet.created_at]
    listed = [q for q in quotes if bet.bound is not None and q.fetched_at <= bet.bound]
    close = choose_close(bet, listed)
    late = late_bet(bet)
    if close.odds is None and close.last_poll is None and late is not None:
        alt = choose_close(late, [q for q in quotes if q.fetched_at <= late.bound])
        if alt.last_poll is not None:
            alt.note = f"{alt.note}, pulled after the listed start and before the first play"
            return alt
    return close


def quotes_for(conn, bet: Bet, history: bool = True) -> list[Quote]:
    """Every quote choose_final may use: to the first-play bound when there is
    one, else to the listed start."""
    b = late_bet(bet) or bet
    return (feed_quotes(conn, b) + tennis_quotes(conn, b)
            + (history_quotes(conn, b) if history else []))


def close_for(conn, bet: Bet) -> Close:
    return choose_final(bet, quotes_for(conn, bet))


# ── writing ──────────────────────────────────────────────────────────────────

def measure(bet: Bet, close: Close) -> dict:
    pct, pp = (same_book_clv(bet.bet_price, close.odds) if close.odds is not None else (None, None))
    return {"clv_pct": pct, "clv_pp": pp}


def write(conn, bet: Bet, close: Close, now: datetime | None = None) -> dict:
    """The bet's closing-line columns, and its measurement row. Commits."""
    now = now or datetime.now(timezone.utc)
    m = measure(bet, close)
    beat = None if m["clv_pct"] is None else bool(m["clv_pct"] > 0)
    conn.execute("""
        UPDATE public.picks
           SET closing_dk_odds = %s, closing_line = %s, clv_pct = %s, clv_pp = %s,
               line_clv_pts = %s, clv_beat_close = %s, clv_captured_at = %s,
               clv_method = 'standard_v2', clv_close_book = %s, clv_bet_book = %s
         WHERE pick_id = %s
    """, (close.odds, close.line, m["clv_pct"], m["clv_pp"], close.line_pts, beat,
          now.strftime("%Y-%m-%dT%H:%M:%SZ"), bet.bet_book if close.odds is not None else None,
          bet.bet_book, bet.pick_id))
    conn.execute("""
        INSERT INTO public.clv_close_measurements
               (pick_id, measured_at, rule, source, bet_book, bet_price, close_market,
                close_fetched_at, close_odds, close_line, clv_pct, clv_pp, line_clv_pts,
                last_poll_at, note, before)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (pick_id) DO UPDATE SET
               measured_at = EXCLUDED.measured_at, rule = EXCLUDED.rule, source = EXCLUDED.source,
               bet_book = EXCLUDED.bet_book, bet_price = EXCLUDED.bet_price,
               close_market = EXCLUDED.close_market, close_fetched_at = EXCLUDED.close_fetched_at,
               close_odds = EXCLUDED.close_odds, close_line = EXCLUDED.close_line,
               clv_pct = EXCLUDED.clv_pct, clv_pp = EXCLUDED.clv_pp,
               line_clv_pts = EXCLUDED.line_clv_pts, last_poll_at = EXCLUDED.last_poll_at,
               note = EXCLUDED.note
    """, (bet.pick_id, now, RULE, close.source if close.odds is not None else "none",
          bet.bet_book, bet.bet_price, close.market, close.fetched_at, close.odds, close.line,
          m["clv_pct"], m["clv_pp"], close.line_pts, close.last_poll, close.note,
          json.dumps(bet.before)))
    conn.commit()
    return {**m, "source": close.source if close.odds is not None else "none"}


# ── the stage ────────────────────────────────────────────────────────────────

_STAGE_WHERE = """
        p.signal_type = 'BET'
    AND p.is_live IS NOT TRUE
    AND COALESCE(p.decision_odds, p.dk_odds) IS NOT NULL
    AND p.model_id NOT LIKE 'golf_%%'
    AND p.game_date >= %s
    AND g.commence_time IS NOT NULL
    AND g.commence_time::timestamptz >= %s::timestamptz
    AND g.commence_time::timestamptz <= %s::timestamptz
    AND p.created_at::timestamptz <= g.commence_time::timestamptz
    AND NOT EXISTS (SELECT 1 FROM public.clv_close_measurements m WHERE m.pick_id = p.pick_id)
  ORDER BY p.pick_id
  LIMIT %s
"""


def measure_started(conn, now: datetime | None = None, limit: int = BATCH) -> dict:
    """Every pre-game BET on a game that started at least SETTLE_AFTER ago,
    from STORED_FROM on, not yet measured. Stored rows only. Returns counts."""
    now = now or datetime.now(timezone.utc)
    if not _ready(conn):
        return {"skipped": "clv_close_measurements does not exist yet"}
    bets = load_bets(conn, _STAGE_WHERE,
                     (STORED_FROM[:10], STORED_FROM, (now - SETTLE_AFTER).isoformat(), limit))
    counts = {"bets": len(bets), "priced": 0, "unpriced": 0, "waiting": 0}
    for bet in bets:
        if bet.bound is None and bet.game_id.startswith("NBA_"):
            # The schedule row may still arrive (docs/clv.md); stamp only
            # after two days, as the earlier writers do.
            if (now - bet.created_at) < timedelta(days=2):
                counts["waiting"] += 1
                continue
        try:
            close = close_for(conn, bet)
            res = write(conn, bet, close, now)
        except Exception as exc:                               # noqa: BLE001
            # One bad bet must not pin the head of the queue (ORDER BY
            # pick_id): it is recorded as measured with no close and the
            # error, and the pass goes on.
            logger.warning(f"CLV final close: pick {bet.pick_id} failed ({exc})")
            try:
                conn.rollback()
            except Exception:                                  # noqa: BLE001
                pass
            counts["failed"] = counts.get("failed", 0) + 1
            try:
                write(conn, bet, Close("none", note=f"error: {str(exc)[:200]}"), now)
            except Exception:                                  # noqa: BLE001
                conn.rollback()
            continue
        counts["priced" if res["clv_pct"] is not None else "unpriced"] += 1
    if bets:
        logger.info(f"CLV final close: {counts}")
    return counts


def _ready(conn) -> bool:
    row = conn.execute("SELECT to_regclass('public.clv_close_measurements') IS NOT NULL").fetchone()
    conn.commit()
    return bool(row and row[0])
