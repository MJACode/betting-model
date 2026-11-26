"""NCAAB game lines on the builder, and NCAAB alerts (Matt, 2026-11-26:
"Do NCAAB next"; game lines, no props).

The scratch test applies the whole byom_legs chain, then
byom_ncaab_2026_11_26.sql twice, then the alerts file, and checks an
NCAAB model can be saved and graded, and that an unstarted NCAAB game is
an open bet. Nothing points at DATABASE_URL.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from tests.test_byom_alerts import CHAIN, ROOT, STUBS

SQL_NAME = "byom_ncaab_2026_11_26.sql"
USER_A = "11111111-1111-1111-1111-111111111111"


def test_the_migration_is_registered_after_the_last_byom_legs_file():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert SQL_NAME in ACTIVE_MIGRATIONS
    assert (ACTIVE_MIGRATIONS.index(SQL_NAME)
            > ACTIVE_MIGRATIONS.index("byom_no_half_yards_2026_11_17.sql"))
    sql = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "byom_ncaab_v1" in sql
    assert "insert into picks" not in sql.lower()


def test_seasons_floors_and_validators():
    from byom.constants import NCAAB_DK_HISTORY_START_SEASON
    from byom.load import _dk_history_floor
    from byom.official import OFFICIAL_SPORTS
    from byom.refresh import REFRESH_SPORTS, _season_for
    from byom.season import current_ncaab_season
    from tracking.job_queue import _validate_byom_game_facts, _validate_byom_refresh

    assert NCAAB_DK_HISTORY_START_SEASON == 2021
    assert _dk_history_floor("NCAAB") == 2021
    assert "NCAAB" in OFFICIAL_SPORTS and "NCAAB" in REFRESH_SPORTS
    # Ending year: games labels the season that opened 2026-11-01 as 2027.
    assert current_ncaab_season(date(2026, 11, 26)) == 2027
    assert current_ncaab_season(date(2027, 3, 15)) == 2027
    assert _season_for("NCAAB", date(2026, 11, 26)) == 2027
    assert _validate_byom_refresh({"sport": "ncaab"})["sport"] == "NCAAB"
    assert _validate_byom_game_facts({"sport": "NCAAB", "season": 2021})["season"] == 2021
    with pytest.raises(ValueError):
        _validate_byom_game_facts({"sport": "NCAAB", "season": 2020})


def test_the_daily_refresh_and_the_backfill_include_ncaab():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'for sport in ("NFL", "NBA", "NHL", "NCAAB"):' in src
    declared = json.loads((ROOT / "jobs/declared_jobs.json").read_text(encoding="utf-8"))
    row = next(r for r in declared if r["key"] == "byom-ncaab-game-facts")
    assert row["job_type"] == "byom_game_facts"
    assert row["args"] == {"sport": "NCAAB", "apply": True}


@pytest.fixture
def scratch():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests.byom_scratch import ScratchPostgres, pg_bin

    if pg_bin("initdb") is None:
        pytest.skip("initdb is not installed")
    cluster = ScratchPostgres()
    raw = None
    try:
        dsn = cluster.start()
        raw = psycopg2.connect(dsn)
        raw.autocommit = True
        cur = raw.cursor()
        cur.execute("""
            CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
            CREATE SCHEMA auth;
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
            CREATE TABLE device_push_tokens (
              token text, device_id text, user_id uuid, enabled boolean);
        """ + STUBS + f"INSERT INTO members VALUES ('{USER_A}');")
        for name in CHAIN:
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        ncaab = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
        cur.execute(ncaab)
        cur.execute(ncaab)  # the second run skips both functions
        cur.execute((ROOT / "data/migrations/byom_alerts_2026_11_25.sql").read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              game_date, commence_time, line_basis, home_score, away_score,
              dk_spread_home, dk_total, home_rest_days, away_rest_days,
              home_role, away_role, is_primetime,
              ats_home_result, ats_away_result, dk_spread_home_price, dk_spread_away_price)
            VALUES
              ('NCAAB_2026-11-24_ohio_new-mexico-state', 'NCAAB', 2027, NULL,
               'Ohio', 'New Mexico State', '2026-11-24', '2026-11-24 16:00+00',
               'DraftKings line at game start', 68, 69, -2.5, 140.5, 3, 3,
               'favorite', 'underdog', NULL, 'loss', 'win', -110, -110),
              ('NCAAB_2099-01-01_duke_unc', 'NCAAB', 2027, NULL,
               'Duke', 'North Carolina', (now() + interval '1 day')::date,
               now() + interval '1 day', 'DraftKings line at game start',
               NULL, NULL, -4.5, 150.5, 3, 3, 'favorite', 'underdog', NULL,
               NULL, NULL, -110, -110);
            INSERT INTO byom_official_legs (
              canonical_key, sport, season, market, leg_side, player_key,
              match_role, leg_role, team, locked_at, point, price, result)
            VALUES
              ('NCAAB_2026-11-24_ohio_new-mexico-state', 'NCAAB', 2027, 'spreads',
               'home', '', 'any', 'favorite', 'New Mexico State',
               '2026-11-24 12:00+00', -2.5, -110, 'loss'),
              ('NCAAB_2099-01-01_duke_unc', 'NCAAB', 2027, 'spreads', 'home', '',
               'any', 'favorite', 'North Carolina', now() - interval '1 hour',
               -4.5, -110, NULL);
        """)
        raw.autocommit = False
        from data.db import DBConnection
        yield psycopg2, raw, DBConnection(raw, url=dsn)
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


FILTERS = '{"sport":"NCAAB","markets":["spreads"],"side":"home"}'


def test_ncaab_is_graded_saved_and_alerted(scratch, monkeypatch):
    psycopg2, raw, conn = scratch
    cur = raw.cursor()
    # Graded: the finished game, at the official and the closing line.
    cur.execute("SELECT timing, bets, wins, losses FROM byom_record(2027, %s::jsonb) "
                "ORDER BY timing", (FILTERS,))
    assert cur.fetchall() == [("close", 1, 0, 1), ("official", 1, 0, 1)]
    # A null season is the ending year (the NBA rule).
    cur.execute("SELECT count(*) FROM byom_legs(NULL, %s::jsonb, 'official')", (FILTERS,))
    assert cur.fetchone()[0] >= 0
    # Open: the unstarted game, labelled from the stored school name.
    cur.execute("SELECT canonical_key, point, price FROM byom_legs(2027, %s::jsonb, 'open')",
                (FILTERS,))
    assert cur.fetchall() == [("NCAAB_2099-01-01_duke_unc", -4.5, -110)]
    # A member can save an NCAAB model.
    cur.execute("SET ROLE authenticated")
    cur.execute("SELECT set_config('byom.uid', %s, false)", (USER_A,))
    cur.execute("SELECT name FROM byom_save_model('Home faves', %s::jsonb, NULL)", (FILTERS,))
    assert cur.fetchone()[0] == "Home faves"
    cur.execute("RESET ROLE")
    cur.execute("SELECT sport FROM byom_models")
    assert cur.fetchone()[0] == "NCAAB"
    raw.commit()

    from byom import alerts
    monkeypatch.setattr("tracking.push_notifier._expo_send", lambda m, conn=None: 0)
    report = alerts.run(conn, sport="NCAAB", rebuild=False, today=datetime.now(timezone.utc))
    assert report["announced"]["alerts"] == 1
    cur.execute("SELECT sport, season, label FROM byom_alerts")
    assert cur.fetchall() == [("NCAAB", 2027, "North Carolina -4.5")]
    # The NFL pass does not pick up the NCAAB model.
    assert alerts.run(conn, sport="NFL", rebuild=False,
                      today=datetime.now(timezone.utc))["announced"]["alerts"] == 0


def test_an_unknown_sport_is_still_refused(scratch):
    psycopg2, raw, _conn = scratch
    cur = raw.cursor()
    with pytest.raises(psycopg2.Error, match="unknown sport"):
        cur.execute("SELECT * FROM byom_legs(2027, '{\"sport\":\"NCAAF\"}', NULL)")
    raw.rollback()
