"""Lineup segments from ESPN play-by-play (data/ingestors/nba_stints.py).

Each test builds a tiny synthetic game. Home players are 1-8, away players are
11-18; the box starters are 1-5 and 11-15 unless a test says otherwise.
"""
from __future__ import annotations

import itertools

import pytest

from data.ingestors import nba_stints as st

HOME5 = {1, 2, 3, 4, 5}
AWAY5 = {11, 12, 13, 14, 15}
ROSTER = {**{i: "H" for i in range(1, 9)}, **{i: "A" for i in range(11, 19)}}
STARTERS = {"H": set(HOME5), "A": set(AWAY5)}
_seq = itertools.count(1)


def P(period, clock, type_text, side=None, a1=None, a2=None, a3=None, *,
      scoring=False, shooting=False, text="", **extra):
    row = {"period": period, "clock": float(clock), "sequence_number": next(_seq),
           "type_text": type_text, "team_side": side, "athlete_id_1": a1,
           "athlete_id_2": a2, "athlete_id_3": a3, "scoring_play": scoring,
           "shooting_play": shooting, "text": text}
    row.update(extra)
    return row


def sub(period, clock, side, pin, pout, text=None):
    return P(period, clock, "Substitution", side, pin, pout,
             text=text if text is not None else f"P{pin} enters the game for P{pout}")


def make2(period, clock, side, who):
    return P(period, clock, "Jump Shot", side, who, scoring=True, shooting=True,
             text=f"P{who} makes 12-foot jumper", espn_score_value=2)


def make3(period, clock, side, who):
    return P(period, clock, "Jump Shot", side, who, scoring=True, shooting=True,
             text=f"P{who} makes 26-foot three point jumper", espn_score_value=3)


def miss(period, clock, side, who):
    return P(period, clock, "Jump Shot", side, who, shooting=True,
             text=f"P{who} misses 12-foot jumper")


def dreb(period, clock, side, who):
    return P(period, clock, "Defensive Rebound", side, who, text=f"P{who} defensive rebound")


def end_period(period):
    return P(period, 0.0, "End Period", text=f"End of period {period}")


def quiet_period(period, home_touch=(), away_touch=()):
    """A period in which the listed players each make one miss; nothing else."""
    length = st.period_seconds(period)
    out, clock = [], length - 10
    for who in home_touch:
        out.append(miss(period, clock, "H", who))
        out.append(dreb(period, clock - 1, "A", 11))
        clock -= 20
    for who in away_touch:
        out.append(miss(period, clock, "A", who))
        out.append(dreb(period, clock - 1, "H", 1))
        clock -= 20
    out.append(end_period(period))
    return out


def derive(plays, roster=ROSTER, starters=STARTERS, seconds=None):
    return st.derive_stints(plays, roster, starters, seconds or {})


def five_game(extra_by_period=None, periods=4):
    """Starters touch the ball every period, so every period's five is seen."""
    plays = []
    for per in range(1, periods + 1):
        plays += quiet_period(per, home_touch=sorted(HOME5), away_touch=sorted(AWAY5))
        if extra_by_period and per in extra_by_period:
            plays = plays[:-1] + extra_by_period[per] + plays[-1:]
    return plays


# ── clock, order, shot value ────────────────────────────────────────────────

@pytest.mark.parametrize("display, secs", [
    ("11:47", 707.0), ("0:2.1", 2.1), ("12:00", 720.0), ("45.3", 45.3),
    ("1:38:59", 98.59), ("", None), (None, None)])
def test_parse_clock(display, secs):
    got = st.parse_clock(display)
    assert got == pytest.approx(secs) if secs is not None else got is None


def test_game_seconds_add_five_minutes_per_overtime():
    assert st.game_seconds(4) == 2880
    assert st.game_seconds(5) == 3180
    assert st.game_seconds(7) == 3780
    assert st.elapsed(5, 300) == 2880 and st.elapsed(5, 0) == 3180


def test_plays_are_ordered_by_clock_not_by_espn_sequence():
    """ESPN appends corrections with later sequence numbers; the clock wins."""
    late = P(1, 600, "Jump Shot", "H", 1, sequence_number=99)
    early = P(1, 700, "Jump Shot", "H", 2, sequence_number=100)
    p2 = P(2, 719, "Jump Shot", "H", 3, sequence_number=1)
    assert [p["athlete_id_1"] for p in st.order_plays([p2, late, early])] == [2, 1, 3]


@pytest.mark.parametrize("row, value", [
    ({"text": "X makes 26-foot three point jumper"}, 3),
    ({"text": "X misses 24-foot step back jumpshot"}, 3),          # distance says three
    ({"text": "X misses 21-foot jumper"}, 2),
    ({"text": "X makes 24-foot step back jumpshot", "scoring_play": True,
      "espn_score_value": 3}, 3),
    ({"text": "X makes 22-foot jumper", "scoring_play": True, "espn_score_value": 2}, 2),
    ({"text": "X misses 22-foot jumper", "coord_x": 2.5, "coord_y": 3.0}, 3),   # corner, 22.7 ft
    ({"text": "X misses 22-foot jumper", "coord_x": 25.0, "coord_y": 22.0}, 2),  # top, inside the arc
    ({"text": "X misses jumper", "coord_x": 25.0, "coord_y": 25.0}, 3),
    ({"text": "X misses jumper", "espn_points_attempted": 3}, 3),
])
def test_field_goal_value(row, value):
    assert st.classify_field_goal(row) == value


def test_a_made_free_throw_is_one_point_even_when_espn_says_zero():
    """2018-19's file has score_value 0 on every made free throw."""
    ft = P(1, 100, "Free Throw - 1 of 2", "H", 1, scoring=True, shooting=True,
           text="P1 makes free throw 1 of 2", espn_score_value=0)
    assert st.play_points(ft) == 1
    assert st.play_points(make3(1, 90, "H", 1)) == 3


# ── substitutions ───────────────────────────────────────────────────────────

def test_a_substitution_reads_entering_then_leaving():
    assert st.sub_players(sub(1, 300, "H", 6, 1)) == (6, 1)


def test_a_half_logged_substitution_is_read_from_its_text():
    """'X enters the game for ' has only the entrant; ' enters the game for Y'
    carries the LEAVING player in athlete_id_1."""
    only_in = P(1, 287, "Substitution", "A", 16, text="Devin Harris enters the game for ")
    only_out = P(1, 287, "Substitution", "A", 11, text=" enters the game for Wesley Matthews")
    assert st.sub_players(only_in) == (16, None)
    assert st.sub_players(only_out) == (None, 11)


def test_a_mid_period_substitution_splits_the_segment():
    plays = five_game({1: [make2(1, 650, "H", 1), sub(1, 400, "H", 6, 1),
                           make2(1, 300, "H", 6)]})
    stints, diag = derive(plays)
    p1 = [s for s in stints if s["period"] == 1]
    assert len(p1) == 2
    first, second = p1
    assert first["home_ids"] == [1, 2, 3, 4, 5] and second["home_ids"] == [2, 3, 4, 5, 6]
    assert (first["start_s"], first["end_s"], second["end_s"]) == (0.0, 320.0, 720.0)
    assert first["home_pts"] == 2 and second["home_pts"] == 2
    assert all(s["n_home"] == 5 and s["n_away"] == 5 for s in stints)


def test_substitutions_between_free_throws_wait_for_the_last_one():
    """The free throws belong to the five on the floor when the foul happened."""
    trip = [P(1, 200, "Shooting Foul", "A", 11, 2, text="P11 shooting foul"),
            P(1, 200, "Free Throw - 1 of 2", "H", 2, scoring=True, shooting=True,
              text="P2 makes free throw 1 of 2"),
            sub(1, 200, "H", 6, 1),
            P(1, 200, "Free Throw - 2 of 2", "H", 2, scoring=True, shooting=True,
              text="P2 makes free throw 2 of 2")]
    stints, _ = derive(five_game({1: trip}))
    p1 = [s for s in stints if s["period"] == 1]
    before = [s for s in p1 if 1 in s["home_ids"]]
    assert sum(s["home_pts"] for s in before) == 2
    assert not any(s["duration_s"] == 0 and s["home_pts"] for s in p1)


def test_a_sub_logged_after_the_entrants_own_play_is_pulled_before_it():
    """Same clock: P6's foul is logged a line before 'P6 enters for P1'."""
    plays = five_game({1: [P(1, 300, "Personal Foul", "H", 6, 12, text="P6 personal foul"),
                           sub(1, 300, "H", 6, 1)]})
    stints, diag = derive(plays)
    assert diag.added_from_play == 0
    assert all(s["n_home"] == 5 for s in stints)


# ── who starts a period ─────────────────────────────────────────────────────

def test_period_starters_come_from_first_appearances():
    plays = [miss(2, 700, "H", 6), sub(2, 650, "H", 7, 6), sub(2, 600, "H", 1, 8)]
    status = st.first_appearances(plays, ROSTER)
    assert status == {6: "start", 7: "bench", 8: "start", 1: "bench"}


def test_a_player_with_no_play_all_quarter_is_carried_from_the_previous_period():
    """Player 5 is on the floor at the end of Q1 and does nothing in Q2: the
    ESPN gap. He fills the fifth spot in Q2."""
    plays = quiet_period(1, home_touch=[1, 2, 3, 4, 5], away_touch=sorted(AWAY5))
    plays += quiet_period(2, home_touch=[1, 2, 3, 4], away_touch=sorted(AWAY5))
    # P6 has more box time left than P5, so only the previous period's
    # five can explain choosing P5.
    seconds = {**{pid: 1440.0 for pid in HOME5 | AWAY5}, 6: 2000.0}
    stints, diag = derive(plays, seconds=seconds)
    q2 = [s for s in stints if s["period"] == 2]
    assert q2 and all(s["home_ids"] == [1, 2, 3, 4, 5] for s in q2)
    assert diag.filled_prev_end == 1 and diag.short_after_fill == 0


def test_without_a_previous_period_the_fill_takes_the_most_unused_box_time():
    """Box starters unusable (four listed): the fifth is the player with the
    most box seconds not yet credited."""
    plays = quiet_period(1, home_touch=[1, 2, 3, 4], away_touch=sorted(AWAY5))
    seconds = {1: 700, 2: 700, 3: 700, 4: 700, 5: 600, 6: 720, 7: 100}
    stints, diag = derive(plays, starters={"H": {1, 2, 3, 4}, "A": set(AWAY5)},
                          seconds=seconds)
    assert stints[0]["home_ids"] == [1, 2, 3, 4, 6]
    assert diag.filled_box == 1


def test_a_play_by_a_player_never_subbed_in_puts_him_on_and_drops_the_quiet_one():
    """P7 enters through a substitution ESPN never logged. P1-P4 all play
    later in the period, so the one who left must be P5."""
    later = []
    for n, who in enumerate((1, 2, 3, 4)):
        later += [miss(1, 200 - 10 * n, "H", who), dreb(1, 199 - 10 * n, "A", 12)]
    extra = {1: [miss(1, 300, "H", 7), dreb(1, 299, "A", 12)] + later}
    plays = quiet_period(1, home_touch=[1, 2, 3, 4, 5], away_touch=sorted(AWAY5))
    plays = plays[:-1] + extra[1] + plays[-1:]
    stints, diag = derive(plays)
    last = [s for s in stints if s["period"] == 1][-1]
    assert last["home_ids"] == [1, 2, 3, 4, 7]
    assert diag.added_from_play == 1 and diag.dropped_extra == 1
    assert all(s["n_home"] == 5 for s in stints)


def test_a_half_logged_change_leaves_five_on_the_floor():
    """Only 'P6 enters the game for ' is logged; P1-P4 all play later, so
    P5 is the one who left."""
    plays = quiet_period(1, home_touch=[1, 2, 3, 4, 5], away_touch=sorted(AWAY5))
    later = []
    for n, who in enumerate((1, 2, 3, 4)):
        later += [miss(1, 200 - 10 * n, "H", who), dreb(1, 199 - 10 * n, "A", 12)]
    plays = plays[:-1] + [P(1, 300, "Substitution", "H", 6, text="P6 enters the game for "),
                          miss(1, 250, "H", 6), dreb(1, 249, "A", 11)] + later + plays[-1:]
    stints, diag = derive(plays)
    assert all(s["n_home"] == 5 for s in stints)
    assert [s for s in stints if s["period"] == 1][-1]["home_ids"] == [1, 2, 3, 4, 6]


def test_a_change_logged_without_its_entrant_is_filled_from_the_next_play():
    """Only ' enters the game for P5' is logged; P6, who has a play later
    without being substituted in, is the one who came on."""
    plays = quiet_period(1, home_touch=[1, 2, 3, 4, 5], away_touch=sorted(AWAY5))
    plays = plays[:-1] + [P(1, 300, "Substitution", "H", 5, text=" enters the game for P5"),
                          miss(1, 250, "H", 6), dreb(1, 249, "A", 11)] + plays[-1:]
    stints, diag = derive(plays)
    assert diag.added_missing == 1
    assert all(s["n_home"] == 5 for s in stints)
    after = [s for s in stints if s["period"] == 1 and s["start_s"] >= 420]
    assert after and all(s["home_ids"] == [1, 2, 3, 4, 6] for s in after)


def test_a_change_undone_at_the_same_instant_leaves_one_segment():
    plays = five_game({1: [sub(1, 400, "H", 6, 1), sub(1, 400, "H", 1, 6)]})
    stints, _ = derive(plays)
    assert len([s for s in stints if s["period"] == 1]) == 1


def test_a_bench_technical_does_not_put_the_player_on_the_floor():
    plays = five_game({1: [P(1, 400, "Technical Foul", "H", 8, text="P8 technical foul")]})
    stints, diag = derive(plays)
    assert not any(8 in s["home_ids"] for s in stints)
    assert diag.added_from_play == 0


# ── time, overtime, points ──────────────────────────────────────────────────

def test_segments_tile_regulation_and_each_overtime():
    plays = five_game(periods=5)
    stints, _ = derive(plays)
    assert sum(s["duration_s"] for s in stints) == pytest.approx(3180.0)
    ot = [s for s in stints if s["period"] == 5]
    assert ot[0]["start_s"] == 2880.0 and ot[-1]["end_s"] == 3180.0
    for a, b in zip(stints, stints[1:]):
        assert b["start_s"] == pytest.approx(a["end_s"])


def test_segment_points_sum_to_the_final_score():
    extra = {1: [make2(1, 650, "H", 1), make3(1, 600, "A", 12), sub(1, 500, "H", 6, 3)],
             3: [make3(3, 100, "H", 6)]}
    stints, _ = derive(five_game(extra))
    assert sum(s["home_pts"] for s in stints) == 5
    assert sum(s["away_pts"] for s in stints) == 3


# ── free throws ESPN left without a team ────────────────────────────────────

def _sas_dal_technical():
    """ESPN 401469046 (NBA_2023-02-23_SAS_DAL), 6:58 of the 1st: Branham's
    and-one layup, Green's shooting foul, Doncic's technical, then the made
    technical and the missed and-one, both logged with no team."""
    sc = {"espn_home_score": 13}
    return [
        make2(1, 418, "A", 12) | {**sc, "espn_away_score": 12},
        P(1, 418, "Shooting Foul", "H", 2, text="P2 shooting foul", **sc, espn_away_score=12),
        P(1, 418, "Technical Foul", "H", 1, text="P1 technical foul", **sc, espn_away_score=12),
        P(1, 418, "Free Throw - Technical", None, scoring=True, shooting=True,
          text="makes technical free throw", **sc, espn_away_score=13),
        P(1, 418, "Free Throw - 1 of 1", None, shooting=True,
          text="misses free throw 1 of 1", **sc, espn_away_score=13),
        dreb(1, 416, "H", 1) | {**sc, "espn_away_score": 13},
    ]


def test_a_free_throw_with_no_team_takes_its_side_from_the_running_score_or_the_trip():
    plays = _sas_dal_technical()
    assert st.infer_sides(plays) == 2
    assert plays[3]["team_side"] == "A"      # the running score rose on the away side
    assert plays[4]["team_side"] == "A"      # a miss: the side of the trip's other free throw
    # the and-one now counts as one possession, ended by the defensive rebound
    ends = st.possession_ends(st.order_plays(plays))
    assert list(ends.values()) == ["A"]


def test_a_free_throw_with_nothing_to_go_on_takes_the_opponent_of_the_foul():
    plays = [P(1, 300, "Shooting Foul", "H", 2, text="P2 shooting foul"),
             P(1, 300, "Free Throw - 1 of 1", None, shooting=True, text="misses free throw 1 of 1")]
    assert st.infer_sides(plays) == 1 and plays[1]["team_side"] == "A"


# ── when the plays do not add up to ESPN's final ────────────────────────────

def _scored(row, h, a):
    return row | {"espn_home_score": h, "espn_away_score": a}


def _dup_game():
    """Home's three at 10:00 is logged a second time at 9:58 (the running
    score does not move on it); a substitution follows; away scores two."""
    return five_game({1: [_scored(make3(1, 600, "H", 1), 3, 0),
                          _scored(make3(1, 598, "H", 1), 3, 0),
                          _scored(sub(1, 500, "H", 6, 1), 3, 0),
                          _scored(make2(1, 400, "A", 11), 3, 2),
                          _scored(make2(1, 300, "H", 6), 5, 2)]})


def test_a_duplicated_play_scores_nothing_when_the_running_score_ends_at_the_final():
    plays = _dup_game()
    stints, diag = derive(plays)
    assert sum(s["home_pts"] for s in stints) == 8          # the plays' own points
    stints, diag = st.derive_stints(plays, ROSTER, STARTERS, {}, final=(5, 2))
    assert sum(s["home_pts"] for s in stints) == 5
    assert sum(s["away_pts"] for s in stints) == 2
    assert diag.points_source == "espn_running_score" and diag.espn_score_sides == ["H"]
    first = [s for s in stints if s["period"] == 1 and 1 in s["home_ids"]]
    assert sum(s["home_pts"] for s in first) == 3            # the three, once, by P1's five


def test_a_lagging_running_score_still_credits_the_scoring_play():
    """The running score shows home's two only on the rebound after the
    change; the points stay with the five that scored them."""
    plays = five_game({1: [_scored(make3(1, 600, "H", 1), 3, 0),
                           _scored(make3(1, 598, "H", 1), 3, 0),        # duplicate
                           _scored(make2(1, 500, "H", 2), 3, 0),        # running score lags
                           _scored(sub(1, 500, "H", 6, 2), 3, 0),
                           _scored(miss(1, 480, "A", 11), 3, 0),
                           _scored(dreb(1, 478, "H", 6), 5, 0)]})
    stints, _ = st.derive_stints(plays, ROSTER, STARTERS, {}, final=(5, 0))
    with_p2 = [s for s in stints if s["period"] == 1 and 2 in s["home_ids"]]
    assert sum(s["home_pts"] for s in with_p2) == 5
    assert sum(s["home_pts"] for s in stints) == 5


def test_the_plays_points_stand_when_they_add_up_or_espn_is_short_too():
    plays = _dup_game()
    # adds up (the final says 8): ESPN's running score is never read
    stints, diag = st.derive_stints(plays, ROSTER, STARTERS, {}, final=(8, 2))
    assert sum(s["home_pts"] for s in stints) == 8 and diag.points_source == "plays"
    # ESPN's running score ends at 5 but the final says 9: plays missing, keep 8
    stints, diag = st.derive_stints(plays, ROSTER, STARTERS, {}, final=(9, 2))
    assert sum(s["home_pts"] for s in stints) == 8 and diag.points_source == "plays"


# ── zero-second segments ────────────────────────────────────────────────────

def test_a_change_with_the_clock_stopped_keeps_the_five_that_played_the_event():
    """NBA_2025-11-26_MIN_OKC, 0:26.8 of the 4th: after the timeout the away
    side brings on P16 for P11, commits a 5-second inbound violation, and P11
    goes back on, all at one instant. The turnover is the zero-second five's,
    not the five before the timeout's."""
    plays = five_game({4: [P(4, 26.8, "Full Timeout", "A", text="Full timeout"),
                           sub(4, 26.8, "A", 16, 11),
                           P(4, 26.8, "5-Second Turnover", "A", text="5 second violation"),
                           sub(4, 26.8, "A", 11, 16)]})
    stints, _ = derive(plays)
    zero = [s for s in stints if s["duration_s"] == 0]
    assert len(zero) == 1
    assert 16 in zero[0]["away_ids"] and 11 not in zero[0]["away_ids"]
    assert zero[0]["away_tov"] == 1 and zero[0]["away_poss"] == 1
    assert sum(s["away_tov"] for s in stints if s["duration_s"] > 0) == 0


# ── possessions ─────────────────────────────────────────────────────────────

def test_possessions_end_on_makes_rebounds_turnovers_and_the_last_free_throw():
    plays = [
        make2(1, 700, "H", 1),                                     # H ends
        miss(1, 690, "A", 11), dreb(1, 688, "H", 2),               # A ends
        P(1, 680, "Lost Ball Turnover", "H", 3, text="P3 lost ball turnover"),  # H ends
        P(1, 670, "Shooting Foul", "H", 1, 12, text="P1 shooting foul"),
        P(1, 670, "Free Throw - 1 of 2", "A", 12, shooting=True, text="P12 misses free throw 1 of 2"),
        P(1, 670, "Offensive Rebound", "A", text="team offensive rebound"),   # dead ball
        P(1, 670, "Free Throw - 2 of 2", "A", 12, scoring=True, shooting=True,
          text="P12 makes free throw 2 of 2"),                     # A ends
        end_period(1),
    ]
    ordered = st.order_plays(plays)
    ends = st.possession_ends(ordered)
    by_play = {ordered[k]["type_text"]: side for k, side in ends.items()}
    # H: the make, the turnover, and the ball it holds when the period ends.
    # A: the defensive rebound that ends its miss, and the made last free throw.
    assert list(ends.values()).count("H") == 3
    assert list(ends.values()).count("A") == 2
    assert by_play["Free Throw - 2 of 2"] == "A" and by_play["End Period"] == "H"
    assert "Free Throw - 1 of 2" not in by_play
    assert st.dead_ball_rebounds(ordered) == {6}


def test_an_and_one_is_one_possession():
    plays = [make2(1, 500, "H", 1),
             P(1, 500, "Shooting Foul", "A", 11, 1, text="P11 shooting foul"),
             P(1, 500, "Free Throw - 1 of 1", "H", 1, scoring=True, shooting=True,
               text="P1 makes free throw 1 of 1")]
    ends = st.possession_ends(st.order_plays(plays))
    assert list(ends.values()) == ["H"]


def test_the_end_of_a_period_closes_the_open_possession():
    plays = [make2(1, 30, "H", 1), miss(1, 5, "A", 11), end_period(1)]
    ends = st.possession_ends(st.order_plays(plays))
    assert list(ends.values()) == ["H", "A"]


def test_no_extra_possession_when_the_last_one_ended_at_the_buzzer():
    plays = [make2(1, 0.0, "H", 1), end_period(1)]
    ends = st.possession_ends(st.order_plays(plays))
    assert list(ends.values()) == ["H"]


# ── garbage time ────────────────────────────────────────────────────────────

BIG_ROSTER = {**{i: "H" for i in range(1, 10)}, **{i: "A" for i in range(11, 20)}}
ALL_SECONDS = {pid: 2000.0 for pid in BIG_ROSTER}


def _blowout_q4(threes, sub_clock, comeback=False):
    """Q1-Q3 quiet; in the 4th home makes `threes` threes early, then at
    `sub_clock` both sides bring on four reserves (one starter each left,
    two combined). Optionally the away side cuts it to 6 with 1:00 left."""
    plays = five_game(periods=3)
    q4, clock = [], 700
    for _ in range(threes):
        q4.append(make3(4, clock, "H", 1))
        clock -= 5
    for pin, pout in ((6, 1), (7, 2), (8, 3), (9, 4)):
        q4.append(sub(4, sub_clock, "H", pin, pout))
    for pin, pout in ((16, 11), (17, 12), (18, 13), (19, 14)):
        q4.append(sub(4, sub_clock, "A", pin, pout))
    if comeback:
        clock = 250
        for _ in range(8):
            q4.append(make3(4, clock, "A", 16))
            clock -= 20
    q4.append(miss(4, 100, "H", 6))
    q4.append(dreb(4, 99, "A", 16))
    q4.append(end_period(4))
    return st.derive_stints(plays + q4, BIG_ROSTER, STARTERS, ALL_SECONDS)


def test_garbage_time_starts_when_the_rule_holds_to_the_buzzer():
    """Up 30 with 5:00 left and two starters on the floor: garbage from 5:00."""
    stints, diag = _blowout_q4(10, 300)
    assert all(s["n_home"] == 5 and s["n_away"] == 5 for s in stints)
    assert diag.garbage_start == pytest.approx(2880 - 300)
    g = [s for s in stints if s["garbage_time"]]
    assert g and all(s["start_s"] >= 2580 for s in g)
    assert sum(s["duration_s"] for s in g) == pytest.approx(300)


def test_garbage_time_can_begin_inside_a_segment():
    """Up 15 when the benches come in at 10:00: not garbage (25 needed), not
    at 9:00 (20 needed), garbage from 6:00 (10 needed). Nothing happens at
    6:00, so the segment is split there: same ten players, two rows."""
    stints, diag = _blowout_q4(5, 600)
    assert diag.garbage_start == pytest.approx(2880 - 360)
    q4 = [s for s in stints if s["period"] == 4 and s["start_s"] >= 2280]
    assert [(s["start_s"], s["end_s"], s["garbage_time"]) for s in q4] == [
        (2280.0, 2520.0, False), (2520.0, 2880.0, True)]
    assert q4[0]["home_ids"] == q4[1]["home_ids"] == [5, 6, 7, 8, 9]


def test_a_comeback_means_no_garbage_time():
    """CTG: the game can never go back to being non-garbage time."""
    stints, diag = _blowout_q4(10, 300, comeback=True)
    assert diag.garbage_start is None
    assert not any(s["garbage_time"] for s in stints)


def test_overtime_games_have_no_garbage_time():
    assert st.garbage_start([(2160, 30, 0, 0), (2880, 30, 0, 1)], 5) is None


def test_garbage_bands_need_25_then_20_then_10():
    # 7:00 left, margin 22, no starters: the 20-point band
    assert st._garbage_ok(420, 22, 0)
    assert not st._garbage_ok(600, 22, 0)
    assert st._garbage_ok(200, 10, 2)
    assert not st._garbage_ok(200, 10, 3)
