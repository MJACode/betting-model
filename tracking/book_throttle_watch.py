"""A red alert in the ops channel when a sportsbook rate limits or refuses our
live reads, and a green one when it answers again.

mike, 2026-11-26: "Can you add a red alert that goes to the ops channel if you
detect that the book is rate limiting or throttling our connection?"

DETECTION IS ON MIKE'S MACHINE, DELIVERY IS HERE. The readers there
(DraftKings' board and the other books' thread) write a row to
`book_throttle_events` when an episode opens, when they bench a book and when
it answers cleanly again (data/ingestors/book_throttle.py says what counts).
This watch runs on the worker every 2 minutes, because the worker holds the
ops webhook, and turns each new episode into one message.

ONE RED MESSAGE PER EPISODE, ONE GREEN ONE WHEN IT CLEARS. Both are ledgered
in `push_sent` (kinds `book_throttle` and `book_throttle_clear`, keyed on the
episode) only after the post confirms, so a redeploy cannot re-page and a
failed post is tried again on the next tick. An episode that opened and
cleared between two ticks is one red message that says it has cleared.

NOT PAGED: a book that has never answered cleanly in the 7 days before the
episode (no 200 in `book_live_raw`). That is a standing block, not a book
throttling a connection it was serving: Caesars has refused every request
from mike's machine since it was added (403 on all 16 stored answers,
2026-11-26 00:14 to 11:48 UTC). DraftKings is the feed itself and always pages.

NEVER RAISES. A watch that dies on its own bookkeeping is the silence it is
there to end.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from loguru import logger

from tracking.watch_util import post_ops_alert, query_rows

KIND, CLEAR_KIND = "book_throttle", "book_throttle_clear"
WINDOW = timedelta(hours=6)          # episodes older than this are history, not news
ANSWERED_WITHIN = timedelta(days=7)

_REASON_TITLE = {
    "rate_limited": "is rate limiting our live reads",
    "refused": "is refusing our live reads",
    "no_answer": "stopped answering our live reads",
}


def _name(book: str) -> str:
    try:
        from pc_monitor.readers import BOOK_NAMES
        return BOOK_NAMES.get(book, book)
    except Exception:                 # noqa: BLE001
        return book


def _et(at: datetime) -> str:
    from zoneinfo import ZoneInfo
    t = at.astimezone(ZoneInfo("America/New_York"))
    return t.strftime("%I:%M:%S %p ET").lstrip("0")


def _what(ev: dict) -> str:
    n, status, reason = ev.get("in_a_row") or 1, ev.get("status"), ev.get("reason")
    if reason == "rate_limited":
        return "HTTP 429 (too many requests)"
    if reason == "no_answer":
        return (f"{n} requests in a row got no answer (a timeout or a dropped connection). "
                "Throttling at the network looks like this; so does the book being down")
    code = f"HTTP {status}" if status else "a bot-challenge page"
    return f"{n} refusals in a row ({code})"


def red_message(ev: dict, backoffs: int, cleared: dict | None) -> tuple[str, str]:
    name = _name(ev["book"])
    title = f"{name} {_REASON_TITLE.get(ev.get('reason'), 'is refusing our live reads')}"
    if cleared is not None:
        title += " (answering again)"
    poll = ev.get("poll_s")
    lines = [
        f"**What:** {_what(ev)}, on the {ev['sport']} read at {_et(ev['at'])}.",
        f"**Our rate:** one read every {poll:g} s for that league." if poll else None,
        f"**From:** {ev.get('host') or 'the PC'}.",
    ]
    if cleared is not None:
        lines.append(f"**Now:** {cleared.get('detail') or 'answering cleanly again'}.")
    else:
        bench = f" It has benched {name} {backoffs} time(s) so far." if backoffs else ""
        lines.append(f"**Now:** the reader backs off by itself and retries.{bench} No live lines from "
                     f"{name} until it answers; an all-clear posts here when it does.")
    if ev["book"] == "draftkings":
        lines.append("DraftKings' board is the feed the NCAAB in-play loop reads.")
    return title, "\n".join(x for x in lines if x)


def green_message(ev: dict, cleared: dict, backoffs: int) -> tuple[str, str]:
    name = _name(ev["book"])
    detail = f"{cleared.get('detail') or 'Answering cleanly again'} (from {_et(cleared['at'])})."
    if backoffs:
        detail += f" Benched {backoffs} time(s) in between."
    return f"{name} is answering our live reads again", detail


def _answered_before(conn, book: str, at: datetime) -> bool:
    if book == "draftkings":
        return True
    rows = query_rows(conn, """
        SELECT 1 FROM book_live_raw
         WHERE book = %s AND status = 200 AND fetched_at >= %s AND fetched_at < %s
         LIMIT 1
    """, (book, at - ANSWERED_WITHIN, at), label="book_throttle_watch")
    return bool(rows)


def _ledger(conn, key: str, kind: str) -> None:
    try:
        conn.execute("INSERT INTO push_sent (lock_key, kind, sent_at) VALUES (%s, %s, %s) "
                     "ON CONFLICT (lock_key, kind) DO NOTHING",
                     (key, kind, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    except Exception:                 # noqa: BLE001 - posted but not ledgered
        logger.exception(f"book_throttle_watch: posted {key} but could not ledger it")
        try:
            conn.rollback()
        except Exception:             # noqa: BLE001
            pass


COLS = ("id", "at", "host", "book", "sport", "kind", "reason", "status",
        "in_a_row", "poll_s", "episode", "detail")


def check(conn, now: datetime, post=None) -> dict:
    out = {"alerted": [], "cleared": [], "skipped": []}
    have = query_rows(conn, "SELECT to_regclass('public.book_throttle_events') IS NOT NULL",
                      label="book_throttle_watch")
    if not have or not have[0][0]:
        return out                     # mike's machine has not created it yet: nothing has happened
    rows = query_rows(conn, f"""
        SELECT {', '.join(COLS)} FROM book_throttle_events
         WHERE at > %s ORDER BY id
    """, (now - WINDOW,), label="book_throttle_watch")
    episodes: dict[str, dict] = {}
    for r in rows:
        ev = dict(zip(COLS, r))
        ep = episodes.setdefault(ev["episode"], {"open": None, "backoffs": 0, "cleared": None})
        if ev["kind"] == "throttled":
            ep["open"] = ev
        elif ev["kind"] == "backoff":
            ep["backoffs"] += 1
        elif ev["kind"] == "cleared":
            ep["cleared"] = ev
    if not episodes:
        return out
    keys = [f"{k}:{e}" for e in episodes for k in (KIND, CLEAR_KIND)]
    sent = {str(r[0]) for r in query_rows(
        conn, "SELECT lock_key FROM push_sent WHERE kind IN (%s, %s) AND lock_key = ANY(%s)",
        (KIND, CLEAR_KIND, keys), label="book_throttle_watch")}
    for episode, ep in episodes.items():
        ev, cleared = ep["open"], ep["cleared"]
        if ev is None:
            continue                   # its opening row is older than the window
        red_key, clear_key = f"{KIND}:{episode}", f"{CLEAR_KIND}:{episode}"
        if red_key not in sent:
            if not _answered_before(conn, ev["book"], ev["at"]):
                out["skipped"].append(episode)
                continue
            title, detail = red_message(ev, ep["backoffs"], cleared)
            if post_ops_alert(title, detail, post=post):
                _ledger(conn, red_key, KIND)
                if cleared is not None:
                    _ledger(conn, clear_key, CLEAR_KIND)
                out["alerted"].append(episode)
        elif cleared is not None and clear_key not in sent:
            title, detail = green_message(ev, cleared, ep["backoffs"])
            if post_ops_alert(title, detail, recovery=True, post=post):
                _ledger(conn, clear_key, CLEAR_KIND)
                out["cleared"].append(episode)
    return out


def run_book_throttle_watch(conn=None, now: datetime | None = None, post=None) -> dict:
    """One tick. Never raises; returns what it did."""
    now = now or datetime.now(timezone.utc)
    own = conn is None
    try:
        if own:
            from data.db import get_connection
            conn = get_connection()
        try:
            res = check(conn, now, post=post)
        finally:
            if own:
                try:
                    conn.close()
                except Exception:     # noqa: BLE001
                    pass
    except Exception as exc:          # noqa: BLE001
        logger.warning(f"book_throttle_watch could not run: {exc}")
        return {"alerted": [], "cleared": [], "skipped": [], "error": str(exc)}
    if res["alerted"] or res["cleared"]:
        logger.info(f"book_throttle_watch: {len(res['alerted'])} alerted, {len(res['cleared'])} cleared")
    return res


def post_test_alerts(post=None) -> dict:
    """The red and the green message, built by the same functions a real
    episode uses, on a made-up FanDuel 429, each titled TEST. mike, 2026-11-26:
    "Send a test alert to ops so I can see it". Writes no table, so nothing
    reads it as an episode; one POST each, no retry."""
    now = datetime.now(timezone.utc)
    ev = {"at": now, "host": "MAHome", "book": "fanduel", "sport": "NBA", "kind": "throttled",
          "reason": "rate_limited", "status": 429, "in_a_row": 1, "poll_s": 1.0,
          "episode": "test", "detail": ""}
    cleared = {"at": now + timedelta(seconds=40), "detail": "answered cleanly again after 40 s"}
    note = "\n\n*Test message: no book is throttling us. This is what the alert looks like.*"
    title, detail = red_message(ev, 1, None)
    red = post_ops_alert(f"TEST: {title}", detail + note, post=post)
    title, detail = green_message(ev, cleared, 1)
    green = post_ops_alert(f"TEST: {title}", detail + note, recovery=True, post=post)
    return {"red_posted": bool(red), "green_posted": bool(green)}


if __name__ == "__main__":  # pragma: no cover
    print(run_book_throttle_watch())
