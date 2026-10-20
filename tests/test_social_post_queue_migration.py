"""social_post_queue must apply on a database that does not have the table.

A 'rel'::regclass cast is resolved while the statement is planned, so an IF
that uses one errors before it can fall through and create the table.
to_regclass returns NULL instead. Production already has the table, locked
down, and a second pass has to return before it inserts the seed again.

The same guard is in pick_placement_checks. byom_facts_schema checks the
catalog the same way, after to_regclass has already said the tables exist.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
QUEUE = ROOT / "data" / "migrations" / "social_post_queue_2026_10_20.sql"
MEDIA = ROOT / "data" / "migrations" / "social_post_media_2026_10_20.sql"
PLACEMENT = ROOT / "data" / "migrations" / "pick_placement_checks_2026_09_22.sql"
DECIDE = ROOT / "data" / "migrations" / "decide_on_best_price_2026_09_09.sql"
QUEUE_SQL = QUEUE.read_text(encoding="utf-8")
MEDIA_SQL = MEDIA.read_text(encoding="utf-8")
PLACEMENT_SQL = PLACEMENT.read_text(encoding="utf-8")
THREAD = "all-time-ledger-2026-10-20"


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _roles(cur) -> None:
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


def _scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    try:
        dsn = cluster.start()
    except Exception as exc:
        cluster.stop()
        pytest.skip(f"scratch cluster did not start: {exc}")
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    return cluster, conn


def test_the_guard_does_not_cast_regclass_and_stays_off_the_end():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert QUEUE.name in ACTIVE_MIGRATIONS
    assert PLACEMENT.name in ACTIVE_MIGRATIONS
    # The posted-stake patch stays last. This file does not move the list.
    assert ACTIVE_MIGRATIONS[-1] == "published_record_units_2026_10_16.sql"
    assert ACTIVE_MIGRATIONS.index(QUEUE.name) < ACTIVE_MIGRATIONS.index(MEDIA.name)
    assert ACTIVE_MIGRATIONS.index("clv_standard_v2_2026_10_14.sql") < len(ACTIVE_MIGRATIONS) - 1

    code = _code(QUEUE_SQL)
    assert "::regclass" not in code
    assert "to_regclass('public.social_post_queue') IS NOT NULL" in code
    assert code.index("RETURN;") < code.index("INSERT INTO public.social_post_queue")
    assert code.count("$mig$") == 2
    assert "CREATE TABLE IF NOT EXISTS public.social_post_queue" in code

    placement = _code(PLACEMENT_SQL)
    assert "::regclass" not in placement
    assert "to_regclass('public.pick_placement_checks') IS NOT NULL" in placement
    assert placement.index("RETURN;") < placement.index("ENABLE ROW LEVEL SECURITY")

    decide = _code(DECIDE.read_text(encoding="utf-8"))
    assert "attrelid = to_regclass('public.mv_scored_pick_outcomes')" in decide
    assert "'public.mv_scored_pick_outcomes'::regclass" not in decide


def test_queue_migration_applies_on_an_empty_database_and_again():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        _roles(cur)
        cur.execute(QUEUE_SQL)
        cur.execute(QUEUE_SQL)

        cur.execute("""
            SELECT position, allow_link, pin, status
              FROM public.social_post_queue
             WHERE thread_key = %s
             ORDER BY position
        """, (THREAD,))
        assert cur.fetchall() == [
            (1, False, True, "queued"),
            (2, False, False, "queued"),
            (3, True, False, "queued"),
        ]
        cur.execute("""
            SELECT c.relrowsecurity
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relname = 'social_post_queue'
        """)
        assert cur.fetchone() == (True,)
        for role in ("anon", "authenticated"):
            for verb in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                cur.execute(
                    "SELECT has_table_privilege(%s, 'public.social_post_queue', %s)",
                    (role, verb))
                assert cur.fetchone()[0] is False, (role, verb)

        cur.execute(MEDIA_SQL)
        cur.execute(MEDIA_SQL)
        cur.execute("""
            SELECT column_name
              FROM information_schema.columns
             WHERE table_schema = 'public' AND table_name = 'social_post_queue'
               AND column_name IN ('media_urls', 'media_ids', 'reply_to_tweet_id')
             ORDER BY column_name
        """)
        assert [row[0] for row in cur.fetchall()] == [
            "media_ids", "media_urls", "reply_to_tweet_id",
        ]

        # A locked table does not grow the seed back. That is the production
        # re-run: the table is already there, and a deleted thread stays deleted.
        cur.execute("DELETE FROM public.social_post_queue")
        cur.execute(QUEUE_SQL)
        cur.execute("SELECT count(*) FROM public.social_post_queue")
        assert cur.fetchone()[0] == 0
    finally:
        conn.close()
        cluster.stop()


def test_a_hand_locked_queue_is_left_alone():
    """Production created the table by hand. The file must not insert again."""
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        _roles(cur)
        cur.execute("""
            CREATE TABLE public.social_post_queue (
              id         BIGSERIAL PRIMARY KEY,
              thread_key TEXT NOT NULL,
              position   INTEGER NOT NULL,
              body       TEXT NOT NULL,
              allow_link BOOLEAN NOT NULL DEFAULT FALSE,
              pin        BOOLEAN NOT NULL DEFAULT FALSE,
              status     TEXT NOT NULL DEFAULT 'queued',
              CONSTRAINT social_post_queue_thread_pos UNIQUE (thread_key, position)
            );
            ALTER TABLE public.social_post_queue ENABLE ROW LEVEL SECURITY;
            REVOKE ALL ON public.social_post_queue FROM anon, authenticated;
            INSERT INTO public.social_post_queue
              (thread_key, position, body, status)
            VALUES ('hand-made', 1, 'leave this row', 'posted');
        """)
        cur.execute(QUEUE_SQL)
        cur.execute(QUEUE_SQL)
        cur.execute("""
            SELECT thread_key, position, body, status
              FROM public.social_post_queue
             ORDER BY thread_key, position
        """)
        assert cur.fetchall() == [("hand-made", 1, "leave this row", "posted")]
    finally:
        conn.close()
        cluster.stop()


def test_placement_checks_apply_on_an_empty_database_and_again():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        _roles(cur)
        cur.execute(PLACEMENT_SQL)
        cur.execute(PLACEMENT_SQL)
        cur.execute("""
            SELECT c.relrowsecurity
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = 'public' AND c.relname = 'pick_placement_checks'
        """)
        assert cur.fetchone() == (True,)
        cur.execute("SELECT count(*) FROM public.pick_placement_checks")
        assert cur.fetchone()[0] == 0
        for verb in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            cur.execute(
                "SELECT has_table_privilege('anon', 'public.pick_placement_checks', %s)",
                (verb,))
            assert cur.fetchone()[0] is False, verb
    finally:
        conn.close()
        cluster.stop()


def test_a_missing_matview_does_not_make_the_decision_guard_raise():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT NOT EXISTS (
              SELECT 1 FROM pg_attribute
               WHERE attrelid = to_regclass('public.mv_scored_pick_outcomes')
                 AND attname = 'decision_edge' AND NOT attisdropped)
        """)
        assert cur.fetchone()[0] is True
    finally:
        conn.close()
        cluster.stop()
