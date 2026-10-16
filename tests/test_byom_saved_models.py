"""Saved BYOM models stay unapplied until sign-in exists.

The migration is not in ACTIVE_MIGRATIONS. The grant sweep does not name
the tables or the RPCs. Scratch Postgres is local.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from byom.season import current_nfl_season

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_saved_models_2026_10_16.sql"
USER_A = "11111111-1111-1111-1111-111111111111"
USER_B = "22222222-2222-2222-2222-222222222222"
USER_C = "33333333-3333-3333-3333-333333333333"


def test_the_migration_is_not_registered_and_not_anon_granted():
    from data.anon_readable import (
        ANON_READABLE,
        ANON_WRITABLE,
        AUTHENTICATED_ONLY,
        RPC_AFTER_SIGN_IN,
        RPC_ANON_CALLABLE,
        RPC_REVOKE,
        WORKER_ONLY_TABLES,
    )
    from data.view_migrations import ACTIVE_MIGRATIONS
    from scripts.apply_anon_grants import MAY_BE_UNAPPLIED

    assert SQL_NAME not in ACTIVE_MIGRATIONS
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "SECURITY DEFINER" in sql
    assert "byom_saved_models_v1" in sql
    assert "auth.uid()" in sql
    assert "byom model cap is 25" in sql
    assert "filter keys must be lowercase" in sql
    assert sql.count("FROM byom_backtest") == 1
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    lowered = sql.lower()
    for banned in ("insert into picks", "discord"):
        assert banned not in lowered, banned
    for table in ("byom_models", "byom_model_snapshots"):
        assert table not in ANON_READABLE
        assert table not in AUTHENTICATED_ONLY
        assert table not in ANON_WRITABLE
        assert table not in WORKER_ONLY_TABLES
        assert table not in MAY_BE_UNAPPLIED
    assert RPC_AFTER_SIGN_IN == (
        "byom_save_model", "byom_list_models", "byom_delete_model")
    assert not (set(RPC_AFTER_SIGN_IN) & set(RPC_ANON_CALLABLE))
    assert not (set(RPC_AFTER_SIGN_IN) & set(RPC_REVOKE))
    sweep = (ROOT / "scripts/apply_anon_grants.py").read_text(encoding="utf-8")
    assert "RPC_AFTER_SIGN_IN" not in sweep
    auth = (ROOT / "mobile/src/lib/authConfig.ts").read_text(encoding="utf-8")
    assert "?? 'false'" in auth


def test_scratch_save_is_per_user_capped_and_snapshots_the_backtest():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    raw = None
    try:
        raw = psycopg2.connect(cluster.start())
        raw.autocommit = True
        cur = raw.cursor()
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
        cur.execute("""
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
        """)
        for name in ("byom_facts_schema_2026_10_16.sql",
                     "byom_game_facts_units_2026_10_16.sql",
                     "byom_prop_facts_units_2026_10_16.sql",
                     "byom_backtest_rpc_2026_10_16.sql",
                     SQL_NAME):
            text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
            cur.execute(text)
            cur.execute(text)
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              lock_window_hours, near_window_hours, line_source,
              ats_home_result, ats_home_units_uncapped, ats_home_units_capped,
              ats_away_result, ats_away_units_uncapped, ats_away_units_capped,
              home_role, away_role)
            VALUES
              ('2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC', 120, 24, 'test',
               'win', 1, 1, 'loss', -1.1, -1.1,
               'favorite', 'underdog')
        """)

        def as_user(uid):
            cur.execute("SELECT set_config('byom.uid', %s, false)", (uid,))

        as_user(USER_A)
        with pytest.raises(psycopg2.errors.RaiseException, match="not accepted"):
            cur.execute("""
                SELECT model_id FROM byom_save_model(
                  'home fav',
                  '{"role":"favorite","side":"home","minOdds":-200}'::jsonb,
                  2026)
            """)
        with pytest.raises(psycopg2.errors.RaiseException, match="lowercase"):
            cur.execute("""
                SELECT model_id FROM byom_save_model(
                  'home fav',
                  '{"Side":"home","role":"favorite"}'::jsonb,
                  2026)
            """)

        cur.execute("""
            SELECT model_id, season, bets, units_uncapped, units_capped
              FROM byom_save_model(
                'home fav',
                '{"role":"favorite","side":"home"}'::jsonb,
                2026)
        """)
        model_id, season, bets, unc, cap = cur.fetchone()
        assert season == 2026
        assert bets == 1
        assert Decimal(str(unc)) == Decimal("1")
        assert Decimal(str(cap)) == Decimal("1")
        cur.execute("""
            SELECT bets,
                   (SELECT coalesce(sum((row->>'bets')::bigint), 0)
                      FROM jsonb_array_elements(summary) AS row)
              FROM byom_model_snapshots
             WHERE model_id = %s
        """, (model_id,))
        snap_bets, summary_bets = cur.fetchone()
        assert snap_bets == summary_bets == 1
        cur.execute("""
            SELECT season FROM byom_save_model('home fav', '{}'::jsonb, NULL)
        """)
        assert cur.fetchone()[0] == current_nfl_season()
        cur.execute("""
            SELECT jsonb_array_length(snapshots)
              FROM byom_list_models()
        """)
        listed = cur.fetchall()
        assert len(listed) == 1
        assert listed[0][0] == 2

        as_user(USER_B)
        cur.execute("SELECT count(*) FROM byom_list_models()")
        assert cur.fetchone()[0] == 0
        with pytest.raises(psycopg2.errors.RaiseException, match="model not found"):
            cur.execute("SELECT byom_delete_model(%s)", (model_id,))

        as_user(USER_C)
        for i in range(25):
            cur.execute(
                "SELECT model_id FROM byom_save_model(%s, '{}'::jsonb, 2026)",
                (f"model {i}",))
            cur.fetchone()
        with pytest.raises(psycopg2.errors.RaiseException, match="cap is 25"):
            cur.execute(
                "SELECT model_id FROM byom_save_model('one more', '{}'::jsonb, 2026)")
        cur.execute("SELECT count(*) FROM byom_list_models()")
        assert cur.fetchone()[0] == 25

        as_user(USER_B)
        cur.execute("SELECT model_id FROM byom_save_model('b only', '{}'::jsonb, 2026)")
        cur.fetchone()

        cur.execute("SET ROLE anon")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("SELECT * FROM byom_save_model('nope', '{}'::jsonb, 2026)")
        cur.execute("RESET ROLE")

        cur.execute("SET ROLE authenticated")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM byom_models")
        cur.execute("RESET ROLE")

        cur.execute("GRANT SELECT ON byom_models TO authenticated")
        as_user(USER_A)
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT count(*) FROM byom_models")
        assert cur.fetchone()[0] == 1
        cur.execute("RESET ROLE")
        as_user(USER_C)
        cur.execute("SET ROLE authenticated")
        cur.execute("SELECT count(*) FROM byom_models")
        assert cur.fetchone()[0] == 25
        cur.execute("RESET ROLE")

        as_user(USER_A)
        cur.execute("SELECT byom_delete_model(%s)", (model_id,))
        assert str(cur.fetchone()[0]) == str(model_id)
        cur.execute(
            "SELECT count(*) FROM byom_models WHERE model_id = %s", (model_id,))
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT count(*) FROM byom_model_snapshots WHERE model_id = %s",
            (model_id,))
        assert cur.fetchone()[0] == 0

        as_user("")
        with pytest.raises(psycopg2.errors.RaiseException, match="sign-in required"):
            cur.execute("SELECT * FROM byom_list_models()")
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
