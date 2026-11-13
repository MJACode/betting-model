"""The NCAAB first-half spread model end to end against a real Postgres: the
capture's ledger and rows, the window's plan, the card's reads, its decision
and its bet, and the decided-once rule.

WHY A REAL DATABASE. The card finds its decision fetch's rows by their
created_at (the ledger's fetch_at, both the transaction's NOW()), reads each
game's consensus as of that instant through unnest(...::timestamptz[]) and
DISTINCT ON, and writes its decision and its bet in one transaction under an
advisory lock. None of that is a claim a fake can check. No Odds API call: the
event list and the event call are fakes. Runs against LATEST_LINE_TEST_DSN or a
throwaway cluster from tests/_pg.py, and SKIPS only where neither exists.
"""
from __future__ import annotations

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

import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402
import models.ncaab_first_half_spread as fh  # noqa: E402
from data.anon_readable import API_ROLES  # noqa: E402
from data.db import DBConnection  # noqa: E402
from data.ingestors import ncaab_espn_box as box  # noqa: E402
from scripts import ncaab_first_half_spread_card as card  # noqa: E402
from scripts import ncaab_first_half_window as win  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
ET = ZoneInfo("America/New_York")
FEED_HOME, FEED_AWAY = "Kansas Jayhawks", "Duke Blue Devils"

GAMES_DDL = """
CREATE TABLE games (
    game_id TEXT PRIMARY KEY, sport TEXT NOT NULL, season INTEGER NOT NULL,
    game_date TEXT NOT NULL, home_team TEXT NOT NULL, away_team TEXT NOT NULL,
    home_score NUMERIC, away_score NUMERIC, commence_time TEXT, went_to_ot INTEGER)
"""
# production's odds columns (information_schema, 2026-11-02): created_at is
# TEXT defaulting to now()::text, prices and lines NUMERIC.
ODDS_DDL = """
CREATE TABLE odds (
    odds_id SERIAL PRIMARY KEY, game_id TEXT NOT NULL, sport TEXT NOT NULL,
    market TEXT NOT NULL, bookmaker TEXT NOT NULL, snapshot_type TEXT NOT NULL,
    snapshot_at TEXT NOT NULL, home_price NUMERIC, away_price NUMERIC, draw_price NUMERIC,
    spread_home NUMERIC, total_line NUMERIC, over_price NUMERIC, under_price NUMERIC,
    home_link TEXT, away_link TEXT, draw_link TEXT, over_link TEXT, under_link TEXT,
    home_sid TEXT, away_sid TEXT, draw_sid TEXT, over_sid TEXT, under_sid TEXT,
    source TEXT, created_at TEXT DEFAULT (now())::text)
"""
LATEST_DDL = "CREATE TABLE latest_odds (game_id TEXT, market TEXT, bookmaker TEXT, spread_home NUMERIC)"
QUOTA_DDL = """CREATE TABLE odds_api_quota (quota_date TEXT PRIMARY KEY, requests_used NUMERIC,
               requests_remaining NUMERIC, observed_at TEXT)"""
PICKS_DDL = ("CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, result TEXT, settled_at TEXT, "
             "profit_kelly REAL, condition_status TEXT, " + ", ".join(
                 f"{c} {'REAL' if c in ('model_probability', 'model_probability_cal', 'dk_implied_prob', 'edge', 'dk_odds', 'scored_line', 'kelly_fraction', 'recommended_bet', 'bankroll_at_pick', 'decision_odds', 'decision_implied_prob', 'decision_edge', 'best_odds', 'best_implied_prob', 'best_edge') else 'TEXT'}"
                 for c in card._COLS) + ")")


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-first-half-pg-") as d:
        yield d


def _iso(t: datetime) -> str:
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@pytest.fixture()
def world(dsn, monkeypatch):
    """Today's game tipping 9 minutes from now (so the real NOW() of the fetch
    is its tip-minus-10 time), and yesterday's finished game of both teams with
    its halves and closing lines."""
    now = datetime.now(UTC).replace(microsecond=0)
    tip = now + timedelta(minutes=9, seconds=30)
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
        fg.append((g, "spreads", "draftkings", _iso(t + timedelta(minutes=30)), +20.0, None))
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
    monkeypatch.setattr(win, "get_connection", connect)
    monkeypatch.setattr(data.db, "get_connection", connect)     # the feed's own connection
    monkeypatch.setattr(feed.ncaab_teams, "make_resolver", lambda conn, d, days_back=1, days_fwd=2: (
        lambda h, a, ct: (gid, False) if (h, a) == (FEED_HOME, FEED_AWAY) else None))
    body = {"bookmakers": [
        {"key": "fanduel", "last_update": _iso(now), "markets": [
            {"key": "spreads_h1", "last_update": _iso(now - timedelta(minutes=1)), "outcomes": [
                {"name": FEED_HOME, "price": +100, "point": -1.5, "link": "fd/h"},
                {"name": FEED_AWAY, "price": -125, "point": 1.5, "link": "fd/a"}]}]},
        {"key": "draftkings", "last_update": _iso(now), "markets": [
            {"key": "spreads_h1", "outcomes": [
                {"name": FEED_HOME, "price": -110, "point": -1.5, "link": "dk/h"},
                {"name": FEED_AWAY, "price": -110, "point": 1.5, "link": "dk/a"}]},
            {"key": "totals_h1", "outcomes": [
                {"name": "Over", "price": -110, "point": 66.5}, {"name": "Under", "price": -110, "point": 66.5}]}]},
        {"key": "pinnacle", "last_update": _iso(now), "markets": [
            {"key": "spreads_h1", "outcomes": [
                {"name": FEED_HOME, "price": +200, "point": -1.5},
                {"name": FEED_AWAY, "price": -250, "point": 1.5}]}]}]}
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


def test_the_tip_minus_10_fetch_decides_once_and_writes_the_bet(world):
    gid, raw = world["gid"], world["raw"]
    plan = win.plan_tick()
    assert plan.fetch == [gid] and plan.marks[gid] == "T-10" and plan.card == [gid]

    out = feed.fetch_first_half([gid])
    assert out["fetched"] == [gid] and not out["failed"] and world["calls"] == ["events", "ev1"]
    led = q(raw, "SELECT endpoint, mark, ok, main_rows, markets FROM ncaab_first_half_fetches "
                 "WHERE game_id = %s", (gid,))
    assert led == [("event_odds", "T-10", True, 4, "spreads_h1,totals_h1")]
    # the fetch's rows carry the ledger's instant as created_at
    same = q(raw, "SELECT count(*) FROM odds o JOIN ncaab_first_half_fetches f "
                  "ON f.game_id = o.game_id AND o.created_at::timestamptz = f.fetch_at "
                  "WHERE o.source = %s", (feed.SOURCE,))
    assert same == [(4,)]
    assert not win.plan_tick().fetch               # satisfied until the next fetch time

    res = card.run_card(do_publish=True)
    assert res["published"] == 1 and res["decided"] == 1
    d = q(raw, "SELECT status, book, side, line, price, fg_spread, fg_books, n_home, n_away, "
               "missing_halves, offers FROM ncaab_first_half_spread_decisions WHERE game_id = %s", (gid,))
    status, book, side, line, price, fgs, fgb, nh, na, miss, offers = d[0]
    assert (status, book, side, line, price) == ("bets", "fanduel", "home", -1.5, 100)
    assert (fgs, fgb) == (-8.0, 3)                 # the three bettable books; Pinnacle and the late row out
    assert (nh, na, miss) == (1, 1, 0)             # yesterday's game counts for both
    assert '"pinnacle"' not in offers
    p = q(raw, "SELECT model_id, pick_side, pick_label, scored_line, decision_book, decision_odds, "
               "dk_odds, line_book, best_book, signal_type FROM picks WHERE game_id = %s", (gid,))
    assert p == [(fh.MODEL_ID, "home", "Duke @ Kansas — First Half Kansas -1.5", -1.5, "fanduel",
                  100.0, -110.0, None, "fanduel", "BET")]
    tg = q(raw, "SELECT game_id, h1_home, h1_away, h2_home, h2_away, spread_close, spread_books "
                "FROM ncaab_first_half_team_games")
    assert tg == [(world["pid"], 40.0, 25.0, 30.0, 35.0, -8.0, 3)]

    # decided once: a second run, a moved line or a later tick writes nothing
    again = card.run_card(do_publish=True)
    assert again["published"] == 0 and again["decided"] == 0
    assert q(raw, "SELECT count(*) FROM picks") == [(1,)]
    assert q(raw, "SELECT count(*) FROM ncaab_first_half_spread_decisions") == [(1,)]
    assert not win.plan_tick().card


def test_a_dry_run_writes_nothing(world):
    gid, raw = world["gid"], world["raw"]
    feed.fetch_first_half([gid])
    res = card.run_card(do_publish=False)
    assert res["bets"] == 1 and res["published"] == 0
    assert q(raw, "SELECT count(*) FROM picks") == [(0,)]
    assert q(raw, "SELECT to_regclass('ncaab_first_half_team_games') IS NULL") == [(True,)]


def test_a_game_whose_decision_fetch_never_landed_is_reported_not_decided(world, monkeypatch):
    gid = world["gid"]
    late = world["tip"] - timedelta(minutes=4)
    with pytest.raises(card.CardIncomplete):
        card.run_card(do_publish=True, now=late)
    conn = world["connect"]()
    try:
        assert card.decided_games(conn, [gid]) == set()
        # the alerter names it once it tips
        assert win.undecided_games(conn, world["tip"] + timedelta(minutes=5)) == []   # no ledger yet
    finally:
        conn.close()
