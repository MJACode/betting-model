"""api_call_daily — the rollup that makes "calls per month" possible at all.

api_call_log is pruned to API_LOG_RETENTION_DAYS (7). Before this rollup existed
the rows were simply deleted, so a monthly total was not merely missing from the
dashboard — it was unobtainable, and would have stayed unobtainable however long
anyone waited. These tests pin the two properties that make the fold trustworthy:
it happens BEFORE the delete, and re-running it cannot destroy a day whose source
rows are already gone.
"""

from __future__ import annotations

import inspect
import re

from monitoring import store


def test_prune_rolls_up_before_it_deletes():
    """Order is the whole thing. Deleting first would throw away the only copy,
    and the failure would be silent and permanent — nothing else in the system
    retains per-source API call counts."""
    src = inspect.getsource(store.prune)
    roll = src.index("roll_up(conn)")
    delete = src.index("DELETE FROM api_call_log")
    assert roll < delete, (
        "prune() deletes before rolling up, so the rows are gone before they "
        "are counted:\n" + src)


def test_the_rollup_upserts_and_never_zeroes_a_pruned_day():
    """The aggregate reads whatever api_call_log still holds. A day already
    pruned produces no GROUP BY row, so ON CONFLICT never fires for it and its
    stored total survives.

    The failure this prevents: a rollup written as DELETE-then-INSERT for a date
    range, or one that LEFT JOINs a calendar, would recompute a pruned day as
    zero and quietly erase months of history on the next run.
    """
    sql = store.ROLLUP_SQL.upper()
    assert "ON CONFLICT" in sql and "DO UPDATE" in sql, store.ROLLUP_SQL
    assert "DELETE" not in sql, (
        "the rollup deletes — a pruned day would be erased rather than kept")
    # It must aggregate only what is present, with no outer join to a date series
    assert "GENERATE_SERIES" not in sql, (
        "the rollup builds a calendar; a pruned day would be recomputed as zero")
    assert "LEFT JOIN" not in sql, store.ROLLUP_SQL


def test_the_rollup_groups_by_eastern_day_not_utc():
    """Every other date in this project is an ET game_date. A chart that groups
    API calls by UTC day lines up wrong against them by a few hours at the
    boundary, which is the kind of off-by-a-bit nobody notices until a number is
    questioned."""
    assert "America/New_York" in store.ROLLUP_SQL, store.ROLLUP_SQL


def test_the_rollup_survives_a_failure_without_blocking_the_prune():
    """roll_up swallows and returns 0. A broken rollup must not wedge the prune,
    or a failed fold would let api_call_log grow without bound."""
    src = inspect.getsource(store.roll_up)
    assert "except Exception" in src and "return 0" in src, src
    assert "rollback" in src, "a failed rollup must roll its transaction back"


def test_the_daily_table_is_created_and_locked_down():
    """It is created on demand by the writer every HTTP call goes through, so it
    has the same recurrence shape as every other worker-only table: a one-off
    revoke would be undone by the next run against a fresh database."""
    from data.anon_readable import WORKER_ONLY_TABLES

    assert "api_call_daily" in WORKER_ONLY_TABLES
    src = inspect.getsource(store)
    assert 'lock_down(conn, "api_call_daily")' in src, (
        "api_call_daily is created without being locked down")


def test_the_schema_guard_probes_both_tables():
    """ensure_table short-circuits on the guard. Probing only api_call_log would
    return True on a database that has never had the rollup table, and the
    rollup would then fail forever on a missing relation — the same shape as the
    job_queue guard that skipped its own lock-down."""
    src = inspect.getsource(store.ensure_table)
    probes = re.findall(r'schema_is_current\(\s*\n?\s*conn,\s*"([a-z_]+)"', src)
    assert set(probes) == {"api_call_log", "api_call_daily"}, probes


def test_the_daily_table_keys_on_day_api_and_source():
    """(day, api, source) is the grain the dashboard charts. A coarser key would
    lose the per-source split the question asks for."""
    ddl = store.DAILY_DDL.upper()
    assert "PRIMARY KEY (DAY, API, SOURCE)" in ddl.replace("\n", " "), store.DAILY_DDL
