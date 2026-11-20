"""
The Picks filter's Model section (Matt, 2026-11-18): each model's published
record and a hot / cold tag over its last 7 days.

Two halves:
  * the view, v_public_track_record_model_daily, must be the daily record view
    split by model and nothing else. Its migration builds it FROM the daily
    view's definition, so it cannot drift from the record; these tests pin
    that it does so, rather than carrying a hand copy of the WHERE clause.
    Reconciled against production 2026-11-19: per model it equals
    v_public_track_record, per (date, sport) it equals the daily view.
  * the behaviour, in mobile/scripts/verify_model_heat.ts, run when node and
    the app's node modules are installed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from tests._node import tsx_cmd

ROOT = Path(__file__).parent.parent
MOBILE = ROOT / "mobile"
MIG = ROOT / "data" / "migrations" / "public_track_record_model_daily_2026_11_18.sql"
SQL = MIG.read_text(encoding="utf-8")
CODE = "\n".join(l for l in SQL.splitlines() if not l.lstrip().startswith("--"))


def test_migration_is_registered_before_the_units_patch():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert MIG.name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"


def test_migration_is_one_statement():
    assert CODE.count("$mig$") == 2
    assert CODE.split("$mig$")[-1].strip() == ";"


def test_the_view_is_derived_from_the_daily_view_not_copied():
    """A hand-copied WHERE would drift the first time the record views change.
    Broken copy: a literal `FROM picks` body instead of the viewdef read."""
    assert "pg_get_viewdef('public.v_public_track_record_daily'::regclass" in CODE
    assert "FROM picks" not in CODE
    assert "md5(daily_def)" in CODE


def test_grants_are_select_only():
    assert "security_invoker = on" in CODE
    for role in ("PUBLIC", "anon", "authenticated"):
        assert f"REVOKE ALL ON public.v_public_track_record_model_daily FROM {role};" in CODE
    # Authenticated only: the anon-key lockdown takes anon off the record
    # views, and this view is rebuilt on later passes.
    assert "GRANT SELECT ON public.v_public_track_record_model_daily TO authenticated;" in CODE
    assert "TO anon" not in CODE


def test_the_view_is_in_the_authenticated_manifest_and_not_anon():
    from data.anon_readable import ANON_READABLE, AUTHENTICATED_READABLE
    assert "v_public_track_record_model_daily" in AUTHENTICATED_READABLE
    assert "v_public_track_record_model_daily" not in ANON_READABLE


def test_the_app_reads_it_by_literal_name():
    src = (MOBILE / "src" / "lib" / "queries.ts").read_text(encoding="utf-8")
    assert ".from('v_public_track_record_model_daily')" in src


@pytest.mark.skipif(tsx_cmd(MOBILE) is None, reason="mobile node modules not installed")
def test_the_behavioural_checks_pass():
    proc = subprocess.run(
        [*tsx_cmd(MOBILE), "scripts/verify_model_heat.ts"],
        cwd=MOBILE, capture_output=True, text=True, timeout=300,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── the migration on a real Postgres ──────────────────────────────────────────
# A stand-in daily view with the production view's shape (SELECT game_date,
# sport, ... GROUP BY game_date, sport ...). The migration is run as the
# runner runs it, then the daily view is changed in ways CREATE OR REPLACE
# cannot follow.

DAILY_V1 = """
CREATE VIEW public.v_public_track_record_daily AS
SELECT game_date, sport, count(*) AS picks, sum(u) AS units
FROM t GROUP BY game_date, sport HAVING count(*) > 0
"""
# A column renamed and one removed: CREATE OR REPLACE would raise here.
DAILY_V2 = """
CREATE VIEW public.v_public_track_record_daily AS
SELECT game_date, sport, count(*) AS bets
FROM t GROUP BY game_date, sport
"""
# GROUP BY on something else: the edit does not apply.
DAILY_V3 = """
CREATE VIEW public.v_public_track_record_daily AS
SELECT game_date, sport, count(*) AS bets FROM t GROUP BY sport, game_date
"""


@pytest.fixture(scope="module")
def dsn():
    from tests._pg import can_scratch, env_dsn, scratch_cluster
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("no scratch Postgres")
    with scratch_cluster("model-daily-pg-") as d:
        yield d


def _cols(cur, view):
    cur.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position",
        (view,),
    )
    return [r[0] for r in cur.fetchall()]


def test_the_migration_builds_skips_rebuilds_and_fails_soft(dsn):
    psycopg2 = pytest.importorskip("psycopg2")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in ("anon", "authenticated"):
        cur.execute(f"DO $$ BEGIN CREATE ROLE {role}; EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    cur.execute("DROP VIEW IF EXISTS public.v_public_track_record_model_daily, public.v_public_track_record_daily")
    cur.execute("DROP TABLE IF EXISTS t")
    cur.execute("CREATE TABLE t (game_date text, sport text, model_id text, u numeric)")
    cur.execute("INSERT INTO t VALUES ('2026-11-17','NHL','a',1),('2026-11-17','NHL','a',-0.5),"
                "('2026-11-17','NHL','b',2),('2026-11-18','NBA','c',1)")
    cur.execute(DAILY_V1)

    # 1. built: the daily view split by model, totals equal to the daily view
    cur.execute(SQL)
    assert _cols(cur, "v_public_track_record_model_daily") == [
        "game_date", "sport", "model_id", "picks", "units"]
    cur.execute("SELECT model_id, picks, units FROM v_public_track_record_model_daily ORDER BY 1")
    assert cur.fetchall() == [("a", 2, 0.5), ("b", 1, 2), ("c", 1, 1)]
    cur.execute("SELECT game_date, sport, sum(picks), sum(units) FROM v_public_track_record_model_daily "
                "GROUP BY 1, 2 EXCEPT SELECT game_date, sport, picks, units FROM v_public_track_record_daily")
    assert cur.fetchall() == []
    cur.execute("SELECT has_table_privilege('anon', 'v_public_track_record_model_daily', 'SELECT'), "
                "has_table_privilege('authenticated', 'v_public_track_record_model_daily', 'SELECT'), "
                "has_table_privilege('authenticated', 'v_public_track_record_model_daily', 'INSERT')")
    assert cur.fetchone() == (False, True, False)

    # 2. current: a second pass changes nothing (the view keeps its oid)
    cur.execute("SELECT 'public.v_public_track_record_model_daily'::regclass::oid")
    oid = cur.fetchone()[0]
    cur.execute(SQL)
    cur.execute("SELECT 'public.v_public_track_record_model_daily'::regclass::oid")
    assert cur.fetchone()[0] == oid

    # 3. the daily view renames and drops columns: rebuilt, no error
    cur.execute("DROP VIEW v_public_track_record_model_daily, v_public_track_record_daily")
    cur.execute(DAILY_V1)
    cur.execute(SQL)
    cur.execute("DROP VIEW v_public_track_record_daily CASCADE")
    cur.execute(DAILY_V2)
    cur.execute(SQL)
    assert _cols(cur, "v_public_track_record_model_daily") == ["game_date", "sport", "model_id", "bets"]

    # 4. a shape the edit cannot apply to: no error, nothing new created
    cur.execute("DROP VIEW v_public_track_record_model_daily, v_public_track_record_daily")
    cur.execute(DAILY_V3)
    cur.execute(SQL)
    cur.execute("SELECT to_regclass('public.v_public_track_record_model_daily')")
    assert cur.fetchone()[0] is None
    conn.close()
