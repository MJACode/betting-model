"""The official pick (first match) beside the closing line, the main-model
staking, and the bet list. Matt, 2026-11-04."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from byom.official import (
    RoleClock,
    first_fit,
    game_lock_candidates,
    game_official_legs,
    prop_lock_candidates,
    prop_official_legs,
)

ROOT = Path(__file__).resolve().parents[1]
SQL_NAME = "byom_official_legs_2026_11_04.sql"
BAND_SQL = "byom_official_lock_bands_2026_11_04.sql"
LOCK_READ_SQL = "byom_official_legs_lock_read_idx_2026_11_04.sql"
PUSHDOWN_SQL = "byom_official_market_pushdown_2026_11_04.sql"
PROP_LOOKUP_SQL = "byom_prop_lookup_2026_11_04.sql"
NHL_SQL = "byom_nhl_2026_11_05.sql"
SAVE_SQL = "byom_save_filters_2026_11_05.sql"
UNITS_SQL = "byom_units_inline_2026_11_05.sql"
TREND_SQL = "byom_trend_filters_2026_11_05.sql"
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


def test_underdog_spread_band_locks_the_first_quote_inside_it_not_the_open():
    # Ex A. Home opens +2.5, then +3.5. Underdogs +3 to +7 lock +3.5.
    spreads = [_q("spreads", 300, 2.5, -110, -110),
               _q("spreads", 100, 3.5, -110, -110)]
    home = [row for row in game_lock_candidates(FACT, [], spreads, [])
            if (row["market"], row["leg_side"]) == ("spreads", "home")]
    locked = first_fit(home, role="underdog", min_spread=3, max_spread=7)
    assert locked["point"] == Decimal("3.5")
    assert locked["team_spread"] == Decimal("3.5")
    assert locked["locked_at"] == KICK - timedelta(hours=100)
    # The open is a candidate, and it is the role-only lock.
    assert first_fit(home, role="underdog")["point"] == Decimal("2.5")


def test_moneyline_price_band_locks_the_first_quote_inside_it():
    # Ex B. ML dogs +150 to +250. Opens +260, then +200. Lock +200.
    spreads = [_q("spreads", 300, 3.5, -110, -110)]
    h2h = [_q("h2h", 280, None, 260, -320),
           _q("h2h", 100, None, 200, -240)]
    home = [row for row in game_lock_candidates(FACT, h2h, spreads, [])
            if (row["market"], row["leg_side"]) == ("h2h", "home")]
    locked = first_fit(home, role="underdog", min_price=150, max_price=250)
    assert locked["price"] == Decimal("200")
    assert locked["locked_at"] == KICK - timedelta(hours=100)
    assert first_fit(home, role="underdog")["price"] == Decimal("260")


def test_a_total_band_and_a_prop_line_band_lock_the_first_quote_inside_them():
    spreads = [_q("spreads", 300, 3.0, -110, -110)]
    totals = [_q("totals", 200, 51.0, -110, -110),
              _q("totals", 50, 45.5, -110, -110)]
    over = [row for row in game_lock_candidates(FACT, [], spreads, totals)
            if (row["market"], row["leg_side"]) == ("totals", "over")]
    locked = first_fit(over, min_total=44, max_total=48)
    assert locked["point"] == Decimal("45.5")
    assert locked["game_total"] == Decimal("45.5")
    # A spread bet reads the total in force at its own quote.
    home_spread = [row for row in game_lock_candidates(FACT, [], spreads, totals)
                   if (row["market"], row["leg_side"]) == ("spreads", "home")]
    # The only spread quote is 300h before the 45.5 total, so the total
    # in force is the 51 that opened at 200h? 300h is earlier than 200h.
    # At 300 hours before kickoff no total has posted yet.
    assert home_spread[0]["game_total"] is None
    clock = RoleClock(spreads)
    fact = {"canonical_key": "k", "sport": "NFL", "season": 2026,
            "market": "player_pass_yds", "player_key": "jalen hurts",
            "team": "PHI", "actual": Decimal("231"), "log_status": "logged"}
    pool = [
        {"snapshot_at": KICK - timedelta(hours=200), "lead_hours": 200.0,
         "point": Decimal("180.5"), "over_price": -110, "under_price": -110,
         "captured_at": None, "prop_id": 1},
        {"snapshot_at": KICK - timedelta(hours=50), "lead_hours": 50.0,
         "point": Decimal("220.5"), "over_price": -115, "under_price": -105,
         "captured_at": None, "prop_id": 2},
    ]
    overs = [row for row in prop_lock_candidates(fact, pool, clock, "PHI", "DAL")
             if row["leg_side"] == "over"]
    line = first_fit(overs, min_line=200, max_line=240)
    assert line["point"] == Decimal("220.5")
    assert line["result"] == "win"


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
    assert BAND_SQL in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(BAND_SQL) == ACTIVE_MIGRATIONS.index(SQL_NAME) + 1
    text = (ROOT / "data/migrations" / SQL_NAME).read_text(encoding="utf-8")
    assert "byom_official_legs_v1" in text
    # The guard never casts a table that may not exist.
    guard = text.split("RAISE NOTICE 'byom official legs already present")[0]
    assert "'public.byom_official_legs'::regclass" not in guard
    bands = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    assert "byom_official_lock_bands_v1" in bands
    # The previous file's guard still sees its marker in the replaced body.
    assert "byom_official_legs_v1" in bands.split("CREATE OR REPLACE FUNCTION public.byom_legs", 1)[1]


def test_byom_legs_forces_a_custom_plan():
    """#1172 Medium, Matt via CE. A pooled connection must not switch
    byom_legs to a generic plan that skips idx_byom_prop_facts_market.
    The skip is that proconfig entry, so a body applied before the SET
    is replaced once."""
    text = (ROOT / "data/migrations" / PROP_LOOKUP_SQL).read_text(encoding="utf-8")
    fn = text.split("CREATE OR REPLACE FUNCTION public.byom_legs", 1)[1]
    head = fn.split("AS $body$", 1)[0]
    assert "SET search_path = public, pg_temp" in head
    assert "SET plan_cache_mode = force_custom_plan" in head
    guard = text.split("RAISE NOTICE 'byom prop lookup already present", 1)[0]
    assert "'plan_cache_mode=force_custom_plan' = ANY (p.proconfig)" in guard
    assert "CREATE OR REPLACE" not in guard


def test_the_lock_read_index_is_registered_and_guarded():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert LOCK_READ_SQL in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(LOCK_READ_SQL) == ACTIVE_MIGRATIONS.index(BAND_SQL) + 1
    text = (ROOT / "data/migrations" / LOCK_READ_SQL).read_text(encoding="utf-8")
    assert text.count("DO $mig$") == 1
    assert "to_regclass('public.idx_byom_official_legs_lock_read') IS NULL" in text
    assert (
        "CREATE INDEX IF NOT EXISTS idx_byom_official_legs_lock_read\n"
        "      ON public.byom_official_legs\n"
        "      (sport, season, match_role, canonical_key, market, leg_side, player_key, locked_at);"
    ) in text
    assert "CREATE OR REPLACE FUNCTION" not in text
    assert "ALTER TABLE" not in text


def test_lock_bands_skip_matches_named_identity_arguments():
    """The skip is one to_regprocedure match. A types-only identity
    comparison never matches, so the ALTER ran on every pass. A body
    stored as `p_filters %s` is not skipped, and the replacement calls
    jsonb_exists."""
    bands = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    code = "\n".join(ln.split("--", 1)[0] for ln in bands.splitlines())
    # One skip: to_regprocedure of the exact signature, and a body the
    # adapter stored as `p_filters %s` is rebuilt. Not a second copy.
    sig = "to_regprocedure('public.byom_legs(integer, jsonb, text)')"
    predicate = "position('p_filters %s' in p.prosrc) = 0"
    assert code.count(f"p.oid = {sig}") == 1
    assert "pg_get_function_identity_arguments" not in code
    assert code.count(predicate) == 1
    head = code.split("ALTER TABLE", 1)[0]
    assert "byom official lock bands already present" in head
    assert "RETURN;" in head
    assert "CREATE OR REPLACE" not in head
    assert predicate in head
    # A fresh database still has the DDL after the skip. The version
    # marker is a comment inside the function, so it is read from the
    # file rather than from the comment-stripped guard.
    body = bands.split("RETURN;", 1)[1]
    assert "jsonb_exists(p_filters, 'primetime')" in body
    assert "jsonb_exists(p_filters, 'months')" in body
    assert "jsonb_exists(p_filters, 'weekdays')" in body
    assert "jsonb_exists(p_filters, 'kick_slots')" in body
    assert "jsonb_exists(p_filters, 'opponents')" in body
    assert "p_filters ?" not in body
    assert "ADD COLUMN IF NOT EXISTS team_spread" in body
    assert "ADD COLUMN IF NOT EXISTS game_total" in body
    assert "ADD COLUMN IF NOT EXISTS context_at_lock" in body
    assert "ADD PRIMARY KEY" in body
    assert "byom_official_lock_bands_v1" in body


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
                     SQL_NAME, SQL_NAME, BAND_SQL, BAND_SQL,
                     LOCK_READ_SQL, LOCK_READ_SQL, PUSHDOWN_SQL, PUSHDOWN_SQL,
                     PROP_LOOKUP_SQL, PROP_LOOKUP_SQL, NHL_SQL, NHL_SQL,
                     SAVE_SQL, SAVE_SQL,
                     UNITS_SQL, UNITS_SQL, TREND_SQL, TREND_SQL):
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


def test_spread_and_price_bands_move_the_official_lock(scratch):
    """Ex A and Ex B, in the RPC. The close stays outside the band."""
    _pg, cur = scratch
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
          ('2026_08_BUF_KC', 'NFL', 2026, 8, 'BUF', 'KC', '2026-11-02',
           '2026-11-03 00:20:00+00', 'DraftKings line at game start', 24, 20,
           8.0, 51.0, 7, 7, 'underdog', 'favorite', false,
           'loss', 'win', 260, -320, 'loss', 'win', -110, -110,
           'loss', 'win', -110, -110);
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result,
          team_spread, game_total, context_at_lock)
        VALUES
          ('2026_08_BUF_KC', 'NFL', 2026, 'spreads', 'home', '', 'any',
           'underdog', 'KC', '2026-10-20 00:00+00', 2.5, -110, 'loss',
           2.5, 51.0, true),
          ('2026_08_BUF_KC', 'NFL', 2026, 'spreads', 'home', '', 'any',
           'underdog', 'KC', '2026-10-28 00:00+00', 3.5, -110, 'win',
           3.5, 47.0, true),
          ('2026_08_BUF_KC', 'NFL', 2026, 'h2h', 'home', '', 'any',
           'underdog', 'KC', '2026-10-20 00:00+00', NULL, 260, 'loss',
           2.5, 51.0, true),
          ('2026_08_BUF_KC', 'NFL', 2026, 'h2h', 'home', '', 'any',
           'underdog', 'KC', '2026-10-28 00:00+00', NULL, 200, 'win',
           3.5, 47.0, true);
    """)
    cur.execute("""
        SELECT point, price FROM byom_bets(
          2026,
          '{"markets":["spreads"],"side":"home","role":"underdog",
            "weeks":[8],"min_team_spread":3,"max_team_spread":7}',
          'official')
    """)
    assert cur.fetchall() == [(Decimal("3.5"), Decimal("-110"))]
    cur.execute("""
        SELECT price FROM byom_bets(
          2026,
          '{"markets":["h2h"],"side":"home","role":"underdog",
            "weeks":[8],"min_price":150,"max_price":250}',
          'official')
    """)
    assert cur.fetchall() == [(Decimal("200"),)]
    # The closing spread is +8 and the closing price is +260. Neither band
    # keeps the close. The official lock is not dropped because of that.
    cur.execute("""
        SELECT timing, bets FROM byom_record(
          2026,
          '{"markets":["spreads"],"side":"home","role":"underdog",
            "weeks":[8],"min_team_spread":3,"max_team_spread":7}')
         ORDER BY timing
    """)
    assert cur.fetchall() == [("official", 1)]


def test_an_old_role_row_still_reads_the_closing_spread(scratch):
    """Before the rebuild, context_at_lock is false and the band uses the close."""
    _pg, cur = scratch
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
          ('2026_09_NYJ_NE', 'NFL', 2026, 9, 'NYJ', 'NE', '2026-11-08',
           '2026-11-09 00:20:00+00', 'DraftKings line at game start', 17, 20,
           4.0, 44.0, 7, 7, 'underdog', 'favorite', false,
           'loss', 'win', 160, -190, 'win', 'loss', -110, -110,
           'loss', 'win', -110, -110);
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result)
        VALUES
          ('2026_09_NYJ_NE', 'NFL', 2026, 'spreads', 'home', '', 'underdog',
           'underdog', 'NE', '2026-11-01 00:00+00', 2.5, -110, 'win');
    """)
    cur.execute("""
        SELECT point, price FROM byom_bets(
          2026,
          '{"markets":["spreads"],"side":"home","role":"underdog",
            "weeks":[9],"min_team_spread":3,"max_team_spread":7}',
          'official')
    """)
    # The stored point is +2.5. The close is +4, which is inside +3 to +7,
    # so the pre-rebuild row is kept. The lock does not move to a quote
    # that was never stored.
    assert cur.fetchall() == [(Decimal("2.5"), Decimal("-110"))]


def test_a_missing_official_table_skips_the_write_and_logs(caplog):
    import logging

    from byom.load import write_official_legs

    class Conn:
        def __init__(self):
            self.writes = []

        def execute(self, sql, params=None):
            self.writes.append(sql)
            class Result:
                def fetchone(_self):
                    return (False,)
            return Result()

        def executemany(self, sql, rows):
            raise AssertionError("official write ran")

    conn = Conn()
    with caplog.at_level(logging.ERROR, logger="byom.load"):
        assert write_official_legs(conn, ["2026_08_BUF_KC"], [{"canonical_key": "x"}], False) == 0
    assert any("official-leg write skipped" in rec.message for rec in caplog.records)
    assert all("DELETE" not in sql and "INSERT" not in sql for sql in conn.writes)


def test_a_healthy_lock_bands_body_skips_the_rebuild(scratch):
    """The to_regprocedure skip still returns when prosrc has no
    `p_filters %s`. Run through the adapter, the way the worker runs it."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("""
        SELECT xmin::text,
               position('p_filters %s' in prosrc),
               position('jsonb_exists(p_filters, ''primetime'')' in prosrc) > 0
          FROM pg_proc WHERE proname = 'byom_legs'
    """)
    before, pct, healed = cur.fetchone()
    assert pct == 0
    assert healed is True
    text = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    cur.execute(_adapt_sql(text))
    cur.execute("""
        SELECT xmin::text, position('%s' in prosrc), position('?' in prosrc)
          FROM pg_proc WHERE proname = 'byom_legs'
    """)
    after, pct, qmark = cur.fetchone()
    assert after == before
    assert pct == 0
    assert qmark == 0


def test_a_damaged_byom_legs_body_rebuilds_despite_the_skip_guard(scratch):
    """The to_regprocedure skip matches once the bands marker is present
    and prosrc has no `p_filters %s`. A body the adapter stored as
    `p_filters %s` must still be replaced, once, with jsonb_exists and
    no bare `?`."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("""
        DO $$ DECLARE src text; BEGIN
          SELECT pg_get_functiondef('public.byom_legs(integer, jsonb, text)'::regprocedure)
            INTO src;
          EXECUTE replace(src,
            'jsonb_exists(p_filters, ''primetime'')',
            'p_filters %s ''primetime''');
        END $$
    """)
    cur.execute("""
        SELECT position('p_filters %s' in prosrc) > 0,
               position('byom_official_lock_bands_v1' in prosrc) > 0,
               pg_get_function_identity_arguments(oid)
          FROM pg_proc
         WHERE proname = 'byom_legs'
    """)
    damaged, marked, identity = cur.fetchone()
    assert damaged is True
    assert marked is True
    assert identity == "p_season integer, p_filters jsonb, p_timing text"
    band = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    adapted = _adapt_sql(band)
    assert adapted.count("to_regprocedure('public.byom_legs(integer, jsonb, text)')") == 1
    assert adapted.count("position('p_filters %s' in p.prosrc) = 0") == 1
    assert "jsonb_exists(p_filters, 'primetime')" in adapted
    assert "p_filters ?" not in adapted
    cur.execute(adapted)
    cur.execute("""
        SELECT position('%s' in prosrc),
               position('?' in prosrc),
               position('jsonb_exists(p_filters, ''primetime'')' in prosrc) > 0,
               position('byom_official_lock_bands_v1' in prosrc) > 0,
               xmin::text
          FROM pg_proc WHERE proname = 'byom_legs'
    """)
    pct, qmark, healed, marked, first = cur.fetchone()
    assert pct == 0
    assert qmark == 0
    assert healed is True
    assert marked is True
    cur.execute(adapted)
    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] == first
    cur.execute("SELECT count(*) FROM byom_record(2026, '{\"primetime\":true}')")
    assert cur.fetchone()[0] >= 0


def test_an_applied_lock_bands_migration_takes_no_table_lock(scratch):
    """The second pass is a catalog read. A reader holding the table
    must not make it wait on AccessExclusiveLock."""
    psycopg2, cur = scratch
    cur.execute("""
        SELECT pg_get_function_identity_arguments(p.oid)
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
         WHERE n.nspname = 'public' AND p.proname = 'byom_legs'
    """)
    identity = cur.fetchone()[0]
    assert identity == "p_season integer, p_filters jsonb, p_timing text"
    cur.execute("""
        SELECT a.attname
          FROM pg_attribute a
         WHERE a.attrelid = 'public.byom_official_legs'::regclass
           AND a.attname IN ('team_spread', 'game_total', 'context_at_lock')
           AND NOT a.attisdropped
    """)
    assert {row[0] for row in cur.fetchall()} == {
        "team_spread", "game_total", "context_at_lock"}
    cur.execute("""
        SELECT a.attname
          FROM pg_constraint c
          JOIN pg_attribute a
            ON a.attrelid = c.conrelid AND a.attnum = ANY (c.conkey)
         WHERE c.conrelid = 'public.byom_official_legs'::regclass
           AND c.contype = 'p'
         ORDER BY a.attnum
    """)
    assert [row[0] for row in cur.fetchall()] == [
        "canonical_key", "market", "leg_side", "player_key", "match_role",
        "locked_at"]
    sql = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    holder = psycopg2.connect(cur.connection.dsn)
    holder.autocommit = False
    try:
        holder.cursor().execute(
            "LOCK TABLE public.byom_official_legs IN ACCESS SHARE MODE")
        cur.execute("SET lock_timeout = '200ms'")
        cur.execute(sql)
    finally:
        cur.execute("RESET lock_timeout")
        holder.rollback()
        holder.close()


def test_unknown_keys_and_timing_still_raise(scratch):
    psycopg2, cur = scratch
    with pytest.raises(psycopg2.errors.RaiseException, match="unknown filter key: stake"):
        cur.execute("SELECT * FROM byom_record(2026, '{\"stake\":1}')")
    with pytest.raises(psycopg2.errors.RaiseException, match="timing"):
        cur.execute("SELECT * FROM byom_bets(2026, '{}', 'open')")


def test_a_second_pass_leaves_byom_legs_alone(scratch):
    """2026-11-04: the lock-bands guard compared identity arguments without
    their names, never matched, and re-created byom_legs on every worker
    pass, each time through data.db's adapter. A re-run must not touch the
    function. Run through the adapter, the way the worker runs it."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    before = cur.fetchone()[0]
    for name in (SQL_NAME, BAND_SQL, LOCK_READ_SQL):
        text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
        cur.execute(_adapt_sql(text))
    cur.execute("SELECT xmin::text, position('%s' in prosrc) FROM pg_proc WHERE proname = 'byom_legs'")
    after, pct = cur.fetchone()
    assert after == before
    assert pct == 0


def test_a_byom_legs_without_force_custom_plan_is_rebuilt_once(scratch):
    """Production applied #1172 before plan_cache_mode was set. The next
    pass must add it, then leave the function alone."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute(
        "ALTER FUNCTION public.byom_legs(integer, jsonb, text) "
        "RESET plan_cache_mode")
    cur.execute(
        "SELECT 'plan_cache_mode=force_custom_plan' = ANY (proconfig) "
        "FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] is not True
    text = _adapt_sql(
        (ROOT / "data/migrations" / PROP_LOOKUP_SQL).read_text(encoding="utf-8"))
    cur.execute(text)
    cur.execute(
        "SELECT 'plan_cache_mode=force_custom_plan' = ANY (proconfig), "
        "'search_path=public, pg_temp' = ANY (proconfig), xmin::text "
        "FROM pg_proc WHERE proname = 'byom_legs'")
    has_plan, has_path, first = cur.fetchone()
    assert has_plan is True
    assert has_path is True
    cur.execute(text)
    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] == first


def test_every_byom_legs_file_skips_once_nhl_is_applied(scratch):
    """2026-11-05: the worker runs every file each pass, in order. The
    NHL body must satisfy the prop-lookup skip (force_custom_plan, #1173),
    or prop lookup rebuilds byom_legs without NHL and the NHL file
    rebuilds it again, every pass."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    before = cur.fetchone()[0]
    for name in (SQL_NAME, BAND_SQL, LOCK_READ_SQL, PUSHDOWN_SQL,
                 PROP_LOOKUP_SQL, NHL_SQL):
        text = (ROOT / "data/migrations" / name).read_text(encoding="utf-8")
        cur.execute(_adapt_sql(text))
    cur.execute(
        "SELECT xmin::text, position('byom_nhl_v1' in prosrc) > 0, "
        "'plan_cache_mode=force_custom_plan' = ANY (proconfig) "
        "FROM pg_proc WHERE proname = 'byom_legs'")
    after, nhl, plan = cur.fetchone()
    assert after == before
    assert nhl is True
    assert plan is True


def _save(cur, name, filters):
    cur.execute("SELECT set_config('byom.uid', '11111111-1111-1111-1111-111111111111', false)")
    cur.execute("SELECT bets, wins FROM byom_save_model(%s, %s::jsonb, 2026)",
                (name, filters))
    saved = cur.fetchone()
    cur.execute("SELECT filters FROM byom_models WHERE name = %s", (name,))
    return saved, cur.fetchone()[0]


def test_a_saved_model_keeps_every_filter_the_preview_grades(scratch):
    """Matt, 2026-11-05: the live save kept 9 keys and dropped the rest,
    so a saved model graded different bets than its preview."""
    _pg, cur = scratch
    game = ('{"markets":["h2h"],"side":"home","min_price":-450,"max_price":150,'
            '"months":[10],"weekdays":[0],"kick_slots":["early","prime"],'
            '"opponents":["DAL","NYJ"],"min_team_spread":-12,"max_team_spread":5,'
            '"min_game_total":40,"max_game_total":50,"weeks":[5,6,7],'
            '"min_rest_days":6,"primetime":null}')
    saved, stored = _save(cur, "every key", game)
    want = {k: v for k, v in __import__("json").loads(game).items() if v is not None}
    assert stored == want
    cur.execute("SELECT coalesce(sum(bets), 0), coalesce(sum(wins), 0) "
                "FROM byom_backtest(2026, %s::jsonb)", (game,))
    assert saved[0] >= 1, "the fixture must leave bets to grade"
    assert tuple(saved) == tuple(cur.fetchone())

    prop = ('{"markets":["player_pass_yds"],"prop_side":"over","min_line":200,'
            '"max_line":240,"player":"Jalen Hurts"}')
    _saved, stored = _save(cur, "prop keys", prop)
    assert stored == __import__("json").loads(prop)


def test_the_save_refuses_what_the_preview_refuses(scratch):
    psycopg2 = pytest.importorskip("psycopg2")
    _pg, cur = scratch
    cases = [
        ('{"markets":["h2h"],"side":"home","spread_size":3}', "unknown filter key: spread_size"),
        ('{"markets":["h2h"],"side":"home","stake":1}', "stake filters are not accepted"),
        ('{"markets":["h2h"],"side":"home","Months":[10]}', "filter keys must be lowercase"),
        ('{"markets":["h2h"],"side":"home","months":[13]}', "unknown filter key: months"),
        ('{"sport":"NHL","markets":["spreads"],"role":"pickem"}', "Pick'em is not an NHL role"),
    ]
    for i, (filters, message) in enumerate(cases):
        with pytest.raises(psycopg2.errors.RaiseException, match=message):
            _save(cur, f"bad {i}", filters)
    cur.execute("SELECT count(*) FROM byom_models WHERE name LIKE 'bad %'")
    assert cur.fetchone()[0] == 0


def test_the_nhl_file_still_skips_after_the_save_file(scratch):
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_save_model'")
    before = cur.fetchone()[0]
    for name in (NHL_SQL, SAVE_SQL):
        cur.execute(_adapt_sql(
            (ROOT / "data/migrations" / name).read_text(encoding="utf-8")))
    cur.execute("SELECT xmin::text, position('byom_save_filters_v1' in prosrc) > 0 "
                "FROM pg_proc WHERE proname = 'byom_save_model'")
    after, marker = cur.fetchone()
    assert after == before and marker is True


def test_the_staking_functions_inline_and_keep_the_staking(scratch):
    """2026-11-05: a SET clause stopped the planner inlining the two
    staking functions, four full calls per row, 2.6s of a 2.7s NBA
    record. No SET, the same 1u-to-win staking, and the planner inlines
    them (the plan names no function)."""
    _pg, cur = scratch
    cur.execute(
        "SELECT proname, proconfig FROM pg_proc "
        "WHERE proname IN ('byom_risk_units', 'byom_win_units') ORDER BY 1")
    assert cur.fetchall() == [("byom_risk_units", None), ("byom_win_units", None)]
    cur.execute("""
        SELECT x, byom_risk_units(x), byom_win_units(x)
          FROM (VALUES (-110::numeric), (150), (-400), (100), (-105.5), (50),
                       (NULL::numeric)) v(x)""")
    def r6(v):
        return None if v is None else round(float(v), 6)

    got = {r6(row[0]): (r6(row[1]), r6(row[2])) for row in cur.fetchall()}
    assert got[-110.0] == (1.1, 1.0)
    assert got[150.0] == (0.666667, 1.0)
    assert got[-400.0] == (3.0, 0.75)
    assert got[100.0] == (1.0, 1.0)
    assert got[-105.5] == (None, None)
    assert got[50.0] == (None, None)
    assert got[None] == (None, None)
    cur.execute(
        "EXPLAIN (VERBOSE) SELECT sum(byom_win_units(g::numeric)), "
        "sum(byom_risk_units(g::numeric)) FROM generate_series(-500, 500) g")
    plan = "\n".join(r[0] for r in cur.fetchall())
    assert "byom_win_units" not in plan and "byom_risk_units" not in plan, plan


def test_a_second_pass_leaves_the_staking_functions_alone(scratch):
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("SELECT string_agg(xmin::text, ',' ORDER BY proname) FROM pg_proc "
                "WHERE proname IN ('byom_risk_units', 'byom_win_units')")
    before = cur.fetchone()[0]
    for name in (SQL_NAME, BAND_SQL, PROP_LOOKUP_SQL, NHL_SQL, UNITS_SQL):
        cur.execute(_adapt_sql(
            (ROOT / "data/migrations" / name).read_text(encoding="utf-8")))
    cur.execute("SELECT string_agg(xmin::text, ',' ORDER BY proname) FROM pg_proc "
                "WHERE proname IN ('byom_risk_units', 'byom_win_units')")
    assert cur.fetchone()[0] == before


def test_the_units_file_is_registered_after_nhl():
    from data.view_migrations import ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(UNITS_SQL) > ACTIVE_MIGRATIONS.index(NHL_SQL)


def _close_h2h(cur, filters):
    cur.execute("SELECT canonical_key, leg_side FROM byom_legs(2026, %s::jsonb, 'close') "
                "WHERE market = 'h2h' ORDER BY 1, 2", (filters,))
    return cur.fetchall()


def test_division_game_and_last_game_filters(scratch):
    """Matt, 2026-11-05: more inputs to narrow game bets. DAL@PHI is an
    NFC East game; DAL lost at GB the week before (the fixture's games)."""
    _pg, cur = scratch
    assert _close_h2h(cur, '{"markets":["h2h"],"side":"home","division_game":true}') == [
        ("2026_07_DAL_PHI", "home")]
    assert ("2026_07_DAL_PHI", "home") not in _close_h2h(
        cur, '{"markets":["h2h"],"side":"home","division_game":false}')
    # DAL's previous game this season (week 6 at GB) was a loss.
    assert _close_h2h(cur, '{"markets":["h2h"],"side":"away","prev_result":"lost"}') == [
        ("2026_07_DAL_PHI", "away")]
    assert _close_h2h(cur, '{"markets":["h2h"],"side":"away","prev_result":"won"}') == []
    # DAL covered nothing at GB: ats_away_result 'loss'.
    assert _close_h2h(cur, '{"markets":["h2h"],"side":"away","prev_ats":"not_covered"}') == [
        ("2026_07_DAL_PHI", "away")]
    # A team's first game has no previous game, so a last-game filter drops it.
    assert ("2026_06_DAL_GB", "away") not in _close_h2h(
        cur, '{"markets":["h2h"],"side":"away","prev_result":"lost"}')


def test_a_last_game_filter_waits_for_that_game_on_the_official_line(scratch):
    """The official lock cannot use a result that is not in yet. DAL's
    week-6 game started 2026-10-19 00:20 UTC, so 'off a loss' is known at
    04:20. A stored quote is the line until the next one: the quote still
    live at 04:20 is the bet, made official at 04:20."""
    _pg, cur = scratch
    cur.execute("""
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result)
        VALUES
          ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'away', '', 'any',
           'underdog', 'DAL', '2026-10-15 00:00+00', NULL, 150, 'win'),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'away', '', 'any',
           'underdog', 'DAL', '2026-10-18 12:00+00', NULL, 170, 'win'),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'away', '', 'any',
           'underdog', 'DAL', '2026-10-20 12:00+00', NULL, 190, 'win')""")

    def official(filters):
        cur.execute("SELECT price, to_char(locked_at AT TIME ZONE 'UTC', 'MM-DD HH24:MI') "
                    "FROM byom_legs(2026, %s::jsonb, 'official') "
                    "WHERE canonical_key = '2026_07_DAL_PHI'", (filters,))
        return [(int(r[0]), r[1]) for r in cur.fetchall()]

    lost = '{"markets":["h2h"],"side":"away","prev_result":"lost"}'
    assert official(lost) == [(170, "10-19 04:20")]
    assert official('{"markets":["h2h"],"side":"away"}') == [(150, "10-15 00:00")]


def test_a_line_that_never_moved_after_the_last_game_is_not_dropped(scratch):
    """CE review #1187 H1: +150 posted before the GB game and unchanged to
    kickoff was bettable after the loss. It must not vanish."""
    _pg, cur = scratch
    cur.execute("""
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result)
        VALUES
          ('2026_07_DAL_PHI', 'NFL', 2026, 'h2h', 'away', '', 'any',
           'underdog', 'DAL', '2026-10-15 00:00+00', NULL, 150, 'win')""")
    cur.execute("SELECT price, to_char(locked_at AT TIME ZONE 'UTC', 'MM-DD HH24:MI') "
                "FROM byom_legs(2026, '{\"markets\":[\"h2h\"],\"side\":\"away\","
                "\"prev_result\":\"lost\"}', 'official')")
    assert [(int(r[0]), r[1]) for r in cur.fetchall()] == [(150, "10-19 04:20")]


def test_line_move_uses_the_quote_that_was_bet_never_the_close(scratch):
    """PHI home spread opened -3, moved to -4.5 (toward PHI), closed -4.5
    in this test. Official 'toward' locks the -4.5 quote; official 'none'
    locks the opener; the close compares -4.5 to the opener."""
    _pg, cur = scratch
    cur.execute("""
        UPDATE byom_game_facts SET dk_spread_home = -4.5, ats_home_result = 'win',
               ats_away_result = 'loss'
         WHERE canonical_key = '2026_07_DAL_PHI';
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result)
        VALUES
          ('2026_07_DAL_PHI', 'NFL', 2026, 'spreads', 'home', '', 'any',
           'favorite', 'PHI', '2026-10-14 00:00+00', -3, -110, 'win'),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'spreads', 'home', '', 'any',
           'favorite', 'PHI', '2026-10-18 00:00+00', -4.5, -110, 'win')""")

    def legs(filters, timing):
        cur.execute("SELECT point FROM byom_legs(2026, %s::jsonb, %s) "
                    "WHERE canonical_key = '2026_07_DAL_PHI'", (filters, timing))
        return [float(r[0]) for r in cur.fetchall()]

    home = '{"markets":["spreads"],"side":"home","line_move":"%s"}'
    assert legs(home % "toward", "official") == [-4.5]
    assert legs(home % "none", "official") == [-3.0]
    assert legs(home % "against", "official") == []
    assert legs(home % "toward", "close") == [-4.5]
    assert legs(home % "none", "close") == []
    away = '{"markets":["spreads"],"side":"away","line_move":"against"}'
    cur.execute("SELECT count(*) FROM byom_legs(2026, %s::jsonb, 'close') "
                "WHERE canonical_key = '2026_07_DAL_PHI'", (away,))
    assert cur.fetchone()[0] == 1


def test_line_move_and_divisions_are_plain_functions(scratch):
    _pg, cur = scratch
    cur.execute("""
        SELECT byom_line_move('spreads', 'home', -3, -110, -4.5, -110),
               byom_line_move('spreads', 'away', -3, -110, -4.5, -110),
               byom_line_move('totals', 'over', 44.5, -110, 46, -110),
               byom_line_move('totals', 'under', 44.5, -110, 46, -110),
               byom_line_move('player_points', 'over', 20.5, -110, 20.5, -120),
               byom_line_move('h2h', 'home', NULL, -150, NULL, -170),
               byom_line_move('h2h', 'away', NULL, 130, NULL, 150),
               byom_line_move('spreads', 'home', NULL, NULL, -3, -110)""")
    assert cur.fetchone() == ("toward", "against", "toward", "against", "none",
                              "toward", "against", None)
    cur.execute("SELECT proname, proconfig FROM pg_proc "
                "WHERE proname IN ('byom_line_move', 'byom_team_division') ORDER BY 1")
    assert cur.fetchall() == [("byom_line_move", None), ("byom_team_division", None)]


# Team codes byom_game_facts held on 2026-11-05 (Supabase, per sport).
_CODES = {
    "NFL": "ARI ATL BAL BUF CAR CHI CIN CLE DAL DEN DET GB HOU IND JAX KC LA LAC "
           "LV MIA MIN NE NO NYG NYJ PHI PIT SEA SF TB TEN WAS",
    "NBA": "ATL BKN BOS CHA CHI CLE DAL DEN DET GSW HOU IND LAC LAL MEM MIA MIL "
           "MIN NOP NYK OKC ORL PHI PHX POR SAC SAS TOR UTA WAS",
    "NHL": "ANA BOS BUF CAR CBJ CGY CHI COL DAL DET EDM FLA LAK MIN MTL NJD NSH "
           "NYI NYR OTT PHI PIT SEA SJS STL TBL TOR UTA VAN VGK WPG WSH",
}


def test_every_team_has_one_division_each_season(scratch):
    _pg, cur = scratch
    cases = [("NFL", 2020, 32, 8), ("NFL", 2026, 32, 8), ("NBA", 2021, 30, 6),
             ("NBA", 2027, 30, 6), ("NHL", 2020, 31, 4), ("NHL", 2021, 31, 4),
             ("NHL", 2022, 32, 4), ("NHL", 2027, 32, 4)]
    for sport, season, teams, divisions in cases:
        codes = [c for c in _CODES[sport].split() if not (sport == "NHL" and season < 2022 and c == "SEA")]
        cur.execute("SELECT count(byom_team_division(%s, %s, t)), "
                    "count(DISTINCT byom_team_division(%s, %s, t)) "
                    "FROM unnest(%s::text[]) AS t", (sport, season, sport, season, codes))
        assert cur.fetchone() == (teams, divisions), (sport, season)
    cur.execute("SELECT byom_team_division('NHL', 2021, 'TOR'), "
                "byom_team_division('NHL', 2022, 'UTA'), byom_team_division('NHL', 2020, 'UTA'), "
                "byom_team_division('NFL', 2026, 'DAL') = byom_team_division('NFL', 2026, 'PHI')")
    assert cur.fetchone() == ("North", "Central", "Pacific", True)


def test_the_save_keeps_the_trend_filters_and_refuses_bad_values(scratch):
    psycopg2 = pytest.importorskip("psycopg2")
    _pg, cur = scratch
    keep = ('{"markets":["h2h"],"side":"away","line_move":"toward","prev_result":"lost",'
            '"prev_ats":"not_covered","prev_total":"over","division_game":true}')
    _saved, stored = _save(cur, "trends", keep)
    assert stored == __import__("json").loads(keep)
    for key, value in (("line_move", '"up"'), ("prev_result", '"tie"'),
                       ("prev_ats", '"push"'), ("prev_total", '"push"'),
                       ("division_game", '"yes"')):
        with pytest.raises(psycopg2.errors.RaiseException, match=f"unknown filter key: {key}"):
            _save(cur, f"bad {key}", '{"markets":["h2h"],"side":"home","%s":%s}' % (key, value))


def test_the_trend_file_leaves_earlier_byom_files_skipping(scratch):
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("SELECT string_agg(xmin::text, ',' ORDER BY proname) FROM pg_proc "
                "WHERE proname IN ('byom_legs', 'byom_save_model')")
    before = cur.fetchone()[0]
    for name in (SQL_NAME, BAND_SQL, PROP_LOOKUP_SQL, NHL_SQL, SAVE_SQL, UNITS_SQL, TREND_SQL):
        cur.execute(_adapt_sql((ROOT / "data/migrations" / name).read_text(encoding="utf-8")))
    cur.execute("SELECT string_agg(xmin::text, ',' ORDER BY proname) FROM pg_proc "
                "WHERE proname IN ('byom_legs', 'byom_save_model')")
    assert cur.fetchone()[0] == before
    cur.execute("SELECT 'plan_cache_mode=force_custom_plan' = ANY (proconfig) "
                "FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] is True


def test_no_active_migration_guards_on_unnamed_identity_arguments():
    """pg_get_function_identity_arguments returns 'p_season integer, ...'.
    A guard that compares it to 'integer, ...' never matches, so the file
    re-runs its DDL on every pass. Use to_regprocedure instead."""
    import re

    from data.view_migrations import ACTIVE_MIGRATIONS
    pattern = re.compile(r"pg_get_function_identity_arguments\([^)]*\)\s*=\s*'")
    hits = [name for name in ACTIVE_MIGRATIONS
            if pattern.search((ROOT / "data/migrations" / name).read_text(encoding="utf-8"))]
    assert hits == []


def test_a_damaged_body_is_rebuilt_once(scratch):
    """Production at 15:00 UTC held byom_legs with `p_filters %s`. The next
    pass after the fix must re-create it, then leave it alone. The shipped
    body calls jsonb_exists, so that is the call this damages."""
    _pg, cur = scratch
    from data.db import _adapt_sql

    cur.execute("""
        DO $$ DECLARE src text; BEGIN
          SELECT pg_get_functiondef('public.byom_legs(integer, jsonb, text)'::regprocedure)
            INTO src;
          EXECUTE replace(src,
            'jsonb_exists(p_filters, ''primetime'')',
            'p_filters %s ''primetime''');
        END $$
    """)
    cur.execute("SELECT position('p_filters %s' in prosrc) > 0 FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] is True
    band = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    cur.execute(_adapt_sql(band))
    cur.execute("SELECT position('%s' in prosrc), xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    pct, first = cur.fetchone()
    assert pct == 0
    cur.execute(_adapt_sql(band))
    cur.execute("SELECT xmin::text FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] == first
    cur.execute("SELECT count(*) FROM byom_record(2026, '{\"primetime\":true}')")
    assert cur.fetchone()[0] >= 0


def test_market_pushdown_returns_the_same_answers(scratch):
    """2026-11-04: byom_legs filters market and side inside the lock
    search. Every filter must return what the previous body returned."""
    _pg, cur = scratch
    filters = [
        '{}', '{"markets":["h2h"]}', '{"markets":["h2h"],"side":"home"}',
        '{"markets":["h2h"],"side":"home","role":"underdog","primetime":true}',
        '{"markets":["spreads"],"side":"away"}', '{"markets":["totals"],"side":"over"}',
        '{"markets":["h2h","spreads"],"role":"favorite"}',
        '{"markets":["h2h"],"min_price":100}',
    ]

    def snapshot():
        out = {}
        for f in filters:
            cur.execute("SELECT timing, market, bets, wins, losses, pushes, ties, "
                        "round(units, 6), skipped FROM byom_record(2026, %s::jsonb) "
                        "ORDER BY 1, 2", (f,))
            out[f] = cur.fetchall()
            cur.execute("SELECT label, price, result, round(units, 6) FROM byom_bets("
                        "2026, %s::jsonb, 'official')", (f,))
            out[f + "|bets"] = cur.fetchall()
        return out

    # Props too (review L1): two players, two markets, both sides, a line
    # that moves, so the one-market search has other markets to skip.
    cur.execute("""
        INSERT INTO byom_prop_facts (
          prop_key, canonical_key, sport, season, week, player_name, player_key,
          team, market, line, line_basis, log_status, actual,
          over_result, under_result, over_price, under_price)
        VALUES
          ('hurts', '2026_07_DAL_PHI', 'NFL', 2026, 7, 'Jalen Hurts', 'jalen hurts',
           'PHI', 'player_pass_yds', 230.5, 'DraftKings line at game start', 'logged',
           240, 'win', 'loss', -110, -110),
          ('dak', '2026_07_DAL_PHI', 'NFL', 2026, 7, 'Dak Prescott', 'dak prescott',
           'DAL', 'player_rush_yds', 12.5, 'DraftKings line at game start', 'logged',
           10, 'loss', 'win', -115, -105);
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result,
          team_spread, game_total, context_at_lock)
        VALUES
          ('2026_07_DAL_PHI', 'NFL', 2026, 'player_pass_yds', 'over', 'jalen hurts',
           'any', 'favorite', 'PHI', '2026-10-15 00:00+00', 224.5, -115, 'win', -2.5, 46.5, true),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'player_pass_yds', 'over', 'jalen hurts',
           'any', 'underdog', 'PHI', '2026-10-22 00:00+00', 235.5, 105, 'win', 3.0, 47.5, true),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'player_pass_yds', 'under', 'jalen hurts',
           'any', 'favorite', 'PHI', '2026-10-15 00:00+00', 224.5, -105, 'loss', -2.5, 46.5, true),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'player_rush_yds', 'over', 'dak prescott',
           'any', 'underdog', 'DAL', '2026-10-16 00:00+00', 14.5, -110, 'loss', 2.5, 46.5, true),
          ('2026_07_DAL_PHI', 'NFL', 2026, 'player_rush_yds', 'under', 'dak prescott',
           'any', 'underdog', 'DAL', '2026-10-16 00:00+00', 14.5, -110, 'win', 2.5, 46.5, true);
    """)
    filters.extend([
        '{"markets":["player_pass_yds"],"prop_side":"over"}',
        '{"markets":["player_pass_yds"],"prop_side":"under"}',
        '{"markets":["player_rush_yds"],"prop_side":"over","side":"away"}',
        '{"markets":["player_pass_yds"],"prop_side":"over","min_line":230,"max_line":240}',
        '{"markets":["player_pass_yds"],"prop_side":"over","min_price":100}',
        '{"markets":["player_pass_yds"],"prop_side":"over","player":"Jalen Hurts"}',
    ])
    cur.execute("SELECT position('byom_official_market_pushdown_v1' in prosrc) > 0, "
                "position('byom_prop_lookup_v1' in prosrc) > 0, "
                "'plan_cache_mode=force_custom_plan' = ANY (proconfig) "
                "FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone() == (True, True, True)
    cur.execute("SELECT count(*) FROM pg_indexes WHERE indexname IN "
                "('idx_byom_prop_facts_leg', 'idx_byom_prop_facts_market')")
    assert cur.fetchone()[0] == 2
    after = snapshot()
    band = (ROOT / "data/migrations" / BAND_SQL).read_text(encoding="utf-8")
    block = band[band.index("EXECUTE $fn$"):band.index("$fn$;") + len("$fn$;")]
    cur.execute("DO $x$ BEGIN " + block + " END $x$")
    cur.execute("SELECT position('byom_official_market_pushdown_v1' in prosrc) > 0 "
                "FROM pg_proc WHERE proname = 'byom_legs'")
    assert cur.fetchone()[0] is False
    before = snapshot()
    assert after == before
    assert any(rows for rows in after.values())



def test_a_prop_ignores_team_role_spread_and_total(scratch):
    """Review M1 on #1169: props are filtered on their own line and price
    only. A role or team-band filter on a prop changes nothing."""
    _pg, cur = scratch
    cur.execute("""
        INSERT INTO byom_prop_facts (
          prop_key, canonical_key, sport, season, week, player_name, player_key,
          team, market, line, line_basis, log_status, actual,
          over_result, under_result, over_price, under_price)
        VALUES ('hurts', '2026_07_DAL_PHI', 'NFL', 2026, 7, 'Jalen Hurts', 'jalen hurts',
                'PHI', 'player_pass_yds', 230.5, 'DraftKings line at game start', 'logged',
                240, 'win', 'loss', -110, -110);
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result,
          team_spread, game_total, context_at_lock)
        VALUES ('2026_07_DAL_PHI', 'NFL', 2026, 'player_pass_yds', 'over', 'jalen hurts',
                'any', 'favorite', 'PHI', '2026-10-15 00:00+00', 224.5, -115, 'win', -2.5, 46.5, true);
    """)
    base = '{"markets":["player_pass_yds"],"prop_side":"over"'

    def rec(extra):
        cur.execute("SELECT timing, bets, wins FROM byom_record(2026, %s::jsonb) ORDER BY 1",
                    (base + extra + "}",))
        return cur.fetchall()

    plain = rec("")
    assert plain == [("close", 1, 1), ("official", 1, 1)]
    assert rec(',"role":"underdog"') == plain
    assert rec(',"min_team_spread":5,"max_team_spread":10') == plain
    assert rec(',"min_game_total":60,"max_game_total":70') == plain
    # A game leg still honours them: bets without the band, none with it.
    cur.execute("SELECT count(*) FROM byom_record(2026, "
                "'{\"markets\":[\"h2h\"]}'::jsonb) WHERE bets > 0")
    assert cur.fetchone()[0] > 0
    cur.execute("SELECT count(*) FROM byom_record(2026, "
                "'{\"markets\":[\"h2h\"],\"min_game_total\":60}'::jsonb) WHERE bets > 0")
    assert cur.fetchone()[0] == 0



def test_nhl_game_bets_grade_label_and_save(scratch):
    """Matt, 2026-11-05: NHL game bets. Moneyline, puck line, totals."""
    _pg, cur = scratch
    cur.execute("""
        INSERT INTO byom_game_facts (
          canonical_key, sport, season, week, away_team, home_team,
          game_date, commence_time, line_basis, home_score, away_score,
          dk_spread_home, dk_total, home_rest_days, away_rest_days,
          home_role, away_role, ml_home_result, ml_away_result,
          dk_ml_home_price, dk_ml_away_price, ats_home_result, ats_away_result,
          dk_spread_home_price, dk_spread_away_price,
          ou_over_result, ou_under_result, dk_total_over_price, dk_total_under_price)
        VALUES ('NHL_2026-11-01_BOS_TOR', 'NHL', 2027, NULL, 'BOS', 'TOR',
                '2026-11-01', '2026-11-01 23:00:00+00', 'DraftKings line at game start',
                4, 2, -1.5, 6.5, 1, 2, 'favorite', 'underdog', 'win', 'loss',
                -150, 130, 'win', 'loss', 160, -190, 'loss', 'win', -110, -110);
        INSERT INTO byom_official_legs (
          canonical_key, sport, season, market, leg_side, player_key,
          match_role, leg_role, team, locked_at, point, price, result,
          team_spread, game_total, context_at_lock)
        VALUES ('NHL_2026-11-01_BOS_TOR', 'NHL', 2027, 'spreads', 'home', '',
                'any', 'favorite', 'TOR', '2026-10-31 15:00+00', -1.5, 175, 'win',
                -1.5, 6.5, true);
    """)
    cur.execute("SELECT timing, bets, wins FROM byom_record(2027, "
                "'{\"sport\":\"NHL\",\"markets\":[\"spreads\"],\"side\":\"home\"}') ORDER BY 1")
    assert cur.fetchall() == [("close", 1, 1), ("official", 1, 1)]
    cur.execute("SELECT label, price FROM byom_bets(2027, "
                "'{\"sport\":\"NHL\",\"markets\":[\"spreads\"],\"side\":\"home\"}', 'official')")
    assert cur.fetchall() == [("TOR -1.5", 175)]
    cur.execute("SELECT set_config('byom.uid', '11111111-1111-1111-1111-111111111111', false)")
    cur.execute("SELECT season FROM byom_save_model('Home puck line', "
                "'{\"sport\":\"NHL\",\"markets\":[\"spreads\"],\"side\":\"home\"}', 2027)")
    assert cur.fetchone()[0] == 2027
    cur.execute("SELECT sport FROM byom_models WHERE name = 'Home puck line'")
    assert cur.fetchone()[0] == "NHL"
