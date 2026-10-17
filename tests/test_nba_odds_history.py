"""data/ingestors/nba_odds_history: what the NBA price purchase asks for and keeps.

The purchase spent ~800k credits on 2026-10-15. These pin the parts that decide
what is bought (the snapshot plan), when it stops (the credit floor), that a
dropped connection does not lose a paid response, and how the half / quarter /
team-total markets are parsed.
"""
import pytest

from data.ingestors import nba_odds_history as h


def test_every_game_date_is_priced_near_any_tip_and_the_evening_before():
    pairs = set(h.line_snapshots(["2026-01-15"]))
    # the day's path, the late window on the next UTC date, and the opener
    assert {("2026-01-15", 15), ("2026-01-15", 19), ("2026-01-15", 22),
            ("2026-01-15", 23)} <= pairs
    assert {("2026-01-16", 0), ("2026-01-16", 1), ("2026-01-16", 2),
            ("2026-01-16", 3)} <= pairs
    assert ("2026-01-14", 22) in pairs
    assert len(pairs) == 9


def test_consecutive_game_dates_share_the_overlapping_snapshot():
    pairs = h.line_snapshots(["2026-01-15", "2026-01-16"])
    assert len(pairs) == len(set(pairs)) == 17      # 9 + 9 less the shared 2026-01-15 22Z
    assert pairs == sorted(pairs, reverse=True)      # newest first


def test_the_meter_stops_before_the_floor_and_before_the_ceiling():
    m = h.Meter(ceiling=1_000, floor=2_200_000)
    assert m.stop_reason(30) is None                 # no balance read yet
    m.remaining = 2_200_020
    assert "floor" in m.stop_reason(30)
    m.remaining = 3_000_000
    m.spent = 980
    assert "ceiling" in m.stop_reason(30)


def test_a_dropped_connection_replays_the_whole_write(monkeypatch):
    from data.db import ConnectionLost
    monkeypatch.setattr(h.time, "sleep", lambda s: None)

    class Conn:
        rolled = 0

        def rollback(self):
            self.rolled += 1

    calls = []

    def write():
        calls.append(1)
        if len(calls) == 1:
            raise ConnectionLost("connection lost at commit")

    assert h._write_with_retry(Conn(), write, "x") is True
    assert len(calls) == 2


def test_a_write_that_keeps_failing_is_reported_not_marked_stored(monkeypatch):
    from data.db import ConnectionLost
    monkeypatch.setattr(h.time, "sleep", lambda s: None)

    class Conn:
        def rollback(self):
            pass

    def write():
        raise ConnectionLost("gone")

    assert h._write_with_retry(Conn(), write, "x", attempts=3) is False


def test_an_unrelated_error_is_not_swallowed(monkeypatch):
    monkeypatch.setattr(h.time, "sleep", lambda s: None)

    class Conn:
        def rollback(self):
            pass

    with pytest.raises(ValueError):
        h._write_with_retry(Conn(), lambda: (_ for _ in ()).throw(ValueError("bug")), "x")


BOOK = [
    {"key": "h2h_h1", "outcomes": [{"name": "Detroit Pistons", "price": -218},
                                   {"name": "Phoenix Suns", "price": 180}]},
    {"key": "spreads_q1", "outcomes": [{"name": "Detroit Pistons", "price": -118, "point": -1.5},
                                       {"name": "Phoenix Suns", "price": -102, "point": 1.5}]},
    {"key": "totals_h1", "outcomes": [{"name": "Over", "price": -112, "point": 112.5},
                                      {"name": "Under", "price": -108, "point": 112.5}]},
    {"key": "team_totals", "outcomes": [
        {"name": "Over", "description": "Detroit Pistons", "price": -118, "point": 112.5},
        {"name": "Under", "description": "Detroit Pistons", "price": -102, "point": 112.5},
        {"name": "Over", "description": "Phoenix Suns", "price": -102, "point": 106.5},
        {"name": "Under", "description": "Phoenix Suns", "price": -118, "point": 106.5},
        {"name": "Over", "description": "Some Other Team", "price": -110, "point": 99.5}]},
]


def test_derivative_markets_parse_into_the_odds_shape():
    rows = {r["market"]: r for r in h.parse_derivatives(BOOK, "Detroit Pistons", "DET", "PHX")}
    assert rows["h2h_h1"]["home_price"] == -218 and rows["h2h_h1"]["away_price"] == 180
    assert rows["spreads_q1"]["spread_home"] == -1.5          # the HOME number
    assert rows["totals_h1"]["total_line"] == 112.5
    assert (rows["team_totals_home"]["total_line"], rows["team_totals_home"]["over_price"]) == (112.5, -118)
    assert (rows["team_totals_away"]["total_line"], rows["team_totals_away"]["under_price"]) == (106.5, -118)
    # a team that is not in the game is never filed under either side
    assert sum(1 for r in h.parse_derivatives(BOOK, "Detroit Pistons", "DET", "PHX")
               if r["market"].startswith("team_totals")) == 2
