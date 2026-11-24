"""AI assistant (MCP): game context -- injuries, public splits, rest, defense vs position.

Matt, 2026-11-22: "1 - all, 2 - yes we can use these stats". A member's
assistant (Grok) said Signal Base could not answer injuries, public betting
percentage, rest or positional matchups, searched the web instead, and listed
a player as questionable for a game his team was not in.

The migration runs on a scratch cluster through the worker's own apply path
(twice: the second pass is a no-op), and every view is read as mcp_reader,
the role the edge function reads as.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from data.view_migrations import ACTIVE_MIGRATIONS, _apply_one
from tests._pg import pg_bin, scratch_cluster

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "data" / "migrations"
NAME = "mcp_stats_context_2026_11_22.sql"
SERVER = ROOT / "supabase" / "functions" / "mcp" / "index.ts"

TABLES = """
CREATE ROLE mcp_reader NOLOGIN;
CREATE ROLE anon NOLOGIN;
CREATE ROLE authenticated NOLOGIN;
CREATE SCHEMA mcp_stats;
CREATE TABLE public.games (sport text, game_id text, game_date text, season int,
  home_team text, away_team text, home_score int, away_score int,
  commence_time text, first_pitch_at text, data_source text);
CREATE TABLE public.injury_status_current (sport text, team text, player_key text,
  player_name text, player_id text, status text, injury_type text, status_ts text, as_of timestamptz);
CREATE TABLE public.scoreboard_splits_history (id bigserial, game_id text, sport text,
  game_date text, market text, side text, bet_pct numeric, money_pct numeric,
  line_value numeric, odds int, source text, snapshot_at timestamptz);
CREATE TABLE public.player_positions (sport text, player_id text, player_name text,
  team text, position text, pos_group text, source text, source_athlete_id text,
  updated_at timestamptz, roster_seen_at timestamptz);
CREATE TABLE public.nba_player_game_log (player_id text, player_name text, team text,
  game_id text, game_date text, season int, minutes numeric, points int, rebounds int,
  assists int, steals int, blocks int, turnovers int, fg3_made int);
CREATE TABLE public.wnba_player_game_log (LIKE public.nba_player_game_log);
CREATE TABLE public.nfl_player_game_log (player_id text, player_name text, pos text,
  team text, opponent text, game_id text, game_date text, season int,
  completions int, attempts int, passing_yards numeric, passing_tds int,
  interceptions int, carries int, rushing_yards numeric, rushing_tds int,
  receptions int, targets int, receiving_yards numeric, receiving_tds int);

INSERT INTO public.games VALUES
  ('NBA', 'G1', '2026-11-20', 2026, 'ATL', 'MIL', 110, 100, '2026-11-21T00:30:00Z', NULL, NULL),
  ('NBA', 'G2', '2026-11-22', 2026, 'ATL', 'DET', NULL, NULL, '2026-11-22T23:00:00Z', NULL, NULL),
  ('NFL', 'N1', '2026-11-16', 2026, 'SF', 'DAL', 20, 17, '2026-11-16T21:25:00Z', NULL, NULL);
INSERT INTO public.injury_status_current VALUES
  ('NBA', 'ATL', 'k1', 'Trae Young', '1', 'Questionable', 'Ankle', '2026-11-22T18:00Z', now()),
  ('NBA', 'MIA', 'k2', 'Someone Else', '2', 'Out', 'out', '2026-11-22T18:00Z', now());
INSERT INTO public.scoreboard_splits_history
  (game_id, sport, game_date, market, side, bet_pct, money_pct, line_value, odds, source, snapshot_at) VALUES
  ('G2', 'NBA', '2026-11-22', 'spreads', 'away', 58, 57, -1.5, NULL, 'action_network', '2026-11-22T18:00Z'),
  ('G2', 'NBA', '2026-11-22', 'spreads', 'away', 90, 90, -1.5, NULL, 'action_network', '2026-11-22T23:30Z'),
  ('G2', 'NBA', '2026-11-22', 'totals', 'over', 70, 74, 223.5, -110, 'dk_network', '2026-11-22T19:00Z');
INSERT INTO public.player_positions (sport, player_id, player_name, team, pos_group) VALUES
  ('NBA', '1', 'Trae Young', 'ATL', 'G'), ('NBA', '3', 'Giannis', 'MIL', 'F');
INSERT INTO public.nba_player_game_log VALUES
  ('1', 'Trae Young', 'ATL', 'G1', '2026-11-20', 2026, 36, 30, 3, 11, 1, 0, 4, 5),
  ('3', 'Giannis', 'MIL', 'G1', '2026-11-20', 2026, 35, 28, 12, 6, 1, 2, 3, 0),
  ('9', 'No Position', 'MIL', 'G1', '2026-11-20', 2026, 10, 5, 1, 1, 0, 0, 0, 1);
INSERT INTO public.nfl_player_game_log VALUES
  ('a', 'A QB', 'QB', 'SF', 'DAL', 'N1', '2026-11-16', 2026, 20, 30, 250, 2, 0, 2, 5, 0, 0, 0, 0, 0),
  ('b', 'A FB', 'FB', 'SF', 'DAL', 'N1', '2026-11-16', 2026, 0, 0, 0, 0, 0, 3, 12, 1, 1, 1, 4, 0),
  ('c', 'A LB', 'LB', 'DAL', 'SF', 'N1', '2026-11-16', 2026, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0);
"""


def _psql(dsn: str, sql: str, role: str | None = None) -> tuple[bool, str]:
    body = (f"SET ROLE {role};\n" if role else "") + sql
    p = subprocess.run([pg_bin("psql"), dsn, "-v", "ON_ERROR_STOP=1", "-At", "-c", body],
                       capture_output=True, text=True)
    out = "\n".join(ln for ln in p.stdout.splitlines() if ln != "SET")
    return p.returncode == 0, (out + "\n" + p.stderr).strip()


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, q, params=None):
        cur = self.raw.cursor()
        cur.execute(q, params)
        return cur

    def commit(self):
        self.raw.commit()

    def rollback(self):
        self.raw.rollback()


def _apply(dsn: str) -> None:
    import psycopg2
    raw = psycopg2.connect(dsn)
    try:
        assert _apply_one(_Conn(raw), NAME, (MIGRATIONS / NAME).read_text(encoding="utf-8")) is None
    finally:
        raw.close()


@pytest.fixture(scope="module")
def dsn():
    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("mcp-context-") as d:
        ok, out = _psql(d, TABLES)
        assert ok, out
        _apply(d)
        _apply(d)  # second pass: the marker makes it a no-op
        yield d


def test_listed_after_the_multi_assistant_migration():
    i = ACTIVE_MIGRATIONS.index
    assert NAME in ACTIVE_MIGRATIONS
    assert i("mcp_stats_views_2026_11_21.sql") < i(NAME)
    assert i("mcp_multi_assistant_2026_11_22.sql") < i(NAME)


def test_file_shape():
    sql = (MIGRATIONS / NAME).read_text(encoding="utf-8")
    body = "\n".join(ln for ln in sql.splitlines() if not ln.strip().startswith("--"))
    assert body.strip().startswith("DO $context$") and body.strip().endswith("$context$;")
    # Guard through to_regclass: a ::regclass cast raises before the view exists.
    assert "obj_description(to_regclass('mcp_stats.injuries')" in body
    assert not re.search(r"GRANT[^;]*\b(anon|authenticated)\b", body)
    # The marker is written last, so a failure above leaves it missing and retries.
    assert body.rindex("mcp_stats context v1") > body.rindex("GRANT SELECT")


def test_injuries_read_by_the_reader(dsn):
    ok, out = _psql(dsn, "SELECT team, player_name, status, detail FROM mcp_stats.injuries "
                         "WHERE sport = 'NBA' AND team IN ('ATL', 'DET');", role="mcp_reader")
    assert ok, out
    assert out.splitlines() == ["ATL|Trae Young|Questionable|Ankle"]


def test_splits_are_pre_start_only_and_name_their_book(dsn):
    ok, out = _psql(dsn, "SELECT market, side, book, bet_pct FROM mcp_stats.public_splits "
                         "WHERE sport = 'NBA' AND game_id = 'G2' ORDER BY market, snapshot_at;",
                    role="mcp_reader")
    assert ok, out
    # The 23:30Z row is after the 23:00Z start: in-game money, not shown.
    assert out.splitlines() == ["spreads|away|Consensus|58", "totals|over|DraftKings|70"]


def test_position_games_carry_the_opponent_and_group(dsn):
    ok, out = _psql(dsn, "SELECT sport, team, opponent, pos_group, value FROM mcp_stats.position_games "
                         "WHERE stat IN ('points', 'rush_yds') ORDER BY sport, team;", role="mcp_reader")
    assert ok, out
    assert out.splitlines() == [
        "NBA|ATL|MIL|G|30",   # opponent from the game row, not the log
        "NBA|MIL|ATL|F|28",   # the player with no listed position is left out
        "NFL|SF|DAL|QB|5",
        "NFL|SF|DAL|RB|12",   # FB counts as RB; the LB is not a skill position
    ]


def test_the_reader_sees_views_not_tables(dsn):
    for table in ("injury_status_current", "scoreboard_splits_history", "nba_player_game_log"):
        ok, out = _psql(dsn, f"SELECT 1 FROM public.{table} LIMIT 1;", role="mcp_reader")
        assert not ok and "permission denied" in out, table
    for role in ("anon", "authenticated"):
        ok, out = _psql(dsn, "SELECT 1 FROM mcp_stats.injuries LIMIT 1;", role=role)
        assert not ok and "permission denied" in out, role


def _case(src: str, name: str) -> str:
    start = src.index(f'case "{name}": {{')
    nxt = src.find("\n    case ", start + 10)
    return src[start:nxt if nxt > 0 else src.index("throw new ToolError(\"invalid_input\");\n}", start)]


def test_server_lists_the_four_tools_on_the_read_path():
    src = SERVER.read_text(encoding="utf-8")
    for name in ("get_injuries", "get_rest", "get_public_splits", "get_defense_vs_position"):
        assert f'name: "{name}"' in src, name
        body = _case(src, name)
        # Same path as every tool: a sealed game id, the read-only role, no raw table.
        assert 'unseal(user, "g", a.game_id)' in body, name
        assert "gameFor(" in body, name
        assert "public." not in body, name
    # Every new tool reads only views the migration grants.
    assert "mcp_stats.injuries" in _case(src, "get_injuries")
    assert "mcp_stats.public_splits" in _case(src, "get_public_splits")
    assert "mcp_stats.position_games" in _case(src, "get_defense_vs_position")
    # Defense vs position looks only at games before this one.
    assert "game_date < ${game.game_date}" in _case(src, "get_defense_vs_position")
