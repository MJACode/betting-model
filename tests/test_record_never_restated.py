"""No restated record, on any surface, without mike's approval. All picks graded
before the daily record goes out.

mike, 2026-10-30: "No restated records of any kind unless I give the approval.
Repo wide rule." and "checks prior to the daily record going out to ensure all
picks are graded, if not grade them."

The automatic restatement ran on every settle pass from 2026-09-10 and posted 19
restated days to Discord and 19 to X in the 45 days to 2026-10-30 (push_sent,
kinds discord_results_restate and x_results_restate). The shape, every time: the
6am recap posted at 06:03, an NHL goalie prop could not grade until the stats
pull at 06:09 flagged who started, the 07:17 pass graded it at 07:24, and the
restatement fired seconds later.
"""
from __future__ import annotations

import inspect
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

ROOT = Path(__file__).parent.parent
PUB = datetime(2026, 10, 30, 10, 3, 3, tzinfo=timezone.utc)
MORNING = datetime(2026, 10, 30, 7, 24, tzinfo=dn.ET)
SETTLED_ROW = ("NHL", "nhl_prop_saves", "WIN", 0.02, -110.0, None, False, 1.0, 1.1)
UNGRADED_ROW = ("NHL", "nhl_prop_saves", "Jake Oettinger Under 22.5 Saves",
                "NHL_2026-10-29_MTL_DAL", "2026-10-29")


class _Conn:
    """Answers each query by what it asks. `ungraded` is what the record's
    universe still holds with no result. `snaps` and `late` feed the scan of
    published recaps. `sent` is the ledger, and writes land in `inserts`."""

    def __init__(self, ungraded=(), settled=(SETTLED_ROW,), snaps=(), late=0,
                 sent=()):
        self.ungraded, self.settled = list(ungraded), list(settled)
        self.snaps, self.late = list(snaps), late
        self.sent, self.inserts, self.deleted = set(sent), [], []
        self.sql = ""

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params
        if "INSERT INTO push_sent" in sql:
            self.inserts.append(params)
            self.sent.add(params[0])
        if "DELETE FROM push_sent" in sql:
            self.deleted.append(params)
            self.sent.clear()
        return self

    def fetchone(self):
        if "count(*)" in self.sql:
            return (1 if self.sent else 0,)
        if "FROM push_sent" in self.sql:
            return (1,) if tuple(self.params)[:1] and self.params[0] in self.sent else None
        return None

    def fetchall(self):
        if "FROM results_snapshots" in self.sql:
            return self.snaps
        if "p.settled_at > %s" in self.sql:
            return [SETTLED_ROW] * self.late
        if "p.result IS NULL" in self.sql:
            return list(self.ungraded)
        if "commence_time" in self.sql or "home_score IS NULL" in self.sql:
            return []
        return list(self.settled)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


@pytest.fixture
def wired(monkeypatch):
    """Both surfaces switched on. Whatever would reach a channel is captured."""
    discord, tweets, alerts = [], [], []
    monkeypatch.setattr(dn, "_results_webhook", lambda: "https://discord.test/results")
    monkeypatch.setattr(dn, "_post", lambda url, body: discord.append(body) or "44")
    monkeypatch.setattr(dn, "_store_snapshot", lambda *a, **k: None)
    monkeypatch.setattr(dn, "all_time_fields", lambda *a, **k: ([], None))
    monkeypatch.setattr(xp, "_enabled", lambda: True)
    monkeypatch.setattr(xp, "_creds", lambda: True)
    monkeypatch.setattr(xp, "post_tweet", lambda *a, **k: tweets.append(a[0]) or "55")
    import tracking.watch_util as watch
    monkeypatch.setattr(watch, "post_ops_alert",
                        lambda title, detail, **k: alerts.append((title, detail)) or True)
    return discord, tweets, alerts


def _use(monkeypatch, conn):
    monkeypatch.setattr(dn, "get_connection", lambda *a, **k: conn)
    monkeypatch.setattr("data.db.get_connection", lambda *a, **k: conn)


# ── a late grade restates nothing ────────────────────────────────────────────

def test_a_pick_graded_after_the_recap_posts_no_recap_on_either_surface(monkeypatch, wired):
    """The morning of 2026-10-30, replayed: the recap for 10-29 is published, the
    goalie prop grades at 07:24, and the pass that follows must post nothing."""
    discord, tweets, _alerts = wired
    conn = _Conn(snaps=[("2026-10-29", PUB, 10)], late=1)
    _use(monkeypatch, conn)
    dn.flag_recaps_gone_short(now=MORNING)
    assert discord == [] and tweets == []


def test_the_settle_step_cannot_call_a_restatement():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    fn = src[src.index("def step_settle("):src.index("\ndef ", src.index("def step_settle(") + 10)]
    assert "restate" not in fn.lower()


def test_neither_daily_notifier_can_post_a_restatement():
    """A parameter that could ask for a second copy is a route to one."""
    assert "restate" not in inspect.signature(dn.notify_discord_results).parameters
    assert "restate" not in inspect.signature(xp.notify_x_results).parameters
    assert not hasattr(dn, "restate_published_recaps")
    assert not hasattr(dn, "_restate_x_if_behind")
    assert not hasattr(dn, "results_restate_note")
    assert "restate" not in inspect.signature(xp.render_results).parameters


def test_a_recap_that_went_short_tells_ops_once_and_never_the_channel(monkeypatch, wired):
    discord, tweets, alerts = wired
    conn = _Conn(snaps=[("2026-10-29", PUB, 10)], late=1)
    _use(monkeypatch, conn)
    assert dn.flag_recaps_gone_short(now=MORNING) == 1
    assert discord == [] and tweets == []
    assert len(alerts) == 1
    assert "2026-10-29" in alerts[0][1] and "not re-posted" in alerts[0][1].lower()
    assert conn.inserts and conn.inserts[0][1] == dn.RECORD_SHORT_KIND
    conn.sent.add(conn.inserts[0][0])
    assert dn.flag_recaps_gone_short(now=MORNING) == 0
    assert len(alerts) == 1, "one late batch is one alert, not one per pass"


def test_a_recap_that_merely_drifted_is_not_short(monkeypatch, wired):
    """Nothing graded after it posted: the count moved because the cuts did."""
    _d, _t, alerts = wired
    _use(monkeypatch, _Conn(snaps=[("2026-10-29", PUB, 10)], late=0))
    assert dn.flag_recaps_gone_short(now=MORNING) == 0
    assert alerts == []


def test_the_short_recap_scan_counts_the_same_picks_the_record_does():
    conn = _Conn(snaps=[("2026-10-29", PUB, 10)], late=1)
    seen = []
    real = conn.execute

    def spy(sql, params=()):
        seen.append(sql)
        return real(sql, params)
    conn.execute = spy
    dn.recaps_gone_short(conn, through="2026-10-30")
    assert any(s.startswith(dn._SETTLED_SQL.format(window="= %s")) for s in seen)


# ── the approval register ────────────────────────────────────────────────────

def test_nothing_is_approved():
    """Only mike's words in chat put an entry here, and this test changes in the
    same commit, so an approval cannot be added by accident."""
    assert config.RECORD_RESTATEMENT_APPROVALS == {}


@pytest.mark.parametrize("job,key", [
    ("_job_publish_results", "2026-10-29"),
    ("_job_publish_x_results", "2026-10-29"),
])
def test_a_job_refuses_to_clear_a_posted_day_and_post_it_again(monkeypatch, wired, job, key):
    """These two delete the ledger row, which turns a second post into a 'first'."""
    from tracking import job_queue
    discord, tweets, _a = wired
    conn = _Conn(sent={f"discord_results:{key}", f"x_results:{key}"})
    _use(monkeypatch, conn)
    with pytest.raises(config.RecordRestatementRefused):
        getattr(job_queue, job)(game_date=key)
    assert conn.deleted == [] and discord == [] and tweets == []


def test_a_job_posts_a_day_that_never_went_out(monkeypatch, wired):
    """A first post is not a restatement. A day with no ledger row still posts."""
    from tracking import job_queue
    discord, tweets, _a = wired
    _use(monkeypatch, _Conn(sent=set()))
    monkeypatch.setattr(dn, "window_still_live", lambda *a, **k: False)
    monkeypatch.setattr(dn, "sport_in_progress", lambda *a, **k: False)
    monkeypatch.setattr(dn, "in_daily_recap_window", lambda *a, **k: True)
    result = job_queue._job_publish_results(game_date="2026-10-29")
    assert len(discord) == 1 and result["ledger_rows_cleared"] == 0


def test_an_approved_day_may_be_posted_again(monkeypatch, wired):
    from tracking import job_queue
    discord, _t, _a = wired
    monkeypatch.setitem(config.RECORD_RESTATEMENT_APPROVALS, "2026-10-29",
                        "mike, 2026-10-31: post it again")
    conn = _Conn(sent={"discord_results:2026-10-29", "x_results:2026-10-29"})
    _use(monkeypatch, conn)
    monkeypatch.setattr(dn, "window_still_live", lambda *a, **k: False)
    monkeypatch.setattr(dn, "sport_in_progress", lambda *a, **k: False)
    monkeypatch.setattr(dn, "in_daily_recap_window", lambda *a, **k: True)
    job_queue._job_publish_results(game_date="2026-10-29")
    assert len(discord) == 1


@pytest.mark.parametrize("job", [
    "_job_publish_record_correction",
    "_job_publish_full_record",
    "_job_publish_full_record_standard",
    "_job_publish_oct13_nhl_line",
    "_job_publish_oct13_nhl_reply",
])
def test_a_written_correction_job_refuses_without_approval(monkeypatch, job):
    from tracking import job_queue
    monkeypatch.setattr("data.db.get_connection",
                        lambda *a, **k: pytest.fail("reached the database"))
    with pytest.raises(config.RecordRestatementRefused):
        getattr(job_queue, job)()


def test_a_capper_recap_refuses_a_corrected_post(monkeypatch):
    from tracking import eggz_picks as ep
    posted = []
    monkeypatch.setattr(ep, "configured_to_post", lambda capper: True)
    monkeypatch.setattr(ep, "_post", lambda *a, **k: posted.append(a) or "1")
    assert ep._post_window(
        _Conn(), "day", "2026-10-22", "2026-10-22", "Oct 22",
        restate_published_at="2026-10-23T06:00:00-04:00", now=MORNING) == 0
    assert posted == []


def test_the_slate_repost_refuses_without_approval(monkeypatch):
    monkeypatch.setattr(dn, "_configured", lambda: True)
    monkeypatch.setattr(dn, "DISCORD_RESTATE_DATES", frozenset({"2026-10-29"}))
    monkeypatch.setattr(dn, "get_connection",
                        lambda *a, **k: pytest.fail("reached the database"))
    assert dn.notify_discord_restate(target_date="2026-10-29") == 0


# ── every pick graded before the record goes out ─────────────────────────────

def test_the_ungraded_query_is_the_records_own_universe():
    """A paused model's or an unposted pick's row must not hold the record, and
    one the record counts must not slip past. Same WHERE, result clause aside."""
    settled = dn._SETTLED_SQL.split("FROM picks p", 1)[1]
    ungraded = dn._UNGRADED_SQL.split("FROM picks p", 1)[1]
    assert "p.result IN ('WIN', 'LOSS', 'PUSH')" in settled
    assert ungraded == settled.replace(
        "p.result IN ('WIN', 'LOSS', 'PUSH')", "p.result IS NULL")


@pytest.fixture
def morning(monkeypatch, wired):
    monkeypatch.setattr(dn, "window_still_live", lambda *a, **k: False)
    monkeypatch.setattr(dn, "sport_in_progress", lambda *a, **k: False)
    return wired


def _grading(monkeypatch, conn, *, fixes=True):
    """The grade step, recorded. `fixes` is whether it clears what was ungraded."""
    calls = []

    def grade(rows):
        calls.append(rows)
        if fixes:
            conn.ungraded.clear()
    monkeypatch.setattr(dn, "_grade_outstanding", grade)
    return calls


def test_an_ungraded_pick_is_graded_and_the_record_then_posts(monkeypatch, morning):
    discord, tweets, alerts = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)
    calls = _grading(monkeypatch, conn)
    assert dn.notify_discord_results("2026-10-29", now=MORNING) == 1
    assert xp.notify_x_results("2026-10-29", now=MORNING) == 1
    assert len(calls) == 1, "Discord graded it, so X found nothing left to grade"
    assert len(discord) == 1 and len(tweets) == 1 and alerts == []


def test_a_pick_that_cannot_be_graded_holds_both_surfaces_and_tells_ops(monkeypatch, morning):
    discord, tweets, alerts = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)
    _grading(monkeypatch, conn, fixes=False)
    assert dn.notify_discord_results("2026-10-29", now=MORNING) == 0
    assert xp.notify_x_results("2026-10-29", now=MORNING) == 0
    assert discord == [] and tweets == []
    assert conn.inserts and all(i[1] == dn.RECORD_HELD_KIND for i in conn.inserts)
    assert len(alerts) == 1, "both surfaces held the same day; ops hears once"
    assert "Jake Oettinger Under 22.5 Saves" in alerts[0][1]


def test_a_held_day_alerts_again_the_next_morning_only(monkeypatch, morning):
    _d, _t, alerts = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)
    _grading(monkeypatch, conn, fixes=False)
    dn.notify_discord_results("2026-10-29", now=MORNING)
    conn.sent.add(conn.inserts[0][0])
    dn.notify_discord_results("2026-10-29", now=MORNING)
    assert len(alerts) == 1
    tomorrow = datetime(2026, 10, 31, 7, 24, tzinfo=dn.ET)
    dn.notify_discord_results("2026-10-29", now=tomorrow)
    assert len(alerts) == 2


def test_a_dry_run_reports_the_hold_and_writes_nothing(monkeypatch, morning):
    discord, _t, alerts = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)
    calls = _grading(monkeypatch, conn)
    assert dn.notify_discord_results("2026-10-29", dry_run=True, now=MORNING) == 0
    assert calls == [] and discord == [] and alerts == [] and conn.inserts == []


def test_a_day_with_everything_graded_never_runs_the_grade_step(monkeypatch, morning):
    discord, _t, _a = morning
    conn = _Conn(ungraded=[])
    _use(monkeypatch, conn)
    calls = _grading(monkeypatch, conn)
    assert dn.notify_discord_results("2026-10-29", now=MORNING) == 1
    assert calls == [] and len(discord) == 1


def test_a_week_with_an_ungraded_pick_holds_on_both_surfaces(monkeypatch, morning):
    discord, tweets, _a = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)
    _grading(monkeypatch, conn, fixes=False)
    week = (date(2026, 10, 19), date(2026, 10, 25), "Week of Oct 19-25")
    at = datetime(2026, 10, 26, 8, 0, tzinfo=dn.ET)
    assert dn.notify_discord_period("week", *week, now=at) == 0
    assert xp.notify_x_period("week", *week, now=at) == 0
    assert discord == [] and tweets == []


def test_grading_pulls_the_nhl_starts_then_grades_each_date(monkeypatch):
    """The evening box often has no start flagged for a goalie. The stats pull
    has it. Grading without that pull leaves the same pick ungraded."""
    order = []
    monkeypatch.setattr("data.ingestors.nhl_game_logs.top_up",
                        lambda days, apply, today=None: order.append(("top_up", days, apply)))
    monkeypatch.setattr("tracking.paper_tracker.settle_picks",
                        lambda game_date=None: order.append(("settle", game_date)))
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-30")
    dn._grade_outstanding([UNGRADED_ROW])
    assert order == [("top_up", 5, True), ("settle", "2026-10-29")]


def test_grading_reaches_back_to_a_held_day_older_than_the_morning_pull(monkeypatch):
    order = []
    monkeypatch.setattr("data.ingestors.nhl_game_logs.top_up",
                        lambda days, apply, today=None: order.append(days))
    monkeypatch.setattr("tracking.paper_tracker.settle_picks", lambda game_date=None: None)
    monkeypatch.setattr(config, "today_et", lambda: "2026-10-30")
    old = ("NHL", "nhl_prop_saves", "x", "g", "2026-10-22")
    dn._grade_outstanding([old])
    assert order == [9]


def test_grading_skips_the_nhl_pull_when_no_nhl_pick_waits(monkeypatch):
    monkeypatch.setattr("data.ingestors.nhl_game_logs.top_up",
                        lambda *a, **k: pytest.fail("no NHL pick is waiting"))
    graded = []
    monkeypatch.setattr("tracking.paper_tracker.settle_picks",
                        lambda game_date=None: graded.append(game_date))
    dn._grade_outstanding([("NBA", "nba_prop_points", "x", "g", "2026-10-29")])
    assert graded == ["2026-10-29"]


def test_a_grading_failure_leaves_the_day_held_instead_of_raising(monkeypatch, morning):
    discord, _t, alerts = morning
    conn = _Conn(ungraded=[UNGRADED_ROW])
    _use(monkeypatch, conn)

    def boom(game_date=None):
        raise RuntimeError("database went away")
    monkeypatch.setattr("tracking.paper_tracker.settle_picks", boom)
    monkeypatch.setattr("data.ingestors.nhl_game_logs.top_up", lambda *a, **k: None)
    assert dn.notify_discord_results("2026-10-29", now=MORNING) == 0
    assert discord == [] and len(alerts) == 1


# ── the 6am order ────────────────────────────────────────────────────────────

def test_the_6am_run_pulls_nhl_starts_before_it_settles():
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    assert (src.index('results["nhl_game_logs"] = step_nhl_game_logs(')
            < src.index('results["settle"] = step_settle(yesterday)'))


# ── the rule itself ──────────────────────────────────────────────────────────

def test_the_rule_is_in_the_always_loaded_file():
    """Reachable by a declared job or a one-off script without opening
    tracking/, so a folder-scoped copy would not load for the session that
    breaks it (CLAUDE.md section 10)."""
    text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "NO RESTATED RECORDS" in text
    assert "RECORD_RESTATEMENT_APPROVALS" in text
