"""Review fixes for the unapplied internal NCAAB margin-band migration.

PR 1215 merged the draft and was not applied. These tests drive that file on a
throwaway cluster. They do not register it, schedule it, or touch production.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "data" / "migrations" / "internal_ncaab_margin_pricing_2026_11_07.sql"
SQL = MIG.read_text(encoding="utf-8")

HOME = 150
AWAY = 96


def _code(sql: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in sql.splitlines())


def _future():
    """A commence date still ahead of now, and the phase the SQL will assign."""
    et = datetime.now(ZoneInfo("America/New_York")).date() + timedelta(days=3)
    phase = "nov" if et.month == 11 else "rest"
    return et, phase, f"{et.isoformat()}T18:00:00Z", f"{et.isoformat()}T15:00:00Z"


def _roles(cur) -> None:
    cur.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            CREATE ROLE anon NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            CREATE ROLE authenticated NOLOGIN;
          END IF;
          IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
            CREATE ROLE service_role NOLOGIN;
          END IF;
        END $$
    """)


def _stubs(cur) -> None:
    cur.execute("""
        CREATE TABLE public.pipeline_log (
          log_id bigserial primary key,
          run_date text not null,
          step text not null,
          status text not null,
          records_in integer,
          records_out integer,
          duration_s numeric,
          error_msg text,
          created_at text
        );
        CREATE TABLE public.ncaab_teams (
          espn_id integer primary key,
          school text not null,
          slug text not null unique,
          display_name text,
          short_name text,
          abbreviation text
        );
        CREATE TABLE public.ncaab_events (
          espn_event_id bigint primary key,
          game_id text not null unique,
          season integer not null,
          game_date text not null,
          commence_time text,
          home_espn_id integer not null,
          away_espn_id integer not null,
          neutral_site boolean,
          status text
        );
        CREATE TABLE public.latest_odds (
          game_id text not null,
          market text not null,
          bookmaker text not null,
          snapshot_at text not null,
          home_price numeric,
          away_price numeric,
          spread_home numeric,
          primary key (game_id, market, bookmaker)
        );
        CREATE TABLE public.ncaab_archive_lines (
          row_key text primary key,
          source text,
          season integer,
          game_date text,
          home_name text,
          away_name text,
          home_score integer,
          away_score integer,
          close_spread_home numeric,
          game_id text
        );
        CREATE TABLE public.ncaab_period_scores (
          game_id text,
          period integer,
          home_points integer,
          away_points integer
        );
    """)


def _reset(cur) -> None:
    cur.execute("""
        TRUNCATE
          internal.ncaab_margin_prices,
          internal.ncaab_margin_dk_odds,
          internal.ncaab_margin_results,
          internal.ncaab_margin_baseline,
          public.ncaab_events,
          public.latest_odds,
          public.ncaab_teams,
          public.ncaab_archive_lines,
          public.ncaab_period_scores,
          public.pipeline_log
    """)
    cur.execute("UPDATE internal.ncaab_margin_config SET min_baseline_n_games = 100")
    cur.execute("""
        INSERT INTO public.ncaab_teams
          (espn_id, school, slug, display_name, short_name, abbreviation)
        VALUES
          (%s, 'Duke', 'duke', 'Duke Blue Devils', 'Duke', 'DUKE'),
          (%s, 'North Carolina', 'north-carolina', 'North Carolina Tar Heels', 'UNC', 'UNC')
    """, (HOME, AWAY))


def _event(cur, game_id, commence, espn_event_id=1):
    et, _, _, _ = _future()
    cur.execute("""
        INSERT INTO public.ncaab_events
          (espn_event_id, game_id, season, game_date, commence_time,
           home_espn_id, away_espn_id, neutral_site, status)
        VALUES (%s, %s, 2027, %s, %s, %s, %s, false, 'STATUS_SCHEDULED')
    """, (espn_event_id, game_id, et.isoformat(), commence, HOME, AWAY))


def _baseline(cur, abs_spread, phase, n_games, p_dog_1_10=0.20):
    cur.execute("""
        INSERT INTO internal.ncaab_margin_baseline
          (abs_spread, season_phase, n_games, mean_margin, sd_margin,
           p_fav_1_10, p_fav_11p, p_dog_1_10, p_dog_11p, seasons_from, seasons_to)
        VALUES (%s, %s, %s, 7.5, 11, 0.40, 0.30, %s, 0.10, 2008, 2026)
    """, (abs_spread, phase, n_games, p_dog_1_10))


def _quote(cur, game_id, snap, book, market, spread, home_price, away_price):
    cur.execute("""
        INSERT INTO public.latest_odds
          (game_id, market, bookmaker, snapshot_at, spread_home, home_price, away_price)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    """, (game_id, market, book, snap, spread, home_price, away_price))


def _price_row(cur, game_id, commence):
    """Fav-side min odds are 244, so +300 clears. Dog 11+ min odds stay at 900."""
    cur.execute("""
        INSERT INTO internal.ncaab_margin_prices (
          game_id, game_date, commence_time, fav_team, dog_team, fav_is_home,
          fav_espn_id, dog_espn_id, center_spread, spread_source, season_phase,
          off_grid, below_sample_floor,
          fav_1_10_fair_prob, fav_1_10_min_odds,
          fav_11p_fair_prob, fav_11p_fair_american, fav_11p_min_odds,
          dog_1_10_fair_prob, dog_1_10_min_odds,
          dog_11p_fair_prob, dog_11p_min_odds, computed_at)
        VALUES (%s, CURRENT_DATE, %s::timestamptz,
                'Duke Blue Devils', 'North Carolina Tar Heels', true,
                %s, %s, -7.5, 'pinnacle', 'rest',
                false, false,
                0.40, 244,
                0.30, 233, 244,
                0.20, 244,
                0.10, 900, now())
    """, (game_id, commence, HOME, AWAY))


def _manual(cur, game_id, band, team, price, espn=None):
    cur.execute("""
        INSERT INTO internal.ncaab_margin_dk_odds (game_id, band, team, team_espn_id, dk_american)
        VALUES (%s, %s, %s, %s, %s)
    """, (game_id, band, team, espn, price))


@pytest.fixture(scope="module")
def db():
    psycopg2 = pytest.importorskip("psycopg2")
    from tests._pg import can_scratch, scratch_cluster

    if not can_scratch():
        pytest.skip("no scratch postgres")
    try:
        cluster = scratch_cluster("ncaab-margin-")
    except RuntimeError as exc:
        pytest.skip(str(exc))
    with cluster as dsn:
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        cur = conn.cursor()
        _roles(cur)
        _stubs(cur)
        cur.execute(SQL)
        cur.execute(SQL)
        try:
            yield conn
        finally:
            conn.close()


def test_the_file_stays_unapplied_and_the_floor_default_is_100():
    from data.view_migrations import ACTIVE_MIGRATIONS

    assert MIG.name not in ACTIVE_MIGRATIONS
    code = _code(SQL)
    assert "select true, 100" in code
    assert "select true, 1\n" not in code
    # The three archive cells Matt's 100 blanks, measured 2026-11-08.
    assert "rest, spread 35.0, 80 games" in SQL
    assert "rest, spread 34.5, 92 games" in SQL
    assert "nov,  spread 35.0, 97 games" in SQL
    assert code.count("order by (q.market = 'alternate_spreads') desc") == 4
    assert "last.fav_is_home is not distinct from fin.fav_home" in code
    assert "last.dog_1_10_fair_prob is not distinct from fin.p_dog_1_10" in code
    assert "ncaab_margin_team_side" in code


def test_default_floor_of_100_blanks_99_games_and_prices_100(db):
    cur = db.cursor()
    _reset(cur)
    cur.execute("SELECT min_baseline_n_games FROM internal.ncaab_margin_config")
    assert cur.fetchone()[0] == 100
    et, phase, commence, snap = _future()
    _baseline(cur, 7.5, phase, n_games=99)
    _event(cur, "g-floor", commence)
    _quote(cur, "g-floor", snap, "pinnacle", "spreads", -7.5, -110, -110)

    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 1
    cur.execute("""
        SELECT below_sample_floor, fav_11p_fair_prob, fav_11p_min_odds,
               fav_1_10_fair_prob, dog_1_10_fair_prob, dog_11p_fair_prob,
               fav_11p_fair_american
          FROM internal.ncaab_margin_prices WHERE game_id = 'g-floor'
    """)
    row = cur.fetchone()
    assert row[0] is True
    assert row[1:] == (None, None, None, None, None, None)

    _manual(cur, "g-floor", "fav_11p", "Duke Blue Devils", 300)
    cur.execute("""
        SELECT bet_flag FROM internal.ncaab_margin_edges
         WHERE game_id = 'g-floor' AND band = 'fav_11p'
    """)
    assert cur.fetchone()[0] is False

    cur.execute("""
        UPDATE internal.ncaab_margin_baseline SET n_games = 100
         WHERE abs_spread = 7.5 AND season_phase = %s
    """, (phase,))
    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 1
    cur.execute("""
        SELECT below_sample_floor, fav_11p_fair_prob, fav_1_10_fair_prob, fav_11p_min_odds
          FROM internal.ncaab_margin_prices
         WHERE game_id = 'g-floor'
         ORDER BY computed_at DESC LIMIT 1
    """)
    below, p11, p110, min_odds = cur.fetchone()
    assert below is False
    assert float(p11) == pytest.approx(0.30)
    assert float(p110) == pytest.approx(0.40)
    assert min_odds is not None


def test_baseline_refresh_nulls_probabilities_under_100(db):
    cur = db.cursor()
    _reset(cur)
    for i, score in ((1, 80), (2, 81)):
        cur.execute("""
            INSERT INTO public.ncaab_archive_lines
              (row_key, source, season, game_date, home_name, away_name,
               home_score, away_score, close_spread_home, game_id)
            VALUES (%s, 'prediction_tracker', 2025, '2024-11-15', 'Home', 'Away',
                    %s, 60, -10.5, %s)
        """, (f"a{i}", score, f"arch{i}"))
    cur.execute("SELECT internal.refresh_ncaab_margin_baseline()")
    cur.execute("""
        SELECT n_games, p_fav_11p, p_fav_1_10, mean_margin IS NOT NULL
          FROM internal.ncaab_margin_baseline
         WHERE abs_spread = 10.5 AND season_phase = 'nov'
    """)
    n_games, p11, p110, has_mean = cur.fetchone()
    assert n_games == 2
    assert p11 is None and p110 is None
    assert has_mean is True

    cur.execute("UPDATE internal.ncaab_margin_config SET min_baseline_n_games = 1")
    cur.execute("SELECT internal.refresh_ncaab_margin_baseline()")
    cur.execute("""
        SELECT p_fav_11p IS NOT NULL, p_dog_11p IS NOT NULL
          FROM internal.ncaab_margin_baseline
         WHERE abs_spread = 10.5 AND season_phase = 'nov'
    """)
    assert cur.fetchone() == (True, True)


def test_reapply_does_not_reset_a_floor_someone_stored(db):
    cur = db.cursor()
    cur.execute("UPDATE internal.ncaab_margin_config SET min_baseline_n_games = 80")
    cur.execute(SQL)
    cur.execute("SELECT min_baseline_n_games FROM internal.ncaab_margin_config")
    assert cur.fetchone()[0] == 80
    cur.execute("UPDATE internal.ncaab_margin_config SET min_baseline_n_games = 100")
    cur.execute("""
        SELECT has_table_privilege('anon', 'internal.ncaab_margin_config', 'SELECT'),
               has_table_privilege('service_role', 'internal.ncaab_margin_prices', 'SELECT')
    """)
    assert cur.fetchone() == (False, True)


def test_draftkings_alt_line_prefers_alternate_spreads(db):
    cur = db.cursor()
    _reset(cur)
    et, phase, commence, snap = _future()
    _baseline(cur, 7.5, phase, n_games=400)
    _event(cur, "g-alt", commence, espn_event_id=2)
    _quote(cur, "g-alt", snap, "pinnacle", "spreads", -7.5, -110, -110)
    # latest_odds keeps one row per (game, market, book). The collision is the
    # main spreads row and the alternate row at the same -10.5. The main row is
    # inserted second, so a limit 1 with no ORDER BY can see it last.
    _quote(cur, "g-alt", snap, "draftkings", "alternate_spreads", -10.5, 150, -180)
    _quote(cur, "g-alt", snap, "draftkings", "spreads", -10.5, -110, -110)

    _event(cur, "g-main", commence, espn_event_id=3)
    _quote(cur, "g-main", snap, "pinnacle", "spreads", -7.5, -110, -110)
    _quote(cur, "g-main", snap, "draftkings", "spreads", -10.5, -115, -105)

    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    cur.execute("""
        SELECT game_id, dk_alt_fav_m10_5, dk_alt_dog_m10_5
          FROM internal.ncaab_margin_prices
         ORDER BY game_id
    """)
    assert cur.fetchall() == [("g-alt", 150, None), ("g-main", -115, None)]


def test_favorite_flip_and_a_non_fav_band_each_write_a_row(db):
    cur = db.cursor()
    _reset(cur)
    et, phase, commence, snap = _future()
    _baseline(cur, 7.5, phase, n_games=400, p_dog_1_10=0.20)
    _event(cur, "g-flip", commence, espn_event_id=4)
    _quote(cur, "g-flip", snap, "pinnacle", "spreads", -7.5, -110, -110)

    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 1
    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 0

    cur.execute("""
        UPDATE public.latest_odds SET spread_home = 7.5
         WHERE game_id = 'g-flip' AND bookmaker = 'pinnacle'
    """)
    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 1
    cur.execute("""
        SELECT fav_is_home, fav_team, dog_team, fav_espn_id, dog_espn_id
          FROM internal.ncaab_margin_prices
         WHERE game_id = 'g-flip'
         ORDER BY computed_at DESC LIMIT 1
    """)
    assert cur.fetchone() == (False, "North Carolina Tar Heels", "Duke Blue Devils", AWAY, HOME)

    cur.execute("""
        UPDATE internal.ncaab_margin_baseline SET p_dog_1_10 = 0.25
         WHERE abs_spread = 7.5 AND season_phase = %s
    """, (phase,))
    cur.execute("SELECT internal.refresh_ncaab_margin_prices(%s)", (et,))
    assert cur.fetchone()[0] == 1
    cur.execute("""
        SELECT dog_1_10_fair_prob, fav_11p_fair_prob
          FROM internal.ncaab_margin_prices
         WHERE game_id = 'g-flip'
         ORDER BY computed_at DESC LIMIT 1
    """)
    dog, fav = cur.fetchone()
    assert float(dog) == pytest.approx(0.25)
    assert float(fav) == pytest.approx(0.30)
    cur.execute("SELECT count(*) FROM internal.ncaab_margin_prices WHERE game_id = 'g-flip'")
    assert cur.fetchone()[0] == 3


def test_graded_bet_flag_requires_the_band_team(db):
    cur = db.cursor()
    _reset(cur)
    _, _, commence, _ = _future()
    _event(cur, "g-grade", commence, espn_event_id=5)
    _price_row(cur, "g-grade", commence)
    cur.execute("""
        INSERT INTO internal.ncaab_margin_results
          (game_id, game_date, home_score, away_score, fav_team, fav_margin, band_hit)
        VALUES ('g-grade', CURRENT_DATE, 80, 60, 'Duke Blue Devils', 20, 'fav_11p')
    """)
    _manual(cur, "g-grade", "fav_11p", "North Carolina Tar Heels", 300)
    _manual(cur, "g-grade", "dog_11p", "Duke Blue Devils", 300)

    cur.execute("""
        SELECT band, bet_flag
          FROM internal.ncaab_margin_graded
         WHERE game_id = 'g-grade' AND band IN ('fav_11p', 'dog_11p', 'fav_1_10')
         ORDER BY band
    """)
    rows = dict(cur.fetchall())
    assert rows["fav_11p"] is False
    assert rows["dog_11p"] is False
    assert rows["fav_1_10"] is None

    _manual(cur, "g-grade", "fav_1_10", "Duke", 300)
    cur.execute("""
        SELECT bet_flag FROM internal.ncaab_margin_graded
         WHERE game_id = 'g-grade' AND band = 'fav_1_10'
    """)
    assert cur.fetchone()[0] is True


def test_manual_odds_match_aliases_and_espn_and_reject_a_typo(db):
    psycopg2 = pytest.importorskip("psycopg2")
    cur = db.cursor()
    _reset(cur)
    _, _, commence, _ = _future()
    _event(cur, "g-name", commence, espn_event_id=6)
    _price_row(cur, "g-name", commence)

    _manual(cur, "g-name", "fav_11p", "  duke   blue   devils ", 300)
    _manual(cur, "g-name", "fav_1_10", "Duke", 300)
    _manual(cur, "g-name", "dog_1_10", "not the display name", 300, espn=AWAY)
    _manual(cur, "g-name", "dog_11p", "Duke Blue Devils", 300, espn=AWAY)

    cur.execute("""
        SELECT band, team_mismatch, bet_flag
          FROM internal.ncaab_margin_edges
         WHERE game_id = 'g-name'
         ORDER BY band
    """)
    got = {band: (mismatch, flag) for band, mismatch, flag in cur.fetchall()}
    assert got["fav_11p"] == (False, True)   # normalized display name, price clears
    assert got["fav_1_10"] == (False, True)   # school name, not the display name
    assert got["dog_1_10"] == (False, True)   # espn id wins over a contradictory name
    assert got["dog_11p"] == (False, False)   # espn id is the dog; +300 does not clear 900

    with pytest.raises(psycopg2.Error) as exc:
        _manual(cur, "g-name", "fav_11p", "Dukke", 300)
    assert "exactly one side" in str(exc.value)

    with pytest.raises(psycopg2.Error) as missing:
        _manual(cur, "no-such-game", "fav_11p", "Duke", 300)
    assert "no ncaab_events row" in str(missing.value)
