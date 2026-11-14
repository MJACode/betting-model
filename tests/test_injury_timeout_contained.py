"""A timed-out return-ramp read costs the ramp rows, not the whole injuries run.

The injuries ingest holds every sport's inserts in one transaction. On
2026-11-12 to 11-14 the return-ramp read hit the statement timeout nine
times; Postgres then refuses every later statement in that transaction
("current transaction is aborted"), so the insert failed, the run rolled
back and no sport's injuries were stored. The fake connection below behaves
the way Postgres does after a failed statement: everything is refused until
ROLLBACK TO SAVEPOINT or ROLLBACK.
"""
from __future__ import annotations

import pytest

from data.ingestors import injury_ingestor as ing


class AbortedTransaction(Exception):
    pass


class PgLikeConn:
    def __init__(self):
        self.aborted = False
        self.savepoints: list[str] = []
        self.inserted: list[str] = []
        self.committed = False

    def execute(self, sql, params=None):
        head = sql.strip().upper()
        if head.startswith("ROLLBACK TO SAVEPOINT"):
            self.aborted = False
            return self
        if self.aborted:
            raise AbortedTransaction("current transaction is aborted, commands ignored until end of transaction block")
        if head.startswith("SAVEPOINT"):
            self.savepoints.append(head.split()[1])
        elif head.startswith("RELEASE SAVEPOINT"):
            self.savepoints.pop()
        elif head.startswith("INSERT"):
            self.inserted.append(sql)
        return self

    def commit(self):
        if self.aborted:
            raise AbortedTransaction("commit of an aborted transaction")
        self.committed = True

    def rollback(self):
        self.aborted = False
        self.savepoints.clear()

    def close(self):
        pass


@pytest.fixture
def conn(monkeypatch):
    c = PgLikeConn()
    monkeypatch.setattr(ing, "get_connection", lambda: c)
    monkeypatch.setattr(ing, "fetch_espn_injuries",
                        lambda sp, d: [{"player_id": "p1", "player_name": "A Player", "sport": sp}])

    def ramp_times_out(cn, sp, d):
        cn.aborted = True          # what a cancelled statement does to the transaction
        raise Exception("canceling statement due to statement timeout")

    monkeypatch.setattr(ing, "fetch_return_ramp_players", ramp_times_out)

    def upsert(cn, rows):
        for _ in rows:
            cn.execute("INSERT INTO injuries VALUES (1)")
        return len(rows)

    monkeypatch.setattr(ing, "_upsert_injuries", upsert)
    monkeypatch.setattr(ing, "_log_pipeline", lambda cn, *a, **k: cn.execute("INSERT INTO pipeline_log VALUES (1)"))
    monkeypatch.setattr(ing, "_replace_current_status", lambda cn, sp, rows, expected: len(rows))
    monkeypatch.setattr(ing, "_static_team_count", lambda sp: 30)
    return c


def test_a_timed_out_ramp_read_still_stores_the_sport_s_injuries(conn):
    out = ing.run_injury_ingestor(sport="NBA", report_date="2026-11-14")
    assert conn.committed
    assert sum("INTO injuries" in s for s in conn.inserted) == 1
    assert not conn.savepoints
    assert isinstance(out, dict)


class _Timeout(Exception):
    pgcode = "57014"


def _veto_conn(error):
    c = PgLikeConn()
    real = c.execute

    def execute(sql, params=None):
        if "FROM injuries" in sql and not c.aborted:
            c.aborted = True
            raise error
        return real(sql, params)

    c.execute = execute
    return c


def test_a_timed_out_injury_veto_read_fails_closed_and_leaves_the_transaction_usable():
    """An empty veto index would let the NFL prop card bet a player who is Out,
    so a timeout is re-raised (the date retries next pass), but only after the
    transaction is restored, so the caller can roll back or go on cleanly."""
    from models.nfl_prop_injury_veto import load_nfl_injury_index
    c = _veto_conn(_Timeout("canceling statement due to statement timeout"))
    with pytest.raises(_Timeout):
        load_nfl_injury_index(c, "2026-11-16")
    assert not c.aborted and not c.savepoints
    c.execute("INSERT INTO picks VALUES (1)")


def test_any_other_injury_veto_read_error_still_fails_open_and_leaves_it_usable():
    from models.nfl_prop_injury_veto import load_nfl_injury_index
    c = _veto_conn(Exception('column "status_ts" does not exist'))
    assert load_nfl_injury_index(c, "2026-11-16") == {}
    assert not c.aborted and not c.savepoints
    c.execute("INSERT INTO picks VALUES (1)")


@pytest.mark.parametrize("call", [
    lambda m, c: m.teams_with_props_today(c, "NBA", "2026-11-14"),
    lambda m, c: m._minutes_since_last_ingest(c),
])
def test_a_failed_player_news_read_leaves_the_transaction_usable(call):
    """Player news failed 'current transaction is aborted' (2026-11-14 04:36):
    its best-effort reads swallowed a failure without restoring the transaction."""
    from data.ingestors import player_news_ingestor as m
    c = PgLikeConn()
    real = c.execute

    def execute(sql, params=None):
        if ("FROM picks" in sql or "FROM player_news" in sql) and not c.aborted:
            c.aborted = True
            raise _Timeout("canceling statement due to statement timeout")
        return real(sql, params)

    c.execute = execute
    call(m, c)
    assert not c.aborted and not c.savepoints
    c.execute("INSERT INTO player_news VALUES (1)")


# ── NBA first-basket stats: one read of nba_pbp per rebuild ─────────────────

def test_the_four_first_basket_statements_read_the_period1_copy_not_nba_pbp():
    """They read nba_pbp twice each, eight passes over 1.2 GB a run, and the
    step timed out four times in six runs (2026-11-13/14)."""
    import re
    from data.ingestors import nba_first_basket as fb
    for name in ("GAMES_SQL", "PLAYERS_SQL", "GAMES_DELETE_SQL", "PLAYERS_DELETE_SQL"):
        sql = getattr(fb, name)
        assert not re.search(r"\bnba_pbp\b(?!_)", sql), name
        assert "fb_period1" in sql, name
    assert re.search(r"FROM nba_pbp p\b", fb.PERIOD1_SQL) and "p.period = 1" in fb.PERIOD1_SQL


class _SeasonConn:
    def __init__(self, has_last_season):
        self.has_last_season = has_last_season

    def execute(self, sql, params=None):
        self.sql = sql
        return self

    def fetchone(self):
        if "to_regclass" in self.sql:
            return (True,)
        return (1,) if self.has_last_season else None


@pytest.mark.parametrize("has_last, want", [(True, [2027]), (False, [2026, 2027])])
def test_first_basket_rebuilds_last_season_only_while_it_has_no_rows(has_last, want):
    from data.ingestors import nba_first_basket as fb
    assert fb.seasons_to_build(_SeasonConn(has_last), 2027) == want
