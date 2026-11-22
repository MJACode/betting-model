"""AI assistant (MCP): one NCAAF game is one slate row, and the slate is whole.

Matt, 2026-11-21 ("We need the research to be better"). A member's assistant
asked for tonight's NCAAF games at 15:53 ET. mcp_meter.calls: get_slate today
returned 20 rows (the cap, all kicked off by 13:05 ET, four of them last
night's finals); get_slate tomorrow returned tonight's six late games under
their CFBD UTC-dated ids; get_game_lines returned not_found for all six. The
prices were stored under the odds feed's ET id of the same games.
"""
from __future__ import annotations

import re
from pathlib import Path

from data.view_migrations import ACTIVE_MIGRATIONS

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"
TWINS = "mcp_stats_games_twins_2026_11_21.sql"
VIEWS = "mcp_stats_views_2026_11_21.sql"
SERVER = ROOT / "supabase" / "functions" / "mcp" / "index.ts"


def _body(name: str) -> str:
    sql = (MIGRATIONS / name).read_text(encoding="utf-8")
    return "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))


def _games_def(body: str) -> str:
    start = body.index("CREATE OR REPLACE VIEW mcp_stats.games")
    return re.sub(r"\s+", " ", body[start:body.index(";", start)])


def _server() -> str:
    return SERVER.read_text(encoding="utf-8")


def _case(src: str, name: str) -> str:
    start = src.index(f'case "{name}"')
    nxt = src.find("\n    case ", start + 1)
    return src[start:nxt if nxt != -1 else len(src)]


def test_twins_migration_is_listed_after_the_views():
    assert TWINS in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(TWINS) > ACTIVE_MIGRATIONS.index(VIEWS)


def test_both_files_define_the_same_games_view():
    # A rerun of the base file on a fresh database must not try to drop
    # alias_ids (CREATE OR REPLACE VIEW cannot), and must not undo the merge.
    assert _games_def(_body(TWINS)) == _games_def(_body(VIEWS))


def test_games_view_collapses_ncaaf_twins_and_keeps_every_id():
    d = _games_def(_body(TWINS))
    assert "alias_ids" in d
    assert "PARTITION BY g.home_team, g.away_team" in d
    assert "t.rn = 1" in d
    # The kept row is the ET-dated one, and the slate date is the ET kickoff date.
    assert "America/New_York" in d
    assert "coalesce(t.et_date, t.game_date)" in d
    # Other sports pass straight through, so they keep the game_date index.
    assert "g.sport <> 'NCAAF'" in d


def test_twins_guard_is_the_property_not_the_text():
    body = _body(TWINS)
    guard = body[:body.index("CREATE OR REPLACE VIEW")]
    assert "mcp_stats.games twins v2" in guard
    assert "pg_get_viewdef" not in guard
    # The marker is written by the same block that builds the view.
    assert "COMMENT ON VIEW mcp_stats.games" in body.split("CREATE OR REPLACE VIEW", 1)[1]


def test_twins_are_keyed_on_the_et_date_not_the_kickoff_instant():
    # The live feed rewrites commence_time to the real kickoff (Boise State,
    # 2026-11-21: 02:30 -> 02:40 UTC), so an instant key re-splits the game.
    d = _games_def(_body(TWINS))
    window = d[d.index("WINDOW w AS"):]
    assert "AT TIME ZONE 'America/New_York', 'YYYY-MM-DD'" in window
    assert "::timestamptz::text" not in window


def test_slate_is_not_cut_at_the_generic_row_cap():
    case = _case(_server(), "get_slate")
    assert "MAX_ROWS}" not in case.replace("SLATE_MAX_ROWS", "")
    cap = int(re.search(r"const SLATE_MAX_ROWS = (\d+);", _server()).group(1))
    assert cap >= 100  # 71 NCAAB games is the biggest day since 2026-11-14
    assert "truncated" in case


def test_slate_says_which_games_have_lines():
    case = _case(_server(), "get_slate")
    assert "has_lines" in case
    assert "any(g.alias_ids)" in case


def test_game_lines_reads_prices_under_every_id_of_the_game():
    case = _case(_server(), "get_game_lines")
    assert "any(alias_ids)" in case
    assert "gp.game_id = any(gm.alias_ids)" in case
    assert "gp.game_id = ${g.id}" not in case
