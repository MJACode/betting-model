"""Another sportsbook's live number from its own page, for the in-play models'
best line (mike, 2026-11-26: "We want best line"; issue #1644).

The rows are `book_live_reads`, written on mike's machine by
data/ingestors/book_live_boards.py: per book and game, a row whenever the
eight numbers change (a market leaving the page goes NULL), clean reads only,
with each answer's own age (FanDuel's page is a CDN copy) and the same book
and sport's previous clean read. `book_live_feed` holds each book and sport's
newest read.

A NUMBER MAY DECIDE ONLY WHEN ALL OF THESE HOLD. Each one is measured, not
assumed (docs/live_betting.md, "Best line on the fast path"):
  FRESH FEED  the book's newest answer for the sport was clean and its PAGE
              time (read_at - page_age_s) is within FEED_MAX_AGE_SEC of now:
              DraftKings' own bound (models/ncaab_live_dk.FEED_MAX_AGE_SEC),
              not a looser one for a cached page. FanDuel's answers ran 13-41 s
              old on 2026-11-26, so FanDuel will often not qualify; that is
              the measurement, not a setting to tune.
  ON OFFER    the game's newest row on that book carries the market.
  KNOWN START the read before the number first appeared is known: not a first
              row after a feed start, not a row written before the prev_*
              columns existed.
  STAMP       `stamp` = that previous read's page time. The page did not show
              the number then, so the book set it after: the caller's
              "no point scored since the stamp" rule (the grade's FRESH rule)
              runs from here, which is what makes a number up before the last
              score ineligible however young it looks. `shown` = the page time
              of the first read that showed it (the state is priced there, as
              DraftKings' rows are priced at their first sighting).
  HELD        the book's newest read is after the first read that showed it.
Pure functions; a loop reads the tables through DbSource.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FEED_MAX_AGE_SEC = 8.0
LOOKBACK_MIN = 60
# The books with a parsed own page (book_live_boards.BOOKS, kind PARSED).
BOOKS = ("fanduel", "betrivers")
SPREAD_KEY = ("spread_home", "spread_home_price", "spread_away_price")
TOTAL_KEY = ("total_line", "over_price", "under_price")
ML_KEY = ("home_ml", "away_ml")
KEYS = {"spreads": SPREAD_KEY, "totals": TOTAL_KEY, "h2h": ML_KEY}
ROW_COLS = ("book", "game_id", "read_at", "page_age_s", "after_start", "spread_home", "spread_home_price",
            "spread_away_price", "total_line", "over_price", "under_price", "home_ml", "away_ml",
            "prev_read_at", "prev_page_age_s")
FEED_COLS = ("book", "last_read_at", "ok", "page_age_s")
QUOTE_COLS = ["game_id", "market", "book", "stamp", "shown", "held", "spread_home", "home_price", "away_price",
              "total_line", "over_price", "under_price"]


def _ts(x) -> pd.Timestamp | None:
    if x is None or (not isinstance(x, pd.Timestamp) and pd.isna(x)):
        return None
    t = pd.Timestamp(x)
    if pd.isna(t):
        return None
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def page_time(read_at, page_age_s) -> pd.Timestamp | None:
    """When the book's own site held what this answer shows: the read time
    less the answer's Age (a CDN copy), the read time when it sent none."""
    t = _ts(read_at)
    if t is None:
        return None
    age = 0.0 if page_age_s is None or pd.isna(page_age_s) else float(page_age_s)
    return t - pd.Timedelta(seconds=max(age, 0.0))


def fresh_books(feed: pd.DataFrame, now, books=BOOKS, max_age: float = FEED_MAX_AGE_SEC) -> set:
    """The books whose newest answer for the sport was clean and whose page
    time is within `max_age` seconds of `now`."""
    now = _ts(now)
    out = set()
    if feed is None or not len(feed):
        return out
    for _i, r in feed.iterrows():
        if r["book"] not in books or not bool(r["ok"]):
            continue
        pt = page_time(r["last_read_at"], r.get("page_age_s"))
        if pt is not None and 0.0 <= (now - pt).total_seconds() <= max_age:
            out.add(r["book"])
    return out


def _same(a, b) -> bool:
    return all((pd.isna(x) and pd.isna(y)) or x == y for x, y in zip(a, b))


def current_quotes(rows: pd.DataFrame, feed: pd.DataFrame, at, markets=("spreads", "totals"),
                   books=BOOKS) -> pd.DataFrame:
    """One row per (book, game, market) that passes every gate above at `at`
    (the caller's decision time), in the loops' odds vocabulary: game_id,
    market, book, stamp, shown, held, spread_home (the HOME number),
    home_price, away_price, total_line, over_price, under_price. A spread's
    prices are the home and away sides at that number; a moneyline's are
    home_price / away_price with no line."""
    at = _ts(at)
    fresh = fresh_books(feed, at, books)
    last_read = {r["book"]: _ts(r["last_read_at"]) for _i, r in (feed.iterrows() if feed is not None else [])}
    out = []
    if rows is None or not len(rows) or not fresh:
        return pd.DataFrame(out, columns=QUOTE_COLS)
    r = rows[rows["book"].isin(fresh)].copy()
    r["read_at"] = pd.to_datetime(r["read_at"], utc=True)
    r = r[r["read_at"] <= at]
    for (book, gid), g in r.groupby(["book", "game_id"], sort=True):
        g = g.sort_values("read_at").reset_index(drop=True)
        last = g.iloc[-1]
        for market in markets:
            key = KEYS[market]
            cur = tuple(last[k] for k in key)
            if any(pd.isna(x) for x in cur):
                continue                                   # not on offer at the newest read
            i = len(g) - 1
            while i > 0 and _same(tuple(g.iloc[i - 1][k] for k in key), cur):
                i -= 1
            first = g.iloc[i]
            if bool(first["after_start"]) or _ts(first.get("prev_read_at")) is None:
                continue                                   # when it went up is unknown
            stamp = page_time(first["prev_read_at"], first.get("prev_page_age_s"))
            shown = page_time(first["read_at"], first.get("page_age_s"))
            held = last_read.get(book) is not None and last_read[book] > first["read_at"]
            row = {"game_id": gid, "market": market, "book": book, "stamp": stamp, "shown": shown, "held": held,
                   "spread_home": np.nan, "home_price": np.nan, "away_price": np.nan,
                   "total_line": np.nan, "over_price": np.nan, "under_price": np.nan}
            if market == "spreads":
                row.update(spread_home=float(cur[0]), home_price=float(cur[1]), away_price=float(cur[2]))
            elif market == "totals":
                row.update(total_line=float(cur[0]), over_price=float(cur[1]), under_price=float(cur[2]))
            else:
                row.update(home_price=float(cur[0]), away_price=float(cur[1]))
            out.append(row)
    return pd.DataFrame(out, columns=QUOTE_COLS)


def feed_rows(conn, sport: str) -> pd.DataFrame:
    """Each book's newest answer for the sport (book_live_feed)."""
    from data.db import release_read
    try:
        rows = conn.execute(f"SELECT {', '.join(FEED_COLS)} FROM book_live_feed WHERE sport = %s",
                            (sport,)).fetchall()
    finally:
        release_read(conn)
    df = pd.DataFrame(rows, columns=list(FEED_COLS))
    if len(df):
        df["last_read_at"] = pd.to_datetime(df["last_read_at"], utc=True)
        df["page_age_s"] = pd.to_numeric(df["page_age_s"], errors="coerce")
    return df


def recent_rows(conn, sport: str, game_ids, books=BOOKS, lookback_min: int = LOOKBACK_MIN) -> pd.DataFrame:
    """The games' book_live_reads rows of the last `lookback_min` minutes."""
    from data.db import release_read
    if not game_ids:
        return pd.DataFrame(columns=list(ROW_COLS))
    try:
        rows = conn.execute(f"""
            SELECT {', '.join(ROW_COLS)} FROM book_live_reads
             WHERE sport = %s AND game_id = ANY(%s) AND book = ANY(%s)
               AND read_at > NOW() - (%s || ' minutes')::interval
             ORDER BY book, game_id, read_at
        """, (sport, sorted(game_ids), list(books), str(int(lookback_min)))).fetchall()
    finally:
        release_read(conn)
    df = pd.DataFrame(rows, columns=list(ROW_COLS))
    if len(df):
        df["read_at"] = pd.to_datetime(df["read_at"], utc=True)
        df["prev_read_at"] = pd.to_datetime(df["prev_read_at"], utc=True)
        for c in ROW_COLS[5:13] + ("page_age_s", "prev_page_age_s"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


class DbSource:
    """A loop's other-books source on the worker, for one sport, on the
    loop's own connection."""

    def __init__(self, conn_fn, sport: str, books=BOOKS):
        self.c, self.sport, self.books = conn_fn, sport, tuple(books)

    def feed(self) -> pd.DataFrame:
        return feed_rows(self.c(), self.sport)

    def rows(self, game_ids) -> pd.DataFrame:
        return recent_rows(self.c(), self.sport, game_ids, self.books)

    def quotes(self, game_ids, at, markets=("spreads", "totals")) -> pd.DataFrame:
        return current_quotes(self.rows(game_ids), self.feed(), at, markets, self.books)
