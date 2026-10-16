"""NHL Stats-tab reads: one worker migration, anon grants, no record rewrite.

The views are ahead of the screen. mobile/src does not query them yet, so
they sit on AHEAD_OF_THE_APP in tests/test_anon_readable.py rather than
being left as an unexplained grant. The migration is not applied from a
development session; ACTIVE_MIGRATIONS is what runs it, after the CLV stamp,
and the file does not mention the published-record views.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "add_nhl_stats_views_2026_10_16.sql"
NAME = MIG.name


def _sql() -> str:
    return MIG.read_text(encoding="utf-8")


def test_the_migration_is_one_statement_and_returns_once_applied():
    text = _sql()
    assert text.count("DO $mig$") == 1
    assert text.strip().endswith(";")
    assert "RAISE NOTICE 'nhl stats views already present" in text
    assert "RETURN;" in text
    assert "SET LOCAL lock_timeout = '10s'" in text
    assert "hits statement_timeout" in text
    assert "v_public_track_record" not in text
    for name in (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
        "player_stat_values_nhl",
        "anon read nhl_skater_game_log",
        "anon read nhl_goalie_game_log",
        "anon read nhl_team_game_log",
    ):
        assert name in text, name
    assert "security_invoker = on" in text
    assert "game_type = 2" in text
    assert "FORCE ROW LEVEL SECURITY" not in text.upper()


def test_the_stat_list_is_the_board_and_the_arrays_are_windows():
    text = _sql()
    for stat in ("points", "goals", "assists", "shots", "hits", "blocks", "pp_points", "toi"):
        assert f"WHEN '{stat}'" in text, stat
    for stat in ("saves", "save_pct", "gaa"):
        assert f"WHEN '{stat}'" in text, stat
    assert 'FILTER (WHERE r.val IS NOT NULL)' in text
    assert "p_window IS NULL OR (p_window > 0 AND r.rn <= p_window)" in text
    assert "WHERE raw.val IS NOT NULL" in text
    assert "3600.0" in text
    assert "/ 60.0" in text


def test_the_prop_quote_is_pre_game_and_refuses_an_ambiguous_player():
    text = _sql()
    assert "sport = 'NHL'" in text
    assert "snapshot_type <> 'in_play'" in text
    assert "snapshot_at::timestamptz <= g.commence_time::timestamptz" in text
    assert "WHEN ids.n = 1 THEN ids.player_id ELSE NULL" in text


def test_it_is_registered_after_the_clv_stamp_and_declared_for_anon():
    from data.anon_readable import (
        ANON_READABLE,
        RPC_ANON_CALLABLE,
        VIEW_BASE_TABLES,
    )
    from data.view_migrations import ACTIVE_MIGRATIONS
    from tests.test_anon_readable import AHEAD_OF_THE_APP

    clv = "clv_standard_v2_2026_10_14.sql"
    assert ACTIVE_MIGRATIONS[-1] == NAME
    assert ACTIVE_MIGRATIONS.index(clv) < ACTIVE_MIGRATIONS.index(NAME)
    for view in (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
    ):
        assert view in ANON_READABLE
        assert view in AHEAD_OF_THE_APP
    for table in ("nhl_skater_game_log", "nhl_goalie_game_log", "nhl_team_game_log"):
        assert table in VIEW_BASE_TABLES
        assert table not in ANON_READABLE
    assert "player_stat_values_nhl" in RPC_ANON_CALLABLE


def test_no_scorer_or_card_reads_the_new_names():
    """A stats view that a scorer started reading would be a BET path."""
    needles = (
        "v_player_season_totals_nhl",
        "v_team_season_totals_nhl",
        "v_nhl_player_prop_odds",
        "player_stat_values_nhl",
    )
    roots = [ROOT / "models", ROOT / "scripts", ROOT / "tracking", ROOT / "nfl"]
    for root in roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for needle in needles:
                assert needle not in text, f"{path} reads {needle}"


def _pg_bin(name: str) -> str | None:
    import shutil
    found = shutil.which(name)
    if found:
        return found
    path = Path(f"/usr/lib/postgresql/16/bin/{name}")
    return str(path) if path.is_file() else None


def test_the_views_run_as_anon_on_a_scratch_database_and_windows_skip_nulls():
    """The DDL, the anon role, and the L5 window. Same shape as the scratch
    cluster in tests/test_discord_void_notice.py. Skips only when Postgres
    cannot be started."""
    import os
    import shutil
    import socket
    import subprocess
    import tempfile

    psycopg2 = pytest.importorskip("psycopg2")

    dsn = os.environ.get("LATEST_LINE_TEST_DSN")
    owned = None
    if not dsn:
        initdb = _pg_bin("initdb")
        pg_ctl = _pg_bin("pg_ctl")
        if not initdb or not pg_ctl:
            pytest.skip("LATEST_LINE_TEST_DSN not set and initdb is missing")
        owned = tempfile.mkdtemp(prefix="nhl-stats-pg-")
        subprocess.run(
            [initdb, "-D", owned, "-A", "trust", "--username", "postgres"],
            check=True, capture_output=True, text=True)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()
        subprocess.run(
            [pg_ctl, "-D", owned, "-o", f"-p {port} -k {owned}",
             "-l", str(Path(owned) / "log"), "-w", "start"],
            check=True, capture_output=True, text=True)
        dsn = f"host={owned} port={port} dbname=postgres user=postgres"

    conn = None
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("""
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                CREATE ROLE anon NOLOGIN;
              END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                CREATE ROLE authenticated NOLOGIN;
              END IF;
            END $$
        """)
        cur.execute("DROP SCHEMA IF EXISTS public CASCADE")
        cur.execute("CREATE SCHEMA public")
        cur.execute("GRANT USAGE ON SCHEMA public TO anon, authenticated")
        cur.execute("""
            CREATE TABLE public.games (
              game_id text PRIMARY KEY,
              sport text, game_date text, season integer,
              home_team text, away_team text, commence_time text
            );
            CREATE TABLE public.player_prop_odds (
              game_id text, game_date text, market text, player_name text,
              bookmaker text, line numeric, over_price integer, under_price integer,
              snapshot_at text, snapshot_type text
            );
            CREATE TABLE public.nhl_skater_game_log (
              nhl_game_id bigint, player_id bigint, player_name text, position text,
              game_id text, season integer, game_type integer, game_date text,
              team text, opponent text, is_home integer,
              goals integer, assists integer, points integer, shots integer,
              hits integer, blocked_shots integer, pp_points integer, toi_seconds integer
            );
            CREATE TABLE public.nhl_goalie_game_log (
              nhl_game_id bigint, player_id bigint, player_name text,
              game_id text, season integer, game_type integer, game_date text,
              team text, opponent text, is_home integer, started integer,
              saves integer, shots_against integer, goals_against integer, toi_seconds integer
            );
            CREATE TABLE public.nhl_team_game_log (
              nhl_game_id bigint, team text, game_id text, season integer,
              game_type integer, game_date text, opponent text, is_home integer,
              goals_for integer, goals_against integer, shots_for integer, shots_against integer,
              hits integer, blocked_shots integer, pp_goals integer, pp_opportunities integer,
              pp_goals_against integer, times_shorthanded integer,
              sat_for_5v5 integer, sat_against_5v5 integer, faceoff_win_pct numeric
            );
        """)
        for table in ("nhl_skater_game_log", "nhl_goalie_game_log", "nhl_team_game_log",
                      "games", "player_prop_odds"):
            cur.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY")
        cur.execute("""
            CREATE POLICY "anon read games" ON public.games FOR SELECT TO anon, authenticated USING (true);
            CREATE POLICY "anon read player_prop_odds" ON public.player_prop_odds
              FOR SELECT TO anon, authenticated USING (true);
            GRANT SELECT ON public.games, public.player_prop_odds TO anon, authenticated
        """)
        sql = _sql()
        cur.execute(sql)
        cur.execute(sql)

        cur.execute("""
            INSERT INTO public.nhl_skater_game_log
              (nhl_game_id, player_id, player_name, position, game_id, season, game_type,
               game_date, team, opponent, is_home, shots)
            VALUES
              (1, 10, 'Cale Makar', 'D', 'g1', 2027, 2, '2026-10-01', 'COL', 'PIT', 1, 1),
              (2, 10, 'Cale Makar', 'D', 'g2', 2027, 2, '2026-10-02', 'COL', 'PIT', 1, 2),
              (3, 10, 'Cale Makar', 'D', 'g3', 2027, 2, '2026-10-03', 'COL', 'PIT', 1, 3),
              (4, 10, 'Cale Makar', 'D', 'g4', 2027, 2, '2026-10-04', 'COL', 'PIT', 1, 4),
              (5, 10, 'Cale Makar', 'D', 'g5', 2027, 2, '2026-10-05', 'COL', 'PIT', 1, 5),
              (6, 10, 'Cale Makar', 'D', 'g6', 2027, 2, '2026-10-06', 'COL', 'PIT', 1, NULL),
              (7, 10, 'Cale Makar', 'D', 'g7', 2027, 2, '2026-10-07', 'COL', 'PIT', 1, 6),
              (8, 11, 'Twin Player', 'C', 'g7', 2027, 2, '2026-10-07', 'COL', 'PIT', 1, 1),
              (9, 12, 'Twin Player', 'C', 'g8', 2027, 2, '2026-10-08', 'COL', 'PIT', 1, 1)
        """)
        cur.execute("""
            INSERT INTO public.nhl_goalie_game_log
              (nhl_game_id, player_id, player_name, game_id, season, game_type, game_date,
               team, opponent, is_home, started, saves, shots_against, goals_against, toi_seconds)
            VALUES
              (1, 99, 'Alexandar Georgiev', 'g1', 2027, 2, '2026-10-01', 'COL', 'PIT', 1, 1, 30, 33, 3, 3600),
              (2, 99, 'Alexandar Georgiev', 'g2', 2027, 2, '2026-10-02', 'COL', 'PIT', 1, 0, NULL, 0, NULL, 0)
        """)
        cur.execute("""
            INSERT INTO public.nhl_team_game_log
              (nhl_game_id, team, game_id, season, game_type, game_date, opponent, is_home, goals_for)
            VALUES (1, 'COL', 'g1', 2027, 2, '2026-10-01', 'PIT', 1, 4)
        """)
        cur.execute("""
            INSERT INTO public.games
              (game_id, sport, game_date, season, home_team, away_team, commence_time)
            VALUES
              ('NHL_2026-10-16_PIT_COL', 'NHL', '2026-10-16', 2027, 'COL', 'PIT', '2026-10-17T01:10:00+00:00')
        """)
        cur.execute("""
            INSERT INTO public.player_prop_odds
              (game_id, game_date, market, player_name, bookmaker, line, over_price, under_price,
               snapshot_at, snapshot_type)
            VALUES
              ('NHL_2026-10-16_PIT_COL', '2026-10-16', 'player_shots_on_goal', 'Cale Makar',
               'hardrockbet', 2.5, -165, 120, '2026-10-16T04:18:19+00:00', 'open'),
              ('NHL_2026-10-16_PIT_COL', '2026-10-16', 'player_shots_on_goal', 'Cale Makar',
               'hardrockbet', 2.5, -200, 150, '2026-10-17T02:00:00+00:00', 'open'),
              ('NHL_2026-10-16_PIT_COL', '2026-10-16', 'player_shots_on_goal', 'Twin Player',
               'hardrockbet', 1.5, -110, -110, '2026-10-16T04:18:19+00:00', 'open')
        """)

        def as_anon(query, params=None):
            cur.execute("SET ROLE anon")
            try:
                cur.execute(query, params)
                return cur.fetchall()
            finally:
                cur.execute("RESET ROLE")

        totals = as_anon(
            "SELECT shots, games_played FROM public.v_player_season_totals_nhl "
            "WHERE player_id = '10' AND kind = 'skater'")
        assert totals == [(21, 7)]
        last5 = as_anon(
            "SELECT \"values\"::float8[] FROM public.player_stat_values_nhl(%s, %s, %s, %s) "
            "WHERE player_id = '10'",
            (2027, "skater", "shots", 5))
        assert last5 == [([6.0, 5.0, 4.0, 3.0, 2.0],)]
        last10 = as_anon(
            "SELECT \"values\"::float8[] FROM public.player_stat_values_nhl(%s, %s, %s, %s) "
            "WHERE player_id = '10'",
            (2027, "skater", "shots", 10))
        assert last10 == [([6.0, 5.0, 4.0, 3.0, 2.0, 1.0],)]
        goalie = as_anon(
            "SELECT saves::float8, round(save_pct, 4)::float8, round(gaa, 2)::float8 "
            "FROM public.v_player_season_totals_nhl WHERE player_id = '99'")
        assert goalie == [(30.0, round(30 / 33, 4), 3.0)]
        gaa_window = as_anon(
            "SELECT \"values\"::float8[] FROM public.player_stat_values_nhl(%s, %s, %s, %s)",
            (2027, "goalie", "gaa", 5))
        assert gaa_window == [([3.0],)]
        team = as_anon(
            "SELECT goals_for FROM public.v_team_season_totals_nhl WHERE team = 'COL'")
        assert team == [(4,)]
        quote = as_anon(
            "SELECT player_id, line::float8, under_price FROM public.v_nhl_player_prop_odds "
            "WHERE game_id = %s AND player_name = 'Cale Makar'",
            ("NHL_2026-10-16_PIT_COL",))
        assert quote == [("10", 2.5, 120)]
        twin = as_anon(
            "SELECT player_id FROM public.v_nhl_player_prop_odds "
            "WHERE game_id = %s AND player_name = 'Twin Player'",
            ("NHL_2026-10-16_PIT_COL",))
        assert twin == [(None,)]
    finally:
        if conn is not None:
            conn.close()
        if owned is not None:
            subprocess.run(
                [_pg_bin("pg_ctl"), "-D", owned, "-w", "-m", "immediate", "stop"],
                check=False, capture_output=True, text=True)
            shutil.rmtree(owned, ignore_errors=True)
