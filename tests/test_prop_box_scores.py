"""Missing prop logs are fetched before the grade, and a timeout does not
abort the next date or the next sport."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import pytest

from data.ingestors import prop_box_scores as box
from tracking import paper_tracker as pt

_TRACKER = Path(pt.__file__).read_text(encoding="utf-8")
_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"


class ScriptConn:
    """Returns scripted rows, and behaves like Postgres after a timeout:
    the next statement fails until ROLLBACK TO SAVEPOINT."""

    def __init__(self, picks=(), logged=None, cool=None, fail=None):
        self.picks = list(picks)
        self.logged = logged or {}
        self.cool = list(cool or [])
        self.fail = fail
        self.sqls = []
        self.aborted = False
        self.commits = 0
        self.closed = False
        self._last = ""

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted:
            if text.upper().startswith("ROLLBACK"):
                self.aborted = False
                self.sqls.append((text, params))
                return self
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.sqls.append((text, params))
        self._last = text
        if self.fail and self.fail in text:
            self.aborted = True
            raise self._error()
        return self

    def _error(self):
        if self.fail == "timeout":
            return psycopg2.errors.QueryCanceled(
                "canceling statement due to statement timeout")
        return RuntimeError("probe failed")

    def fetchall(self):
        text = self._last
        if "FROM picks" in text:
            return self.picks
        if "nhl_skater_game_log" in text:
            return [(g,) for g in self.logged.get("skater", [])]
        if "nhl_goalie_game_log" in text:
            return [(g,) for g in self.logged.get("goalie", [])]
        if "player_game_log" in text and "nhl_" not in text and "wnba_" not in text \
                and "nba_" not in text and "nfl_" not in text:
            return [(g,) for g in self.logged.get("MLB", [])]
        if "wnba_player_game_log" in text:
            return [(g,) for g in self.logged.get("WNBA", [])]
        if "nba_player_game_log" in text:
            return [(g,) for g in self.logged.get("NBA", [])]
        if "nfl_player_game_log" in text:
            return [(g,) for g in self.logged.get("NFL", [])]
        return []

    def fetchone(self):
        if "pipeline_log" in self._last:
            return self.cool[0] if self.cool else None
        rows = self.fetchall()
        return rows[0] if rows else None

    def commit(self):
        if self.aborted:
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.commits += 1

    def rollback(self):
        self.aborted = False

    def close(self):
        self.closed = True


def _pick(model, game, day, player="1"):
    return (model, game, day, player)


def test_the_window_matches_the_prop_settler():
    assert box.WINDOW_DAYS == pt._PROP_SETTLE_WINDOW_DAYS


def test_the_probe_is_date_bounded_and_selects_an_unlogged_final():
    conn = ScriptConn(picks=[
        _pick("nhl_prop_shots_on_goal", "NHL_2026-10-13_NJD_DET", "2026-10-13", "8476474"),
    ])
    missing = box.missing_prop_games(conn, "2026-10-14")
    probe = next(sql for sql, params in conn.sqls if "FROM picks" in sql)
    params = next(params for sql, params in conn.sqls if "FROM picks" in sql)
    assert "p.result IS NULL" in probe
    assert "p.signal_type = 'BET'" in probe
    assert "g.home_score IS NOT NULL" in probe
    assert params == ("2026-10-01", "2026-10-14")
    game = missing["NHL"]["2026-10-13"]["NHL_2026-10-13_NJD_DET"]
    assert game["kinds"] == {"skater"}
    assert game["players"] == {"8476474"}
    assert any("nhl_skater_game_log" in sql for sql, _ in conn.sqls)


def test_a_logged_game_is_not_fetched_and_a_goalie_gap_is():
    conn = ScriptConn(
        picks=[
            _pick("nhl_prop_shots_on_goal", "NHL_LOGGED", "2026-10-13"),
            _pick("nhl_prop_saves", "NHL_GOALIE", "2026-10-13", "8477970"),
        ],
        logged={"skater": ["NHL_LOGGED"]},
    )
    missing = box.missing_prop_games(conn, "2026-10-13")
    assert "NHL_LOGGED" not in missing["NHL"]["2026-10-13"]
    assert missing["NHL"]["2026-10-13"]["NHL_GOALIE"]["kinds"] == {"goalie"}
    assert any("nhl_goalie_game_log" in sql for sql, _ in conn.sqls)


def test_a_probe_timeout_rolls_back_and_returns_empty():
    conn = ScriptConn(fail="timeout")
    # The timeout is raised from the picks read. Tag it so execute matches.
    conn.fail = "FROM picks"
    conn._error = lambda: psycopg2.errors.QueryCanceled(
        "canceling statement due to statement timeout")
    assert box.missing_prop_games(conn, "2026-10-14") == {}
    conn.execute("SELECT 1")
    assert any(sql.startswith("ROLLBACK TO SAVEPOINT prop_box_probe")
               for sql, _ in conn.sqls)


def test_a_probe_error_that_is_not_a_timeout_raises_after_rollback():
    conn = ScriptConn()
    conn.fail = "FROM picks"
    with pytest.raises(RuntimeError):
        box.missing_prop_games(conn, "2026-10-14")
    conn.execute("SELECT 1")
    assert conn.aborted is False


def test_only_the_newest_dates_are_kept():
    picks = [
        _pick("nhl_prop_shots_on_goal", f"G{i}", f"2026-09-{i:02d}")
        for i in range(1, 22)
    ]
    conn = ScriptConn(picks=picks)
    missing = box.missing_prop_games(conn, "2026-09-21")
    days = set(missing["NHL"])
    assert "2026-09-01" not in days
    assert "2026-09-02" in days
    assert "2026-09-21" in days
    assert len(days) == box.MAX_DATES


def test_ensure_fetches_only_the_missing_sport():
    conn = ScriptConn(picks=[
        _pick("nhl_prop_shots_on_goal", "NHL_A", "2026-10-13"),
        _pick("nhl_prop_shots_on_goal", "NHL_B", "2026-10-12"),
    ], logged={"skater": ["NHL_B"]})
    seen = {}

    def nhl(dates):
        seen["nhl"] = dates
        return {"games": 1}

    def boom(*_a, **_k):
        raise AssertionError("filled a sport that had nothing missing")

    out = box.ensure_prop_box_scores(
        "2026-10-14", connect=lambda: conn, nhl_fill=nhl,
        mlb_fill=boom, wnba_fill=boom, nba_fill=boom, nfl_fill=boom,
    )
    assert seen["nhl"] == {"2026-10-13": {"NHL_A"}}
    assert "NHL_B" not in str(seen["nhl"])
    assert out["filled"]["NHL"] == {"games": 1}
    assert out["games"] == {"NHL": 1}
    assert conn.closed is False


def test_nothing_missing_makes_no_fetch():
    conn = ScriptConn()
    called = []
    out = box.ensure_prop_box_scores(
        "2026-10-14", connect=lambda: conn,
        nhl_fill=lambda d: called.append("nhl"),
        mlb_fill=lambda d: called.append("mlb"),
        wnba_fill=lambda d: called.append("wnba"),
        nba_fill=lambda d: called.append("nba"),
        nfl_fill=lambda: called.append("nfl"),
    )
    assert called == []
    assert out["filled"] == {}


def test_a_recent_nfl_attempt_is_not_repeated():
    conn = ScriptConn(
        picks=[_pick("nfl_prop_pass_yards", "NFL_1", "2026-10-13", "p")],
        cool=[("2026-10-14 12:40:00.000000+00",)],
    )
    called = []
    now = datetime(2026, 10, 14, 12, 50, tzinfo=timezone.utc)
    out = box.ensure_prop_box_scores(
        "2026-10-14", connect=lambda: conn, now=lambda: now,
        nfl_fill=lambda: called.append("nfl"),
        nhl_fill=lambda d: called.append("nhl"),
    )
    assert called == []
    assert out["cooled"] == ["NFL"]
    assert conn.commits == 0
    assert not any("INSERT INTO pipeline_log" in sql for sql, _ in conn.sqls)


def test_an_uncooled_nfl_attempt_is_marked_before_the_fetch():
    conn = ScriptConn(
        picks=[_pick("nfl_live_prop", "NFL_1", "2026-10-13")],
    )
    order = []

    def nfl():
        order.append("fetch")
        return {"players": 1}

    real_mark = box._mark

    def mark(conn_, step, through):
        order.append("mark")
        return real_mark(conn_, step, through)

    box._mark = mark
    try:
        out = box.ensure_prop_box_scores(
            "2026-10-14", connect=lambda: conn, nfl_fill=nfl,
        )
    finally:
        box._mark = real_mark
    assert order == ["mark", "fetch"]
    assert conn.commits == 1
    assert out["filled"]["NFL"] == {"players": 1}
    insert = next(params for sql, params in conn.sqls if "INSERT INTO pipeline_log" in sql)
    assert insert[1] == "prop_box_nfl"


def test_wnba_is_one_date_and_the_defaults_name_the_ingestors():
    src = Path(box.__file__).read_text(encoding="utf-8")
    assert "only_date=game_date" in src
    assert "ingest_game_log_for_date" in src
    assert "run_nfl_props_data_ingestor" in src
    conn = ScriptConn(picks=[
        _pick("wnba_prop_player_points", "WNBA_1", "2026-10-13"),
        _pick("nba_prop_player_points", "NBA_1", "2026-10-13", "99"),
    ])
    seen = {}
    out = box.ensure_prop_box_scores(
        "2026-10-14", connect=lambda: conn,
        wnba_fill=lambda day: seen.setdefault("wnba", []).append(day),
        nba_fill=lambda dates: seen.setdefault("nba", dates),
    )
    assert seen["wnba"] == ["2026-10-13"]
    assert seen["nba"] == {"2026-10-13": {"NBA_1": {"99"}}}
    assert "WNBA" in out["filled"] and "NBA" in out["filled"]


def test_settle_picks_pulls_boxes_before_it_grades_props():
    body = _TRACKER[_TRACKER.index("def settle_picks("):
                    _TRACKER.index("def print_performance_summary(")]
    assert "_heal_stranded_mlb(conn, game_date, settled_at)" in body
    assert "mirror_stored_finals(conn, game_date)" in body
    assert "_void_postponed_mlb_picks(conn, _d, settled_at)" in body
    assert body.index("ensure_prop_box_scores") < body.index("_settle_prop_picks_window")
    assert body.index("_backfill_clv") < body.index("ensure_prop_box_scores")


class GradeConn:
    def __init__(self, fail_on):
        self.fail_on = fail_on
        self.aborted = False
        self.commits = 0
        self.sqls = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        if self.aborted:
            if text.upper().startswith("ROLLBACK"):
                self.aborted = False
                self.sqls.append(text)
                return self
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.sqls.append(text)
        if self.fail_on and self.fail_on in text:
            self.aborted = True
            if self.fail_on == "TIMEOUT":
                raise psycopg2.errors.QueryCanceled(
                    "canceling statement due to statement timeout")
            raise RuntimeError("grade failed")
        return self

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.aborted = False


def test_a_timed_out_prop_date_does_not_abort_the_next(monkeypatch):
    monkeypatch.setattr(pt, "_prop_settle_window_days", lambda conn, game_date: 2)
    graded = []

    def settle(conn, d, settled_at):
        if d == "2026-10-14":
            conn.execute("TIMEOUT grade")
        graded.append(d)
        return (1, 0, 0, 0, 0.0, 0.0)

    monkeypatch.setattr(pt, "_settle_prop_picks", settle)
    conn = GradeConn("TIMEOUT")
    totals = pt._settle_prop_picks_window(conn, "2026-10-14", "TS")
    assert graded == ["2026-10-13"]
    assert totals[0] == 1
    assert conn.commits == 0
    assert conn.aborted is False
    conn.execute("SELECT 1")


def test_a_non_timeout_prop_error_rolls_back_and_raises(monkeypatch):
    monkeypatch.setattr(pt, "_prop_settle_window_days", lambda conn, game_date: 2)

    def settle(conn, d, settled_at):
        conn.execute("BOOM grade")
        return (0, 0, 0, 0, 0.0, 0.0)

    monkeypatch.setattr(pt, "_settle_prop_picks", settle)
    conn = GradeConn("BOOM")
    with pytest.raises(RuntimeError):
        pt._settle_prop_picks_window(conn, "2026-10-14", "TS")
    assert any(sql.startswith("ROLLBACK TO SAVEPOINT prop_settle_day") for sql in conn.sqls)
    conn.execute("SELECT 1")
    assert conn.commits == 0
