"""NO DATA IS EVER DELETED (CLAUDE.md section 1b, mike 2026-11-14).

mike: *"We should not be deleting any data, that needs to be a hard rule that
only mike can override."* Measured the same day (docs/data_archive.md): the odds
prune deleted 2.50M `odds` rows and 6.27M `player_prop_odds` rows in the seven
morning runs of 11-08 to 11-14, `api_call_log` lost every row older than 7 days,
and `app_timings` and `player_news` had their own retention deletes.

Every one of those jobs now asks `config.data_deletion_approved(job)` first and
deletes nothing when the answer is no. These tests run each job against a
connection that RECORDS what it is sent, then assert no DELETE reached it. A
recorder, not one that raises: three of the four jobs swallow statement errors,
so a raising fake would let the delete "fail" quietly and the test pass. Each
test was run against the code before the gate and failed.
"""
from __future__ import annotations

from pathlib import Path

import config

ROOT = Path(__file__).resolve().parent.parent


class _Cursor:
    rowcount = 0

    def fetchall(self):
        return []

    def fetchone(self):
        return None


class _Recorder:
    """Every statement sent, in order. Nothing is executed."""

    def __init__(self):
        self.sql: list[str] = []

    def execute(self, sql, params=None):
        self.sql.append(str(sql))
        return _Cursor()

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def deletes(self) -> list[str]:
        return [s for s in self.sql if "DELETE" in s.upper()]


def test_no_deletion_is_approved():
    """Only mike opens an entry, in chat, with Updated-By: mike on the commit."""
    assert config.DATA_DELETION_APPROVALS == {}, (
        "config.DATA_DELETION_APPROVALS has an entry. It may only be added on "
        "mike's word in chat (CLAUDE.md section 1b); update this test in the "
        "same commit, naming who approved it.")


def test_the_rule_is_in_claude_md_itself():
    """A SQL DELETE run by hand opens no file, so the rule cannot be path-scoped."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "NO DATA IS EVER DELETED" in text


def test_the_odds_prune_deletes_nothing_without_approval(monkeypatch):
    import data.prune_odds as po

    def no_connection():
        raise AssertionError("the odds prune opened a database connection")

    monkeypatch.setattr(po, "get_connection", no_connection)
    summary = po.run_prune_odds(run_date="2026-11-15", keep_days=2)
    assert summary["refused"] is True
    assert summary["tables"] == []


def test_the_odds_prune_still_refuses_a_zero_day_window():
    """The old guard still comes first: a 0-day window would blank the board."""
    import pytest
    import data.prune_odds as po
    with pytest.raises(ValueError):
        po.run_prune_odds(run_date="2026-11-15", keep_days=0)


def test_the_api_call_log_is_rolled_up_and_not_deleted():
    from monitoring import store
    conn = _Recorder()
    assert store.prune(conn) == 0
    assert any("INSERT INTO api_call_daily" in s for s in conn.sql), \
        "the daily totals must still be folded"
    assert conn.deletes() == []


def test_app_timings_are_not_deleted():
    from data.app_timings_retention import prune_app_timings
    conn = _Recorder()
    assert prune_app_timings(conn) == 0
    assert conn.deletes() == []


def test_the_notification_inbox_is_not_deleted():
    from tracking.notification_inbox import prune_notification_inbox
    conn = _Recorder()
    assert prune_notification_inbox(conn) == 0
    assert conn.deletes() == []


def test_player_news_is_not_deleted():
    from data.ingestors import player_news_ingestor as pni
    conn = _Recorder()
    assert pni.prune_old(conn, retention_days=21) == 0
    assert conn.deletes() == []


def test_an_approval_names_the_job_it_opens(monkeypatch):
    """An entry opens its own job and no other."""
    from data.app_timings_retention import prune_app_timings
    monkeypatch.setitem(config.DATA_DELETION_APPROVALS, "player_news", "test")
    assert config.data_deletion_approved("player_news")
    assert not config.data_deletion_approved("app_timings")
    conn = _Recorder()
    assert prune_app_timings(conn) == 0
    assert conn.deletes() == []
