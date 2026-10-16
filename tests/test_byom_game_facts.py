"""NFL game facts: lock, grade, and the backfill that writes them.

Pure tests always run. The scratch-Postgres test applies the unapplied
migration and builds a handful of rows. It does not touch production.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.constants import (
    DK_HISTORY_START_SEASON,
    LOCK_WINDOW_HOURS,
    NEAR_LOCK_WINDOW_HOURS,
)
from byom.game_facts import (
    assemble_game,
    grade_ats,
    grade_ml,
    grade_total,
    parse_game_id,
    units_1u_to_win,
)

ROOT = Path(__file__).resolve().parents[1]
BOOKS = ["draftkings", "fanduel"]
KICK = datetime(2024, 9, 6, 0, 20, tzinfo=timezone.utc)


def _q(hours_before, book, market, point, home, away, source="nfl_odds_history",
       game_id="2024_01_BAL_KC"):
    return {
        "game_id": game_id,
        "bookmaker": book,
        "market": market,
        "snapshot_at": KICK - timedelta(hours=hours_before),
        "commence_time": KICK,
        "point": point,
        "price_home": home,
        "price_away": away,
        "line_source": source,
    }


def _game(**over):
    base = {
        "game_id": "NFL_2024_01_BAL_KC",
        "game_date": "2024-09-05",
        "home_team": "KC",
        "away_team": "BAL",
        "home_score": 27,
        "away_score": 20,
        "commence_time": KICK,
        "week": 99,
    }
    base.update(over)
    return base


def _quotes():
    return [
        # Outside the 120h window. A different number, and it must not lock.
        _q(130, "draftkings", "spreads", -2.5, -110, -110),
        # Lock. Fanduel 10 minutes earlier is inside the shop lag and is the
        # better price. A still-better Fanduel quote 90 minutes earlier is not.
        _q(100, "draftkings", "spreads", -3, -115, -105),
        _q(100 + 10 / 60, "fanduel", "spreads", -3, -105, -115),
        _q(100 + 1.5, "fanduel", "spreads", -3, -101, -120),
        _q(100, "pinnacle", "spreads", -3, -100, -120),
        _q(100, "fanduel", "spreads", -2.5, 200, -250),
        _q(100, "draftkings", "totals", 47.5, -110, -110),
        _q(100, "draftkings", "h2h", None, -150, 130),
        # 24h window, then the close, then an in-play quote.
        _q(20, "draftkings", "spreads", -3.5, -108, -112),
        _q(2, "draftkings", "spreads", -4, -112, -108),
        _q(-1, "draftkings", "spreads", -14, -800, 600),
    ]


def test_the_windows_are_named_and_unconfirmed():
    text = (ROOT / "byom" / "constants.py").read_text(encoding="utf-8")
    assert LOCK_WINDOW_HOURS == 120
    assert NEAR_LOCK_WINDOW_HOURS == 24
    assert DK_HISTORY_START_SEASON == 2020
    assert text.count("UNCONFIRMED") >= 2
    assert "LOCK_WINDOW_HOURS = 120" in text
    assert "NEAR_LOCK_WINDOW_HOURS = 24" in text


def test_week_comes_from_the_id_and_the_prefix_does_not_matter():
    bare = parse_game_id("2024_01_BAL_KC")
    prefixed = parse_game_id("NFL_2024_01_BAL_KC")
    assert bare == prefixed
    assert bare[0] == "2024_01_BAL_KC"
    assert bare[2] == 1
    assert parse_game_id("not-a-game") is None


def test_units_store_the_uncapped_and_the_3u_capped_pair():
    # -400 lays 4 to win 1. The Record caps the lay at 3 and pays 0.75.
    assert units_1u_to_win("win", -400) == (Decimal("1"), Decimal("0.7500"))
    assert units_1u_to_win("loss", -400) == (Decimal("-4.0000"), Decimal("-3.0000"))
    # -300 lays exactly 3, so the cap does not bind.
    assert units_1u_to_win("loss", -300) == (Decimal("-3.0000"), Decimal("-3.0000"))
    assert units_1u_to_win("win", -110) == (Decimal("1"), Decimal("1.0000"))
    assert units_1u_to_win("loss", -110) == (Decimal("-1.1000"), Decimal("-1.1000"))
    assert units_1u_to_win("loss", 150) == (Decimal("-0.6667"), Decimal("-0.6667"))
    assert units_1u_to_win("push", -110) == (Decimal("0"), Decimal("0"))
    assert units_1u_to_win("tie", -110) == (Decimal("0"), Decimal("0"))
    assert units_1u_to_win("win", None) == (None, None)
    assert units_1u_to_win("loss", None) == (None, None)


def test_an_unplayed_game_keeps_the_line_and_nulls_the_result():
    fact = assemble_game(
        _game(home_score=None, away_score=None), _quotes(),
        {"BAL": [], "KC": []}, BOOKS)
    assert fact is not None
    assert fact["dk_spread_home"] == Decimal("-3")
    assert fact["ats_home_result"] is None
    assert fact["ats_home_units_uncapped"] is None
    assert fact["ats_home_units_capped"] is None
    assert fact["ml_home_result"] is None
    assert fact["ml_home_units_uncapped"] is None
    assert fact["ou_over_result"] is None
    assert fact["ou_over_units_uncapped"] is None


def test_pushes_and_ties_are_results():
    assert grade_ats(24, 21, -3) == ("push", "push")
    assert grade_ml(17, 17) == ("tie", "tie")
    assert grade_total(20, 27, 47) == ("push", "push")
    assert grade_ats(27, 20, -3) == ("win", "loss")
    assert grade_total(27, 20, 47.5) == ("loss", "win")


def test_the_lock_is_the_first_snapshot_inside_the_window():
    played = {"BAL": [], "KC": []}
    fact = assemble_game(_game(), _quotes(), played, BOOKS)
    assert fact["week"] == 1
    assert fact["lock_window_hours"] == 120
    assert fact["near_window_hours"] == 24
    assert fact["dk_spread_home"] == Decimal("-3")
    assert fact["lock_spread_at"] == KICK - timedelta(hours=100)
    assert fact["near_spread_home"] == Decimal("-3.5")
    assert fact["close_spread_home"] == Decimal("-4")
    # Graded at the best price on DK's -3, not the -2.5 and not Pinnacle.
    assert fact["grade_spread_home_book"] == "fanduel"
    assert fact["grade_spread_home_price"] == Decimal("-105")
    assert fact["ats_home_result"] == "win"
    assert fact["ats_home_units_uncapped"] == Decimal("1")
    assert fact["ats_home_units_capped"] == Decimal("1.0000")
    # Away is its own best price: DraftKings -105 beats Fanduel -115.
    assert fact["grade_spread_away_book"] == "draftkings"
    assert fact["grade_spread_away_price"] == Decimal("-105")
    assert fact["ats_away_units_uncapped"] == Decimal("-1.0500")
    assert fact["ats_away_units_capped"] == Decimal("-1.0500")
    assert fact["home_role"] == "favorite"
    assert fact["away_role"] == "underdog"
    assert fact["is_primetime"] is True
    assert fact["line_source"] == "nfl_odds_history"
    assert fact["ou_over_result"] == "loss"


def test_a_short_price_and_a_large_spread_are_kept():
    game = _game(game_id="NFL_2024_03_NYJ_SF", home_score=30, away_score=10,
                 game_date="2024-09-22", commence_time=KICK)
    quotes = [_q(80, "draftkings", "spreads", -17.5, -800, 550,
                 game_id="2024_03_NYJ_SF")]
    fact = assemble_game(game, quotes, {"SF": [], "NYJ": []}, BOOKS)
    assert fact is not None
    assert fact["dk_spread_home"] == Decimal("-17.5")
    assert fact["ats_home_units_uncapped"] == Decimal("1")
    assert fact["ats_home_units_capped"] == Decimal("0.3750")
    assert fact["ats_away_units_uncapped"] == Decimal("-0.1818")
    assert fact["ats_away_units_capped"] == Decimal("-0.1818")


def test_seasons_before_draftkings_history_are_not_built():
    game = _game(game_id="NFL_2019_01_ATL_MIN")
    quotes = [_q(80, "draftkings", "spreads", -3, -110, -110,
                 game_id="2019_01_ATL_MIN")]
    assert assemble_game(game, quotes, {}, BOOKS) is None


def test_odds_is_the_source_when_history_has_no_lock():
    quotes = [_q(48, "draftkings", "spreads", -6, -110, -110, source="odds")]
    fact = assemble_game(_game(), quotes, {"BAL": [], "KC": []}, BOOKS)
    assert fact["line_source"] == "odds"
    assert fact["dk_spread_home"] == Decimal("-6")


def test_history_wins_when_both_sources_have_a_lock():
    quotes = _quotes() + [
        _q(48, "draftkings", "spreads", -7, -110, -110, source="odds"),
    ]
    fact = assemble_game(_game(), _quotes() and quotes, {"BAL": [], "KC": []}, BOOKS)
    assert fact["dk_spread_home"] == Decimal("-3")
    assert fact["line_source"] == "nfl_odds_history"


def test_rest_days_and_a_sunday_afternoon_is_not_primetime():
    played = {
        "BAL": [datetime(2024, 9, 5).date(), datetime(2024, 9, 15).date()],
        "NYJ": [datetime(2024, 9, 15).date()],
    }
    kick = datetime(2024, 9, 15, 17, 0, tzinfo=timezone.utc)
    game = _game(game_id="NFL_2024_02_BAL_NYJ", game_date="2024-09-15",
                 home_team="NYJ", away_team="BAL", commence_time=kick,
                 home_score=10, away_score=24)
    quotes = [_q(30, "draftkings", "spreads", 3, -110, -110,
                 game_id="2024_02_BAL_NYJ")]
    quotes[0]["snapshot_at"] = kick - timedelta(hours=30)
    quotes[0]["commence_time"] = kick
    fact = assemble_game(game, quotes, played, BOOKS)
    assert fact["away_rest_days"] == 10
    assert fact["home_rest_days"] is None
    assert fact["is_primetime"] is False
    assert fact["home_role"] == "underdog"


def test_quotes_are_read_per_game_and_the_odds_cast_is_inside_a_case():
    text = (ROOT / "byom" / "load.py").read_text(encoding="utf-8")
    assert "game_id IN (%s, %s)" in text
    assert "bookmaker = 'draftkings'" in text
    assert "FROM nfl_odds_history\n WHERE season = %s" not in text
    assert "AND o.snapshot_at::timestamptz" not in text
    assert "ELSE NULL END" in text


def test_the_builder_has_no_spread_price_or_line_filter_and_does_not_touch_picks():
    text = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("byom/game_facts.py", "byom/load.py", "scripts/byom_game_facts.py")
    )
    lowered = text.lower()
    for banned in ("min_odds", "max_edge", "spread_size", "price_band",
                   "insert into picks", "models.scorer", "discord"):
        assert banned not in lowered, banned


def test_the_job_defaults_to_not_writing_and_ships_disabled():
    from byom.constants import SHOP_FIRST_APPLY_BEFORE
    from tracking.job_queue import JOBS, _validate_byom_game_facts

    assert "byom_game_facts" in JOBS
    assert _validate_byom_game_facts({}) == {
        "sport": "NFL", "season": None, "apply": False}
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"season": 2019})
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"sport": "NBA"})
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    found = [entry for entry in declared if entry["job_type"] == "byom_game_facts"]
    assert len(found) == 1
    assert found[0]["enabled"] is False
    assert found[0]["args"]["apply"] is False
    assert found[0]["args"]["sport"] == "NFL"
    assert SHOP_FIRST_APPLY_BEFORE == "2026-10-17"
    assert SHOP_FIRST_APPLY_BEFORE in found[0]["note"]


def test_build_on_scratch_postgres_grades_the_stored_lines():
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

        cur.execute("""
            INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type,
                              snapshot_at, home_price, away_price, spread_home)
            VALUES ('NFL_2024_01_BAL_KC', 'NFL', 'spreads', 'draftkings', 'open',
                    'not-a-timestamp', -110, -110, -3)
        """)
        conn = Conn()
        skipped = build_season(conn, 2019, apply=True, books=BOOKS)
        assert skipped["written"] == 0
        first = build_season(conn, 2024, apply=True, books=BOOKS)
        assert first["written"] == 3
        again = build_season(conn, 2024, apply=True, books=BOOKS)
        assert again["written"] == 3
        season_2026 = build_season(conn, 2026, apply=True, books=BOOKS)
        assert season_2026["written"] == 1
        cur = raw.cursor()
        cur.execute("SELECT count(*) FROM byom_game_facts")
        assert cur.fetchone()[0] == 4
        cur.execute("""
            SELECT canonical_key, week, dk_spread_home, grade_spread_home_book,
                   grade_spread_home_price, ats_home_result,
                   ats_home_units_uncapped, ats_home_units_capped,
                   close_spread_home, near_spread_home, home_role, is_primetime,
                   line_source, away_rest_days
              FROM byom_game_facts
             WHERE canonical_key = '2024_01_BAL_KC'
        """)
        row = cur.fetchone()
        assert row[0] == "2024_01_BAL_KC"
        assert row[1] == 1
        assert Decimal(str(row[2])) == Decimal("-3")
        assert row[3] == "fanduel"
        assert Decimal(str(row[4])) == Decimal("-105")
        assert row[5] == "win"
        assert Decimal(str(row[6])) == Decimal("1")
        assert Decimal(str(row[7])) == Decimal("1.0000")
        assert Decimal(str(row[8])) == Decimal("-4")
        assert Decimal(str(row[9])) == Decimal("-3.5")
        assert row[10] == "favorite"
        assert row[11] is True
        assert row[12] == "nfl_odds_history"
        cur.execute("""
            SELECT ats_home_result, ats_home_units_uncapped,
                   ats_home_units_capped, dk_spread_home
              FROM byom_game_facts WHERE canonical_key = '2024_03_NYJ_SF'
        """)
        big = cur.fetchone()
        assert Decimal(str(big[3])) == Decimal("-17.5")
        assert big[0] == "win"
        assert Decimal(str(big[1])) == Decimal("1")
        assert Decimal(str(big[2])) == Decimal("0.3750")
        cur.execute("""
            SELECT ats_home_result, ats_home_units_uncapped,
                   ats_home_units_capped, ml_home_result
              FROM byom_game_facts WHERE canonical_key = '2024_04_DET_GB'
        """)
        push = cur.fetchone()
        assert push[0] == "push"
        assert Decimal(str(push[1])) == Decimal("0")
        assert Decimal(str(push[2])) == Decimal("0")
        cur.execute("""
            SELECT ml_home_result, ml_home_units_uncapped,
                   ml_home_units_capped, line_source, week
              FROM byom_game_facts WHERE canonical_key = '2026_01_NE_SEA'
        """)
        odds_only = cur.fetchone()
        assert odds_only[0] == "tie"
        assert Decimal(str(odds_only[1])) == Decimal("0")
        assert Decimal(str(odds_only[2])) == Decimal("0")
        assert odds_only[3] == "odds"
        assert odds_only[4] == 1
        dry = build_season(conn, 2024, apply=False, books=BOOKS)
        assert dry["facts"] == 3 and dry["written"] == 0
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def _load_fixture(cur):
    kick = KICK
    games = [
        ("NFL_2019_01_ATL_MIN", 2019, "2019-09-08", "MIN", "ATL", 20, 10,
         "2019-09-08T17:00:00Z"),
        ("NFL_2024_01_BAL_KC", 2024, "2024-09-05", "KC", "BAL", 27, 20,
         kick.isoformat()),
        ("NFL_2024_03_NYJ_SF", 2024, "2024-09-22", "SF", "NYJ", 30, 10,
         "2024-09-22T20:25:00Z"),
        ("NFL_2024_04_DET_GB", 2024, "2024-09-29", "GB", "DET", 24, 21,
         "2024-09-29T17:00:00Z"),
        ("NFL_2026_01_NE_SEA", 2026, "2026-09-09", "SEA", "NE", 17, 17,
         "2026-09-10T00:20:00Z"),
    ]
    for game_id, season, day, home, away, hs, aws, commence in games:
        cur.execute("""
            INSERT INTO games (game_id, sport, season, week, game_date,
                               home_team, away_team, home_score, away_score,
                               commence_time)
            VALUES (%s, 'NFL', %s, 99, %s, %s, %s, %s, %s, %s)
        """, (game_id, season, day, home, away, hs, aws, commence))

    def hist(hours, game_id, season, book, market, point, home, away, commence):
        kick_at = datetime.fromisoformat(commence.replace("Z", "+00:00"))
        cur.execute("""
            INSERT INTO nfl_odds_history
              (snapshot_at, game_id, season, week, commence_time, bookmaker,
               market, point, price_home, price_away, lead_hours)
            VALUES (%s, %s, %s, NULL, %s, %s, %s, %s, %s, %s, NULL)
        """, (kick_at - timedelta(hours=hours), game_id, season, kick_at,
              book, market, point, home, away))

    commence = kick.isoformat()
    hist(130, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -2.5, -110, -110, commence)
    hist(100, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -3, -115, -105, commence)
    hist(100 + 10 / 60, "2024_01_BAL_KC", 2024, "fanduel", "spreads", -3, -105, -115, commence)
    hist(100 + 1.5, "2024_01_BAL_KC", 2024, "fanduel", "spreads", -3, -101, -120, commence)
    hist(100, "2024_01_BAL_KC", 2024, "pinnacle", "spreads", -3, -100, -120, commence)
    hist(100, "2024_01_BAL_KC", 2024, "fanduel", "spreads", -2.5, 200, -250, commence)
    hist(100, "2024_01_BAL_KC", 2024, "draftkings", "totals", 47.5, -110, -110, commence)
    hist(100, "2024_01_BAL_KC", 2024, "draftkings", "h2h", None, -150, 130, commence)
    hist(20, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -3.5, -108, -112, commence)
    hist(2, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -4, -112, -108, commence)
    hist(-1, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -14, -800, 600, commence)
    # A different number in odds must not replace the history lock.
    cur.execute("""
        INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type,
                          snapshot_at, home_price, away_price, spread_home)
        VALUES ('NFL_2024_01_BAL_KC', 'NFL', 'spreads', 'draftkings', 'open',
                '2024-09-04T00:20:00Z', -110, -110, -7)
    """)
    hist(40, "2024_03_NYJ_SF", 2024, "draftkings", "spreads", -17.5, -800, 550,
         "2024-09-22T20:25:00Z")
    hist(40, "2024_04_DET_GB", 2024, "draftkings", "spreads", -3, -110, -110,
         "2024-09-29T17:00:00Z")
    hist(40, "2019_01_ATL_MIN", 2019, "draftkings", "spreads", -3, -110, -110,
         "2019-09-08T17:00:00Z")
    cur.execute("""
        INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type,
                          snapshot_at, home_price, away_price, spread_home)
        VALUES
          ('NFL_2026_01_NE_SEA', 'NFL', 'spreads', 'draftkings', 'open',
           '2026-09-08T00:20:00Z', -110, -110, -3),
          ('NFL_2026_01_NE_SEA', 'NFL', 'h2h', 'draftkings', 'open',
           '2026-09-08T00:20:00Z', -120, 100, NULL),
          ('NFL_2026_01_NE_SEA', 'NFL', 'spreads', 'draftkings', 'in_play',
           '2026-09-10T01:00:00Z', -900, 600, -14)
    """)
