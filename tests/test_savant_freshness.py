"""
Baseball Savant must be refreshed on a schedule, and its staleness must be visible.

WHY THIS EXISTS
---------------
Measured 2026-08-31. `player_savant_stats` held ONE row per player per season,
and for season 2026 it held 580 pitchers captured on 2026-05-13 and ZERO
batters. The ingestor was never wired into run_pipeline or the scheduler -- it
existed only as a manual script.

So for four months every live pitcher-prop score used a mid-May snapshot as
"current season", and every batter-prop score fell back to 2025 because 2026
batter rows did not exist. Nothing raised, nothing failed a check, and the
picks looked exactly like picks made on fresh data.

That is the failure mode this repo keeps meeting from a new angle: an absent
producer is indistinguishable from a quiet one. It needs a schedule AND a
check, because either alone would have left this invisible.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

_ROOT = Path(__file__).parent.parent
_SCHED = (_ROOT / "scheduler.py").read_text(encoding="utf-8")
_PIPE = (_ROOT / "run_pipeline.py").read_text(encoding="utf-8")


# ── it runs at all ───────────────────────────────────────────────────────────

def test_savant_is_a_pipeline_step():
    assert '"savant"' in _PIPE, "no savant step — it can only be run by hand"
    assert "run_savant_ingestor" in _PIPE, "the step must reach the ingestor"


def test_savant_has_a_schedule():
    ids = re.findall(r'^\s*id="([^"]+)"', _SCHED, re.M)
    assert "savant_refresh" in ids, (
        "the ingestor with no schedule is exactly how 2026 batter Savant was "
        "never pulled at all")


def test_the_savant_job_belongs_to_the_pipeline_service():
    """Not the poller service, and not both — a duplicated job would double
    the CSV pulls and could interleave two writers on the same rows."""
    import importlib
    import scheduler
    importlib.reload(scheduler)
    assert "savant_refresh" in scheduler._PIPELINE_JOBS


# ── staleness is visible ─────────────────────────────────────────────────────

def test_rows_are_stamped_with_a_capture_date():
    """A season-to-date aggregate is meaningless without the date it was taken:
    a May capture and a September one are otherwise identical rows."""
    from data.ingestors import baseball_savant_ingestor as ing
    src = inspect.getsource(ing._upsert_savant_stats)
    assert "as_of_date" in src
    assert "setdefault" in src, (
        "stamp centrally, or a new caller silently reintroduces an undateable row")


def test_the_stamp_defaults_rather_than_being_required_at_call_sites():
    from data.ingestors import baseball_savant_ingestor as ing

    class _Conn:
        def executemany(self, sql, rows):
            self.rows = rows

    conn = _Conn()
    ing._upsert_savant_stats(conn, [{"player_id": "1", "season": 2026}])
    assert conn.rows[0]["as_of_date"], "row went in with no capture date"


def test_the_insert_persists_the_stamp():
    """Stamping the dict is useless if the SQL never writes the column."""
    from data.ingestors import baseball_savant_ingestor as ing
    src = inspect.getsource(ing._upsert_savant_stats)
    assert "%(as_of_date)s" in src, "as_of_date is stamped but never inserted"
    assert "as_of_date   = EXCLUDED.as_of_date" in src, (
        "an upsert that does not refresh as_of_date leaves the row looking as "
        "old as its first capture forever")


def test_the_column_is_migrated():
    setup = (_ROOT / "data/db_setup.py").read_text(encoding="utf-8")
    assert '("player_savant_stats", "as_of_date", "TEXT")' in setup


# ── the health check ─────────────────────────────────────────────────────────

def test_health_checks_savant_freshness_and_both_player_types():
    src = (_ROOT / "tracking/system_health.py").read_text(encoding="utf-8")
    assert "savant_freshness" in src, "staleness must be reported, not inferred"
    assert "savant_player_types" in src, (
        "a season with pitchers and no batters reads as populated to any check "
        "that only asks for the newest row — which is exactly what 2026 was")
