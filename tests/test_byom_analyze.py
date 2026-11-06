"""The BYOM builders refresh the planner's row counts after they write.

2026-11-05: 11,075 byom_prop_facts rows sat under the autovacuum
threshold, the planner counted 1 row for the current NBA season, and the
points preview took 6.0s (anon stops at 3s). byom/analyze.py.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_the_job_is_registered_and_declared_once():
    from tracking.job_queue import JOBS

    assert "byom_analyze" in JOBS
    jobs = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    mine = [j for j in jobs if j["job_type"] == "byom_analyze"]
    assert len(mine) == 1
    assert mine[0]["enabled"] is True
    assert mine[0]["args"] == {}


def test_the_backfill_jobs_analyze_after_an_apply():
    text = (ROOT / "tracking/job_queue.py").read_text(encoding="utf-8")
    for name in ("_job_byom_game_facts", "_job_byom_prop_facts"):
        body = text.split(f"def {name}(", 1)[1].split("\ndef ", 1)[0]
        assert "analyze_tables(conn)" in body, name
        assert 'if kw.get("apply"):' in body, name


def test_a_failed_analyze_is_skipped_not_raised():
    from byom.analyze import TABLES, analyze_tables

    class Conn:
        def __init__(self):
            self.rolled = 0

        def execute(self, sql, params=None):
            if "byom_prop_facts" in sql:
                raise RuntimeError("must be owner")

        def commit(self):
            pass

        def rollback(self):
            self.rolled += 1

    conn = Conn()
    done = analyze_tables(conn)
    assert done == [t for t in TABLES if t != "byom_prop_facts"]
    assert conn.rolled == 1


def test_analyze_gives_the_planner_the_real_row_count():
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
        for name in TABLE_NAMES:
            cur.execute(f"CREATE TABLE public.{name} (k int); "
                        f"ALTER TABLE public.{name} SET (autovacuum_enabled = false); "
                        f"INSERT INTO public.{name} SELECT generate_series(1, 5000)")
        cur.execute("SELECT reltuples FROM pg_class WHERE relname = 'byom_prop_facts'")
        assert cur.fetchone()[0] < 0  # never analyzed
        raw.autocommit = False

        class Conn:
            def execute(self, sql, params=None):
                c = raw.cursor()
                c.execute(sql, params)
                return c

            def commit(self):
                raw.commit()

            def rollback(self):
                raw.rollback()

        from byom.analyze import analyze_tables
        assert analyze_tables(Conn()) == list(TABLE_NAMES)
        cur = raw.cursor()
        cur.execute("SELECT relname, reltuples FROM pg_class "
                    "WHERE relname = ANY (%s)", (list(TABLE_NAMES),))
        assert {r[0]: r[1] for r in cur.fetchall()} == {n: 5000 for n in TABLE_NAMES}
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


TABLE_NAMES = ("byom_game_facts", "byom_prop_facts", "byom_official_legs")
