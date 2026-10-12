"""A pregame pick is not written once the game's pregame cutoff has passed.

The cutoff is pregame_cutoff_sql (actual first pitch, clamped), read at
insert time against a fresh now(). An unknown start is kept. A live row is
kept and is not looked up. Card writers that insert on their own call the
same gate. Card slates drop a game at or past that cutoff.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from loguru import logger

from models.scorer import _insert_picks, run_scorer

NOW = datetime(2026, 9, 17, 23, 30, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]
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


def test_the_wnba_card_writer_rejects_a_started_game(clock, warnings):
    """A card that inserts on its own still hits the gate."""
    import models.wnba_prop_market as mk
    from scripts.wnba_prop_market_card import norm_name, pick_rows, publish

    bet = mk.MarketBet(
        game_id="g1", player="A'ja Wilson", market="player_points",
        side="over", book="draftkings", line=21.5, price=-105,
        fair=0.58, edge=0.06, sharp_price=-140,
    )
    games = {"g1": {"home": "LV", "away": "SEA",
                    "commence_time": "2026-09-17T23:00:00Z"}}
    row = pick_rows([bet], games, {}, {norm_name("A'ja Wilson"): "1"},
                    "2026-09-17", 1000.0)[0]

    class Card:
        def __init__(self, cutoff):
            self.cutoff = cutoff
            self.inserted = []

        def execute(self, sql, params=None):
            card = self

            class R:
                def fetchall(_self):
                    return [("g1", card.cutoff)]

                def fetchone(_self):
                    return None
            if "INSERT INTO picks" in sql:
                self.inserted.append(params)
            return R()

        def commit(self):
            pass

    started = Card(NOW - timedelta(minutes=4))
    assert publish(started, [dict(row)]) == 0
    assert started.inserted == []
    got = _rejected(warnings)
    assert len(got) == 1
    assert got[0]["extra"]["game_id"] == "g1"
    assert got[0]["extra"]["model"] == "wnba_prop_market"
    assert got[0]["extra"]["minutes_after_start"] == pytest.approx(4)

    warnings.clear()
    open_game = Card(NOW + timedelta(hours=1))
    assert publish(open_game, [dict(row)]) == 1
    assert len(open_game.inserted) == 1
    assert _rejected(warnings) == []


class _Slate:
    def __init__(self, rows):
        self.rows = rows
        self.sql = ""
        self.params = None

    def execute(self, sql, params=None):
        self.sql, self.params = sql, params
        return self

    def fetchall(self):
        return self.rows


def test_mlb_slate_drops_a_game_at_or_past_the_cutoff_column():
    """Future commence_time, cutoff already passed: the game is off the card.

    A rain delay (cutoff still ahead, scheduled start already past) stays.
    """
    from scripts.mlb_game_market_card import slate

    future = "2026-09-17T23:00:00+00:00"
    past = "2026-09-16T20:00:00+00:00"
    now = datetime(2026, 9, 16, 22, 0, tzinfo=timezone.utc)
    rows = [
        ("EARLY", "NYY", "BOS", future, "2026-09-16", past),
        ("DELAY", "CLE", "CWS", past, "2026-09-16", future),
        ("AT", "TOR", "DET", future, "2026-09-16", now.isoformat()),
    ]
    conn = _Slate(rows)
    games = slate(conn, "2026-09-16", now=now)
    assert set(games) == {"DELAY"}
    assert "first_pitch_at" in conn.sql
    assert "> %s::timestamptz" in conn.sql


def test_wnba_and_nhl_slates_use_the_same_cutoff_predicate():
    from scripts.nhl_prop_card import slate as nhl_prop
    from scripts.nhl_totals_card import slate as nhl_totals
    from scripts.wnba_prop_market_card import slate as wnba

    now = datetime(2026, 10, 2, 0, 0, tzinfo=timezone.utc)
    future = "2026-10-02T02:00:00+00:00"
    past = "2026-10-01T22:00:00+00:00"
    wnba_conn = _Slate([
        ("W_EARLY", "NY", "LV", future, past),
        ("W_OPEN", "MIN", "IND", future, "2026-10-02T01:00:00+00:00"),
    ])
    assert set(wnba(wnba_conn, "2026-10-01", now=now)) == {"W_OPEN"}
    assert "first_pitch_at" in wnba_conn.sql

    prop_conn = _Slate([
        ("P_EARLY", "NYR", "BOS", future, past),
        ("P_OPEN", "VAN", "EDM", future, "2026-10-02T02:10:00Z"),
    ])
    assert set(nhl_prop(prop_conn, "2026-10-01", now)) == {"P_OPEN"}
    assert "first_pitch_at" in prop_conn.sql

    totals_conn = _Slate([
        ("T_EARLY", "OTT", "PHI", future, "2026-10-01", past),
        ("T_OPEN", "BOS", "UTA", future, "2026-10-01", "2026-10-02T01:00:00Z"),
    ])
    assert set(nhl_totals(totals_conn, now)) == {"T_OPEN"}
    assert "first_pitch_at" in totals_conn.sql


def test_nfl_slate_filters_started_games_only_when_now_is_passed():
    from scripts.nfl_prop_market_card import slate

    now = datetime(2026, 9, 14, 17, 0, tzinfo=timezone.utc)
    future_ko = "2026-09-14T20:00:00+00:00"
    rows = [
        ("GONE", future_ko, "BUF", "KC", True, "2026-09-14",
         "2026-09-14T16:00:00+00:00"),
        ("OPEN", future_ko, "NYJ", "NE", True, "2026-09-14",
         "2026-09-14T18:00:00+00:00"),
        ("AT", future_ko, "DAL", "PHI", True, "2026-09-14", now.isoformat()),
    ]
    live = _Slate(rows)
    assert set(slate(live, "2026-09-14", "2026-09-21", now=now)) == {"OPEN"}
    assert "LEFT JOIN games" in live.sql
    assert "first_pitch_at" in live.sql
    assert "> %s::timestamptz" in live.sql

    replay = _Slate(rows)
    # No clock: the replay window is the whole date range. The fake still
    # returns the long rows; without `now` they are not cutoff-filtered.
    got = slate(replay, "2026-09-14", "2026-09-21")
    assert set(got) == {"GONE", "OPEN", "AT"}
    assert "first_pitch_at" not in replay.sql


def test_open_quotes_are_bounded_on_the_pregame_cutoff():
    import inspect
    from models.mlb_game_market import load_latest_quotes
    src = inspect.getsource(load_latest_quotes)
    assert "pregame_cutoff_sql(" in src
    assert "o.commence_time" not in src
    assert "<= g.commence_time" not in src


def test_the_started_game_skip_rereads_the_cutoff():
    import inspect
    src = inspect.getsource(run_scorer)
    assert "commence_time <= now_utc" not in src
    assert "_pregame_cutoff" in src
    assert "_game_started(cutoff)" in src


def test_every_picks_insert_goes_through_the_cutoff_gate():
    exempt = "tracking/first_signal_repair.py"
    phrase = "restores a pick that already existed"
    skip = {"tests", "__pycache__", ".venv", "venv", "node_modules", ".git"}
    missing = []
    seen = []
    for path in ROOT.rglob("*.py"):
        if skip & set(path.parts):
            continue
        text = path.read_text(encoding="utf-8")
        if not re.search(r"INSERT\s+INTO\s+picks\b", text):
            continue
        rel = path.relative_to(ROOT).as_posix()
        seen.append(rel)
        if rel == exempt:
            assert phrase in text
            assert "_drop_pregame_after_cutoff" not in text
            continue
        if "_drop_pregame_after_cutoff" not in text:
            missing.append(rel)
    assert missing == [], missing
    assert "models/scorer.py" in seen
    assert exempt in seen
