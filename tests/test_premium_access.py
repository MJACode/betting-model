"""premium_access job: grant / expire comped premium for one email.

Validation runs anywhere. The behaviour test runs the real SQL through the
worker's DBConnection wrapper on a scratch Postgres, with access_grants and
app_grant_access_for taken from the production migration file, and asks the
gate itself whether each user has access.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts import premium_access as pa

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "data/migrations/add_access_grants_2026_11_05.sql").read_text(encoding="utf-8")


def _ok(**over):
    args = {"action": "grant", "email": " Someone@Example.com ",
            "note": "comped by Matt 2026-11-26"}
    args.update(over)
    return args


def test_validate_normalises_email_and_action():
    out = pa.validate(_ok(action="GRANT"))
    assert out == {"action": "grant", "email": "someone@example.com",
                   "note": "comped by Matt 2026-11-26"}


@pytest.mark.parametrize("bad", [
    {"action": "delete"},
    {"action": ""},
    {"email": "not-an-email"},
    {"email": "a@b.com'; DROP TABLE x; --"},
    {"note": ""},
    {"note": "short"},
])
def test_validate_refuses(bad):
    with pytest.raises(ValueError):
        pa.validate(_ok(**bad))


def test_the_only_delete_is_one_login_by_id():
    sql = {k: v for k, v in vars(pa).items() if k.endswith("_SQL")}
    deleting = [k for k, v in sql.items()
                if re.search(r"\b(delete|truncate|drop)\b", v, re.I)]
    assert deleting == ["DELETE_LOGIN_SQL"]
    assert sql["DELETE_LOGIN_SQL"] == "DELETE FROM auth.users WHERE id = %s::uuid"


def test_delete_login_needs_a_different_replacement():
    with pytest.raises(ValueError):
        pa.validate(_ok(action="delete_login"))
    with pytest.raises(ValueError):
        pa.validate(_ok(action="delete_login", replaced_by="someone@example.com"))
    out = pa.validate(_ok(action="delete_login", replaced_by="New@Example.com"))
    assert out["replaced_by"] == "new@example.com"


def test_the_job_is_registered_and_declared_entries_validate():
    from tracking import job_queue as q
    assert "premium_access" in q.JOBS
    entries = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    mine = [e for e in entries if e["job_type"] == "premium_access"]
    assert mine
    for e in mine:
        q.JOBS["premium_access"][1](e["args"])


def _migration_part(start: str, end: str) -> str:
    i = MIGRATION.index(start)
    return MIGRATION[i:MIGRATION.index(end, i) + len(end)]


def test_grant_and_expire_on_a_scratch_cluster():
    psycopg2 = pytest.importorskip("psycopg2")
    from data.db import DBConnection
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    raw = None
    try:
        try:
            dsn = cluster.start()
        except Exception as exc:
            pytest.skip(f"scratch cluster did not start: {exc}")
        raw = psycopg2.connect(dsn)
        cur = raw.cursor()
        # The auth columns the insert writes, as GoTrue defines them.
        cur.execute("""
            CREATE SCHEMA auth;
            CREATE TABLE auth.users (
                instance_id uuid, id uuid PRIMARY KEY, aud varchar, role varchar,
                email varchar, encrypted_password varchar,
                email_confirmed_at timestamptz,
                confirmation_token varchar, recovery_token varchar,
                email_change_token_new varchar, email_change_token_current varchar,
                reauthentication_token varchar, email_change varchar,
                raw_app_meta_data jsonb, raw_user_meta_data jsonb,
                created_at timestamptz, updated_at timestamptz,
                is_sso_user boolean NOT NULL DEFAULT false,
                is_anonymous boolean NOT NULL DEFAULT false);
            CREATE TABLE auth.identities (
                provider_id text NOT NULL, user_id uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
                identity_data jsonb NOT NULL, provider text NOT NULL,
                last_sign_in_at timestamptz, created_at timestamptz, updated_at timestamptz,
                id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                UNIQUE (provider_id, provider));
            DO $$ BEGIN
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon NOLOGIN; END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
              IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='service_role') THEN CREATE ROLE service_role NOLOGIN; END IF;
            END $$;
        """)
        cur.execute(_migration_part("CREATE TABLE IF NOT EXISTS public.access_grants", ");"))
        cur.execute(_migration_part("CREATE OR REPLACE FUNCTION public.app_grant_access_for",
                                    "$$;"))
        raw.commit()
        conn = DBConnection(raw)

        def has_access(uid):
            return conn.execute("SELECT public.app_grant_access_for(%s::uuid)",
                                (uid,)).fetchone()[0]

        # grant: new login + grant, and the gate opens.
        g = pa.apply(conn, "grant", "new@example.com", "comped by Matt test")
        conn.commit()
        assert g["login_created"] and g["grants_changed"] == 1
        assert has_access(g["user_id"])
        ident = conn.execute("SELECT provider, user_id::text FROM auth.identities").fetchall()
        assert ident == [("email", g["user_id"])]
        nulls = conn.execute(
            "SELECT count(*) FROM auth.users WHERE email_change IS NULL "
            "OR confirmation_token IS NULL OR recovery_token IS NULL").fetchone()[0]
        assert nulls == 0

        # grant again: nothing changes.
        g2 = pa.apply(conn, "grant", "new@example.com", "comped by Matt test")
        conn.commit()
        assert g2["user_id"] == g["user_id"]
        assert not g2["login_created"] and g2["grants_changed"] == 0
        assert conn.execute("SELECT count(*) FROM auth.users").fetchone()[0] == 1

        # expire: gate closes, row kept.
        e = pa.apply(conn, "expire", "new@example.com", "expired by Matt test")
        conn.commit()
        assert e["grants_changed"] == 1 and not has_access(g["user_id"])
        assert conn.execute("SELECT count(*) FROM public.access_grants").fetchone()[0] == 1
        assert e["grants"][0]["notes"].endswith("| expired by Matt test")

        # expire again, and expire an unknown email: no-ops.
        assert pa.apply(conn, "expire", "new@example.com", "x" * 10)["grants_changed"] == 0
        unknown = pa.apply(conn, "expire", "nobody@example.com", "x" * 10)
        assert unknown["user_id"] is None and unknown["grants_changed"] == 0

        # grant after expiry: a fresh grant on the same login reopens it.
        g3 = pa.apply(conn, "grant", "new@example.com", "re-comped by Matt test")
        conn.commit()
        assert g3["user_id"] == g["user_id"] and g3["grants_changed"] == 1
        assert has_access(g["user_id"])

        # delete_login: refused while the replacement has no login with access.
        with pytest.raises(ValueError, match="has not been replaced"):
            pa.apply(conn, "delete_login", "new@example.com", "x" * 10,
                     replaced_by="repl@example.com")
        conn.rollback()
        r = pa.apply(conn, "grant", "repl@example.com", "comped by Matt test")
        conn.commit()
        # refused while the old login still has access.
        with pytest.raises(ValueError, match="still has app access"):
            pa.apply(conn, "delete_login", "new@example.com", "x" * 10,
                     replaced_by="repl@example.com")
        conn.rollback()
        pa.apply(conn, "expire", "new@example.com", "x" * 10)
        conn.commit()
        # refused while the old login owns member data.
        conn.execute("CREATE TABLE public.subscriptions (user_id uuid "
                     "REFERENCES auth.users(id) ON DELETE CASCADE)")
        conn.execute("INSERT INTO public.subscriptions VALUES (%s::uuid)", (g["user_id"],))
        conn.commit()
        with pytest.raises(ValueError, match="owns member data"):
            pa.apply(conn, "delete_login", "new@example.com", "x" * 10,
                     replaced_by="repl@example.com")
        conn.rollback()
        conn.execute("DROP TABLE public.subscriptions")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM auth.users").fetchone()[0] == 2

        # all checks pass: archived into the result, then deleted.
        d = pa.apply(conn, "delete_login", "new@example.com", "x" * 10,
                     replaced_by="repl@example.com")
        conn.commit()
        assert d["result"] == "deleted"
        assert d["archive"]["user"]["email"] == "new@example.com"
        assert "encrypted_password" not in d["archive"]["user"]
        assert len(d["archive"]["identities"]) == 1
        assert len(d["archive"]["access_grants"]) == 2
        emails = [x[0] for x in conn.execute("SELECT email FROM auth.users").fetchall()]
        assert emails == ["repl@example.com"]
        assert has_access(r["user_id"])
        again = pa.apply(conn, "delete_login", "new@example.com", "x" * 10,
                         replaced_by="repl@example.com")
        assert again["result"].startswith("no login")
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
