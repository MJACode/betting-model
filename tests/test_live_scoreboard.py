"""Scoreboard live scores for NFL, NBA and NHL (data/ingestors/live_scoreboard.py).

Matt, 2026-10-29: show live games and scores on the Scoreboard. The NBA
finals are read from a saved ESPN payload; the in-progress events are built
in the same document shape.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from data.ingestors import live_scoreboard as ls

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "espn_nba_scoreboard_2026-04-10.json"


def _event(state, *, home=("GB", "Green Bay Packers", "9"), away=("CAR", "Carolina Panthers", "29"),
           hs="17", as_="10", period=3, clock="7:42", name="STATUS_IN_PROGRESS",
           completed=False, situation=None, date="2026-10-30T00:15Z", short=""):
    comp = {"competitors": [
        {"id": home[2], "homeAway": "home", "score": hs,
         "team": {"id": home[2], "abbreviation": home[0], "displayName": home[1]}},
        {"id": away[2], "homeAway": "away", "score": as_,
         "team": {"id": away[2], "abbreviation": away[0], "displayName": away[1]}},
    ]}
    if situation is not None:
        comp["situation"] = situation
    return {"id": "401", "date": date, "competitions": [comp],
            "status": {"period": period, "displayClock": clock,
                       "type": {"state": state, "name": name,
                                "completed": completed, "shortDetail": short}}}


def test_real_nba_finals_parse_with_our_codes():
    data = json.loads(FIX.read_text(encoding="utf-8"))
    rows = ls.parse_scoreboard("NBA", data)
    assert rows, "the saved payload holds completed games"
    assert all(r["state"] == "post" for r in rows)
    assert all(len(r["home"]) == 3 and len(r["away"]) == 3 for r in rows)
    assert all(r["home_score"] is not None for r in rows)
    first = next(r for r in rows if r["home"] == "CHA")
    assert first["home_score"] == 100


def test_in_progress_nfl_game_carries_clock_possession_and_down():
    ev = _event("in", situation={"possession": "9", "downDistanceText": "2nd & 7 at CAR 35"})
    [row] = ls.parse_scoreboard("NFL", {"events": [ev]})
    assert row["state"] == "in"
    assert (row["home"], row["away"]) == ("GB", "CAR")
    assert (row["home_score"], row["away_score"]) == (17, 10)
    assert row["clock_label"] == "Q3 7:42"
    assert row["possession"] == "home"
    assert row["situation"] == "2nd & 7 at CAR 35"
    assert row["event_date"] == "2026-10-29"


def test_pregame_and_postponed_write_nothing():
    pre = _event("pre", hs="0", as_="0")
    ppd = _event("post", name="STATUS_POSTPONED", completed=False)
    assert ls.parse_scoreboard("NFL", {"events": [pre, ppd]}) == []


def test_espn_abbrevs_that_are_not_ours_map_by_name():
    ev = _event("in", home=("WSH", "Washington Commanders", "28"), away=("LAR", "Los Angeles Rams", "14"))
    [row] = ls.parse_scoreboard("NFL", {"events": [ev]})
    assert (row["home"], row["away"]) == ("WAS", "LA")
    hockey = _event("in", home=("TB", "Tampa Bay Lightning", "20"), away=("UTAH", "Utah Mammoth", "129764"),
                    period=2, clock="12:15")
    [h] = ls.parse_scoreboard("NHL", {"events": [hockey]})
    assert (h["home"], h["away"]) == ("TBL", "UTA")
    assert h["clock_label"] == "P2 12:15"


def test_clock_labels():
    assert ls.clock_label("NBA", {"period": 2, "displayClock": "0.0",
                                  "type": {"state": "in", "name": "STATUS_HALFTIME"}}) == "Half"
    assert ls.clock_label("NHL", {"period": 2, "displayClock": "0:00",
                                  "type": {"state": "in", "name": "STATUS_END_PERIOD"}}) == "End P2"
    assert ls.clock_label("NFL", {"period": 5, "displayClock": "8:01",
                                  "type": {"state": "in", "name": "STATUS_IN_PROGRESS"}}) == "OT 8:01"
    assert ls.clock_label("NBA", {"period": 4, "type": {"state": "post", "shortDetail": "Final/OT"}}) == "Final/OT"


GAMES = [
    {"game_id": "NFL_2026_08_CAR_GB", "sport": "NFL", "game_date": "2026-10-29",
     "home_team": "GB", "away_team": "CAR", "home_score": None, "away_score": None,
     "commence_time": "2026-10-30T00:15:00+00:00"},
    {"game_id": "NBA_2026-10-29_SAC_NOP", "sport": "NBA", "game_date": "2026-10-29",
     "home_team": "NOP", "away_team": "SAC", "home_score": None, "away_score": None,
     "commence_time": "2026-10-30T00:10:00+00:00"},
    {"game_id": "NHL_2026-10-28_PHI_WSH", "sport": "NHL", "game_date": "2026-10-28",
     "home_team": "WSH", "away_team": "PHI", "home_score": 5, "away_score": 2,
     "commence_time": "2026-10-28T23:30:00Z"},
]


def test_due_sports_is_started_unsettled_and_not_already_final():
    before = datetime(2026, 10, 29, 23, 0, tzinfo=timezone.utc)
    assert ls.due_sports(GAMES, set(), before) == set()
    during = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)
    assert ls.due_sports(GAMES, set(), during) == {"NFL", "NBA"}
    assert ls.due_sports(GAMES, {"NFL_2026_08_CAR_GB"}, during) == {"NBA"}
    late = datetime(2026, 10, 30, 8, 0, tzinfo=timezone.utc)
    assert ls.due_sports(GAMES, set(), late) == set()


def test_match_attaches_our_game_id_and_drops_strangers():
    rows = ls.parse_scoreboard("NFL", {"events": [
        _event("in"),
        _event("in", home=("KC", "Kansas City Chiefs", "12"), away=("DEN", "Denver Broncos", "7")),
    ]})
    out = ls.match_games("NFL", rows, GAMES)
    assert [r["game_id"] for r in out] == ["NFL_2026_08_CAR_GB"]
    assert out[0]["game_date"] == "2026-10-29"


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, games, finished=()):
        self.games, self.finished, self.upserts, self.commits = games, list(finished), [], 0

    def execute(self, sql, params=None):
        if "to_regclass" in sql:
            return _Cur([(True,)])
        if "FROM public.games" in sql:
            cols = ("game_id", "sport", "game_date", "home_team", "away_team",
                    "home_score", "away_score", "commence_time")
            return _Cur([tuple(g[c] for c in cols) for g in self.games])
        if "FROM public.live_scoreboard" in sql:
            return _Cur([(g,) for g in self.finished])
        if "INSERT INTO public.live_scoreboard" in sql:
            self.upserts.append(params)
            return _Cur([])
        raise AssertionError(sql)

    def commit(self):
        self.commits += 1


def test_run_once_polls_only_live_sports_and_upserts():
    calls = []

    def fetch(sport, dates):
        calls.append(sport)
        return {"events": [_event("in", situation={"possession": "29"})]} if sport == "NFL" else {"events": []}

    conn = _Conn(GAMES)
    now = datetime(2026, 10, 30, 1, 0, tzinfo=timezone.utc)
    out = ls.run_once(conn, now=now, fetch=fetch)
    assert sorted(calls) == ["NBA", "NFL"]
    assert out == {"NBA": 0, "NFL": 1}
    [row] = conn.upserts
    assert row["game_id"] == "NFL_2026_08_CAR_GB" and row["possession"] == "away"
    assert row["snapshot_at"] == now.isoformat()


def test_idle_tick_makes_no_http_call():
    def fetch(sport, dates):
        raise AssertionError("no game is live; ESPN must not be called")

    conn = _Conn(GAMES)
    morning = datetime(2026, 10, 29, 13, 40, tzinfo=timezone.utc)
    assert ls.run_once(conn, now=morning, fetch=fetch) == {}


def test_scheduler_runs_it_on_the_poller_service():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert '"live_scoreboard"' in src[src.index("_POLLER_JOBS = {"):src.index("_ALWAYS_JOBS")]
    assert 'id="live_scoreboard"' in src


def _load(name: str) -> dict:
    return json.loads((ROOT / "tests" / "fixtures" / name).read_text(encoding="utf-8"))


def test_real_nfl_scoreboards_map_to_our_codes_and_scores():
    """Fetched 2026-10-29 from site.api.espn.com. LAR is our LA, WSH is our WAS.
    Scores are the games rows for those dates."""
    sunday = _load("espn_nfl_scoreboard_2026-10-18.json")
    rows = ls.parse_scoreboard("NFL", sunday)
    assert len(rows) == len(sunday["events"])
    by = {(r["away"], r["home"], r["event_date"]): r for r in rows}
    assert (by[("ARI", "LA", "2026-10-18")]["away_score"],
            by[("ARI", "LA", "2026-10-18")]["home_score"]) == (18, 16)
    assert by[("ARI", "LA", "2026-10-18")]["clock_label"] == "Final"
    assert (by[("HOU", "JAX", "2026-10-18")]["away_score"],
            by[("HOU", "JAX", "2026-10-18")]["home_score"]) == (34, 31)
    ot = next(r for r in rows if r["clock_label"] == "Final/OT")
    assert ot["period"] == 5 and (ot["away"], ot["home"]) == ("PIT", "TB")
    monday = _load("espn_nfl_scoreboard_2026-10-19.json")
    [wsh] = ls.parse_scoreboard("NFL", monday)
    assert (wsh["away"], wsh["home"], wsh["event_date"]) == ("WAS", "SF", "2026-10-19")
    assert (wsh["away_score"], wsh["home_score"]) == (17, 23)
    games = [
        {"game_id": "NFL_2026_06_ARI_LA", "sport": "NFL", "game_date": "2026-10-18",
         "home_team": "LA", "away_team": "ARI"},
        {"game_id": "NFL_2026_06_HOU_JAX", "sport": "NFL", "game_date": "2026-10-18",
         "home_team": "JAX", "away_team": "HOU"},
        {"game_id": "NFL_2026_06_WAS_SF", "sport": "NFL", "game_date": "2026-10-19",
         "home_team": "SF", "away_team": "WAS"},
    ]
    matched = ls.match_games("NFL", rows + [wsh], games)
    assert {r["game_id"] for r in matched} == {
        "NFL_2026_06_ARI_LA", "NFL_2026_06_HOU_JAX", "NFL_2026_06_WAS_SF"}


def test_real_nhl_scoreboards_map_the_abbreviations_espn_does_not_share():
    """Fetched 2026-10-29. Scoreboard spelling is LA/NJ/SJ/TB/UTA, not ours.
    Final/SO is period 5. Scores are the games rows for those dates."""
    day = _load("espn_nhl_scoreboard_2026-10-24.json")
    rows = ls.parse_scoreboard("NHL", day)
    assert len(rows) == len(day["events"])
    by = {(r["away"], r["home"]): r for r in rows}
    assert (by[("LAK", "NJD")]["away_score"], by[("LAK", "NJD")]["home_score"]) == (1, 3)
    assert by[("LAK", "NJD")]["event_date"] == "2026-10-24"
    assert (by[("SJS", "BOS")]["away_score"], by[("SJS", "BOS")]["home_score"]) == (4, 6)
    assert (by[("TBL", "UTA")]["away_score"], by[("TBL", "UTA")]["home_score"]) == (4, 5)
    assert by[("TBL", "UTA")]["clock_label"] == "Final/OT"
    assert by[("TBL", "UTA")]["event_date"] == "2026-10-24"
    assert (by[("BUF", "WSH")]["away_score"], by[("BUF", "WSH")]["home_score"]) == (3, 4)
    later = _load("espn_nhl_scoreboard_2026-10-27.json")
    rows2 = ls.parse_scoreboard("NHL", later)
    assert len(rows2) == len(later["events"])
    so = next(r for r in rows2 if r["clock_label"] == "Final/SO")
    assert (so["away"], so["home"], so["period"], so["event_date"]) == ("NYI", "NSH", 5, "2026-10-27")
    uta = next(r for r in rows2 if (r["away"], r["home"]) == ("MIN", "UTA"))
    assert (uta["away_score"], uta["home_score"], uta["event_date"]) == (3, 1, "2026-10-27")
    bare = json.loads(json.dumps(day))
    for ev in bare["events"]:
        for c in ev["competitions"][0]["competitors"]:
            c["team"]["displayName"] = None
    assert len(ls.parse_scoreboard("NHL", bare)) == len(day["events"])


def test_abbreviation_only_maps_both_utah_spellings_and_drops_unknowns():
    assert ls.team_code("NHL", "UTAH", None) == "UTA"
    assert ls.team_code("NHL", "UTA", None) == "UTA"
    assert ls.team_code("NHL", "LA", None) == "LAK"
    assert ls.team_code("NHL", "NJ", None) == "NJD"
    assert ls.team_code("NHL", "SJ", None) == "SJS"
    assert ls.team_code("NHL", "TB", None) == "TBL"
    assert ls.team_code("NFL", "LAR", None) == "LA"
    assert ls.team_code("NFL", "WSH", None) == "WAS"
    assert ls.team_code("NFL", "JAX", None) == "JAX"
    assert ls.team_code("NFL", "XYZ", None) is None
    assert ls.team_code("NHL", "ZZZ", None) is None


def test_an_abbreviation_that_is_not_ours_is_dropped_and_warned():
    from loguru import logger

    ev = _event("post", home=("XYZ", "Not A Club", "1"), away=("GB", "Green Bay Packers", "9"),
                completed=True, name="STATUS_FINAL", short="Final")
    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        rows = ls.parse_scoreboard("NFL", {"events": [ev]})
    finally:
        logger.remove(sink)
    assert rows == []
    assert any("XYZ" in m for m in messages)


def test_migration_is_declared_before_the_posted_stake_pair_and_grants_select_only():
    mig = (ROOT / "data" / "view_migrations.py").read_text(encoding="utf-8")
    assert mig.index("add_live_scoreboard_2026_10_29.sql") < mig.index('"published_pick_units_2026_10_17.sql"')
    sql = (ROOT / "data" / "migrations" / "add_live_scoreboard_2026_10_29.sql").read_text(encoding="utf-8")
    assert "REVOKE ALL ON public.live_scoreboard FROM anon, authenticated" in sql
    assert "GRANT SELECT ON public.live_scoreboard TO anon, authenticated" in sql
    # The guard returns before any DDL once the table, policy and grant exist.
    assert sql.index("RETURN;") < sql.index("CREATE TABLE")
