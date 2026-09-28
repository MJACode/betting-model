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


def test_no_schedule_drops_a_two_event_matchup_rather_than_collapse(monkeypatch):
    """A Stats API outage must not invent ids -- and (review H2) must not
    collapse two events onto the base row either: with no schedule ever read
    and no base/_G2 rows to match, a matchup with two events is DROPPED at
    ERROR this pass. A lone event keeps the old base id."""
    mgi.clear_cache()

    def boom(d):
        raise ConnectionError("statsapi down")
    monkeypatch.setattr(mgi, "_fetch_schedule", boom)
    games, odds = oi._process_events([G1_LIVE, G2_PRE, SINGLE], "MLB", "open",
                                     "2026-09-25T22:55:00Z")
    assert {g["game_id"] for g in games} == {"MLB_2026-09-25_NYM_PHI"}
    assert {r["game_id"] for r in odds} == {"MLB_2026-09-25_NYM_PHI"}


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


def _final(raw, gid, snapshot_at, home_score=2, away_score=10):
    """A 'Final' live_game_state snapshot. home_score=None is what the feed
    writes for a POSTPONED game (MLB_2026-07-27_CLE_CIN, 23:50Z)."""
    raw.execute("""INSERT INTO live_game_state (game_id, snapshot_at,
                   abstract_game_state, home_score, away_score)
                   VALUES (?, ?, 'Final', ?, ?)""",
                (gid, snapshot_at, home_score, away_score))


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
    _final(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T22:54:00+00:00")
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 23:05:00")
    # After game 2's start, so check 1 passes; checks 4 and 5 both catch it
    # (check 4 alone: test_check_four_alone_holds_a_pick_created_after_the_final).
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T01:00:00-04:00")
    assert _result(raw, pid) is None


def test_a_game_one_pick_whose_row_start_was_overwritten_settles_on_game_one(raw, schedule):
    """Review H3: check 2 no longer compares the pick's game_time with the
    row's commence_time (rewritten on every upsert). A game-1 pick on the base
    row -- which IS game 1, holding game 1's final -- grades on it even though
    the row's commence_time now says game 2's start."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T01:00:00-04:00")
    assert _result(raw, pid) == "LOSS"


def test_a_game_two_pick_on_a_collapsed_row_is_held_by_check_two(raw, schedule):
    """A collapsed row (no _G2 row yet) is game 1; a pick whose start is
    unambiguously game 2's is held, whatever the row's commence_time says."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T03:00:00-04:00")
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


# ── check 5, and the 2899429 case (the guard as first pushed did NOT hold it) ─

def test_2899429_is_held(raw, schedule):
    """Pick 2899429's own timestamps (a walks prop; the guard is the same for
    game-level picks): created 21:27:50Z for the 23:05Z start the row carried
    then, settled LOSS at 23:12:19Z on the row that by then said 23:30Z and
    held game 1's final (live 'Final' at 22:54:55Z). Check 1 passes (23:05 is
    before 23:12), check 2 passes (25 minutes), first_pitch_at was NULL, and
    it was created before game 1 ended. Only check 5 sees it."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00", 2, 10)
    _final(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T22:54:55.011468+00:00")
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:05:00+00:00",
                "2026-09-25 21:27:50")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-25T23:12:19+00:00")
    assert _result(raw, pid) is None


def test_2899429_reason_is_check_five_even_on_a_non_doubleheader_day():
    reason = pt._settle_hold_reason(
        "2026-09-25T21:27:50+00:00", "2026-09-25T23:05:00+00:00",
        "2026-09-25T23:30:00+00:00", None, "2026-09-25T22:54:55+00:00",
        "2026-09-25T23:12:19+00:00", doubleheader=False)
    assert reason and "too soon after" in reason


def test_a_postponement_final_does_not_count_as_a_final(raw, schedule):
    """The feed marks a postponed game 'Final' with no score. That snapshot
    (hours before the replay) must not make check 5 or 4 hold the replay."""
    _game(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-25T23:05:00+00:00", 3, 1,
          home="PHI", away="NYM")
    _final(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-25T16:00:00+00:00",
           home_score=None, away_score=None)
    _final(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-26T02:10:00+00:00", 3, 1)
    pid = _pick(raw, "MLB_2026-09-25_NYM_PHI", "2026-09-25T23:05:00+00:00",
                "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T03:00:00-04:00")
    assert _result(raw, pid) == "WIN"


def test_check_four_alone_holds_a_pick_created_after_the_final():
    reason = pt._settle_hold_reason(
        "2026-09-25T23:05:00+00:00", "2026-09-25T20:05:00+00:00",
        "2026-09-25T20:05:00+00:00", None, "2026-09-25T22:54:00+00:00",
        "2026-09-26T01:00:00+00:00", doubleheader=True)
    assert reason and "after the scored game ended" in reason


def test_a_one_hour_start_restamp_is_not_a_doubleheader_collapse():
    """MLB_2026-08-13_CIN_CWS: morning picks carry the book's 18:11Z start,
    the game went live at 17:00:01Z (71 minutes earlier). Even on a
    doubleheader day that is not a game-2 pick on game 1's row."""
    assert pt._settle_hold_reason(
        "2026-08-13T14:18:54+00:00", "2026-08-13T18:11:00+00:00",
        "2026-08-13T18:11:00+00:00", "2026-08-13T17:00:01+00:00",
        "2026-08-13T20:18:14+00:00", "2026-08-13T21:00:00+00:00",
        doubleheader=True) is None


# ── review H1: an event is assigned once, by start order, or refused ─────────

def _ev(eid, commence, home="New York Yankees", away="Baltimore Orioles", price=-110):
    return _event(eid, commence, [_h2h("draftkings", "2026-09-25T15:00:00Z",
                                       price, 100, home=home, away=away)],
                  home=home, away=away)


def _ids(events, snap="2026-09-25T15:00:00Z"):
    games, _ = oi._process_events(events, "MLB", "open", snap)
    return {g["commence_time"][11:16]: g["game_id"] for g in games}


def test_a_game_one_delayed_91_minutes_keeps_its_id(schedule):
    """Seen at 20:05Z first; the book then delays it to 21:36Z, 89 minutes
    from game 2's effective start (23:05Z) and 91 from its own. Nearest-start
    would now call it game 2. The recorded assignment keeps it on game 1."""
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")]) == {
        "20:05": "MLB_2026-09-25_BAL_NYY", "23:30": "MLB_2026-09-25_BAL_NYY_G2"}
    assert _ids([_ev("g1", "2026-09-25T21:36:00Z"), _ev("g2", "2026-09-25T23:30:00Z")]) == {
        "21:36": "MLB_2026-09-25_BAL_NYY", "23:30": "MLB_2026-09-25_BAL_NYY_G2"}
    # ...and alone, once game 2 has left the board.
    assert _ids([_ev("g1", "2026-09-25T21:36:00Z")]) == {"21:36": "MLB_2026-09-25_BAL_NYY"}


def test_a_game_one_delayed_91_minutes_first_seen_with_game_two_goes_by_start_order(schedule):
    assert _ids([_ev("g2", "2026-09-25T23:05:00Z"), _ev("g1", "2026-09-25T21:36:00Z")]) == {
        "21:36": "MLB_2026-09-25_BAL_NYY", "23:05": "MLB_2026-09-25_BAL_NYY_G2"}


def test_a_lone_game_one_delayed_91_minutes_never_seen_is_refused(schedule):
    """Not within an hour of either game: ambiguous, so DROPPED, not guessed."""
    assert _ids([_ev("g1", "2026-09-25T21:36:00Z")]) == {}


def test_game_two_listed_at_the_placeholder_is_game_two(schedule):
    """The book lists game 2 at MLB's 20:10Z placeholder, five minutes after
    game 1. Beside game 1: start order. Alone after game 1 was assigned: the
    one game left. Alone with nothing assigned: 0 min from game 2's
    placeholder and 5 from game 1, so the closer one, game 2."""
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T20:10:00Z")]) == {
        "20:05": "MLB_2026-09-25_BAL_NYY", "20:10": "MLB_2026-09-25_BAL_NYY_G2"}
    mgi.clear_cache()
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")])
    assert _ids([_ev("g2", "2026-09-25T20:10:00Z")]) == {"20:10": "MLB_2026-09-25_BAL_NYY_G2"}
    mgi.clear_cache()
    assert _ids([_ev("gx", "2026-09-25T20:10:00Z")]) == {"20:10": "MLB_2026-09-25_BAL_NYY_G2"}


# ── N1: a lone event near two games goes to the closer one ───────────────────
# BAL@NYY: game 1 at 20:05Z, game 2 TBD with its placeholder at 20:10Z. Books
# often list only game 1 on the morning of a traditional doubleheader.

G1_ID, G2_ID = "MLB_2026-09-25_BAL_NYY", "MLB_2026-09-25_BAL_NYY_G2"


def test_lone_game_one_at_listed_start_is_game_one(schedule):
    """Game 1's event alone at its listed 20:05Z start is 0 min from game 1
    and 5 from game 2's placeholder: game 1, not DROPPED. (It was dropped at
    efa2ab7b, leaving game 1's open, props and public betting empty until
    game 2 was listed.) A book a minute late is still game 1."""
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z")]) == {"20:05": G1_ID}
    assert mgi._event_map.by_event[("odds_api", "g1")] == G1_ID
    mgi.clear_cache()
    assert _ids([_ev("g1b", "2026-09-25T20:06:00Z")]) == {"20:06": G1_ID}
    # The same answer from the lookup itself, and from the one-event helper.
    mgi.clear_cache()
    cands = mgi.schedule_state(DATE)[("BAL", "NYY")]
    assert mgi.unambiguous_game_number(DATE, "BAL", "NYY", cands,
                                       "2026-09-25T20:05:00Z") == 1
    assert mgi.mlb_event_game_id(DATE, "BAL", "NYY", "2026-09-25T20:05:00Z",
                                 event_id="solo") == G1_ID


def test_lone_game_one_then_game_two_arrives_maps_to_g2(schedule):
    """Game 1 assigned alone by closeness, then game 2's event arrives: it
    goes to _G2 and game 1 keeps its id -- wherever game 2 is listed (its real
    23:30Z start, or MLB's 20:10Z placeholder that is nearer game 1's start),
    and even after game 1 is delayed onto the placeholder."""
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z")]) == {"20:05": G1_ID}
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"),
                 _ev("g2", "2026-09-25T23:30:00Z")]) == {"20:05": G1_ID, "23:30": G2_ID}
    assert _ids([_ev("g1", "2026-09-25T20:10:00Z"),
                 _ev("g2", "2026-09-25T23:30:00Z")]) == {"20:10": G1_ID, "23:30": G2_ID}
    assert _ids([_ev("g2", "2026-09-25T23:30:00Z")]) == {"23:30": G2_ID}

    # Game 2 first listed at the placeholder, alone, after game 1 was claimed.
    mgi.clear_cache()
    assert _ids([_ev("h1", "2026-09-25T20:05:00Z")]) == {"20:05": G1_ID}
    assert _ids([_ev("h2", "2026-09-25T20:10:00Z")]) == {"20:10": G2_ID}
    assert _ids([_ev("h1", "2026-09-25T20:05:00Z"),
                 _ev("h2", "2026-09-25T20:10:00Z")]) == {"20:05": G1_ID, "20:10": G2_ID}
    assert mgi._event_map.by_game == {("odds_api", G1_ID): "h1",
                                      ("odds_api", G2_ID): "h2"}


def test_lone_event_at_a_true_tie_is_refused(schedule):
    """20:07Z and 20:08Z are 2 and 3 minutes from game 1 and game 2's
    placeholder: within TIE_TOLERANCE, so which game is noise -- DROPPED,
    and nothing recorded. Two synthetic games at exactly equal distance too."""
    assert mgi.TIE_TOLERANCE == mgi.timedelta(minutes=2)
    assert _ids([_ev("t1", "2026-09-25T20:07:00Z")]) == {}
    assert _ids([_ev("t2", "2026-09-25T20:08:00Z")]) == {}
    assert not mgi._event_map.by_event
    assert _ids([_ev("t3", "2026-09-25T20:09:00Z")]) == {"20:09": G2_ID}

    ts = mgi._ts
    cands = [(1, ts("2026-07-04T17:05:00Z")), (2, ts("2026-07-04T17:55:00Z"))]
    tie = "2026-07-04T17:30:00Z"
    assert mgi.unambiguous_game_number("2026-07-04", "A", "B", cands, tie) is None
    assert mgi.unambiguous_game_number("2026-07-04", "A", "B", cands,
                                       "2026-07-04T17:20:00Z") == 1
    # Settlement's check 2 keeps the strict rule: near both is unknown.
    assert mgi.unambiguous_game_number("2026-07-04", "A", "B", cands,
                                       "2026-07-04T17:20:00Z", closest=False) is None


def test_a_split_doubleheader_game_one_delayed_over_2h15_keeps_its_id(schedule):
    cb = dict(home="Boston Red Sox", away="Chicago Cubs")
    assert _ids([_ev("c1", "2026-09-25T17:05:00Z", **cb), _ev("c2", "2026-09-25T21:35:00Z", **cb)]) == {
        "17:05": "MLB_2026-09-25_CHC_BOS", "21:35": "MLB_2026-09-25_CHC_BOS_G2"}
    assert _ids([_ev("c1", "2026-09-25T19:25:00Z", **cb)]) == {"19:25": "MLB_2026-09-25_CHC_BOS"}


def test_a_second_event_on_a_claimed_game_is_dropped(schedule):
    """Two event ids never share a game_id: the later one is refused."""
    _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")])
    assert _ids([_ev("g3", "2026-09-25T20:05:00Z")]) == {}


def test_two_events_at_the_same_start_are_refused(schedule):
    assert _ids([_ev("a", "2026-09-25T20:05:00Z"), _ev("b", "2026-09-25T20:05:00Z")]) == {}


def test_single_games_never_touch_the_event_map(schedule):
    """A re-issued event id on a single game must not be refused."""
    ph = dict(home="Philadelphia Phillies", away="New York Mets")
    assert _ids([_ev("s1", "2026-09-25T23:05:00Z", **ph)]) == {"23:05": "MLB_2026-09-25_NYM_PHI"}
    assert _ids([_ev("s2", "2026-09-25T23:05:00Z", **ph)]) == {"23:05": "MLB_2026-09-25_NYM_PHI"}
    assert not mgi._event_map.by_event


class _MapConn:
    """A tiny mlb_event_game_map in memory, speaking the SQL _EventMap sends."""
    rows: list = []

    def execute(self, sql, params=()):
        me = self
        if sql.startswith("INSERT INTO mlb_event_game_map"):
            src, eid, gid = params[:3]
            if not any(r[0] == src and (r[1] == eid or r[2] == gid) for r in me.rows):
                me.rows.append(params)
            res = []
        elif "WHERE source = %s AND game_date" in sql:
            res = [(r[1], r[2]) for r in me.rows if r[0] == params[0] and r[3:6] == params[1:4]]
        elif "WHERE source = %s AND game_id" in sql:
            res = [(r[1],) for r in me.rows if r[0] == params[0] and r[2] == params[1]]
        elif "WHERE source = %s AND event_id" in sql:
            res = [(r[2],) for r in me.rows if r[0] == params[0] and r[1] == params[1]]
        else:
            res = []

        class R:
            def fetchall(_):
                return res

            def fetchone(_):
                return res[0] if res else None
        return R()

    def commit(self):
        pass

    def close(self):
        pass


def test_the_assignment_survives_a_restart_through_the_table(schedule, monkeypatch):
    import data.db
    _MapConn.rows = []
    monkeypatch.setattr(mgi, "_EVENT_MAP_DB", True)
    monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: _MapConn())
    _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")])
    assert {(r[1], r[2]) for r in _MapConn.rows} == {
        ("g1", "MLB_2026-09-25_BAL_NYY"), ("g2", "MLB_2026-09-25_BAL_NYY_G2")}
    mgi._event_map.clear()                       # a new process
    assert _ids([_ev("g1", "2026-09-25T21:36:00Z")]) == {"21:36": "MLB_2026-09-25_BAL_NYY"}


def test_a_missing_map_table_degrades_to_memory(schedule, monkeypatch):
    import data.db

    class Missing(_MapConn):
        def execute(self, sql, params=()):
            raise RuntimeError('relation "mlb_event_game_map" does not exist')
    monkeypatch.setattr(mgi, "_EVENT_MAP_DB", True)
    monkeypatch.setattr(data.db, "get_connection", lambda *a, **k: Missing())
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")]) == {
        "20:05": "MLB_2026-09-25_BAL_NYY", "23:30": "MLB_2026-09-25_BAL_NYY_G2"}
    assert mgi._event_map.by_event[("odds_api", "g1")] == "MLB_2026-09-25_BAL_NYY"


# ── review H2: a failed schedule read keeps the last good one ────────────────

def test_a_failed_refetch_keeps_the_last_good_schedule(monkeypatch):
    mgi.clear_cache()
    clock = [1000.0]
    monkeypatch.setattr(mgi.time, "monotonic", lambda: clock[0])
    calls = []

    def fetch(d):
        calls.append(clock[0])
        if len(calls) > 1:
            raise ConnectionError("down")
        return SCHEDULE
    monkeypatch.setattr(mgi, "_fetch_schedule", fetch)
    assert len(mgi.schedule_state(DATE)[("BAL", "NYY")]) == 2
    clock[0] += mgi._SCHEDULE_TTL_S + 1                 # stale: refetch fails
    assert len(mgi.schedule_state(DATE)[("BAL", "NYY")]) == 2
    clock[0] += 30                                      # inside the retry gap
    assert len(mgi.schedule_state(DATE)[("BAL", "NYY")]) == 2
    assert len(calls) == 2
    clock[0] += mgi._SCHEDULE_RETRY_S                   # retried after ~60s
    mgi.schedule_state(DATE)
    assert len(calls) == 3


def test_a_cold_failure_is_unknown_not_empty_and_recovers(monkeypatch):
    mgi.clear_cache()
    clock = [1000.0]
    monkeypatch.setattr(mgi.time, "monotonic", lambda: clock[0])
    state = {"up": False}

    def fetch(d):
        if not state["up"]:
            raise ConnectionError("down")
        return SCHEDULE
    monkeypatch.setattr(mgi, "_fetch_schedule", fetch)
    assert mgi.schedule_state(DATE) is None
    assert mgi.schedule_starts(DATE) == {}
    state["up"] = True
    clock[0] += 10
    assert mgi.schedule_state(DATE) is None             # not before the retry gap
    clock[0] += mgi._SCHEDULE_RETRY_S
    assert mgi.schedule_state(DATE)[("BAL", "NYY")]


def test_a_cold_failure_matches_existing_base_and_g2_rows(monkeypatch):
    mgi.clear_cache()
    monkeypatch.setattr(mgi, "_fetch_schedule",
                        lambda d: (_ for _ in ()).throw(ConnectionError("down")))
    from datetime import datetime, timezone
    monkeypatch.setattr(mgi._event_map, "existing_rows", lambda d, a, h: {
        1: datetime(2026, 9, 25, 20, 5, tzinfo=timezone.utc),
        2: datetime(2026, 9, 25, 23, 30, tzinfo=timezone.utc)})
    assert _ids([_ev("g1", "2026-09-25T20:05:00Z"), _ev("g2", "2026-09-25T23:30:00Z")]) == {
        "20:05": "MLB_2026-09-25_BAL_NYY", "23:30": "MLB_2026-09-25_BAL_NYY_G2"}


def test_settlement_fails_closed_without_a_schedule_when_a_g2_row_exists(raw, monkeypatch):
    mgi.clear_cache()
    monkeypatch.setattr(mgi, "_fetch_schedule",
                        lambda d: (_ for _ in ()).throw(ConnectionError("down")))
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    _game(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00", 5, 1)
    p1 = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00",
               "2026-09-25 14:00:00")
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T03:00:00-04:00")
    assert _result(raw, p1) is None


# ── review H3: a delayed game 2 settles; a long hold is raised once ──────────

def test_a_game_two_delayed_75_minutes_settles(raw, schedule):
    """picks.game_time is written once (23:30Z); the games row's
    commence_time follows the book to 00:45Z. The pick is on the _G2 row,
    which is its game: it must grade, not hold forever."""
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    _game(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-26T00:45:00+00:00", 5, 1)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY_G2", "2026-09-25T23:30:00+00:00",
                "2026-09-25 21:00:00", odds=-115.0)
    pt._settle_game_picks(_Shim(raw), DATE, "2026-09-26T02:00:00-04:00")
    assert _result(raw, pid) == "WIN"


def test_a_hold_older_than_two_days_is_raised_once(raw, schedule, monkeypatch):
    import tracking.watch_util as wu
    sent, state = [], {}
    monkeypatch.setattr(wu, "post_ops_alert", lambda t, d, **k: sent.append((t, d)) or True)
    monkeypatch.setattr(wu, "read_alert_state", lambda f: dict(state))
    monkeypatch.setattr(wu, "write_alert_state", lambda f, s: state.update(s))
    _game(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T20:05:00+00:00", 2, 10)
    pid = _pick(raw, "MLB_2026-09-25_BAL_NYY", "2026-09-25T23:30:00+00:00",
                "2026-09-25 14:00:00")
    for _ in range(3):
        pt._settle_game_picks(_Shim(raw), DATE, "2026-09-28T12:00:00-04:00")
    assert _result(raw, pid) is None
    assert len(sent) == 1 and f"pick {pid}" in sent[0][1]
    assert str(pid) in state


# ── suspended / resumed games ────────────────────────────────────────────────

def test_a_resumed_game_is_not_the_resume_dates_doubleheader(monkeypatch):
    """SF@ATL gamePk 824912 was suspended 2026-06-16 and resumed 06-17 18:00Z;
    the 06-17 schedule lists it (officialDate 06-16, gameNumber 1) beside that
    day's own 824913 (gameNumber 1, 23:15Z). It is 06-16's game, so 06-17 has
    one SF@ATL game: base id, no doubleheader, no hold logic."""
    SF, ATL = 137, 144
    day = [
        {**_sched(824912, SF, ATL, 1, "2026-06-17T18:00:00Z", dh="N"),
         "officialDate": "2026-06-16", "resumedFrom": "2026-06-16T23:15:00Z"},
        {**_sched(824913, SF, ATL, 1, "2026-06-17T23:15:00Z", dh="N"),
         "officialDate": "2026-06-17"},
    ]
    mgi.clear_cache()
    monkeypatch.setattr(mgi, "_fetch_schedule", lambda d: day if d == "2026-06-17" else [])
    cands = mgi.schedule_state("2026-06-17")[("SF", "ATL")]
    assert [n for n, _ in cands] == [1]
    ev = _event("sfatl", "2026-06-17T23:15:00Z",
                [_h2h("draftkings", "2026-06-17T15:00:00Z", -120, 100,
                      home="Atlanta Braves", away="San Francisco Giants")],
                home="Atlanta Braves", away="San Francisco Giants")
    games, _ = oi._process_events([ev], "MLB", "open", "2026-06-17T15:00:00Z")
    assert [g["game_id"] for g in games] == ["MLB_2026-06-17_SF_ATL"]


def test_pbp_spot_check_resolves_g2_and_skips_a_resumed_game():
    from data.ingestors.mlb_pbp_ingestor import resolve_game_pk
    sched = [
        {"game_id": 823491, "away_id": BAL, "home_id": NYY, "game_num": 1, "game_date": DATE},
        {"game_id": 823489, "away_id": BAL, "home_id": NYY, "game_num": 2, "game_date": DATE},
        {"game_id": 777, "away_id": CHC, "home_id": BOS, "game_num": 1, "game_date": "2026-09-24"},
        {"game_id": 824703, "away_id": CHC, "home_id": BOS, "game_num": 1, "game_date": DATE},
    ]
    sch = lambda date=None, sportId=None: sched                         # noqa: E731
    assert resolve_game_pk("MLB_2026-09-25_BAL_NYY", sch) == 823491
    assert resolve_game_pk("MLB_2026-09-25_BAL_NYY_G2", sch) == 823489
    assert resolve_game_pk("MLB_2026-09-25_CHC_BOS", sch) == 824703
    with pytest.raises(ValueError):
        resolve_game_pk("NHL_2026-09-25_BOS_NYR", sch)
    assert mgi.parse_mlb_game_id("MLB_2026-09-25_BAL_NYY_G2") == ("2026-09-25", "BAL", "NYY", 2)
    assert mgi.parse_mlb_game_id("MLB_2026-09-25_BAL_NYY") == ("2026-09-25", "BAL", "NYY", 1)


# ── the unapplied migrations (text checks; neither has been run anywhere) ────

MIG = Path(__file__).parent.parent / "data" / "migrations"


def test_matview_migration_limits_checks_to_doubleheader_rows_and_regrants_cleanly():
    sql = (MIG / "scored_outcomes_doubleheader_guard_2026_09_25.sql").read_text()
    body = sql.split("$v$")[1]
    # M1: both ungrading WHENs are gated on dh_rows.
    assert body.count("WHEN dh.game_id IS NOT NULL") == 2
    assert "'MLB_2026-09-25_BAL_NYY'" in body and "'MLB_2026-08-13_CIN_CWS'" not in body
    assert "interval '120 minutes'" in body
    # M2: revoke before re-grant, grant option and comments preserved.
    tail = sql.split("$v$")[2]
    assert tail.index("REVOKE ALL ON public.%I FROM PUBLIC, anon, authenticated") \
        < tail.index("GRANT %s ON public.%I TO %s%s")
    assert "WITH GRANT OPTION" in tail and "COMMENT ON COLUMN" in tail
    # Low: the idempotency marker is a COMMENT (pg_get_viewdef strips comments).
    assert "obj_description('public.mv_scored_pick_outcomes'::regclass" in sql
    assert "COMMENT ON MATERIALIZED VIEW public.mv_scored_pick_outcomes" in sql
    assert "position('dh_guard_2026_09_25' in d)" not in sql
    # Low: the partial index for the finals CTE.
    assert "WHERE abstract_game_state = 'Final'" in sql.split("DO $mig$")[0]
    assert "CASCADE" not in sql.split("-- WHAT IT DOES")[1].split("DO $mig$")[1]


def test_event_map_migration_is_unapplied_and_locked_down():
    sql = (MIG / "mlb_event_game_map_2026_09_28.sql").read_text()
    assert "NOT APPLIED" in sql.splitlines()[0]
    assert "PRIMARY KEY (source, event_id)" in sql and "UNIQUE (source, game_id)" in sql
    assert "ENABLE ROW LEVEL SECURITY" in sql
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert not any("mlb_event_game_map" in m or "doubleheader_guard" in m
                   for m in ACTIVE_MIGRATIONS)
