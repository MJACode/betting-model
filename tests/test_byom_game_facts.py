"""NFL game facts: the line at game start, and the backfill that writes them.

Pure tests always run. The scratch-Postgres test applies the unapplied
migration and builds a handful of rows. It does not touch production.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.constants import DK_HISTORY_START_SEASON, LINE_BASIS
from byom.game_facts import (
    assemble_game,
    grade_ats,
    grade_ml,
    grade_total,
    parse_game_id,
)

ROOT = Path(__file__).resolve().parents[1]
KICK = datetime(2024, 9, 6, 0, 20, tzinfo=timezone.utc)
_BANNED_KEYS = (
    "lock_window_hours", "near_window_hours", "lock_spread_at",
    "close_spread_home", "near_spread_home", "line_source",
    "grade_spread_home_price", "grade_spread_home_book",
    "ats_home_units_uncapped", "ats_home_units_capped",
    "ml_home_units_uncapped",
)


def _q(hours_before, book, market, point, home=None, away=None,
       source="nfl_odds_history", game_id="2024_01_BAL_KC"):
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
        # Older than any former window. It is a candidate, and it loses
        # only because a later pre-start snapshot exists.
        _q(130, "draftkings", "spreads", -2.5),
        _q(100, "draftkings", "spreads", -3),
        # Other books, including a later one, are not the line.
        _q(100 + 10 / 60, "fanduel", "spreads", -3),
        _q(1, "fanduel", "spreads", -9),
        _q(100, "pinnacle", "spreads", -3),
        _q(100, "draftkings", "totals", 47.5),
        _q(100, "draftkings", "h2h", None),
        _q(20, "draftkings", "spreads", -3.5),
        # Last pre-start DraftKings spread.
        _q(2, "draftkings", "spreads", -4),
        # In-play is not the line.
        _q(-1, "draftkings", "spreads", -14),
    ]


def test_the_line_basis_is_a_label():
    text = (ROOT / "byom" / "constants.py").read_text(encoding="utf-8")
    assert LINE_BASIS == "DraftKings line at game start"
    assert DK_HISTORY_START_SEASON == 2020
    assert "LOCK_WINDOW" not in text
    assert "SHOP_LAG" not in text
    assert "120" not in text
    assert "24" not in text


def test_week_comes_from_the_id_and_the_prefix_does_not_matter():
    bare = parse_game_id("2024_01_BAL_KC")
    prefixed = parse_game_id("NFL_2024_01_BAL_KC")
    assert bare == prefixed
    assert bare[0] == "2024_01_BAL_KC"
    assert bare[2] == 1
    assert parse_game_id("not-a-game") is None


def test_an_unplayed_game_keeps_the_line_and_nulls_the_result():
    fact = assemble_game(
        _game(home_score=None, away_score=None), _quotes(),
        {"BAL": [], "KC": []})
    assert fact is not None
    assert fact["line_basis"] == LINE_BASIS
    assert fact["dk_spread_home"] == Decimal("-4")
    assert fact["dk_total"] == Decimal("47.5")
    assert fact["ats_home_result"] is None
    assert fact["ml_home_result"] is None
    assert fact["ou_over_result"] is None
    for key in _BANNED_KEYS:
        assert key not in fact


def test_pushes_and_ties_are_results():
    assert grade_ats(24, 21, -3) == ("push", "push")
    assert grade_ml(17, 17) == ("tie", "tie")
    assert grade_total(20, 27, 47) == ("push", "push")
    assert grade_ats(27, 20, -3) == ("win", "loss")
    assert grade_total(27, 20, 47.5) == ("loss", "win")


def test_the_line_is_the_last_pre_start_draftkings_snapshot():
    fact = assemble_game(_game(), _quotes(), {"BAL": [], "KC": []})
    assert fact["week"] == 1
    assert fact["line_basis"] == LINE_BASIS
    # 2h before kickoff, not the 100h -3, not the 130h -2.5, not in-play -14.
    assert fact["dk_spread_home"] == Decimal("-4")
    assert fact["dk_total"] == Decimal("47.5")
    # 27 - 20 + (-4) = 3, so home covers. Moneyline is the score only.
    assert fact["ats_home_result"] == "win"
    assert fact["ats_away_result"] == "loss"
    assert fact["ml_home_result"] == "win"
    assert fact["ml_away_result"] == "loss"
    assert fact["ou_over_result"] == "loss"
    assert fact["ou_under_result"] == "win"
    assert fact["home_role"] == "favorite"
    assert fact["away_role"] == "underdog"
    assert fact["is_primetime"] is True
    for key in _BANNED_KEYS:
        assert key not in fact


def test_a_snapshot_older_than_any_former_window_is_still_the_line():
    quotes = [_q(200, "draftkings", "spreads", -2.5)]
    fact = assemble_game(_game(), quotes, {"BAL": [], "KC": []})
    assert fact is not None
    assert fact["dk_spread_home"] == Decimal("-2.5")
    assert fact["line_basis"] == LINE_BASIS


def test_a_missing_line_does_not_skip_the_game():
    quotes = [_q(1, "fanduel", "spreads", -9)]
    fact = assemble_game(_game(), quotes, {"BAL": [], "KC": []})
    assert fact is not None
    assert fact["dk_spread_home"] is None
    assert fact["dk_total"] is None
    assert fact["ats_home_result"] is None
    assert fact["ou_over_result"] is None
    assert fact["ml_home_result"] == "win"
    assert fact["home_role"] is None
    assert fact["line_basis"] == LINE_BASIS


def test_a_large_spread_is_kept():
    game = _game(game_id="NFL_2024_03_NYJ_SF", home_score=30, away_score=10,
                 game_date="2024-09-22", commence_time=KICK)
    quotes = [_q(80, "draftkings", "spreads", -17.5, game_id="2024_03_NYJ_SF")]
    fact = assemble_game(game, quotes, {"SF": [], "NYJ": []})
    assert fact is not None
    assert fact["dk_spread_home"] == Decimal("-17.5")
    assert fact["ats_home_result"] == "win"
    assert fact["line_basis"] == LINE_BASIS


def test_seasons_before_draftkings_history_are_not_built():
    game = _game(game_id="NFL_2019_01_ATL_MIN")
    quotes = [_q(80, "draftkings", "spreads", -3, game_id="2019_01_ATL_MIN")]
    assert assemble_game(game, quotes, {}) is None
    assert assemble_game(_game(game_id="not-a-game"), _quotes(), {}) is None


def test_the_later_snapshot_wins_across_both_stores():
    quotes = [
        _q(100, "draftkings", "spreads", -3, source="nfl_odds_history"),
        _q(48, "draftkings", "spreads", -7, source="odds"),
    ]
    fact = assemble_game(_game(), quotes, {"BAL": [], "KC": []})
    assert fact["dk_spread_home"] == Decimal("-7")

    flipped = [
        _q(2, "draftkings", "spreads", -4, source="nfl_odds_history"),
        _q(48, "draftkings", "spreads", -7, source="odds"),
    ]
    fact = assemble_game(_game(), flipped, {"BAL": [], "KC": []})
    assert fact["dk_spread_home"] == Decimal("-4")


def test_an_in_play_quote_is_not_the_line():
    quotes = [
        _q(10, "draftkings", "spreads", -3),
        _q(-0.5, "draftkings", "spreads", -14),
    ]
    fact = assemble_game(_game(), quotes, {"BAL": [], "KC": []})
    assert fact["dk_spread_home"] == Decimal("-3")


def test_rest_days_and_a_sunday_afternoon_is_not_primetime():
    played = {
        "BAL": [datetime(2024, 9, 5).date(), datetime(2024, 9, 15).date()],
        "NYJ": [datetime(2024, 9, 15).date()],
    }
    kick = datetime(2024, 9, 15, 17, 0, tzinfo=timezone.utc)
    game = _game(game_id="NFL_2024_02_BAL_NYJ", game_date="2024-09-15",
                 home_team="NYJ", away_team="BAL", commence_time=kick,
                 home_score=10, away_score=24)
    quotes = [_q(30, "draftkings", "spreads", 3, game_id="2024_02_BAL_NYJ")]
    quotes[0]["snapshot_at"] = kick - timedelta(hours=30)
    quotes[0]["commence_time"] = kick
    fact = assemble_game(game, quotes, played)
    assert fact["away_rest_days"] == 10
    assert fact["home_rest_days"] is None
    assert fact["is_primetime"] is False
    assert fact["home_role"] == "underdog"
    assert fact["ml_home_result"] == "loss"


def test_quotes_are_read_per_game_and_the_odds_cast_is_inside_a_case():
    text = (ROOT / "byom" / "load.py").read_text(encoding="utf-8")
    assert "game_id IN (%s, %s)" in text
    assert "WHERE o.game_id = %s" in text
    assert "bookmaker = 'draftkings'" in text
    assert "('h2h', 'spreads', 'totals')" in text
    assert "make_interval" not in text
    assert "price_home" in text
    assert "_shop_quotes" not in text
    assert "bookmaker <> 'draftkings'" not in text
    assert "FROM nfl_odds_history\n WHERE season = %s" not in text
    assert "AND o.snapshot_at::timestamptz" not in text
    assert "ELSE NULL END" in text


def test_the_builder_has_no_spread_price_or_line_filter_and_does_not_touch_picks():
    text = "\n".join(
        (ROOT / name).read_text(encoding="utf-8")
        for name in ("byom/game_facts.py", "byom/load.py",
                     "byom/constants.py", "scripts/byom_game_facts.py")
    )
    lowered = text.lower()
    for banned in ("min_odds", "max_edge", "spread_size", "price_band",
                   "insert into picks", "models.scorer", "discord",
                   "lock_window", "units_1u", "grade_spread", "line_source"):
        assert banned not in lowered, banned


def test_a_job_queued_without_sport_uses_nfl(monkeypatch):
    """A queued byom_game_facts row with no sport builds NFL and writes nothing."""
    from tracking.job_queue import JOBS

    seen = {}

    def build_seasons(conn, seasons, apply=False, sport="NFL"):
        seen["sport"] = sport
        seen["apply"] = apply
        seen["seasons"] = seasons
        return {"apply": apply, "sport": sport, "seasons": []}

    class Conn:
        def close(self):
            seen["closed"] = True

    monkeypatch.setattr("byom.load.build_seasons", build_seasons)
    monkeypatch.setattr("data.db.get_connection", lambda: Conn())

    fn, validate = JOBS["byom_game_facts"]
    stored = validate({})
    assert stored["sport"] == "NFL"
    assert stored["apply"] is False
    # The runner calls the job with the validated args. Dropping sport here
    # is a row whose args never carried it: the job still builds NFL.
    out = fn(**{key: value for key, value in stored.items() if key != "sport"})
    assert seen["sport"] == "NFL"
    assert seen["apply"] is False
    assert seen["seasons"] is None
    assert seen["closed"] is True
    assert out["sport"] == "NFL"
    # An explicit null is the same call. .get's default does not apply
    # when the key is present, so the job must treat None as NFL.
    seen.clear()
    out = fn(sport=None, season=None, apply=False)
    assert seen["sport"] == "NFL"
    assert seen["apply"] is False
    assert seen["closed"] is True
    assert out["sport"] == "NFL"
    # NBA is the same runner. The validator's stored args are what a
    # queued row carries, and the job forwards that sport.
    seen.clear()
    stored_nba = validate({"sport": "nba", "apply": False})
    out = fn(**stored_nba)
    assert stored_nba["sport"] == "NBA"
    assert seen["sport"] == "NBA"
    assert seen["apply"] is False
    assert seen["seasons"] is None
    assert seen["closed"] is True
    assert out["sport"] == "NBA"


def test_the_job_defaults_to_not_writing_and_nba_stays_off():
    from tracking.job_queue import JOBS, _validate_byom_game_facts

    assert "byom_game_facts" in JOBS
    assert _validate_byom_game_facts({}) == {
        "sport": "NFL", "season": None, "apply": False}
    assert _validate_byom_game_facts({"sport": "NBA", "apply": False}) == {
        "sport": "NBA", "season": None, "apply": False}
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"season": 2019})
    # NBA is not on the NFL DraftKings-history floor.
    assert _validate_byom_game_facts(
        {"sport": "NBA", "season": 2019})["season"] == 2019
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"sport": "MLB"})
    declared = json.loads(
        (ROOT / "jobs" / "declared_jobs.json").read_text(encoding="utf-8"))
    game = [entry for entry in declared if entry["job_type"] == "byom_game_facts"]
    assert len(game) == 1
    assert game[0]["key"] == "byom-nba-game-facts"
    assert game[0]["enabled"] is False
    assert game[0]["requested_by"] == "owner"
    assert game[0]["args"] == {"sport": "NBA", "apply": False}
    assert "season" not in game[0]["args"]
    assert "byom_nba_props_2026_10_29.sql" in game[0]["note"]
    assert "byom-nba-prop-facts" in game[0]["note"]
    assert all(entry["key"] != "byom-nfl-game-facts" for entry in declared)
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert "byom_game_facts_units_2026_10_16.sql" not in ACTIVE_MIGRATIONS
    assert not (ROOT / "data" / "migrations" / "byom_game_facts_units_2026_10_16.sql").exists()


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
              total_line numeric, over_price numeric, under_price numeric,
              created_at text);
        """)
        text = (ROOT / "data/migrations" / "byom_facts_schema_2026_10_16.sql").read_text(
            encoding="utf-8")
        cur.execute(text)
        cur.execute(text)
        price = (ROOT / "data/migrations" / "byom_dk_start_price_2026_10_23.sql").read_text(
            encoding="utf-8")
        cur.execute(price)
        cur.execute(price)
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
        skipped = build_season(conn, 2019, apply=True)
        assert skipped["written"] == 0
        first = build_season(conn, 2024, apply=True)
        assert first["written"] == 5
        again = build_season(conn, 2024, apply=True)
        assert again["written"] == 5
        season_2026 = build_season(conn, 2026, apply=True)
        assert season_2026["written"] == 1
        cur = raw.cursor()
        cur.execute("SELECT count(*) FROM byom_game_facts")
        assert cur.fetchone()[0] == 6
        cur.execute("""
            SELECT canonical_key, week, line_basis, dk_spread_home, dk_total,
                   ats_home_result, ml_home_result, ou_over_result,
                   home_role, is_primetime
              FROM byom_game_facts
             WHERE canonical_key = '2024_01_BAL_KC'
        """)
        row = cur.fetchone()
        assert row[0] == "2024_01_BAL_KC"
        assert row[1] == 1
        assert row[2] == "DraftKings line at game start"
        assert Decimal(str(row[3])) == Decimal("-4")
        assert Decimal(str(row[4])) == Decimal("47.5")
        assert row[5] == "win"
        assert row[6] == "win"
        assert row[7] == "loss"
        assert row[8] == "favorite"
        assert row[9] is True
        cur.execute("""
            SELECT dk_spread_home_price, dk_spread_away_price,
                   dk_total_over_price, dk_total_under_price,
                   dk_ml_home_price, dk_ml_away_price
              FROM byom_game_facts
             WHERE canonical_key = '2024_01_BAL_KC'
        """)
        px = [None if value is None else Decimal(str(value))
              for value in cur.fetchone()]
        assert px == [
            Decimal("-112"), Decimal("-108"),
            Decimal("-110"), Decimal("-110"),
            Decimal("-150"), Decimal("130"),
        ]
        cur.execute("""
            SELECT dk_spread_home, ats_home_result, ml_home_result, line_basis
              FROM byom_game_facts WHERE canonical_key = '2024_03_NYJ_SF'
        """)
        big = cur.fetchone()
        assert Decimal(str(big[0])) == Decimal("-17.5")
        assert big[1] == "win"
        assert big[2] == "win"
        assert big[3] == "DraftKings line at game start"
        cur.execute("""
            SELECT ats_home_result, ml_home_result
              FROM byom_game_facts WHERE canonical_key = '2024_04_DET_GB'
        """)
        push = cur.fetchone()
        assert push[0] == "push"
        assert push[1] == "win"
        cur.execute("""
            SELECT dk_spread_home, ats_home_result, ml_home_result, line_basis
              FROM byom_game_facts WHERE canonical_key = '2024_05_DAL_PHI'
        """)
        bare = cur.fetchone()
        assert bare[0] is None
        assert bare[1] is None
        assert bare[2] == "win"
        assert bare[3] == "DraftKings line at game start"
        cur.execute("""
            SELECT dk_spread_home FROM byom_game_facts
             WHERE canonical_key = '2024_06_CHI_GB'
        """)
        old = cur.fetchone()
        assert Decimal(str(old[0])) == Decimal("-1.5")
        cur.execute("""
            SELECT ml_home_result, ats_home_result, line_basis, week
              FROM byom_game_facts WHERE canonical_key = '2026_01_NE_SEA'
        """)
        odds_only = cur.fetchone()
        assert odds_only[0] == "tie"
        assert odds_only[1] == "loss"
        assert odds_only[2] == "DraftKings line at game start"
        assert odds_only[3] == 1
        dry = build_season(conn, 2024, apply=False)
        assert dry["facts"] == 5 and dry["written"] == 0
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
        ("NFL_2024_05_DAL_PHI", 2024, "2024-10-06", "PHI", "DAL", 21, 14,
         "2024-10-06T17:00:00Z"),
        ("NFL_2024_06_CHI_GB", 2024, "2024-10-13", "GB", "CHI", 24, 20,
         "2024-10-13T17:00:00Z"),
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
    hist(1, "2024_01_BAL_KC", 2024, "fanduel", "spreads", -9, -110, -110, commence)
    hist(100, "2024_01_BAL_KC", 2024, "pinnacle", "spreads", -3, -100, -120, commence)
    hist(100, "2024_01_BAL_KC", 2024, "draftkings", "totals", 47.5, -110, -110, commence)
    hist(100, "2024_01_BAL_KC", 2024, "draftkings", "h2h", None, -150, 130, commence)
    hist(20, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -3.5, -108, -112, commence)
    hist(2, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -4, -112, -108, commence)
    hist(-1, "2024_01_BAL_KC", 2024, "draftkings", "spreads", -14, -800, 600, commence)
    # An earlier odds number must not replace the later history line.
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
    hist(200, "2024_06_CHI_GB", 2024, "draftkings", "spreads", -1.5, -110, -110,
         "2024-10-13T17:00:00Z")
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
