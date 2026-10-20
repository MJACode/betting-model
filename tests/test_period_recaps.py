"""Weekly and monthly results recaps, on the daily recap's path.

The daily tweet and the daily Discord embed stay as they are. A week is the
prior Monday through Sunday and opens the following Monday at 7:30am ET. A
month is the previous calendar month and opens on the first Monday of the
new month at that same minute. Both read the settled-pick query the daily
recap reads, and both are ledgered so a retry does not post twice.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

ET = ZoneInfo("America/New_York")


def _at(text: str) -> datetime:
    return datetime.fromisoformat(text).replace(tzinfo=ET)


def test_monday_before_730_has_not_opened_the_new_week():
    # 2026-10-19 is a Monday. 7:29pm is not the gate; 7:29am is.
    due = dn.recap_periods_due(_at("2026-10-19T07:29:00"))
    assert [w["span"] for w in due] == ["month"]
    # The month that opened on the first Monday (Oct 5) is still September.
    month = due[0]
    assert month["start"].isoformat() == "2026-09-01"
    assert month["end"].isoformat() == "2026-09-30"
    assert month["heading"] == "September"


def test_monday_at_730_opens_the_prior_mon_sun_week():
    due = dn.recap_periods_due(_at("2026-10-19T07:30:00"))
    week = next(w for w in due if w["span"] == "week")
    assert week["start"].isoformat() == "2026-10-12"
    assert week["end"].isoformat() == "2026-10-18"
    assert week["heading"] == "Week of Oct 12-18"


def test_a_later_weekday_still_retries_that_week():
    due = dn.recap_periods_due(_at("2026-10-21T15:00:00"))
    week = next(w for w in due if w["span"] == "week")
    assert week["start"].isoformat() == "2026-10-12"
    assert week["end"].isoformat() == "2026-10-18"


def test_sunday_does_not_open_the_week_that_is_still_in_progress():
    due = dn.recap_periods_due(_at("2026-10-18T21:00:00"))
    week = next(w for w in due if w["span"] == "week")
    assert week["end"].isoformat() == "2026-10-11"


def test_the_first_monday_opens_the_previous_calendar_month():
    due = dn.recap_periods_due(_at("2026-10-05T07:30:00"))
    month = next(w for w in due if w["span"] == "month")
    assert month["start"].isoformat() == "2026-09-01"
    assert month["end"].isoformat() == "2026-09-30"
    assert month["heading"] == "September"
    week = next(w for w in due if w["span"] == "week")
    assert week["heading"] == "Week of Sep 28-Oct 4"


def test_the_minute_before_the_first_monday_is_still_the_older_month():
    due = dn.recap_periods_due(_at("2026-10-05T07:29:00"))
    month = next(w for w in due if w["span"] == "month")
    assert month["heading"] == "August"
    assert month["start"].isoformat() == "2026-08-01"
    assert month["end"].isoformat() == "2026-08-31"


def test_a_week_that_crosses_months_names_both():
    assert dn.period_heading(
        "week", date(2026, 9, 28), date(2026, 10, 4),
    ) == "Week of Sep 28-Oct 4"


def test_the_period_tweet_uses_the_daily_tally_and_states_roi():
    recap = {"wins": 10, "losses": 8, "pushes": 1, "units": 3.2,
             "risked": 25.8, "clv": "", "by_sport": [
                 {"sport": "MLB", "wins": 6, "losses": 4, "pushes": 0},
                 {"sport": "NFL", "wins": 4, "losses": 4, "pushes": 1},
             ]}
    week = xp.render_results(recap, "2026-10-12", heading="Week of Oct 12-18 results")
    month = xp.render_results(
        {"wins": 40, "losses": 35, "pushes": 2, "units": -4.5, "risked": 90.0,
         "clv": "55% beat close (11/20)", "by_sport": []},
        "2026-09-01", heading="September results")
    assert week.startswith("\U0001F4CA Week of Oct 12-18 results: 10-8-1")
    assert "+3.20u" in week and "ROI" in week
    assert "MLB 6-4" in week and "NFL 4-4-1" in week
    assert month.startswith("\U0001F4CA September results: 40-35-2")
    assert "-4.50u" in month and "ROI" in month
    assert "55% beat close (11/20)" in month
    assert len(week) <= xp.MAX_TWEET and len(month) <= xp.MAX_TWEET
    xp._assert_no_link(week)
    xp._assert_no_link(month)


def test_a_push_only_period_does_not_invent_an_roi():
    text = xp.render_results(
        {"wins": 0, "losses": 0, "pushes": 3, "units": 0.0, "risked": 0.0,
         "by_sport": []},
        "2026-10-12", heading="Week of Oct 12-18 results")
    assert "0-0-3" in text and "+0.00u" in text and "ROI" not in text


def test_the_job_is_monday_730_et_on_the_pipeline(monkeypatch):
    import scheduler
    assert "period_recaps" in scheduler._PIPELINE_JOBS
    job = {j.id: j for j in scheduler.build_scheduler().get_jobs()}["period_recaps"]
    blob = str(job.trigger)
    assert "mon" in blob
    assert "7" in blob and "30" in blob


def test_settle_retries_the_period_recaps():
    src = (Path(__file__).parent.parent / "run_pipeline.py").read_text(encoding="utf-8")
    assert "post_period_recaps" in src
    assert src.index("notify_x_results") < src.index("post_period_recaps")


def test_discord_period_uses_the_results_webhook_and_ledgers_once(monkeypatch):
    posted = []
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, body: posted.append((url, body)) or "99")
    rows = [("MLB", "mlb_ml", "WIN", 0.02, -110, None, False, 1.0, 1.1)]
    monkeypatch.setattr(dn, "_settled_rows_since", lambda conn, a, b: rows)

    class _Conn:
        def __init__(self):
            self.sent = set()
            self.sql = ""
            self.params = None

        def execute(self, sql, params=None):
            self.sql = sql
            self.params = params
            if "INSERT" in sql:
                self.sent.add((params[0], params[1]))
            return self

        def fetchone(self):
            if self.params and (self.params[0], self.params[1]) in self.sent:
                return (1,)
            return None

        def commit(self):
            pass

        def close(self):
            pass

    conn = _Conn()
    monkeypatch.setattr(dn, "get_connection", lambda: conn)
    start = __import__("datetime").date(2026, 10, 12)
    end = __import__("datetime").date(2026, 10, 18)
    assert dn.notify_discord_period("week", start, end, "Week of Oct 12-18") == 1
    assert dn.notify_discord_period("week", start, end, "Week of Oct 12-18") == 0
    assert len(posted) == 1
    assert posted[0][0] == "https://discord.test/results"
    title = posted[0][1]["embeds"][0]["title"]
    desc = posted[0][1]["embeds"][0]["description"]
    assert "Week of Oct 12-18" in title
    assert "1-0" in desc and "+1.00u" in desc and "ROI" in desc
    assert ("discord_results_week:2026-10-12", "discord_results_week") in conn.sent


def test_x_period_uses_the_same_window_and_does_not_repost(monkeypatch):
    import data.db
    from datetime import date

    rows = [("MLB", "mlb_ml", "WIN", 0.02, -110, None, False, 1.0, 1.1),
            ("MLB", "mlb_ml", "LOSS", 0.02, -110, None, False, -1.1, 1.1)]
    monkeypatch.setattr(dn, "_settled_rows_since", lambda conn, a, b: rows)
    monkeypatch.setattr(xp, "_enabled", lambda: True)
    monkeypatch.setattr(xp, "_creds", lambda: ("a", "b", "c", "d"))
    seen = {}

    class _Conn:
        def close(self):
            pass

    monkeypatch.setattr(data.db, "get_connection", lambda: _Conn())
    sent = set()

    def _sent(conn, key, kind):
        return (key, kind) in sent

    ledgered = []

    def _remember(conn, key, kind, tweet_id):
        sent.add((key, kind))
        ledgered.append((key, kind, tweet_id))

    monkeypatch.setattr(xp, "_already_sent", _sent)
    monkeypatch.setattr(xp, "_ledger", _remember)
    posted = []

    def _deliver(text, dry_run=False, reply_to=None, allow_link=False):
        posted.append(text)
        return "id1", False

    monkeypatch.setattr(xp, "_deliver_tweet", _deliver)
    start, end = date(2026, 9, 1), date(2026, 9, 30)
    assert xp.notify_x_period("month", start, end, "September") == 1
    assert xp.notify_x_period("month", start, end, "September") == 0
    assert len(posted) == 1
    assert posted[0].startswith("\U0001F4CA September results:")
    assert "1-1" in posted[0] and "ROI" in posted[0]
    assert ledgered == [("x_results_month:2026-09-01", "x_results_month", "id1")]
    seen["args"] = True
