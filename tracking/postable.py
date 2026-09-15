"""What counts as a currently postable pre-game BET.

Discord, push, and the `signal_delivery` health check must agree: a pick the
producer will not announce is not a delivery failure, and a pick the producer
would announce must alarm if the ledger is empty past grace.

`still_pre_game` is the Python half of the first-pitch guard (the SQL half is
`g.commence_time::timestamptz > NOW()` in the producers). Health checks run
against sqlite in tests, so they cannot use that cast; they call this instead.
"""
from __future__ import annotations

from datetime import datetime, timezone


def still_pre_game(commence, now=None) -> bool:
    """True when this signal's game has NOT started yet.

    THE DELIVERY HALF OF THE FIRST-PITCH GUARD (2026-09-03). Capture now refuses
    to lock a pick written after its own first pitch, but a legitimately
    pre-game pick can still reach the poster after the game has started -- the
    2026-08-31 MIN/DET signal was created 38 seconds before first pitch and
    captured four minutes after it. Posting that sends a member to a live game
    at a pre-game number.

    Parsed, never string-compared: these columns are TEXT in mixed shapes ('Z'
    vs '-04:00' vs naive) and a string comparison silently keeps the wrong rows
    (§7). Done in Python rather than SQL because the health check (and the
    producer tests) run against sqlite, where a ::timestamptz cast is a syntax
    error.

    FAILS OPEN. A missing or unparseable commence_time counts as pre-game, so a
    feed that stops populating the column cannot silently empty the board --
    the same direction every other guard in this repo fails.
    """
    if not commence:
        return True
    try:
        raw = str(commence).strip().replace(" ", "T", 1)
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        ts = datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts > (now or datetime.now(timezone.utc))
