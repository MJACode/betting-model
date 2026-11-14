"""A pregame pick is not written once the game's pregame cutoff has passed.

The gate is models.scorer._insert_picks, so every lane that writes through
it is covered. The cutoff is pregame_cutoff_sql (actual first pitch,
clamped), read at insert time against a fresh now(). An unknown start is
kept. A failed read is kept. A live row (is_live) is kept and is not looked
up, which is how the in-play lanes keep betting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import psycopg2
import pytest
from loguru import logger

from models.scorer import _insert_picks

NOW = datetime(2026, 9, 17, 23, 30, tzinfo=timezone.utc)
REJECTED = "pregame pick rejected: at or past the pregame cutoff"


def _row(**kw):
    base = {
        "game_id": "G1",
        "model_id": "unit_model",
        "sport": "MLB",
        "game_date": "2026-09-17",
        "pick_side": "home",
        "pick_label": "NYY -1.5",
        "model_probability": 0.6,
        "dk_implied_prob": 0.5,
        "edge": 0.1,
        "dk_odds": -110,
        "scored_line": -1.5,
        "kelly_fraction": 0.01,
        "recommended_bet": 10.0,
        "bankroll_at_pick": 1000.0,
        "signal_type": "BET",
        "confidence_tier": "MED",
        "is_live": False,
    }
    base.update(kw)
    return base


class _Conn:
    """Answers the cutoff lookup; records the insert."""

    def __init__(self, cutoffs):
        self.cutoffs = cutoffs
        self.lookups = []
        self.inserted = []

    def execute(self, sql, params=None):
        self.lookups.append(sql)
        rows = self.cutoffs

        class R:
            def fetchall(_self):
                return rows
        return R()

    def executemany(self, sql, batch):
        self.inserted.extend(list(batch))


@pytest.fixture
def clock(monkeypatch):
    monkeypatch.setattr("models.scorer._utcnow", lambda: NOW)
    monkeypatch.setattr("models.scorer._calibrated", lambda model, prob: prob)


@pytest.fixture
def warnings():
    found = []
    hid = logger.add(lambda m: found.append(m.record), level="WARNING")
    try:
        yield found
    finally:
        logger.remove(hid)


def _rejected(records):
    return [r for r in records if r["message"] == REJECTED]


def test_a_row_before_the_cutoff_is_inserted(clock, warnings):
    cutoff = NOW + timedelta(minutes=1)
    conn = _Conn([("G1", cutoff)])
    _insert_picks(conn, [_row()])
    assert len(conn.inserted) == 1
    assert conn.inserted[0]["game_id"] == "G1"
    assert any("first_pitch_at" in sql for sql in conn.lookups)
    assert _rejected(warnings) == []


@pytest.mark.parametrize("minutes_after", [0, 30])
def test_a_row_at_or_after_the_cutoff_is_rejected_and_logged(
        clock, warnings, minutes_after):
    cutoff = NOW - timedelta(minutes=minutes_after)
    conn = _Conn([("G1", cutoff.isoformat())])
    _insert_picks(conn, [_row()])
    assert conn.inserted == []
    got = _rejected(warnings)
    assert len(got) == 1
    extra = got[0]["extra"]
    assert extra["game_id"] == "G1"
    assert extra["model"] == "unit_model"
    assert extra["minutes_after_start"] == pytest.approx(minutes_after)


def test_an_unknown_start_is_inserted(clock, warnings):
    for cutoffs in ([], [("G1", None)]):
        warnings.clear()
        conn = _Conn(cutoffs)
        _insert_picks(conn, [_row()])
        assert len(conn.inserted) == 1, cutoffs
        assert _rejected(warnings) == []


def test_a_failed_cutoff_read_keeps_the_row(clock, warnings):
    class Boom(_Conn):
        def execute(self, *args, **kwargs):
            raise RuntimeError("games unavailable")

    conn = Boom([])
    _insert_picks(conn, [_row()])
    assert len(conn.inserted) == 1
    assert _rejected(warnings) == []


def test_a_live_row_is_inserted_and_not_looked_up(clock, warnings):
    class Boom:
        def execute(self, *args, **kwargs):
            raise AssertionError("a live row must not look up a cutoff")

        def executemany(self, sql, batch):
            self.inserted = list(batch)

    conn = Boom()
    _insert_picks(conn, [_row(is_live=True)])
    assert len(conn.inserted) == 1
    assert conn.inserted[0]["is_live"] is True
    assert _rejected(warnings) == []


def test_a_live_row_stays_when_the_pregame_cutoff_has_passed(clock, warnings):
    """In-play lanes set is_live and bet after the cutoff. The past cutoff
    on the same game must not drop that row, and must not be queried when
    the batch is live-only. A mixed batch still drops the pregame copy."""
    past = (NOW - timedelta(minutes=12)).isoformat()
    conn = _Conn([("G1", past)])
    _insert_picks(conn, [
        _row(is_live=True, model_id="mlb_live_win_prob"),
        _row(model_id="mlb_moneyline"),
    ])
    assert [r["model_id"] for r in conn.inserted] == ["mlb_live_win_prob"]
    assert conn.inserted[0]["is_live"] is True
    got = _rejected(warnings)
    assert len(got) == 1
    assert got[0]["extra"]["model"] == "mlb_moneyline"


def test_the_insert_calls_the_gate_before_it_writes():
    import inspect
    from models import scorer
    src = inspect.getsource(scorer._insert_picks)
    gate = inspect.getsource(scorer._drop_pregame_after_cutoff)
    assert src.index("_drop_pregame_after_cutoff") < src.index("executemany")
    assert "is_live" in gate
    lookup = inspect.getsource(scorer._cutoff_by_game)
    assert "pregame_cutoff_sql" in lookup
    assert "_fail_open" in lookup


_ABORTED = "current transaction is aborted, commands ignored until end of transaction block"
_TIMEOUT = "canceling statement due to statement timeout"


class _AbortConn:
    """Postgres-shaped: a failed statement aborts the transaction until
    ROLLBACK TO SAVEPOINT. The cutoff SELECT is what times out."""

    def __init__(self, *, lose=False):
        self.lose = lose
        self.aborted = False
        self.inserted = []
        self.events: list[tuple] = []

    def execute(self, sql, params=None):
        text = " ".join(sql.split())
        upper = text.upper()
        if self.aborted:
            if upper.startswith("ROLLBACK TO SAVEPOINT"):
                self.aborted = False
                self.events.append(("savepoint_rollback", text))
                return self
            self.events.append(("poisoned", text[:80]))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.events.append(("exec", text[:120]))
        if upper.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK")):
            return self
        if "first_pitch_at" in text:
            if self.lose:
                from data.db import ConnectionLost
                raise ConnectionLost("server closed the connection")
            self.aborted = True
            raise psycopg2.errors.QueryCanceled(_TIMEOUT)
        return self

    def fetchall(self):
        return []

    def executemany(self, sql, batch):
        if self.aborted:
            self.events.append(("poisoned", "executemany"))
            raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
        self.inserted.extend(list(batch))
        self.events.append(("insert", len(self.inserted)))


def test_a_timed_out_cutoff_read_still_inserts_the_batch(clock, warnings):
    """The fake that only raises RuntimeError never aborts a transaction.
    This one does: QueryCanceled leaves the connection in the failed state,
    and the next statement raises InFailedSqlTransaction unless the lookup
    rolled back to its savepoint."""
    conn = _AbortConn()
    _insert_picks(conn, [_row(), _row(model_id="unit_model_b")])
    assert [r["model_id"] for r in conn.inserted] == ["unit_model", "unit_model_b"]
    assert not conn.aborted
    assert any(ev[0] == "savepoint_rollback" for ev in conn.events)
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    assert _rejected(warnings) == []


def test_a_lost_connection_on_the_cutoff_read_is_not_swallowed(clock):
    from data.db import ConnectionLost
    conn = _AbortConn(lose=True)
    with pytest.raises(ConnectionLost):
        _insert_picks(conn, [_row()])
    assert conn.inserted == []


def test_the_scorer_loop_skips_a_passed_cutoff_and_scores_the_rest(monkeypatch):
    """The skip re-reads the cutoff. The games row's commence_time is still
    in the future on every game, so a once-per-pass snapshot of that column
    would score them all.

    NHL_OFFSET's cutoff is 19:30-04:00 (23:30 UTC). The clock is 21:00 UTC.
    Truncating the offset would read 19:30 as UTC and skip the game about
    four hours early. NHL_PAST's re-read cutoff is already past, so it is
    skipped. An unknown cutoff is scored. A timed-out read is scored, and
    the game after it is scored on the same connection."""
    from types import SimpleNamespace

    import models.scorer as scorer

    future = "2099-01-01T00:00:00+00:00"
    when = datetime(2026, 9, 17, 21, 0, tzinfo=timezone.utc)
    games = [
        ("NHL_OFFSET", "NHL", 2026, "2026-09-17", "EDM", "VAN", future),
        ("NHL_PAST", "NHL", 2026, "2026-09-17", "BOS", "NYR", future),
        ("NHL_UNKNOWN", "NHL", 2026, "2026-09-17", "TOR", "MTL", future),
        ("NHL_FAIL", "NHL", 2026, "2026-09-17", "CGY", "EDM", future),
        ("NHL_AFTER", "NHL", 2026, "2026-09-17", "SEA", "VGK", future),
    ]
    cutoffs = {
        "NHL_OFFSET": "2026-09-17T19:30:00-04:00",
        "NHL_PAST": "2020-01-01T00:00:00+00:00",
        "NHL_AFTER": future,
    }

    class LoopConn:
        def __init__(self):
            self.aborted = False
            self.last = ""
            self.params = ()
            self.events: list[tuple] = []
            self.closed = False

        def execute(self, sql, params=None):
            text = " ".join(sql.split())
            upper = text.upper()
            if self.aborted:
                if upper.startswith("ROLLBACK TO SAVEPOINT"):
                    self.aborted = False
                    self.events.append(("savepoint_rollback", text))
                    self.last = text
                    self.params = params or ()
                    return self
                self.events.append(("poisoned", text[:80]))
                raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
            self.last = text
            self.params = params or ()
            self.events.append(("exec", text[:100], self.params))
            if upper.startswith(("SAVEPOINT", "RELEASE SAVEPOINT", "ROLLBACK", "SET LOCAL")):
                return self
            gid = self.params[0] if self.params else None
            if "first_pitch_at" in text and gid == "NHL_FAIL":
                self.aborted = True
                raise psycopg2.errors.QueryCanceled(_TIMEOUT)
            return self

        def fetchone(self):
            if "first_pitch_at" not in self.last:
                return None
            gid = self.params[0] if self.params else None
            if gid not in cutoffs:
                return None
            return (cutoffs[gid],)

        def fetchall(self):
            if "home_team" in self.last and "FROM games" in self.last:
                return games
            return []

        def rollback(self):
            self.aborted = False
            self.events.append(("rollback",))

        def commit(self):
            if self.aborted:
                raise psycopg2.errors.InFailedSqlTransaction(_ABORTED)
            self.events.append(("commit",))

        def close(self):
            self.closed = True

    conn = LoopConn()
    built: list[str] = []
    monkeypatch.setattr(scorer, "get_connection", lambda: conn)
    monkeypatch.setattr(scorer, "_get_postponed_games", lambda _date: set())
    monkeypatch.setattr(scorer, "_utcnow", lambda: when)
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda *a, **k: {"home_price": -110})
    monkeypatch.setattr(
        scorer, "_nhl_matchup",
        lambda c, gid: SimpleNamespace(reason=None, game_id=gid))
    def _build(conn, game_id, *a, **k):
        conn.events.append(("built", game_id))
        built.append(game_id)
        return {"x": 1}

    monkeypatch.setattr(scorer, "build_nhl_game_features", _build)
    monkeypatch.setattr(scorer, "score_game", lambda *a, **k: [])

    result = scorer.run_scorer("2026-09-17", dry_run=False)

    assert built == ["NHL_OFFSET", "NHL_UNKNOWN", "NHL_FAIL", "NHL_AFTER"]
    assert "NHL_PAST" not in built
    assert result["games"] == 5
    assert not conn.aborted
    assert any(ev[0] == "savepoint_rollback" for ev in conn.events)
    assert not any(ev[0] == "poisoned" for ev in conn.events)
    reset = next(i for i, ev in enumerate(conn.events) if ev[0] == "savepoint_rollback")
    after = next(i for i, ev in enumerate(conn.events)
                 if ev[0] == "built" and ev[1] == "NHL_AFTER")
    assert reset < after
