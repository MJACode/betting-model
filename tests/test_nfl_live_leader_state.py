"""The ESPN core -> model-input adapter (nfl_live_leader/state.py).

The play documents below are REAL core documents from TB @ DAL, 2026 week 5
(core event 401872980), trimmed to the fields the adapter reads: DAL (team 6)
is home, TB (team 27) away, and TB leads 24-16 after DAL's touchdown at 5:26
of the 4th quarter. The live `situation` shape -- the possessing team as
`team`, no `possession` key -- is the one measured on a live core football
payload (college-football event 401871067, 2026-10-13).

What is pinned:
  * secs comes from the LAST REAL PLAY's SNAP clock, never the running clock,
    and an administrative row (a timeout) is skipped when choosing that play;
  * the score is that play's post-play score;
  * possession is parsed WHOLE from '/teams/(\\d+)' -- the old core parser's
    substring test read team 12 as team 1;
  * every transitional state is skipped: after a scoring play, no scrimmage
    down, possession unknown, possession disagreeing with the play's end team;
  * the plays list is not in sequence order, so "last" is by sequenceNumber.
"""

from __future__ import annotations

import copy

import pytest

from nfl_live_leader import state as S

T = "http://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/2026/teams/{}?lang=en&region=us"
DAL, TB = "6", "27"

TD = {"id": "4018729803742", "sequenceNumber": "374200",
      "type": {"id": "67", "text": "Passing Touchdown", "abbreviation": "TD"},
      "period": {"number": 4}, "clock": {"value": 326.0, "displayValue": "5:26"},
      "homeScore": 16, "awayScore": 24, "scoringPlay": True, "scoreValue": 6,
      "start": {"down": 2, "team": {"$ref": T.format(DAL)}},
      "end": {"down": -1, "team": {"$ref": T.format(DAL)}}}
KICKOFF = {"id": "4018729803781", "sequenceNumber": "378100",
           "type": {"id": "53", "text": "Kickoff", "abbreviation": "K"},
           "period": {"number": 4}, "clock": {"value": 326.0, "displayValue": "5:26"},
           "homeScore": 16, "awayScore": 24, "scoringPlay": False, "scoreValue": 0,
           "start": {"down": 0, "team": {"$ref": T.format(DAL)}},
           "end": {"down": 1, "team": {"$ref": T.format(TB)}}}
RUSH_442 = {"id": "4018729803857", "sequenceNumber": "385700",
            "type": {"id": "5", "text": "Rush", "abbreviation": "RUSH"},
            "period": {"number": 4}, "clock": {"value": 282.0, "displayValue": "4:42"},
            "homeScore": 16, "awayScore": 24, "scoringPlay": False, "scoreValue": 0,
            "start": {"down": 2, "team": {"$ref": T.format(TB)}},
            "end": {"down": 3, "team": {"$ref": T.format(TB)}}}
RUSH_116 = {"id": "4018729804150", "sequenceNumber": "415000",
            "type": {"id": "5", "text": "Rush", "abbreviation": "RUSH"},
            "period": {"number": 4}, "clock": {"value": 76.0, "displayValue": "1:16"},
            "homeScore": 16, "awayScore": 24, "scoringPlay": False, "scoreValue": 0,
            "start": {"down": 1, "team": {"$ref": T.format(TB)}},
            "end": {"down": 2, "team": {"$ref": T.format(TB)}}}
TIMEOUT_111 = {"id": "4018729804161", "sequenceNumber": "416100",
               "type": {"id": "21", "text": "Timeout", "abbreviation": "TO"},
               "period": {"number": 4}, "clock": {"value": 71.0, "displayValue": "1:11"},
               "homeScore": 16, "awayScore": 24, "scoringPlay": False, "scoreValue": 0,
               "start": {"down": 2, "team": {"$ref": T.format(TB)}},
               "end": {"down": 2, "team": {"$ref": T.format(TB)}}}

META = S.EventMeta(event_id="401872980", date="2026-10-09T00:15Z", home_id=DAL, away_id=TB,
                   home_abbr="DAL", away_abbr="TB", status_ref=None, situation_ref=None,
                   plays_ref=None)


def status(period=4, clock=250.0, state="in", completed=False, name="STATUS_IN_PROGRESS"):
    return {"clock": clock, "period": period,
            "type": {"id": "2", "name": name, "state": state, "completed": completed}}


def situation(down=3, team=TB, last=None):
    s = {"down": down, "distance": 4, "yardLine": 63, "possessionText": "TB 37"}
    if team is not None:
        s["team"] = {"$ref": T.format(team)}
    if last is not None:
        s["lastPlay"] = {"$ref": f"https://x/plays/{last['id']}"}
    return s


def test_an_ordinary_snap_is_evaluable_with_the_training_inputs():
    st = S.state_from_docs(META, status(clock=250.0), situation(3, TB), [RUSH_442])
    assert st.evaluable, st.reason
    assert st.secs == 282.0                      # the SNAP of the 4:42 rush, not 250 running
    assert (st.home_score, st.away_score) == (16, 24)
    assert st.possession == "away" and st.lead == 8 and st.period == 4
    assert S.in_window(st)


def test_the_running_clock_is_never_the_model_clock():
    for running in (0.0, 100.0, 281.0, 599.0):
        st = S.state_from_docs(META, status(clock=running), situation(3, TB), [RUSH_442])
        assert st.secs == 282.0


def test_a_timeout_is_skipped_for_the_play_before_it():
    """situation.lastPlay is the timeout at 1:11; the model's clock is the 1:16
    snap of the rush before it (nflverse has no timeout state)."""
    st = S.state_from_docs(META, status(clock=71.0), situation(2, TB, TIMEOUT_111),
                           [TIMEOUT_111, RUSH_116, RUSH_442])
    assert st.evaluable, st.reason
    assert st.secs == 76.0
    assert st.last_play_type == "rush"


def test_last_play_is_chosen_by_sequence_not_list_order():
    st = S.state_from_docs(META, status(), situation(2, TB), [RUSH_116, RUSH_442, TIMEOUT_111])
    assert st.secs == 76.0


def test_after_a_scoring_play_nothing_is_evaluated():
    st = S.state_from_docs(META, status(clock=326.0), situation(0, DAL), [TD])
    assert not st.evaluable and "scoring" in st.reason
    # the score IS read, so the score clock sees the touchdown at once
    assert st.score == (16, 24)


def test_a_conversion_try_is_skipped():
    pat = copy.deepcopy(RUSH_442)
    pat["type"] = {"id": "999", "text": "Two-Point Pass"}
    st = S.state_from_docs(META, status(), situation(1, TB), [pat])
    assert not st.evaluable and "conversion" in st.reason


def test_no_scrimmage_down_is_transitional():
    for down in (0, -1, None, 5):
        st = S.state_from_docs(META, status(), situation(down, TB), [KICKOFF])
        assert not st.evaluable and "transitional" in st.reason, down


def test_after_the_kickoff_lands_the_receiver_has_the_ball():
    st = S.state_from_docs(META, status(), situation(1, TB), [TD, KICKOFF])
    assert st.evaluable, st.reason
    assert st.possession == "away" and st.secs == 326.0


def test_possession_unknown_is_skipped():
    st = S.state_from_docs(META, status(), situation(3, None), [RUSH_442])
    assert st.possession is None and not st.evaluable
    assert "possession unknown" in st.reason


def test_possession_disagreeing_with_the_play_is_skipped():
    st = S.state_from_docs(META, status(), situation(1, DAL), [RUSH_442])
    assert not st.evaluable and "disagrees" in st.reason


def test_possession_is_parsed_whole_not_by_substring():
    """Home team 1, away team 12, the ball with team 12. The old core parser's
    `home_id in poss_ref` said HOME, because '1' is inside '/teams/12'."""
    meta = S.EventMeta(event_id="x", date=None, home_id="1", away_id="12", home_abbr="ATL",
                       away_abbr="KC", status_ref=None, situation_ref=None, plays_ref=None)
    play = copy.deepcopy(RUSH_442)
    play["end"]["team"] = {"$ref": T.format("12")}
    st = S.state_from_docs(meta, status(), situation(1, "12"), [play])
    assert S.team_id({"$ref": T.format("12")}) == "12"
    assert "1" in T.format("12")                     # the trap the old parser fell into
    assert st.possession == "away", st.reason
    assert st.evaluable


def test_the_site_api_possession_key_is_a_fallback():
    s = {"down": 1, "possession": TB}
    assert S.possession_team_id(s) == TB
    assert S.possession_team_id({"down": 1}) is None


@pytest.mark.parametrize("st_kw,reason", [
    (dict(period=5), "overtime"),
    (dict(period=4, state="post", completed=True, name="STATUS_FINAL"), "game over"),
    (dict(period=3), "period 3"),
    (dict(period=None), "period unknown"),
    (dict(state="pre", period=0), "not in progress (pre)"),
])
def test_status_refusals(st_kw, reason):
    st = S.state_from_docs(META, status(**st_kw), situation(3, TB), [RUSH_442])
    assert not st.evaluable and st.reason == reason
    assert not S.in_window(st)


def test_a_previous_quarters_play_is_not_the_state():
    q3 = copy.deepcopy(RUSH_442)
    q3["period"] = {"number": 3}
    st = S.state_from_docs(META, status(period=4), situation(1, TB), [q3])
    assert not st.evaluable and "period 3" in st.reason


def test_window_bounds():
    base = S.state_from_docs(META, status(), situation(3, TB), [RUSH_442])
    for secs, lead_scores, inside in ((600.0, (16, 24), True), (601.0, (16, 24), False),
                                      (300.0, (21, 24), False), (300.0, (20, 24), True),
                                      (300.0, (8, 24), True), (300.0, (7, 24), False)):
        b = copy.copy(base)
        b.secs = secs
        b.home_score, b.away_score = lead_scores
        assert S.in_window(b) is inside, (secs, lead_scores)


def test_game_seconds():
    assert S.game_seconds(4, 282) == 282.0
    assert S.game_seconds(3, 100) == 1000.0
    assert S.game_seconds(5, 100) is None and S.game_seconds(None, 1) is None


def test_admin_rows_are_the_measured_set():
    assert S.is_admin_play(TIMEOUT_111)
    for tid, text in (("74", "Official Timeout"), ("75", "Two-minute warning"),
                      ("2", "End Period"), ("65", "End of Half"), ("66", "End of Game"),
                      ("70", "Coin Toss")):
        assert S.is_admin_play({"type": {"id": tid, "text": text}})
    for p in (RUSH_442, KICKOFF, TD):
        assert not S.is_admin_play(p)


# ─── team identity ────────────────────────────────────────────────────────────

def test_team_map_is_the_nfl_packages():
    import importlib.util
    from pathlib import Path

    from nfl_live_leader.teams import TEAM_MAP

    path = Path(__file__).resolve().parents[1] / "nfl" / "data_ingest" / "parse.py"
    spec = importlib.util.spec_from_file_location("_nfl_parse_for_test", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert TEAM_MAP == mod.TEAM_MAP


def test_espn_and_book_names_map_to_the_platform_abbreviations():
    from nfl_live_leader.teams import abbrev

    assert abbrev("WSH") == "WAS" and abbrev("LAR") == "LA" and abbrev("JAC") == "JAX"
    assert abbrev("Los Angeles Rams") == "LA" and abbrev("Washington Commanders") == "WAS"
    assert abbrev("DAL") == "DAL" and abbrev("LAC") == "LAC"
    assert abbrev("XYZ") is None and abbrev(None) is None
