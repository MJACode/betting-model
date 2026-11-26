"""When a sportsbook rate limits or refuses our live reads: a row in Supabase
for each episode, and a red alert in the ops channel.

mike, 2026-11-26: "Can you add a red alert that goes to the ops channel if you
detect that the book is rate limiting or throttling our connection?"

TWO HALVES, ON TWO MACHINES.
  * Here, on mike's machine, inside DraftKings' board (dk_live_board.py) and
    the other books' thread (book_live_boards.py): ThrottleTracker sees every
    real request's answer and writes a row to `book_throttle_events` only when
    something changes. An episode opens ('throttled'), the reader benches the
    book ('backoff'), or the book answers cleanly again ('cleared'). A clean
    read on a healthy book writes nothing.
  * On the worker, tracking/book_throttle_watch.py reads the new rows every
    2 minutes and posts the red alert and the green all-clear. The worker is
    the machine that holds the ops webhook; mike's machine is not known to.

WHAT COUNTS. An episode opens on the first 429 (the book saying "too many
requests", which needs no second look), or on the Nth push-back in a row, N
being the reader's own back-off count (3 for the other books, 5 for
DraftKings): a 403 or 503, a bot-challenge page, or no answer at all (a
timeout or a dropped connection, which is how throttling at the network
looks). A 400, 404 or 500 is a wrong URL or a broken page, not throttling: it
stays in the feed tables and neither opens nor closes an episode.

NOT DETECTED: an answer that arrives slowly. No request time is recorded.

NEVER RAISES AND NEVER DELAYS A READ. A failed write is rolled back and the
rows wait for the next flush (at most MAX_PENDING of them).
"""
from __future__ import annotations

import logging
import socket
from datetime import datetime, timezone
from typing import Callable

log = logging.getLogger("data.ingestors.book_throttle")

TABLE = "book_throttle_events"
COLS = ("id", "at", "host", "book", "sport", "kind", "reason", "status",
        "in_a_row", "poll_s", "episode", "detail")
INDEX = "book_throttle_events_at"
DDL = """
CREATE TABLE IF NOT EXISTS book_throttle_events (
    id        BIGSERIAL PRIMARY KEY,
    at        TIMESTAMPTZ NOT NULL,
    host      TEXT,
    book      TEXT NOT NULL,
    sport     TEXT NOT NULL,
    kind      TEXT NOT NULL,
    reason    TEXT,
    status    INTEGER,
    in_a_row  INTEGER,
    poll_s    DOUBLE PRECISION,
    episode   TEXT NOT NULL,
    detail    TEXT
);
CREATE INDEX IF NOT EXISTS book_throttle_events_at ON book_throttle_events (at)
"""

THROTTLED, BACKOFF, CLEARED = "throttled", "backoff", "cleared"
RATE_LIMITED, REFUSED, NO_ANSWER = "rate_limited", "refused", "no_answer"
MAX_PENDING = 200


def reason_for(status: int | None, refused: bool, answered: bool = True) -> str | None:
    """What one answer says about our request rate. `refused` is the reader's
    own verdict (a 403/429/503 or a challenge page). None: not push-back."""
    if not answered:
        return NO_ANSWER
    if status == 429:
        return RATE_LIMITED
    if refused or status in (403, 503):
        return REFUSED
    return None


def ensure_table(conn) -> None:
    """Create the table once; a no-op catalog read every later start."""
    from data.anon_readable import API_ROLES, lock_down
    from data.ddl_guard import schema_is_current
    if not schema_is_current(conn, TABLE, columns=COLS, indexes=(INDEX,), rls=True,
                             revoked_from=API_ROLES):
        conn.execute(DDL)
        lock_down(conn, TABLE)
    conn.commit()


class ThrottleTracker:
    """Episodes per book. `observe` takes every real request's answer and
    returns the row it adds (or None); `flush` writes what is waiting."""

    def __init__(self, threshold: int, *, clock: Callable[[], datetime] | None = None,
                 host: str | None = None):
        self.threshold = int(threshold)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.host = host if host is not None else socket.gethostname()
        self.in_a_row: dict[str, int] = {}
        self.open: dict[str, dict] = {}            # book -> the row that opened its episode
        self.pending: list[dict] = []
        self.table_ready = False

    def _row(self, book, sport, kind, reason, status, in_a_row, poll_s, episode, detail) -> dict:
        row = {"at": self.clock(), "host": self.host, "book": book, "sport": sport, "kind": kind,
               "reason": reason, "status": status, "in_a_row": in_a_row,
               "poll_s": None if poll_s is None else float(poll_s), "episode": episode,
               "detail": (detail or "")[:300]}
        self.pending = (self.pending + [row])[-MAX_PENDING:]
        return row

    def observe(self, book: str, sport: str, *, clean: bool, reason: str | None,
                status: int | None = None, poll_s: float | None = None, detail: str = "") -> dict | None:
        if reason is None:
            if not clean:
                return None                         # a 4xx/5xx that is not push-back: no change
            self.in_a_row[book] = 0
            ep = self.open.pop(book, None)
            if ep is None:
                return None
            secs = (self.clock() - ep["at"]).total_seconds()
            return self._row(book, sport, CLEARED, ep["reason"], status, 0, poll_s, ep["episode"],
                             f"answered cleanly again after {secs:.0f} s")
        n = self.in_a_row[book] = self.in_a_row.get(book, 0) + 1
        if book in self.open or (reason != RATE_LIMITED and n < self.threshold):
            return None
        at = self.clock()
        row = self._row(book, sport, THROTTLED, reason, status, n, poll_s,
                        f"{book}|{at.isoformat()}", detail)
        self.open[book] = row
        return row

    def backoff(self, book: str, sport: str, seconds: float, *,
                poll_s: float | None = None) -> dict | None:
        """The reader has benched the book for `seconds`. Recorded only inside
        an episode: DraftKings' board also benches on a run of 404s or 500s,
        which is a broken page, not throttling."""
        ep = self.open.get(book)
        if ep is None:
            return None
        return self._row(book, sport, BACKOFF, ep["reason"], None, self.in_a_row.get(book, 0), poll_s,
                         ep["episode"], f"left alone {seconds:.0f} s")

    def flush(self, conn) -> int:
        """Write what is waiting. Never raises; a failure keeps the rows."""
        if not self.pending:
            return 0
        rows = list(self.pending)
        try:
            if not self.table_ready:
                ensure_table(conn)
                self.table_ready = True
            cols = COLS[1:]
            sql = (f"INSERT INTO {TABLE} ({', '.join(cols)}) "
                   f"VALUES ({', '.join(['%s'] * len(cols))})")
            for r in rows:
                conn.execute(sql, tuple(r[c] for c in cols))
            conn.commit()
        except Exception as exc:                    # noqa: BLE001
            log.error("throttle events not written (kept for the next flush): %s", exc)
            try:
                conn.rollback()
            except Exception:                       # noqa: BLE001
                pass
            return 0
        self.pending = self.pending[len(rows):]
        for r in rows:
            log.warning("throttle %s: %s %s %s (%s)", r["kind"], r["book"], r["sport"],
                        r["reason"], r["detail"])
        return len(rows)
