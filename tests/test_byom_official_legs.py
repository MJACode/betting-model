"""The official pick (first match) beside the closing line, the main-model
staking, and the bet list. Matt, 2026-11-04."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.official import RoleClock, game_official_legs, prop_official_legs

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_official_legs_2026_11_04.sql"
KICK = datetime(2026, 10, 27, 0, 15, tzinfo=timezone.utc)


def _q(market, hours_before, point=None, home=None, away=None, **extra):
    snap = KICK - timedelta(hours=hours_before)
    return {"market": market, "snapshot_at": snap, "lead_hours": float(hours_before),
            "point": point, "price_home": home, "price_away": away, **extra}


FACT = {
    "canonical_key": "2026_07_DAL_PHI", "sport": "NFL", "season": 2026,
    "home_team": "PHI", "away_team": "DAL",
    "home_score": Decimal("21"), "away_score": Decimal("38"),
}


def _legs(**kw):
    out = {}
    for leg in game_official_legs(FACT, kw.get("h2h", []), kw.get("spreads", []),
                                  kw.get("totals", [])):
        out[(leg["market"], leg["leg_side"], leg["match_role"])] = leg
    return out


def test_the_lock_is_the_first_quote_that_fits_the_role_not_the_close():
    # PHI opens a 2.5 favorite, flips to a 4.5 dog. The moneyline follows.
    spreads = [_q("spreads", 300, -2.5, -110, -110),
               _q("spreads", 100, 3.0, -115, -105),
               _q("spreads", 1, 4.5, -110, -110)]
    h2h = [_q("h2h", 299, None, -135, 115),
           _q("h2h", 99, None, 140, -165),
           _q("h2h", 1, None, 185, -225)]
    legs = _legs(h2h=h2h, spreads=spreads)

    # Home dog: first moneyline quote after the flip, not the +185 close.
    dog = legs[("h2h", "home", "underdog")]
    assert dog["price"] == Decimal("140")
    assert dog["locked_at"] == KICK - timedelta(hours=99)
    assert dog["result"] == "loss"
    # Any role: the first priced quote of all.
    assert legs[("h2h", "home", "any")]["price"] == Decimal("-135")
    assert legs[("h2h", "home", "any")]["leg_role"] == "favorite"
    # Home favorite only fits before the flip.
    assert legs[("h2h", "home", "favorite")]["price"] == Decimal("-135")
    # Nobody was ever a pick'em, so no row: a model asking for one has no bet.
    assert ("h2h", "home", "pickem") not in legs
    # The away side is the mirror.
    assert legs[("h2h", "away", "favorite")]["price"] == Decimal("-165")


def test_a_spread_locks_its_own_point_and_grades_on_it():
    spreads = [_q("spreads", 300, -2.5, -110, -110),
               _q("spreads", 100, 3.0, -115, -105)]
    legs = _legs(spreads=spreads)
    home_dog = legs[("spreads", "home", "underdog")]
    # point is the HOME number. PHI +3 lost by 17.
    assert home_dog["point"] == Decimal("3.0")
    assert home_dog["price"] == Decimal("-115")
    assert home_dog["result"] == "loss"
    away_fav = legs[("spreads", "away", "favorite")]
    assert away_fav["point"] == Decimal("3.0")
    assert away_fav["result"] == "win"


def test_a_quote_without_a_price_or_a_point_is_not_official_and_kickoff_bounds_it():
    spreads = [_q("spreads", 200, -3.0, None, None),
               _q("spreads", 150, None, -110, -110),
               _q("spreads", 120, -3.5, -108, -112),
               _q("spreads", -1, -9.5, -110, -110)]
    totals = [_q("totals", 140, 44.5, 1.91, -110),
              _q("totals", 130, 45.0, -112, -108)]
    legs = _legs(spreads=spreads, totals=totals)
    assert legs[("spreads", "home", "any")]["point"] == Decimal("-3.5")
    # A decimal price is not American: the over waits, the under does not.
    assert legs[("totals", "over", "any")]["point"] == Decimal("45.0")
    assert legs[("totals", "under", "any")]["point"] == Decimal("44.5")
    # A total has no role, so only `any`.
    assert ("totals", "over", "underdog") not in legs


def test_no_spread_yet_means_no_role_so_only_any_matches():
    h2h = [_q("h2h", 300, None, 150, -170)]
    spreads = [_q("spreads", 10, 3.5, -110, -110)]
    legs = _legs(h2h=h2h, spreads=spreads)
    assert legs[("h2h", "home", "any")]["leg_role"] is None
    # The first h2h quote is before any spread, so it cannot be a dog lock.
    assert ("h2h", "home", "underdog") not in legs


def test_the_role_clock_holds_the_last_spread():
    clock = RoleClock([_q("spreads", 50, -1.0, -110, -110),
                       _q("spreads", 10, 1.0, -110, -110)])
    assert clock.home_role(KICK - timedelta(hours=60)) is None
    assert clock.home_role(KICK - timedelta(hours=30)) == "favorite"
    assert clock.home_role(KICK) == "underdog"


def test_a_prop_locks_on_the_first_priced_line_and_grades_on_that_line():
    clock = RoleClock([_q("spreads", 300, 3.5, -110, -110)])
    fact = {"canonical_key": "k", "sport": "NFL", "season": 2026,
            "market": "player_pass_yds", "player_key": "jalen hurts",
            "team": "PHI", "actual": Decimal("231"), "log_status": "logged"}
    pool = [
        {"snapshot_at": KICK - timedelta(hours=200), "lead_hours": 200.0,
         "point": Decimal("224.5"), "over_price": -115, "under_price": None,
         "captured_at": None, "prop_id": 1},
        {"snapshot_at": KICK - timedelta(hours=100), "lead_hours": 100.0,
         "point": Decimal("235.5"), "over_price": -110, "under_price": -110,
         "captured_at": None, "prop_id": 2},
    ]
    rows = {(r["leg_side"], r["match_role"]): r
            for r in prop_official_legs(fact, pool, clock, "PHI", "DAL")}
    assert rows[("over", "any")]["point"] == Decimal("224.5")
    assert rows[("over", "any")]["result"] == "win"
    assert rows[("under", "any")]["point"] == Decimal("235.5")
    assert rows[("under", "any")]["result"] == "win"
    assert rows[("over", "underdog")]["leg_role"] == "underdog"
    assert ("over", "favorite") not in rows
    # A player who did not play is not graded.
    gone = dict(fact, log_status="non_participant", actual=None)
    assert all(r["result"] is None
               for r in prop_official_legs(gone, pool, clock, "PHI", "DAL"))


# ── SQL ─────────────────────────────────────────────────────────────────────

def test_the_file_is_registered_and_guards_on_what_it_builds():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert SQL_NAME in ACTIVE_MIGRATIONS
    text = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "byom_official_legs_v1" in text
    # The guard never casts a table that may not exist.
    guard = text.split("RAISE NOTICE 'byom official legs already present")[0]
    assert "'public.byom_official_legs'::regclass" not in guard


@pytest.fixture
def scratch():
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
            CREATE ROLE anon NOLOGIN; CREATE ROLE authenticated NOLOGIN;
            CREATE SCHEMA auth;
            CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
              SELECT NULLIF(current_setting('byom.uid', true), '')::uuid $$;
            GRANT USAGE ON SCHEMA auth TO anon, authenticated;
        """)
        for name in ("byom_facts_schema_2026_10_16.sql",
                     "byom_dk_start_price_2026_10_23.sql",
                     "byom_prop_facts_dk_prices_2026_10_28.sql",
                     "byom_saved_models_2026_10_16.sql",
                     "byom_prop_phase_a_filters_2026_10_29.sql",
                     SQL_NAME, SQL_NAME):
            cur.execute((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))
        cur.execute("""
            INSERT INTO byom_game_facts (
              canonical_key, sport, season, week, away_team, home_team,
              game_date, commence_time, line_basis, home_score, away_score,
              dk_spread_home, dk_total, home_rest_days, away_rest_days,
              home_role, away_role, is_primetime,
              ml_home_result, ml_away_result, dk_ml_home_price, dk_ml_away_price,
              ats_home_result, ats_away_result,
              dk_spread_home_price, dk_spread_away_price,
              ou_over_result, ou_under_result,
              dk_total_over_price, dk_total_under_price)
            VALUES
              ('2026_07_DAL_PHI', 'NFL', 2026, 7, 'DAL', 'PHI', '2026-10-26',
               '2026-10-27 00:15:00+00', 'DraftKings line at game start', 21, 38,
               4.5, 47.5, 7, 7, 'underdog', 'favorite', true,
               'loss', 'win', 185, -225, 'loss', 'win', -110, -110,
               'win', 'loss', -110, -110),
              ('2026_06_DAL_GB', 'NFL', 2026, 6, 'DAL', 'GB', '2026-10-18',
               '2026-10-19 00:20:00+00', 'DraftKings line at game start', 23, 13,
               1.5, 44.5, 7, 7, 'underdog', 'favorite', true,
               'win', 'loss', -105, -115, 'win', 'loss', -110, -110,
               'loss', 'win', -110, -110),
              ('2026_05_NYJ_KC', 'NFL', 2026, 5, 'NYJ', 'KC', '2026-10-11',
               '2026-10-11 17:00:00+00', 'DraftKings line at game start', 30, 10,
               -10.5, 44.5, 7, 7, 'favorite', 'underdog', false,
               'win', 'loss', -500, 380, 'win', 'loss', -110, -110,
               'loss', 'win', -110, -110);
            INSERT INTO byom_official_legs (
              canonical_key, sport, season, market, leg_side, player_key,
              match_role, leg_role, team, locked_at, point, price, result)
            VALUES
              ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'home', '', 'any',
               'favorite', 'PHI', '2026-10-15 00:00+00', NULL, -135, 'loss'),
              ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'home', '', 'underdog',
               'underdog', 'PHI', '2026-10-22 00:00+00', NULL, 140, 'loss'),
              ('2026_07_DAL_PHI', 'NFL', 2026, 'spreads', 'away', '', 'any',
               'underdog', 'DAL', '2026-10-15 00:00+00', 2.5, -110, 'win'),
              ('2026_06_DAL_GB', 'NFL', 2026, 'h2h', 'home', '', 'underdog',
               'underdog', 'GB', '2026-10-10 00:00+00', NULL, 120, 'win'),
              ('2026_05_NYJ_KC', 'NFL', 2026, 'h2h', 'home', '', 'any',
               'favorite', 'KC', '2026-10-01 00:00+00', NULL, -400, 'win');
        """)
        yield psycopg2, cur
    finally:
        if raw is not None:
            raw.close()
        cluster.stop()


def _record(cur, filters):
    cur.execute("SELECT timing, bets, wins, losses, units, risked "
                "FROM byom_record(2026, %s::jsonb) ORDER BY timing", (filters,))
    return {row[0]: tuple(row[1:]) for row in cur.fetchall()}


def test_home_dogs_in_primetime_both_timings(scratch):
    _pg, cur = scratch
    rec = _record(cur, '{"markets":["h2h"],"side":"home","role":"underdog","primetime":true}')
    # Close: GB -105 won (+1u), PHI +185 lost (risk 100/185).
    bets, wins, losses, units, risked = rec["close"]
    assert (bets, wins, losses) == (2, 1, 1)
    assert float(units) == pytest.approx(1 - 100 / 185)
    # Official: GB +120 won, PHI +140 lost. Locked prices, not the close.
    bets, wins, losses, units, _ = rec["official"]
    assert (bets, wins, losses) == (2, 1, 1)
    assert float(units) == pytest.approx(1 - 100 / 140)


def test_risk_is_capped_at_three_units_like_stake_for(scratch):
    _pg, cur = scratch
    rec = _record(cur, '{"markets":["h2h"],"side":"home","primetime":false}')
    # KC -500 won at close: risk capped at 3u, so the win is 3 * 100/500.
    assert float(rec["close"][3]) == pytest.approx(0.6)
    assert float(rec["close"][4]) == pytest.approx(3)
    # Official -400 win: risk 3u, win 0.75u.
    assert float(rec["official"][3]) == pytest.approx(0.75)


def test_backtest_keeps_its_columns_and_is_the_close(scratch):
    _pg, cur = scratch
    cur.execute("SELECT market, bets, wins, losses, pushes, ties, units, skipped "
                "FROM byom_backtest(2026, '{\"markets\":[\"h2h\"],\"side\":\"home\"}')")
    rows = cur.fetchall()
    assert [r[0] for r in rows] == ["h2h"]
    assert rows[0][1:4] == (3, 2, 1)


def test_bet_list_labels_come_from_the_stored_fields(scratch):
    _pg, cur = scratch
    cur.execute("SELECT label, price, result, units, total_bets FROM byom_bets("
                "2026, '{\"markets\":[\"spreads\"],\"side\":\"away\"}', 'close')")
    rows = cur.fetchall()
    # Away spread is the negative of the stored HOME number.
    assert [r[0] for r in rows] == ["DAL -4.5", "DAL -1.5", "NYJ +10.5"]
    assert rows[0][4] == 3
    cur.execute("SELECT label FROM byom_bets("
                "2026, '{\"markets\":[\"spreads\"],\"side\":\"away\"}', 'official')")
    assert cur.fetchall() == [("DAL -2.5",)]
    cur.execute("SELECT byom_leg_label('spreads','home','PHI',0,NULL), "
                "byom_leg_label('totals','under',NULL,47.50,NULL), "
                "byom_leg_label('player_anytime_td','over',NULL,0.5,'A.J. Brown'), "
                "byom_leg_label('player_pass_yds','over',NULL,224.50,'Jalen Hurts')")
    assert cur.fetchone() == ("PHI PK", "Under 47.5", "A.J. Brown Yes",
                              "Jalen Hurts Over 224.5")


def test_anon_reads_and_cannot_write(scratch):
    psycopg2, cur = scratch
    cur.execute("SET ROLE anon")
    try:
        cur.execute("SELECT count(*) FROM byom_record(2026, '{}')")
        assert cur.fetchone()[0] > 0
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cur.execute("DELETE FROM byom_official_legs")
    finally:
        cur.execute("RESET ROLE")


def test_unknown_keys_and_timing_still_raise(scratch):
    psycopg2, cur = scratch
    with pytest.raises(psycopg2.errors.RaiseException, match="unknown filter key: stake"):
        cur.execute("SELECT * FROM byom_record(2026, '{\"stake\":1}')")
    with pytest.raises(psycopg2.errors.RaiseException, match="timing"):
        cur.execute("SELECT * FROM byom_bets(2026, '{}', 'open')")
