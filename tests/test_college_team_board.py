"""NCAAB and NCAABW Teams boards.

The board is the NBA/WNBA one: Efficiency / Record / Betting, default Net Rtg,
no rest splits, no college player props. Team detail keeps the NCAAF per-game
last-10 list and does not grow an NBA first-quarter card. Game-line pills are
the Teams board's existing day-and-book gate, not a sport exclusion.

The efficiency numbers come from team_stats_board_compute, patched by
data/migrations/team_stats_board_college_hoops_2026_11_12.sql. That file is
not on the worker's migration list. eFG% is stored as points because the
catalog format `dec1` prints the number as stored.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MIGRATION_NAME = "team_stats_board_college_hoops_2026_11_12.sql"
SQL = (ROOT / "data" / "migrations" / MIGRATION_NAME).read_text(encoding="utf-8")


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _fn(src: str, name: str) -> str:
    start = src.index(f"function {name}")
    # The next top-level function, or the end of the file.
    nxt = src.find("\nfunction ", start + 1)
    nxt = len(src) if nxt < 0 else nxt
    # Also stop at a top-level export function that follows.
    exp = src.find("\nexport function ", start + 1)
    if exp > start:
        nxt = min(nxt, exp)
    return src[start:nxt]


def _before(body: str, women: str, men: str) -> None:
    assert women in body, women
    assert body.index(women) < body.index(men), (women, men)


def test_the_migration_is_hand_applied_and_scales_efg():
    listed = re.findall(r'"([^"]+\.sql)"', _read("data/view_migrations.py"))
    assert MIGRATION_NAME not in listed
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in SQL
    assert "team_board_college_hoops" in SQL
    # Points, not a 0-1 rate: dec1 would print 0.6 for a stored 0.566.
    assert "100.0 * (sum(s.fgm) + 0.5 * sum(s.tpm))" in SQL
    assert "JOIN ncaabw_teams sch ON sch.espn_id = s.team_espn_id" in SQL
    assert "JOIN ncaab_teams sch ON sch.espn_id = s.team_espn_id" in SQL
    _before(SQL, "p_sport = 'NCAABW'", "p_sport = 'NCAAB'")
    _before(SQL, "eff_ncaabw AS", "eff_ncaab AS")
    # Conference stays off the name row.
    assert "NULL::text" in SQL
    assert "sch.conference" not in SQL


def test_a_zero_to_one_efg_is_not_what_dec1_prints_as_points():
    """The catalog format is dec1. 55.8 must be stored as 55.8."""
    # Mirrors formatTeamStat's dec1 branch and the SQL scale.
    rate = (10 + 0.5 * 4) / 20  # 0.6
    points = round(100.0 * rate, 1)
    assert points == 60.0
    assert f"{points:.1f}" == "60.0"
    assert f"{rate:.1f}" == "0.6"


def test_both_sports_are_on_the_board_and_off_rest_and_props():
    team = _read("mobile/src/lib/teamStatCatalog.ts")
    ball = re.search(r"const BALL: Sport\[\] = \[(.*?)\];", team).group(1)
    hoops = re.search(r"const HOOPS: Sport\[\] = \[(.*?)\];", team).group(1)
    rest = re.search(r"const RESTFUL: Sport\[\] = \[(.*?)\];", team).group(1)
    for sport in ("'NCAABW'", "'NCAAB'"):
        assert sport in ball
        assert sport in hoops
        assert sport not in rest
    _before(ball, "'NCAABW'", "'NCAAB'")
    _before(hoops, "'NCAABW'", "'NCAAB'")
    defaults = _fn(team, "defaultTeamStatFor")
    _before(defaults, "NCAABW: 'net_rating'", "NCAAB: 'net_rating'")
    for name in ("teamBoardSeason", "teamSeasonLabel"):
        body = _fn(team, name)
        _before(body, "sport === 'NCAABW'", "sport === 'NCAAB'")
    assert "How a team did against past lines. It describes, it doesn’t predict." in team

    cat = _read("mobile/src/lib/statCatalog.ts")
    market = _fn(cat, "propMarketForStat")
    _before(market, "def.sport === 'NCAABW'", "def.sport === 'NCAAB'")
    assert "def.sport === 'NCAABW' || def.sport === 'NCAAB') return null;" in market
    raw = cat[cat.index("function rawPropModelForStat"):]
    assert "def.sport === 'NCAAF' || def.sport === 'NCAABW' || def.sport === 'NCAAB') return null;" in raw


def test_fetch_falls_back_one_ending_year_label_and_does_not_short_circuit():
    q = _read("mobile/src/lib/queries.ts")
    body = _fn(q, "fetchTeamStats")
    head = body.split("const seasons")[0]
    assert "sport === 'UFC' || sport === 'GOLF') return { season: null, rows: [] };" in head
    assert "sport === 'NCAAB" not in head
    assert "sport === 'NFL' || sport === 'NCAAF'" in body
    assert "[season, season - 1]" in body
    assert "team_stats_board" in body


def test_the_worker_refreshes_both_sports_women_first():
    src = _read("data/team_board_cache.py")
    sports = re.search(r"TEAM_BOARD_SPORTS: tuple\[str, \.\.\.\] = \((.*?)\)", src, re.S).group(1)
    assert '"NCAABW"' in sports and '"NCAAB"' in sports
    _before(sports, '"NCAABW"', '"NCAAB"')


def test_team_detail_uses_meeting_rows_and_no_first_quarter_card():
    screen = _read("mobile/src/screens/TeamStatsScreen.tsx")
    gate = "sport === 'NCAABW' || sport === 'NCAAB' || sport === 'NCAAF'"
    assert gate in screen
    # The 10-cell strip is the other branch. College does not take it.
    assert screen.index(gate) < screen.index("<FormStrip")
    # The kickoff is its own text, so a long school name cannot cut the clock.
    assert "{side}\n            {unstarted" not in screen
    assert "<Text style={styles.fixtureWhen}>" in screen
    assert "teamStatFor(sport, 'rest_adv_ats_pct')" in screen
    assert "favourite/dog and rest splits" in screen
    assert "Home/away and favourite/dog splits describe" in screen
    q1 = screen[screen.index('title="First quarter"') - 80:screen.index('title="First quarter"')]
    assert "sport === 'NBA'" in q1
    assert "NCAAB" not in q1
    assert "headerBackButtonDisplayMode" not in screen


def test_game_line_pills_are_not_switched_off_for_college():
    board = _read("mobile/src/components/TeamsBoard.tsx")
    start = board.index("const showLines =")
    expr = board[start:board.index(";", start)]
    assert "NCAAB" not in expr
    assert "booksReady" in expr and "unstarted.size > 0" in expr
    assert "fetchGameLinesForDate" in board
