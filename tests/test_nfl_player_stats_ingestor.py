"""Pure-function tests for the nflverse weekly player-stats parser."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.ingestors.nfl_player_stats_ingestor import (
    current_nfl_season,
    parse_player_week_csv,
)

_HEADER = (
    "player_id,player_name,player_display_name,position,position_group,season,week,"
    "season_type,game_id,team,opponent_team,completions,attempts,passing_yards,"
    "passing_tds,passing_interceptions,carries,rushing_yards,rushing_tds,receptions,"
    "targets,receiving_yards,receiving_tds,def_sacks,def_interceptions"
)

_QB_ROW = (
    "00-0026158,J.Flacco,Joe Flacco,QB,QB,2025,1,REG,2025_01_CIN_CLE,CLE,CIN,"
    "31,45,290,1,2,2,6,0,0,0,0,0,0,0"
)
_WR_ROW = (
    "00-0039075,P.Nacua,Puka Nacua,WR,WR,2025,1,REG,2025_01_HOU_LA,LA,HOU,"
    "0,0,0,0,0,1,1,0,10,11,130,0,0,0"
)
# A kicker-style row: zero across every tracked stat → skipped.
_ZERO_ROW = (
    "00-0099999,K.Icker,Kicker Guy,K,SPEC,2025,1,REG,2025_01_CIN_CLE,CLE,CIN,"
    "0,0,0,0,0,0,0,0,0,0,0,0,0,0"
)
# Half-sack defender → kept (def_sacks is fractional).
_DEF_ROW = (
    "00-0088888,D.Fender,De Fender,LB,LB,2025,1,REG,2025_01_CIN_CLE,CIN,CLE,"
    "0,0,0,0,0,0,0,0,0,0,0,0,0.5,0"
)

_GAME_DATES = {"2025_01_CIN_CLE": "2025-09-07", "2025_01_HOU_LA": "2025-09-07"}


def _csv(*rows: str) -> str:
    return "\n".join([_HEADER, *rows])


def test_current_nfl_season_labels():
    assert current_nfl_season(date(2026, 8, 19)) == 2026   # pre-season → new label
    assert current_nfl_season(date(2026, 10, 1)) == 2026   # in season
    assert current_nfl_season(date(2027, 1, 15)) == 2026   # playoffs → prior label
    assert current_nfl_season(date(2027, 2, 10)) == 2026   # Super Bowl month
    assert current_nfl_season(date(2027, 3, 1)) == 2027    # off-season rolls over


def test_parse_qb_row():
    rows = parse_player_week_csv(_csv(_QB_ROW), _GAME_DATES)
    assert len(rows) == 1
    r = rows[0]
    assert r["player_id"] == "00-0026158"
    assert r["player_name"] == "Joe Flacco"       # display name preferred
    assert r["pos"] == "QB"
    assert r["team"] == "CLE" and r["opponent"] == "CIN"
    assert r["game_id"] == "NFL_2025_01_CIN_CLE"  # platform prefix
    assert r["game_date"] == "2025-09-07"         # joined from the schedule
    assert r["season"] == 2025 and r["week"] == 1 and r["season_type"] == "REG"
    assert r["completions"] == 31 and r["attempts"] == 45
    assert r["passing_yards"] == 290.0 and r["passing_tds"] == 1
    assert r["interceptions"] == 2                # passing_interceptions → interceptions
    assert r["carries"] == 2 and r["rushing_yards"] == 6.0


def test_all_zero_rows_are_skipped():
    rows = parse_player_week_csv(_csv(_QB_ROW, _ZERO_ROW, _WR_ROW), _GAME_DATES)
    assert {r["player_name"] for r in rows} == {"Joe Flacco", "Puka Nacua"}


def test_fractional_def_sacks_kept():
    rows = parse_player_week_csv(_csv(_DEF_ROW), _GAME_DATES)
    assert len(rows) == 1
    assert rows[0]["def_sacks"] == 0.5


def test_unknown_game_id_is_skipped():
    rows = parse_player_week_csv(_csv(_QB_ROW), {"some_other_game": "2025-09-07"})
    assert rows == []


def test_negative_yards_parse():
    row = _QB_ROW.replace(",290,", ",-4,")
    rows = parse_player_week_csv(_csv(row), _GAME_DATES)
    assert rows[0]["passing_yards"] == -4.0
