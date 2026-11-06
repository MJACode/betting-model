"""Refresh the planner's row counts for the BYOM tables after a write.

2026-11-05, measured in production: the NBA points preview took 6.0s for
the current season (anon cuts off at 3s). 11,075 byom_prop_facts rows had
been written since the last automatic analyze, and the planner still
counted 1 row for NBA 2027 and 176 games (there were 1,203). On that
count it chose a nested loop that discarded 19,135,872 rows.

Postgres re-analyzes a table only after about 10% of it changes. That is
about 49,000 rows of byom_prop_facts, so a daily refresh of one season
never reaches it, and a new season always looks empty. So every builder
that writes these tables analyzes them after it commits.

ANALYZE reads a sample. It does not lock out reads or writes, and it does
not change any row. A failure is logged and skipped: a stale count makes
a preview slow, never wrong.
"""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)

TABLES = ("byom_game_facts", "byom_prop_facts", "byom_official_legs")


def analyze_tables(conn) -> list[str]:
    """ANALYZE each BYOM table. Returns the tables analyzed."""
    done: list[str] = []
    for table in TABLES:
        try:
            # data.db's connection has execute, not cursor. ANALYZE may
            # run inside a transaction (VACUUM may not).
            conn.execute(f"ANALYZE public.{table}")
            conn.commit()
            done.append(table)
        except Exception as exc:  # noqa: BLE001 - slow, never wrong
            try:
                conn.rollback()
            except Exception:  # noqa: BLE001
                pass
            log.warning("ANALYZE %s failed: %s", table, exc)
    return done
