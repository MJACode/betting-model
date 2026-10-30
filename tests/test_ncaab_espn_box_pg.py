"""The NCAAB box-score feed against a real Postgres.

WHY A REAL DATABASE. Four properties are claims about the server, not about
Python: the migration and the write-time guard create the same locked-down
tables and, once they exist, neither runs DDL again; the due query's key
('espn:' || a BIGINT) and its cool-down (a TIMESTAMPTZ against a text
parameter) mean on Postgres what they mean on sqlite; production's NUMERIC
scores read back as whole points; and the DISTINCT ON the docs give picks one
row per game and team. Runs against LATEST_LINE_TEST_DSN or a throwaway
cluster from tests/_pg.py, and SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.anon_readable import API_ROLES  # noqa: E402
from data.db import DBConnection  # noqa: E402
from data.ddl_guard import schema_is_current  # noqa: E402
from data.ingestors import ncaab_espn_box as box  # noqa: E402
from data.ingestors import ncaab_sdv_import as sdv  # noqa: E402
from data.ingestors import ncaab_teams as nt  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

ROOT = Path(__file__).parent.parent
FIX = Path(__file__).parent / "fixtures" / "ncaab_espn_box"
MIGRATION = (ROOT / "data" / "migrations" / "add_ncaab_period_scores_2026_10_30.sql").read_text(
    encoding="utf-8")
SUMMARY = json.loads((FIX / "summary_401825519.json").read_text(encoding="utf-8"))
GAME_ID = "NCAAB_2026-02-15_maryland_rutgers"
NOW = datetime(2026, 2, 16, 15, 0, tzinfo=timezone.utc)

# production's types for the columns read (information_schema, 2026-10-30)
GAMES_DDL = """
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL,
    game_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score NUMERIC, away_score NUMERIC, commence_time TEXT, went_to_ot INTEGER)
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-box-pg-") as d:
        yield d


@pytest.fixture()
def raw(dsn):
    conn = psycopg2.connect(dsn)
    conn.autocommit = True
    cur = conn.cursor()
    for role in API_ROLES:            # Supabase's two API roles, as production has them
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    f"'{role}') THEN CREATE ROLE {role}; END IF; END $$")
    cur.execute("DROP TABLE IF EXISTS games, ncaab_events, ncaab_team_game_stats, "
                "ncaab_player_season, ncaab_period_scores, ncaab_box_misses")
    cur.execute(GAMES_DDL)
    cur.execute(nt.EVENTS_DDL)
    cur.execute("INSERT INTO games VALUES (%s, 'NCAAB', 2026, '2026-02-15', 'Rutgers', "
                "'Maryland', 68, 57, '2026-02-15T17:00:00Z', 0)", (GAME_ID,))
    cur.execute("INSERT INTO ncaab_events (espn_event_id, game_id, season, game_date, "
                "commence_time, home_espn_id, away_espn_id) VALUES (401825519, %s, 2026, "
                "'2026-02-15', '2026-02-15T17:00:00Z', 164, 120)", (GAME_ID,))
    try:
        yield conn
    finally:
        conn.close()


class Recording(DBConnection):
    """The real wrapper, keeping every statement it was handed."""

    def __init__(self, dsn):
        super().__init__(psycopg2.connect(dsn), url=dsn)
        self.seen: list[str] = []

    def execute(self, sql, params=None):
        self.seen.append(" ".join(str(sql).split()))
        return super().execute(sql, params)

    def ddl(self):
        return [s for s in self.seen
                if s.split(None, 1)[0].upper() in ("CREATE", "ALTER", "REVOKE", "GRANT", "DROP")]


def _locked(raw, table):
    cur = raw.cursor()
    cur.execute("SELECT relrowsecurity FROM pg_class WHERE oid = to_regclass(%s)", (table,))
    rls = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM pg_roles r WHERE r.rolname IN ('anon', 'authenticated') "
                "AND has_table_privilege(r.oid, %s, 'SELECT,INSERT,UPDATE,DELETE')", (table,))
    return rls and cur.fetchone()[0] == 0


def test_the_migration_creates_locked_tables_and_then_ensure_runs_no_ddl(raw, dsn):
    cur = raw.cursor()
    cur.execute(MIGRATION)
    cur.execute(MIGRATION)                                   # a second pass is a no-op
    for t in ("ncaab_period_scores", "ncaab_box_misses"):
        assert _locked(raw, t), t
    c = Recording(dsn)
    try:
        sdv.ensure_tables(c)                                 # production already has it
        c.seen.clear()
        box.ensure_tables(c)
        assert c.ddl() == [], c.ddl()
        assert schema_is_current(c, "ncaab_period_scores", columns=box.PERIODS_COLS,
                                 indexes=("idx_ncaab_period_scores_season",),
                                 rls=True, revoked_from=API_ROLES)
    finally:
        c._conn.close()


def test_ensure_alone_creates_the_same_locked_tables_once(raw, dsn):
    c = Recording(dsn)
    try:
        box.ensure_tables(c)
        assert c.ddl(), "nothing was created on an empty database"
        for t in ("ncaab_team_game_stats", "ncaab_period_scores", "ncaab_box_misses"):
            assert _locked(raw, t), t
        c.seen.clear()
        box.ensure_tables(c)
        assert c.ddl() == [], c.ddl()
    finally:
        c._conn.close()
    # and the migration, run after, finds nothing to do
    raw.cursor().execute(MIGRATION)


class Espn:
    def __init__(self, summaries):
        self.summaries = summaries
        self.calls = []

    def __call__(self, url, params):
        self.calls.append(params)
        return copy.deepcopy(self.summaries[int(params["event"])])


def test_a_run_on_postgres_stores_once_and_cools_a_refusal(raw, dsn):
    raw.cursor().execute(MIGRATION)
    espn = Espn({401825519: {"header": {"id": "401825519"}}})     # not final: refused
    c = Recording(dsn)
    try:
        t = box.run_recent("2026-02-16", now=NOW, connect=lambda: c, get_json=espn)
        assert t["refused"] == 1 and t["failed"] == []
        # inside the cool-down: the TIMESTAMPTZ comparison keeps it out
        t = box.run_recent("2026-02-16", now=NOW + timedelta(minutes=10),
                           connect=lambda: c, get_json=espn)
        assert t["due"] == 0 and len(espn.calls) == 1
        espn.summaries[401825519] = SUMMARY
        t = box.run_recent("2026-02-16", now=NOW + timedelta(hours=1),
                           connect=lambda: c, get_json=espn)
        assert (t["games_stored"], t["box_rows"], t["period_rows"]) == (1, 2, 2), t
        t = box.run_recent("2026-02-16", now=NOW + timedelta(hours=2),
                           connect=lambda: c, get_json=espn)
        assert t["due"] == 0 and len(espn.calls) == 2
    finally:
        c._conn.close()
    cur = raw.cursor()
    cur.execute("SELECT contest_id, team, o_poss, d_poss, pts FROM ncaab_team_game_stats "
                "ORDER BY team")
    assert cur.fetchall() == [("espn:401825519", "Maryland", 64.175, 65.4, 57.0),
                              ("espn:401825519", "Rutgers", 65.4, 64.175, 68.0)]
    cur.execute("SELECT period, home_points, away_points FROM ncaab_period_scores "
                "ORDER BY period")
    assert cur.fetchall() == [(1, 27, 27), (2, 41, 30)]


def test_the_documented_reader_picks_one_source_per_game(raw, dsn):
    raw.cursor().execute(MIGRATION)
    c = DBConnection(psycopg2.connect(dsn), url=dsn)
    try:
        sdv.ensure_tables(c)
        c.commit()
        cols = [x for x in sdv.TEAM_COLS if x != "loaded_at"]
        for team, tid, opp, home, pts in (("Maryland", 120, 164, False, 57),
                                          ("Rutgers", 164, 120, True, 68)):
            row = {x: None for x in cols}
            row.update(contest_id="6465747", team=team, espn_game_id=401825519,
                       team_espn_id=tid, opp_espn_id=opp, is_home=home, season=2026,
                       o_poss=67, d_poss=67, pts=pts, source="sportsdataverse_ncaa")
            c.execute(f"INSERT INTO ncaab_team_game_stats ({', '.join(cols)}) VALUES "
                      f"({', '.join(['%s'] * len(cols))})", tuple(row[x] for x in cols))
        c.commit()
        box.run_recent("2026-02-16", now=NOW, connect=lambda: c,
                       get_json=Espn({401825519: SUMMARY}))
        rows = c.execute("""
            SELECT DISTINCT ON (espn_game_id, team_espn_id) team_espn_id, source, o_poss
              FROM ncaab_team_game_stats WHERE espn_game_id IS NOT NULL
             ORDER BY espn_game_id, team_espn_id, (source = 'sportsdataverse_ncaa') DESC
        """).fetchall()
        assert rows == [(120, "sportsdataverse_ncaa", 67.0), (164, "sportsdataverse_ncaa", 67.0)]
        n = c.execute("SELECT count(*) FROM ncaab_team_game_stats").fetchone()[0]
        assert n == 4
    finally:
        c._conn.close()
