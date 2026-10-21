"""Best line among the member's books, graded with the published stake.

The migration is not in ACTIVE_MIGRATIONS and is not applied here.
Scratch Postgres is local. The DraftKings path stays the stored results.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_book_quotes_2026_10_21.sql"
KICK = datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)
USER_A = "11111111-1111-1111-1111-111111111111"


def _sql(name: str) -> str:
    return (ROOT / "data/migrations" / name).read_text(encoding="utf-8")


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def test_the_migration_is_unregistered_and_leaves_the_old_files_alone():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert SQL_NAME not in ACTIVE_MIGRATIONS
    sql = _sql(SQL_NAME)
    code = _code(sql)
    assert "NOT in data/view_migrations.ACTIVE_MIGRATIONS" in sql
    assert "byom_best_line_v1" in sql
    assert "byom_backtest_v1" in sql
    assert "byom_saved_models_v1" in sql
    assert "SET statement_timeout = '3s'" in code
    assert "in-function 3s timeout does not apply" in sql
    assert "anon 3s" in sql and "authenticated 8s" in sql
    assert "published_pick_unit_profit" in sql
    assert "published_pick_unit_risked" in sql
    assert "idx_byom_game_book_quotes_fact_book" in sql
    assert "idx_byom_prop_book_quotes_fact_book" in sql
    assert "(fact_id, book)" in sql
    assert "CONCURRENTLY" not in code
    assert "insert into picks" not in sql.lower()
    assert code.index("RETURN;") < code.index("CREATE FUNCTION")
    for name in (
        "byom_facts_schema_2026_10_16.sql",
        "byom_saved_models_2026_10_16.sql",
        "byom_backtest_rpc_2026_10_16.sql",
    ):
        old = _sql(name)
        assert "byom_best_line_v1" not in old
        assert "byom_game_book_quotes" not in old
    load = (ROOT / "byom" / "load.py").read_text(encoding="utf-8")
    props = (ROOT / "byom" / "prop_load.py").read_text(encoding="utf-8")
    assert "write_game_quotes" in load
    assert "price_home" not in load
    assert "'h2h'" not in load
    assert "write_prop_quotes" in props
    assert "over_price" not in props


def _quote(book, hours, line, over=-110, under=-110, captured=None,
           prop_id=1, market="player_pass_yds", name="Lamar Jackson"):
    snap = KICK - timedelta(hours=hours)
    return {
        "player_name": name,
        "team": "BAL",
        "market": market,
        "bookmaker": book,
        "snapshot_at": snap,
        "commence_time": KICK,
        "point": None if line is None else Decimal(str(line)),
        "over_price": over,
        "under_price": under,
        "prop_id": prop_id,
        "captured_at": snap if captured is None else captured,
    }


def test_each_book_keeps_its_own_last_pre_kickoff_line():
    from byom.book_quotes import game_quote_rows, prop_quote_rows, write_game_quotes
    from byom.prop_facts import ANYTIME_TD_MARKET, player_key

    key = player_key("Lamar Jackson")
    facts = [
        {
            "player_key": key,
            "market": "player_pass_yds",
            "prop_key": "2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5",
        },
        {
            "player_key": key,
            "market": ANYTIME_TD_MARKET,
            "prop_key": "2026_01_BAL_KC|player_anytime_td|lamar jackson|0.5",
        },
    ]
    later = KICK - timedelta(hours=1, minutes=5)
    earlier = KICK - timedelta(hours=1, minutes=30)
    rows = prop_quote_rows(facts, [
        _quote("fanduel", 10, 200.5),
        _quote("fanduel", 1, 260.5, captured=earlier, prop_id=1),
        _quote("fanduel", 1, 240.5, captured=later, prop_id=2),
        _quote("fanduel", 1, None, captured=KICK - timedelta(minutes=30), prop_id=9),
        _quote("draftkings", 2, 220.5),
        _quote("draftkings", 3, None),
        _quote("caesars", 1, 199.5, name="Nobody Else"),
        _quote("draftkings", 1, None, market=ANYTIME_TD_MARKET),
    ])
    picked = {(row["book"], row["market"], row["side"]): row["line"] for row in rows}
    assert picked[("fanduel", "player_pass_yds", "over")] == Decimal("240.5")
    assert picked[("draftkings", "player_pass_yds", "over")] == Decimal("220.5")
    assert picked[("draftkings", ANYTIME_TD_MARKET, "over")] == Decimal("0.5")
    assert ("caesars", "player_pass_yds", "over") not in picked

    game = game_quote_rows("2026_01_BAL_KC", [
        {
            "bookmaker": "fanduel", "market": "spreads",
            "snapshot_at": KICK - timedelta(hours=10), "commence_time": KICK,
            "point": Decimal("-3"), "price_home": -110, "price_away": -110,
        },
        {
            "bookmaker": "fanduel", "market": "spreads",
            "snapshot_at": KICK - timedelta(hours=1), "commence_time": KICK,
            "point": Decimal("-1"), "price_home": -110, "price_away": -110,
        },
        {
            "bookmaker": "fanduel", "market": "spreads",
            "snapshot_at": KICK - timedelta(minutes=30), "commence_time": KICK,
            "point": None, "price_home": -110, "price_away": -110,
        },
        {
            "bookmaker": "draftkings", "market": "spreads",
            "snapshot_at": KICK - timedelta(hours=2), "commence_time": KICK,
            "point": Decimal("-3"), "price_home": -110, "price_away": -110,
        },
        {
            "bookmaker": "draftkings", "market": "h2h",
            "snapshot_at": KICK - timedelta(hours=2), "commence_time": KICK,
            "point": None, "price_home": -150, "price_away": None,
        },
    ])
    lines = {(row["book"], row["market"], row["side"]): row["line"] for row in game}
    assert lines[("fanduel", "spreads", "home")] == Decimal("-1")
    assert lines[("fanduel", "spreads", "away")] == Decimal("1")
    assert lines[("draftkings", "spreads", "home")] == Decimal("-3")
    assert ("draftkings", "h2h", "home") in lines
    assert lines[("draftkings", "h2h", "home")] is None
    assert ("draftkings", "h2h", "away") not in lines

    class Missing:
        def execute(self, sql, params=None):
            assert "to_regclass" in sql
            return self

        def fetchone(self):
            return (None,)

    assert write_game_quotes(Missing(), [{"canonical_key": "2026_01_BAL_KC"}]) == 0


def test_scratch_best_line_grades_units_and_keeps_the_draftkings_record():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin
    from tracking.published_units import unit_profit, unit_risked

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
            CREATE SCHEMA IF NOT EXISTS auth;
            CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid
            LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid
            $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;
        """)
        for name in (
            "byom_facts_schema_2026_10_16.sql",
            "byom_backtest_rpc_2026_10_16.sql",
            "published_pick_units_2026_10_17.sql",
            "byom_saved_models_2026_10_16.sql",
            SQL_NAME,
        ):
            text = _sql(name)
            cur.execute(text)
            cur.execute(text)

        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              line_basis, home_score, away_score,
              dk_spread_home, dk_total,
              ats_home_result, ats_away_result,
              ml_home_result, ml_away_result,
              ou_over_result, ou_under_result,
              home_rest_days, away_rest_days, is_primetime,
              home_role, away_role)
            VALUES
              ('2026_01_BAL_KC', 'NFL', 2026, 1, 'BAL', 'KC',
               'DraftKings line at game start', 24, 22, -3, 47,
               'loss', 'win', 'win', 'loss', 'loss', 'win',
               7, 7, false, 'favorite', 'underdog'),
              ('2026_02_BUF_NYJ', 'NFL', 2026, 2, 'BUF', 'NYJ',
               'DraftKings line at game start', 20, 20, 0, 40,
               'push', 'push', 'tie', 'tie', 'push', 'push',
               10, 10, false, 'pickem', 'pickem')
        """)
        cur.execute("""
            INSERT INTO byom_prop_facts (
              prop_key, canonical_key, sport, season, week, player_name,
              player_key, team, market, line, line_basis, actual,
              over_result, under_result, log_status)
            VALUES
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5',
               '2026_01_BAL_KC', 'NFL', 2026, 1, 'Lamar Jackson',
               'lamar jackson', 'BAL', 'player_pass_yds', 240.5,
               'DraftKings line at game start', 250, 'win', 'loss', 'logged'),
              ('2026_01_BAL_KC|player_pass_yds|scratch player|10.5',
               '2026_01_BAL_KC', 'NFL', 2026, 1, 'Scratch Player',
               'scratch player', 'BAL', 'player_pass_yds', 10.5,
               'DraftKings line at game start', 100, NULL, NULL,
               'non_participant')
        """)
        cur.execute("""
            INSERT INTO byom_game_book_quotes
              (fact_id, book, market, side, line, price, captured_at)
            VALUES
              ('2026_01_BAL_KC', 'draftkings', 'spreads', 'home', -3, -110, now()),
              ('2026_01_BAL_KC', 'draftkings', 'spreads', 'away', 3, -110, now()),
              ('2026_01_BAL_KC', 'fanduel', 'spreads', 'home', -1, -110, now()),
              ('2026_01_BAL_KC', 'fanduel', 'spreads', 'away', 1, -110, now()),
              ('2026_01_BAL_KC', 'draftkings', 'totals', 'over', 47, -110, now()),
              ('2026_01_BAL_KC', 'draftkings', 'totals', 'under', 47, -110, now()),
              ('2026_01_BAL_KC', 'fanduel', 'totals', 'over', 44.5, -110, now()),
              ('2026_01_BAL_KC', 'fanduel', 'totals', 'under', 44.5, -110, now()),
              ('2026_01_BAL_KC', 'draftkings', 'h2h', 'home', NULL, -150, now()),
              ('2026_01_BAL_KC', 'draftkings', 'h2h', 'away', NULL, 130, now()),
              ('2026_01_BAL_KC', 'fanduel', 'h2h', 'home', NULL, 150, now()),
              ('2026_01_BAL_KC', 'fanduel', 'h2h', 'away', NULL, -170, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'spreads', 'home', 0, -110, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'spreads', 'away', 0, -110, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'h2h', 'home', NULL, -110, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'h2h', 'away', NULL, -110, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'totals', 'over', 40, -110, now()),
              ('2026_02_BUF_NYJ', 'draftkings', 'totals', 'under', 40, -110, now())
        """)
        cur.execute("""
            INSERT INTO byom_prop_book_quotes
              (fact_id, book, market, side, line, price, captured_at)
            VALUES
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5',
               'draftkings', 'player_pass_yds', 'over', 240.5, -110, now()),
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5',
               'draftkings', 'player_pass_yds', 'under', 240.5, -110, now()),
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5',
               'fanduel', 'player_pass_yds', 'over', 260.5, -110, now()),
              ('2026_01_BAL_KC|player_pass_yds|lamar jackson|240.5',
               'fanduel', 'player_pass_yds', 'under', 260.5, -110, now()),
              ('2026_01_BAL_KC|player_pass_yds|scratch player|10.5',
               'draftkings', 'player_pass_yds', 'over', 10.5, -110, now()),
              ('2026_01_BAL_KC|player_pass_yds|scratch player|10.5',
               'draftkings', 'player_pass_yds', 'under', 10.5, -110, now())
        """)

        def fetch(filters, books):
            cur.execute(
                """
                SELECT market, bets, wins, losses, pushes, ties,
                       units, roi, risked
                  FROM byom_backtest(2026, %s::jsonb, %s)
                """,
                (json.dumps(filters), books),
            )
            return {row[0]: row[1:] for row in cur.fetchall()}

        cur.execute("SET statement_timeout = '3s'")
        cur.execute("SET ROLE anon")
        home = {"weeks": [1], "side": "home", "markets": ["spreads"]}
        dk = fetch(home, None)["spreads"]
        assert dk[:5] == (1, 0, 1, 0, 0)
        assert dk[5] is None and dk[6] is None and dk[7] is None
        best = fetch(home, ["fanduel", "draftkings"])["spreads"]
        assert best[:5] == (1, 1, 0, 0, 0)
        assert float(best[5]) == pytest.approx(unit_profit(-110, "WIN"), abs=1e-9)
        assert float(best[7]) == pytest.approx(unit_risked(-110, "WIN"), abs=1e-9)
        assert float(best[6]) == pytest.approx(
            unit_profit(-110, "WIN") / unit_risked(-110, "WIN"), abs=1e-9)
        only_dk = fetch(home, ["draftkings"])["spreads"]
        assert only_dk[:5] == (1, 0, 1, 0, 0)
        assert float(only_dk[5]) == pytest.approx(unit_profit(-110, "LOSS"), abs=1e-9)
        assert float(only_dk[7]) == pytest.approx(unit_risked(-110, "LOSS"), abs=1e-9)
        assert "spreads" not in fetch(home, ["caesars"])
        assert fetch(home, []) == {}
        with pytest.raises(psycopg2.errors.RaiseException, match="sportsbook slugs"):
            fetch(home, ["not a book"])
        rested = {"weeks": [1], "side": "home", "markets": ["spreads"],
                  "min_rest_days": 8}
        assert fetch(rested, ["draftkings"]) == {}

        totals_dk = fetch({"weeks": [1], "markets": ["totals"]}, None)["totals"]
        assert totals_dk[:5] == (2, 1, 1, 0, 0)
        totals = fetch(
            {"weeks": [1], "markets": ["totals"]},
            ["fanduel", "draftkings"],
        )["totals"]
        assert totals[:5] == (2, 2, 0, 0, 0)

        pushed = fetch(
            {"weeks": [2], "side": "home", "markets": ["spreads"]},
            ["draftkings"],
        )["spreads"]
        assert pushed[:5] == (1, 0, 0, 1, 0)
        assert float(pushed[5]) == pytest.approx(unit_profit(-110, "PUSH"), abs=1e-9)
        assert float(pushed[7]) == pytest.approx(unit_risked(-110, "PUSH"), abs=1e-9)
        assert pushed[6] is None
        tied = fetch(
            {"weeks": [2], "side": "home", "markets": ["h2h"]},
            ["draftkings"],
        )["h2h"]
        assert tied[4] == 1
        assert float(tied[5]) == pytest.approx(unit_profit(-110, "TIE"), abs=1e-9)
        assert float(tied[7]) == pytest.approx(unit_risked(-110, "TIE"), abs=1e-9)

        price = fetch(
            {"weeks": [1], "side": "home", "markets": ["h2h"]},
            ["fanduel", "draftkings"],
        )["h2h"]
        assert price[1] == 1
        assert float(price[7]) == pytest.approx(unit_risked(150, "WIN"), abs=1e-9)
        assert float(price[7]) != pytest.approx(unit_risked(-150, "WIN"), abs=1e-6)

        props = fetch(
            {"markets": ["player_pass_yds"]},
            ["fanduel", "draftkings"],
        )["player_pass_yds"]
        assert props[:5] == (2, 2, 0, 0, 0)
        assert float(props[5]) == pytest.approx(
            2 * unit_profit(-110, "WIN"), abs=1e-9)
        assert float(props[7]) == pytest.approx(
            2 * unit_risked(-110, "WIN"), abs=1e-9)
        dk_props = fetch(
            {"markets": ["player_pass_yds"]}, ["draftkings"],
        )["player_pass_yds"]
        assert dk_props[:5] == (2, 1, 1, 0, 0)
        cur.execute("RESET ROLE")

        cur.execute("SELECT set_config('byom.uid', %s, false)", (USER_A,))
        cur.execute("""
            INSERT INTO byom_models (user_id, name, filters)
            VALUES (%s, 'legacy', '{}'::jsonb)
            RETURNING model_id
        """, (USER_A,))
        legacy = cur.fetchone()[0]
        cur.execute("""
            INSERT INTO byom_model_snapshots (
              model_id, user_id, season, filters, summary,
              bets, wins, losses, pushes, ties)
            VALUES (%s, %s, 2026, '{}'::jsonb, '[]'::jsonb, 0, 0, 0, 0, 0)
        """, (legacy, USER_A))
        cur.execute("""
            SELECT result_version, units, roi, books
              FROM byom_model_snapshots WHERE model_id = %s
        """, (legacy,))
        assert cur.fetchone() == (None, None, None, None)

        cur.execute("""
            SELECT bets, losses FROM byom_save_model(
              'dk home',
              '{"weeks":[1],"side":"home","markets":["spreads"]}'::jsonb,
              2026)
        """)
        assert cur.fetchone() == (1, 1)
        cur.execute("""
            SELECT result_version, units, roi, books
              FROM byom_model_snapshots s
              JOIN byom_models m ON m.model_id = s.model_id
             WHERE m.name = 'dk home'
        """)
        assert cur.fetchone() == (1, None, None, None)

        cur.execute("""
            SELECT bets, wins FROM byom_save_model(
              'best home',
              '{"weeks":[1],"side":"home","markets":["spreads"],
                "books":["FanDuel","draftkings"]}'::jsonb,
              2026)
        """)
        assert cur.fetchone() == (1, 1)
        cur.execute("""
            SELECT s.result_version, s.units, s.roi, s.books, s.filters
              FROM byom_model_snapshots s
              JOIN byom_models m ON m.model_id = s.model_id
             WHERE m.name = 'best home'
        """)
        version, units, roi, books, filters = cur.fetchone()
        assert version == 2
        assert sorted(books) == ["draftkings", "fanduel"]
        assert "books" not in filters
        assert float(units) == pytest.approx(unit_profit(-110, "WIN"), abs=1e-9)
        assert float(roi) == pytest.approx(
            unit_profit(-110, "WIN") / unit_risked(-110, "WIN"), abs=1e-9)
        with pytest.raises(psycopg2.errors.RaiseException, match="lowercase"):
            cur.execute("""
                SELECT byom_save_model('nope', '{"Books":["draftkings"]}'::jsonb, 2026)
            """)
        with pytest.raises(psycopg2.errors.RaiseException, match="sportsbook slugs"):
            cur.execute("""
                SELECT byom_save_model('nope', '{"books":[]}'::jsonb, 2026)
            """)

        cur.execute("SELECT count(*) FROM byom_game_book_quotes")
        quote_count = cur.fetchone()[0]
        cur.execute(_sql(SQL_NAME))
        cur.execute(_sql("byom_backtest_rpc_2026_10_16.sql"))
        cur.execute(_sql("byom_saved_models_2026_10_16.sql"))
        cur.execute("SELECT count(*) FROM byom_game_book_quotes")
        assert cur.fetchone()[0] == quote_count
        cur.execute("""
            SELECT pg_get_function_identity_arguments(p.oid)
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = 'public' AND p.proname = 'byom_backtest'
        """)
        assert cur.fetchall() == [
            ("p_season integer, p_filters jsonb, p_books text[]",)]
        cur.execute("""
            SELECT prosrc LIKE '%byom_best_line_v1%'
              FROM pg_proc WHERE proname = 'byom_save_model'
        """)
        assert cur.fetchone()[0] is True
        cur.execute("""
            SELECT indexdef FROM pg_indexes
             WHERE indexname = 'idx_byom_game_book_quotes_fact_book'
        """)
        assert "(fact_id, book)" in cur.fetchone()[0]
        cur.execute("SET ROLE anon")
        cur.execute("SELECT count(*) FROM byom_game_book_quotes")
        assert cur.fetchone()[0] == quote_count
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("""
                INSERT INTO byom_game_book_quotes
                  (fact_id, book, market, side, line, price, captured_at)
                VALUES ('x', 'draftkings', 'spreads', 'home', -3, -110, now())
            """)
        cur.execute("RESET ROLE")
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()
