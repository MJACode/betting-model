"""The published stake, once.

Discord #results and the Record tab both call the SQL functions in
``data/migrations/published_record_units_2026_10_16.sql``. The stake is
``stake_for``: 1 unit to win at ``COALESCE(decision_odds, dk_odds)``, risk
capped at 3, or the pick's own ``stake_units`` to win (1 to 3,
``pick_stake_units_2026_11_06.sql``). A missing price is the bare stake, not a
made-up −110.

``stake_for`` remains the Python twin for a short test tuple. The migration's
stake body is pinned equal to it, and the live recap does not recompute: it
adds the two columns those functions return.
"""
from __future__ import annotations

from tracking.discord_notifier import stake_for

STAKE_FN = "published_pick_stake"
PROFIT_FN = "published_pick_unit_profit"
RISKED_FN = "published_pick_unit_risked"


def unit_profit(price, result, stake_units=None) -> float:
    """Units won or lost. A push is 0. Same pair as the SQL profit function.
    `stake_units` is the pick's own stake (picks.stake_units); None is 1u."""
    stake = stake_for(None, price, stake_units)
    if result == "WIN":
        return stake.win
    if result == "LOSS":
        return -stake.risk
    return 0.0


def unit_risked(price, result, stake_units=None) -> float:
    """Units laid on a graded win or loss. A push, a void, and an ungraded
    pick laid nothing. Same pair as the SQL risked function."""
    if result not in ("WIN", "LOSS"):
        return 0.0
    return stake_for(None, price, stake_units).risk


def install_sqlite(db) -> None:
    """Register the two scalar functions so a SQLite recap query can run.

    The bodies are the Python twins. The migration's SQL body is what
    production executes; ``tests/test_record_units_agree.py`` pins that body
    to ``stake_for``.
    """
    db.create_function(PROFIT_FN, 2, unit_profit)
    db.create_function(RISKED_FN, 2, unit_risked)
    # The three-argument pair (pick_stake_units_2026_11_06.sql): the pick's own
    # stake_units as the third argument.
    db.create_function(PROFIT_FN, 3, unit_profit)
    db.create_function(RISKED_FN, 3, unit_risked)
