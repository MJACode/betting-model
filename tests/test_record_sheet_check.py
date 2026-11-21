"""The record-vs-sheet check (tracking/record_sheet_check.py).

Matt, 2026-11-21: the "SignalBase Record History" sheet is the reference for
the published record, and the record is checked against it every hour. The
fixtures here carry the populations the two can disagree about: a pick with a
different stake, a pick one side lacks, a pick graded minutes ago, and an
OPEN row the sheet counts in no total.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from tracking import record_sheet_check as rsc

ET = rsc.ET
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=ET)

CSV = (
    "status,date,sport,pick,book,posted_odds,closing_odds,beat_close,result,units,"
    "running_units,posted_at (ET),game_time (ET),in_play,pick_id,risked,week_start,month\n"
    "OPEN,2026-11-23,NFL,CIN @ WAS Under 54,Caesars,-109,,,,,,,,,4632351,,2026-11-23,Nov 2026\n"
    "W,2026-11-18,NCAAB,Utah State 1H -15.0,FanDuel,-110,,,WIN,+1.00u,+1.00u,,,,4599384,1.10u,,\n"
    "L,2026-11-20,NCAAB,Eastern Illinois 1H +28.5,FanDuel,-125,,,LOSS,-1.25u,-0.25u,,,,4660093,1.25u,,\n"
    "W,2026-09-05,UFC,Mario Pinto vs Ryan Spann Under 1.5,DK,-130,,,WIN,+1.00u,+0.75u,,,,1438528,1.30u,,\n"
)


def _rec(result, units, date="2026-11-18", settled=NOW - timedelta(days=1), pick="x"):
    return {"date": date, "sport": "NCAAB", "pick": pick, "result": result,
            "units": units, "settled_at": settled}


def test_parse_keeps_graded_rows_only_and_reads_units():
    sheet = rsc.parse_sheet_csv(CSV)
    assert set(sheet) == {4599384, 4660093, 1438528}     # the OPEN row is no total
    assert sheet[4660093]["units"] == -1.25
    assert sheet[4599384]["result"] == "WIN"


def test_parse_refuses_a_page_that_is_not_the_picks_tab():
    with pytest.raises(rsc.SheetUnreadable):
        rsc.parse_sheet_csv("<html>Sign in</html>\n")


def test_a_two_unit_stake_is_a_difference():
    """The 2026-11-21 gap: the record counted 4599384 at 2u, the sheet at 1u."""
    sheet = rsc.parse_sheet_csv(CSV)
    record = {4599384: _rec("WIN", 2.00), 4660093: _rec("LOSS", -1.25, "2026-11-20"),
              1438528: _rec("WIN", 1.00, "2026-09-05")}
    found = rsc.compare_picks(record, sheet, NOW)
    assert [(f["kind"], f["pick_id"]) for f in found] == [("differs", 4599384)]


def test_agreeing_record_has_no_findings():
    sheet = rsc.parse_sheet_csv(CSV)
    record = {4599384: _rec("WIN", 1.00), 4660093: _rec("LOSS", -1.25, "2026-11-20"),
              1438528: _rec("WIN", 1.00, "2026-09-05")}
    assert rsc.compare_picks(record, sheet, NOW) == []


def test_a_struck_pick_on_the_sheet_is_reported():
    """The other 2026-11-21 gap: the sheet counted the UFC win, the record did not."""
    sheet = rsc.parse_sheet_csv(CSV)
    record = {4599384: _rec("WIN", 1.00), 4660093: _rec("LOSS", -1.25, "2026-11-20")}
    found = rsc.compare_picks(record, sheet, NOW)
    assert [(f["kind"], f["pick_id"]) for f in found] == [("not_in_record", 1438528)]


def test_a_pick_graded_minutes_ago_is_not_yet_a_gap_but_an_old_one_is():
    sheet = rsc.parse_sheet_csv(CSV)
    base = {4599384: _rec("WIN", 1.00), 4660093: _rec("LOSS", -1.25, "2026-11-20"),
            1438528: _rec("WIN", 1.00, "2026-09-05")}
    fresh = {**base, 999: _rec("WIN", 1.00, "2026-11-21", NOW - timedelta(minutes=20))}
    assert rsc.compare_picks(fresh, sheet, NOW) == []
    stale = {**base, 999: _rec("WIN", 1.00, "2026-11-20", NOW - timedelta(hours=5))}
    assert [f["kind"] for f in rsc.compare_picks(stale, sheet, NOW)] == ["not_on_sheet"]


class _Conn:
    """Only what compare_posts reads: the last all-time line, then the daily
    lines from DAILY_POST_CHECK_FROM on."""

    def __init__(self, all_time, daily):
        self._all, self._daily = all_time, daily

    def execute(self, sql, params=()):
        rows = [self._all] if "all_time" in sql else self._daily

        class _R:
            def fetchone(_):
                return rows[0] if rows else None

            def fetchall(_):
                return rows
        return _R()


def test_discord_lines_are_checked_against_the_sheet():
    sheet = rsc.parse_sheet_csv(CSV)
    # all-time through 11-20: the sheet holds 2-1, +0.75u
    ok = _Conn(("2026-11-20", 2, 1, 0, 0.75), [("2026-11-21", 0, 0, 0, 0.0)])
    assert rsc.compare_posts(ok, sheet) == []
    off = _Conn(("2026-11-20", 1, 1, 0, -0.25), [("2026-11-21", 1, 0, 0, 1.0)])
    kinds = sorted(f["kind"] for f in rsc.compare_posts(off, sheet))
    assert kinds == ["all_time", "daily"]


def test_the_check_reads_the_recaps_own_predicate():
    """The record side is the Discord recap's query, not a copy of it."""
    from tracking.discord_notifier import _SETTLED_SQL
    sql = rsc._record_sql()
    tail = _SETTLED_SQL.partition("FROM picks p")[2].format(window=">= %s")
    assert sql.endswith(tail)
    assert "p.pick_id" in sql


def test_a_sign_in_page_is_unreadable_not_an_empty_sheet():
    class _Resp:
        status_code = 200
        headers = {"content-type": "text/html; charset=utf-8"}
        content = b"<html>sign in</html>"
    with pytest.raises(rsc.SheetUnreadable):
        rsc.fetch_sheet(lambda url, timeout: _Resp())
