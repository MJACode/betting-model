"""The fill measurement of the first-post moneyline model
(`ncaab_moneyline_first_post`): was its bet quote still on the board, at the
same number, when the NCAAB odds capture next polled?

WHY. The research behind the model saw the board only every 30 minutes, so it
could only bound how long a first post stayed up: at least 69% of its
2021-2025 bet quotes, and only 34% of its 2025-26 ones, were certainly still
posted five minutes later. Whether the bets can be filled is the first thing
to measure live. The capture (scripts/ncaab_odds_capture.py) is the only job
that sees the whole board every five minutes, including the quotes that did
not move, so it records this, once per bet, on its first poll after the bet.

WHAT IS WRITTEN, on the bet's row in ncaab_moneyline_first_post_decisions
(scripts/ncaab_moneyline_first_post_card.py):
  fill_status      'unchanged'        the book still listed that moneyline at
                                      the bet's two prices
                   'changed'          listed at another price (fill_p1/fill_p2)
                   'book_not_listed'  the game was on the board, that book's
                                      moneyline was not
                   'game_not_listed'  the game was not on the board (it had
                                      started, or did not resolve)
  fill_checked_at  the poll's clock (UTC)

Kept free of pandas: it runs inside every capture tick. It never raises into
the capture (the capture wraps the call), and a missing ledger table is no
work.
"""
from __future__ import annotations

from datetime import datetime

from data.ingestors.pregame_line_poller import _num

DECISIONS_TABLE = "ncaab_moneyline_first_post_decisions"


def _ledger_exists(conn) -> bool:
    return bool(conn.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' "
        "AND table_name = %s", (DECISIONS_TABLE,)).fetchone())


def _same(a, b) -> bool:
    x, y = _num(a), _num(b)
    try:
        return abs(float(x) - float(y)) < 1e-9
    except (TypeError, ValueError):
        return x == y


def fill_status(row: dict | None, game_listed: bool, p1, p2) -> tuple[str, float | None, float | None]:
    """(status, the listed home price, the listed away price) for one bet,
    from the poll's parsed row for its (game, h2h, book), None when absent."""
    if row is None:
        return ("book_not_listed" if game_listed else "game_not_listed"), None, None
    h, a = row.get("home_price"), row.get("away_price")
    same = _same(h, p1) and _same(a, p2)
    try:
        h, a = float(_num(h)), float(_num(a))
    except (TypeError, ValueError):
        h = a = None
    return ("unchanged" if same else "changed"), h, a


def record_fill(conn, odds_rows: list[dict], polled_at: datetime) -> int:
    """Write the fill status of every first-post bet decided before this poll
    and not yet checked. odds_rows: every row the poll parsed (changed or
    not). -> how many bets were checked. Commits its own write."""
    if not _ledger_exists(conn):
        return 0
    pend = conn.execute(f"""
        SELECT game_id, bookmaker, p1, p2 FROM {DECISIONS_TABLE}
        WHERE status = 'bets' AND n_bets = 1 AND fill_status IS NULL AND decided_at < %s
    """, (polled_at,)).fetchall()
    if not pend:
        return 0
    feed = {(r.get("game_id"), r.get("bookmaker")): r for r in odds_rows if r.get("market") == "h2h"}
    games = {r.get("game_id") for r in odds_rows}
    n = 0
    for gid, book, p1, p2 in pend:
        status, h, a = fill_status(feed.get((gid, book)), gid in games, p1, p2)
        got = conn.execute(f"""
            UPDATE {DECISIONS_TABLE} SET fill_status = %s, fill_checked_at = %s,
                   fill_p1 = %s, fill_p2 = %s
            WHERE game_id = %s AND bookmaker = %s AND fill_status IS NULL RETURNING game_id
        """, (status, polled_at.isoformat(), h, a, gid, book)).fetchone()
        n += bool(got)
    conn.commit()
    return n
