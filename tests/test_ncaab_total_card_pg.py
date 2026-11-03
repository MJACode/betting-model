"""The NCAAB totals ledger against a real Postgres.

WHY A REAL DATABASE. Releasing a row left by the old 10-game wait is a claim
about the server: the upsert must replace that row, must leave a real decision
exactly as it was, and must return nothing for it, because publish() writes the
bet only when a row comes back. Runs against LATEST_LINE_TEST_DSN or a throwaway
cluster from tests/_pg.py, and SKIPS only where neither exists (the worker).
"""
from __future__ import annotations

import pytest

psycopg2 = pytest.importorskip("psycopg2")

from data.db import DBConnection  # noqa: E402
from scripts import ncaab_total_card as card  # noqa: E402
from tests._pg import can_scratch, env_dsn, scratch_cluster  # noqa: E402


@pytest.fixture(scope="module")
def dsn():
    if env_dsn():
        yield env_dsn()
        return
    if not can_scratch():
        pytest.skip("LATEST_LINE_TEST_DSN not set and no initdb -- needs a scratch Postgres")
    with scratch_cluster("ncaab-total-card-pg-") as d:
        yield d


@pytest.fixture()
def conn(dsn):
    c = DBConnection(psycopg2.connect(dsn), url=dsn)
    c.execute("DROP TABLE IF EXISTS ncaab_total_decisions, picks")
    c.execute(card.DECISIONS_DDL)
    c.execute("CREATE TABLE picks (game_id TEXT, model_id TEXT, signal_type TEXT)")
    for gid, detail in (("old_wait", "below_10_games: games played 0/0"),
                        ("priced", "below_cut: over 150.5 edge +0.0100 model 151.00 mean 150.60")):
        c.execute("INSERT INTO ncaab_total_decisions (game_id, check_hour, n_bets, detail) "
                  "VALUES (%s, 'first', 0, %s)", (gid, detail))
    c.commit()
    yield c
    c.close()


def _decision(gid):
    return {"game_id": gid, "check_hour": "second", "quote_at": "q", "cutoff": "c", "total_line": 157.5,
            "model_total": 139.5, "edge": 0.0631, "side": "under", "n_bets": 1, "detail": "bets: under"}


def test_a_row_from_the_old_wait_is_released_and_a_real_decision_stands(conn):
    assert card.decided_games(conn, ["old_wait", "priced", "new"]) == {"priced"}
    got = {g: conn.execute(card._INSERT_DECISION, _decision(g)).fetchone()
           for g in ("old_wait", "priced", "new")}
    conn.commit()
    assert got["old_wait"] and got["new"]
    assert got["priced"] is None          # no row back: publish() writes no bet
    rows = {r[0]: r[1:] for r in conn.execute(
        "SELECT game_id, check_hour, n_bets, side FROM ncaab_total_decisions").fetchall()}
    assert rows["old_wait"] == ("second", 1, "under")
    assert rows["new"] == ("second", 1, "under")
    assert rows["priced"] == ("first", 0, None)
    # released once: it is now a real decision, and it stands
    assert card.decided_games(conn, ["old_wait", "priced", "new"]) == {"old_wait", "priced", "new"}
    assert conn.execute(card._INSERT_DECISION, _decision("old_wait")).fetchone() is None
