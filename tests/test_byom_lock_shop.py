"""The lock-time book shop: captured once, then the grade survives pruning.

The migration is unapplied on production. The scratch cluster is local.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from byom.game_facts import (
    capture_game,
    regrade_from_shop,
    shop_markets_to_replace,
)
from tests.test_byom_game_facts import BOOKS, _game, _quotes

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "data/migrations/byom_lock_shop_2026_10_16.sql").read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _spread_shop(window: int):
    _fact, shops = capture_game(_game(), _quotes(), {"BAL": [], "KC": []}, BOOKS)
    return [
        row for row in shops
        if row["market"] == "spreads" and row["lock_window_hours"] == window
    ]


def test_the_migration_is_one_statement_and_unconfirmed_windows_are_not_checks():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert "byom_lock_shop_2026_10_16.sql" in ACTIVE_MIGRATIONS
    assert SQL.count("DO $mig$") == 1
    assert SQL.strip().endswith(";")
    code = _code(SQL)
    assert code.count("$mig$") == 2
    assert "CONCURRENTLY" not in code.upper()
    assert "120" not in code
    assert "24" not in code
    assert "UNCONFIRMED" in SQL
    assert "public.picks" not in code
    assert "v_public_track_record" not in code
    ret = code.index("RETURN;")
    for marker in ("CREATE TABLE", "REVOKE ALL", "ENABLE ROW LEVEL SECURITY",
                   "CREATE POLICY"):
        assert ret < code.index(marker), marker


def test_the_shop_is_on_the_anon_read_list_ahead_of_the_app():
    from data.anon_readable import AHEAD_OF_THE_APP, ANON_READABLE

    assert "byom_lock_shop" in ANON_READABLE
    assert "byom_lock_shop" in AHEAD_OF_THE_APP


def test_the_shop_keeps_every_book_at_the_draftkings_line():
    rows = _spread_shop(120)
    by_book = {row["bookmaker"]: row for row in rows}
    assert set(by_book) == {"draftkings", "fanduel", "pinnacle"}
    assert by_book["fanduel"]["price_home"] == Decimal("-105")
    assert by_book["fanduel"]["point"] == Decimal("-3")
    assert by_book["pinnacle"]["price_home"] == Decimal("-100")
    # The -2.5 at the same timestamp is a different number.
    assert all(row["point"] == Decimal("-3") for row in rows)
    near = _spread_shop(24)
    assert [row["bookmaker"] for row in near] == ["draftkings"]
    assert near[0]["point"] == Decimal("-3.5")


def test_a_stored_shop_is_the_grade_after_the_live_quote_is_gone():
    fact, shops = capture_game(_game(), _quotes(), {"BAL": [], "KC": []}, BOOKS)
    assert fact["grade_spread_home_book"] == "fanduel"
    kept = [q for q in _quotes() if q["bookmaker"] != "fanduel"]
    rebuilt, _shops = capture_game(_game(), kept, {"BAL": [], "KC": []}, BOOKS)
    assert rebuilt["grade_spread_home_book"] == "draftkings"
    stored = [row for row in shops if row["lock_window_hours"] == 120]
    regrade_from_shop(rebuilt, stored, BOOKS)
    assert rebuilt["grade_spread_home_book"] == "fanduel"
    assert rebuilt["grade_spread_home_price"] == Decimal("-105")
    assert rebuilt["ats_home_units_uncapped"] == Decimal("1")
    assert rebuilt["ats_home_units_capped"] == Decimal("1.0000")


def test_a_moved_draftkings_line_replaces_that_market():
    stored = {
        "2024_01_BAL_KC": [{
            "canonical_key": "2024_01_BAL_KC",
            "lock_window_hours": 120,
            "market": "spreads",
            "dk_point": Decimal("-3"),
        }],
    }
    fresh = [{
        "canonical_key": "2024_01_BAL_KC",
        "lock_window_hours": 120,
        "market": "spreads",
        "dk_point": Decimal("-3.5"),
    }]
    assert shop_markets_to_replace(fresh, stored) == [
        ("2024_01_BAL_KC", 120, "spreads")]
    fresh[0]["dk_point"] = Decimal("-3")
    assert shop_markets_to_replace(fresh, stored) == []
    fresh[0]["market"] = "h2h"
    fresh[0]["dk_point"] = None
    assert shop_markets_to_replace(fresh, stored) == []


def test_scratch_shop_still_grades_after_the_book_is_deleted():
    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2.errors import InsufficientPrivilege

    from tests.byom_scratch import ScratchPostgres, pg_bin
    from tests.test_byom_game_facts import _load_fixture

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")

    cluster = ScratchPostgres()
    raw = None
    try:
        raw = psycopg2.connect(cluster.start())
        raw.autocommit = True
        cur = raw.cursor()
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
        cur.execute("""
            CREATE TABLE games (
              game_id text PRIMARY KEY, sport text, season int, week int,
              game_date text, home_team text, away_team text,
              home_score numeric, away_score numeric, commence_time text);
            CREATE TABLE nfl_odds_history (
              snapshot_at timestamptz NOT NULL, game_id text NOT NULL,
              season smallint, week smallint, commence_time timestamptz,
              bookmaker text NOT NULL, market text NOT NULL,
              point numeric, price_home numeric, price_away numeric,
              lead_hours numeric,
              PRIMARY KEY (snapshot_at, game_id, bookmaker, market));
            CREATE TABLE odds (
              odds_id bigserial PRIMARY KEY, game_id text, sport text,
              market text, bookmaker text, snapshot_type text, snapshot_at text,
              home_price numeric, away_price numeric, spread_home numeric,
              total_line numeric, over_price numeric, under_price numeric);
        """)
        for name in ("byom_facts_schema_2026_10_16.sql",
                     "byom_game_facts_units_2026_10_16.sql",
                     "byom_lock_shop_2026_10_16.sql"):
            text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
            cur.execute(text)
            cur.execute(text)
        _load_fixture(cur)
        raw.autocommit = False
        from byom.load import build_season

        class Conn:
            def execute(self, sql, params=None):
                c = raw.cursor()
                c.execute(sql, params)
                return c

            def executemany(self, sql, seq):
                c = raw.cursor()
                c.executemany(sql, seq)
                return c

            def commit(self):
                raw.commit()

        conn = Conn()
        first = build_season(conn, 2024, apply=True, books=BOOKS)
        assert first["written"] == 3
        assert first["shop"] > 0
        cur = raw.cursor()
        cur.execute("""
            SELECT bookmaker, price_home
              FROM byom_lock_shop
             WHERE canonical_key = '2024_01_BAL_KC'
               AND market = 'spreads' AND lock_window_hours = 120
             ORDER BY bookmaker
        """)
        shop = cur.fetchall()
        assert [row[0] for row in shop] == ["draftkings", "fanduel", "pinnacle"]
        cur.execute("""
            SELECT grade_spread_home_book, grade_spread_home_price
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        assert cur.fetchone()[0] == "fanduel"
        cur.execute("""
            DELETE FROM nfl_odds_history
             WHERE bookmaker = 'fanduel' AND game_id = '2024_01_BAL_KC'
        """)
        again = build_season(conn, 2024, apply=True, books=BOOKS)
        assert again["written"] == 3
        cur.execute("""
            SELECT grade_spread_home_book, grade_spread_home_price
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        graded = cur.fetchone()
        assert graded[0] == "fanduel"
        assert Decimal(str(graded[1])) == Decimal("-105")
        cur.execute("""
            SELECT count(*) FROM byom_lock_shop
             WHERE canonical_key = '2024_01_BAL_KC'
               AND bookmaker = 'fanduel' AND market = 'spreads'
               AND lock_window_hours = 120
        """)
        assert cur.fetchone()[0] == 1
        dry = build_season(conn, 2024, apply=False, books=BOOKS)
        assert dry["shop"] == 0 and dry["written"] == 0
        raw.commit()
        raw.autocommit = True
        cur = raw.cursor()
        cur.execute("SET ROLE anon")
        cur.execute("SELECT count(*) FROM public.byom_lock_shop")
        assert cur.fetchone()[0] > 0
        with pytest.raises(InsufficientPrivilege):
            cur.execute(
                "INSERT INTO public.byom_lock_shop "
                "(canonical_key, sport, season, week, lock_window_hours, "
                "market, bookmaker, line_source) "
                "VALUES ('2024_01_BAL_KC', 'NFL', 2024, 1, 120, 'spreads', "
                "'draftkings', 'nfl_odds_history')")
        cur.execute("RESET ROLE")
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
