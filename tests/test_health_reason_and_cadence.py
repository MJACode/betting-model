"""Every health row says WHY it is in its state, and how fresh it expects to be.

mike, 2026-09-08: "add a column for refresh frequency and status reason, for
exmaple if skipped, the reason wjyu".

`detail` was already the reason, but it is a SENTENCE, and every table that
renders it clamps it — so the answer to "why is this one skipped?" sat three
lines down inside a truncated cell. `reason` is that answer as one word.

`cadence` is DERIVED from each check's own argument (its max_age_hours, or the
gap between its min_date and the run date) rather than declared in a side table.
A hand-maintained list of frequencies drifts from the bar actually enforced the
first time someone tunes a threshold — and then the column lies, which is worse
than not having it.
"""
import sqlite3

import tracking.system_health as sh


class Report(sh.HealthReport):
    """A report with a fixed run_date, so cadence maths is deterministic."""

    def __init__(self):
        super().__init__("2026-09-08")


def _one(r):
    assert len(r.results) == 1, r.results
    return r.results[0]


# ── cadence is derived, not declared ─────────────────────────────────────────

def test_cadence_reads_a_daily_bar_off_the_dates():
    assert sh._cadence_from_dates("2026-09-07", "2026-09-08") == "daily"


def test_cadence_reads_a_same_day_bar():
    assert sh._cadence_from_dates("2026-09-08", "2026-09-08") == "same day"


def test_cadence_reads_a_multi_day_window():
    assert sh._cadence_from_dates("2026-09-05", "2026-09-08") == "every 3 days"


def test_cadence_survives_a_missing_or_unparseable_date():
    """Fail open to something true rather than to a wrong number."""
    assert sh._cadence_from_dates("", "2026-09-08") == "each run"
    assert sh._cadence_from_dates("not-a-date", "2026-09-08") == "each run"


def test_a_ts_check_reports_its_own_max_age():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE odds (snapshot_at TEXT)")
    r = Report()
    r.ts_check(c, "odds_dk_lines", "CRIT", "odds", "snapshot_at", 6,
               gate_ok=False, gate_note="no games")
    assert _one(r)["cadence"] == "every 6h"


def test_a_24h_ts_check_reads_as_daily():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE odds (snapshot_at TEXT)")
    r = Report()
    r.ts_check(c, "x", "WARN", "odds", "snapshot_at", 24, gate_ok=False)
    assert _one(r)["cadence"] == "daily"


# ── reason is the one-word answer ────────────────────────────────────────────

def test_a_skipped_check_says_the_gate_was_shut():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE umpires (game_date TEXT)")
    r = Report()
    r.date_check(c, "umpires", "WARN", "umpires", "game_date", "2026-09-07",
                 gate_ok=False, gate_note="no MLB finals yesterday")
    res = _one(r)
    assert res["status"] == sh.SKIPPED
    assert res["reason"] == sh.REASON_GATE_SHUT
    assert res["detail"] == "no MLB finals yesterday"       # the long form survives


def test_stale_data_and_an_empty_table_are_different_reasons():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t (d TEXT)")
    r = Report()
    r.date_check(c, "empty", "WARN", "t", "d", "2026-09-07")
    assert _one(r)["reason"] == sh.REASON_NO_ROWS

    c.execute("INSERT INTO t VALUES ('2026-09-01')")
    r2 = Report()
    r2.date_check(c, "stale", "WARN", "t", "d", "2026-09-07")
    assert _one(r2)["reason"] == sh.REASON_STALE_DATA


def test_a_broken_query_is_its_own_reason():
    c = sqlite3.connect(":memory:")
    r = Report()
    r.date_check(c, "boom", "WARN", "no_such_table", "d", "2026-09-07")
    res = _one(r)
    assert res["status"] == sh.ERROR
    assert res["reason"] == sh.REASON_QUERY_ERROR


def test_a_passing_check_says_fresh():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE t (d TEXT)")
    c.execute("INSERT INTO t VALUES ('2026-09-08')")
    r = Report()
    r.date_check(c, "ok", "WARN", "t", "d", "2026-09-07")
    assert _one(r)["reason"] == sh.REASON_FRESH


def test_a_stuck_gate_is_not_reported_as_stale_data():
    """Nothing was read, so the DATA is not the subject — the gate is.

    Calling it "data behind" would send whoever reads the column to the feed,
    which is the one place the answer is not.
    """
    results = [{"check_name": "golf_odds", "status": sh.SKIPPED, "severity": "WARN",
                "detail": "no tournament", "latest_seen": None,
                "reason": sh.REASON_GATE_SHUT, "cadence": "daily"}]
    sh._apply_skip_budgets(results, {"golf_odds": 400})
    assert results[0]["status"] == sh.STALE
    assert results[0]["reason"] == sh.REASON_GATE_STUCK


# ── every row carries both, always ───────────────────────────────────────────

def test_a_bare_add_still_fills_both_columns():
    """A check that passes neither must still render a complete row — an empty
    cell reads as "nobody knows", which is what this change is fixing."""
    r = Report()
    r.add("hand_written", sh.STALE, "CRIT", "something is wrong")
    res = _one(r)
    assert res["reason"] == sh.REASON_STALE_DATA
    assert res["cadence"] == "each run"


def test_the_persist_writes_both_columns():
    import io
    text = io.open(sh.__file__, encoding="utf-8").read()
    stmt = text[text.index("INSERT INTO system_health_checks"):]
    stmt = stmt[:stmt.index('""",')]
    for col in ("reason", "cadence"):
        assert col in stmt, f"{col} is computed but never persisted"
        assert f"{col} = EXCLUDED.{col}" in stmt, f"{col} is inserted but never updated"


def test_the_column_ddl_is_gated():
    """ALTER TABLE fires pgrst_ddl_watch and 503s the app; this runs every pass."""
    import io
    text = io.open(sh.__file__, encoding="utf-8").read()
    body = text[text.index("def _ensure_reason_columns"):]
    body = body[:body.index("\ndef ")]
    # Drop the docstring first: it explains WHY the ALTER is dangerous, so it
    # names "ALTER TABLE" several lines above the guard. Ordering the raw text
    # would have compared against prose.
    body = body[body.index('"""', body.index('"""') + 3) + 3:]
    # The CALL, not the name: the `from data.ddl_guard import schema_is_current`
    # line survives even when the guard is deleted, so asserting on the bare
    # symbol passed while the DDL ran unguarded. A guard that its own import
    # can satisfy is not a guard.
    assert "schema_is_current(conn" in body, "the DDL is ungated"
    assert body.index("schema_is_current(conn") < body.index("ALTER TABLE"), (
        "the guard must be consulted before any ALTER runs"
    )
