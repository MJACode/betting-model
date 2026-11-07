"""The NCAAB first-post moneyline card end to end against a real Postgres.

WHY A REAL DATABASE. What makes a post NEW is a claim about the server: the
AFTER INSERT trigger that keeps latest_odds current
(data/migrations/latest_line_state_tables.sql, installed here as production
has it), the keyed read of each book's FIRST complete moneyline row, the
in-play exclusion, the standing quotes read with no freshness window, the
ledger whose INSERT returns no row the second time, and the bet row itself.
So is one bet a game across the two moneyline models: both cards' locks and
reads of each other's BETs, and the 15:00 UTC card writing `other_model_bet`.
And the fill check the capture writes on its next poll. This runs the real
run_card() of both cards over a scratch schema. Runs against
LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py, and SKIPS only
where neither exists (the worker).
"""
from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import models.ncaab_moneyline_first_post as fp  # noqa: E402
import models.ncaab_moneyline_own_spread as om  # noqa: E402
from data.db import DBConnection  # noqa: E402
from scripts import ncaab_first_post_fill as fill  # noqa: E402
from scripts import ncaab_moneyline_card as card15  # noqa: E402
from scripts import ncaab_moneyline_first_post_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "data" / "migrations" / "latest_line_state_tables.sql"
DAY = "2026-12-05"
DUKE = "NCAAB_2026-12-05_kansas_duke"
ZAGS = "NCAAB_2026-12-05_ucla_gonzaga"
IONA = "NCAAB_2026-12-05_iona_siena"
T0 = datetime(2026, 12, 4, 20, 0, tzinfo=UTC)          # the board the evening before

SCHEMA = """
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated NOLOGIN; END IF;
END $$;
DROP SCHEMA public CASCADE; CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO anon, authenticated;
CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, season INTEGER, game_date TEXT,
    home_team TEXT, away_team TEXT, commence_time TEXT);
CREATE TABLE odds (
    odds_id BIGSERIAL PRIMARY KEY, game_id TEXT, sport TEXT, market TEXT, bookmaker TEXT,
    snapshot_type TEXT, snapshot_at TEXT,
    home_price NUMERIC, away_price NUMERIC, draw_price NUMERIC, spread_home NUMERIC, total_line NUMERIC,
    over_price NUMERIC, under_price NUMERIC, created_at TEXT DEFAULT now()::text,
    home_link TEXT, away_link TEXT, draw_link TEXT, over_link TEXT, under_link TEXT,
    home_sid TEXT, away_sid TEXT, draw_sid TEXT, over_sid TEXT, under_sid TEXT, source TEXT);
CREATE TABLE player_prop_odds (
    prop_id BIGSERIAL PRIMARY KEY, game_id TEXT, game_date TEXT, player_name TEXT, team TEXT, market TEXT,
    bookmaker TEXT DEFAULT 'draftkings', snapshot_type TEXT, snapshot_at TEXT,
    line NUMERIC, over_price NUMERIC, under_price NUMERIC, created_at TEXT DEFAULT now()::text,
    over_link TEXT, under_link TEXT, over_sid TEXT, under_sid TEXT);
CREATE TABLE live_game_state (
    state_id BIGSERIAL PRIMARY KEY, game_id TEXT, snapshot_at TEXT, inning SMALLINT, inning_half TEXT,
    outs SMALLINT, bases_state TEXT, home_score SMALLINT, away_score SMALLINT,
    current_pitcher_id TEXT, current_batter_id TEXT, on_deck_batter_id TEXT,
    abstract_game_state TEXT, raw_state JSONB, created_at TEXT DEFAULT now()::text);
"""


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-ml-first-post-pg-") as d:
        yield d


@pytest.fixture(scope="module")
def p_home():
    """P(home wins) at a -3.5 spread priced -110/-110, from the live table."""
    import pandas as pd
    t = pd.Timestamp(T0)
    rows = pd.DataFrame([{"game_id": "g", "bookmaker": "draftkings", "ts": t, "line": -3.5,
                          "p1": -110.0, "p2": -110.0, "order": 0, "instant": t,
                          "tip": t + pd.Timedelta(hours=9)}])
    return float(om.spread_quotes(rows, fp.load_artifact()["table"])["ph_own"].iloc[0])


def _american(p):
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def _connect(dsn):
    return DBConnection(psycopg2.connect(dsn), url=dsn)


def _iso(t: datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


class Board:
    """Writes odds rows the way the capture does: snapshot_at the feed's
    stamp, created_at when stored."""

    def __init__(self, c):
        self.c = c

    def put(self, gid, book, at: datetime, p1, p2, line=None, market="h2h", stype="open",
            stored: datetime | None = None):
        self.c.execute(
            "INSERT INTO odds (game_id, sport, market, bookmaker, snapshot_type, snapshot_at, "
            "spread_home, home_price, away_price, home_link, away_link, created_at) VALUES "
            "(%s, 'NCAAB', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (gid, market, book, stype, _iso(at), line, p1, p2, f"{book}/{gid}/h", f"{book}/{gid}/a",
             (stored or at + timedelta(seconds=20)).isoformat()))
        self.c.commit()


@pytest.fixture()
def db(dsn, monkeypatch, p_home):
    raw = psycopg2.connect(dsn)
    raw.set_client_encoding("UTF8")
    raw.autocommit = True
    cur = raw.cursor()
    cur.execute(SCHEMA)
    cur.execute(io.open(MIGRATION, encoding="utf-8").read())
    raw.close()
    c = _connect(dsn)
    cols = ", ".join(f"{col} TEXT" for col in card15._COLS
                     if col not in ("model_probability", "dk_implied_prob", "edge", "scored_line"))
    c.execute(f"""CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, {cols}, condition_status TEXT,
                  model_probability NUMERIC NOT NULL, dk_implied_prob NUMERIC NOT NULL,
                  edge NUMERIC NOT NULL, scored_line NUMERIC,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    for gid, home, away, ct in ((DUKE, "Duke", "Kansas", "2026-12-06T00:00:00Z"),
                                (ZAGS, "Gonzaga", "UCLA", "2026-12-06T03:00:00Z"),
                                (IONA, "Siena", "Iona", "2026-12-05T23:00:00Z")):
        c.execute("INSERT INTO games VALUES (%s, 'NCAAB', 2027, %s, %s, %s, %s)", (gid, DAY, home, away, ct))
    c.commit()
    b = Board(c)
    # Every bettable book hangs Duke -3.5 at -110/-110 from 20:00Z; three books
    # post a fair moneyline (with vig) at 20:30Z, hours before anything below.
    fair_h, fair_a = str(_american(p_home + 0.02)), str(_american(1 - p_home + 0.02))
    for gid in (DUKE, ZAGS, IONA):
        for book in ("draftkings", "fanduel", "betmgm", "williamhill_us", "fanatics", "betrivers",
                     "hardrockbet", "betparx"):
            b.put(gid, book, T0, "-110", "-110", line="-3.5", market="spreads")
        for book in ("draftkings", "fanduel", "betmgm"):
            b.put(gid, book, T0 + timedelta(minutes=30), fair_h, fair_a)
    monkeypatch.setattr(card, "get_connection", lambda: _connect(dsn))
    monkeypatch.setattr(card15, "get_connection", lambda: _connect(dsn))
    # The ledgers' lock-down revokes from Supabase's API roles; the DDL itself
    # is what this test needs.
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (conn.execute(card.DECISIONS_DDL), conn.commit()))
    monkeypatch.setattr(card15, "ensure_decisions_table",
                        lambda conn: (conn.execute(card15.DECISIONS_DDL), conn.commit()))
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    card._ART.clear()
    card15._ART.clear()
    c.board = b
    c.cheap = (str(_american(p_home - 0.04)), str(_american(1 - p_home + 0.07)))   # edge +0.04 home
    c.fair = (fair_h, fair_a)
    yield c
    c.close()


def _ledger(c):
    return {(r[0], r[1]): r[2:] for r in c.execute(
        "SELECT game_id, bookmaker, status, side, price, n_books, n_bets, fill_status "
        "FROM ncaab_moneyline_first_post_decisions").fetchall()}


def _picks(c, model=fp.MODEL_ID):
    return c.execute("SELECT game_id, model_id, pick_side, pick_label, scored_line, line_book, "
                     "decision_book, decision_odds, best_book, signal_type FROM picks "
                     "WHERE model_id = %s ORDER BY game_id", (model,)).fetchall()


def _seed(c):
    """The card's first run: every post already up is before the model."""
    out = card.run_card(do_publish=True, now=T0 + timedelta(hours=1))
    assert out["bets"] == 0 and out["decided"] == 9
    assert {v[0] for v in _ledger(c).values()} == {"pre_model"}


def test_a_new_first_post_bets_once_at_the_posting_books_price(db):
    _seed(db)
    t = datetime(2026, 12, 4, 23, 40, 30, tzinfo=UTC)
    db.board.put(DUKE, "betrivers", t, *db.cheap)
    assert card.plan(t + timedelta(seconds=30)) == [(DUKE, "betrivers")]
    out = card.run_card(do_publish=True, now=t + timedelta(seconds=40))
    assert (out["bets"], out["published"], out["decided"]) == (1, 1, 1)
    led = _ledger(db)
    assert led[(DUKE, "betrivers")][:5] == ("bets", "home", float(db.cheap[0]), 4, 1)
    (pick,) = _picks(db)
    assert pick[:7] == (DUKE, fp.MODEL_ID, "home", "Duke ML", None, None, "betrivers")
    assert float(pick[7]) == float(db.cheap[0]) and pick[8:] == ("betrivers", "BET")
    # the same minute again, and a later post at another book: no second bet
    assert card.plan(t + timedelta(minutes=1)) == []
    db.board.put(DUKE, "fanatics", t + timedelta(minutes=9), *db.cheap)
    card.run_card(do_publish=True, now=t + timedelta(minutes=10))
    assert _ledger(db)[(DUKE, "fanatics")][0] == "game_already_bet"
    assert len(_picks(db)) == 1


def test_a_post_below_the_cut_leaves_the_game_open_and_a_later_post_bets(db):
    _seed(db)
    t = datetime(2026, 12, 4, 23, 0, tzinfo=UTC)
    db.board.put(ZAGS, "williamhill_us", t, *db.fair)
    card.run_card(do_publish=True, now=t + timedelta(minutes=1))
    assert _ledger(db)[(ZAGS, "williamhill_us")][0] == "below_cut"
    later = t + timedelta(hours=10)
    db.board.put(ZAGS, "fanatics", later, *db.cheap)
    out = card.run_card(do_publish=True, now=later + timedelta(minutes=1))
    assert out["bets"] == 1 and _ledger(db)[(ZAGS, "fanatics")][0] == "bets"
    assert [p[6] for p in _picks(db)] == ["fanatics"]


def test_an_in_play_row_and_a_moved_post_are_not_first_posts(db):
    _seed(db)
    t = datetime(2026, 12, 4, 23, 10, tzinfo=UTC)
    db.board.put(DUKE, "hardrockbet", t, *db.cheap, stype="in_play")      # never a pre-game quote
    db.board.put(DUKE, "betparx", t, *db.cheap)                           # posted ...
    db.board.put(DUKE, "betparx", t + timedelta(minutes=3), db.fair[0], db.fair[1])   # ... and moved
    out = card.run_card(do_publish=True, now=t + timedelta(minutes=4))
    led = _ledger(db)
    assert (DUKE, "hardrockbet") not in led
    assert led[(DUKE, "betparx")][0] == "moved_before_seen" and out["bets"] == 0


def test_a_post_the_card_saw_late_is_missed_and_the_run_fails_once(db):
    _seed(db)
    t = datetime(2026, 12, 4, 23, 0, tzinfo=UTC)
    db.board.put(IONA, "betrivers", t, *db.cheap)
    with pytest.raises(card.CardIncomplete, match="missed"):
        card.run_card(do_publish=True, now=t + timedelta(minutes=20))
    assert _ledger(db)[(IONA, "betrivers")][0] == "missed" and _picks(db) == []
    card.run_card(do_publish=True, now=t + timedelta(minutes=21))          # reported once


def test_a_game_the_15z_model_bet_is_closed_to_this_one(db):
    _seed(db)
    db.execute("INSERT INTO picks (game_id, model_id, sport, pick_side, signal_type, "
               "model_probability, dk_implied_prob, edge) VALUES (%s, %s, 'NCAAB', 'away', 'BET', "
               "0.5, 0.5, 0.02)", (ZAGS, om.MODEL_ID))
    db.commit()
    t = datetime(2026, 12, 5, 16, 0, tzinfo=UTC)
    db.board.put(ZAGS, "betrivers", t, *db.cheap)
    out = card.run_card(do_publish=True, now=t + timedelta(minutes=1))
    assert out["bets"] == 0 and _ledger(db)[(ZAGS, "betrivers")][0] == "other_model_bet"
    assert _picks(db) == []


def test_the_15z_card_records_a_game_this_model_bet_and_writes_no_second_bet(db):
    _seed(db)
    t = datetime(2026, 12, 5, 13, 0, tzinfo=UTC)
    db.board.put(DUKE, "betrivers", t, *db.cheap)
    assert card.run_card(do_publish=True, now=t + timedelta(minutes=1))["bets"] == 1
    # 15:00 UTC. The other two games have no quote stamped 14:00-15:00 UTC on
    # this board, so the card fails after its writes, as it should.
    with pytest.raises(card15.CardIncomplete, match="may have stopped"):
        card15.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    led = {r[0]: r[1] for r in db.execute(
        "SELECT game_id, status FROM ncaab_moneyline_decisions").fetchall()}
    assert led == {DUKE: "other_model_bet", ZAGS: "no_quotes", IONA: "no_quotes"}
    assert _picks(db, om.MODEL_ID) == []
    assert db.execute("SELECT COUNT(*) FROM picks WHERE game_id = %s AND signal_type = 'BET'",
                      (DUKE,)).fetchone()[0] == 1


def test_the_capture_writes_the_fill_check_on_its_next_poll(db):
    _seed(db)
    t = datetime(2026, 12, 4, 23, 40, tzinfo=UTC)
    db.board.put(DUKE, "betrivers", t, *db.cheap)
    db.board.put(ZAGS, "betrivers", t, *db.cheap)
    db.board.put(IONA, "betrivers", t, *db.cheap)
    assert card.run_card(do_publish=True, now=t + timedelta(minutes=1))["bets"] == 3
    # A poll that started before the bets were decided (decided_at is the
    # server's clock) checks nothing.
    assert fill.record_fill(db, [], datetime.now(UTC) - timedelta(hours=1)) == 0
    poll = [
        {"game_id": DUKE, "market": "h2h", "bookmaker": "betrivers",
         "home_price": float(db.cheap[0]), "away_price": float(db.cheap[1])},
        {"game_id": ZAGS, "market": "h2h", "bookmaker": "betrivers",
         "home_price": float(db.cheap[0]) + 15, "away_price": float(db.cheap[1]) - 15},
        {"game_id": IONA, "market": "spreads", "bookmaker": "betrivers", "home_price": -110,
         "away_price": -110},
    ]
    later = datetime.now(UTC) + timedelta(minutes=5)       # decided_at is the server's NOW()
    assert fill.record_fill(db, poll, later) == 3
    led = _ledger(db)
    assert led[(DUKE, "betrivers")][-1] == "unchanged"
    assert led[(ZAGS, "betrivers")][-1] == "changed"
    assert led[(IONA, "betrivers")][-1] == "book_not_listed"
    assert fill.record_fill(db, poll, later + timedelta(minutes=5)) == 0      # once per bet
    (p1, p2) = db.execute("SELECT fill_p1, fill_p2 FROM ncaab_moneyline_first_post_decisions "
                          "WHERE game_id = %s AND bookmaker = 'betrivers'", (ZAGS,)).fetchone()
    assert (p1, p2) == (float(db.cheap[0]) + 15, float(db.cheap[1]) - 15)
