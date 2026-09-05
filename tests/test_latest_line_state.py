"""The current-state tables behind the "latest line" views, driven through the
real triggers on a real Postgres.

WHY A REAL DATABASE. The migration is plpgsql over transition tables, ON
CONFLICT guards and window functions; a Python re-implementation would test the
re-implementation. So this runs against whatever Postgres LATEST_LINE_TEST_DSN
points at (a scratch cluster: `initdb` + `pg_ctl`; the sandbox carries
/usr/lib/postgresql/16/bin) and SKIPS where there is none -- Matt's Windows
machine, the worker. The static shape is pinned separately in
tests/test_latest_odds_views.py, which always runs.

Every assertion here was watched failing under a mutation of the migration
before it was trusted (docs/sessions/2026-09.md, 2026-09-05).
"""

from __future__ import annotations

import io
import os
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

DSN = os.environ.get("LATEST_LINE_TEST_DSN")
pytestmark = pytest.mark.skipif(
    not DSN, reason="LATEST_LINE_TEST_DSN not set -- needs a scratch Postgres")

ROOT = Path(__file__).parent.parent
MIGRATION = ROOT / "data" / "migrations" / "latest_line_state_tables.sql"

# The log tables as the migration sees them: every column it references, the
# real types. Roles because the migration grants to them and the views run as
# the caller (security_invoker), so the read-through is exercised as the app.
SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO anon, authenticated;
CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, game_date TEXT, home_team TEXT, away_team TEXT, commence_time TEXT);
ALTER TABLE games ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read games" ON games FOR SELECT TO anon, authenticated USING (true);
GRANT SELECT ON games TO anon, authenticated;
CREATE TABLE odds (
    odds_id BIGSERIAL PRIMARY KEY, game_id TEXT, sport TEXT, market TEXT, bookmaker TEXT,
    snapshot_type TEXT, snapshot_at TEXT,
    home_price NUMERIC, away_price NUMERIC, draw_price NUMERIC, spread_home NUMERIC, total_line NUMERIC,
    over_price NUMERIC, under_price NUMERIC, created_at TEXT DEFAULT now()::text,
    home_link TEXT, away_link TEXT, draw_link TEXT, over_link TEXT, under_link TEXT,
    home_sid TEXT, away_sid TEXT, draw_sid TEXT, over_sid TEXT, under_sid TEXT, source TEXT);
CREATE TABLE player_prop_odds (
    prop_id BIGSERIAL PRIMARY KEY, game_id TEXT, game_date TEXT, player_name TEXT, team TEXT, market TEXT,
    bookmaker TEXT DEFAULT 'draftkings', snapshot_type TEXT, snapshot_at TEXT,
    line NUMERIC, over_price NUMERIC, under_price NUMERIC, created_at TEXT DEFAULT now()::text,
    over_link TEXT, under_link TEXT, over_sid TEXT, under_sid TEXT);
CREATE INDEX idx_prop_odds_date ON player_prop_odds(game_date);
CREATE TABLE live_game_state (
    state_id BIGSERIAL PRIMARY KEY, game_id TEXT, snapshot_at TEXT, inning SMALLINT, inning_half TEXT,
    outs SMALLINT, bases_state TEXT, home_score SMALLINT, away_score SMALLINT,
    current_pitcher_id TEXT, current_batter_id TEXT, on_deck_batter_id TEXT,
    abstract_game_state TEXT, raw_state JSONB, created_at TEXT DEFAULT now()::text);
INSERT INTO games VALUES ('G1', 'MLB', '2026-09-05', 'HOU', 'ARI', '2026-09-05T23:16:00Z'),
                         ('G2', 'MLB', '2026-09-05', 'SEA', 'OAK', '2026-09-06T01:41:00Z'),
                         ('G3', 'MLB', '2026-09-06', 'TOR', 'KC',  '2026-09-06T17:11:00Z');
"""


@pytest.fixture
def db():
    conn = psycopg2.connect(DSN)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(SCHEMA)
    cur.execute(io.open(MIGRATION, encoding="utf-8").read())
    yield cur
    conn.close()


def odds(cur, game, market, book, snap, price, snapshot_type="open", **extra):
    cols = dict(game_id=game, sport="MLB", market=market, bookmaker=book,
                snapshot_type=snapshot_type, snapshot_at=snap, home_price=price, **extra)
    keys = ", ".join(cols)
    cur.execute(f"INSERT INTO odds ({keys}) VALUES ({', '.join('%s' for _ in cols)}) RETURNING odds_id",
                list(cols.values()))
    return cur.fetchone()[0]


def prop(cur, game, market, player, book, snap, line, over, snapshot_type="open", game_date="2026-09-05"):
    cur.execute(
        "INSERT INTO player_prop_odds (game_id, game_date, player_name, team, market, bookmaker, "
        "snapshot_type, snapshot_at, line, over_price) VALUES (%s,%s,%s,'HOU',%s,%s,%s,%s,%s,%s) RETURNING prop_id",
        (game, game_date, player, market, book, snapshot_type, snap, line, over))
    return cur.fetchone()[0]


def as_app(cur, sql, role="authenticated"):
    """Run a read the way PostgREST does: as the API role, through RLS."""
    cur.execute(f"SET ROLE {role}")
    try:
        cur.execute(sql)
        return cur.fetchall()
    finally:
        cur.execute("RESET ROLE")


# ── odds → latest_odds ───────────────────────────────────────────────────────

def test_a_newer_snapshot_replaces_and_an_older_one_is_ignored(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T12:00:00Z", -120)
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T11:00:00Z", -999)   # late arrival
    rows = as_app(db, "SELECT home_price, snapshot_at FROM v_latest_dk_odds WHERE game_id = 'G1'")
    assert rows == [(-120, "2026-09-05T12:00:00Z")]


def test_in_play_rows_never_become_the_latest_pre_game_line(db):
    odds(db, "G1", "totals", "draftkings", "2026-09-05T10:00:00Z", -110, total_line=8.5)
    odds(db, "G1", "totals", "draftkings", "2026-09-06T00:30:00Z", -150, total_line=6.5, snapshot_type="in_play")
    rows = as_app(db, "SELECT total_line FROM v_latest_dk_odds WHERE game_id = 'G1'")
    assert rows == [(8.5,)], "the DK view returned the in-play price as the latest line"
    # A key whose only rows are in-play has no state row -- as it had no view row.
    odds(db, "G2", "totals", "draftkings", "2026-09-06T02:00:00Z", -150, snapshot_type="in_play")
    assert as_app(db, "SELECT count(*) FROM v_latest_dk_odds WHERE game_id = 'G2'") == [(0,)]


def test_every_book_is_kept_and_the_consensus_is_hidden_from_the_all_books_view(db):
    for book in ("draftkings", "fanduel", "sbr_consensus"):
        odds(db, "G1", "h2h", book, "2026-09-05T10:00:00Z", -105)
    rows = as_app(db, "SELECT bookmaker FROM v_latest_odds_all_books WHERE game_id = 'G1' ORDER BY 1")
    assert rows == [("draftkings",), ("fanduel",)]
    db.execute("SELECT count(*) FROM latest_odds WHERE game_id = 'G1'")
    assert db.fetchone() == (3,), "the state table is the faithful record; the view applies the exclusion"
    # The models only ever DECIDE on DraftKings (§6): the DK view is DK alone.
    assert as_app(db, "SELECT count(*) FROM v_latest_dk_odds WHERE game_id = 'G1'") == [(1,)]


def test_a_bulk_insert_costs_one_upsert_per_key_and_keeps_the_newest_of_the_batch(db):
    db.execute("""
        INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, home_price)
        SELECT 'G1', 'MLB', 'h2h', 'draftkings', 'open', '2026-09-05T10:' || lpad(i::text, 2, '0') || ':00Z', -100 - i
          FROM generate_series(0, 59) i""")
    assert as_app(db, "SELECT home_price FROM v_latest_dk_odds WHERE game_id = 'G1'") == [(-159,)]


def test_relabelling_the_latest_row_as_in_play_falls_back_to_the_previous_pre_game_row(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    last = odds(db, "G1", "h2h", "draftkings", "2026-09-05T23:20:00Z", -140)
    # odds_ingestor._mark_in_play: a row stamped after first pitch is in-play.
    db.execute("UPDATE odds SET snapshot_type = 'in_play' WHERE odds_id = %s", (last,))
    assert as_app(db, "SELECT home_price FROM v_latest_dk_odds WHERE game_id = 'G1'") == [(-110,)]
    # ...and the reverse repair (repair_bogus_first_pitch_labels) restores it.
    db.execute("UPDATE odds SET snapshot_type = 'open' WHERE odds_id = %s", (last,))
    assert as_app(db, "SELECT home_price FROM v_latest_dk_odds WHERE game_id = 'G1'") == [(-140,)]


def test_the_date_filter_is_answered_from_games(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    odds(db, "G3", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    rows = as_app(db, "SELECT game_id FROM v_latest_dk_odds WHERE game_date = '2026-09-06'")
    assert rows == [("G3",)]


# ── player_prop_odds → latest_prop_odds ──────────────────────────────────────

def test_a_standard_market_keeps_one_row_even_when_the_line_moves(db):
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -250)
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T12:00:00-04:00", 1.5, +150)
    rows = as_app(db, "SELECT line, over_price FROM v_latest_prop_odds_all_books WHERE game_id = 'G1'")
    assert rows == [(1.5, 150)], "the morning 0.5 is still standing beside the evening 1.5"


def test_an_alternate_market_keeps_every_line_of_the_newest_pass_only(db):
    # executemany writes one row per statement, so the trigger sees the lines
    # of one pass one at a time and must not retire its siblings.
    for line, price in ((1.5, -120), (2.5, +180), (3.5, +500)):
        prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", line, price)
    rows = as_app(db, "SELECT line FROM v_latest_prop_odds_all_books WHERE game_id = 'G1' ORDER BY 1")
    assert rows == [(1.5,), (2.5,), (3.5,)]
    # The next pass posts only two ladders: the newest snapshot REPLACES the set.
    for line, price in ((1.5, -130), (2.5, +170)):
        prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T12:00:00-04:00", line, price)
    rows = as_app(db, "SELECT line, over_price FROM v_latest_prop_odds_all_books WHERE game_id = 'G1' ORDER BY 1")
    assert rows == [(1.5, -130), (2.5, 170)], "the 08:00 pass's 3.5 outlived the 12:00 pass"


def test_a_late_row_for_an_alternate_market_cannot_add_a_stale_line(db):
    prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T12:00:00-04:00", 1.5, -130)
    prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 3.5, +500)
    rows = as_app(db, "SELECT line FROM v_latest_prop_odds_all_books WHERE game_id = 'G1'")
    assert rows == [(1.5,)]


def test_books_and_players_are_independent_keys(db):
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -250)
    prop(db, "G1", "batter_hits", "Carlos Santana", "fanduel", "2026-09-05T08:00:00-04:00", 0.5, -240)
    prop(db, "G1", "batter_hits", "Jose Altuve", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -200)
    rows = as_app(db, "SELECT player_name, bookmaker FROM v_latest_prop_odds_all_books WHERE game_id = 'G1' ORDER BY 1, 2")
    assert rows == [("Carlos Santana", "draftkings"), ("Carlos Santana", "fanduel"), ("Jose Altuve", "draftkings")]


def test_relabelling_a_prop_row_recomputes_its_key_from_the_log(db):
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -250)
    last = prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T19:30:00-04:00", 0.5, -400)
    db.execute("UPDATE player_prop_odds SET snapshot_type = 'in_play' WHERE prop_id = %s", (last,))
    assert as_app(db, "SELECT over_price FROM v_latest_prop_odds_all_books WHERE game_id = 'G1'") == [(-250,)]


def test_the_stats_read_shape_returns_only_the_market_asked_for(db):
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -250)
    prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 1.5, +150)
    prop(db, "G1", "batter_home_runs", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, +400)
    rows = as_app(db, """SELECT market, line FROM v_latest_prop_odds_all_books
                          WHERE game_date = '2026-09-05' AND market IN ('batter_hits', 'batter_hits_alternate')
                          ORDER BY game_id, market, player_name, bookmaker, line""")
    assert rows == [("batter_hits", 0.5), ("batter_hits_alternate", 1.5)]


# ── live_game_state → latest_live_game_state ─────────────────────────────────

def test_the_live_view_is_the_newest_snapshot_with_state_id_breaking_ties(db):
    # One statement per snapshot, as the poller writes them: the tie between
    # the two 23:45 rows is decided by the upsert guard, not by ordering
    # inside a single batch.
    for snap, inning, score in (("2026-09-05T23:30:00Z", 1, 0), ("2026-09-05T23:45:00Z", 2, 1),
                                ("2026-09-05T23:45:00Z", 2, 2)):
        db.execute("INSERT INTO live_game_state (game_id, snapshot_at, inning, home_score) VALUES ('G1', %s, %s, %s)",
                   (snap, inning, score))
    rows = as_app(db, "SELECT inning, home_score FROM v_live_game_state_latest WHERE game_date = '2026-09-05'")
    assert rows == [(2, 2)]
    db.execute("INSERT INTO live_game_state (game_id, snapshot_at, inning, home_score) VALUES ('G1', '2026-09-05T23:40:00Z', 9, 9)")
    assert as_app(db, "SELECT inning FROM v_live_game_state_latest") == [(2,)], "an older snapshot overwrote the newest"


# ── rebuild from the log ─────────────────────────────────────────────────────

def test_the_rebuild_reproduces_the_trigger_state_and_never_regresses_it(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T12:00:00Z", -120)
    for line, price in ((1.5, -120), (2.5, +180)):
        prop(db, "G1", "batter_hits_alternate", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", line, price)
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T08:00:00-04:00", 0.5, -250)
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T12:00:00-04:00", 1.5, +150)
    db.execute("INSERT INTO live_game_state (game_id, snapshot_at, inning) VALUES ('G1', '2026-09-05T23:30:00Z', 1), ('G1', '2026-09-05T23:45:00Z', 2)")

    def state():
        db.execute("SELECT * FROM latest_odds ORDER BY 1,2,3"); a = db.fetchall()
        db.execute("SELECT * FROM latest_prop_odds ORDER BY 1,2,3,4,5"); b = db.fetchall()
        db.execute("SELECT * FROM latest_live_game_state ORDER BY 1"); c = db.fetchall()
        return a, b, c

    by_trigger = state()
    db.execute("TRUNCATE latest_odds, latest_prop_odds, latest_live_game_state")
    # The odds rebuild runs by snapshot_at range; split the key's rows across
    # two ranges to prove the newest wins whichever order the chunks run in.
    db.execute("SELECT latest_lines_rebuild_odds('2026-09-05T11:00:00Z', '2026-09-06')")
    db.execute("SELECT latest_lines_rebuild_odds('2026-09-05', '2026-09-05T11:00:00Z')")
    db.execute("SELECT latest_lines_rebuild_props('2026-09-05', '2026-09-06')")
    db.execute("SELECT latest_lines_rebuild_live_state()")
    assert state() == by_trigger
    # Re-running is a no-op, and a rebuild beside live ingestion cannot undo a
    # newer trigger-written row.
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T14:00:00Z", -130)
    prop(db, "G1", "batter_hits", "Carlos Santana", "draftkings", "2026-09-05T14:00:00-04:00", 1.5, +140)
    db.execute("SELECT latest_lines_rebuild_odds('2026-09-05', '2026-09-05T11:00:00Z')")
    db.execute("SELECT latest_lines_rebuild_props('2026-09-05', '2026-09-06')")
    assert as_app(db, "SELECT home_price FROM v_latest_dk_odds WHERE game_id = 'G1'") == [(-130,)]
    assert as_app(db, "SELECT over_price FROM v_latest_prop_odds_all_books WHERE market = 'batter_hits'") == [(140,)]


# ── access ───────────────────────────────────────────────────────────────────

def test_the_api_roles_can_read_but_never_write_the_state_tables(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    for role in ("anon", "authenticated"):
        assert as_app(db, "SELECT count(*) FROM latest_odds", role) == [(1,)]
        db.execute(f"SET ROLE {role}")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            db.execute("DELETE FROM latest_odds")
        db.execute("RESET ROLE")
    db.execute("SELECT relrowsecurity FROM pg_class WHERE relname IN ('latest_odds', 'latest_prop_odds', 'latest_live_game_state')")
    assert db.fetchall() == [(True,)] * 3


def test_the_migration_is_idempotent(db):
    odds(db, "G1", "h2h", "draftkings", "2026-09-05T10:00:00Z", -110)
    db.execute(io.open(MIGRATION, encoding="utf-8").read())
    db.execute("SELECT count(*) FROM latest_odds")
    assert db.fetchone() == (1,), "a re-run emptied or duplicated the state"
    db.execute("SELECT count(*) FROM pg_trigger WHERE tgname LIKE 'trg_latest_%'")
    assert db.fetchone() == (5,)
