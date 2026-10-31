"""A recap a later grade left short is noticed. It is never posted again.

2026-09-10. The 6am run posted the 2026-09-09 recap MLB-only at 06:02; the three
NFL props settled at 07:24. From that day every settle pass re-posted any such
recap, labelled "restated", until mike ended it on 2026-10-30. The behaviour now
is pinned in tests/test_record_never_restated.py. This file keeps the scan, which
only tells ops, and the nflverse fetch retry that shipped alongside it.

A LATE GRADE IS THE SIGNAL, NOT A COUNT DIFFERENCE: every daily snapshot from 09-01
to 09-08 disagrees with today's count because the recap query applies the CURRENT
cuts and those moved.
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402

ROOT = Path(__file__).parent.parent
PUB = datetime(2026, 9, 10, 10, 2, 22, tzinfo=timezone.utc)


class _Conn:
    """Answers the snapshot scan with `snaps` and the late-settlement query
    with `late_by_date`; records every SQL it saw."""

    def __init__(self, snaps, late_by_date):
        self.snaps, self.late_by_date, self.sql = snaps, late_by_date, []

    def execute(self, sql, params=()):
        self.sql.append((sql, params))
        conn = self

        class _R:
            def fetchall(_):
                if "FROM results_snapshots" in sql:
                    return conn.snaps
                if "p.settled_at > %s" in sql:
                    return [("NFL",)] * conn.late_by_date.get(params[0], 0)
                return []

            def fetchone(_):
                return None
        return _R()

    def close(self):
        pass


# ── the scan ─────────────────────────────────────────────────────────────────

def test_a_recap_with_a_late_grade_is_short():
    conn = _Conn([("2026-09-09", PUB, 7)], {"2026-09-09": 3})
    due = dn.recaps_gone_short(conn, through="2026-09-10")
    assert due == [{"game_date": "2026-09-09", "published_at": PUB,
                    "settled": 7, "late": 3}]


def test_a_recap_whose_count_merely_drifted_is_not_short():
    conn = _Conn([("2026-09-01", PUB, 56)], {"2026-09-01": 0})
    assert dn.recaps_gone_short(conn, through="2026-09-10") == []


def test_the_scan_is_bounded_to_finished_days_and_the_lookback():
    conn = _Conn([], {})
    dn.recaps_gone_short(conn, through="2026-09-20")
    sql, params = conn.sql[0]
    assert "game_date < %s" in sql and "game_date >= %s" in sql
    assert params == ("2026-09-20", "2026-09-13")


def test_the_late_query_is_the_recap_universe_plus_settled_after():
    """Over the SAME universe the recap counts, or a pick outside the cut could
    raise an alert for a record it never appears in."""
    conn = _Conn([("2026-09-09", PUB, 7)], {"2026-09-09": 1})
    dn.recaps_gone_short(conn, through="2026-09-10")
    late_sql, late_params = conn.sql[1]
    assert late_sql.startswith(dn._SETTLED_SQL.format(window="= %s"))
    assert late_sql.rstrip().endswith("AND p.settled_at > %s")
    assert late_params == ("2026-09-09", PUB)


def test_the_check_after_noon_does_not_touch_the_database(monkeypatch):
    opened = []
    monkeypatch.setattr(dn, "get_connection", lambda *a, **k: opened.append(1))
    evening = datetime(2026, 10, 21, 21, 56, tzinfo=dn.ET)
    assert dn.flag_recaps_gone_short(now=evening) == 0
    assert opened == []


def test_the_short_recap_check_never_fails_settle():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    fn = src[src.index("def step_settle("):src.index("\ndef ", src.index("def step_settle(") + 10)]
    tail = fn[fn.index("flag_recaps_gone_short"):]
    assert "except Exception" in tail and "return True" in tail


# ── the nflverse fetch retry ─────────────────────────────────────────────────

def _resp(status, text="csv"):
    class R:
        status_code = status

        def raise_for_status(self):
            if status >= 400:
                raise RuntimeError(f"HTTP {status}")
        text_ = text
    r = R(); r.text = text
    return r


def test_a_transient_403_is_retried_and_the_second_answer_is_used(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    answers = iter([_resp(403), _resp(200, "ok")])
    slept = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: next(answers))
    monkeypatch.setattr(ing.time, "sleep", slept.append)
    assert ing._fetch_season_csv(2026) == "ok"
    assert slept == [5]


def test_a_404_is_an_answer_not_a_retry(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    calls = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: calls.append(1) or _resp(404))
    monkeypatch.setattr(ing.time, "sleep", lambda s: pytest.fail("slept on a 404"))
    assert ing._fetch_season_csv(2026) is None
    assert calls == [1]


def test_a_persistent_403_still_raises_after_the_last_attempt(monkeypatch):
    from data.ingestors import nfl_player_stats_ingestor as ing
    calls = []
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: calls.append(1) or _resp(403))
    monkeypatch.setattr(ing.time, "sleep", lambda s: None)
    with pytest.raises(RuntimeError):
        ing._fetch_season_csv(2026)
    assert len(calls) == ing._FETCH_ATTEMPTS
