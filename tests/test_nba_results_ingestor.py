"""NBA finals + box scores from ESPN (data/ingestors/nba_results_ingestor.py).

Fixtures are REAL ESPN payloads, trimmed (2026-10-15):
  espn_nba_scoreboard_2026-04-10.json  15 finals, every ESPN-only team code
  espn_nba_scoreboard_2026-04-04.json  SAS @ DEN 136-134 in overtime
  espn_nba_summary_401811026.json      DET @ CHA 118-100, two DNPs
The same parser was run DRY over 2026-04-01..12 against production and matched
all 2,061 nba_api box rows stat for stat (three minutes off by one, rounding).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data.ingestors import nba_results_ingestor as nri
from data.ingestors.nba_espn_box import (
    box_team_totals, fill_missing, parse_nba_box, parse_nba_dnp, parse_nba_scoreboard,
)

FIX = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


BOARD_0410 = _load("espn_nba_scoreboard_2026-04-10.json")
BOARD_0404 = _load("espn_nba_scoreboard_2026-04-04.json")
SUMMARY = _load("espn_nba_summary_401811026.json")
GID = "NBA_2026-04-10_DET_CHA"
EVENT = "401811026"
AFTER = datetime(2026, 4, 11, 12, 0, tzinfo=timezone.utc)


# ── parsers ──────────────────────────────────────────────────────────────────

def test_scoreboard_maps_espn_codes_and_dates_games_by_their_et_tip():
    games = {g["game_id"]: g for g in parse_nba_scoreboard(BOARD_0410, "2026-04-10")}
    assert len(games) == 15
    # ESPN GS / NO / NY / SA / UTAH / WSH -> ours
    for gid in ("NBA_2026-04-10_GSW_SAC", "NBA_2026-04-10_NOP_BOS",
                "NBA_2026-04-10_TOR_NYK", "NBA_2026-04-10_DAL_SAS",
                "NBA_2026-04-10_MEM_UTA", "NBA_2026-04-10_MIA_WAS"):
        assert gid in games, gid
    # 2026-04-11T02:30Z is 22:30 ET on the 10th
    lal = games["NBA_2026-04-10_PHX_LAL"]
    assert lal["commence_time"] == "2026-04-11T02:30Z"
    assert (lal["home_score"], lal["away_score"]) == (101, 73)
    assert lal["went_to_ot"] == 0 and lal["season_type"] == 2
    cha = games[GID]
    assert (cha["home"], cha["away"], cha["home_score"], cha["away_score"]) == ("CHA", "DET", 100, 118)
    assert cha["event_id"] == EVENT


def test_overtime_comes_from_the_period_count():
    games = {g["game_id"]: g for g in parse_nba_scoreboard(BOARD_0404, "2026-04-04")}
    assert games["NBA_2026-04-04_SAS_DEN"]["went_to_ot"] == 1
    assert games["NBA_2026-04-04_SAS_DEN"]["period"] == 5


def test_a_non_nba_opponent_is_dropped_not_invented():
    board = copy.deepcopy(BOARD_0410)
    board["events"][0]["competitions"][0]["competitors"][1]["team"] = {
        "abbreviation": "MAC", "displayName": "Maccabi Ra'anana"}
    assert len(parse_nba_scoreboard(board, "2026-04-10")) == 14


def test_box_points_add_up_to_the_final_and_dnps_are_separate():
    players = parse_nba_box(SUMMARY)
    by_team = {}
    for p in players:
        by_team[p["team"]] = by_team.get(p["team"], 0) + p["points"]
    assert by_team == {"DET": 118, "CHA": 100} == box_team_totals(SUMMARY)
    assert len(players) == 27                       # 14 DET + 13 CHA played
    assert all(p["espn_id"] for p in players)
    harris = next(p for p in players if p["name"] == "Tobias Harris")
    assert harris["espn_id"] == "6440" and harris["starter"] is True
    assert (harris["points"], harris["rebounds"], harris["turnovers"]) == (8, 6, 1)
    assert (harris["fg_made"], harris["fg_att"]) == (3, 5)
    dnp = parse_nba_dnp(SUMMARY)
    assert {d["name"] for d in dnp} == {"Tolu Smith", "Isaac Jones"}
    assert {d["reason"] for d in dnp} == {"COACH'S DECISION"}


def test_a_no_minutes_row_is_a_dnp_not_a_zero_stat_line():
    """ESPN's '--' minutes with every count zero: stats.nba.com has no row for
    such a player, and a prop on him must void, not lose."""
    s = copy.deepcopy(SUMMARY)
    ath = s["boxscore"]["players"][1]["statistics"][0]["athletes"][-1]
    name = ath["athlete"]["displayName"]
    ath["stats"] = ["--", "0", "0-0", "0-0", "0-0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]
    assert name not in {p["name"] for p in parse_nba_box(s)}
    assert {"name": name, "reason": "NO MINUTES"}.items() <= next(
        d for d in parse_nba_dnp(s) if d["name"] == name).items()


# ── player ids ───────────────────────────────────────────────────────────────

def _resolver():
    xwalk = {"6440": "202699"}                         # ESPN Tobias Harris -> NBA.com
    log = [
        ("202699", "Tobias Harris", "DET"),
        ("1630595", "Cade Cunningham", "DET"),
        ("1629130", "Duncan Robinson", "MIA"),         # traded: different team
        ("111", "Same Name", "DET"), ("222", "Same Name", "DET"),
        ("333", "Taken Name", "DET"),
    ]
    xwalk["999"] = "333"                               # 333 is ESPN 999's
    return nri.PlayerResolver(xwalk, log)


def test_resolution_order():
    r = _resolver()
    assert r.resolve("6440", "Somebody Else", "CHA") == ("202699", "crosswalk")
    assert r.resolve("1", "Cade Cunningham", "DET") == ("1630595", "name_team")
    assert r.resolve("2", "Duncan Robinson", "DET") == ("1629130", "name_league")
    assert r.resolve("3", "Rookie Guy", "DET") == ("espn:3", "fallback")


def test_ambiguous_or_claimed_names_fall_back():
    r = _resolver()
    assert r.resolve("4", "Same Name", "DET") == ("espn:4", "fallback")
    # 333 belongs to ESPN athlete 999; a different athlete with that name
    # must not take it
    assert r.resolve("5", "Taken Name", "DET") == ("espn:5", "fallback")
    assert r.resolve("999", "Taken Name", "DET") == ("333", "crosswalk")


def test_a_rookie_keeps_one_id_across_games():
    """Game 1 logs him as espn:42; game 2 finds that id by name."""
    r = nri.PlayerResolver({}, [("espn:42", "Rookie Guy", "DET")])
    assert r.resolve("42", "Rookie Guy", "DET") == ("espn:42", "name_team")
    # ...and another ESPN athlete with the same name does not take it
    assert r.resolve("43", "Rookie Guy", "DET") == ("espn:43", "fallback")


def test_the_fallback_cannot_collide_with_an_nba_id():
    assert nri.fallback_id("4433249", "x") == "espn:4433249"
    assert not nri.fallback_id("4433249", "x").isdigit()
    assert nri.fallback_id("", "D'Angelo Russell Jr.") == "espn:name:dangelo-russell"


def test_one_unresolved_player_does_not_drop_the_game():
    game = {"game_id": GID, "game_date": "2026-04-10", "season": 2026,
            "home": "CHA", "away": "DET"}
    players = parse_nba_box(SUMMARY)
    rows, fallbacks = nri.build_log_rows(players, _resolver(), game)
    assert len(rows) == len(players) == 27
    assert len(fallbacks) == 24                        # Harris, Cade, Robinson resolve
    assert {r["player_id"] for r in rows if r["player_name"] == "Duncan Robinson"} == {"1629130"}
    assert {r["player_id"] for r in rows if r["player_name"] == "Tobias Harris"} == {"202699"}
    assert all(type(r["is_starter"]) is int for r in rows)


def test_two_box_rows_never_share_an_id():
    game = {"game_id": GID, "game_date": "2026-04-10", "season": 2026}
    r = nri.PlayerResolver({"1": "777", "2": "777"}, [])
    players = [dict(parse_nba_box(SUMMARY)[0], espn_id="1", name="A"),
               dict(parse_nba_box(SUMMARY)[1], espn_id="2", name="B")]
    rows, fb = nri.build_log_rows(players, r, game)
    assert [x["player_id"] for x in rows] == ["777", "espn:2"]


# ── the step, against an in-memory store ─────────────────────────────────────

class _Conn:
    def __init__(self):
        self.commits = 0

    def execute(self, sql, params=None):
        return self

    def fetchone(self):
        return None

    def fetchall(self):
        return []

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class FakeStore:
    """games, log and dnp in dicts; every write recorded."""

    def __init__(self, games, log=None, xwalk=None):
        self.conn = _Conn()
        self.games = {g["game_id"]: dict(g) for g in games}
        self.log = dict(log or {})            # (player_id, game_id) -> row
        self.dnp = {}
        self.xwalk = xwalk or {}
        self.writes = []

    def window_games(self, start, end):
        out = {}
        for gid, g in self.games.items():
            if start <= g["game_date"] <= end:
                out[gid] = {**g, "logged": self.is_logged(gid)}
        return out

    def resolver(self, since):
        return nri.PlayerResolver(self.xwalk, [(k[0], r["player_name"], r["team"])
                                               for k, r in self.log.items()])

    def is_logged(self, gid):
        return any(k[1] == gid for k in self.log)

    def write_score(self, action, game):
        self.writes.append(("score", action["kind"], action["game_id"]))
        g = self.games[action["game_id"]]
        g.update(home_score=action["home_score"], away_score=action["away_score"],
                 home_win=action["home_win"], source="games")
        if action["went_to_ot"] is not None:
            g["went_to_ot"] = action["went_to_ot"]
        return 1

    def upsert_log(self, rows):
        self.writes.append(("log", len(rows)))
        for r in rows:
            self.log[(r["player_id"], r["game_id"])] = r
        return len(rows)

    def ensure_dnp_table(self):
        pass

    def has_dnp(self, gid):
        return any(k[0] == gid for k in self.dnp)

    def upsert_dnp(self, rows):
        self.writes.append(("dnp", len(rows)))
        for r in rows:
            self.dnp[(r["game_id"], r["espn_athlete_id"])] = r
        return len(rows)


def _game(**kw):
    g = {"game_id": GID, "game_date": "2026-04-10", "season": 2026, "home": "CHA",
         "away": "DET", "home_score": None, "away_score": None, "went_to_ot": 0,
         "commence_time": "2026-04-10T23:00:00+00:00", "source": "games"}
    g.update(kw)
    return g


class _ESPN:
    def __init__(self, board=BOARD_0410, summary=SUMMARY):
        self.board, self.summary, self.calls = board, summary, []

    def __call__(self, url, params):
        self.calls.append((url.rsplit("/", 1)[-1], params))
        if url.endswith("scoreboard"):
            return self.board
        if params.get("event") == EVENT:
            return self.summary
        raise AssertionError(f"unexpected summary fetch {params}")


def _run(store, espn, **kw):
    kw.setdefault("now", AFTER)
    return nri.ingest_nba_results(dates=["2026-04-10"], get_json=espn, store=store,
                                  sleep=0, **kw)


def test_a_final_is_scored_and_its_whole_box_logged():
    store, espn = FakeStore([_game()]), _ESPN()
    t = _run(store, espn)
    g = store.games[GID]
    assert (g["home_score"], g["away_score"], g["home_win"]) == (100, 118, 0)
    assert t["scores_filled"] == 1 and t["box_games"] == 1
    assert t["box_rows"] == 27 and len(store.log) == 27
    assert t["dnp_rows"] == 2 and len(store.dnp) == 2
    # the 14 other finals that night have no games row here: ignored
    assert t["not_in_games"] == 14
    assert store.conn.commits == 1


def test_a_rerun_writes_nothing_and_fetches_nothing():
    store, espn = FakeStore([_game()]), _ESPN()
    _run(store, espn)
    before = list(store.writes)
    espn2 = _ESPN()
    t = _run(store, espn2)
    assert store.writes == before
    assert espn2.calls == [], "an idle pass must not call ESPN"
    assert t["dates_fetched"] == 0
    # and a forced recheck still never rewrites a scored, logged game
    espn3 = _ESPN()
    _run(store, espn3, recheck=True)
    assert store.writes == before


def test_a_logged_game_with_no_score_gets_the_score_without_a_box_fetch():
    log = {("x", GID): {"player_id": "x", "player_name": "X", "team": "CHA", "game_id": GID}}
    store, espn = FakeStore([_game()], log=log), _ESPN()
    t = _run(store, espn)
    assert t["scores_filled"] == 1 and t["box_games"] == 0
    assert [c[0] for c in espn.calls] == ["scoreboard"]


def test_a_different_stored_score_is_never_overwritten():
    store, espn = FakeStore([_game(home_score=99, away_score=118)]), _ESPN()
    t = _run(store, espn)
    assert t["score_conflicts"] == 1
    assert store.games[GID]["home_score"] == 99
    assert not [w for w in store.writes if w[0] == "score"]
    assert t["box_games"] == 1                  # the box still logs


def test_preseason_and_unknown_games_write_nothing():
    board = copy.deepcopy(BOARD_0410)
    for ev in board["events"]:
        ev["season"] = {"year": 2027, "type": 1}
    store, espn = FakeStore([_game()]), _ESPN(board=board)
    t = _run(store, espn)
    assert t["preseason"] == 15 and store.writes == []


def test_a_game_that_has_not_started_is_not_fetched():
    store, espn = FakeStore([_game()]), _ESPN()
    t = _run(store, espn, now=datetime(2026, 4, 10, 20, 0, tzinfo=timezone.utc))
    assert espn.calls == [] and t["dates_fetched"] == 0


def test_an_incomplete_box_is_left_for_the_next_pass():
    s = copy.deepcopy(SUMMARY)
    del s["boxscore"]["players"][0]["statistics"][0]["athletes"][0]   # drop a DET scorer
    store, espn = FakeStore([_game()]), _ESPN(summary=s)
    t = _run(store, espn)
    assert t["box_incomplete"] == 1 and store.log == {}
    assert t["scores_filled"] == 1               # the score is still written
    t2 = _run(store, _ESPN())                    # ESPN finishes the box
    assert t2["box_games"] == 1 and len(store.log) == 27


def test_a_regular_season_game_only_the_schedule_has_is_inserted():
    store, espn = FakeStore([_game(source="schedule", went_to_ot=None)]), _ESPN()
    t = _run(store, espn)
    assert ("score", "insert", GID) in store.writes
    assert t["games_inserted"] == 1


def test_overtime_is_corrected_on_an_already_scored_game():
    board = copy.deepcopy(BOARD_0410)
    ev = next(e for e in board["events"] if e["id"] == EVENT)
    ev["status"]["period"] = 5
    log = {("x", GID): {"player_id": "x", "player_name": "X", "team": "CHA", "game_id": GID}}
    store = FakeStore([_game(home_score=100, away_score=118, went_to_ot=0)], log=log)
    t = _run(store, _ESPN(board=board), recheck=True)
    assert t["ot_fixed"] == 1 and store.games[GID]["went_to_ot"] == 1


def test_a_recheck_adds_the_dnp_list_to_a_logged_game_and_nothing_else():
    log = {("x", GID): {"player_id": "x", "player_name": "X", "team": "CHA", "game_id": GID}}
    store = FakeStore([_game(home_score=100, away_score=118)], log=log)
    t = _run(store, _ESPN(), recheck=True)
    assert store.writes == [("dnp", 2)]
    assert t["dnp_rows"] == 2 and t["box_games"] == 0 and len(store.log) == 1
    _run(store, _ESPN(), recheck=True)
    assert store.writes == [("dnp", 2)], "the second recheck wrote again"


def test_a_game_missed_during_an_outage_is_healed_past_the_lookback():
    """Ten days after the game: outside the 3-day lookback, inside the 14-day
    self-heal reach, and only because it still lacks a score."""
    later = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    store, espn = FakeStore([_game()]), _ESPN()
    t = nri.ingest_nba_results(run_date="2026-04-20", get_json=espn, store=store,
                               sleep=0, now=later)
    assert t["scores_filled"] == 1 and t["dates_fetched"] == 1
    store2, espn2 = FakeStore([_game()]), _ESPN()
    nri.ingest_nba_results(run_date="2026-04-20", get_json=espn2, store=store2,
                           sleep=0, now=later, heal_days=0)
    assert espn2.calls == [], "the lookback alone does not reach ten days back"


def test_dry_run_writes_nothing_and_returns_the_plan():
    store, espn = FakeStore([_game()]), _ESPN()
    t = _run(store, espn, dry_run=True)
    assert store.writes == []
    assert t["planned_scores"][0]["kind"] == "fill"
    assert len(t["planned_box"][0]["rows"]) == 27


def test_a_failed_scoreboard_turns_the_step_red():
    store = FakeStore([_game()])

    def boom(url, params):
        raise OSError("403 Forbidden")

    with pytest.raises(RuntimeError):
        _run(store, boom)
    t = _run(store, boom, raise_on_error=False)
    assert t["errors"] == 1


def test_settlements_fill_missing_logs_a_game_with_a_rookie_in_it(monkeypatch):
    """The old fill_missing left a game unlogged when any name did not
    resolve, so a rookie's games never reached the log. It now logs the game,
    the rookie under espn:<id>."""
    store = FakeStore([_game(home_score=100, away_score=118)],
                      xwalk={"6440": "202699"})
    monkeypatch.setattr(nri, "PgStore", lambda conn: store)
    monkeypatch.setattr(nri, "SUMMARY_SLEEP", 0)
    monkeypatch.setattr(nri, "datetime", _FixedNow)
    out = fill_missing({"2026-04-10": {GID: {"202699"}}}, get_json=_ESPN(),
                       connect=lambda: store.conn)
    assert out["games"] == 1
    assert store.log[("202699", GID)]["points"] == 8
    assert ("espn:5107199", GID) in store.log          # Daniss Jenkins, unresolved here


class _FixedNow(datetime):
    @classmethod
    def now(cls, tz=None):
        return AFTER if tz else AFTER.replace(tzinfo=None)
