"""The game scorer's "unplaceable BET" clean-up must not delete a bet priced at another book.

Measured 2026-10-02. Three nhl_prop_saves picks, each taken at Hard Rock at a
number DraftKings did not hang (so `dk_odds` NULL, `decision_odds` set,
`line_book` = hardrockbet), were inserted at 00:21:06Z, posted to Discord at
00:21:08Z, and deleted at 00:21:18Z by the statement below -- which keyed "no
price at all" on `dk_odds` alone. picks_log holds the three INSERTs and the
three DELETEs. A published pick with no row cannot settle (CLAUDE.md 1c).

This runs the REAL statement, lifted from the source, against a real schema.
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest

from data.db_setup import SCHEMA_SQL

SRC = (Path(__file__).resolve().parents[1] / "models" / "scorer.py").read_text(encoding="utf-8")


def _statement() -> str:
    """The clean-up DELETE as written in run_scorer, parameter marks made sqlite's."""
    m = re.search(r'conn\.execute\("""\s*(DELETE FROM picks\s+WHERE result IS NULL\s+AND signal_type = \'BET\'\s+'
                  r'AND dk_odds IS NULL.*?\))"""', SRC, re.S)
    assert m, "the unplaceable-BET clean-up is no longer where this test reads it"
    return m.group(1).replace("%s", "?")


@pytest.fixture
def db():
    c = sqlite3.connect(":memory:")
    c.executescript(SCHEMA_SQL)
    have = {r[1] for r in c.execute("PRAGMA table_info(picks)")}
    for col in ("decision_odds REAL", "decision_book TEXT", "line_book TEXT"):
        if col.split()[0] not in have:
            c.execute(f"ALTER TABLE picks ADD COLUMN {col}")
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time) "
              "VALUES ('G_LATER', 'NHL', 2027, '2026-10-01', 'VAN', 'EDM', '2026-10-02T02:10:00+00:00')")
    c.execute("INSERT INTO games (game_id, sport, season, game_date, home_team, away_team, commence_time) "
              "VALUES ('G_STARTED', 'NHL', 2027, '2026-10-01', 'CGY', 'SEA', '2026-10-01T23:10:00+00:00')")
    yield c
    c.close()


def _bet(c, label, game="G_LATER", dk_odds=None, decision_odds=None, line_book=None, signal="BET"):
    c.execute("""INSERT INTO picks (game_id, model_id, sport, game_date, pick_side, pick_label, model_probability,
                 dk_implied_prob, edge, dk_odds, kelly_fraction, recommended_bet, bankroll_at_pick, signal_type,
                 decision_odds, decision_book, line_book)
                 VALUES (?, 'nhl_prop_saves', 'NHL', '2026-10-01', 'under', ?, 0.69, 0.0, 0.0, ?, 0.01, 10.0, 1000.0,
                         ?, ?, ?, ?)""", (game, label, dk_odds, signal, decision_odds, line_book, line_book))


def _left(c) -> set[str]:
    return {r[0] for r in c.execute("SELECT pick_label FROM picks")}


def test_a_bet_priced_at_another_books_line_survives_and_a_bet_with_no_price_does_not(db):
    _bet(db, "priced at Hard Rock, DraftKings has no such number", decision_odds=-125.0, line_book="hardrockbet")
    _bet(db, "no price anywhere")
    _bet(db, "priced at DraftKings", dk_odds=-110.0, decision_odds=-110.0)
    _bet(db, "no price, but the game has started", game="G_STARTED")
    _bet(db, "not a bet", signal="NONE")
    db.execute(_statement(), ("2026-10-01", "2026-10-02T00:21:18+00:00"))
    assert _left(db) == {"priced at Hard Rock, DraftKings has no such number", "priced at DraftKings",
                         "no price, but the game has started", "not a bet"}


def test_the_statement_names_both_prices():
    sql = _statement()
    assert "dk_odds IS NULL" in sql and "decision_odds IS NULL" in sql
