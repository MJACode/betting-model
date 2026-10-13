"""A day the 6am run could not recap posts at the first pass that can.

WHAT HAPPENED (2026-10-13, measured on production). The 6am run settled
2026-10-12 and logged "Discord(results): nothing settled for 2026-10-12" at
06:02. That day had eight BETs: six from paused models, which the recap leaves
out on purpose, and two NHL props (nhl_prop_saves 3523486,
nhl_prop_shots_on_goal 3527680) that the 07:17 refresh pass graded WIN at
07:24:06 ET. Nothing asked again -- a refresh pass settles TODAY and both
notifiers refuse a day that is not over -- so neither Discord nor X posted the
day until it was pushed by hand at 08:50. 2026-10-05 had the same shape
(2 counting bets, first graded 10-06 07:26 ET) and was never recapped at all.

These tests replay 10-12 through run_pipeline.step_settle against a real SQL
engine (SQLite, in memory), running the recap's own SQL: the 6am run posts
nothing, the 07:24 pass posts once on both surfaces, a later pass posts
nothing new. Every pick row below is the production row for 2026-10-12
(pick_id, model, result, paused marker, settled_at, price); kelly_fraction is
a stand-in because conviction is flat 1u.
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pytest
from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402
import run_pipeline as rp  # noqa: E402
from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

ET = dn.ET
DAY = "2026-10-12"

# (pick_id, sport, model_id, result, downgrade_reason, settled_at, dk_odds)
# exactly as production holds them (SELECT ... FROM picks WHERE game_date =
# '2026-10-12' AND signal_type = 'BET').
PAUSED_BY_MIDNIGHT = [
    (3518807, "MLB", "mlb_prop_pitcher_er", "WIN", "model paused",
     "2026-10-12T20:36:12.466377-04:00", -127.0),
    (3516418, "MLB", "mlb_prop_pitcher_er", "WIN", "model paused",
     "2026-10-12T20:36:12.466377-04:00", -125.0),
    (3533055, "MLB", "mlb_prop_pitcher_hits", "WIN", "model paused",
     "2026-10-12T23:16:59.933675-04:00", 127.0),
    (3518810, "MLB", "mlb_prop_pitcher_er", "WIN", "model paused",
     "2026-10-12T23:16:59.933675-04:00", -119.0),
    (3532375, "MLB", "mlb_prop_pitcher_outs", "LOSS", "model paused",
     "2026-10-12T23:16:59.933675-04:00", -128.0),
]
NFL_PAUSED = (3533870, "NFL", "nfl_prop_receptions", "NO_ACTION",
              "model paused", "2026-10-13T06:02:33.147691-04:00", -192.0)
NHL_COUNTING = [
    (3527680, "NHL", "nhl_prop_shots_on_goal", "WIN", None,
     "2026-10-13T07:24:06.124437-04:00", -130.0),
    (3523486, "NHL", "nhl_prop_saves", "WIN", None,
     "2026-10-13T07:24:06.124437-04:00", None),
]


def _lite(sql: str) -> str:
    """psycopg2 placeholders to SQLite's. `%%` is a literal percent in the
    recap SQL's LIKE; it must become `%` before `%s` becomes `?`."""
    return sql.replace("%%", "%").replace("%s", "?")


class _LiteConn:
    """The repo's connection shape over one shared SQLite database. close()
    is a no-op so every get_connection() in a pass sees the same data.

    `fail_snapshot` makes the NEXT results_snapshots write fail, once, in one
    of the two ways production can:
      "lost"  -- the pooler drops mid-write. data.db's contract: it has
                 already reconnected, the transaction's uncommitted work is
                 gone, and it raises ConnectionLost.
      "error" -- the statement errors. PostgreSQL then refuses every
                 statement until rollback, and COMMIT of that transaction is
                 a ROLLBACK that raises nothing. SQLite does neither on its
                 own, so `aborted` models it.
    """

    def __init__(self, db):
        self.db, self.statements = db, []
        self.fail_snapshot: str | None = None
        self.aborted = False

    def _refuse_if_aborted(self):
        if self.aborted:
            raise RuntimeError("current transaction is aborted, commands "
                               "ignored until end of transaction block")

    def execute(self, sql, params=()):
        self.statements.append(sql)
        self._refuse_if_aborted()
        return self.db.execute(_lite(sql), tuple(params or ()))

    def executemany(self, sql, rows):
        self.statements.append(sql)
        self._refuse_if_aborted()
        if self.fail_snapshot and "results_snapshots" in sql:
            mode, self.fail_snapshot = self.fail_snapshot, None
            if mode == "lost":
                from data.db import ConnectionLost
                self.db.rollback()
                raise ConnectionLost("connection lost with uncommitted "
                                     "writes; reconnected, transaction "
                                     "discarded")
            self.aborted = True
            raise RuntimeError("snapshot insert failed")
        self.db.executemany(_lite(sql), rows)

    def commit(self):
        if self.aborted:
            self.aborted = False
            self.db.rollback()
            return
        self.db.commit()

    def rollback(self):
        self.aborted = False
        self.db.rollback()

    def close(self):
        pass


def _schema(db):
    db.execute("""CREATE TABLE picks (
        pick_id INTEGER PRIMARY KEY, game_date TEXT, sport TEXT, model_id TEXT,
        signal_type TEXT, result TEXT, kelly_fraction REAL, dk_odds REAL,
        clv_pct REAL, is_live INTEGER, downgrade_reason TEXT,
        condition_status TEXT, settled_at TEXT)""")
    db.execute("""CREATE TABLE push_sent (
        lock_key TEXT, kind TEXT, sent_at TEXT, message_id TEXT,
        UNIQUE (lock_key, kind))""")
    db.execute("""CREATE TABLE results_snapshots (
        game_date TEXT, scope TEXT, sport TEXT, wins INT, losses INT,
        pushes INT, settled INT, record_only INT, units REAL, risked REAL,
        roi_pct REAL, clv_graded INT, clv_beat INT, clv_pct REAL,
        published_at TEXT)""")
    db.execute("CREATE UNIQUE INDEX uq_snap ON results_snapshots "
               "(game_date, scope, COALESCE(sport, ''))")


def _add_pick(db, row, *, graded: bool):
    pick_id, sport, model, result, reason, settled_at, odds = row
    db.execute(
        "INSERT INTO picks VALUES (?,?,?,?,'BET',?,0.02,?,NULL,0,?,NULL,?)",
        (pick_id, DAY, sport, model, result if graded else None, odds, reason,
         settled_at if graded else None))


def _grade(db, row):
    pick_id, _s, _m, result, _r, settled_at, _o = row
    db.execute("UPDATE picks SET result = ?, settled_at = ? WHERE pick_id = ?",
               (result, settled_at, pick_id))


class World:
    """One production day, a clock, and the two surfaces, all fake."""

    def __init__(self, monkeypatch, *, nhl_graded_by_midnight=False):
        self.db = sqlite3.connect(":memory:")
        _schema(self.db)
        for row in PAUSED_BY_MIDNIGHT:
            _add_pick(self.db, row, graded=True)
        _add_pick(self.db, NFL_PAUSED, graded=False)
        for row in NHL_COUNTING:
            _add_pick(self.db, row, graded=False)
        if nhl_graded_by_midnight:
            for row in NHL_COUNTING:
                _grade(self.db, row[:5] + ("2026-10-12T23:50:00.000000-04:00",)
                       + row[6:])
        self.conn = _LiteConn(self.db)
        self.now = datetime(2026, 10, 13, 0, 0, tzinfo=ET)
        self.to_grade: list = []
        self.discord: list = []        # every Discord recap that was DELIVERED
        self.tweets: list = []         # every tweet that was DELIVERED
        self.discord_fails = False
        self.x_fails = False
        self.retry_calls = 0
        self._patch(monkeypatch)

    def _patch(self, mp):
        world = self

        class _Frozen(datetime):
            @classmethod
            def now(cls, tz=None):
                return world.now.astimezone(tz) if tz else world.now

        mp.setattr(dn, "datetime", _Frozen)
        mp.setattr(xp, "datetime", _Frozen)
        mp.setattr(config, "today_et", lambda: world.now.date().isoformat())
        mp.setattr(dn, "get_connection", lambda *a, **k: world.conn)
        import data.db
        mp.setattr(data.db, "get_connection", lambda *a, **k: world.conn)

        mp.setattr(config, "DISCORD_WEBHOOK_RESULTS",
                   "https://discord.test/results", raising=False)
        mp.setenv("RUN_X_PUBLISHER", "1")
        for name in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                     "X_ACCESS_TOKEN_SECRET"):
            mp.setenv(name, "test-value")

        def _post(url, payload):
            if world.discord_fails:
                return None
            world.discord.append(payload["embeds"][0])
            return f"msg-{len(world.discord)}"

        def _tweet(text, dry_run=False, reply_to=None):
            if world.x_fails:
                return None
            world.tweets.append(text)
            return f"tw-{len(world.tweets)}"

        mp.setattr(dn, "_post", _post)
        mp.setattr(xp, "post_tweet", _tweet)

        def _settle(game_date=None):
            for row in world.to_grade:
                _grade(world.db, row)
            world.db.commit()
            graded, world.to_grade = len(world.to_grade), []
            return {"settled": graded}

        mp.setattr(rp, "_import_step", lambda name: _settle)

    def daily(self, hhmmss: str, *grade):
        """The 6am run: step_settle(yesterday)."""
        return self._pass(hhmmss, DAY, grade)

    def refresh(self, hhmmss: str, *grade):
        """A refresh pass: `--step settle` with run_date = today ET."""
        return self._pass(hhmmss, None, grade)

    def _pass(self, hhmmss, settle_date, grade):
        h, m, s = (int(x) for x in hhmmss.split(":"))
        self.now = datetime(2026, 10, 13, h, m, s, tzinfo=ET)
        self.to_grade = list(grade)
        return rp.step_settle(settle_date or self.now.date().isoformat())

    def ledger(self) -> set[str]:
        return {r[0] for r in self.db.execute(
            "SELECT lock_key FROM push_sent WHERE kind IN "
            "('discord_results', 'x_results', 'discord_results_restate', "
            "'x_results_restate')").fetchall()}


# ── 2026-10-12, replayed ─────────────────────────────────────────────────────

def test_the_day_posts_once_on_both_surfaces_at_the_first_pass_that_can(monkeypatch):
    w = World(monkeypatch)

    # 00:24 ET: an overnight pass. Nothing counting is graded yet.
    assert w.refresh("00:24:00") is True
    # 06:02 ET: the 6am run. Only the paused NFL row grades (NO_ACTION).
    assert w.daily("06:02:33", NFL_PAUSED) is True
    assert w.discord == [] and w.tweets == [], (
        "only paused rows have settled: the recap must not post at 6am")
    assert w.ledger() == set()

    # 07:24 ET: the 07:17 hourly pass grades the two NHL props.
    assert w.refresh("07:24:30", *NHL_COUNTING) is True
    assert len(w.discord) == 1, "Discord must post the day once, now"
    assert len(w.tweets) == 1, "X must post the day once, in the same pass"
    embed = w.discord[0]
    assert embed["title"] == "\U0001F4CA Results — Mon Oct 12"
    assert "2-0" in embed["description"] and "2 settled" in embed["description"]
    assert w.tweets[0].startswith("\U0001F4CA Oct 12 results: 2-0")
    assert w.ledger() == {f"discord_results:{DAY}", f"x_results:{DAY}"}
    snap = w.db.execute(
        "SELECT wins, losses, settled, published_at FROM results_snapshots "
        "WHERE game_date = ? AND scope = 'daily' AND sport IS NULL",
        (DAY,)).fetchone()
    assert snap[:3] == (2, 0, 2)
    assert snap[3].startswith("2026-10-13T07:24:30"), (
        "the receipt is stamped when it was actually published")

    # Every later pass that day: nothing new on either surface, and the
    # restatement scan does not mistake the 07:24 grading for a late pick.
    for hhmmss in ("08:24:00", "12:24:00", "23:54:00"):
        assert w.refresh(hhmmss) is True
    assert len(w.discord) == 1 and len(w.tweets) == 1
    assert w.ledger() == {f"discord_results:{DAY}", f"x_results:{DAY}"}


def test_an_overnight_pass_never_posts_yesterday(monkeypatch):
    """The overnight passes (00:17-05:17 ET) settle today too, and yesterday
    already passes the day-is-over guard at 00:17. Here the counting bets are
    graded before midnight, so without the hour gate the 00:24 pass would
    post yesterday before its late games and the 6am-only ingests are in."""
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    for hhmmss in ("00:24:00", "01:24:00", "05:24:00"):
        w.refresh(hhmmss)
    assert w.discord == [] and w.tweets == []
    # The 6am run is still the one that posts it, exactly as before.
    w.daily("06:02:33", NFL_PAUSED)
    assert len(w.discord) == 1 and len(w.tweets) == 1


def test_a_late_pick_after_the_retry_is_restated_once_not_reposted(monkeypatch):
    """The recap posted at 07:24 counts what had settled. A counting pick
    graded later is a correction: restated once on both surfaces, through the
    existing path -- never a second ordinary post."""
    w = World(monkeypatch)
    w.daily("06:02:33", NFL_PAUSED)
    w.refresh("07:24:30", *NHL_COUNTING)
    late = (3599999, "NHL", "nhl_prop_shots_on_goal", "LOSS", None,
            "2026-10-13T09:24:06.000000-04:00", -110.0)
    _add_pick(w.db, late, graded=False)
    w.refresh("09:24:30", late)
    w.refresh("10:24:30")
    assert len(w.discord) == 2 and len(w.tweets) == 2
    assert "restated" in w.discord[1]["title"]
    assert "1 pick settled after this recap was first posted" in (
        w.discord[1]["description"])
    assert "2-1" in w.discord[1]["description"]
    assert w.tweets[1].startswith("\U0001F4CA Oct 12 results (restated): 2-1")


# ── one surface failed ──────────────────────────────────────────────────────

def test_x_failing_at_6am_is_retried_alone_at_the_next_pass(monkeypatch):
    """Before this change X was never retried: the next pass asked for TODAY.
    Now the missing surface posts at 07:24 and Discord is not posted again."""
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    w.x_fails = True
    w.daily("06:02:33", NFL_PAUSED)
    assert len(w.discord) == 1 and w.tweets == []
    w.x_fails = False
    w.refresh("07:24:30")
    w.refresh("08:24:30")
    assert len(w.discord) == 1, "Discord already posted: never twice"
    assert len(w.tweets) == 1
    assert w.tweets[0].startswith("\U0001F4CA Oct 12 results: 2-0")


def test_x_failing_at_6am_then_a_late_pick_ends_on_the_same_numbers(monkeypatch):
    """X failed at 6am, Discord posted 2-0, a counting pick grades at 07:24.
    The retry tweets the day (2-1); the restatement scan in the same pass
    sees Discord's 06:02 recap is behind and restates both. X ends with two
    tweets carrying the same record -- the second says "(restated)", so it is
    not duplicate content -- and Discord with its original plus one restated."""
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    late = (3599999, "NHL", "nhl_prop_shots_on_goal", "LOSS", None,
            "2026-10-13T07:24:06.000000-04:00", -110.0)
    _add_pick(w.db, late, graded=False)
    w.x_fails = True
    w.daily("06:02:33", NFL_PAUSED)
    assert len(w.discord) == 1 and w.tweets == []
    w.x_fails = False
    w.refresh("07:24:30", late)
    w.refresh("08:24:30")
    assert len(w.discord) == 2 and "restated" in w.discord[1]["title"]
    assert "2-1" in w.discord[1]["description"]
    assert [t.split("\n")[0].split(",")[0] for t in w.tweets] == [
        "\U0001F4CA Oct 12 results: 2-1",
        "\U0001F4CA Oct 12 results (restated): 2-1"]


def test_discord_failing_at_6am_is_retried_alone_at_the_next_pass(monkeypatch):
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    w.discord_fails = True
    w.daily("06:02:33", NFL_PAUSED)
    assert w.discord == [] and len(w.tweets) == 1
    w.discord_fails = False
    w.refresh("07:24:30")
    w.refresh("08:24:30")
    assert len(w.discord) == 1 and len(w.tweets) == 1, (
        "nothing settled after the tweet: X is not touched again")
    assert "2-0" in w.discord[0]["description"]


def test_a_tweet_left_behind_by_a_late_discord_post_is_restated_once(monkeypatch):
    """Discord failed at 6am, X tweeted 2-0. A counting pick grades at 07:24
    and Discord's retry posts 2-1. The restatement scan measures lateness
    against Discord's snapshot (07:24), so it would never see that the tweet
    missed a pick -- X would say 2-0 for good. The retry restates it once."""
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    late = (3599999, "NHL", "nhl_prop_shots_on_goal", "LOSS", None,
            "2026-10-13T07:24:06.000000-04:00", -110.0)
    _add_pick(w.db, late, graded=False)
    w.discord_fails = True
    w.daily("06:02:33", NFL_PAUSED)
    assert w.discord == [] and len(w.tweets) == 1
    assert w.tweets[0].startswith("\U0001F4CA Oct 12 results: 2-0")
    w.discord_fails = False
    w.refresh("07:24:30", late)
    w.refresh("08:24:30")
    w.refresh("09:24:30")
    assert len(w.discord) == 1 and "2-1" in w.discord[0]["description"]
    assert len(w.tweets) == 2
    assert w.tweets[1].startswith("\U0001F4CA Oct 12 results (restated): 2-1")


# ── a delivered post stays ledgered when its receipt fails ──────────────────
# The recap posts, then writes its "already posted" row and its snapshot (the
# receipt). Both used to share one transaction, and the snapshot write
# swallows its own failure. So a failed snapshot took the ledger row with it:
# a pooler drop discards the whole transaction (data.db raises ConnectionLost,
# which the snapshot write swallowed), and a failed statement turns the
# transaction's COMMIT into a ROLLBACK that raises nothing (measured on a
# local PostgreSQL 16.2 with psycopg2 2.9.12: 0 ledger rows after commit()).
# On master only the 6am run asks, so that cost one post. With the retry,
# every pass from 7am saw "Discord missing, something counting settled" and
# posted the day again -- once per pass: 5 recaps from the 5 passes replayed
# below. 2026-10-12 had 46 settle passes between 07:00 ET and midnight ET
# (pipeline_log, step 'dispatch:settle').

@pytest.mark.parametrize("failure", ["lost", "error"])
def test_a_failed_receipt_never_reposts_the_day(monkeypatch, failure):
    """The snapshot write fails on every pass (a schema drift, a constraint):
    the day still posts exactly once."""
    w = World(monkeypatch)
    w.daily("06:02:33", NFL_PAUSED)
    for hhmmss, grade in (("07:24:30", NHL_COUNTING), ("08:24:30", ()),
                          ("09:24:30", ()), ("10:24:30", ()),
                          ("23:54:30", ())):
        w.conn.fail_snapshot = failure
        w.refresh(hhmmss, *grade)
    assert len(w.discord) == 1, f"Discord posted the day {len(w.discord)} times"
    assert len(w.tweets) == 1
    assert w.ledger() == {f"discord_results:{DAY}", f"x_results:{DAY}"}, (
        "the post went out: its ledger row must land even though the "
        "snapshot did not")
    assert w.db.execute("SELECT count(*) FROM results_snapshots").fetchone()[0] == 0


@pytest.mark.parametrize("failure", ["lost", "error"])
def test_a_failed_receipt_on_a_restatement_never_repeats_it(monkeypatch, failure):
    """The same shape on the existing restatement path: a correction whose
    snapshot write fails must still be ledgered, or every pass restates it."""
    w = World(monkeypatch)
    w.daily("06:02:33", NFL_PAUSED)
    w.refresh("07:24:30", *NHL_COUNTING)
    late = (3599999, "NHL", "nhl_prop_shots_on_goal", "LOSS", None,
            "2026-10-13T09:24:06.000000-04:00", -110.0)
    _add_pick(w.db, late, graded=False)
    for hhmmss, grade in (("09:24:30", (late,)), ("10:24:30", ()),
                          ("11:24:30", ()), ("23:54:30", ())):
        w.conn.fail_snapshot = failure
        w.refresh(hhmmss, *grade)
    assert len(w.discord) == 2, f"Discord posted {len(w.discord)} recaps"
    assert "restated" in w.discord[1]["title"]
    assert len(w.tweets) == 2


def test_a_later_snapshot_still_lands_after_the_ledger_commits(monkeypatch):
    """Committing the ledger first must not lose the receipt on a good day."""
    w = World(monkeypatch)
    w.daily("06:02:33", NFL_PAUSED)
    w.refresh("07:24:30", *NHL_COUNTING)
    assert w.db.execute(
        "SELECT settled FROM results_snapshots WHERE game_date = ? "
        "AND scope = 'daily' AND sport IS NULL", (DAY,)).fetchone() == (2,)
    assert not w.db.in_transaction, "nothing left uncommitted"


# ── what it costs, and what it must not do ──────────────────────────────────

def test_a_day_with_nothing_counting_posts_nothing_and_logs_nothing(monkeypatch):
    """2026-09-28 had no counting bets at all. Every pass from 7am must stay
    silent: no post, no "nothing settled" line, one statement."""
    w = World(monkeypatch)
    w.daily("06:02:33", NFL_PAUSED)
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="DEBUG")
    try:
        for hhmmss in ("07:24:30", "08:24:30", "22:54:30"):
            w.now = datetime(2026, 10, 13, *map(int, hhmmss.split(":")),
                             tzinfo=ET)
            before = len(w.conn.statements)
            assert dn.post_missed_recap() == 0
            assert len(w.conn.statements) - before == 1, "one statement a pass"
    finally:
        logger.remove(sink)
    assert w.discord == [] and w.tweets == []
    assert not [l for l in lines if "nothing settled" in l or DAY in l]


def test_once_both_surfaces_posted_a_pass_is_one_statement(monkeypatch):
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    w.daily("06:02:33", NFL_PAUSED)
    assert len(w.discord) == 1 and len(w.tweets) == 1
    w.now = datetime(2026, 10, 13, 7, 24, 30, tzinfo=ET)
    before = len(w.conn.statements)
    assert dn.post_missed_recap() == 0
    assert len(w.conn.statements) - before == 1


def test_before_7am_the_retry_does_not_touch_the_database(monkeypatch):
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    for h in range(0, dn.RECAP_RETRY_FROM_HOUR_ET):
        w.now = datetime(2026, 10, 13, h, 59, 59, tzinfo=ET)
        assert dn.post_missed_recap() == 0
    assert w.conn.statements == []


def test_a_surface_switched_off_does_not_count_as_missing(monkeypatch):
    """A worker without X credentials must not look like a missed recap on
    every pass once Discord has posted."""
    w = World(monkeypatch, nhl_graded_by_midnight=True)
    monkeypatch.delenv("X_API_KEY")
    w.daily("06:02:33", NFL_PAUSED)
    assert len(w.discord) == 1 and w.tweets == []
    called = []
    monkeypatch.setattr(dn, "notify_discord_results",
                        lambda *a, **k: called.append(a) or 0)
    w.now = datetime(2026, 10, 13, 8, 24, 30, tzinfo=ET)
    assert dn.post_missed_recap() == 0
    assert called == [], "nothing is missing: the notifiers are not called"


def test_the_6am_run_runs_nothing_new(monkeypatch):
    """The retry is only for a pass settling TODAY. The 6am run settles
    yesterday and has just made the ordinary attempt itself."""
    w = World(monkeypatch)
    calls = []
    monkeypatch.setattr(dn, "post_missed_recap",
                        lambda *a, **k: calls.append(w.now) or 0)
    w.daily("06:02:33", NFL_PAUSED)
    assert calls == []
    w.refresh("07:24:30")
    assert len(calls) == 1


def test_the_retry_counts_exactly_the_recaps_universe():
    """Built from _SETTLED_SQL, so a paused model's row can never wake it."""
    sql = dn._missed_recap_state_sql()
    assert dn._SETTLED_SQL.format(window="= %s") in sql
    assert config.paused_row_exclusion_sql("p") in sql
