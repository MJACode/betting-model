"""The play-by-play shot parser: digit order, ends, teams, order, context.

Each rule here was measured on the feed before it was written down
(data/ingestors/nhl_shot_events.py says where), and each one, got wrong,
produces a table that looks fine: a swapped digit order turns every home power
play into a penalty kill, a wrong end puts a tap-in 170 feet out, and a blocked
shot credited to the blocking team moves an attempt to the other side of the
ledger. No network and no database here.
"""
from __future__ import annotations

import math

import pytest

from data.ingestors.nhl_shot_events import (COLUMNS, GameMeta, decode_situation,
                                            parse_game, period_sides, shooter_view)

HOME, AWAY = 10, 20


# ── situationCode ────────────────────────────────────────────────────────────

def test_situation_code_digits_are_away_goalie_away_skaters_home_skaters_home_goalie():
    # "1451" on a home goal is the league's own "pp" (2023020001, event 170).
    assert decode_situation("1451") == {"away_goalie_in_net": 1, "away_skaters": 4,
                                        "home_skaters": 5, "home_goalie_in_net": 1}
    assert decode_situation(None) is None
    assert decode_situation("15a1") is None


def test_a_home_power_play_is_a_power_play_for_home_and_a_kill_for_away():
    sit = decode_situation("1451")
    home = shooter_view(sit, is_home=True)
    away = shooter_view(sit, is_home=False)
    assert (home["strength"], home["strength_state"]) == ("PP", "5v4")
    assert (away["strength"], away["strength_state"]) == ("SH", "4v5")
    assert home["empty_net"] == away["empty_net"] == 0


def test_an_extra_attacker_is_even_strength_and_the_other_net_is_empty():
    # "0651": the AWAY net is empty (2023020001, event 179, the league's
    # "empty-net", home team scoring).
    sit = decode_situation("0651")
    home = shooter_view(sit, is_home=True)
    away = shooter_view(sit, is_home=False)
    assert (home["strength"], home["strength_state"], home["empty_net"]) == ("EV", "5v6", 1)
    assert (away["strength"], away["strength_state"], away["empty_net"]) == ("EV", "6v5", 0)
    assert away["shooting_goalie_pulled"] == 1 and home["shooting_goalie_pulled"] == 0


def test_a_power_play_with_the_goalie_pulled_is_still_a_power_play():
    # home goalie out, 6 home skaters against 4
    assert shooter_view(decode_situation("1460"), is_home=True)["strength"] == "PP"


def test_penalty_shots_and_shootout_attempts_are_labelled_apart():
    assert shooter_view(decode_situation("1010"), is_home=True)["strength"] == "PS"
    assert shooter_view(decode_situation("0101"), is_home=False)["strength"] == "PS"
    assert shooter_view(decode_situation("1010"), is_home=True, shootout=True)["strength"] == "SO"


# ── which end a team attacks ─────────────────────────────────────────────────

def _play(eid, sort, per, clock, kind, owner=None, x=None, y=0, zone=None, side=None,
          sit="1551", ptype="REG", **details):
    d = dict(details)
    if owner is not None:
        d["eventOwnerTeamId"] = owner
    if x is not None:
        d.update(xCoord=x, yCoord=y)
    if zone:
        d["zoneCode"] = zone
    p = {"eventId": eid, "sortOrder": sort, "timeInPeriod": clock, "typeDescKey": kind,
         "situationCode": sit,
         "periodDescriptor": {"number": per, "periodType": ptype}, "details": d}
    if side:
        p["homeTeamDefendingSide"] = side
    return p


def test_the_end_is_read_off_owner_zones_when_the_feed_has_no_side():
    # 2018-19 carries no homeTeamDefendingSide at all. Home owns events in its
    # offensive zone at x > 0 and in its defensive zone at x < 0: home attacks +89.
    plays = [_play(i, i, 1, "01:00", "hit", owner=HOME, x=60, zone="O") for i in range(3)]
    plays += [_play(9, 9, 1, "02:00", "faceoff", owner=AWAY, x=70, zone="D")]
    chosen, ev = period_sides(plays, HOME, AWAY)
    assert chosen[1] == (1, "derived")
    assert ev[1]["votes"] == 4 and ev[1]["feed"] is None


def test_blocked_shots_do_not_vote_because_their_zone_is_the_blockers():
    # A block by AWAY of a HOME shot, owned by the shooter (HOME) and zoned "D"
    # from the blocker's side, at x = 70: read as an owner zone it would say
    # home DEFENDS +89. It must be ignored.
    plays = [_play(i, i, 1, "01:00", "blocked-shot", owner=HOME, x=70, zone="D")
             for i in range(10)]
    plays += [_play(20 + i, 20 + i, 1, "02:00", "shot-on-goal", owner=HOME, x=75, zone="O")
              for i in range(3)]
    chosen, ev = period_sides(plays, HOME, AWAY)
    assert chosen[1] == (1, "derived") and ev[1]["votes"] == 3


def test_decisive_votes_beat_the_feed_and_the_feed_beats_too_few_votes():
    votes = [_play(i, i, 1, "01:00", "hit", owner=HOME, x=-60, zone="O", side="left")
             for i in range(5)]          # home attacks -89; the feed says +89
    thin = [_play(10, 10, 2, "01:00", "hit", owner=HOME, x=60, zone="O", side="left")]
    chosen, ev = period_sides(votes + thin, HOME, AWAY)
    assert chosen[1] == (-1, "derived") and ev[1]["feed"] == 1
    assert chosen[2] == (1, "feed")


def test_a_period_with_nothing_to_go_on_takes_the_opposite_of_its_neighbour():
    plays = [_play(i, i, 3, "01:00", "hit", owner=HOME, x=60, zone="O") for i in range(4)]
    plays.append(_play(50, 50, 4, "00:30", "faceoff", owner=HOME, x=0, zone="N", ptype="OT"))
    chosen, _ = period_sides(plays, HOME, AWAY)
    assert chosen[4] == (-1, "adjacent")


# ── a whole game ─────────────────────────────────────────────────────────────

META = GameMeta(2023029999, "NHL_2023-11-01_AAA_HHH", 2024, 2, "2023-11-01", "HHH", "AAA")


def _game(plays):
    return {"gameType": 2, "season": 20232024, "gameDate": "2023-11-01",
            "gameState": "OFF",
            "homeTeam": {"id": HOME, "abbrev": "HHH", "sog": 1},
            "awayTeam": {"id": AWAY, "abbrev": "AAA", "sog": 2},
            "rosterSpots": [{"playerId": 1, "teamId": HOME}, {"playerId": 3, "teamId": HOME},
                            {"playerId": 2, "teamId": AWAY}],
            "plays": plays}


def _sample_game():
    # Period 1, the feed says home defends left, so home attacks +89 and away -89.
    # Three hits give the derived side the same answer.
    plays = [_play(100 + i, i, 1, "00:10", "hit", owner=HOME, x=50, zone="O", side="left")
             for i in range(3)]
    plays += [
        _play(1, 10, 1, "01:00", "shot-on-goal", owner=HOME, x=80, y=-5, zone="O",
              side="left", shootingPlayerId=1, goalieInNetId=900, shotType="wrist"),
        # A blocked AWAY shot owned by the BLOCKING team (HOME): the shooter
        # (player 2) is on the away roster, so the attempt is AWAY's.
        _play(2, 11, 1, "01:02", "blocked-shot", owner=HOME, x=-70, y=10, zone="D",
              side="left", shootingPlayerId=2, blockingPlayerId=3),
        # sortOrder 13 but earlier on the clock than the goal (sortOrder 12):
        # the parser must order by the clock.
        _play(4, 13, 1, "01:03", "missed-shot", owner=AWAY, x=-85, y=2, zone="O",
              side="left", shootingPlayerId=2, goalieInNetId=800, reason="wide-left"),
        _play(3, 12, 1, "01:04", "goal", owner=AWAY, x=-84, y=1, zone="O", side="left",
              sit="1541", scoringPlayerId=2, goalieInNetId=800, homeScore=0, awayScore=1),
        _play(5, 14, 1, "01:30", "shot-on-goal", owner=AWAY, x=-60, y=0, zone="O",
              side="left", shootingPlayerId=2, goalieInNetId=800),
        _play(6, 30, 5, "00:00", "goal", owner=HOME, x=-80, y=0, zone="O", sit="1010",
              ptype="SO", scoringPlayerId=1, goalieInNetId=900),
    ]
    return _game(plays)


def test_every_row_carries_every_insert_column():
    rows, _ = parse_game(_sample_game(), META)
    assert rows and all(set(COLUMNS) <= set(r) for r in rows)


def test_a_blocked_shot_belongs_to_the_shooter_even_when_owned_by_the_blocker():
    rows, diag = parse_game(_sample_game(), META)
    blk = next(r for r in rows if r["event_type"] == "blocked-shot")
    assert blk["shooting_team"] == "AAA" and blk["is_home"] == 0
    assert blk["event_owner_team"] == "HHH" and blk["blocker_id"] == 3
    assert diag["counts"]["block_owner_is_blocker_team"] == 1
    # normalised towards the net AWAY attacks (-89 this period)
    assert blk["attacking_net_x"] == -89 and (blk["x_norm"], blk["y_norm"]) == (70, -10)


def test_coordinates_are_rotated_so_the_attacking_net_is_at_plus_89():
    rows, _ = parse_game(_sample_game(), META)
    by_id = {r["event_id"]: r for r in rows}
    assert by_id[1]["attacking_net_x"] == 89 and (by_id[1]["x_norm"], by_id[1]["y_norm"]) == (80, -5)
    goal = by_id[3]
    assert goal["attacking_net_x"] == -89 and (goal["x_norm"], goal["y_norm"]) == (84, -1)
    assert math.hypot(89 - goal["x_norm"], goal["y_norm"]) < 6
    assert goal["side_source"] == "derived"


def test_the_clock_not_sortorder_decides_the_previous_event_and_the_score():
    rows, diag = parse_game(_sample_game(), META)
    by_id = {r["event_id"]: r for r in rows}
    miss, goal, after = by_id[4], by_id[3], by_id[5]
    assert (miss["prev_event_type"], miss["prev_team"], miss["prev_seconds_since"]) == (
        "blocked-shot", "AAA", 1)
    assert (goal["prev_event_type"], goal["prev_team"], goal["prev_seconds_since"]) == (
        "missed-shot", "AAA", 1)
    assert (goal["home_score_before"], goal["away_score_before"]) == (0, 0)
    assert (after["home_score_before"], after["away_score_before"]) == (0, 1)
    assert diag["counts"]["sortorder_not_chronological"] == 1
    assert diag["counts"]["score_mismatch"] == 0
    assert goal["strength"] == "PP" and goal["strength_state"] == "5v4"


def test_a_shootout_attempt_is_stored_flagged_and_never_scores_or_counts_as_a_shot():
    rows, diag = parse_game(_sample_game(), META)
    so = next(r for r in rows if r["period_type"] == "SO")
    assert so["strength"] == "SO" and so["game_seconds"] is None
    assert so["side_source"] == "shot" and so["x_norm"] == 80
    # non-shootout shots on goal + goals: home 1, away 2 (the goal and a shot)
    assert diag["sog_counted"] == diag["sog_feed"] == (1, 2)


def test_a_feed_whose_teams_are_not_the_logged_game_is_refused():
    g = _sample_game()
    g["homeTeam"]["abbrev"] = "ZZZ"
    with pytest.raises(ValueError, match="teams"):
        parse_game(g, META)
