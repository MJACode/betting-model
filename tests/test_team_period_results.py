"""Team betting results by period: the migration, the writer, the purchase and the wiring.

Runs the writer on a scratch Postgres. What it pins:
  - the line is DraftKings' newest PRE-TIP row; an in_play row and a row
    stamped after the tip are never the line, whatever their snapshot_type
  - with no DraftKings row the line is the other books' median, to the half
    point, and spread_source says so
  - the away side's spread is the negated home number (CLAUDE.md section 4):
    an away underdog that loses by less than the number covers
  - a total equal to the points is a push; ATS likewise
  - H1 = periods 1 + 2, only when both are stored; Q4 is period 4 alone,
    overtime not added; FG is the final score, overtime included
  - rest days come from every game of the season, opponent's too
  - a re-run rewrites nothing unchanged; a second pass of the migration
    returns before any DDL; anon can read and cannot write
  - the daily purchase refuses when the credit plan does, and buys nothing
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (ROOT / "data" / "migrations" / "add_team_period_results_2026_11_13.sql").read_text(
    encoding="utf-8")


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


SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
CREATE TABLE games (game_id text primary key, sport text, season int, game_date text, commence_time text,
                    home_team text, away_team text, home_score int, away_score int);
CREATE TABLE nba_period_scores (game_id text, period int, home_points int, away_points int,
                                source text, primary key (game_id, period));
CREATE TABLE odds (game_id text, market text, bookmaker text, snapshot_type text, snapshot_at text,
                   spread_home numeric, total_line numeric, source text);
"""

G1 = "NBA_2026-10-21_NYK_BOS"   # BOS home 110-100 over NYK, went to overtime
G2 = "NBA_2026-10-23_LAL_NYK"   # NYK home 99-101 to LAL
G3 = "NBA_2026-10-25_BOS_LAL"   # scheduled, not played: rest days only

FIXTURE = f"""
INSERT INTO games VALUES
 ('{G1}','NBA',2027,'2026-10-21','2026-10-21T23:30:00Z','BOS','NYK',110,100),
 ('{G2}','NBA',2027,'2026-10-23','2026-10-23T23:30:00Z','NYK','LAL',99,101),
 ('{G3}','NBA',2027,'2026-10-25','2026-10-25T23:30:00Z','LAL','BOS',NULL,NULL);
-- G1 quarters 25-24, 25-26, 25-25, 23-23 (98-98), overtime 12-2.
INSERT INTO nba_period_scores VALUES
 ('{G1}',1,25,24,'t'), ('{G1}',2,25,26,'t'), ('{G1}',3,25,25,'t'), ('{G1}',4,23,23,'t'), ('{G1}',5,12,2,'t'),
 ('{G2}',1,30,20,'t');   -- G2 has only its first quarter stored: no H1 row
INSERT INTO odds VALUES
 -- G1 full game: DraftKings -5.5 at 23:00, then an in_play -20 and a post-tip 'open' -9.
 ('{G1}','spreads','draftkings','open','2026-10-21T22:00:00Z',-4.5,NULL,NULL),
 ('{G1}','spreads','draftkings','open','2026-10-21T23:00:00Z',-5.5,NULL,NULL),
 ('{G1}','spreads','draftkings','in_play','2026-10-21T23:10:00Z',-20,NULL,NULL),
 ('{G1}','spreads','draftkings','open','2026-10-21T23:45:00Z',-9,NULL,NULL),
 ('{G1}','totals','draftkings','open','2026-10-21T23:00:00Z',NULL,210,NULL),
 -- G1 first quarter: no DraftKings; three books, median -1.5.
 ('{G1}','spreads_q1','fanduel','close','2026-10-21T23:25:00Z',-1.5,NULL,'x'),
 ('{G1}','spreads_q1','betmgm','close','2026-10-21T23:25:00Z',-2.0,NULL,'x'),
 ('{G1}','spreads_q1','pinnacle','close','2026-10-21T23:25:00Z',-1.0,NULL,'x'),
 -- G1 fourth quarter total 46: the regulation quarter is 46 (push), with overtime it would be 60.
 ('{G1}','totals_q4','draftkings','close','2026-10-21T23:25:00Z',NULL,46,'x'),
 -- G1 first half total 100.5: 100 points, under.
 ('{G1}','totals_h1','draftkings','close','2026-10-21T23:25:00Z',NULL,100.5,'x'),
 -- G2: NYK -3 at home, lost by 2; LAL +3 covers.
 ('{G2}','spreads','draftkings','open','2026-10-23T23:00:00Z',-3,NULL,NULL);
"""


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql, params=None):
        cur = self.raw.cursor()
        cur.execute(sql, params)
        return cur

    def commit(self):
        pass


@pytest.fixture(scope="module")
def db():
    cluster, conn = _scratch()
    try:
        cur = conn.cursor()
        cur.execute(SCHEMA)
        cur.execute(FIXTURE)
        cur.execute(MIGRATION)
        yield conn
    finally:
        conn.close()
        cluster.stop()


def _rebuild(conn):
    from data.ingestors.team_period_results import rebuild
    return rebuild(_Conn(conn), "NBA", [2027])


def _row(conn, game, team, period):
    cur = conn.cursor()
    cur.execute("SELECT pts_for, pts_against, spread, total_line, spread_source, total_source, ats, ou, "
                "rest_days, opp_rest_days FROM team_period_results "
                "WHERE game_id = %s AND team = %s AND period = %s", (game, team, period))
    return cur.fetchone()


def test_full_game_line_is_draftkings_newest_pre_tip_row(db):
    _rebuild(db)
    pf, pa, spread, total, s_src, t_src, ats, ou, *_ = _row(db, G1, "BOS", "FG")
    assert (pf, pa) == (110, 100)                       # overtime included
    assert float(spread) == -5.5 and s_src == "draftkings"
    assert ats == "W"                                   # +10 - 5.5
    assert float(total) == 210 and ou == "P"            # 210 points on 210


def test_away_side_takes_the_negated_home_number(db):
    _rebuild(db)
    lal = _row(db, G2, "LAL", "FG")
    nyk = _row(db, G2, "NYK", "FG")
    assert float(lal[2]) == 3 and lal[6] == "W"         # lost by... won by 2 as +3 dog: covers
    assert float(nyk[2]) == -3 and nyk[6] == "L"


def test_consensus_median_when_draftkings_has_no_line(db):
    _rebuild(db)
    pf, pa, spread, _t, s_src, _ts, ats, ou, *_ = _row(db, G1, "BOS", "Q1")
    assert (pf, pa) == (25, 24)
    assert float(spread) == -1.5 and s_src == "consensus"
    assert ats == "L"                                   # +1 - 1.5
    assert ou is None                                   # no first-quarter total stored
    nyk = _row(db, G1, "NYK", "Q1")
    assert float(nyk[2]) == 1.5 and nyk[6] == "W"


def test_h1_sums_two_periods_and_needs_both(db):
    _rebuild(db)
    pf, pa, _s, total, *_rest = _row(db, G1, "BOS", "H1")
    assert (pf, pa) == (50, 50) and float(total) == 100.5
    assert _row(db, G1, "BOS", "H1")[7] == "U"
    assert _row(db, G2, "NYK", "H1") is None


def test_q4_is_the_regulation_quarter_without_overtime(db):
    _rebuild(db)
    pf, pa, _s, total, _ss, _ts, ats, ou, *_ = _row(db, G1, "BOS", "Q4")
    assert (pf, pa) == (23, 23)
    assert float(total) == 46 and ou == "P"
    assert ats is None                                  # no fourth-quarter spread stored


def test_rest_days_from_every_game_of_the_season(db):
    _rebuild(db)
    # NYK: 10-21 then 10-23 (2 days); LAL's first game is 10-23 (no prior game).
    assert _row(db, G2, "NYK", "FG")[8:] == (2, None)
    assert _row(db, G2, "LAL", "FG")[8:] == (None, 2)
    cur = db.cursor()
    cur.execute("SELECT count(*) FROM team_period_results WHERE game_id = %s", (G3,))
    assert cur.fetchone()[0] == 0                        # an unplayed game has no rows


def test_a_rerun_rewrites_nothing_unchanged(db):
    _rebuild(db)
    assert _rebuild(db)["rows"] == 0


def test_anon_reads_and_cannot_write(db):
    _rebuild(db)
    cur = db.cursor()
    cur.execute("SELECT has_table_privilege('anon', 'team_period_results', 'SELECT'), "
                "has_table_privilege('anon', 'team_period_results', 'INSERT')")
    assert cur.fetchone() == (True, False)


def test_a_second_pass_returns_before_any_ddl(db):
    cur = db.cursor()
    cur.execute("SELECT xmin::text FROM pg_class WHERE oid = 'public.team_period_results'::regclass")
    before = cur.fetchone()[0]
    cur.execute(MIGRATION)
    cur.execute("SELECT xmin::text FROM pg_class WHERE oid = 'public.team_period_results'::regclass")
    assert cur.fetchone()[0] == before


# ── no database ─────────────────────────────────────────────────────────────

def test_registered_readable_and_wired_into_the_nba_step():
    from data.anon_readable import all_readable
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert "add_team_period_results_2026_11_13.sql" in ACTIVE_MIGRATIONS
    assert "team_period_results" in all_readable()
    src = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")
    step = src[src.index("def step_nba_quarters"):src.index("def step_nba_schedule")]
    assert "buy_period_lines_daily" in step and "team_period_results" in step
    assert step.index("buy_period_lines_daily") < step.index("tpr_rebuild(conn")


def test_period_markets_cover_every_period():
    from data.ingestors.nba_odds_history import PERIOD_LINE_MARKETS
    from data.ingestors.team_period_results import PERIOD_MARKETS, PERIODS

    assert set(PERIOD_MARKETS) == set(PERIODS)
    bought = {m for p, pair in PERIOD_MARKETS.items() if p != "FG" for m in pair}
    assert bought == set(PERIOD_LINE_MARKETS)


def test_parse_period_lines_keys_the_home_number():
    from data.ingestors.nba_odds_history import parse_period_lines

    rows = parse_period_lines([
        {"key": "spreads_q3", "outcomes": [
            {"name": "Boston Celtics", "point": -1.5, "price": -110},
            {"name": "New York Knicks", "point": 1.5, "price": -110}]},
        {"key": "totals_q2", "outcomes": [
            {"name": "Over", "point": 56.5, "price": -110},
            {"name": "Under", "point": 56.5, "price": -110}]},
        {"key": "h2h_q1", "outcomes": []},
    ], "Boston Celtics", "BOS", "NYK")
    by = {r["market"]: r for r in rows}
    assert set(by) == {"spreads_q3", "totals_q2"}
    assert by["spreads_q3"]["spread_home"] == -1.5
    assert by["totals_q2"]["total_line"] == 56.5


def test_daily_purchase_refuses_when_the_plan_does(monkeypatch):
    import config
    from data.ingestors import nba_odds_history as h
    from data.ingestors import odds_quota

    monkeypatch.setattr(config, "ODDS_API_KEY", "dummy")
    monkeypatch.setattr(h, "_known_games", lambda conn, a, b: {"G": {"game_id": "G"}})
    monkeypatch.setattr(h, "_period_lines_done", lambda conn, ids: set())
    seen = {}

    def plan(conn, **kw):
        seen.update(kw)
        return None, ["no measured burn rate"]

    monkeypatch.setattr(odds_quota, "plan_credit_budget", plan)
    bought = []
    monkeypatch.setattr(h, "buy_period_lines", lambda *a, **k: bought.append(1) or {})
    out = h.buy_period_lines_daily(object(), 2027)
    assert out["skipped"] == ["no measured burn rate"] and not bought
    assert seen["credits_per_call"] == 10 * len(h.PERIOD_LINE_MARKETS) + 1
    assert seen["shard_calls"] == seen["total_calls"] == 1


def test_the_bought_period_lines_are_never_pruned():
    from data import prune_odds
    from data.ingestors.nba_odds_history import PERIOD_LINE_SOURCE

    assert PERIOD_LINE_SOURCE in prune_odds.PROTECTED_SOURCES
