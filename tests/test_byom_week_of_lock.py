"""A BYOM bet locks on a game-week line only (Matt, 2026-11-26: "Game week
only").

DraftKings posts a season's lines in August. Before this, the official lock
was the first DraftKings quote that fit, so "Tets" held 20 open bets through
Jan 5 all locked 2026-08-31, and 23 of its 27 graded 2026 bets locked more
than 14 days early. Now only quotes from the 7 days before kickoff count: a
line already in force when game week opens locks at that moment.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from tests.test_byom_alerts import CHAIN, ROOT, STUBS

ALERTS_SQL = "byom_alerts_2026_11_25.sql"
WEEK_SQL = "byom_week_of_lock_2026_11_26.sql"
USER_A = "11111111-1111-1111-1111-111111111111"
MODEL = "aaaaaaaa-0000-0000-0000-000000000001"
FILTERS = '{"markets":["spreads"],"side":"home","role":"favorite"}'


def test_registered_after_the_alerts_file():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert ACTIVE_MIGRATIONS.index(WEEK_SQL) == ACTIVE_MIGRATIONS.index(ALERTS_SQL) + 1
    sql = (ROOT / "data/migrations" / WEEK_SQL).read_text(encoding="utf-8")
    assert "interval ''7 days''" in sql
    assert "DELETE FROM" not in sql.upper()


@pytest.fixture
def scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    raw = None
    try:
        dsn = cluster.start()
        raw = psycopg2.connect(dsn)
        raw.autocommit = True
        cur = raw.cursor()
        cur.execute("""
            CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
            CREATE SCHEMA auth;
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            CREATE TABLE device_push_tokens (
              token text, device_id text, user_id uuid, enabled boolean);
        """ + STUBS + f"INSERT INTO members VALUES ('{USER_A}');")
        for name in CHAIN:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute((ROOT / "data/migrations" / ALERTS_SQL).read_text(encoding="utf-8"))
        cur.execute(f"""
            INSERT INTO byom_models (model_id, user_id, name, sport, filters)
            VALUES ('{MODEL}', '{USER_A}', 'Home faves', 'NFL', '{FILTERS}');
            -- An alert written under the first-line rule, before the change.
            INSERT INTO byom_alerts (model_id, user_id, sport, season, canonical_key,
              market, leg_side, team, home_team, away_team, commence_time, point,
              price, label, locked_at)
            VALUES ('{MODEL}', '{USER_A}', 'NFL', 2026, '2026_13_DET_BUF', 'spreads',
              'home', 'BUF', 'BUF', 'DET', now() + interval '2 days', -1, -110,
              'BUF -1', now() - interval '60 days');
        """)
        week = (ROOT / "data/migrations" / WEEK_SQL).read_text(encoding="utf-8")
        cur.execute(week)
        cur.execute("SELECT 'public.byom_legs(integer, jsonb, text)'::regprocedure::oid")
        oid = cur.fetchone()[0]
        cur.execute(week)  # returns before any DDL
        cur.execute("SELECT 'public.byom_legs(integer, jsonb, text)'::regprocedure::oid")
        assert cur.fetchone()[0] == oid
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              game_date, commence_time, line_basis, home_score, away_score,
              dk_spread_home, dk_total, home_rest_days, away_rest_days,
              home_role, away_role, is_primetime,
              ats_home_result, ats_away_result, dk_spread_home_price, dk_spread_away_price)
            VALUES
              -- Played: posted in August at -1, moved to -3 three days out.
              ('2026_10_NYJ_KC', 'NFL', 2026, 10, 'NYJ', 'KC', '2026-11-08',
               '2026-11-08 18:00+00', 'DraftKings line at game start', 30, 10,
               -3, 44.5, 7, 7, 'favorite', 'underdog', false,
               'win', 'loss', -110, -110),
              -- Two days away: the August line is still in force.
              ('2026_13_DET_BUF', 'NFL', 2026, 13, 'DET', 'BUF',
               (now() + interval '2 days')::date, now() + interval '2 days',
               'DraftKings line at game start', NULL, NULL, -1, 47.5, 7, 7,
               'favorite', 'underdog', false, NULL, NULL, -110, -110),
              -- Twenty days away: game week has not opened.
              ('2026_16_MIA_NE', 'NFL', 2026, 16, 'MIA', 'NE',
               (now() + interval '20 days')::date, now() + interval '20 days',
               'DraftKings line at game start', NULL, NULL, -4, 44.5, 7, 7,
               'favorite', 'underdog', false, NULL, NULL, -110, -110);
            INSERT INTO byom_official_legs (
              canonical_key, sport, season, market, leg_side, player_key,
              match_role, leg_role, team, locked_at, point, price, result)
            VALUES
              ('2026_10_NYJ_KC', 'NFL', 2026, 'spreads', 'home', '', 'any', 'favorite',
               'KC', '2026-08-31 16:00+00', -1, -110, 'win'),
              ('2026_10_NYJ_KC', 'NFL', 2026, 'spreads', 'home', '', 'any', 'favorite',
               'KC', '2026-11-05 18:00+00', -3, -110, 'win'),
              ('2026_13_DET_BUF', 'NFL', 2026, 'spreads', 'home', '', 'any', 'favorite',
               'BUF', now() - interval '60 days', -1, -110, NULL),
              ('2026_16_MIA_NE', 'NFL', 2026, 'spreads', 'home', '', 'any', 'favorite',
               'NE', now() - interval '60 days', -4, -110, NULL);
        """)
        raw.autocommit = False
        from data.db import DBConnection
        yield psycopg2, raw, DBConnection(raw, url=dsn)
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def test_an_august_line_locks_when_game_week_opens(scratch):
    _pg, raw, _conn = scratch
    cur = raw.cursor()
    cur.execute("SELECT point, locked_at::text FROM byom_legs(2026, %s::jsonb, 'official') "
                "WHERE canonical_key = '2026_10_NYJ_KC'", (FILTERS,))
    # The -1 posted 2026-08-31 was still the line when game week opened
    # (2026-11-01 18:00 UTC), so the bet is -1, official at that moment.
    assert cur.fetchall() == [(-1, "2026-11-01 18:00:00+00")]


def test_open_bets_are_game_week_only_and_old_rows_are_kept_not_shown(scratch, monkeypatch):
    _pg, raw, conn = scratch
    cur = raw.cursor()
    cur.execute("SELECT canonical_key FROM byom_legs(2026, %s::jsonb, 'open')", (FILTERS,))
    # Two days away is open; twenty days away is not (game week is ahead).
    assert cur.fetchall() == [("2026_13_DET_BUF",)]

    from byom import alerts
    monkeypatch.setattr("tracking.push_notifier._expo_send", lambda m, conn=None: 0)
    report = alerts.run(conn, rebuild=False, today=datetime.now(timezone.utc))
    assert report["announced"]["alerts"] == 1
    cur.execute("SELECT lock_rule, label FROM byom_alerts ORDER BY lock_rule")
    # The first-line row is kept; the week-of bet is written beside it.
    assert cur.fetchall() == [("first_line", "BUF -1"), ("week_of", "BUF -1")]
    cur.execute("SET ROLE authenticated")
    cur.execute("SELECT set_config('byom.uid', %s, false)", (USER_A,))
    cur.execute("SELECT count(*), max(locked_at) > now() - interval '8 days' "
                "FROM byom_my_open_bets()")
    assert cur.fetchone() == (1, True)
    raw.rollback()
