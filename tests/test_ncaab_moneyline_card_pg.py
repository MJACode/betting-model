"""The NCAAB moneyline card end to end against a real Postgres.

WHY A REAL DATABASE. The card's 15:00 UTC reads are SQL on `odds`, whose
snapshot_at and prices are TEXT: the cast, the one-hour bound, the bookmaker
filter (Pinnacle and Bovada read for the moneyline, not for the spread) and the
NULL line of a moneyline are claims about the server, not about Python. So are
the ledger (a decided game writes nothing the second time, because the INSERT
returns no row) and the bet row itself (every column the card writes must
exist and take its value, scored_line NULL). This runs the real run_card() over
a scratch schema: the 15:05 run decides and bets once, a rerun writes nothing,
and the 16:05 run writes a game nobody decided as `missed`, bets nothing, and
fails. Runs against LATEST_LINE_TEST_DSN or a throwaway cluster from
tests/_pg.py, and SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

psycopg2 = pytest.importorskip("psycopg2")

import models.ncaab_moneyline_own_spread as om  # noqa: E402
from data.db import DBConnection  # noqa: E402
from scripts import ncaab_moneyline_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402

UTC = timezone.utc
DAY = "2026-12-05"
DUKE = "NCAAB_2026-12-05_kansas_duke"
ZAGS = "NCAAB_2026-12-05_ucla_gonzaga"
IONA = "NCAAB_2026-12-05_iona_siena"


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-moneyline-card-pg-") as d:
        yield d


@pytest.fixture(scope="module")
def p_home():
    """P(home wins) at a -3.5 spread priced -110/-110, from the live table."""
    import pandas as pd
    art = om.load_artifact()
    t = pd.Timestamp("2026-12-05 15:00", tz="UTC")
    rows = pd.DataFrame([{"game_id": "g", "bookmaker": "draftkings", "ts": t, "line": -3.5,
                          "p1": -110.0, "p2": -110.0, "order": 0, "instant": t,
                          "tip": t + pd.Timedelta(hours=9)}])
    return float(om.spread_quotes(rows, art["table"])["ph_own"].iloc[0])


def _american(p):
    return round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)


def _connect(dsn):
    return DBConnection(psycopg2.connect(dsn), url=dsn)


@pytest.fixture()
def db(dsn, monkeypatch, p_home):
    c = _connect(dsn)
    c.execute("DROP TABLE IF EXISTS ncaab_moneyline_decisions, picks, odds, games")
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
        # the bet: BetRivers' home moneyline is the best edge against its own -3.5
        (DUKE, "Duke", "Kansas", "2026-12-06T00:00:00Z"),
        # DraftKings alone, priced about at its own spread: below the cut
        (ZAGS, "Gonzaga", "UCLA", "2026-12-06T03:00:00Z"),
        # no quote at all
        (IONA, "Siena", "Iona", "2026-12-05T23:00:00Z"),
        # tips at 15:00 UTC: never the card's
        ("NCAAB_2026-12-05_army_navy", "Navy", "Army", "2026-12-05T15:00:00Z"),
    ]
    for gid, home, away, ct in games:
        c.execute("INSERT INTO games VALUES (%s, 'NCAAB', 2027, %s, %s, %s, %s)",
                  (gid, DAY, ct, home, away))

    def odds(gid, book, stamp, p1, p2, line=None, market="h2h", stype="open"):
        c.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
                  "spread_home, home_price, away_price, home_link, away_link) VALUES "
                  "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                  (gid, market, book, stype, stamp, line, p1, p2, f"{book}/{gid}/h", f"{book}/{gid}/a"))

    best = str(_american(p_home - 0.04))           # BetRivers: edge +0.04 on the home side
    dk = str(_american(p_home - 0.02))             # DraftKings: edge +0.02, the reference
    away = str(_american(1 - p_home + 0.06))       # every away side: a negative edge
    for book, home_p in (("draftkings", dk), ("fanduel", dk), ("betmgm", dk), ("betrivers", best)):
        odds(DUKE, book, f"{DAY}T14:18:31Z", "-110", "-110", line="-3.5", market="spreads")
        odds(DUKE, book, f"{DAY}T14:20:00Z", home_p, away)
    odds(DUKE, "pinnacle", f"{DAY}T14:50:00Z", dk, away)                 # reference only
    odds(DUKE, "fanatics", f"{DAY}T13:40:00Z", "+300", "-400")           # 80 minutes old: stale
    odds(DUKE, "fanatics", f"{DAY}T13:40:00Z", "-110", "-110", line="-3.5", market="spreads")
    odds(DUKE, "hardrockbet", f"{DAY}T15:02:00Z", "+300", "-400")        # after 15:00: not yet
    odds(DUKE, "hardrockbet", f"{DAY}T14:30:00Z", "-110", "-110", line="-3.5", market="spreads")
    odds(DUKE, "betparx", f"{DAY}T14:56:00Z", "+300", "-400", stype="in_play")
    odds(DUKE, "betparx", f"{DAY}T14:30:00Z", "-110", "-110", line="-3.5", market="spreads")
    odds(ZAGS, "draftkings", f"{DAY}T14:18:31Z", "-110", "-110", line="-3.5", market="spreads")
    odds(ZAGS, "draftkings", f"{DAY}T14:20:00Z", str(_american(p_home + 0.005)), away)
    c.commit()
    monkeypatch.setattr(card, "get_connection", lambda: _connect(dsn))
    # The ledger's lock-down revokes from Supabase's API roles, which a scratch
    # cluster does not have: the DDL itself is what this test needs.
    monkeypatch.setattr(card, "ensure_decisions_table",
                        lambda conn: (conn.execute(card.DECISIONS_DDL), conn.commit()))
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    c.best_price, c.dk_price = float(best), float(dk)
    yield c
    c.close()


def _ledger(c):
    return {r[0]: r[1:] for r in c.execute(
        "SELECT game_id, status, book, side, price, n_books, n_bets FROM ncaab_moneyline_decisions"
    ).fetchall()}


def test_the_15z_run_bets_once_at_the_bet_books_price_and_a_rerun_writes_nothing(db, p_home):
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert (out["bets"], out["published"], out["decided"]) == (1, 1, 3)
    led = _ledger(db)
    assert set(led) == {DUKE, ZAGS, IONA}                         # Army-Navy tips at 15:00
    assert led[DUKE] == ("bets", "betrivers", "home", db.best_price, 4, 1)
    assert led[ZAGS][0] == "below_cut" and led[ZAGS][-1] == 0
    assert led[IONA][:2] == ("no_quotes", None)
    (pick,) = db.execute(
        "SELECT game_id, model_id, pick_side, pick_label, scored_line, line_book, dk_odds, "
        "dk_implied_prob, edge, decision_book, decision_odds, best_book, best_bet_link, signal_type, "
        "model_probability, decision_edge FROM picks WHERE signal_type = 'BET'").fetchall()
    assert pick[:6] == (DUKE, "ncaab_moneyline_own_spread", "home", "Duke ML", None, None)
    assert pick[6] == str(db.dk_price) and float(pick[8]) > 0.01
    assert pick[9:14] == ("betrivers", str(db.best_price), "betrivers", f"betrivers/{DUKE}/h", "BET")
    assert abs(float(pick[14]) - p_home) < 1e-4
    assert abs(float(pick[15]) - 0.04) < 0.005
    # The game priced below the cut is a NONE row with no stake, for the app's
    # All board, and is not a bet in the ledger; the unpriced one writes no row.
    assert db.execute(
        "SELECT game_id, signal_type, kelly_fraction, recommended_bet FROM picks "
        "WHERE signal_type <> 'BET'").fetchall() == [(ZAGS, "NONE", "0.0", "0.0")]
    # the same hour again, and an hour later with a better price up: nothing
    card._ART.clear()
    again = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 40, tzinfo=UTC))
    assert again["decided"] == 0
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
               "home_price, away_price) VALUES (%s, 'h2h', 'fanduel', 'open', "
               "'2026-12-05T15:30:00Z', '+150', '-180')", (DUKE,))
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
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
               "home_price, away_price) VALUES ('NCAAB_2026-12-05_yale_brown', 'h2h', "
               "'draftkings', 'open', '2026-12-05T16:00:00Z', '+150', '-180')")
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


# ── a best side at a state-limited book (betPARX, mike 2026-11-06) ──────────
# betPARX at BetRivers' home price against the same -3.5 is the same bet, so
# BetRivers takes it. A betPARX price that is strictly best is an ordinary
# no-bet (the 2026-11-07 re-grade, docs/sports/ncaab.md), and the run must not fail.

def _parx(db, home_price, away_price):
    db.execute("INSERT INTO odds (game_id, market, bookmaker, snapshot_type, snapshot_at, "
               "home_price, away_price) VALUES (%s, 'h2h', 'betparx', 'open', %s, %s, %s)",
               (DUKE, f"{DAY}T14:45:00Z", str(home_price), str(away_price)))
    db.commit()


def test_an_exact_tie_at_a_state_limited_book_bets_at_the_book_that_can_be_bet(db, p_home):
    _parx(db, _american(p_home - 0.04), _american(1 - p_home + 0.06))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 1
    assert _ledger(db)[DUKE][:2] == ("bets", "betrivers")


def test_a_best_side_at_a_state_limited_book_is_a_no_bet_and_the_run_does_not_fail(db, p_home):
    _parx(db, _american(p_home - 0.05), _american(1 - p_home + 0.06))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 0
    assert _ledger(db)[DUKE][:2] == ("book_not_bettable", "betparx")
    assert db.execute("SELECT COUNT(*) FROM picks WHERE signal_type = 'BET'").fetchone()[0] == 0


def test_any_other_book_that_cannot_be_bet_still_fails_the_run(db, monkeypatch):
    monkeypatch.setattr(card.config, "BEST_LINE_BOOKMAKERS",
                        [b for b in card.config.BEST_LINE_BOOKMAKERS if b != "betrivers"])
    with pytest.raises(card.CardIncomplete, match="book_not_bettable"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
