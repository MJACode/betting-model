"""The lock-time book shop: captured once, stored as reference.

The grade is DraftKings' own lock price. The shop does not set it.
The migration is unapplied on production. The scratch cluster is local.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from byom.game_facts import (
    capture_game,
    shop_markets_to_replace,
)
from tests.test_byom_game_facts import KICK, _game, _q, _quotes

ROOT = Path(__file__).resolve().parents[1]
SQL = (ROOT / "data/migrations/byom_lock_shop_2026_10_16.sql").read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _spread_shop(window: int):
    _fact, shops = capture_game(_game(), _quotes(), {"BAL": [], "KC": []})
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
    for marker in ("CREATE TABLE", "DROP POLICY", "REVOKE ALL",
                   "ENABLE ROW LEVEL SECURITY"):
        assert ret < code.index(marker), marker
    assert "CREATE POLICY" not in code
    assert "GRANT " not in code
    assert "FORCE ROW LEVEL SECURITY" not in code.upper()


def test_the_skip_guard_refuses_select_and_every_write_verb():
    """A later GRANT of SELECT or UPDATE would still take the early return
    if the guard only named INSERT."""
    code = _code(SQL)
    for role in ("anon", "authenticated"):
        assert f"('{role}')" in code
    for verb in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE",
                 "REFERENCES", "TRIGGER"):
        assert f"('{verb}')" in code
    assert "has_table_privilege(" in code
    assert "public.byom_lock_shop" in code


def test_the_shop_is_worker_only():
    from data.anon_readable import (
        AHEAD_OF_THE_APP, ANON_READABLE, WORKER_ONLY_TABLES)

    assert "byom_lock_shop" not in ANON_READABLE
    assert "byom_lock_shop" not in AHEAD_OF_THE_APP
    assert "byom_lock_shop" in WORKER_ONLY_TABLES


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


def test_the_grade_stays_draftkings_when_a_better_shop_price_is_present():
    fact, shops = capture_game(_game(), _quotes(), {"BAL": [], "KC": []})
    assert fact["grade_spread_home_book"] == "draftkings"
    assert fact["grade_spread_home_price"] == Decimal("-115")
    books = {
        row["bookmaker"] for row in shops
        if row["market"] == "spreads" and row["lock_window_hours"] == 120
    }
    assert books == {"draftkings", "fanduel", "pinnacle"}
    kept = [q for q in _quotes() if q["bookmaker"] != "fanduel"]
    rebuilt, _shops = capture_game(_game(), kept, {"BAL": [], "KC": []})
    assert rebuilt["grade_spread_home_book"] == "draftkings"
    assert rebuilt["grade_spread_home_price"] == Decimal("-115")
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
    # Stored rows are spreads. An h2h market with nothing stored is an insert.
    assert shop_markets_to_replace(fresh, stored) == []


def test_a_moved_h2h_snapshot_replaces_that_market():
    """h2h has no line. The DraftKings snapshot is the lock. Another book's
    timestamp may be earlier inside the shop lag and is not the check."""
    t1 = "2024-09-05T12:00:00+00:00"
    t2 = "2024-09-05T18:00:00+00:00"
    stored = {
        "2024_01_BAL_KC": [
            {"canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
             "market": "h2h", "bookmaker": "draftkings", "snapshot_at": t1},
            {"canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
             "market": "h2h", "bookmaker": "fanduel", "snapshot_at": t1},
        ],
    }
    fresh = [{
        "canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
        "market": "h2h", "bookmaker": "fanduel", "snapshot_at": t2,
        "dk_point": None,
    }, {
        "canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
        "market": "h2h", "bookmaker": "draftkings", "snapshot_at": t2,
        "dk_point": None,
    }]
    assert shop_markets_to_replace(fresh, stored) == [
        ("2024_01_BAL_KC", 120, "h2h")]
    fresh[1]["snapshot_at"] = t1
    assert shop_markets_to_replace(fresh, stored) == []
    stored["2024_01_BAL_KC"] = [
        row for row in stored["2024_01_BAL_KC"]
        if row["bookmaker"] != "draftkings"
    ]
    fresh[1]["snapshot_at"] = t1
    assert shop_markets_to_replace(fresh, stored) == [
        ("2024_01_BAL_KC", 120, "h2h")]


def test_fresh_h2h_books_without_draftkings_replace_a_stored_draftkings_row():
    """A stale stored DraftKings h2h row does not stay when the fresh
    rows for that market have no DraftKings quote."""
    t1 = "2024-09-05T12:00:00+00:00"
    t2 = "2024-09-05T18:00:00+00:00"
    stored = {
        "2024_01_BAL_KC": [
            {"canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
             "market": "h2h", "bookmaker": "draftkings", "snapshot_at": t1},
            {"canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
             "market": "h2h", "bookmaker": "fanduel", "snapshot_at": t1},
        ],
    }
    fresh = [{
        "canonical_key": "2024_01_BAL_KC", "lock_window_hours": 120,
        "market": "h2h", "bookmaker": "fanduel", "snapshot_at": t2,
        "dk_point": None,
    }]
    assert shop_markets_to_replace(fresh, stored) == [
        ("2024_01_BAL_KC", 120, "h2h")]
    stored["2024_01_BAL_KC"] = [
        row for row in stored["2024_01_BAL_KC"]
        if row["bookmaker"] != "draftkings"
    ]
    assert shop_markets_to_replace(fresh, stored) == []


def test_a_moved_draftkings_h2h_snapshot_grades_the_new_price():
    """The grade is the new DraftKings lock. The earlier shop price is
    not the grade, and another book's price at the new snapshot is not
    either. regrade_from_shop is not on this path."""
    from datetime import timedelta

    both = _quotes() + [
        _q(80, "draftkings", "h2h", None, -160, 140),
        _q(80, "fanduel", "h2h", None, -140, 120),
    ]
    fact, _shops = capture_game(_game(), both, {"BAL": [], "KC": []})
    assert fact["grade_ml_home_book"] == "draftkings"
    assert fact["grade_ml_home_price"] == Decimal("-150")
    assert fact["lock_ml_at"] == KICK - timedelta(hours=100)
    early = KICK - timedelta(hours=100)
    moved_quotes = [
        q for q in both
        if not (q["bookmaker"] == "draftkings" and q["market"] == "h2h"
                and q["snapshot_at"] == early)
    ]
    fact2, shops2 = capture_game(_game(), moved_quotes, {"BAL": [], "KC": []})
    assert fact2["grade_ml_home_book"] == "draftkings"
    assert fact2["grade_ml_home_price"] == Decimal("-160")
    assert fact2["grade_ml_away_price"] == Decimal("140")
    assert fact2["lock_ml_at"] == KICK - timedelta(hours=80)
    dk = [
        row for row in shops2
        if row["market"] == "h2h" and row["bookmaker"] == "draftkings"
        and row["lock_window_hours"] == 120
    ]
    assert len(dk) == 1
    assert dk[0]["price_home"] == Decimal("-160")
    assert dk[0]["snapshot_at"] == fact2["lock_ml_at"]
    builder = (ROOT / "byom" / "game_facts.py").read_text(encoding="utf-8")
    load = (ROOT / "byom" / "load.py").read_text(encoding="utf-8")
    assert "regrade_from_shop" not in builder
    assert "regrade_from_shop" not in load


def test_the_shop_apply_warning_fires_only_after_the_date_with_no_rows(caplog):
    import logging
    from datetime import date

    from byom.load import warn_if_shop_apply_window_missed

    class Conn:
        def __init__(self, reg, count):
            self.reg = reg
            self.count = count
            self.sqls = []

        def execute(self, sql, params=None):
            self.sqls.append(sql)
            self.sql = sql
            return self

        def fetchone(self):
            if "count(*)" in self.sql:
                return (self.count,)
            return (self.reg,)

    before = Conn("byom_lock_shop", 0)
    assert warn_if_shop_apply_window_missed(before, today=date(2026, 10, 16)) is None
    assert before.sqls == []
    empty = Conn("byom_lock_shop", 0)
    with caplog.at_level(logging.WARNING, logger="byom.load"):
        missed = warn_if_shop_apply_window_missed(empty, today=date(2026, 10, 17))
    assert missed is not None
    assert "no rows" in missed
    assert "empty table" in missed
    assert "production write" in missed
    assert any(missed in record.message for record in caplog.records)
    assert any("to_regclass" in sql for sql in empty.sqls)
    assert any("count(*)" in sql for sql in empty.sqls)
    present = Conn("byom_lock_shop", 1)
    assert warn_if_shop_apply_window_missed(present, today=date(2026, 10, 17)) is None
    missing = Conn(None, 0)
    assert warn_if_shop_apply_window_missed(
        missing, today=date(2026, 10, 17)) is not None
    assert all("count(*)" not in sql for sql in missing.sqls)
    job = (ROOT / "tracking" / "job_queue.py").read_text(encoding="utf-8")
    start = job.index("def _job_byom_game_facts")
    body = job[start:job.index("\nJOBS =", start)]
    warn_at = body.index("warn_if_shop_apply_window_missed(conn)")
    build_at = body.index("return build_seasons(")
    assert warn_at < build_at


def test_scratch_shop_still_grades_after_the_book_is_deleted():
    from datetime import date, timedelta

    psycopg2 = pytest.importorskip("psycopg2")
    from psycopg2.errors import InsufficientPrivilege

    from byom.load import warn_if_shop_apply_window_missed
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

        class Early:
            def execute(self, sql, params=None):
                c = raw.cursor()
                c.execute(sql, params)
                return c

        early = Early()
        assert warn_if_shop_apply_window_missed(
            early, today=date(2026, 10, 16)) is None
        empty_shop = warn_if_shop_apply_window_missed(
            early, today=date(2026, 10, 17))
        assert empty_shop is not None and "no rows" in empty_shop
        cur.execute("ALTER TABLE byom_lock_shop RENAME TO byom_lock_shop_hidden")
        missing_shop = warn_if_shop_apply_window_missed(
            early, today=date(2026, 10, 17))
        assert missing_shop is not None and "no rows" in missing_shop
        cur.execute("ALTER TABLE byom_lock_shop_hidden RENAME TO byom_lock_shop")
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
        first = build_season(conn, 2024, apply=True)
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
        graded_now = cur.fetchone()
        assert graded_now[0] == "draftkings"
        assert Decimal(str(graded_now[1])) == Decimal("-115")
        assert warn_if_shop_apply_window_missed(
            conn, today=date(2026, 10, 17)) is None
        cur.execute("""
            SELECT grade_ml_home_book, grade_ml_home_price, lock_ml_at
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        ml_now = cur.fetchone()
        assert ml_now[0] == "draftkings"
        assert Decimal(str(ml_now[1])) == Decimal("-150")
        assert ml_now[2] == KICK - timedelta(hours=100)
        cur.execute("""
            DELETE FROM nfl_odds_history
             WHERE bookmaker = 'fanduel' AND game_id = '2024_01_BAL_KC'
        """)
        again = build_season(conn, 2024, apply=True)
        assert again["written"] == 3
        cur.execute("""
            SELECT grade_spread_home_book, grade_spread_home_price
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        graded = cur.fetchone()
        assert graded[0] == "draftkings"
        assert Decimal(str(graded[1])) == Decimal("-115")
        cur.execute("""
            SELECT count(*) FROM byom_lock_shop
             WHERE canonical_key = '2024_01_BAL_KC'
               AND bookmaker = 'fanduel' AND market = 'spreads'
               AND lock_window_hours = 120
        """)
        assert cur.fetchone()[0] == 1
        later = KICK - timedelta(hours=80)
        cur.execute("""
            INSERT INTO nfl_odds_history
              (snapshot_at, game_id, season, week, commence_time, bookmaker,
               market, point, price_home, price_away, lead_hours)
            VALUES
              (%s, '2024_01_BAL_KC', 2024, NULL, %s, 'draftkings', 'h2h',
               NULL, -160, 140, NULL),
              (%s, '2024_01_BAL_KC', 2024, NULL, %s, 'fanduel', 'h2h',
               NULL, -140, 120, NULL)
        """, (later, KICK, later, KICK))
        held = build_season(conn, 2024, apply=True)
        assert held["written"] == 3
        cur.execute("""
            SELECT grade_ml_home_price, lock_ml_at
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        held_ml = cur.fetchone()
        assert Decimal(str(held_ml[0])) == Decimal("-150")
        assert held_ml[1] == KICK - timedelta(hours=100)
        cur.execute("""
            DELETE FROM nfl_odds_history
             WHERE game_id = '2024_01_BAL_KC'
               AND bookmaker = 'draftkings'
               AND market = 'h2h'
               AND snapshot_at = %s
        """, (KICK - timedelta(hours=100),))
        moved = build_season(conn, 2024, apply=True)
        assert moved["written"] == 3
        cur.execute("""
            SELECT grade_ml_home_book, grade_ml_home_price, grade_ml_away_price,
                   lock_ml_at
              FROM byom_game_facts WHERE canonical_key = '2024_01_BAL_KC'
        """)
        graded_ml = cur.fetchone()
        assert graded_ml[0] == "draftkings"
        assert Decimal(str(graded_ml[1])) == Decimal("-160")
        assert Decimal(str(graded_ml[2])) == Decimal("140")
        assert graded_ml[3] == later
        cur.execute("""
            SELECT price_home, snapshot_at
              FROM byom_lock_shop
             WHERE canonical_key = '2024_01_BAL_KC'
               AND market = 'h2h' AND bookmaker = 'draftkings'
               AND lock_window_hours = 120
        """)
        shop_ml = cur.fetchall()
        assert len(shop_ml) == 1
        assert Decimal(str(shop_ml[0][0])) == Decimal("-160")
        assert shop_ml[0][1] == graded_ml[3]
        dry = build_season(conn, 2024, apply=False)
        assert dry["shop"] == 0 and dry["written"] == 0
        raw.commit()
        raw.autocommit = True
        cur = raw.cursor()
        cur.execute("""
            SELECT relrowsecurity FROM pg_class
             WHERE oid = 'public.byom_lock_shop'::regclass
        """)
        assert cur.fetchone()[0] is True
        cur.execute("""
            SELECT count(*) FROM pg_policy
             WHERE polrelid = 'public.byom_lock_shop'::regclass
        """)
        assert cur.fetchone()[0] == 0
        for role in ("anon", "authenticated"):
            for verb in ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE",
                         "REFERENCES", "TRIGGER"):
                cur.execute(
                    "SELECT has_table_privilege(%s, %s, %s)",
                    (role, "public.byom_lock_shop", verb))
                assert cur.fetchone()[0] is False, (role, verb)
        cur.execute("SET ROLE anon")
        with pytest.raises(InsufficientPrivilege):
            cur.execute("SELECT count(*) FROM public.byom_lock_shop")
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
