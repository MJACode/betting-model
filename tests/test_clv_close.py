"""The final close of a pre-game bet (tracking/clv_close.py, issue #1470).

The rule: the bet book's quote at our exact number, in its last pull before the
start, pulled AFTER the bet; the main line when it is ours, else the book's
alternate ladder no more than 15 minutes older than that last main pull;
otherwise no closing price (never a made-up 0.00).

The first half drives choose_close() with hand-built quotes: it is pure. The
second runs the real reads and the real write on a scratch Postgres
(tests/_pg.py): rows pulled before the bet, after the start, and from another
book must all be ignored, and the row's earlier values must be kept.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone

import pytest

from tracking import clv_close as cc

T0 = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)      # the start
BET_AT = T0 - timedelta(hours=3)


def _bet(**kw) -> cc.Bet:
    base = dict(pick_id=1, model_id="ncaab_spread_market", game_id="NCAAB_2026-11-19_a_b",
                pick_side="home", number=-3.5, kind="game", market="spreads", player=None,
                created_at=BET_AT, bound=T0, bet_price=-110.0, bet_book="draftkings",
                prop_market=None)
    base.update(kw)
    return cc.Bet(**base)


def _q(market, minutes_before, number, source="feed", **prices) -> cc.Quote:
    return cc.Quote(market, T0 - timedelta(minutes=minutes_before), number, prices, source)


# ── the rule, pure ───────────────────────────────────────────────────────────

def test_the_main_line_at_our_number_in_the_last_pull_is_the_close():
    bet = _bet()
    c = cc.choose_close(bet, [_q("spreads", 60, -3.5, home_price=-105),
                              _q("spreads", 4, -3.5, home_price=-125)])
    assert (c.odds, c.market, c.line, c.line_pts) == (-125, "spreads", -3.5, 0.0)
    assert cc.measure(bet, c)["clv_pct"] > 0


def test_a_moved_main_line_is_priced_from_the_alternate_ladder_at_our_number():
    bet = _bet()
    c = cc.choose_close(bet, [_q("spreads", 4, -5.5, home_price=-110),
                              _q("alternate_spreads", 6, -3.5, home_price=-160),
                              _q("alternate_spreads", 6, -4.5, home_price=-135)])
    assert (c.odds, c.market, c.line) == (-160, "alternate_spreads", -3.5)
    assert c.line_pts == 2.0                       # we laid two fewer than the close


def test_an_old_main_pull_at_our_number_is_not_the_close_once_the_line_moved():
    bet = _bet()
    c = cc.choose_close(bet, [_q("spreads", 90, -3.5, home_price=-110),
                              _q("spreads", 4, -5.5, home_price=-110)])
    assert c.odds is None and c.source == "none" and c.line == -5.5 and c.line_pts == 2.0


def test_an_alternate_ladder_much_older_than_the_last_main_pull_is_not_the_close():
    bet = _bet()
    c = cc.choose_close(bet, [_q("spreads", 2, -5.5, home_price=-110),
                              _q("alternate_spreads", 40, -3.5, home_price=-150)])
    assert c.odds is None


def test_the_other_side_and_the_other_sign_are_not_our_bet():
    away = _bet(pick_side="away", number=3.5)
    # A home -3.5 row prices the AWAY side at +3.5, not our home 3.5.
    c = cc.choose_close(away, [_q("spreads", 4, -3.5, home_price=-110, away_price=-110)])
    assert c.odds is None
    c = cc.choose_close(away, [_q("spreads", 4, 3.5, home_price=-110, away_price=-120)])
    assert c.odds == -120


def test_a_prop_under_with_only_overs_on_the_ladder_has_no_close():
    bet = _bet(kind="prop", market="player_rebounds", player="X", pick_side="under",
               number=5.5, prop_market="player_rebounds")
    c = cc.choose_close(bet, [_q("player_rebounds", 3, 6.5, over_price=-110, under_price=-110),
                              _q("player_rebounds_alternate", 3, 5.5, over_price=-150)])
    assert c.odds is None and c.line_pts == -1.0   # the close's 6.5 was the easier under


def test_no_pull_after_the_bet_is_no_close_not_zero():
    c = cc.choose_close(_bet(), [])
    assert c.source == "none" and c.odds is None and c.last_poll is None


def test_a_moneyline_has_no_ladder_and_no_number():
    bet = _bet(model_id="nhl_moneyline", market="h2h", number=None, pick_side="away")
    assert bet.alt is None
    c = cc.choose_close(bet, [_q("h2h", 5, None, home_price=-150, away_price=130)])
    assert c.odds == 130 and c.line is None and c.line_pts is None


def test_alternate_names():
    assert cc.alternate_market("spreads") == "alternate_spreads"
    assert cc.alternate_market("totals") == "alternate_totals"
    assert cc.alternate_market("spreads_h1") == "spreads_h1_alternate"
    assert cc.alternate_market("team_totals_home") == "team_totals_home_alternate"
    assert cc.alternate_market("player_points") == "player_points_alternate"
    assert cc.alternate_market("h2h") is None and cc.alternate_market("h2h_3way") is None


# ── the reads and the write, on a real Postgres ──────────────────────────────

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from data.view_migrations import _apply_one  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from pathlib import Path  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GAME = "NCAAB_2026-11-19_away_home"

SCHEMA = """
CREATE TABLE games (game_id text PRIMARY KEY, game_date text, home_team text, away_team text,
                    commence_time text);
CREATE TABLE picks (pick_id bigint PRIMARY KEY, model_id text, game_id text, game_date text,
  pick_side text, scored_line numeric, pick_label text, prop_market text, dk_odds numeric,
  decision_odds numeric, decision_book text, created_at text, game_time text, signal_type text,
  is_live boolean, closing_dk_odds numeric, closing_line numeric, clv_pct numeric, clv_pp numeric,
  line_clv_pts numeric, clv_beat_close boolean, clv_captured_at text, clv_method text,
  clv_close_book text, clv_bet_book text);
CREATE TABLE odds (game_id text, market text, bookmaker text, snapshot_type text, snapshot_at text,
  created_at text, spread_home numeric, total_line numeric, home_price numeric, away_price numeric,
  draw_price numeric, over_price numeric, under_price numeric);
CREATE TABLE player_prop_odds (game_id text, market text, bookmaker text, player_name text, line numeric,
  over_price numeric, under_price numeric, snapshot_at text, created_at text);
CREATE TABLE nba_schedule (game_id text, commence_time text, game_type text);
CREATE FUNCTION clv_game_market(m text) RETURNS text LANGUAGE sql IMMUTABLE AS
  $$ SELECT CASE WHEN m LIKE '%spread%' THEN 'spreads' WHEN m LIKE '%moneyline%' THEN 'h2h' ELSE 'totals' END $$;
CREATE FUNCTION clv_prop_key(m text) RETURNS text LANGUAGE sql IMMUTABLE AS
  $$ SELECT CASE WHEN m = 'nhl_prop_saves' THEN 'player_total_saves' END $$;
"""


@pytest.fixture(scope="module")
def cluster():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("clv-close-pg-") as d:
        yield d


_N = {"n": 0}


@pytest.fixture()
def db(cluster):
    _N["n"] += 1
    name = f"clv_close_t{_N['n']}_{int(time.time() * 1000) % 10_000_000}"
    admin = psycopg2.connect(cluster)
    admin.autocommit = True
    with admin.cursor() as cur:
        cur.execute(f"CREATE DATABASE {name}")
    dsn = cluster.replace("dbname=postgres", f"dbname={name}")
    raw = psycopg2.connect(dsn)
    with raw.cursor() as cur:
        cur.execute("DO $$ BEGIN CREATE ROLE anon NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        cur.execute("DO $$ BEGIN CREATE ROLE authenticated NOLOGIN; EXCEPTION WHEN duplicate_object THEN NULL; END $$")
        cur.execute(SCHEMA.split("\n", 1)[1])
    raw.commit()
    conn = DBConnection(raw, url=dsn)
    sql = (ROOT / "data" / "migrations" / "clv_close_2026_11_19.sql").read_text(encoding="utf-8")
    assert _apply_one(conn, "clv_close_2026_11_19.sql", sql) is None
    try:
        yield conn
    finally:
        raw.close()
        with admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {name}")
        admin.close()


def _z(t: datetime) -> str:
    return t.strftime("%Y-%m-%d %H:%M:%S+00")


def _odds(db, minutes_before, spread, home, book="draftkings", market="spreads",
          snapshot_minutes_before=None, typ="open"):
    fetched = T0 - timedelta(minutes=minutes_before)
    snap = T0 - timedelta(minutes=snapshot_minutes_before if snapshot_minutes_before is not None else minutes_before)
    db.execute("INSERT INTO odds VALUES (%s,%s,%s,%s,%s,%s,%s,NULL,%s,%s,NULL,NULL,NULL)",
               (GAME, market, book, typ, _z(snap), _z(fetched), spread, home, -home))
    db.commit()


def _pick(db, pick_id=7, created=BET_AT, line=-3.5, side="home", clv=0.0):
    db.execute("INSERT INTO games VALUES (%s,'2026-11-19','home','away',%s) ON CONFLICT DO NOTHING",
               (GAME, T0.strftime("%Y-%m-%dT%H:%M:%SZ")))
    db.execute("""INSERT INTO picks (pick_id, model_id, game_id, game_date, pick_side, scored_line, pick_label,
                  dk_odds, decision_odds, decision_book, created_at, signal_type, is_live, clv_pct,
                  clv_method, closing_dk_odds)
                  VALUES (%s,'ncaab_spread_market',%s,'2026-11-19',%s,%s,'Home -3.5',-110,-110,'draftkings',
                          %s,'BET',false,%s,'standard_v2',-110)""",
               (pick_id, GAME, side, line, _z(created), clv))
    db.commit()


def _row(db, sql, params=()):
    cur = db.execute(sql, params)
    cols = [d[0] for d in cur._cur.description]
    r = cur.fetchone()
    db.commit()
    return dict(zip(cols, r)) if r else None


def test_rows_before_the_bet_after_the_start_and_at_other_books_are_ignored(db):
    _pick(db)
    _odds(db, 200, -3.5, -105)                      # pulled before the bet
    _odds(db, 6, -3.5, -130)                        # the close
    _odds(db, -5, -3.5, -300)                       # pulled after the start
    _odds(db, 2, -3.5, -999, book="fanduel")        # another book
    bets = cc.load_bets(db, "p.pick_id = %s", (7,))
    close = cc.choose_close(bets[0], cc.feed_quotes(db, bets[0]))
    assert close.odds == -130


def test_a_pull_after_the_bet_whose_price_last_changed_before_it_is_still_the_close(db):
    _pick(db)
    _odds(db, 6, -3.5, -120, snapshot_minutes_before=400)   # book's last change long ago
    bets = cc.load_bets(db, "p.pick_id = %s", (7,))
    assert cc.choose_close(bets[0], cc.feed_quotes(db, bets[0])).odds == -120


def test_the_write_keeps_what_the_row_held_and_a_missing_close_is_null_not_zero(db):
    _pick(db, clv=0.0)
    _odds(db, 200, -3.5, -110)                      # only a pull before the bet
    res = cc.measure_started(db, now=T0 + timedelta(hours=1))
    assert res["unpriced"] == 1
    p = _row(db, "SELECT clv_pct, clv_method, closing_dk_odds FROM picks WHERE pick_id = 7")
    assert p == {"clv_pct": None, "clv_method": "standard_v2", "closing_dk_odds": None}
    m = _row(db, "SELECT source, before, rule FROM clv_close_measurements WHERE pick_id = 7")
    assert m["source"] == "none" and m["rule"] == cc.RULE
    before = m["before"] if isinstance(m["before"], dict) else json.loads(m["before"])
    assert float(before["clv_pct"]) == 0.0 and before["clv_method"] == "standard_v2"
    # measured once: a second pass leaves it alone
    assert cc.measure_started(db, now=T0 + timedelta(hours=2))["bets"] == 0


def test_the_stage_prices_from_the_ladder_and_waits_for_the_start(db):
    _pick(db)
    _odds(db, 5, -5.5, -110)
    _odds(db, 5, -3.5, -165, market="alternate_spreads")
    assert cc.measure_started(db, now=T0 + timedelta(minutes=5))["bets"] == 0   # not settled yet
    assert cc.measure_started(db, now=T0 + timedelta(minutes=30))["priced"] == 1
    p = _row(db, "SELECT clv_pct, closing_dk_odds, closing_line, line_clv_pts, clv_close_book FROM picks WHERE pick_id = 7")
    assert float(p["closing_dk_odds"]) == -165 and float(p["closing_line"]) == -3.5
    assert float(p["line_clv_pts"]) == 2.0 and p["clv_close_book"] == "draftkings"
    assert float(p["clv_pct"]) > 0


def test_the_tables_are_closed_to_the_app_roles(db):
    for t in ("clv_close_quotes", "clv_close_purchases", "clv_close_measurements"):
        r = _row(db, "SELECT has_table_privilege('anon', %s, 'SELECT') a, has_table_privilege('authenticated', %s, 'SELECT') b",
                 (f"public.{t}", f"public.{t}"))
        assert r == {"a": False, "b": False}, t


def test_one_bet_that_fails_does_not_stop_the_pass(db, monkeypatch):
    _pick(db, pick_id=7)
    _pick(db, pick_id=8)
    _odds(db, 5, -3.5, -130)
    real = cc.choose_close

    def boom(bet, quotes):
        if bet.pick_id == 7:
            raise ValueError("bad row")
        return real(bet, quotes)

    monkeypatch.setattr(cc, "choose_close", boom)
    res = cc.measure_started(db, now=T0 + timedelta(hours=1))
    assert res["failed"] == 1 and res["priced"] == 1
    m = _row(db, "SELECT source, note FROM clv_close_measurements WHERE pick_id = 7")
    assert m["source"] == "none" and "bad row" in m["note"]
    # and it is not picked up again, so it cannot pin the head of the queue
    assert cc.measure_started(db, now=T0 + timedelta(hours=2))["bets"] == 0
