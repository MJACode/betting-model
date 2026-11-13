"""Scoreboard % bets / % money (data/ingestors/scoreboard_splits.py).

The game documents follow the v2 shape cut from real Action Network
responses in tests/test_nba_public_splits_ingestor.py. No network, no
database.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import scoreboard_splits as ss

ROOT = Path(__file__).resolve().parents[1]


def _entry(kind, side, value, odds, tix, money, live=False):
    return {"type": kind, "side": side, "value": value, "odds": odds,
            "is_live": live, "book_id": 15,
            "bet_info": {"tickets": {"value": 0, "percent": tix},
                         "money": {"value": 0, "percent": money}}}


def _game(entries, *, start="2026-10-30T00:15:00.000Z",
          home=("GB", "Green Bay Packers"), away=("CAR", "Carolina Panthers")):
    market = {"moneyline": [], "spread": [], "total": []}
    for e in entries:
        market[e["type"]].append(e)
    return {"id": 1, "start_time": start, "status": "scheduled",
            "home_team_id": 1, "away_team_id": 2,
            "teams": [{"id": 1, "abbr": home[0], "full_name": home[1]},
                      {"id": 2, "abbr": away[0], "full_name": away[1]}],
            "markets": {"15": {"event": market}}}


CAR_GB = [
    _entry("spread", "away", 3.5, -108, 47, 53),
    _entry("spread", "home", -3.5, -112, 53, 47),
    _entry("total", "over", 46.5, -120, 60, 70),
    _entry("total", "under", 46.5, 100, 40, 30),
    _entry("moneyline", "away", 0, 160, 0, 0),
    _entry("moneyline", "home", 0, -192, 0, 0),
]

GAMES = [{"game_id": "NFL_2026_08_CAR_GB", "sport": "NFL", "game_date": "2026-10-29",
          "home_team": "GB", "away_team": "CAR",
          "commence_time": "2026-10-30T00:15:00+00:00"}]
BEFORE = datetime(2026, 10, 29, 14, 0, tzinfo=timezone.utc)


def test_rows_carry_bets_and_money_per_side_on_our_game_id():
    counts: dict = {}
    rows = ss.build_rows("NFL", {"games": [_game(CAR_GB)]}, GAMES, BEFORE, counts)
    got = {(r["market"], r["side"]): (r["bet_pct"], r["money_pct"]) for r in rows}
    assert got[("spreads", "away")] == (47.0, 53.0)
    assert got[("spreads", "home")] == (53.0, 47.0)
    assert got[("totals", "over")] == (60.0, 70.0)
    by = {(r["market"], r["side"]): r["line_value"] for r in rows}
    assert by[("spreads", "home")] == -3.5
    assert by[("spreads", "away")] == 3.5
    assert by[("totals", "over")] == 46.5
    assert all(r["game_id"] == "NFL_2026_08_CAR_GB" for r in rows)
    assert counts == {"games": 1}


def test_a_zero_zero_pair_is_missing_not_zero_percent():
    rows = ss.build_rows("NFL", {"games": [_game(CAR_GB)]}, GAMES, BEFORE)
    assert not [r for r in rows if r["market"] == "h2h"]


def test_a_started_game_keeps_its_last_pre_start_split():
    after = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)
    counts: dict = {}
    assert ss.build_rows("NFL", {"games": [_game(CAR_GB)]}, GAMES, after, counts) == []
    assert counts == {"started": 1}


def test_a_team_we_do_not_carry_is_not_matched():
    stranger = _game(CAR_GB, home=("KC", "Kansas City Chiefs"), away=("DEN", "Denver Broncos"))
    counts: dict = {}
    assert ss.build_rows("NFL", {"games": [stranger]}, GAMES, BEFORE, counts) == []
    assert counts == {"unmatched": 1}


def test_abbreviations_that_differ_from_ours_still_match():
    nhl = [{"game_id": "NHL_2026-10-29_UTA_TBL", "sport": "NHL", "game_date": "2026-10-29",
            "home_team": "TBL", "away_team": "UTA", "commence_time": "2026-10-29T23:10:00Z"}]
    game = _game(CAR_GB[:2], start="2026-10-29T23:10:00Z",
                 home=("TB", "Tampa Bay Lightning"), away=("UTAH", "Utah Mammoth"))
    rows = ss.build_rows("NHL", {"games": [game]}, nhl, BEFORE)
    assert {r["game_id"] for r in rows} == {"NHL_2026-10-29_UTA_TBL"}


def test_a_pair_that_does_not_sum_to_100_is_dropped():
    bad = [_entry("spread", "away", 3.5, -108, 47, 53), _entry("spread", "home", -3.5, -112, 70, 47)]
    rows = ss.build_rows("NFL", {"games": [_game(bad)]}, GAMES, BEFORE)
    assert all(r["bet_pct"] is None for r in rows)
    assert [r["money_pct"] for r in rows] == [53.0, 47.0] or [r["money_pct"] for r in rows] == [47.0, 53.0]


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0]

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self):
        self.rows, self.commits = [], 0

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            return _Cur([(True,)])
        if "FROM public.games" in sql:
            g = GAMES[0]
            return _Cur([(g["game_id"], g["sport"], g["game_date"], g["home_team"],
                          g["away_team"], g["commence_time"])])
        raise AssertionError(sql)

    def executemany(self, sql, rows):
        assert "INSERT INTO public.scoreboard_splits" in sql
        self.rows.extend(rows)

    def commit(self):
        self.commits += 1


def test_run_fetches_only_sports_and_days_with_an_unstarted_game(monkeypatch):
    monkeypatch.setattr(ss.time, "sleep", lambda s: None)
    calls = []

    def fetch(sport, day):
        calls.append((sport, day))
        return {"games": [_game(CAR_GB)]}

    conn = _Conn()
    out = ss.run(conn, now=BEFORE, fetch=fetch)
    assert calls == [("NFL", "2026-10-29")]
    assert out["NFL"]["rows"] == 4 and len(conn.rows) == 4


def test_never_written_to_public_betting():
    src = (ROOT / "data" / "ingestors" / "scoreboard_splits.py").read_text(encoding="utf-8")
    assert "INSERT INTO public_betting" not in src
    assert "INSERT INTO public.public_betting" not in src


def test_wired_into_the_refresh_pass_and_migrations():
    sh = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
    assert "par scoreboard-splits" in sh
    mig = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert mig.index("add_scoreboard_splits_2026_10_29.sql") < mig.index('"published_pick_units_2026_10_17.sql"')
    sql = (ROOT / "data" / "migrations" / "add_scoreboard_splits_2026_10_29.sql").read_text(encoding="utf-8")
    assert sql.index("RETURN;") < sql.index("CREATE TABLE")
    assert "GRANT SELECT ON public.scoreboard_splits TO anon, authenticated" in sql
