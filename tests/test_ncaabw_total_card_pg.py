"""The NCAABW totals ledger and DraftKings' first post against a real Postgres.

A fork of tests/test_ncaab_total_card_pg.py (2026-11-10) on the women's card.

WHY A REAL DATABASE. "Decided once" is a claim about the server: the insert
must return nothing for a game the ledger already holds, because publish()
writes the bet only when a row comes back. The first post is a claim about the
server's ordering and casts: odds stores snapshot_at and created_at as TEXT and
the total as NUMERIC, and the earliest usable row must win, a feed typo must
never be it, and a later or in-play row must never be read as it. And the
short-schedule guard reads the Division I flag off the team registry. Runs
against LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and
SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from scripts import ncaabw_total_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaabw-total-card-pg-") as d:
        yield d


@pytest.fixture()
def conn(dsn):
    c = DBConnection(psycopg2.connect(dsn), url=dsn)
    c.execute("DROP TABLE IF EXISTS ncaabw_total_decisions, picks")
    c.execute(card.DECISIONS_DDL)
    c.execute("CREATE TABLE picks (game_id TEXT, model_id TEXT, signal_type TEXT)")
    c.execute("INSERT INTO ncaabw_total_decisions (game_id, check_hour, n_bets, detail) "
              "VALUES ('priced', 'first', 0, "
              "'below_cut: over 130.5 edge +0.0100 model 131.00 mean 130.60')")
    c.commit()
    yield c
    c.close()


def _decision(gid):
    return {"game_id": gid, "check_hour": "second", "quote_at": "q", "cutoff": "c", "total_line": 157.5,
            "model_total": 139.5, "edge": 0.0631, "side": "under", "n_bets": 1, "detail": "bets: under"}


def test_a_decided_game_stands_and_a_new_one_is_written_once(conn):
    assert card.decided_games(conn, ["priced", "new"]) == {"priced"}
    got = {g: conn.execute(card._INSERT_DECISION, _decision(g)).fetchone() for g in ("priced", "new")}
    conn.commit()
    assert got["new"]
    assert got["priced"] is None          # no row back: publish() writes no bet
    rows = {r[0]: r[1:] for r in conn.execute(
        "SELECT game_id, check_hour, n_bets, side FROM ncaabw_total_decisions").fetchall()}
    assert rows["new"] == ("second", 1, "under")
    assert rows["priced"] == ("first", 0, None)
    assert card.decided_games(conn, ["priced", "new"]) == {"priced", "new"}
    assert conn.execute(card._INSERT_DECISION, _decision("new")).fetchone() is None
    # a BET in picks decides a game the ledger does not hold
    conn.execute("INSERT INTO picks VALUES ('bet_only', %s, 'BET'), ('none_only', %s, 'NONE')",
                 (card.MODEL_ID, card.MODEL_ID))
    assert card.decided_games(conn, ["bet_only", "none_only"]) == {"bet_only"}
    assert card.decided_games(conn, ["bet_only"], bets=False) == set()


# ── DraftKings' first post, end to end through run_card ──────────────────────

GID = "NCAABW_2027-01-11_kansas_duke"
TIP = "2027-01-12T00:00:00Z"


@pytest.fixture()
def board(dsn):
    from scripts.ncaabw_total_card import _COLS
    c = DBConnection(psycopg2.connect(dsn), url=dsn)
    from data.anon_readable import API_ROLES
    for role in API_ROLES:         # the API roles the ledger is locked down from
        c.execute(f"DO $$ BEGIN CREATE ROLE {role} NOLOGIN; "
                  f"EXCEPTION WHEN duplicate_object THEN NULL; END $$;")
    c.execute("DROP TABLE IF EXISTS ncaabw_total_decisions, picks, odds, games, ncaabw_teams")
    c.execute("CREATE TABLE ncaabw_teams (espn_id INTEGER PRIMARY KEY, is_d1 BOOLEAN)")
    c.execute("CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, condition_status TEXT, "
              + ", ".join(f"{col} TEXT" for col in _COLS) + ")")
    c.execute("CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, season INTEGER, "
              "game_date TEXT, commence_time TEXT, home_team TEXT, away_team TEXT)")
    c.execute("CREATE TABLE odds (odds_id SERIAL PRIMARY KEY, game_id TEXT, market TEXT, "
              "bookmaker TEXT, snapshot_type TEXT, snapshot_at TEXT, created_at TEXT, "
              "total_line NUMERIC, over_price NUMERIC, under_price NUMERIC, "
              "over_link TEXT, under_link TEXT)")
    c.execute("INSERT INTO games VALUES (%s, 'NCAABW', 2027, '2027-01-11', %s, 'Duke', 'Kansas')",
              (GID, TIP))
    c.commit()
    yield c
    c.close()


def _odds(c, snap, stored, line, op=-110, up=-110, book="draftkings", kind="open", gid=GID):
    c.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
              "created_at, total_line, over_price, under_price, over_link, under_link) "
              "VALUES (%s, 'totals', %s, %s, %s, %s, %s, %s, %s, 'lo', 'lu')",
              (gid, book, kind, snap, stored, line, op, up))
    c.commit()


def test_the_first_post_is_the_earliest_usable_pregame_draftkings_row(board):
    c = board
    now = datetime(2027, 1, 11, 2, 8, tzinfo=timezone.utc)
    _odds(c, "2027-01-10T23:55:00Z", "2027-01-10 23:56:00+00", 1465.0)       # the feed typo
    _odds(c, "2027-01-11T00:10:00Z", "2027-01-11 00:12:00+00", 146.5, -112, -108)
    _odds(c, "2027-01-11T00:10:00Z", "2027-01-11 00:14:00+00", 146.5, -110, -110)  # same stamp, stored last
    _odds(c, "2027-01-11T00:40:00Z", "2027-01-11 00:41:00+00", 147.5)
    _odds(c, "2027-01-10T20:00:00Z", "2027-01-10 20:01:00+00", 150.5, book="fanduel")
    _odds(c, "2027-01-10T20:00:00Z", "2027-01-10 20:01:00+00", 151.5, kind="in_play")
    _odds(c, "2027-01-10T21:00:00", "2027-01-10 21:01:00+00", 145.5, op=None)  # no over price
    got = card.load_first_posts(c, {GID: {}}, now)
    q = got[GID]
    assert (q.line, q.over_price, q.under_price) == (146.5, -110.0, -110.0)
    assert q.quote_at == datetime(2027, 1, 11, 0, 10, tzinfo=timezone.utc)
    # a row stored after the run's instant is not read
    assert card.load_first_posts(c, {GID: {}}, datetime(2027, 1, 11, 0, 11, tzinfo=timezone.utc)) == {}
    # the standing number moved: the first post no longer stands
    standing = card.load_quotes(c, {GID: {}}, now)[GID]
    assert standing.line == 147.5 and not card.same_quote(q, standing)


def _stub_season(monkeypatch, at, keep_games=None):
    """The synthetic season of tests/test_ncaabw_total_blend.py with its last
    game renamed to GID and tipping at TIP; the artifact and the bankroll
    stubbed. The slate, the ledger, the first post, the standing number, the
    team registry and the writes are the real server's. keep_games keeps only
    that many stored games before GID (a schedule not stored whole).
    -> the season's team ids."""
    from tests import test_ncaabw_total_blend as T
    import models.scorer as scorer
    games, box = T._season()
    sg, _ = T._prepared(games, box)
    t, _ = T._late_target(sg)
    old = t["game_id"].iloc[0]
    games = games.assign(game_id=games["game_id"].replace(old, GID))
    games.loc[games["game_id"] == GID, ["game_date", "commence_time"]] = ["2027-01-11", TIP]
    teams = sorted(set(sg["home_espn_id"]) | set(sg["away_espn_id"]))
    art = T._art(teams)
    if keep_games is not None:
        import pandas as pd
        games = pd.concat([games[games["game_id"] != GID].sort_values("commence_time").tail(keep_games),
                           games[games["game_id"] == GID]])
    monkeypatch.delenv("RUN_NCAABW_TOTAL_CARD", raising=False)
    monkeypatch.setattr(card, "load_season", lambda conn, season: (games, box))
    monkeypatch.setattr(card, "artifact", lambda: art)
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    return [int(t) for t in teams]


def test_run_card_bets_the_standing_first_post_once(board, dsn, monkeypatch):
    c = board
    first = datetime(2027, 1, 11, 0, 10, tzinfo=timezone.utc)
    _odds(c, "2027-01-11T00:10:00Z", "2027-01-11 00:11:00+00", 125.5)
    _stub_season(monkeypatch, first)
    monkeypatch.setattr(card, "get_connection", lambda: DBConnection(psycopg2.connect(dsn), url=dsn))
    out = card.run_card(do_publish=True, now=first + timedelta(minutes=3))
    assert out["bets"] == 1 and out["published"] == 1 and out["decided"] == 1
    ((line, side, quote_at, cutoff),) = c.execute(
        "SELECT total_line, side, quote_at, cutoff FROM ncaabw_total_decisions").fetchall()
    assert float(line) == 125.5 and side == "over"
    assert quote_at.startswith("2027-01-11T00:10:00") and cutoff.startswith("2027-01-11T00:00:00")
    ((label, scored),) = c.execute("SELECT pick_label, scored_line FROM picks").fetchall()
    assert label == "Duke vs Kansas Over 125.5" and float(scored) == 125.5
    # the line moves and the card runs again: nothing new is written
    _odds(c, "2027-01-11T00:20:00Z", "2027-01-11 00:21:00+00", 129.5)
    again = card.run_card(do_publish=True, now=first + timedelta(minutes=13))
    assert again["decided"] == 0 and again["diag"]["already_decided"] == 1
    assert c.execute("SELECT count(*) FROM picks").fetchone()[0] == 1


def test_run_card_never_bets_a_first_post_that_moved(board, dsn, monkeypatch):
    c = board
    first = datetime(2027, 1, 11, 0, 10, tzinfo=timezone.utc)
    _odds(c, "2027-01-11T00:10:00Z", "2027-01-11 00:11:00+00", 125.5)
    _odds(c, "2027-01-11T00:12:00Z", "2027-01-11 00:13:00+00", 126.5)
    _stub_season(monkeypatch, first)
    monkeypatch.setattr(card, "get_connection", lambda: DBConnection(psycopg2.connect(dsn), url=dsn))
    out = card.run_card(do_publish=True, now=first + timedelta(minutes=8))
    assert out["bets"] == 0 and out["decided"] == 1 and out["diag"]["first_post_gone"] == 1
    ((detail, n_bets, line),) = c.execute(
        "SELECT detail, n_bets, total_line FROM ncaabw_total_decisions").fetchall()
    assert detail.startswith("first_post_gone: first post 125.5") and n_bets == 0 and float(line) == 125.5
    assert c.execute("SELECT count(*) FROM picks").fetchone()[0] == 0


def test_run_card_stops_a_division_i_game_on_a_schedule_not_stored_whole(board, dsn, monkeypatch):
    """The registry's Division I flag, read from the real server: a Division I
    team under 10 stored games means the season's schedule was never loaded
    whole (2026-11-10: 1,245 women's games stored to 2026-11-23). The game is
    not decided and nothing is written; once the schedule is whole it bets."""
    c = board
    first = datetime(2027, 1, 11, 0, 10, tzinfo=timezone.utc)
    _odds(c, "2027-01-11T00:10:00Z", "2027-01-11 00:11:00+00", 125.5)
    teams = _stub_season(monkeypatch, first, keep_games=12)
    for t in teams:
        c.execute("INSERT INTO ncaabw_teams VALUES (%s, TRUE)", (t,))
    c.commit()
    assert card.d1_team_ids(c) == set(teams)
    monkeypatch.setattr(card, "get_connection", lambda: DBConnection(psycopg2.connect(dsn), url=dsn))
    with pytest.raises(card.CardIncomplete, match="schedule_short"):
        card.run_card(do_publish=True, now=first + timedelta(minutes=3))
    assert c.execute("SELECT count(*) FROM picks").fetchone()[0] == 0
    assert c.execute("SELECT to_regclass('ncaabw_total_decisions')").fetchone()[0] is None or \
        c.execute("SELECT count(*) FROM ncaabw_total_decisions").fetchone()[0] == 0
    # the schedule loaded whole: the same first post, still standing, is bet
    _stub_season(monkeypatch, first)
    out = card.run_card(do_publish=True, now=first + timedelta(minutes=8))
    assert out["bets"] == 1 and out["published"] == 1
