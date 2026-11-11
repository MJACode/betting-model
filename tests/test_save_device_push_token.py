"""Push-token save. The app's upsert 403s; the definer function is the write.

The migration is NOT in ACTIVE_MIGRATIONS. The worker must not apply it.
These tests read the file and, when initdb is installed, reproduce the RLS
refusal on a scratch cluster and show the function writes without letting
anon read the table.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "save_device_push_token_2026_11_11.sql"
SQL = MIG.read_text(encoding="utf-8")

TOKEN = "ExponentPushToken[probe-token-value]"
OTHER = "ExponentPushToken[second-token-val]"
DEVICE = "11111111-aaaa-4aaa-8aaa-111111111111"
SEEN = "2026-11-11T00:00:00Z"


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_migration_is_hand_applied_and_returns_nothing():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name not in ACTIVE_MIGRATIONS
    code = _code(SQL)
    assert code.count("$mig$") == 2
    assert code.count("$fn$") == 2
    assert "SECURITY DEFINER" in code
    assert "SET search_path = public, pg_temp" in code
    assert "RETURNS void" in code
    assert "ON CONFLICT (token) DO UPDATE" in code
    assert "CREATE POLICY" not in code.upper()
    assert "FOR SELECT" not in code.upper()
    assert "REVOKE ALL ON FUNCTION public.save_device_push_token" in code
    assert "FROM PUBLIC, anon, authenticated" in code
    assert (
        "GRANT EXECUTE ON FUNCTION public.save_device_push_token"
        "(text, text, text, boolean, text)"
    ) in code
    assert "TO anon, authenticated" in code


def test_direct_upsert_is_refused_and_the_function_is_not_a_read():
    psycopg2 = pytest.importorskip("psycopg2")

    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    conn = None
    try:
        try:
            dsn = cluster.start()
        except Exception as exc:
            pytest.skip(f"scratch cluster did not start: {exc}")
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
            END $$;
            GRANT USAGE ON SCHEMA public TO anon, authenticated;
            CREATE TABLE public.device_push_tokens (
                token text PRIMARY KEY,
                platform text,
                device_id text,
                enabled boolean DEFAULT true,
                last_seen text
            );
            ALTER TABLE public.device_push_tokens ENABLE ROW LEVEL SECURITY;
            CREATE POLICY "anon insert device token" ON public.device_push_tokens
                FOR INSERT TO anon, authenticated WITH CHECK (true);
            CREATE POLICY "anon update device token" ON public.device_push_tokens
                FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);
            GRANT SELECT, INSERT, UPDATE ON public.device_push_tokens
                TO anon, authenticated;
        """)

        cur.execute("SET ROLE anon")
        cur.execute(
            "INSERT INTO public.device_push_tokens "
            "(token, platform, device_id, enabled, last_seen) "
            "VALUES (%s, 'ios', %s, true, %s)",
            (TOKEN, DEVICE, SEEN),
        )
        with pytest.raises(psycopg2.Error) as conflict:
            cur.execute(
                "INSERT INTO public.device_push_tokens "
                "(token, platform, device_id, enabled, last_seen) "
                "VALUES (%s, 'ios', %s, true, %s) "
                "ON CONFLICT (token) DO UPDATE SET last_seen = EXCLUDED.last_seen",
                (TOKEN, DEVICE, SEEN),
            )
        assert conflict.value.pgcode == "42501"
        assert "row-level security" in conflict.value.pgerror
        with pytest.raises(psycopg2.Error) as missing:
            cur.execute(
                "INSERT INTO public.device_push_tokens "
                "(token, platform, device_id, enabled, last_seen) "
                "VALUES (%s, 'ios', %s, true, %s) "
                "ON CONFLICT (token) DO UPDATE SET last_seen = EXCLUDED.last_seen",
                (OTHER, DEVICE, SEEN),
            )
        assert missing.value.pgcode == "42501"
        cur.execute(
            "UPDATE public.device_push_tokens SET enabled = false WHERE token = %s",
            (TOKEN,),
        )
        assert cur.rowcount == 0
        cur.execute("RESET ROLE")

        cur.execute(SQL)
        cur.execute(SQL)

        cur.execute("SET ROLE anon")
        with pytest.raises(psycopg2.Error) as still:
            cur.execute(
                "INSERT INTO public.device_push_tokens "
                "(token, platform, device_id, enabled, last_seen) "
                "VALUES (%s, 'ios', %s, true, %s) "
                "ON CONFLICT (token) DO UPDATE SET enabled = EXCLUDED.enabled",
                (OTHER, DEVICE, SEEN),
            )
        assert still.value.pgcode == "42501"

        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'ios', true, %s)",
            (OTHER, DEVICE, SEEN),
        )
        cur.execute(
            "SELECT public.save_device_push_token(%s, NULL, NULL, false, %s)",
            (OTHER, "2026-11-11T01:00:00Z"),
        )
        cur.execute("SELECT count(*) FROM public.device_push_tokens")
        assert cur.fetchone()[0] == 0
        with pytest.raises(psycopg2.Error) as bad:
            cur.execute(
                "SELECT public.save_device_push_token(%s, %s, 'ios', true, %s)",
                ("short", DEVICE, SEEN),
            )
        assert bad.value.pgcode == "22023"
        cur.execute("RESET ROLE")

        cur.execute("SET ROLE authenticated")
        cur.execute(
            "SELECT public.save_device_push_token(%s, %s, 'android', true, %s)",
            (TOKEN, DEVICE, "2026-11-11T02:00:00Z"),
        )
        cur.execute("RESET ROLE")

        cur.execute(
            "SELECT token, device_id, platform, enabled, last_seen "
            "FROM public.device_push_tokens ORDER BY token"
        )
        assert cur.fetchall() == [
            (TOKEN, DEVICE, "android", True, "2026-11-11T02:00:00Z"),
            (OTHER, DEVICE, "ios", False, "2026-11-11T01:00:00Z"),
        ]
        cur.execute(
            "SELECT prosecdef, proconfig FROM pg_proc "
            "WHERE proname = 'save_device_push_token'"
        )
        secdef, config = cur.fetchone()
        assert secdef is True
        assert config is not None and any(
            item == "search_path=public, pg_temp" for item in config
        )
        sig = "public.save_device_push_token(text, text, text, boolean, text)"
        cur.execute("SELECT has_function_privilege('anon', %s, 'EXECUTE')", (sig,))
        assert cur.fetchone()[0] is True
        cur.execute(
            "SELECT has_function_privilege('authenticated', %s, 'EXECUTE')", (sig,)
        )
        assert cur.fetchone()[0] is True
        cur.execute("SELECT has_function_privilege('public', %s, 'EXECUTE')", (sig,))
        assert cur.fetchone()[0] is False
    finally:
        if conn is not None:
            conn.close()
        cluster.stop()
