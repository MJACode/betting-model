"""
Doubleheaders get one game_id per PHYSICAL game, and settlement cannot grade a
pick on the other game's final.

THE BUG (2026-09-25). BAL@NYY was a doubleheader. Every MLB ingestor minted
`MLB_2026-09-25_BAL_NYY` for both games, so game 1's in-play prices (a +3300
NYY price stamped 'open') and its final score landed on the same row as game
2's pre-game board. A game-2 BET settled LOSS at 7:12 PM ET on game 1's box
score, before game 2 had started. CHC@BOS was a split doubleheader the same day.

The fixture is those two doubleheaders as the Stats API lists them (read
2026-09-25): BAL@NYY is TRADITIONAL -- game 2 carries startTimeTBD and a
placeholder start five minutes after game 1 -- and CHC@BOS is SPLIT, with real
times for both.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import data.mlb_game_id as mgi
from data.db_setup import SCHEMA_SQL
from data.ingestors import odds_ingestor as oi
from tracking import paper_tracker as pt

DATE = "2026-09-25"
BAL, NYY, CHC, BOS, NYM, PHI = 110, 147, 112, 111, 121, 143


def _sched(pk, away, home, num, start, tbd=False, dh="S"):
    return {"gamePk": pk, "gameNumber": num, "doubleHeader": dh,
            "gameDate": start, "status": {"startTimeTBD": tbd},
            "teams": {"away": {"team": {"id": away}},
                      "home": {"team": {"id": home}}}}


SCHEDULE = [
    _sched(823491, BAL, NYY, 1, "2026-09-25T20:05:00Z", dh="Y"),
    _sched(823489, BAL, NYY, 2, "2026-09-25T20:10:00Z", tbd=True, dh="Y"),
    _sched(824703, CHC, BOS, 1, "2026-09-25T17:05:00Z"),
    _sched(824706, CHC, BOS, 2, "2026-09-25T21:35:00Z"),
    _sched(900001, NYM, PHI, 1, "2026-09-25T23:05:00Z", dh="N"),
]


@pytest.fixture
def schedule(monkeypatch):
    mgi.clear_cache()
    monkeypatch.setattr(mgi, "_fetch_schedule",
                        lambda d: SCHEDULE if d == DATE else [])


def _h2h(book, last_update, home_price, away_price, home="New York Yankees",
         away="Baltimore Orioles"):
    return {"key": book, "markets": [{"key": "h2h", "last_update": last_update,
            "outcomes": [{"name": home, "price": home_price},
                         {"name": away, "price": away_price}]}]}


def _event(eid, commence, books, home="New York Yankees", away="Baltimore Orioles"):
    return {"id": eid, "commence_time": commence, "home_team": home,
            "away_team": away, "bookmakers": books}


# Game 1 was live 20:05Z-22:54Z; the Odds API lists game 2 at 23:30Z.
G1_LIVE = _event("ev-g1", "2026-09-25T20:05:00Z", [
    _h2h("draftkings", "2026-09-25T21:50:00Z", 3300, -10000),
    _h2h("betmgm", "2026-09-25T22:54:00Z", 3300, -10000)])
G2_PRE = _event("ev-g2", "2026-09-25T23:30:00Z", [
    _h2h("draftkings", "2026-09-25T22:00:00Z", -115, -104)])
CHC_BOS = [
    _event("ev-cb1", "2026-09-25T17:05:00Z",
           [_h2h("draftkings", "2026-09-25T16:00:00Z", -130, 110,
                 home="Boston Red Sox", away="Chicago Cubs")],
           home="Boston Red Sox", away="Chicago Cubs"),
    _event("ev-cb2", "2026-09-25T21:35:00Z",
           [_h2h("draftkings", "2026-09-25T20:00:00Z", -120, 100,
                 home="Boston Red Sox", away="Chicago Cubs")],
           home="Boston Red Sox", away="Chicago Cubs"),
]
SINGLE = _event("ev-s", "2026-09-25T23:05:00Z",
                [_h2h("draftkings", "2026-09-25T18:00:00Z", -140, 120,
                      home="Philadelphia Phillies", away="New York Mets")],
                home="Philadelphia Phillies", away="New York Mets")


# ── the id itself ────────────────────────────────────────────────────────────

def test_game_one_and_single_games_keep_the_old_id():
    assert mgi.mlb_game_id(DATE, "BAL", "NYY") == "MLB_2026-09-25_BAL_NYY"
    assert mgi.mlb_game_id(DATE, "BAL", "NYY", 1) == "MLB_2026-09-25_BAL_NYY"
    assert mgi.mlb_game_id(DATE, "BAL", "NYY", None) == "MLB_2026-09-25_BAL_NYY"
    assert mgi.mlb_game_id(DATE, "BAL", "NYY", 2) == "MLB_2026-09-25_BAL_NYY_G2"


def test_game_number_reads_the_raw_schedule_and_the_statsapi_wrapper():
    assert mgi.game_number({"gameNumber": 2}) == 2       # raw /schedule
    assert mgi.game_number({"game_num": 2}) == 2         # statsapi.schedule()
    assert mgi.game_number({}) == 1
    assert mgi.game_number({"game_num": None}) == 1


def test_a_tbd_game_two_is_not_matched_on_its_placeholder_start(schedule):
    """The Stats API lists BAL@NYY game 2 at 20:10Z -- five minutes after game
    1 -- with startTimeTBD. A book that lists game 1 a few minutes late must
    still get game 1."""
    cands = mgi.schedule_starts(DATE)[("BAL", "NYY")]
    assert [n for n, _ in cands] == [1, 2]
    assert mgi.game_number_for_start(cands, "2026-09-25T20:09:00Z") == 1
    assert mgi.game_number_for_start(cands, "2026-09-25T23:30:00Z") == 2


# ── odds ingestion: distinct ids, rows on the right game ─────────────────────

def test_both_doubleheaders_get_distinct_game_ids(schedule):
    games, odds = oi._process_events([G1_LIVE, G2_PRE, *CHC_BOS, SINGLE],
                                     "MLB", "open", "2026-09-25T22:55:00Z")
    by_id = {g["game_id"]: g for g in games}
    assert set(by_id) == {"MLB_2026-09-25_BAL_NYY", "MLB_2026-09-25_BAL_NYY_G2",
                          "MLB_2026-09-25_CHC_BOS", "MLB_2026-09-25_CHC_BOS_G2",
                          "MLB_2026-09-25_NYM_PHI"}
    # Each row keeps ITS OWN start -- the collapsed row carried game 2's.
    assert by_id["MLB_2026-09-25_BAL_NYY"]["commence_time"].startswith("2026-09-25T20:05")
    assert by_id["MLB_2026-09-25_BAL_NYY_G2"]["commence_time"].startswith("2026-09-25T23:30")


def test_odds_rows_attach_to_their_own_game(schedule):
    _, odds = oi._process_events([G1_LIVE, G2_PRE], "MLB", "open",
                                 "2026-09-25T22:55:00Z")
    g1 = [r for r in odds if r["game_id"] == "MLB_2026-09-25_BAL_NYY"]
    g2 = [r for r in odds if r["game_id"] == "MLB_2026-09-25_BAL_NYY_G2"]
    assert {r["home_price"] for r in g1} == {3300}
    assert {r["home_price"] for r in g2} == {-115}


def test_the_same_event_gets_the_same_id_whether_or_not_game_one_is_listed(schedule):
    """Once game 1 is over the feed lists game 2 alone. Batch position must not
    decide the id, or game 2 would inherit game 1's the moment game 1 ends."""
    _, alone = oi._process_events([G2_PRE], "MLB", "open", "2026-09-25T23:00:00Z")
    assert {r["game_id"] for r in alone} == {"MLB_2026-09-25_BAL_NYY_G2"}


def test_a_single_game_day_produces_the_same_ids_as_before(schedule):
    games, odds = oi._process_events([SINGLE], "MLB", "open", "2026-09-25T18:00:00Z")
    assert [g["game_id"] for g in games] == ["MLB_2026-09-25_NYM_PHI"]
    assert {r["game_id"] for r in odds} == {"MLB_2026-09-25_NYM_PHI"}
    assert oi._build_game_id("MLB", DATE, "NYM", "PHI") == "MLB_2026-09-25_NYM_PHI"


def test_no_schedule_falls_back_to_the_old_id(monkeypatch):
    """A Stats API outage must not invent ids: every game is game 1."""
    mgi.clear_cache()

    def boom(d):
        raise ConnectionError("statsapi down")
    monkeypatch.setattr(mgi, "_fetch_schedule", boom)
    games, _ = oi._process_events([G1_LIVE, G2_PRE], "MLB", "open",
                                  "2026-09-25T22:55:00Z")
    assert {g["game_id"] for g in games} == {"MLB_2026-09-25_BAL_NYY"}


def test_other_sports_are_untouched(schedule):
    assert oi._build_game_id("NHL", DATE, "BOS", "NYR",
                             commence_time="2026-09-25T23:00:00Z") == "NHL_2026-09-25_BOS_NYR"


# ── snapshot_type, per snapshot ──────────────────────────────────────────────

def test_game_one_live_rows_are_in_play_even_when_the_batch_says_open(schedule):
    """The evening refresh stamps every row 'open'; game 1's +3300 at 21:50Z
    and 22:54Z was after its 20:05Z start."""
    _, odds = oi._process_events([G1_LIVE, G2_PRE], "MLB", "open",
                                 "2026-09-25T22:55:00Z")
    types = {(r["game_id"], r["bookmaker"]): r["snapshot_type"] for r in odds}
    assert types[("MLB_2026-09-25_BAL_NYY", "draftkings")] == "in_play"
    assert types[("MLB_2026-09-25_BAL_NYY", "betmgm")] == "in_play"
    assert types[("MLB_2026-09-25_BAL_NYY_G2", "draftkings")] == "open"


def test_game_two_pregame_rows_are_open_even_when_the_batch_says_in_play(schedule):
    """The live fetch stamps every row 'in_play'; game 2's -115/-104 at 22:00Z
    was 90 minutes before its 23:30Z start."""
    _, odds = oi._process_events([G1_LIVE, G2_PRE], "MLB", "in_play",
                                 "2026-09-25T22:55:00Z")
    types = {(r["game_id"], r["bookmaker"]): r["snapshot_type"] for r in odds}
    assert types[("MLB_2026-09-25_BAL_NYY", "draftkings")] == "in_play"
    assert types[("MLB_2026-09-25_BAL_NYY_G2", "draftkings")] == "open"


def test_in_play_inside_the_warmup_window_is_left_alone():
    """Games go live up to ~36 minutes before the listed start
    (data/first_pitch.py); demoting those would create the permissive leak."""
    assert mgi.snapshot_type_for("in_play", "2026-09-25T23:00:00Z",
                                 "2026-09-25T23:30:00Z") == "in_play"
    assert mgi.snapshot_type_for("in_play", "2026-09-25T22:29:00Z",
                                 "2026-09-25T23:30:00Z") == "open"
    assert mgi.snapshot_type_for("open", "bad", "2026-09-25T23:30:00Z") == "open"
    assert mgi.snapshot_type_for("open", "2026-09-25T23:31:00Z",
                                 "2026-09-25T23:30:00Z") == "in_play"


# ── Stats API side: same physical game, same id ──────────────────────────────

def test_stats_api_sites_mint_the_same_ids_as_the_odds_side():
    from data.ingestors.live_game_state_poller import _game_id_from_statsapi
    from data.ingestors.mlb_pbp_ingestor import _game_id_from_schedule
    g1 = {"away_id": BAL, "home_id": NYY, "game_num": 1}
    g2 = {"away_id": BAL, "home_id": NYY, "game_num": 2}
    single = {"away_id": NYM, "home_id": PHI}
    for fn in (_game_id_from_statsapi, _game_id_from_schedule):
        assert fn(g1, DATE) == "MLB_2026-09-25_BAL_NYY"
        assert fn(g2, DATE) == "MLB_2026-09-25_BAL_NYY_G2"
        assert fn(single, DATE) == "MLB_2026-09-25_NYM_PHI"


# ── scores and grading ───────────────────────────────────────────────────────

class _Shim:
    def __init__(self, conn):
        self._c = conn

    def execute(self, sql, params=None):
        sql = sql.replace("NOW()::TEXT", "datetime('now')").replace("%s", "?")
        return self._c.execute(sql, params or [])

    def commit(self):
        self._c.commit()

    def rollback(self):
        self._c.rollback()


class _FakeStatsapi:
    def __init__(self, games):
        self._g = games

    def schedule(self, date=None, sportId=None):
        return self._g


@pytest.fixture
def raw():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    for col in ("player_id TEXT", "is_live BOOLEAN DEFAULT 0"):
        try:
            c.execute(f"ALTER TABLE picks ADD COLUMN {col}")
        except sqlite3.OperationalError:
            pass
    yield c
    c.close()


def _game(raw, gid, commence, home_score=None, away_score=None,
          first_pitch=None, home="NYY", away="BAL"):
    raw.execute("""INSERT INTO games (game_id, sport, season, game_date,
                   home_team, away_team, commence_time, first_pitch_at,
                   home_score, away_score, home_win)
                   VALUES (?, 'MLB', 2026, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (gid, DATE, home, away, commence, first_pitch, home_score,
                 away_score,
                 None if home_score is None else int(home_score > away_score)))


def _pick(raw, gid, game_time, created_at, side="home", odds=3300.0):
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   game_time, pick_side, pick_label, model_probability,
                   dk_implied_prob, edge, dk_odds, kelly_fraction,
                   recommended_bet, bankroll_at_pick, signal_type, created_at)
                   VALUES (?, 'mlb_moneyline', 'MLB', ?, ?, ?, 'NYY ML', 0.6,
                           0.5, 0.1, ?, 0.02, 20.0, 1000.0, 'BET', ?)""",
                (gid, DATE, game_time, side, odds, created_at))
    return raw.execute("SELECT last_insert_rowid()").fetchone()[0]


def _result(raw, pid):
    return raw.execute("SELECT result FROM picks WHERE pick_id = ?",
                       (pid,)).fetchone()[0]


def test_each_game_gets_its_own_final(raw, monkeypatch, schedule):
    """Date + teams wrote game 1's final onto every BAL@NYY row, and game 2's
    was then dropped by `home_score IS NULL`."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00")
    _game(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00")
    monkeypatch.setattr(pt, "STATSAPI_AVAILABLE", True)
    monkeypatch.setattr(pt, "statsapi", _FakeStatsapi([
        {"status": "Final", "home_id": NYY, "away_id": BAL, "game_num": 1,
         "home_score": 2, "away_score": 10},
        {"status": "Final", "home_id": NYY, "away_id": BAL, "game_num": 2,
         "home_score": 5, "away_score": 1},
    ]), raising=False)
    monkeypatch.setattr(pt, "_fetch_and_store_f5_scores", lambda c, d: 0)
    pt._fetch_and_store_scores(_Shim(raw), DATE)
    rows = dict(((g, (h, a)) for g, h, a in raw.execute(
        "SELECT game_id, home_score, away_score FROM games")))
    assert rows["MLB_2026-09-25_BAL_NYY"] == (2, 10)
    assert rows["MLB_2026-09-25_BAL_NYY_G2"] == (5, 1)


def test_grading_uses_each_games_own_score(raw, schedule):
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    _game(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00", 5, 1)
    p1 = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
               "2026-09-25 14:00:00")
    p2 = _pick(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00",
               "2026-09-25 21:00:00", odds=-115.0)
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T02:00:00-04:00")
    assert _result(raw, p1) == "LOSS"      # NYY lost game 1, 2-10
    assert _result(raw, p2) == "WIN"       # NYY won game 2, 5-1


# ── the interim settlement guard (independent of the id) ─────────────────────

def test_a_game_two_pick_on_a_collapsed_row_is_not_settled_before_game_two(raw, schedule):
    """Tonight's shape: ONE row, game 1's final, game 2's commence_time. The
    game-2 pick must not settle at 7:12 PM ET (23:12Z) -- game 2 starts 23:30Z."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 22:58:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-25T19:12:00-04:00")
    assert _result(raw, pid) is None


def test_a_pick_created_after_the_scored_game_ended_is_held(raw, schedule):
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    raw.execute("""INSERT INTO live_game_state (game_id, snapshot_at, abstract_game_state)
                   VALUES ('MLB_2026-09-25_BAL_NYY', '2026-09-25T22:54:00+00:00', 'Final')""")
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 23:05:00")
    # After game 2's start, so check 1 passes; check 4 must catch it.
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T01:00:00-04:00")
    assert _result(raw, pid) is None


def test_a_game_one_pick_whose_row_start_was_overwritten_is_held(raw, schedule):
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T01:00:00-04:00")
    assert _result(raw, pid) is None


def test_a_row_whose_live_state_began_hours_before_the_pick_is_held(raw, schedule):
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10,
          first_pitch="2026-09-25T20:04:00+00:00")
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T01:00:00-04:00")
    assert _result(raw, pid) is None


def test_a_delayed_single_game_still_settles(raw, schedule):
    """Checks 2-4 only run on a doubleheader day. NYM@PHI is a single game
    whose commence_time moved two hours (a delay): it must grade as before."""
    _game(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-26T01:05:00+00:00", 3, 1,
          home="PHI", away="NYM")
    pid = _pick(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-25T23:05:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T03:00:00-04:00")
    assert _result(raw, pid) == "WIN"


def test_rows_without_timestamps_settle_exactly_as_before():
    assert pt._settle_hold_reason(None, None, None, None, None,
                                  "2026-09-26T01:00:00-04:00") is None


def test_the_not_started_check_applies_on_any_day():
    reason = pt._settle_hold_reason(None, "2026-09-25T23:30:00+00:00", None,
                                    None, None, "2026-09-25T19:12:00-04:00",
                                    doubleheader=False)
    assert reason and "after this pass" in reason


def test_a_held_prop_pick_stays_unsettled(raw, schedule):
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    raw.execute("""INSERT INTO picks (game_id, model_id, sport, game_date,
                   game_time, pick_side, pick_label, model_probability,
                   dk_implied_prob, edge, dk_odds, scored_line, kelly_fraction,
                   recommended_bet, bankroll_at_pick, signal_type, created_at,
                   player_id)
                   VALUES ('MLB_2026-09-25_BAL_NYY', 'mlb_prop_batter_hits',
                           'MLB', ?, '2026-09-25T23:30:00+00:00', 'over',
                           'Aaron Judge Over 0.5 Hits', 0.6, 0.5, 0.1, -150,
                           0.5, 0.02, 20.0, 1000.0, 'BET',
                           '2026-09-25 22:00:00', '592450')""", (DATE,))
    pid = raw.execute("SELECT last_insert_rowid()").fetchone()[0]
    raw.execute("""INSERT INTO player_game_log (player_id, player_name, team,
                   player_type, game_id, game_date, season, hits)
                   VALUES ('592450', 'Aaron Judge', 'NYY', 'batter',
                           'MLB_2026-09-25_BAL_NYY', ?, 2026, 0)""", (DATE,))
    pt._settle_prop_picks(_Shim(raw), DATE, "2026-09-25T19:12:00-04:00")
    assert _result(raw, pid) is None
