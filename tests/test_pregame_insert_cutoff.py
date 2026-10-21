"""A pregame pick is not written once the game's pregame cutoff has passed.

The gate is models.scorer._insert_picks, so every lane that writes through
it is covered. The cutoff is pregame_cutoff_sql (actual first pitch,
clamped), read at insert time against a fresh now(). An unknown start is
kept. A failed read is kept. A live row (is_live) is kept and is not looked
up, which is how the in-play lanes keep betting.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
    assert "first_pitch_at" in conn.lookups[0]
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
    assert "pregame_cutoff_sql" in inspect.getsource(scorer._cutoff_by_game)
