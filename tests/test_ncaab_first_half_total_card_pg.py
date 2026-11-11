"""The NCAAB first-half total model end to end against a real Postgres: the
capture's tip-minus-60 call, the window's plan, the card's reads, its decision
and its bet, and the decided-once rule.

WHY A REAL DATABASE. The card finds its decision fetch's rows by their
created_at (the ledger's fetch_at, both the transaction's NOW()), reads each
game's full-game total consensus as of that instant through
unnest(...::timestamptz[]) and DISTINCT ON, and writes its decision and its bet
in one transaction under an advisory lock. None of that is a claim a fake can
check. No Odds API call: the event list and the event call are fakes. Runs
against LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and
SKIPS only where neither exists.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

psycopg2 = pytest.importorskip("psycopg2")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402
from data.anon_readable import API_ROLES  # noqa: E402
from data.db import DBConnection  # noqa: E402
from data.ingestors import ncaab_espn_box as box  # noqa: E402
from scripts import ncaab_first_half_spread_card as spread_card  # noqa: E402
from scripts import ncaab_first_half_total_card as card  # noqa: E402
from scripts import ncaab_first_half_window as win  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402
from tests.test_ncaab_first_half_spread_card_pg import (  # noqa: E402
    GAMES_DDL, LATEST_DDL, ODDS_DDL, PICKS_DDL, QUOTA_DDL,
)

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
FEED_HOME, FEED_AWAY = "Kansas Jayhawks", "Duke Blue Devils"


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-first-half-total-pg-") as d:
        yield d


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
def world(dsn, monkeypatch):
    """Today's game tipping 59.5 minutes from now (so the real NOW() of the
    fetch is its tip-minus-60 time), and yesterday's finished game of both
    teams with its halves and closing lines."""
    now = datetime.now(UTC).replace(microsecond=0)
    tip = now + timedelta(minutes=59, seconds=30)
    gdate = tip.astimezone(ET).date().isoformat()
    gid = f"NCAAB_{gdate}_duke_kansas"
    ptip = now - timedelta(days=1)
    pdate = ptip.astimezone(ET).date().isoformat()
    pid = f"NCAAB_{pdate}_duke_kansas_old"
    raw = psycopg2.connect(dsn)
    raw.autocommit = True
    cur = raw.cursor()
    for role in API_ROLES:
        cur.execute(f"DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
                    f"'{role}') THEN CREATE ROLE {role}; END IF; END $$")
    cur.execute("DROP TABLE IF EXISTS games, odds, latest_odds, odds_api_quota, picks, "
                "ncaab_period_scores, ncaab_first_half_fetches, ncaab_first_half_spread_decisions, "
                "ncaab_first_half_total_decisions, ncaab_first_half_team_games")
    for ddl in (GAMES_DDL, ODDS_DDL, LATEST_DDL, QUOTA_DDL, PICKS_DDL, box.PERIODS_DDL):
        cur.execute(ddl)
    cur.execute("INSERT INTO games VALUES (%s,'NCAAB',2027,%s,'Kansas','Duke',NULL,NULL,%s,0)",
                (gid, gdate, _iso(tip)))
    cur.execute("INSERT INTO games VALUES (%s,'NCAAB',2027,%s,'Kansas','Duke',70,60,%s,0)",
                (pid, pdate, _iso(ptip)))
    for p, h, a in ((1, 40, 25), (2, 30, 35)):
        cur.execute("INSERT INTO ncaab_period_scores (game_id, period, home_points, away_points, "
                    "espn_event_id, season, game_date, source) VALUES (%s,%s,%s,%s,1,2027,%s,'t')",
                    (pid, p, h, a, pdate))
    fg = []
    for g, t in ((pid, ptip), (gid, now)):
        for b, sp, tot in (("draftkings", -8.0, 140.5), ("fanduel", -8.5, 141.5), ("betmgm", -7.5, 140.5),
                           ("pinnacle", -2.0, 150.0)):
            fg.append((g, "spreads", b, _iso(t - timedelta(hours=2)), sp, None))
            fg.append((g, "totals", b, _iso(t - timedelta(hours=2)), None, tot))
        # stored after its tip / after the decision: never read
        fg.append((g, "totals", "draftkings", _iso(t + timedelta(minutes=30)), None, 170.0))
    for g, mk, b, snap, sp, tot in fg:
        cur.execute("INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, "
                    "snapshot_at, spread_home, total_line, created_at) VALUES "
                    "(%s,'NCAAB',%s,%s,'open',%s,%s,%s,%s)", (g, mk, b, snap, sp, tot, snap))
    cur.execute("INSERT INTO latest_odds VALUES (%s,'spreads','draftkings',-8.0)", (gid,))
    cur.execute("INSERT INTO odds_api_quota VALUES ('2026-11-01', 600000, 4400000, 'x'), "
                "('2026-11-02', 700000, 4300000, 'y')")

    def connect():
        return DBConnection(psycopg2.connect(dsn), url=dsn)

    import data.db
    monkeypatch.setattr(card, "get_connection", connect)
    monkeypatch.setattr(spread_card, "get_connection", connect)
    monkeypatch.setattr(win, "get_connection", connect)
    monkeypatch.setattr(data.db, "get_connection", connect)     # the feed's own connection
    monkeypatch.setattr(feed.ncaab_teams, "make_resolver", lambda conn, d, days_back=1, days_fwd=2: (
        lambda h, a, ct: (gid, False) if (h, a) == (FEED_HOME, FEED_AWAY) else None))

    def tot(book, line, over, under, age_min):
        return {"key": book, "last_update": _iso(now), "markets": [
            {"key": "totals_h1", "last_update": _iso(now - timedelta(minutes=age_min)), "outcomes": [
                {"name": "Over", "price": over, "point": line, "link": f"{book}/o"},
                {"name": "Under", "price": under, "point": line, "link": f"{book}/u"}]}]}
    body = {"bookmakers": [
        tot("fanduel", 69.5, -110, -110, 2),
        tot("draftkings", 69.5, -105, -115, 1),
        # the biggest edge, on an under shorter than -200: set aside before the pick
        tot("betmgm", 76.5, +190, -250, 3),
        tot("pinnacle", 69.5, -180, +150, 1)]}                   # not bettable
    calls = []
    monkeypatch.setattr(feed, "_list_events", lambda key: calls.append("events") or [
        {"id": "ev1", "home_team": FEED_HOME, "away_team": FEED_AWAY, "commence_time": _iso(tip)}])
    monkeypatch.setattr(feed, "_get_event_odds", lambda key, ev, mk: calls.append(ev) or body)
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    try:
        yield {"gid": gid, "pid": pid, "tip": tip, "raw": raw, "connect": connect, "calls": calls}
    finally:
        raw.close()


def q(raw, sql, params=None):
    cur = raw.cursor()
    cur.execute(sql, params)
    return cur.fetchall()


def test_the_tip_minus_60_fetch_decides_once_and_writes_the_bet(world):
    gid, raw = world["gid"], world["raw"]
    plan = win.plan_tick()
    assert plan.fetch == [gid] and plan.marks[gid] == "T-60"
    assert plan.total_card == [gid] and plan.card == []     # the spread decides at tip minus 10

    out = feed.fetch_first_half([gid])
    assert out["fetched"] == [gid] and not out["failed"] and world["calls"] == ["events", "ev1"]
    led = q(raw, "SELECT endpoint, mark, ok, main_rows, markets FROM ncaab_first_half_fetches "
                 "WHERE game_id = %s", (gid,))
    assert led == [("event_odds", "T-60", True, 4, "totals_h1")]
    assert not win.plan_tick().fetch               # satisfied until the next fetch time

    res = card.run_card(do_publish=True)
    assert res["published"] == 1 and res["decided"] == 1
    d = q(raw, "SELECT status, book, side, line, price, fg_total, fg_books, n_home, n_away, "
               "missing_halves, offers, book_ages, mu, lead_min FROM ncaab_first_half_total_decisions "
               "WHERE game_id = %s", (gid,))
    status, book, side, line, price, fgt, fgb, nh, na, miss, offers, ages, mu, lead = d[0]
    assert (status, book, side, line, price) == ("bets", "fanduel", "under", 69.5, -110)
    assert (fgt, fgb) == (140.5, 3)                # the three bettable books; Pinnacle and the late row out
    assert (nh, na, miss) == (1, 1, 0)             # yesterday's game counts for both
    assert 55.0 <= lead <= 60.5
    offers = {o["book"]: o for o in json.loads(offers)}
    assert set(offers) == {"betmgm", "draftkings", "fanduel"}
    assert offers["betmgm"]["edge"] > offers["fanduel"]["edge"]     # set aside by the -200 floor
    # every stored book's own update age, Pinnacle's too (the spread's ledger keeps the same)
    assert json.loads(ages) == {"betmgm": 3.0, "draftkings": 1.0, "fanduel": 2.0, "pinnacle": 1.0}
    # the mean the card used is the model's own, from the frozen artifact
    art = ft.load_artifact(2027)
    assert abs(mu - ft.first_half_mean(140.5, 0.0, 0.0, art)) < 0.5
    p = q(raw, "SELECT model_id, pick_side, pick_label, scored_line, decision_book, decision_odds, "
               "dk_odds, line_book, best_book, signal_type FROM picks WHERE game_id = %s", (gid,))
    assert p == [(ft.MODEL_ID, "under", "Duke @ Kansas — First Half Under 69.5", 69.5, "fanduel",
                  -110.0, -115.0, None, "fanduel", "BET")]
    tg = q(raw, "SELECT game_id, h1_home, h1_away, h2_home, h2_away, total_close, total_books "
                "FROM ncaab_first_half_team_games")
    assert tg == [(world["pid"], 40.0, 25.0, 30.0, 35.0, 140.5, 3)]

    # decided once: a second run, a moved line or a later tick writes nothing
    again = card.run_card(do_publish=True)
    assert again["published"] == 0 and again["decided"] == 0
    assert q(raw, "SELECT count(*) FROM picks") == [(1,)]
    assert q(raw, "SELECT count(*) FROM ncaab_first_half_total_decisions") == [(1,)]
    assert not win.plan_tick().total_card
    # the spread model has not decided it: its own fetch is fifty minutes later
    assert q(raw, "SELECT to_regclass('ncaab_first_half_spread_decisions') IS NULL") == [(True,)]
    conn = world["connect"]()
    try:
        assert card.first_decision(conn) is not None
    finally:
        conn.close()


def _earlier_bet(raw, gid, model_id, side, status=None, signal="BET"):
    with raw.cursor() as cur:
        cur.execute("INSERT INTO picks (game_id, model_id, sport, pick_side, pick_label, signal_type, "
                    "condition_status, model_probability, dk_implied_prob, edge) "
                    "VALUES (%s, %s, 'NCAAB', %s, %s, %s, %s, 0.6, 0.5, 0.1)",
                    (gid, model_id, side, f"Kansas vs Duke {side.title()} 140.5", signal, status))
    raw.commit()


def _first_half_stake(raw, gid):
    return q(raw, "SELECT stake_units, stake_reason FROM picks WHERE game_id = %s AND model_id = %s",
             (gid, ft.MODEL_ID))


def test_a_bet_an_earlier_full_game_total_agrees_with_is_two_units(world):
    """mike, 2026-11-06: the higher-confidence pick gets more units. The card
    bets the first-half Under; the full-game total model bet the Under first."""
    gid, raw = world["gid"], world["raw"]
    _earlier_bet(raw, gid, "ncaab_total_blend", "under")
    feed.fetch_first_half([gid])
    assert card.run_card(do_publish=True)["published"] == 1
    [(units, reason)] = _first_half_stake(raw, gid)
    assert float(units) == config.NCAAB_AGREEMENT_STAKE_UNITS == 2.0
    assert reason == "Two models agree: NCAAB Totals also bet Kansas vs Duke Under 140.5"


@pytest.mark.parametrize("side, status, signal", [
    ("over", None, "BET"),         # the other side is not agreement
    ("under", "VOID", "BET"),      # a voided pick does not count
    ("under", None, "NONE"),       # priced, not bet, does not count
])
def test_a_bet_nothing_earlier_agrees_with_stays_one_unit(world, side, status, signal):
    gid, raw = world["gid"], world["raw"]
    _earlier_bet(raw, gid, "ncaab_total_blend", side, status, signal)
    feed.fetch_first_half([gid])
    assert card.run_card(do_publish=True)["published"] == 1
    assert _first_half_stake(raw, gid) == [(None, None)]


def test_a_side_bet_is_not_agreement_for_a_total(world):
    gid, raw = world["gid"], world["raw"]
    _earlier_bet(raw, gid, "ncaab_spread_market", "under")    # wrong family, even with the same word
    feed.fetch_first_half([gid])
    assert card.run_card(do_publish=True)["published"] == 1
    assert _first_half_stake(raw, gid) == [(None, None)]


def test_a_dry_run_writes_nothing(world):
    gid, raw = world["gid"], world["raw"]
    feed.fetch_first_half([gid])
    res = card.run_card(do_publish=False)
    assert res["bets"] == 1 and res["published"] == 0
    assert q(raw, "SELECT count(*) FROM picks") == [(0,)]
    assert q(raw, "SELECT to_regclass('ncaab_first_half_total_decisions') IS NULL") == [(True,)]


def test_a_decision_fetch_is_not_decided_on_long_after_it_landed(world):
    """A run that comes ten minutes after the tip-minus-60 call would write its
    price as the bet's: the game is missed instead, never bet stale."""
    gid = world["gid"]
    feed.fetch_first_half([gid])
    with pytest.raises(card.CardIncomplete):
        card.run_card(do_publish=True, now=datetime.now(UTC) + timedelta(minutes=10))
    conn = world["connect"]()
    try:
        assert card.decided_games(conn, [gid]) == set()
    finally:
        conn.close()
    # in time, the same fetch decides
    assert card.run_card(do_publish=True)["decided"] == 1


def test_a_game_whose_decision_fetch_never_landed_is_reported_not_decided(world):
    gid = world["gid"]
    late = world["tip"] - timedelta(minutes=54)
    with pytest.raises(card.CardIncomplete):
        card.run_card(do_publish=True, now=late)
    conn = world["connect"]()
    try:
        assert card.decided_games(conn, [gid]) == set()
        # before the model's first decision the alerter names nothing for it
        assert card.first_decision(conn) is None
        assert win.undecided_games(conn, world["tip"] + timedelta(minutes=5),
                                   model=ft.MODEL_ID) == []
    finally:
        conn.close()
