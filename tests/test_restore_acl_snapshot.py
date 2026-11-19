"""ops.acl_snapshot restore: the diff is the grant, not a printed promise."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.restore_acl_from_snapshot import (  # noqa: E402
    default_statements,
    parse_acl,
    policy_statement,
    rel_statements,
)


def test_parse_acl_names_public_when_the_grantee_is_empty():
    got = parse_acl(["=r/postgres", "anon=arwd/postgres"])
    assert got["PUBLIC"] == {"r"}
    assert got["anon"] == {"a", "r", "w", "d"}


def test_a_live_grant_anon_lost_is_granted_back():
    lines = rel_statements(
        "public.games", "r",
        ["anon=r/postgres", "authenticated=r/postgres"],
        ["authenticated=r/postgres"],
    )
    assert lines == ["GRANT SELECT ON TABLE public.games TO \"anon\""]


def test_an_extra_live_privilege_is_revoked():
    lines = rel_statements(
        "public.games", "r",
        ["anon=r/postgres"],
        ["anon=arwd/postgres"],
    )
    assert lines == [
        "REVOKE DELETE, INSERT, UPDATE ON TABLE public.games FROM \"anon\""
    ]


def test_sequence_usage_uses_the_sequence_keyword():
    lines = rel_statements(
        "public.picks_pick_id_seq", "S",
        ["anon=rwU/postgres"],
        None,
    )
    assert lines == [
        "GRANT SELECT, UPDATE, USAGE ON SEQUENCE public.picks_pick_id_seq TO \"anon\""
    ]


def test_default_privileges_name_the_grantor():
    lines = default_statements(
        "postgres:f",
        ["=X/postgres"],
        None,
    )
    assert lines == [
        "ALTER DEFAULT PRIVILEGES FOR ROLE \"postgres\" IN SCHEMA public "
        "GRANT EXECUTE ON FUNCTIONS TO PUBLIC"
    ]


def test_policy_roles_become_an_alter():
    stmt = policy_statement(
        "public.games:anon read games", "{anon,authenticated}")
    assert stmt == (
        'ALTER POLICY "anon read games" ON public.games TO anon, authenticated'
    )


def test_a_null_snapshot_acl_keeps_the_owners_execute():
    """NULL proacl is the built-in default, not an empty grant list.

    Step B replaces that NULL with an explicit ACL. A restore that treats
    NULL as nobody must not REVOKE the owner's EXECUTE.
    """
    import psycopg2
    import pytest

    from scripts.restore_acl_from_snapshot import build_statements
    from tests._pg import pg_bin, scratch_cluster

    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("aclnull-") as dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            "CREATE FUNCTION public.f() RETURNS int LANGUAGE sql AS $$ SELECT 1 $$")
        cur.execute(
            "CREATE SCHEMA IF NOT EXISTS ops; "
            "CREATE TABLE ops.acl_snapshot ("
            " taken_at timestamptz NOT NULL DEFAULT now(),"
            " label text NOT NULL, kind text NOT NULL,"
            " object text NOT NULL, detail jsonb NOT NULL)")
        cur.execute(
            "INSERT INTO ops.acl_snapshot (label, kind, object, detail) "
            "VALUES ('pre', 'proacl', 'public.f()', "
            """ '{"acl": null, "owner": "postgres"}'::jsonb)""")
        cur.execute("REVOKE ALL ON FUNCTION public.f() FROM PUBLIC")
        cur.execute("GRANT EXECUTE ON FUNCTION public.f() TO postgres")
        conn.commit()
        lines = build_statements(cur, "pre")
        text = "\n".join(lines)
        conn.close()
    assert 'FROM "postgres"' not in text
    assert "GRANT EXECUTE ON FUNCTION public.f() TO PUBLIC" in text


def test_a_null_sequence_acl_keeps_select_and_update():
    """acldefault('S') is a foreign server (USAGE only). Sequences are 's'."""
    import psycopg2
    import pytest

    from scripts.restore_acl_from_snapshot import build_statements
    from tests._pg import pg_bin, scratch_cluster

    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("aclseq-") as dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute("CREATE ROLE anon NOLOGIN")
        cur.execute("CREATE SEQUENCE public.s")
        cur.execute(
            "CREATE SCHEMA IF NOT EXISTS ops; "
            "CREATE TABLE ops.acl_snapshot ("
            " taken_at timestamptz NOT NULL DEFAULT now(),"
            " label text NOT NULL, kind text NOT NULL,"
            " object text NOT NULL, detail jsonb NOT NULL)")
        cur.execute(
            "INSERT INTO ops.acl_snapshot (label, kind, object, detail) "
            "VALUES ('pre', 'relacl', 'public.s', '{\"acl\": null}'::jsonb)")
        cur.execute("REVOKE ALL ON SEQUENCE public.s FROM anon")
        conn.commit()
        lines = build_statements(cur, "pre")
        text = "\n".join(lines)
        conn.close()
    assert "REVOKE" not in text
    assert 'FROM "postgres"' not in text


def test_a_missing_defacl_row_is_an_empty_list():
    """No pg_default_acl row means nothing extra, not acldefault()."""
    import psycopg2
    import pytest

    from scripts.restore_acl_from_snapshot import build_statements
    from tests._pg import pg_bin, scratch_cluster

    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("acldef-") as dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            "CREATE SCHEMA IF NOT EXISTS ops; "
            "CREATE TABLE ops.acl_snapshot ("
            " taken_at timestamptz NOT NULL DEFAULT now(),"
            " label text NOT NULL, kind text NOT NULL,"
            " object text NOT NULL, detail jsonb NOT NULL)")
        cur.execute(
            "INSERT INTO ops.acl_snapshot (label, kind, object, detail) "
            "VALUES ('pre', 'defacl', 'postgres:r', "
            """ '{"acl": ["anon=r/postgres"]}'::jsonb)""")
        conn.commit()
        lines = build_statements(cur, "pre")
        text = "\n".join(lines)
        conn.close()
    assert 'GRANT SELECT ON TABLES TO "anon"' in text
    assert "REVOKE" not in text


def test_an_unlisted_global_function_default_is_granted_back_to_public():
    """A pre-step snapshot has no postgres:f:global row. Step B creates one.

    Restore must grant PUBLIC execute back. Undo B is not the only path.
    """
    import psycopg2
    import pytest

    from scripts.restore_acl_from_snapshot import build_statements
    from tests._pg import pg_bin, scratch_cluster

    if not pg_bin("psql"):
        pytest.skip("psql is not installed")
    with scratch_cluster("aclglob-") as dsn:
        conn = psycopg2.connect(dsn)
        cur = conn.cursor()
        cur.execute(
            "ALTER DEFAULT PRIVILEGES FOR ROLE postgres "
            "REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC")
        cur.execute(
            "CREATE SCHEMA IF NOT EXISTS ops; "
            "CREATE TABLE ops.acl_snapshot ("
            " taken_at timestamptz NOT NULL DEFAULT now(),"
            " label text NOT NULL, kind text NOT NULL,"
            " object text NOT NULL, detail jsonb NOT NULL)")
        cur.execute(
            "INSERT INTO ops.acl_snapshot (label, kind, object, detail) "
            "VALUES ('pre', 'defacl', 'postgres:r', "
            """ '{"acl": ["anon=r/postgres"]}'::jsonb)""")
        conn.commit()
        lines = build_statements(cur, "pre")
        text = "\n".join(lines)
        conn.close()
    assert "GRANT EXECUTE ON FUNCTIONS TO PUBLIC" in text
    assert "IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO PUBLIC" not in text


def test_dry_run_refuses_without_a_dsn():
    from scripts.restore_acl_from_snapshot import main
    assert main(["--label", "pre_step_a_20261118"]) == 2
