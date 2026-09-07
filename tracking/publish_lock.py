"""One publisher at a time, across every process that can publish.

WHY THIS EXISTS (2026-09-06)

Every publisher in this repo has the same three steps, in this order:

    1. read   -- "which BETs have not been ledgered as sent?"
    2. send   -- POST the webhook / push the devices
    3. ledger -- INSERT the push_sent rows, ON CONFLICT DO NOTHING

The order is deliberate and must not change: nothing is ledgered unless the
send actually succeeded, so a down webhook leaves the signal eligible for the
next pass instead of silently consuming it (tracking/discord_notifier.py).

But the three steps are not ATOMIC, and since `signal_publisher` shipped there
is more than one process that runs them. `pollers` runs the pre-game line poller
every 30 seconds and publishes whatever tick wrote a BET; `worker` runs the
refresh pass, the scheduler's NFL card polls and the daily pipeline, and each of
those publishes too. Two of them inside the same window both read an empty
ledger for the same pick, both send, and the second INSERT is swallowed by
ON CONFLICT DO NOTHING. The ledger ends up correct and the CHANNEL ends up
wrong: one row, one message_id, two identical cards.

MEASURED. `NCAAF_2026-09-06_louisville_ole-miss:ncaaf_over_under` carries
exactly one `discord_signal` row -- sent_at 12:29:11.358 ET, message
1546195572803772550 -- and #ncaaf carried the "Ole Miss vs Louisville Under
55.5" card twice at 12:29 PM. Its `new_bet` row is stamped 12:29:11.106, a
quarter of a second earlier, so the push path was inside the same window.

WHAT THIS IS

A Postgres ADVISORY LOCK, which is held by a SESSION (a connection) and is
visible cluster-wide, so it serializes the read-send-ledger sequence across
`worker` and `pollers` alike -- something the ledger itself cannot do, because
the ledger only learns about a send after it has happened.

A run that cannot take the lock does NOT wait and does NOT send: it returns
having done nothing, because the process holding the lock is at that moment
publishing the very signals this run would have published. Nothing is lost --
and if that run dies mid-send, the un-ledgered signals are picked up by the next
pass, exactly as they are after any other failure.

CLAUDE.md 1b: this is shared, sport-agnostic and producer-agnostic on purpose.
The duplicate was visible in Discord because Discord renders a card; the push
path has the identical shape and gives a member the same alert twice, which is
worse and harder to see.

FAILS OPEN. A connection that cannot evaluate `pg_try_advisory_lock` (the test
doubles) is treated as "lock acquired" -- that is exactly today's behaviour, and
a publisher that refused to publish because it could not take a lock would be a
worse failure than the duplicate it is preventing.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Arbitrary but STABLE 32-bit keys. Each producer gets its own, so a slow
# Discord webhook cannot hold up the push path, and vice versa. Never reuse a
# key for something else: an advisory lock has no namespace beyond this number.
DISCORD_SIGNALS_LOCK = 812_090_601
DISCORD_LIVE_LOCK = 812_090_602
PUSH_SIGNALS_LOCK = 812_090_603


@contextmanager
def publish_lock(conn, key: int, label: str):
    """Yield True when this process owns `key` and should publish, else False.

    Always releases what it took, including on an exception, so a publisher that
    raises mid-send does not wedge every later pass until the pod restarts.
    """
    acquired = _try_acquire(conn, key, label)
    try:
        yield acquired
    finally:
        if acquired:
            _release(conn, key)


def _try_acquire(conn, key: int, label: str) -> bool:
    try:
        row = conn.execute("SELECT pg_try_advisory_lock(%s)", (key,)).fetchone()
    except Exception as exc:                                      # noqa: BLE001
        # Not a Postgres connection (the test doubles). See FAILS OPEN above.
        logger.debug(f"{label}: advisory lock unavailable ({exc}); "
                     f"publishing without it")
        return True
    got = bool(row and row[0])
    if not got:
        logger.info(f"{label}: another publisher holds the lock; "
                    f"leaving this batch to it")
    return got


def _release(conn, key: int) -> None:
    try:
        conn.execute("SELECT pg_advisory_unlock(%s)", (key,))
    except Exception:                                             # noqa: BLE001
        # Best effort: a session-level advisory lock is dropped when the
        # connection closes, and every caller closes its connection.
        pass
