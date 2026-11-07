"""The NCAAB spread card end to end against a real Postgres.

WHY A REAL DATABASE. The card's 15:00 UTC read is SQL on `odds`, whose
snapshot_at and prices are TEXT: the cast, the one-hour bound and the
bookmaker filter are claims about the server, not about Python. So are the
ledger (a decided game writes nothing the second time, because the INSERT
returns no row) and the bet row itself (every column the card writes must
exist and take its value). This runs the real run_card() over a scratch
schema: the 15:05 run decides and bets once, a rerun writes nothing, and the
16:05 run writes a game nobody decided as `missed`, bets nothing, and fails.
Runs against LATEST_LINE_TEST_DSN or a throwaway cluster from tests/_pg.py,
and SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from scripts import ncaab_spread_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
DAY = "2026-12-05"


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-spread-card-pg-") as d:
        yield d


def _connect(dsn):
    return DBConnection(psycopg2.connect(dsn), url=dsn)


@pytest.fixture()
def db(dsn, monkeypatch):
    c = _connect(dsn)
    c.execute("DROP TABLE IF EXISTS ncaab_spread_decisions, picks, odds, games")
    c.execute("""CREATE TABLE games (game_id TEXT PRIMARY KEY, sport TEXT, season INTEGER,
                 game_date TEXT, commence_time TEXT, home_team TEXT, away_team TEXT)""")
    c.execute("""CREATE TABLE odds (odds_id SERIAL PRIMARY KEY, game_id TEXT, market TEXT,
                 bookmaker TEXT, snapshot_type TEXT, snapshot_at TEXT,
                 created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), spread_home TEXT,
                 home_price TEXT, away_price TEXT, home_link TEXT, away_link TEXT)""")
    cols = ", ".join(f"{col} TEXT" for col in card._COLS
                     if col not in ("model_probability", "dk_implied_prob", "edge", "scored_line"))
    c.execute(f"""CREATE TABLE picks (pick_id SERIAL PRIMARY KEY, {cols}, condition_status TEXT,
                  model_probability NUMERIC NOT NULL, dk_implied_prob NUMERIC NOT NULL,
                  edge NUMERIC NOT NULL, scored_line NUMERIC,
                  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    games = [
        # the bet: four books at -10, BetRivers at -8 (and one stale, one late, one
        # sign-crossed and one non-bettable quote that must all be ignored)
        ("NCAAB_2026-12-05_kansas_duke", "Duke", "Kansas", "2026-12-06T00:00:00Z"),
        # BetRivers' -8 again, but only two other books: not a bet
        ("NCAAB_2026-12-05_ucla_gonzaga", "Gonzaga", "UCLA", "2026-12-06T03:00:00Z"),
        # no quote at all
        ("NCAAB_2026-12-05_iona_siena", "Siena", "Iona", "2026-12-05T23:00:00Z"),
        # tips at 15:00 UTC: never the card's
        ("NCAAB_2026-12-05_army_navy", "Navy", "Army", "2026-12-05T15:00:00Z"),
    ]
    for gid, home, away, ct in games:
        c.execute("INSERT INTO games VALUES (%s, 'NCAAB', 2027, %s, %s, %s, %s)",
                  (gid, DAY, ct, home, away))
    duke, ucla = games[0][0], games[1][0]

    def odds(gid, book, stamp, line, p1="-110", p2="-110", market="spreads", stype="open"):
        c.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
                  "spread_home, home_price, away_price, home_link, away_link) VALUES "
                  "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (gid, market, book, stype, stamp, line, p1, p2, f"{book}/{gid}/h", f"{book}/{gid}/a"))
    for book in ("draftkings", "fanduel", "betmgm", "williamhill_us"):
        odds(duke, book, f"{DAY}T14:18:31Z", "-10.0")
    odds(duke, "betrivers", f"{DAY}T14:42:00Z", "-8.0")
    odds(duke, "fanatics", f"{DAY}T13:40:00Z", "-6.5")          # 80 minutes old: stale
    odds(duke, "hardrockbet", f"{DAY}T15:02:00Z", "-6.0")       # after 15:00: not yet
    odds(duke, "betparx", f"{DAY}T14:30:00Z", "10.0")           # sign-crossed: artefact
    odds(duke, "pinnacle", f"{DAY}T14:50:00Z", "-5.0")          # reference book, not read
    odds(duke, "fanduel", f"{DAY}T14:55:00Z", "-5.0", market="h2h")
    odds(duke, "betmgm", f"{DAY}T14:56:00Z", "-5.0", stype="in_play")
    for book in ("draftkings", "fanduel"):
        odds(ucla, book, f"{DAY}T14:18:31Z", "-10.0")
    odds(ucla, "betrivers", f"{DAY}T14:42:00Z", "-8.0")
    c.commit()
    monkeypatch.setattr(card, "get_connection", lambda: _connect(dsn))
    # The ledger's lock-down revokes from Supabase's API roles, which a scratch
    # cluster does not have: the DDL itself is what this test needs.
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (conn.execute(card.DECISIONS_DDL), conn.commit()))
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    yield c
    c.close()


def _ledger(c):
    return {r[0]: r[1:] for r in c.execute(
        "SELECT game_id, status, book, side, line, price, consensus, n_books, n_bets "
        "FROM ncaab_spread_decisions").fetchall()}


def test_the_15z_run_bets_once_at_the_bet_books_number_and_a_rerun_writes_nothing(db):
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert (out["bets"], out["published"], out["decided"]) == (1, 1, 3)
    led = _ledger(db)
    assert set(led) == {"NCAAB_2026-12-05_kansas_duke", "NCAAB_2026-12-05_ucla_gonzaga",
                        "NCAAB_2026-12-05_iona_siena"}            # Army-Navy tips at 15:00
    assert led["NCAAB_2026-12-05_kansas_duke"] == ("bets", "betrivers", "home", -8.0, -110.0,
                                                   -10.0, 5, 1)
    assert led["NCAAB_2026-12-05_ucla_gonzaga"][0] == "too_few_books"
    assert led["NCAAB_2026-12-05_iona_siena"][:2] == ("no_quotes", None)
    (pick,) = db.execute(
        "SELECT game_id, model_id, pick_side, pick_label, scored_line, line_book, dk_odds, "
        "dk_implied_prob, edge, decision_book, decision_odds, best_book, best_bet_link, signal_type, "
        "model_probability FROM picks WHERE signal_type = 'BET'").fetchall()
    assert pick[:6] == ("NCAAB_2026-12-05_kansas_duke", "ncaab_spread_market", "home",
                        "Duke -8.0", -8.0, "betrivers")
    assert pick[6] is None and float(pick[7]) == 0.0 and float(pick[8]) == 0.0
    assert pick[9:14] == ("betrivers", "-110.0", "betrivers",
                          "betrivers/NCAAB_2026-12-05_kansas_duke/h", "BET")
    assert 0.55 < float(pick[14]) < 0.6
    # The game priced and not bet (too few books) is a NONE row with no stake,
    # for the app's All board; the unpriced one (no quotes) writes no row.
    assert db.execute(
        "SELECT game_id, signal_type, kelly_fraction, recommended_bet FROM picks "
        "WHERE signal_type <> 'BET'").fetchall() == [
        ("NCAAB_2026-12-05_ucla_gonzaga", "NONE", "0.0", "0.0")]
    # the same hour again, and an hour later with a better number up: nothing
    card._ART.clear()
    again = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 40, tzinfo=UTC))
    assert again["decided"] == 0
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, spread_home, "
               "home_price, away_price) VALUES ('NCAAB_2026-12-05_kansas_duke', 'spreads', 'fanduel', "
               "'open', '2026-12-05T15:30:00Z', '-4.0', '-110', '-110')")
    db.commit()
    later = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 16, 5, tzinfo=UTC))
    assert later["decided"] == 0
    assert db.execute("SELECT signal_type, COUNT(*) FROM picks GROUP BY 1 ORDER BY 1"
                      ).fetchall() == [("BET", 1), ("NONE", 1)]


def test_a_game_nobody_decided_at_15z_is_written_missed_and_the_run_fails(db):
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    # a game the schedule added after the 15:05 run, still to tip
    db.execute("INSERT INTO games VALUES ('NCAAB_2026-12-05_yale_brown', 'NCAAB', 2027, %s, "
               "'2026-12-06T01:00:00Z', 'Brown', 'Yale')", (DAY,))
    for book in ("draftkings", "fanduel", "betmgm", "williamhill_us"):
        db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
                   "spread_home, home_price, away_price) VALUES ('NCAAB_2026-12-05_yale_brown', "
                   "'spreads', %s, 'open', '2026-12-05T16:00:00Z', '-3.0', '+150', '-110')", (book,))
    db.commit()
    with pytest.raises(card.CardIncomplete, match="missed"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 16, 5, tzinfo=UTC))
    led = _ledger(db)
    assert led["NCAAB_2026-12-05_yale_brown"][0] == "missed"
    assert led["NCAAB_2026-12-05_yale_brown"][-1] == 0
    assert db.execute("SELECT COUNT(*) FROM picks WHERE game_id = 'NCAAB_2026-12-05_yale_brown'"
                      ).fetchone()[0] == 0
    # reported once: the next run is clean
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 17, 5, tzinfo=UTC))


def test_the_first_run_ever_after_15z_records_the_days_games_without_failing(db):
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 18, 5, tzinfo=UTC))
    assert out["bets"] == 0 and out["decided"] == 3
    assert {v[0] for v in _ledger(db).values()} == {"missed"}
    assert db.execute("SELECT COUNT(*) FROM picks").fetchone()[0] == 0


# ── a best quote at a state-limited book (betPARX, mike 2026-11-06) ──────────
# The consensus still reads betPARX and a pick may never name it. An exact tie
# with BetRivers' -8 is the same bet, so BetRivers takes it. A betPARX number
# that is strictly best is an ordinary no-bet: the next-best quote is not the
# one the research chose, and the run must not fail and alert every day it
# happens (docs/sports/ncaab.md, the 2026-11-07 re-grade).

def _parx(db, line):
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, spread_home, "
               "home_price, away_price) VALUES ('NCAAB_2026-12-05_kansas_duke', 'spreads', 'betparx', "
               "'open', '2026-12-05T14:45:00Z', %s, '-110', '-110')", (line,))
    db.commit()


def test_an_exact_tie_at_a_state_limited_book_bets_at_the_book_that_can_be_bet(db):
    _parx(db, "-8.0")
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 1
    assert _ledger(db)["NCAAB_2026-12-05_kansas_duke"][:2] == ("bets", "betrivers")


def test_a_best_quote_at_a_state_limited_book_is_a_no_bet_and_the_run_does_not_fail(db):
    _parx(db, "-7.5")
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 0
    assert _ledger(db)["NCAAB_2026-12-05_kansas_duke"][:2] == ("book_not_bettable", "betparx")
    assert db.execute("SELECT COUNT(*) FROM picks WHERE signal_type = 'BET'").fetchone()[0] == 0


def test_any_other_book_that_cannot_be_bet_still_fails_the_run(db, monkeypatch):
    """Only the state-limited books are expected. A book that left the deciding
    list some other way is still a broken run the alerter must report."""
    monkeypatch.setattr(card.config, "BEST_LINE_BOOKMAKERS",
                        [b for b in card.config.BEST_LINE_BOOKMAKERS if b != "betrivers"])
    with pytest.raises(card.CardIncomplete, match="book_not_bettable"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
