"""
Tests for the pipeline-observability health checks added 2026-08-27.

These exist because of a specific outage: a NameError in the WNBA prop scorer
aborted every hourly refresh pass at step 9 of 24 for three days, and every
existing health check stayed green — they all measure DATA freshness, and the
daily 6am pipeline (which continues past step failures) kept the data fresh.
Nothing measured whether the PASSES completed, or whether a captured signal was
ever actually delivered.

Each test below is one branch of that new logic.
"""

import sqlite3
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.db_setup import SCHEMA_SQL, _MIGRATIONS
import tracking.system_health as sh
from config import today_et


class _Shim:
    """Minimal DBConnection stand-in over sqlite3.

    The health SQL uses `?` placeholders, which sqlite3 takes natively, so no
    dialect adaptation is needed here.
    """

    def __init__(self, path):
        self._c = sqlite3.connect(path)

    def execute(self, sql, params=()):
        return self._c.execute(sql, tuple(params))

    def commit(self):
        self._c.commit()

    def close(self):
        self._c.close()


def _iso(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


@pytest.fixture
def db(monkeypatch):
    """A fresh schema-complete SQLite DB wired into system_health."""
    path = tempfile.mktemp(suffix=".db")
    c = sqlite3.connect(path)
    c.executescript(SCHEMA_SQL)
    for tbl, col, defn in _MIGRATIONS:          # columns added post-CREATE
        try:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass
    # Postgres-only table the notifier and the delivery check both join.
    c.execute("""
        CREATE TABLE model_action_thresholds (
            model_id TEXT PRIMARY KEY, min_prob REAL NOT NULL,
            min_edge REAL NOT NULL DEFAULT 0, prob_only BOOLEAN NOT NULL DEFAULT 0,
            paused BOOLEAN NOT NULL DEFAULT 0, min_odds REAL)
    """)
    c.commit()
    monkeypatch.setattr(sh, "get_connection", lambda: _Shim(path))
    yield c
    c.close()


def _results(name):
    return {r["check_name"]: r for r in sh.run_system_health()["results"]}[name]


def _add_run(c, kind="hourly", started=60, finished=59, failed=None, total=24):
    c.execute(
        "INSERT INTO pipeline_runs (run_id, run_kind, started_at, finished_at,"
        " steps_total, steps_failed, failed_steps, ok) VALUES (?,?,?,?,?,?,?,?)",
        (uuid.uuid4().hex, kind, _iso(started),
         None if finished is None else _iso(finished),
         total, len(failed or []), ",".join(failed or []) or None, not failed))
    c.commit()


# ── refresh_pass_completion ──────────────────────────────────────────────────

class TestPassCompletion:
    def test_no_ledger_rows_is_empty(self, db):
        assert _results("refresh_pass_completion")["status"] == sh.EMPTY

    def test_first_pass_in_flight_is_not_a_failure(self, db):
        """The health check runs as a STEP, before the pass calls finish_run --
        so the very first pass has a started row and no finished one."""
        _add_run(db, started=5, finished=None)
        assert _results("refresh_pass_completion")["status"] == sh.SKIPPED

    def test_recent_finish_is_never_stale(self, db):
        _add_run(db, started=20, finished=19)
        assert _results("refresh_pass_completion")["status"] in (sh.OK, sh.SKIPPED)

    def test_stale_finish_is_never_ok(self, db):
        """The property that matters, independent of the ET pass window: a pass
        that last completed hours ago must never report healthy."""
        _add_run(db, started=400, finished=395)
        assert _results("refresh_pass_completion")["status"] != sh.OK

    def test_run_that_never_finished_is_caught(self, db):
        """A hang, an OOM or a worker killed mid-pass leaves finished_at NULL --
        the only way that becomes visible rather than silent."""
        _add_run(db, started=20, finished=19)
        _add_run(db, started=400, finished=None)
        assert _results("refresh_pass_completion")["status"] != sh.OK


# ── refresh_pass_steps ───────────────────────────────────────────────────────

class TestPassSteps:
    def test_too_few_passes_to_judge(self, db):
        for _ in range(2):
            _add_run(db)
        assert _results("refresh_pass_steps")["status"] == sh.SKIPPED

    def test_clean_passes_are_ok(self, db):
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i)
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.OK, "CRIT")

    def test_persistent_failure_is_crit_and_names_the_step(self, db):
        """The exact shape of the 8/24-8/27 outage."""
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i,
                     failed=["wnba-prop-scoring"])
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")
        assert "wnba-prop-scoring" in r["detail"]

    def test_intermittent_failure_warns_but_is_not_crit(self, db):
        """A flaky upstream API must not redden every run."""
        _add_run(db, started=62, finished=61, failed=["golf-odds"])
        for i in range(2):
            _add_run(db, started=60 + i, finished=59 + i)
        r = _results("refresh_pass_steps")
        assert r["severity"] == "WARN"
        assert "golf-odds" in r["detail"]

    def test_daily_runs_do_not_count_as_refresh_passes(self, db):
        for i in range(3):
            _add_run(db, kind="daily", started=60 + i, finished=59 + i)
        assert _results("refresh_pass_steps")["status"] == sh.SKIPPED


# ── signal_delivery ──────────────────────────────────────────────────────────

def _add_signal(c, *, sport="MLB", model="mlb_moneyline", locked=200,
                prob=0.80, edge=0.15, suffix="", delivered=False,
                paused=0, prob_only=0, min_prob=0.70, min_edge=0.10,
                void=False, game_date=None, commence=None, opening_only=False):
    c.execute("INSERT OR REPLACE INTO model_action_thresholds"
              " (model_id, min_prob, min_edge, prob_only, paused, min_odds)"
              " VALUES (?,?,?,?,?,NULL)", (model, min_prob, min_edge, prob_only, paused))
    today = today_et()
    if game_date is None:
        game_date = today
    game_id = f"G1{suffix}"
    lock_key = f"{game_id}:{model}"
    created = _iso(locked)
    if commence is not None:
        c.execute(
            "INSERT OR REPLACE INTO games (game_id, sport, season, game_date,"
            " home_team, away_team, commence_time) VALUES (?,?,?,?,?,?,?)",
            (game_id, sport, 2026, game_date, "HOME", "AWAY", commence))
    if not opening_only:
        c.execute(
            "INSERT INTO picks (game_id, model_id, sport, game_date,"
            " pick_side, pick_label, model_probability, dk_implied_prob,"
            " edge, kelly_fraction, recommended_bet, bankroll_at_pick,"
            " signal_type, condition_status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (game_id, model, sport, game_date, "home", "Test pick",
             prob, 0.50, edge, 0.02, 20.0, 1000.0, "BET",
             "VOID" if void else None, created))
    # Capture-table leftover: the 2026-09-14 false CRIT was nine opening_signals
    # rows whose picks (and push_sent rows) mike deleted on 2026-09-11.
    c.execute(
        "INSERT INTO opening_signals (lock_key, game_id, model_id, sport,"
        " game_date, pick_side, pick_label, model_probability, edge, locked_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?)",
        (lock_key, game_id, model, sport, game_date, "home", "Test pick",
         prob, edge, created))
    if delivered:
        c.execute("INSERT INTO push_sent (lock_key, kind, sent_at)"
                  " VALUES (?, 'discord_signal', ?)", (lock_key, created))
    c.commit()
    return lock_key


@pytest.fixture
def mlb_wired(monkeypatch):
    import config
    monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {"MLB": "https://x"}, raising=False)
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)


class TestSignalDelivery:
    def test_skipped_when_no_webhook_configured(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)
        _add_signal(db)
        assert _results("signal_delivery")["status"] == sh.SKIPPED

    def test_undelivered_signal_is_crit(self, db, mlb_wired):
        _add_signal(db, delivered=False)
        r = _results("signal_delivery")
        assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")

    def test_delivered_signal_is_ok(self, db, mlb_wired):
        _add_signal(db, delivered=True)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_just_locked_signal_gets_a_grace_window(self, db, mlb_wired):
        """A signal locked minutes ago has not had a pass yet."""
        _add_signal(db, locked=5, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_sport_without_a_channel_is_not_counted(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {"NFL": "https://x"}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "", raising=False)
        _add_signal(db, sport="MLB", delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_default_channel_covers_every_sport(self, db, monkeypatch):
        import config
        monkeypatch.setattr(config, "DISCORD_WEBHOOKS", {}, raising=False)
        monkeypatch.setattr(config, "DISCORD_WEBHOOK_DEFAULT", "https://x", raising=False)
        _add_signal(db, sport="NHL", model="nhl_moneyline", delivered=False)
        assert _results("signal_delivery")["status"] == sh.STALE

    def test_paused_model_is_not_postable(self, db, mlb_wired):
        _add_signal(db, paused=1, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_below_threshold_is_not_postable(self, db, mlb_wired):
        _add_signal(db, prob=0.55, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_capture_table_leftover_is_not_a_delivery_failure(self, db, mlb_wired):
        """The 2026-09-14 CRIT. Nine opening_signals rows, no standing pick,
        no discord_signal ledger row -- because mike deleted the picks and
        cleared push_sent on 2026-09-11 so a re-fire would announce. Capture
        is the CLV shadow track; Discord publishes from picks. A leftover
        here is not an outage."""
        _add_signal(db, opening_only=True, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_void_pick_is_not_postable(self, db, mlb_wired):
        """A VOIDED pick is not publishable (CLAUDE.md §1c). The notifier
        excludes it; the delivery check must too."""
        _add_signal(db, void=True, delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_lookahead_pick_outside_the_game_date_window_still_counts(self, db, mlb_wired):
        """The notifier has no date horizon. A pick written today for a game
        next week is postable now; waiting for its game_date to enter the
        3-day window is how a look-ahead outage stays green until kickoff."""
        future = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        _add_signal(db, game_date="2099-01-01", commence=future, delivered=False)
        assert _results("signal_delivery")["status"] == sh.STALE

    def test_a_started_undelivered_pick_is_not_a_standing_crit(self, db, mlb_wired):
        """The 2026-09-15 CRIT. Five MLB props (Lodolo / Alcantara / Campusano /
        Bogaerts / Cronenworth) were written pre-commence, never posted, then
        first pitch passed. `_new_signals` will not announce a started game, so
        holding CRIT until the 3-day window ages out is a false alarm nobody
        can action. A live outage still CRITs via the pre-commence cases
        above."""
        _add_signal(db, locked=200, commence=_iso(50), delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_pick_written_after_first_pitch_is_not_a_delivery_failure(self, db, mlb_wired):
        """Same first-pitch guard as _deliverable, now on picks.created_at."""
        _add_signal(db, locked=200, commence=_iso(400), delivered=False)
        assert _results("signal_delivery")["status"] == sh.OK

    def test_delivery_check_reads_picks_not_the_capture_table(self):
        """Source pin. The check claimed it used the notifier predicate while
        still SELECTing from opening_signals -- that is the disagreement this
        file exists to stop. Scoped to the signal_delivery block so the
        capture check, which should keep reading opening_signals, is free."""
        src = (Path(__file__).parent.parent / "tracking"
               / "system_health.py").read_text(encoding="utf-8")
        start = src.index("# ── Signal delivery")
        block = src[start:src.index("# ── Published picks", start)]
        assert "FROM picks p" in block
        assert "FROM opening_signals" not in block
        assert "opening_signals" not in block.split("SELECT", 1)[1]
        assert "still_pre_game" in block


# ── run_ledger ───────────────────────────────────────────────────────────────

class TestRunLedger:
    """The ledger is observability: it must record accurately, and it must never
    be able to break the pass it is observing."""

    def _wire(self, monkeypatch, path):
        import tracking.run_ledger as rl
        monkeypatch.setattr(rl, "get_connection", lambda: _Shim(path))
        return rl

    def test_creates_its_own_table(self, monkeypatch):
        """Supabase MCP is read-only and setup_database() only runs at first-time
        setup, so the ledger creates the table itself rather than needing a
        manual migration."""
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()               # empty DB, no tables at all
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("hourly")
        rows = sqlite3.connect(path).execute(
            "SELECT run_kind, finished_at FROM pipeline_runs WHERE run_id = ?",
            (run_id,)).fetchall()
        assert rows == [("hourly", None)]

    def test_finish_records_failed_steps(self, monkeypatch):
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("hourly")
        rl.finish_run(run_id, 24, ["wnba-prop-scoring", "golf-odds"])
        total, failed, names, ok = sqlite3.connect(path).execute(
            "SELECT steps_total, steps_failed, failed_steps, ok FROM pipeline_runs"
            " WHERE run_id = ?", (run_id,)).fetchone()
        assert (total, failed, names) == (24, 2, "wnba-prop-scoring,golf-odds")
        assert not ok

    def test_clean_pass_is_marked_ok(self, monkeypatch):
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()
        rl = self._wire(monkeypatch, path)
        run_id = rl.start_run("evening")
        rl.finish_run(run_id, 22, [])
        failed, names, ok = sqlite3.connect(path).execute(
            "SELECT steps_failed, failed_steps, ok FROM pipeline_runs WHERE run_id = ?",
            (run_id,)).fetchone()
        assert (failed, names, bool(ok)) == (0, None, True)

    def test_table_is_created_locked_down(self, monkeypatch):
        """The ledger creates its own table, so IT is what has to apply the RLS
        that data/supabase_schema.sql specifies for pipeline_runs.

        Because it did not, production ran with anon holding SELECT + INSERT +
        UPDATE + DELETE on the ledger recording whether the pipeline ran at all
        (found 2026-08-29, ERROR-level rls_disabled_in_public). A table created
        at runtime never passes through a migration, so nothing else can do it.
        """
        import tracking.run_ledger as rl
        issued: list[str] = []

        class _Recorder:
            def execute(self, sql, params=None):
                issued.append(" ".join(sql.split()))
                return self
            def fetchone(self): return None
            def fetchall(self): return []
            def commit(self): pass
            def rollback(self): pass
            def close(self): pass

        rl._ensure_table(_Recorder())
        joined = " | ".join(issued).lower()
        assert "enable row level security" in joined, \
            "pipeline_runs must be created with RLS on"
        assert "revoke all on pipeline_runs from anon, authenticated" in joined, \
            "revoke must name the roles — a PUBLIC-only revoke is a no-op here"

    def test_lockdown_failure_never_blocks_the_ledger(self, monkeypatch):
        """RLS statements are Postgres-only and no-op on SQLite. A backend that
        rejects them must still get its ledger row — observability may never be
        able to break the thing it observes."""
        path = tempfile.mktemp(suffix=".db")
        sqlite3.connect(path).close()
        rl = self._wire(monkeypatch, path)          # _Shim has no rollback()
        run_id = rl.start_run("hourly")
        rows = sqlite3.connect(path).execute(
            "SELECT run_kind FROM pipeline_runs WHERE run_id = ?", (run_id,)).fetchall()
        assert rows == [("hourly",)]

    def test_db_failure_never_raises(self, monkeypatch):
        """A dead database must not take the pass down with it."""
        import tracking.run_ledger as rl

        def boom():
            raise RuntimeError("database is on fire")

        monkeypatch.setattr(rl, "get_connection", boom)
        run_id = rl.start_run("hourly")     # still returns a usable id
        assert isinstance(run_id, str) and run_id
        rl.finish_run(run_id, 24, ["x"])    # and does not raise

    def test_finish_with_no_run_id_is_a_noop(self, monkeypatch):
        """The shell passes "" when `start` could not reach the DB."""
        import tracking.run_ledger as rl
        monkeypatch.setattr(rl, "get_connection",
                            lambda: (_ for _ in ()).throw(AssertionError("should not connect")))
        rl.finish_run("", 24, [])


class TestHealthCheckIsNotCountedAsAFailingStep:
    """`health-check` is not a producer. Until 2026-09-14 the refresh --step
    path returned False on any CRIT, so counting it in refresh_pass_steps
    created a loop that could never clear: the check CRITs -> the health
    step fails -> the check CRITs again next pass, forever, whether or not
    the original cause was fixed. Observed live on 2026-08-27 and again
    2026-09-12..14. Refresh no longer fails the step; this exclusion stays
    for historical rows still inside the window."""

    def test_health_check_alone_does_not_trip_the_persistent_failure_alarm(self, db):
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i, failed=["health-check"])
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.OK, "CRIT"), (
            "a health-check-only failure is the aggregate CRIT signal echoing "
            "back, not an independent broken step")

    def test_a_real_step_is_still_caught_alongside_health_check(self, db):
        """The exclusion must not blind the check to the failure that matters."""
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i,
                     failed=["health-check", "wnba-prop-scoring"])
        r = _results("refresh_pass_steps")
        assert (r["status"], r["severity"]) == (sh.STALE, "CRIT")
        assert "wnba-prop-scoring" in r["detail"]
        assert "health-check" not in r["detail"]

    def test_the_loop_clears_once_the_real_cause_is_fixed(self, db):
        """The property the loop violated: after the underlying CRIT is
        resolved, this check must be able to return to OK."""
        for i in range(3):
            _add_run(db, started=60 + i, finished=59 + i, failed=["health-check"])
        assert _results("refresh_pass_steps")["status"] == sh.OK


class TestSavantFreshnessQueryDoesNotAbortTheRun:
    """The savant_freshness check's `where` clause must be valid SQL. A
    malformed one (missing the WHERE keyword, shipped 2026-08-31) doesn't just
    fail its own check: on Postgres a bad statement aborts the transaction, so
    every check dispatched afterward raises too and run_system_health() never
    reaches its upsert. Diagnosed 2026-09-02 after system_health_checks sat
    stale for ~41h behind a pipeline that just logged "step returned False"
    on every single pass, with no further detail."""

    def _seed_savant(self, db, season):
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for player_type in ("batter", "pitcher"):
            db.execute(
                "INSERT INTO player_savant_stats "
                "(player_id, player_name, player_type, season, as_of_date) "
                "VALUES (?,?,?,?,?)",
                (f"p-{player_type}", "Test Player", player_type, season, today))
        db.commit()

    def test_savant_freshness_is_not_an_error(self, db):
        self._seed_savant(db, datetime.now(timezone.utc).year)
        r = _results("savant_freshness")
        assert r["status"] != sh.ERROR, r["detail"]

    def test_a_later_check_still_runs_after_savant_freshness(self, db):
        """A broken date_check() must not silently blank out every check that
        runs after it in the same pass — the actual shape of the outage."""
        self._seed_savant(db, datetime.now(timezone.utc).year)
        results = sh.run_system_health()["results"]
        names = {row["check_name"] for row in results}
        assert "schema_drift" in names, (
            "schema_drift runs late in run_system_health(); its absence is "
            "exactly what the 08-31 cascade looked like")


# ── mlb_bullpen_workload / mlb_team_stats / umpires overnight window ────────

class _FrozenDatetime(datetime):
    """Freezes datetime.now(); every other classmethod (strptime, etc.) is
    inherited unchanged. Swapped into `sh.datetime` for one test only.
    """
    _frozen = None

    @classmethod
    def now(cls, tz=None):
        return cls._frozen.astimezone(tz) if tz else cls._frozen


class TestDailyOnlyFeedsOvernightWindow:
    """mlb_team_stats, mlb_bullpen_workload and umpires are written ONLY by
    the once-daily 6am ET run (Steps 0d/3/3b/5c) — refresh_pass.sh's hourly
    steps never touch them. This health check runs on every hourly pass too,
    so before the daily run has had a chance to complete, checking "today" /
    "yesterday" against a table that has not been touched yet is checking
    something that cannot possibly be true. Measured 2026-09-08: all three
    fired STALE/CRIT on 6 straight overnight hourly passes, self-healing
    within minutes of the 6am run reaching their step every single time —
    a false alarm, not a feed problem.
    """

    def _freeze(self, monkeypatch, et_hour: int):
        from zoneinfo import ZoneInfo
        today = today_et()
        d = datetime.strptime(today, "%Y-%m-%d")
        frozen = d.replace(hour=et_hour, tzinfo=ZoneInfo("America/New_York"))
        _FrozenDatetime._frozen = frozen
        monkeypatch.setattr(sh, "datetime", _FrozenDatetime)
        return today

    def _seed_yesterday_finals(self, db, today):
        yday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO games (game_id, sport, season, game_date, home_team,"
            " away_team, home_score, away_score) VALUES (?,'MLB',2026,?,?,?,4,2)",
            ("g1", yday, "NYY", "BOS"))
        db.commit()
        return yday

    def test_bullpen_stale_two_days_is_not_an_overnight_false_alarm(self, db, monkeypatch):
        """Data genuinely 3+ days behind must still CRIT, even inside the
        overnight window — the relaxation covers exactly one day, not staleness
        in general."""
        today = self._freeze(monkeypatch, et_hour=3)
        yday = self._seed_yesterday_finals(db, today)
        stale_date = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=4)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO mlb_bullpen_stats (game_date, season, team, game_pk,"
            " player_id, ip) VALUES (?,2026,'NYY',1,100,1.0)", (stale_date,))
        db.commit()
        assert _results("mlb_bullpen_workload")["status"] == sh.STALE

    def test_bullpen_one_day_behind_is_ok_before_the_daily_run(self, db, monkeypatch):
        """3am ET: yesterday's bullpen data has not been ingested yet (the 6am
        run owns that), so 'the day before yesterday' is the honest floor."""
        today = self._freeze(monkeypatch, et_hour=3)
        self._seed_yesterday_finals(db, today)
        day2 = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO mlb_bullpen_stats (game_date, season, team, game_pk,"
            " player_id, ip) VALUES (?,2026,'NYY',1,100,1.0)", (day2,))
        db.commit()
        assert _results("mlb_bullpen_workload")["status"] == sh.OK

    def test_bullpen_same_lag_is_stale_after_the_daily_run(self, db, monkeypatch):
        """9am ET: the daily run has already had its chance. The exact same
        'day before yesterday' data that was OK at 3am is stale now."""
        today = self._freeze(monkeypatch, et_hour=9)
        self._seed_yesterday_finals(db, today)
        day2 = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")
        db.execute(
            "INSERT INTO mlb_bullpen_stats (game_date, season, team, game_pk,"
            " player_id, ip) VALUES (?,2026,'NYY',1,100,1.0)", (day2,))
        db.commit()
        assert _results("mlb_bullpen_workload")["status"] == sh.STALE

    def test_team_stats_yesterday_is_ok_before_the_daily_run(self, db, monkeypatch):
        today = self._freeze(monkeypatch, et_hour=3)
        db.execute("INSERT INTO games (game_id, sport, season, game_date,"
                   " home_team, away_team) VALUES ('g2','MLB',2026,?,'NYY','BOS')",
                   (today,))
        yday = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
        db.execute("INSERT INTO mlb_team_stats (team, season, as_of_date)"
                   " VALUES ('NYY',2026,?)", (yday,))
        db.commit()
        assert _results("mlb_team_stats")["status"] == sh.OK

    def test_umpires_two_days_behind_is_ok_before_the_daily_run(self, db, monkeypatch):
        today = self._freeze(monkeypatch, et_hour=3)
        self._seed_yesterday_finals(db, today)
        day2 = (datetime.strptime(today, "%Y-%m-%d") - timedelta(days=2)).strftime("%Y-%m-%d")
        db.execute("INSERT INTO umpires (game_id, game_date, umpire_name)"
                   " VALUES ('g-ump',?,'Test Ump')", (day2,))
        db.commit()
        assert _results("umpires")["status"] == sh.OK
