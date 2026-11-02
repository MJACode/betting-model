"""The postseason prop purchase (data/ingestors/nba_odds_history.py): rows land in their own
table, `games` is never touched, and a stored game is not bought twice."""
from __future__ import annotations

from data.ingestors import nba_odds_history as N


class _Resp:
    status_code = 200

    def __init__(self, body):
        self._body = body

    def json(self):
        return self._body


class _Meter:
    def __init__(self):
        self.calls = []

    def get(self, url, params):
        self.calls.append(url)
        if url.endswith("/events"):
            return _Resp({"data": [
                {"id": "e1", "commence_time": "2025-04-20T00:00:00Z",
                 "home_team": "Denver Nuggets", "away_team": "Los Angeles Lakers"},
                {"id": "e2", "commence_time": "2025-04-20T02:30:00Z",
                 "home_team": "Boston Celtics", "away_team": "Miami Heat"}]})
        return _Resp({"timestamp": "2025-04-19T23:00:00Z", "data": {"bookmakers": [
            {"key": "draftkings", "markets": [{"key": "player_points", "outcomes": [
                {"name": "Over", "description": "Nikola Jokic", "price": -110, "point": 27.5},
                {"name": "Under", "description": "Nikola Jokic", "price": -110, "point": 27.5}]}]}]}})

    def stop_reason(self, next_cost):
        return None


class _Conn:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append(sql)
        return self

    def commit(self):
        pass


def _games():
    return [{"game_id": "NBA_2025-04-19_LAL_DEN", "game_date": "2025-04-19", "home": "DEN", "away": "LAL"},
            {"game_id": "NBA_2025-04-19_MIA_BOS", "game_date": "2025-04-19", "home": "BOS", "away": "MIA",
             "done": True}]


def test_postseason_rows_go_to_their_writer_and_games_is_left_alone():
    written = []
    conn, meter = _Conn(), _Meter()
    s = N.buy_props_date(conn, meter, "2025-04-19", _games(), 60,
                         write=lambda c, rows: written.extend(rows), stamp_games=False)
    assert s["events"] == 1 and len(written) == 1 and written[0]["game_id"] == "NBA_2025-04-19_LAL_DEN"
    assert written[0]["market"] == "player_points" and written[0]["line"] == 27.5
    assert not any("UPDATE games" in q for q in conn.sql)


def test_a_stored_game_is_not_bought_again():
    conn, meter = _Conn(), _Meter()
    N.buy_props_date(conn, meter, "2025-04-19", _games(), 60, write=lambda c, r: None, stamp_games=False)
    assert sum(u.endswith("/odds") for u in meter.calls) == 1


def test_the_regular_season_path_still_stamps_games():
    conn, meter = _Conn(), _Meter()
    N.buy_props_date(conn, meter, "2025-04-19", _games(), 60, write=lambda c, r: None)
    assert any("UPDATE games" in q for q in conn.sql)
