"""data/ingestors/nba_schedule_ingestor: tip-off times, game types, overtime.

The schedule is what filled `games.commence_time` for every NBA game 2018-19 to
2025-26 (all 9,509 were NULL) and inserted the neutral-site games the game-log
ingestor drops. These pin the parsing that decides which rows reach `games`.
"""
import pandas as pd

from data.ingestors.nba_schedule_ingestor import ot_periods, schedule_rows, season_str


def _row(**kw):
    base = {
        "gameId": "0022500001", "gameDateTimeUTC": "2025-10-21T23:30:00Z",
        "gameDateEst": "2025-10-21T00:00:00Z", "gameStatusText": "Final/OT2",
        "homeTeam_teamTricode": "OKC", "awayTeam_teamTricode": "HOU",
        "homeTeam_score": 125, "awayTeam_score": 124, "arenaName": "Paycom Center",
        "arenaCity": "Oklahoma City", "arenaState": "OK", "isNeutral": False,
        "gameLabel": "", "gameSubLabel": "",
        "nationalBroadcasters_0_broadcasterDisplay": "NBC",
    }
    base.update(kw)
    return base


def test_season_label_is_the_ending_year():
    assert season_str(2026) == "2025-26"
    assert season_str(2020) == "2019-20"


def test_overtime_periods_come_from_the_status_text():
    assert ot_periods("Final") == 0
    assert ot_periods("Final/OT") == 1
    assert ot_periods("Final/OT2") == 2
    assert ot_periods("7:30 pm ET") is None      # not played yet
    assert ot_periods(None) is None


def test_a_late_west_coast_tip_keeps_its_eastern_date():
    # 02:30Z on the 22nd is 10:30 pm ET on the 21st: the game is the 21st's.
    rows = schedule_rows(2026, pd.DataFrame([_row(gameDateTimeUTC="2025-10-22T02:30:00Z",
                                                  homeTeam_tricode="LAL")]))
    assert rows[0]["game_date"] == "2025-10-21"
    assert rows[0]["game_id"] == "NBA_2025-10-21_HOU_OKC"
    assert rows[0]["commence_time"].startswith("2025-10-22T02:30:00")


def test_game_type_is_read_from_the_first_three_digits():
    frame = pd.DataFrame([_row(gameId="0022500001"), _row(gameId="0042500101"),
                          _row(gameId="0052500001"), _row(gameId="0012500001")])
    kinds = [r["game_type"] for r in schedule_rows(2026, frame)]
    assert kinds == ["regular", "playoff", "playin", "preseason"]


def test_scores_only_for_a_final_and_neutral_sites_are_flagged():
    frame = pd.DataFrame([
        _row(isNeutral=True, arenaCity="Mexico City"),
        _row(gameId="0022500002", gameStatusText="7:30 pm ET", homeTeam_score=0, awayTeam_score=0),
    ])
    final, future = schedule_rows(2026, frame)
    assert (final["home_score"], final["away_score"], final["is_neutral"]) == (125, 124, True)
    assert final["ot_periods"] == 2 and final["national_tv"] == "NBC"
    assert future["home_score"] is None and future["ot_periods"] is None


def test_an_undecided_playoff_slot_is_skipped():
    rows = schedule_rows(2026, pd.DataFrame([_row(gameId="0042500201", homeTeam_teamTricode=None)]))
    assert rows == []
