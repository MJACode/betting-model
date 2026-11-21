"""site_public_record is security_invoker, and anon still reads it.

The hand file created the view with security_invoker off. Supabase's
security_definer_view lint flags that. The rows come from
site_public_record_rows(), a SECURITY DEFINER function, so the view can
run as the caller without sending anon through v_public_track_record.

The skip is reloptions plus the view text. It does not look at anon
grants, so a pass after step A does not run the DDL again.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MIG = ROOT / "data" / "migrations" / "site_public_record_invoker_2026_11_21.sql"
SQL = MIG.read_text(encoding="utf-8")

_INVOKER = (
    "security_invoker=1",
    "security_invoker=true",
    "security_invoker=yes",
    "security_invoker=on",
)

_COLUMNS = (
    "sport", "picks", "wins", "losses", "pushes",
    "units", "risked", "first_date", "last_date", "refreshed_at",
)

# Production, 2026-11-21, in order. format_type prints timestamptz as
# "timestamp with time zone" and numeric(12,2) with the typmod.
_PROD_TYPES = (
    ("sport", "text"),
    ("picks", "integer"),
    ("wins", "integer"),
    ("losses", "integer"),
    ("pushes", "integer"),
    ("units", "numeric(12,2)"),
    ("risked", "numeric(12,2)"),
    ("first_date", "date"),
    ("last_date", "date"),
    ("refreshed_at", "timestamp with time zone"),
)

# The function cannot store a numeric typmod. Postgres prints the return
# type without (12,2). The view casts those two columns.
_FN_RESULT = (
    "TABLE(sport text, picks integer, wins integer, losses integer, "
    "pushes integer, units numeric, risked numeric, first_date date, "
    "last_date date)"
)

def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_worker_applies_it_and_the_posted_stake_pair_stays_last():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert "site_public_record_2026_11.sql" not in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS.index(MIG.name) < len(ACTIVE_MIGRATIONS) - 1


def test_it_is_one_statement_and_the_skip_is_not_an_anon_grant():
    code = _code(SQL).strip()
    assert code.startswith("DO $mig$")
    assert code.endswith("$mig$;")
    assert code.count("$mig$") == 2
    assert code.count("$ddl$") == 2
    head, body = code.split("CREATE OR REPLACE VIEW", 1)
    assert "RETURN;" in head
    assert "security_invoker=true" in head
    assert "security_invoker=on" in head
    assert "site_public_record_rows" in head
    assert "refreshed_at" in head
    assert "reloptions" in head
    assert "has_table_privilege" not in head
    assert "TO anon, authenticated" not in code
    assert "WITH (security_invoker = true, security_barrier = true)" in body
    for col in _COLUMNS:
        assert col in body
    # Anon SELECT is repaired only from the picks gate, on the lines above
    # the GRANT. The function anon keeps is granted on its own line.
    grant = "GRANT SELECT ON public.site_public_record TO anon;"
    assert grant in code
    window = code.split(grant, 1)[0].splitlines()[-8:]
    assert any("public.picks" in ln for ln in window)
    assert "GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO anon;" in code
    assert "%" not in SQL


def test_the_view_casts_match_production_and_the_function_pins_search_path():
    hand = (ROOT / "data" / "migrations" / "site_public_record_2026_11.sql").read_text(
        encoding="utf-8")
    assert "LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp" in hand
    assert "units numeric, risked numeric, first_date date, last_date date" in hand
    assert "f.units::numeric(12, 2) AS units" in SQL
    assert "f.risked::numeric(12, 2) AS risked" in SQL
    assert "now() AS refreshed_at" in SQL


def test_the_hand_file_still_builds_the_definer_view_and_names_this_one():
    hand = (ROOT / "data" / "migrations" / "site_public_record_2026_11.sql").read_text(
        encoding="utf-8")
    spec = (ROOT / "data" / "anon_lockdown_spec.py").read_text(encoding="utf-8")
    assert "WITH (security_invoker = false, security_barrier = true)" in hand
    assert "site_public_record_rows()" in hand
    assert MIG.name in hand
    assert MIG.name in spec


def test_the_worker_adapter_leaves_casts_alone():
    from data.db import _adapt_sql
    adapted = _adapt_sql(SQL)
    assert adapted is not None
    assert "%(text)s" not in adapted
    assert "%(numeric)s" not in adapted
    assert "%(regclass)s" not in adapted
    assert "::text[]" in adapted
    assert "::regclass" in adapted
    assert "::numeric(12, 2)" in adapted


def _run_migration(cur) -> None:
    """The text the worker executes, after its SQLite-to-Postgres adapter."""
    from data.db import _adapt_sql
    adapted = _adapt_sql(SQL)
    assert adapted is not None
    cur.execute(adapted)


def _ddl_counter(cur) -> None:
    cur.execute("""
        CREATE TABLE ddl_seen (n integer NOT NULL);
        INSERT INTO ddl_seen VALUES (0);
        CREATE FUNCTION count_ddl() RETURNS event_trigger LANGUAGE plpgsql AS
        $$ BEGIN UPDATE ddl_seen SET n = n + 1; END $$;
        CREATE EVENT TRIGGER count_ddl ON ddl_command_start
          EXECUTE FUNCTION count_ddl()
    """)


def _ddl_n(cur) -> int:
    cur.execute("SELECT n FROM ddl_seen")
    return cur.fetchone()[0]


def _notices(conn) -> list[str]:
    found = [n.strip() for n in conn.notices]
    del conn.notices[:]
    return found


def _invoker(cur) -> bool:
    cur.execute("""
        SELECT lower(opt)
          FROM pg_catalog.pg_class c,
               unnest(coalesce(c.reloptions, ARRAY[]::text[])) AS opt
         WHERE c.oid = 'public.site_public_record'::regclass
    """)
    opts = {row[0] for row in cur.fetchall()}
    return any(opt in opts for opt in _INVOKER)


def _rows(conn) -> list[tuple]:
    """SELECT the website's columns as anon. Rolls back the role change."""
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SET LOCAL ROLE anon")
        cur.execute("""
            SELECT sport, picks, wins, losses, pushes, units, risked
              FROM public.site_public_record
             ORDER BY sport
        """)
        rows = cur.fetchall()
        conn.rollback()
        return rows
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.autocommit = True


def _refused(conn, sql: str) -> str:
    conn.autocommit = False
    cur = conn.cursor()
    try:
        cur.execute("SET LOCAL ROLE anon")
        cur.execute(sql)
        conn.rollback()
        raise AssertionError(f"anon was allowed: {sql}")
    except Exception as exc:
        conn.rollback()
        if "anon was allowed" in str(exc):
            raise
        return f"{getattr(exc, 'pgcode', '')} {exc}"
    finally:
        conn.autocommit = True


def _record_fixture(cur, *, anon_reads_picks: bool) -> None:
    """The production shape: invoker record view over push_sent, definer
    function, definer site view. Anon can read the site view and execute
    the function. Anon cannot read the inner view."""
    cur.execute("CREATE ROLE anon NOLOGIN")
    cur.execute("CREATE ROLE authenticated NOLOGIN")
    cur.execute("""
        CREATE TABLE public.push_sent (
          lock_key text, kind text, sent_at timestamptz
        )
    """)
    cur.execute("ALTER TABLE public.push_sent ENABLE ROW LEVEL SECURITY")
    cur.execute("""
        CREATE TABLE public.site_retired_models (model_id text PRIMARY KEY)
    """)
    cur.execute("ALTER TABLE public.site_retired_models ENABLE ROW LEVEL SECURITY")
    cur.execute("""
        REVOKE ALL ON public.site_retired_models FROM PUBLIC, anon, authenticated
    """)
    cur.execute("INSERT INTO public.site_retired_models (model_id) VALUES ('nba_moneyline')")
    cur.execute("""
        CREATE VIEW public.v_public_track_record WITH (security_invoker = true) AS
        SELECT t.sport, t.model_id,
               t.picks, t.wins, t.losses, t.pushes, t.units, t.risked,
               t.first_date::date AS first_date,
               t.last_date::date AS last_date
          FROM (VALUES
            ('NBA', 'nba_live_total', 2, 1, 1, 0, 1.25::numeric, 2::numeric,
             '2026-09-01', '2026-09-02'),
            ('NBA', 'nba_moneyline', 4, 4, 0, 0, 9::numeric, 4::numeric,
             '2026-09-01', '2026-09-03'),
            ('NFL', 'nfl_spread', 1, 1, 0, 0, 0.50::numeric, 1::numeric,
             '2026-10-01', '2026-10-01')
          ) AS t(sport, model_id, picks, wins, losses, pushes, units, risked,
                 first_date, last_date)
         WHERE NOT EXISTS (
           SELECT 1 FROM public.push_sent p
            WHERE p.lock_key = t.model_id AND p.kind = 'discord_void')
    """)
    cur.execute("REVOKE ALL ON public.v_public_track_record FROM PUBLIC, anon, authenticated")
    cur.execute("REVOKE ALL ON public.push_sent FROM PUBLIC, anon, authenticated")
    cur.execute("""
        CREATE FUNCTION public.site_public_record_rows()
        RETURNS TABLE (sport text, picks integer, wins integer, losses integer,
                       pushes integer, units numeric, risked numeric,
                       first_date date, last_date date)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp
        AS $fn$
          SELECT r.sport,
                 sum(r.picks)::integer, sum(r.wins)::integer,
                 sum(r.losses)::integer, sum(r.pushes)::integer,
                 round(sum(r.units), 2), round(sum(r.risked), 2),
                 min(r.first_date)::date, max(r.last_date)::date
            FROM public.v_public_track_record r
           WHERE NOT EXISTS (
             SELECT 1 FROM public.site_retired_models s
              WHERE s.model_id = r.model_id)
           GROUP BY r.sport
        $fn$
    """)
    cur.execute("""
        REVOKE ALL ON FUNCTION public.site_public_record_rows()
          FROM PUBLIC, anon, authenticated
    """)
    cur.execute("""
        GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO anon
    """)
    cur.execute("""
        GRANT EXECUTE ON FUNCTION public.site_public_record_rows() TO authenticated
    """)
    cur.execute("""
        CREATE VIEW public.site_public_record
        WITH (security_invoker = false, security_barrier = true) AS
        SELECT f.sport, f.picks, f.wins, f.losses, f.pushes,
               f.units::numeric(12, 2) AS units,
               f.risked::numeric(12, 2) AS risked,
               f.first_date, f.last_date,
               now() AS refreshed_at
          FROM public.site_public_record_rows() f
    """)
    cur.execute("REVOKE ALL ON public.site_public_record FROM PUBLIC")
    cur.execute("GRANT SELECT ON public.site_public_record TO anon")
    cur.execute("GRANT SELECT ON public.site_public_record TO authenticated")
    cur.execute("CREATE TABLE public.picks (id integer)")
    cur.execute("REVOKE ALL ON public.picks FROM PUBLIC, anon, authenticated")
    if anon_reads_picks:
        cur.execute("GRANT SELECT ON public.picks TO anon")


def _expected_rows():
    return [
        ("NBA", 2, 1, 1, 0, Decimal("1.25"), Decimal("2.00")),
        ("NFL", 1, 1, 0, 0, Decimal("0.50"), Decimal("1.00")),
    ]


def _normalize(rows):
    out = []
    for sport, picks, wins, losses, pushes, units, risked in rows:
        out.append((
            sport, picks, wins, losses, pushes,
            Decimal(units).quantize(Decimal("0.01")),
            Decimal(risked).quantize(Decimal("0.01")),
        ))
    return out


def _columns(cur) -> list[tuple]:
    cur.execute("""
        SELECT a.attname, format_type(a.atttypid, a.atttypmod)
          FROM pg_attribute a
         WHERE a.attrelid = 'public.site_public_record'::regclass
           AND a.attnum > 0 AND NOT a.attisdropped
         ORDER BY a.attnum
    """)
    return [(name, typ) for name, typ in cur.fetchall()]


def _assert_prod_shape(cur) -> None:
    assert _columns(cur) == list(_PROD_TYPES)
    cur.execute("""
        SELECT pg_get_function_result(p.oid), p.proconfig
          FROM pg_proc p
         WHERE p.oid = 'public.site_public_record_rows()'::regprocedure
    """)
    result, proconfig = cur.fetchone()
    assert result == _FN_RESULT
    assert proconfig is not None
    assert "search_path=public, pg_temp" in proconfig


def _cluster():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests._pg import pg_bin, scratch_cluster
    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    return psycopg2, scratch_cluster


def test_step_a_already_applied_anon_still_reads_and_the_second_pass_is_a_noop():
    """Production order. Step A has already revoked anon on picks and on
    the inner record view. The site view is still the definer view from
    the hand file, and anon can already read it. The migration turns the
    view to security_invoker. The same rows come back. The next pass
    issues no DDL."""
    psycopg2, scratch_cluster = _cluster()
    with scratch_cluster("site-invoker-") as dsn:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            _ddl_counter(cur)
            cur.execute("UPDATE ddl_seen SET n = 0")
            _notices(conn)
            _run_migration(cur)
            assert _ddl_n(cur) == 0, "a database without the function ran DDL"
            assert any("site_public_record_rows is missing - skipping" in n
                       for n in _notices(conn))

            _record_fixture(cur, anon_reads_picks=False)
            assert _invoker(cur) is False
            before = _normalize(_rows(conn))
            assert before == _expected_rows()
            refused = _refused(conn, "SELECT 1 FROM public.v_public_track_record")
            assert "42501" in refused

            cur.execute("UPDATE ddl_seen SET n = 0")
            _notices(conn)
            _run_migration(cur)
            assert _ddl_n(cur) > 0, "the counter did not see this file's DDL"
            assert _invoker(cur) is True
            cur.execute("""
                SELECT pg_get_viewdef('public.site_public_record'::regclass, true)
            """)
            viewdef = cur.fetchone()[0]
            assert "site_public_record_rows" in viewdef
            assert "refreshed_at" in viewdef
            assert "v_public_track_record" not in viewdef
            assert _normalize(_rows(conn)) == before
            _assert_prod_shape(cur)
            assert "model_id" not in {name for name, _typ in _columns(cur)}
            refused = _refused(conn, "SELECT 1 FROM public.v_public_track_record")
            assert "42501" in refused
            cur.execute("""
                SELECT has_table_privilege('anon', 'public.site_public_record', 'SELECT'),
                       has_table_privilege('anon', 'public.picks', 'SELECT'),
                       has_function_privilege(
                         'anon', 'public.site_public_record_rows()', 'EXECUTE')
            """)
            assert cur.fetchone() == (True, False, True)

            cur.execute("UPDATE ddl_seen SET n = 0")
            _notices(conn)
            _run_migration(cur)
            assert _ddl_n(cur) == 0, "the second pass ran DDL"
            assert any("already security_invoker - skipping" in n for n in _notices(conn))
            assert _normalize(_rows(conn)) == before
            assert _invoker(cur) is True
        finally:
            conn.close()


def test_apply_then_reapply_then_step_a_reapply_does_not_run_ddl():
    """Anon can read picks: the body runs and grants anon. The next pass
    skips. Step A then revokes anon on picks and on the inner view. The
    pass skips again, and anon still gets the same rows."""
    psycopg2, scratch_cluster = _cluster()
    with scratch_cluster("site-invoker-a-") as dsn:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            cur = conn.cursor()
            _record_fixture(cur, anon_reads_picks=True)
            _ddl_counter(cur)
            cur.execute("CREATE TABLE ddl_probe (id integer)")
            assert _ddl_n(cur) >= 1
            cur.execute("DROP TABLE ddl_probe")
            assert _invoker(cur) is False
            before = _normalize(_rows(conn))
            assert before == _expected_rows()

            cur.execute("UPDATE ddl_seen SET n = 0")
            _run_migration(cur)
            assert _ddl_n(cur) > 0, "the counter did not see this file's DDL"
            assert _invoker(cur) is True
            assert _normalize(_rows(conn)) == before
            _assert_prod_shape(cur)
            cur.execute("""
                SELECT has_table_privilege('anon', 'public.picks', 'SELECT'),
                       has_table_privilege('anon', 'public.site_public_record', 'SELECT')
            """)
            assert cur.fetchone() == (True, True)

            cur.execute("UPDATE ddl_seen SET n = 0")
            _notices(conn)
            _run_migration(cur)
            assert _ddl_n(cur) == 0, "the second pass ran DDL"
            assert any("already security_invoker - skipping" in n for n in _notices(conn))

            cur.execute("""
                REVOKE ALL ON public.picks FROM PUBLIC, anon, authenticated;
                REVOKE ALL ON public.v_public_track_record FROM anon;
                REVOKE ALL ON public.push_sent FROM anon;
            """)
            cur.execute("UPDATE ddl_seen SET n = 0")
            _notices(conn)
            _run_migration(cur)
            assert _ddl_n(cur) == 0, "step A sent the file back through DDL"
            assert any("already security_invoker - skipping" in n for n in _notices(conn))
            assert _invoker(cur) is True
            assert _normalize(_rows(conn)) == before
            refused = _refused(conn, "SELECT 1 FROM public.picks")
            assert "42501" in refused
            refused = _refused(conn, "SELECT 1 FROM public.v_public_track_record")
            assert "42501" in refused
            cur.execute("""
                SELECT has_table_privilege('anon', 'public.site_public_record', 'SELECT'),
                       has_table_privilege('anon', 'public.site_public_record', 'INSERT'),
                       has_function_privilege(
                         'anon', 'public.site_public_record_rows()', 'EXECUTE')
            """)
            assert cur.fetchone() == (True, False, True)
        finally:
            conn.close()
