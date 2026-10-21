"""NFL prop odds loads stay one (game, market) statement.

2026-10-03 15:56:56Z, pipeline_log 119483, dispatch:nfl-prop-scoring for
2026-10-04:

    SELECT ... FROM player_prop_odds
    WHERE game_id = ANY(<fourteen NFL_2026_04_* games>)
      AND bookmaker = 'draftkings'
      AND snapshot_type = ANY(ARRAY['open'])
      AND market = ANY(<PROP_MARKETS_NFL>)
    ORDER BY snapshot_at ASC

Cancelled at statement_timeout. One of those games is 4,100 open DraftKings
rows across the twelve markets. The card's statement at 15:52:53Z was the
same table for one game, eight markets, and no bookmaker predicate.

A cancel aborts the transaction. The next slice has to roll back first or
it dies as "current transaction is aborted" and the rest of the slate is
the cascade, not the scan.
"""
from __future__ import annotations

import psycopg2

from pathlib import Path

from data.ingestors.nfl_prop_odds_ingestor import (
    load_nfl_prop_odds, load_nfl_prop_quotes, statement_timeout_error,
)


class _Cur:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows=(), fail_first=0, fail_with=None):
        self.rows = list(rows)
        self.fail_first = fail_first
        self.fail_with = fail_with or psycopg2.errors.QueryCanceled(
            "canceling statement due to statement timeout")
        self.calls: list[tuple[str, object]] = []
        self.events: list[tuple] = []

    def execute(self, sql, params=None):
        self.events.append(("exec", None if not params else params[0]))
        self.calls.append((sql, params))
        if self.fail_first:
            self.fail_first -= 1
            raise self.fail_with
        return _Cur(self.rows)

    def rollback(self):
        self.events.append(("rollback",))


_ROW_OLD = ("G1", "Marvin Harrison Jr.", "player_receptions",
            4.5, -120, -100, None, None, "2026-10-03T12:00:00Z", "draftkings")
_ROW_NEW = ("G1", "Marvin Harrison Jr.", "player_receptions",
            4.5, -110, -110, None, None, "2026-10-04T12:00:00Z", "draftkings")


def test_a_slate_is_one_statement_per_game_and_market():
    conn = _Conn()
    load_nfl_prop_odds(conn, ["G1", "G2"], ["player_receptions", "player_rush_yds"])
    assert len(conn.calls) == 4
    for sql, params in conn.calls:
        assert "game_id = %s" in sql
        assert "game_id = ANY" not in sql
        assert "market = %s" in sql
        assert "market = ANY" not in sql
        assert "bookmaker = %s" in sql
        assert "ORDER BY snapshot_at ASC" in sql
    assert [p[0] for _, p in conn.calls] == ["G1", "G1", "G2", "G2"]
    assert [next(x for x in p if x in ("player_receptions", "player_rush_yds"))
            for _, p in conn.calls] == [
        "player_receptions", "player_rush_yds",
        "player_receptions", "player_rush_yds"]


def test_latest_snapshot_in_a_slice_still_wins():
    conn = _Conn([_ROW_OLD, _ROW_NEW])
    got = load_nfl_prop_odds(conn, ["G1"], ["player_receptions"])
    row = got[("G1", "marvinharrison", "player_receptions")]
    assert row["over_price"] == -110
    assert row["snapshot_at"] == "2026-10-04T12:00:00Z"


def test_a_cancelled_slice_is_rolled_back_and_the_next_game_still_loads():
    conn = _Conn([
        ("G2", "A", "player_receptions", 3.5, -105, -115, None, None,
         "2026-10-04T15:00:00Z", "draftkings"),
    ], fail_first=2)
    got = load_nfl_prop_odds(conn, ["G1", "G2"], ["player_receptions"])
    assert ("G2", "a", "player_receptions") in got
    assert ("G1", "a", "player_receptions") not in got
    # two cancels on G1 (the try and the retry), then G2.
    assert conn.events == [
        ("exec", "G1"), ("rollback",),
        ("exec", "G1"), ("rollback",),
        ("exec", "G2"),
    ]


def test_every_slice_cancelled_is_still_a_failed_load():
    conn = _Conn(fail_first=2)
    try:
        load_nfl_prop_odds(conn, ["G1"], ["player_receptions"])
    except RuntimeError as exc:
        assert "statement timeout" in str(exc)
    else:
        raise AssertionError("a fully cancelled load must fail the date")
    assert conn.events[-1] == ("rollback",)


def test_a_non_timeout_error_is_not_swallowed():
    conn = _Conn(fail_first=1, fail_with=RuntimeError("disk full"))
    try:
        load_nfl_prop_odds(conn, ["G1"], ["player_receptions"])
    except RuntimeError as exc:
        assert "disk full" in str(exc)
    else:
        raise AssertionError("non-timeout errors must propagate")
    assert conn.events == [("exec", "G1")]


def test_an_empty_slate_does_not_touch_the_table():
    conn = _Conn()
    assert load_nfl_prop_odds(conn, []) == {}
    assert load_nfl_prop_quotes(conn, []) == {}
    assert conn.calls == []


def test_quotes_are_one_market_and_only_the_books_asked_for():
    conn = _Conn()
    load_nfl_prop_quotes(
        conn, ["G1"], ["player_pass_yds", "player_rush_yds"],
        books=("pinnacle", "draftkings"))
    assert len(conn.calls) == 2
    for sql, params in conn.calls:
        assert "game_id = %s" in sql
        assert "game_id = ANY" not in sql
        assert "market = %s" in sql
        assert "bookmaker = ANY(%s)" in sql
        assert "bookmaker = %s" not in sql.replace("bookmaker = ANY(%s)", "")
    assert conn.calls[0][1][1] == ["pinnacle", "draftkings"]


def test_the_card_asks_only_for_the_books_it_can_bet_or_read():
    src = Path("scripts/nfl_prop_market_card.py").read_text(encoding="utf-8")
    assert "books=tuple(mk.SHARP_BOOKS) + tuple(SOFT_BOOKS)" in src


def test_statement_timeout_includes_the_aborted_transaction_that_follows():
    assert statement_timeout_error(psycopg2.errors.QueryCanceled(
        "canceling statement due to statement timeout"))
    assert statement_timeout_error(psycopg2.errors.InFailedSqlTransaction(
        "current transaction is aborted, commands ignored until end of transaction block"))
    assert not statement_timeout_error(RuntimeError("disk full"))


def test_scorer_resets_the_connection_after_a_model_timeout():
    src = Path("models/scorer.py").read_text(encoding="utf-8")
    body = src.split("def run_nfl_prop_scorer(", 1)[1].split("\ndef ", 1)[0]
    assert "statement_timeout_error(exc)" in body
    assert body.count("_rollback_nfl_prop_conn(conn)") >= 2
    # The odds prefetch is inside the try that closes on failure, not before it.
    assert body.index("load_nfl_prop_odds") < body.index("conn.close()")
