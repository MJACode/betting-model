"""The alerter has one job: a failure reaches a person.

The gap it closes is not detection. `tracking/system_health.py` had already
written "[WARN] refresh_pass_steps: STALE" on 2026-09-06 while `odds` — the
step that fetches the lines every model prices against — was dying with
EMAXCONNSESSION. It wrote it to a table and to the log, and 32 of 50 passes
failed before a person queried `pipeline_runs` by hand and noticed.

So these tests are about DELIVERY and about not becoming noise: the throttle,
the recovery, and the rule that nothing is stamped unless the post confirmed.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import failure_alerter as fa  # noqa: E402

NOW = datetime(2026, 9, 6, 23, 0, tzinfo=timezone.utc)


class FakeConn:
    """Answers the three queries the alerter makes, by shape.

    Heartbeats default to FRESH for every watched job, so a test about health
    checks or the clean rate is not also silently a test about job silence.
    """

    def __init__(self, health=(), runs=(), beats=None):
        self._health, self._runs, self._last = health, runs, None
        if beats is None:
            from datetime import timedelta as _td

            from tracking.job_heartbeat import MAX_SILENCE
            # Stamped ahead of every clock these tests use, so no test about
            # health checks or the clean rate is ALSO a test about job silence.
            fresh = (NOW + _td(days=1)).isoformat()
            beats = [(j, fresh) for j in MAX_SILENCE]
        self._beats = beats

    def execute(self, sql, params=()):
        if "system_health_checks" in sql:
            self._last = "health"
        elif "job_heartbeats" in sql:
            self._last = "beats"
        elif "FROM games g" in sql:    # the undecided-game read: nothing tipped
            self._last = "tipped"
        elif "FROM nba_schedule s" in sql or "FROM picks p" in sql:    # the NBA prop watch: nothing
            self._last = "tipped"
        else:
            self._last = "runs"
        return self

    def fetchall(self):
        return list({"health": self._health, "beats": self._beats, "tipped": []}.get(
            self._last, self._runs))


def _state_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("WATCHDOG_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)


def _posts(monkeypatch, ok=True):
    """Capture ops posts instead of sending them."""
    sent = []

    def _fake(title, detail, *, recovery=False):
        sent.append({"title": title, "detail": detail, "recovery": recovery})
        return ok

    monkeypatch.setattr(fa, "post_ops_alert", _fake)
    return sent


def _clean_runs(n=12):
    return [(True, None)] * n


class TestWhatCountsAsAFailure:
    def test_a_stale_check_is_a_condition(self):
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "no snapshot in 6h")],
                        runs=_clean_runs())
        c = fa._conditions(conn)
        assert "health:odds_dk_lines" in c
        assert c["health:odds_dk_lines"][0] == "CRIT"

    def test_ok_and_skipped_are_not(self):
        # SKIPPED is usually legitimate — no golf tournament, no NBA games —
        # and alerting on it would bury the channel out of season.
        conn = FakeConn(health=[("a", "OK", "CRIT", ""), ("b", "SKIPPED", "WARN", "")],
                        runs=_clean_runs())
        assert fa._conditions(conn, NOW) == {}

    def test_severity_carries_through(self):
        conn = FakeConn(health=[("x", "STALE", "WARN", "flaky upstream")],
                        runs=_clean_runs())
        assert fa._conditions(conn)["health:x"][0] == "WARN"

    def test_the_clean_rate_rule_fires_on_the_measured_incident(self):
        # 2026-09-06 as measured: 1 of the last 12 passes clean, `odds` in 5.
        runs = [(False, "odds,public-betting")] * 5 + [(False, "lineups")] * 6 \
            + [(True, None)]
        conn = FakeConn(health=[], runs=runs)
        c = fa._conditions(conn)
        assert "pass:clean_rate" in c
        sev, title, detail = c["pass:clean_rate"]
        assert sev == "CRIT"
        assert "1/12" in title
        assert "`odds`" in detail          # names the worst offender

    def test_a_healthy_board_is_silent(self):
        conn = FakeConn(health=[("a", "OK", "CRIT", "")], runs=_clean_runs())
        assert fa._conditions(conn, NOW) == {}

    def test_the_floor_sits_below_a_normal_day(self):
        # Measured 2026-09-04 and 09-05: 0.64 and 0.69 clean. A threshold that
        # fires on a normal day is a threshold that gets muted.
        assert fa.CLEAN_RATE_FLOOR < 0.64

    def test_too_few_passes_to_judge_says_nothing(self):
        conn = FakeConn(health=[], runs=[(False, "odds")] * 3)
        assert "pass:clean_rate" not in fa._conditions(conn)


class TestDeliveryAndNoise:
    def test_a_new_condition_alerts(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        r = fa.run_failure_alerter(conn=conn, now=NOW)
        assert r["alerted"] == ["health:odds_dk_lines"]
        assert len(sent) == 1 and sent[0]["recovery"] is False

    def test_the_same_condition_does_not_alert_again_immediately(
            self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        r = fa.run_failure_alerter(conn=conn, now=NOW + timedelta(minutes=10))
        assert r["alerted"] == []
        assert len(sent) == 1, "a standing failure must not post every tick"

    def test_it_alerts_again_after_the_renotify_window(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        later = NOW + timedelta(minutes=fa.RENOTIFY_CRIT_MIN + 1)
        r = fa.run_failure_alerter(conn=conn, now=later)
        assert r["alerted"] == ["health:odds_dk_lines"]
        assert len(sent) == 2

    def test_warn_is_throttled_harder_than_crit(self):
        # A WARN repeating at CRIT's cadence is how a channel stops being read.
        assert fa.RENOTIFY_WARN_MIN > fa.RENOTIFY_CRIT_MIN

    def test_a_cleared_condition_posts_a_recovery_once(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        bad = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                       runs=_clean_runs())
        good = FakeConn(health=[("odds_dk_lines", "OK", "CRIT", "fine")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=bad, now=NOW)
        r = fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=10))
        assert r["recovered"] == ["health:odds_dk_lines"]
        assert sent[-1]["recovery"] is True
        # ...and not again on the next quiet pass.
        r2 = fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=20))
        assert r2["recovered"] == []

    def test_a_healthy_first_run_announces_nothing(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        conn = FakeConn(health=[("a", "OK", "CRIT", "")], runs=_clean_runs())
        r = fa.run_failure_alerter(conn=conn, now=NOW)
        assert sent == [] and r["alerted"] == [] and r["recovered"] == []

    def test_a_failed_post_does_not_stamp_the_throttle(self, monkeypatch, tmp_path):
        # Stamping on a POST that never landed would silence the next two hours
        # on the strength of a message nobody received (§7).
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch, ok=False)
        conn = FakeConn(health=[("odds_dk_lines", "STALE", "CRIT", "stale")],
                        runs=_clean_runs())
        fa.run_failure_alerter(conn=conn, now=NOW)
        r = fa.run_failure_alerter(conn=conn, now=NOW + timedelta(minutes=1))
        assert r["alerted"] == []          # still not confirmed
        assert len(sent) == 2, "an unconfirmed alert must be retried"

    def test_a_flapping_condition_alerts_on_each_new_occurrence(
            self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        sent = _posts(monkeypatch)
        bad = FakeConn(health=[("x", "STALE", "CRIT", "d")], runs=_clean_runs())
        good = FakeConn(health=[("x", "OK", "CRIT", "")], runs=_clean_runs())
        fa.run_failure_alerter(conn=bad, now=NOW)
        fa.run_failure_alerter(conn=good, now=NOW + timedelta(minutes=10))
        r = fa.run_failure_alerter(conn=bad, now=NOW + timedelta(minutes=20))
        assert r["alerted"] == ["health:x"], (
            "recovery must clear the throttle, or a flapping failure is "
            "announced once and then silently repeats")


class TestItCannotBreakTheWorker:
    def test_a_dead_database_is_reported_not_raised(self, monkeypatch, tmp_path):
        _state_dir(monkeypatch, tmp_path)
        _posts(monkeypatch)

        class Boom:
            def execute(self, *a, **k):
                raise RuntimeError("connection refused")

        r = fa.run_failure_alerter(conn=Boom(), now=NOW)
        assert r["conditions"] == []

    def test_the_watchdog_still_owns_outage_detection(self):
        # This module reads the database to do its job, so during a real
        # outage it can say nothing. The watchdog covers exactly that case and
        # holds no database dependency on its alerting path — duplicating it
        # here would make a second, weaker copy of the one check that has to
        # work when everything else does not.
        src = (Path(__file__).parent.parent / "tracking"
               / "heartbeat_watchdog.py").read_text(encoding="utf-8")
        assert "db_unreachable" in src

    def test_the_scheduler_runs_it_and_never_lets_it_raise(self):
        src = (Path(__file__).parent.parent / "scheduler.py").read_text(
            encoding="utf-8")
        assert 'id="failure_alerter"' in src
        block = src[src.index("def run_failure_alerter() -> None:"):]
        block = block[:block.index("\ndef ", 10)]
        assert "except Exception" in block


class TestSilentJobs:
    """A job whose correct output is often NOTHING cannot be watched by
    watching its output. The NFL polls write a pick only when one qualifies,
    so before this a dead poll and a quiet market were identical.
    """

    def test_a_silent_job_is_a_critical_condition(self):
        from datetime import timedelta as _td
        old = (NOW - _td(hours=6)).isoformat()
        conn = FakeConn(health=[], runs=_clean_runs(),
                        beats=[("nfl_opener_poll", old)])
        c = fa._conditions(conn, NOW)
        assert "job:nfl_opener_poll" in c
        sev, title, detail = c["job:nfl_opener_poll"]
        assert sev == "CRIT"
        assert "silent" in title
        assert "360" in detail or "minutes ago" in detail

    def test_a_job_with_no_row_is_NOT_reported(self):
        """Two very different things produce no row: a job DISABLED on this
        deployment (RUN_NFL_LIVE=0 never registers) and a fresh deploy where
        nothing has ticked yet. Alerting on either means a burst of false
        alarms every deploy plus a permanent alarm per switched-off job.

        The scheduler seeds a row at REGISTRATION, so "has a row and has gone
        quiet" means "was registered and has stopped" — which is the condition
        worth waking someone for."""
        conn = FakeConn(health=[], runs=_clean_runs(), beats=[])
        assert [k for k in fa._conditions(conn, NOW) if k.startswith("job:")] == []

    def test_a_seeded_job_that_never_ticks_still_goes_stale(self):
        """Seeding must not become a permanent excuse: a job registered and
        then never run is exactly the silent failure this exists for."""
        from datetime import timedelta as _td
        seeded_long_ago = (NOW - _td(hours=3)).isoformat()
        conn = FakeConn(health=[], runs=_clean_runs(),
                        beats=[("nfl_opener_poll", seeded_long_ago)])
        assert "job:nfl_opener_poll" in fa._conditions(conn, NOW)

    def test_fresh_jobs_are_silent(self):
        conn = FakeConn(health=[], runs=_clean_runs())
        assert [k for k in fa._conditions(conn, NOW) if k.startswith("job:")] == []

    def test_the_jobs_with_no_output_check_are_watched(self):
        # The three the 2026-09-06 audit found uncovered, plus the watcher.
        from tracking.job_heartbeat import MAX_SILENCE
        for j in ("nfl_opener_poll", "nfl_poll_hourly", "nfl_live_worker",
                  "failure_alerter"):
            assert j in MAX_SILENCE, j

    def test_the_overnight_gap_does_not_trip_the_in_play_worker(self):
        # nfl_live_worker runs 9am-midnight ET, so ~9h of silence is correct
        # behaviour and must not alert.
        from tracking.job_heartbeat import MAX_SILENCE
        assert MAX_SILENCE["nfl_live_worker"] > 9 * 60


class TestHealthCheckOnlyIsNotADirtyPass:
    """Observability is not a producer. A refresh whose only failed step is
    health-check is the identity of a clean pass: odds/score/settle ran.

    Measured 2026-09-14 last-12 non-daily (Supabase `pipeline_runs`):
    1 ok, 9 failed_steps='health-check', 2 'aborted' → 1/12 under the 0.50
    floor. After this, that window is 10/12 and silent. `aborted` stays
    dirty: deploy-replace and hang share one sentinel.
    """

    def test_health_check_only_is_identity_with_a_clean_pass(self):
        runs = [(False, "health-check")] * 12
        conn = FakeConn(health=[], runs=runs)
        clean, total, ranked = fa._clean_rate(conn)
        assert (clean, total) == (12, 12)
        assert ranked == []
        assert "pass:clean_rate" not in fa._conditions(conn)

    def test_underscore_health_check_is_the_same_identity(self):
        runs = [(False, "health_check")] * 12
        clean, total, ranked = fa._clean_rate(FakeConn(health=[], runs=runs))
        assert (clean, total) == (12, 12)
        assert ranked == []

    def test_a_real_step_alongside_health_check_is_still_dirty(self):
        runs = [(False, "odds,health-check")] * 12
        clean, total, ranked = fa._clean_rate(FakeConn(health=[], runs=runs))
        assert (clean, total) == (0, 12)
        assert ranked == [("odds", 12)]
        assert "pass:clean_rate" in fa._conditions(FakeConn(health=[], runs=runs))

    def test_aborted_still_counts_as_dirty(self):
        """No column distinguishes deploy-replace from a hang; a pass that
        did not finish did not produce what the pass produces."""
        runs = [(False, "aborted")] * 12
        conn = FakeConn(health=[], runs=runs)
        clean, total, ranked = fa._clean_rate(conn)
        assert (clean, total) == (0, 12)
        assert ranked == [("aborted", 12)]
        assert "pass:clean_rate" in fa._conditions(conn)

    def test_an_empty_failed_steps_map_on_a_failed_row_is_dirty(self):
        """Identity: we do not invent a health-check excuse for an unknown
        failure."""
        runs = [(False, None)] * 12
        clean, total, ranked = fa._clean_rate(FakeConn(health=[], runs=runs))
        assert (clean, total) == (0, 12)
        assert ranked == []

    def test_the_measured_2026_09_14_window_is_silent_after_decoupling(self):
        # Last 12 as queried 2026-09-14T12:26Z: 1 clean, 2 aborted,
        # 9 health-check-only.
        runs = (
            [(True, None)]
            + [(False, "aborted")]
            + [(False, "health-check")] * 9
            + [(False, "aborted")]
        )
        assert len(runs) == 12
        conn = FakeConn(health=[], runs=runs)
        clean, total, ranked = fa._clean_rate(conn)
        assert (clean, total) == (10, 12)
        assert ranked == [("aborted", 2)]
        assert 10 / 12 >= fa.CLEAN_RATE_FLOOR
        assert "pass:clean_rate" not in fa._conditions(conn)

    def test_an_empty_window_is_identity(self):
        assert fa._clean_rate(FakeConn(health=[], runs=[])) == (0, 0, [])


# ── a real-money model that lost a game ──────────────────────────────────────

class NbaConn(FakeConn):
    """Answers the undecided-game read by shape, with the real SQL running against
    what a test stores: games, the schedule, each model's decisions and BETs. A
    table not in `tables` does not exist yet."""

    ALL = ("nba_total_luck_decisions", "nba_team_total_luck_decisions",
           "nba_first_half_total_luck_decisions", "nba_q1_trend_decisions")

    def __init__(self, games=(), decisions=None, bets=(), tables=ALL, health=(), boom=False,
                 rule_decided=None, listed=(), sched=(), open_bets=(), other_rows=(), watch_boom=False):
        super().__init__(health=health, runs=_clean_runs())
        self._games, self._decisions = list(games), decisions or {}
        self._bets, self._tables, self._boom = list(bets), set(tables), boom
        # None: nba_prop_market has decided every game asked about, so a test about another
        # model reads only that model's alert
        self._rule_decided, self._listed, self._sched = rule_decided, list(listed), list(sched)
        self._open_bets, self._other_rows, self._watch_boom = list(open_bets), set(other_rows), watch_boom
        self._rows = None
        self.rollbacks = 0

    def execute(self, sql, params=()):
        self._rows = None
        if "FROM games g" in sql:
            if self._boom:
                raise RuntimeError("the read failed")
            self._rows = self._games
        elif "FROM nba_schedule s" in sql:
            if self._watch_boom:
                raise RuntimeError("the watch's read failed")
            self._rows = self._sched if "in_games" in sql else self._listed
        elif "FROM nba_schedule" in sql:
            self._rows = [(2027, "2026-10-21", "regular"), (2027, "2027-04-11", "regular")]
        elif "SELECT game_id FROM nba_prop_market_decisions" in sql:
            self._rows = [(g,) for g in params[0]
                          if self._rule_decided is None or g in self._rule_decided]
        elif "SELECT game_id FROM games WHERE game_id" in sql:
            self._rows = [(g,) for g in params[0] if g in self._other_rows]
        elif "FROM picks p" in sql:
            self._rows = self._open_bets
        elif "information_schema.tables" in sql:
            self._rows = [(1,)] if params[0] in self._tables else []
        elif "_decisions WHERE game_id" in sql:
            table = next(t for t in self.ALL if t in sql)
            self._rows = [(g,) for g in self._decisions.get(table, ())]
        elif "FROM picks" in sql:
            model = params[0]
            self._rows = [(g,) for m, g in self._bets if m == model]
        else:
            return super().execute(sql, params)
        return self

    def fetchall(self):
        if self._rows is not None:
            return list(self._rows)
        return super().fetchall()

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def rollback(self):
        self.rollbacks += 1


GAME = "NBA_2026-10-30_DEN_PHX"
TIPPED = (GAME, "PHX", "DEN", "2026-10-30", 2027, (NOW - timedelta(hours=2)).isoformat(),
          None, "regular")


def _decided_by(*tables):
    return {t: [GAME] for t in tables}


class TestAModelThatLostAGame:
    def test_a_tipped_game_with_no_team_total_decision_is_critical_and_names_the_game(self):
        conn = NbaConn([TIPPED], _decided_by("nba_total_luck_decisions",
                                             "nba_first_half_total_luck_decisions",
                                             "nba_q1_trend_decisions"))
        out = fa._conditions(conn, NOW)
        assert [k for k in out if k.startswith("undecided:")] == ["undecided:nba_team_total_luck"]
        sev, title, detail = out["undecided:nba_team_total_luck"]
        assert sev == "CRIT"
        assert GAME in detail and "nba_team_total_luck" in title

    def test_each_model_is_named_on_its_own(self):
        out = fa._conditions(NbaConn([TIPPED]), NOW)
        assert sorted(k for k in out if k.startswith("undecided:")) == [
            "undecided:nba_first_half_total_luck", "undecided:nba_q1_trend",
            "undecided:nba_team_total_luck", "undecided:nba_total_luck"]

    def test_a_game_all_three_decided_says_nothing(self):
        out = fa._conditions(NbaConn([TIPPED], _decided_by(*NbaConn.ALL)), NOW)
        assert not [k for k in out if k.startswith(("undecided:", "check:"))]

    def test_a_decisions_table_that_does_not_exist_is_no_decision(self):
        """query_rows-style silence on a missing table would hide a model whose card
        has never once run, the most expensive case there is."""
        tables = [t for t in NbaConn.ALL if "first_half" not in t]
        conn = NbaConn([TIPPED], _decided_by(*tables), tables=tables)
        out = fa._conditions(conn, NOW)
        assert [k for k in out if k.startswith("undecided:")] == [
            "undecided:nba_first_half_total_luck"]

    def test_a_bet_with_no_decision_row_counts_as_decided_as_the_plan_reads_it(self):
        tables = ("nba_total_luck_decisions", "nba_first_half_total_luck_decisions",
                  "nba_q1_trend_decisions")
        conn = NbaConn([TIPPED], _decided_by(*tables), bets=[("nba_team_total_luck", GAME)])
        assert not [k for k in fa._conditions(conn, NOW) if k.startswith("undecided:")]

    def test_a_game_that_has_not_tipped_is_owed_nothing_yet(self):
        later = list(TIPPED)
        later[5] = (NOW + timedelta(minutes=30)).isoformat()
        assert not [k for k in fa._conditions(NbaConn([tuple(later)]), NOW)
                    if k.startswith("undecided:")]

    def test_a_game_that_tipped_over_a_day_ago_has_left_the_window(self):
        old = list(TIPPED)
        old[5] = (NOW - timedelta(hours=25)).isoformat()
        assert not [k for k in fa._conditions(NbaConn([tuple(old)]), NOW)
                    if k.startswith("undecided:")]

    def test_a_preseason_game_is_nobody_s_to_decide(self):
        pre = list(TIPPED)
        pre[7] = "preseason"
        assert not [k for k in fa._conditions(NbaConn([tuple(pre)]), NOW)
                    if k.startswith("undecided:")]

    def test_a_cup_placeholder_with_no_teams_is_never_planned_so_never_lost(self):
        tbd = list(TIPPED)
        tbd[1] = "TBD"
        assert not [k for k in fa._conditions(NbaConn([tuple(tbd)]), NOW)
                    if k.startswith("undecided:")]

    def test_a_failed_read_is_reported_and_leaves_every_other_alert_standing(self):
        conn = NbaConn([TIPPED], health=[("settlement_lag", "STALE", "WARN", "1 pick")], boom=True)
        out = fa._conditions(conn, NOW)
        assert out["check:nba_undecided_games"][0] == "WARN"
        assert "health:settlement_lag" in out
        assert conn.rollbacks == 1


# ── nba_prop_market's own watch ──────────────────────────────────────────────


def pregame_et():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


PO = "NBA_2027-04-20_MIA_BOS"
PO_TIP = (NOW - timedelta(hours=2)).isoformat()
PO_ROW = (PO, "BOS", "MIA", "2027-04-20", 2027, PO_TIP, PO_TIP, "playoff")
WATCH_SCHED = [("A", 2027, "2027-04-11", "regular", "LAL", "GSW", True, True)]
TODAY = "NBA_2026-09-06_MIA_BOS"      # dated on NOW's own ET date, so its confirmation stamp can count


def _listed(gid=TODAY, kind="playoff", tip=PO_TIP, updated=None, status="Scheduled", home=None, away=None):
    _, day, a, h = gid.split("_")
    return (gid, day, kind, tip, home or h, away or a, status, updated or NOW)


def _watch(out):
    return {k: v for k, v in out.items() if k.startswith(("undecided:", "refused:", "stranded:", "start_gap:", "check:"))}


class TestTheRulesOwnWatch:
    def test_a_postseason_game_with_no_rule_decision_is_a_warning_under_the_rules_key_alone(self):
        """Not a page: the rule writes no decision when Pinnacle has no price in its window. And never
        under the three total models, which do not bet these games, so owe them nothing."""
        out = _watch(fa._conditions(NbaConn([PO_ROW], rule_decided=set(), sched=WATCH_SCHED), NOW))
        assert list(out) == [f"undecided:nba_prop_market:{PO}"]
        sev, title, detail = out[f"undecided:nba_prop_market:{PO}"]
        assert sev == "WARN" and PO in title and "postseason (playoff)" in detail
        assert "regular-season" not in detail

    @pytest.mark.parametrize("kind", ["playin", "playoff", "cup_final"])
    def test_a_decided_postseason_game_says_nothing(self, kind):
        row = (PO, "BOS", "MIA", "2027-04-20", 2027, PO_TIP, PO_TIP, kind)
        assert not _watch(fa._conditions(NbaConn([row], rule_decided={PO}, sched=WATCH_SCHED), NOW))

    def test_a_bet_with_no_ledger_row_counts_as_decided(self):
        out = fa._conditions(NbaConn([PO_ROW], rule_decided=set(), bets=[("nba_prop_market", PO)],
                                     sched=WATCH_SCHED), NOW)
        assert not _watch(out)

    def test_a_regular_season_game_the_rule_lost_is_named_too_at_the_same_level(self):
        """So this has run live, on real games, before the first postseason game needs it."""
        out = _watch(fa._conditions(NbaConn([TIPPED], _decided_by(*NbaConn.ALL), rule_decided=set()), NOW))
        assert list(out) == [f"undecided:nba_prop_market:{GAME}"]
        assert out[f"undecided:nba_prop_market:{GAME}"][0] == "WARN"
        assert "regular-season" in out[f"undecided:nba_prop_market:{GAME}"][2]

    def test_each_lost_game_has_its_own_key(self):
        """A WARN re-posts every 12 hours, so a shared key would hide the night's second lost game."""
        two = [PO_ROW, ("NBA_2027-04-20_NYK_ATL", "ATL", "NYK", "2027-04-20", 2027, PO_TIP, PO_TIP, "playoff")]
        out = _watch(fa._conditions(NbaConn(two, rule_decided=set(), sched=WATCH_SCHED), NOW))
        assert sorted(out) == [f"undecided:nba_prop_market:{PO}", "undecided:nba_prop_market:NBA_2027-04-20_NYK_ATL"]

    def test_the_failed_refresh_game_with_only_a_feed_row_is_watched(self):
        """The schedule alone would miss it, and this is the very game the rule keeps betting."""
        row = (PO, "BOS", "MIA", "2027-04-20", 2027, PO_TIP, None, None)
        out = _watch(fa._conditions(NbaConn([row], rule_decided=set(), sched=WATCH_SCHED), NOW))
        assert list(out) == [f"undecided:nba_prop_market:{PO}"]
        assert "postseason (unlisted)" in out[f"undecided:nba_prop_market:{PO}"][2]

    def test_a_wrong_date_feed_row_is_not_a_lost_game_but_is_reported(self):
        """Its real game has its own id, named if that game is lost. This one has no game to lose,
        and it is reported apart because of what a bet on it would have done."""
        wrong = ("NBA_2027-04-19_MIA_BOS", "BOS", "MIA", "2027-04-19", 2027, PO_TIP, None, None)
        real = (PO, 2027, "2027-04-20", "playoff", "BOS", "MIA", True, False)
        out = _watch(fa._conditions(NbaConn([wrong], rule_decided=set(), sched=[*WATCH_SCHED, real]), NOW))
        assert list(out) == ["refused:nba_prop_market:NBA_2027-04-19_MIA_BOS"]
        assert out["refused:nba_prop_market:NBA_2027-04-19_MIA_BOS"][0] == "WARN"
        assert PO in out["refused:nba_prop_market:NBA_2027-04-19_MIA_BOS"][2]

    def test_a_listed_game_with_no_games_row_confirmed_on_its_day_is_named(self):
        out = _watch(fa._conditions(NbaConn(listed=[_listed(updated=NOW)], rule_decided=set()), NOW))
        assert list(out) == [f"undecided:nba_prop_market:{TODAY}"]

    def test_a_game_6_the_series_never_needed_is_not_named(self):
        """The refresh never deletes, so a row ESPN stopped listing just stays, with an older stamp."""
        stale = NOW - timedelta(days=3)
        out = _watch(fa._conditions(NbaConn(listed=[_listed(tip=(NOW - timedelta(hours=3)).isoformat(),
                                                            updated=stale)], rule_decided=set()), NOW))
        assert out == {}

    @pytest.mark.parametrize("row", [
        _listed(status="Postponed"),
        _listed(status="Canceled"),
        _listed(gid="NBA_2026-09-06_nan_nan", kind="cup_final"),
        _listed(home="TBD"),
    ])
    def test_a_postponed_row_or_a_placeholder_is_not_named(self, row):
        """The stored Cup final is a placeholder with no teams and no games row."""
        assert _watch(fa._conditions(NbaConn(listed=[row], rule_decided=set()), NOW)) == {}

    def test_a_listed_game_with_no_tip_is_named_only_once_its_date_is_over(self):
        """ESPN's Cup final slot has timeValid false today, so no tip is stored."""
        today = NOW.astimezone(pregame_et()).date()
        over = today - timedelta(days=1)
        row = _listed(gid=f"NBA_{over}_MIA_BOS", tip=None, updated=NOW)
        assert list(_watch(fa._conditions(NbaConn(listed=[row], rule_decided=set()), NOW))) == [
            f"undecided:nba_prop_market:NBA_{over}_MIA_BOS"]
        row = _listed(gid=f"NBA_{today}_MIA_BOS", tip=None, updated=NOW)
        assert _watch(fa._conditions(NbaConn(listed=[row], rule_decided=set()), NOW)) == {}

    def test_a_listed_game_the_feed_holds_the_other_way_round_is_not_named_twice(self):
        """ESPN's id has no row because that row is the game. The rule's own read watches the feed's."""
        flipped = "NBA_2026-09-06_BOS_MIA"
        out = _watch(fa._conditions(NbaConn(listed=[_listed(updated=NOW)], rule_decided=set(),
                                            other_rows={flipped}), NOW))
        assert out == {}

    def test_an_open_bet_on_a_game_with_no_final_is_named(self):
        """A bet with no final never settles, and the settlement checks start from a final score."""
        tip = (NOW - timedelta(hours=13)).isoformat()
        conn = NbaConn(rule_decided=None, open_bets=[(PO, "2027-04-20", tip, None), (PO, "2027-04-20", tip, tip)])
        out = _watch(fa._conditions(conn, NOW))
        assert list(out) == [f"stranded:nba_prop:{PO}"]
        sev, title, detail = out[f"stranded:nba_prop:{PO}"]
        assert sev == "WARN" and title.startswith("2 open") and "void_picks" in detail

    def test_the_stranded_alert_keeps_a_played_game_from_being_voided(self):
        """A played game's bet has a real result, and whoever acts can already see it. CLAUDE.md 1c
        keeps VOID for a row the model should never have produced, so the alert says so before it
        names the void command, and names the opt-in a posted bet needs."""
        tip = (NOW - timedelta(hours=13)).isoformat()
        conn = NbaConn(rule_decided=None, open_bets=[(PO, "2027-04-20", tip, tip)])
        detail = _watch(fa._conditions(conn, NOW))[f"stranded:nba_prop:{PO}"][2]
        played, _, postponed = detail.partition("**The game was postponed or cancelled:**")
        assert "**The game was played and its final landed on another row:** do not void" in played
        assert "void_picks" not in played and "Write the final and the box lines" in played
        assert "NO_ACTION" in postponed and f"void_picks.py --game-id {PO}" in postponed
        assert "--allow-posted" in postponed and "RECORD_EXCLUSIONS" in postponed and "naming who asked" in postponed

    def test_two_starts_that_disagree_reach_the_channel_not_just_the_log(self):
        """Before the game, while someone can still read the real start. If the feed is the stale one
        a bet could land after the real tip, and nothing else would say so."""
        espn = (NOW + timedelta(hours=1)).isoformat()
        feed = (NOW + timedelta(hours=6)).isoformat()
        row = (PO, "BOS", "MIA", "2027-04-20", 2027, feed, espn, "playoff")
        out = _watch(fa._conditions(NbaConn([row], sched=WATCH_SCHED), NOW))
        assert list(out) == [f"start_gap:nba_prop_market:{PO}"]
        sev, title, detail = out[f"start_gap:nba_prop_market:{PO}"]
        assert sev == "WARN" and PO in title
        assert espn in detail and feed in detail and "real start" in detail
        assert f"`{feed}`, the feed's" in detail and "closing-line value stays empty" in detail

    def test_two_starts_inside_the_feeds_ordinary_lag_say_nothing(self):
        espn = (NOW + timedelta(hours=1)).isoformat()
        feed = (NOW + timedelta(hours=1, minutes=20)).isoformat()
        row = (PO, "BOS", "MIA", "2027-04-20", 2027, feed, espn, "playoff")
        assert not _watch(fa._conditions(NbaConn([row], sched=WATCH_SCHED), NOW))

    def test_a_game_still_inside_twelve_hours_is_given_its_time(self):
        tip = (NOW - timedelta(hours=11)).isoformat()
        assert not _watch(fa._conditions(NbaConn(open_bets=[(PO, "2027-04-20", tip, tip)]), NOW))

    def test_the_open_bet_read_is_either_prop_models_open_unvoided_bets_on_unscored_games(self):
        import inspect

        import scripts.nba_pregame_window as w
        src = inspect.getsource(w.stranded_prop_bets)
        for clause in ("p.result IS NULL", "condition_status IS DISTINCT FROM 'VOID'",
                       "g.home_score IS NULL", "p.signal_type = 'BET'", "p.game_date >= %s"):
            assert clause in src
        from scripts.nba_props_card import PROP_MODEL_IDS
        assert set(PROP_MODEL_IDS) == {"nba_prop_market", "nba_prop_projection"}

    def test_a_failed_watch_read_is_reported_and_leaves_the_three_models_alerts_standing(self):
        conn = NbaConn([TIPPED], _decided_by("nba_total_luck_decisions", "nba_first_half_total_luck_decisions"),
                       sched=WATCH_SCHED, watch_boom=True)
        out = fa._conditions(conn, NOW)
        assert out["undecided:nba_team_total_luck"][0] == "CRIT"
        assert out["check:nba_prop_watch"][0] == "WARN"
