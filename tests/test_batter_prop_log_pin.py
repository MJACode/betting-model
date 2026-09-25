"""The batter log load inside dispatch:prop-scoring stays date-bounded.

2026-09-25 00:11:02Z the evening refresh cancelled this statement at
statement_timeout (pipeline_log 95334, 57014):

    SELECT ... FROM player_game_log
    WHERE player_type = 'batter' AND at_bats >= 1 AND hits IS NOT NULL
    ORDER BY player_id, game_date

No slate bound. 321,134 rows. EXPLAIN walked the whole player index and
sorted it (cost 30150). `game_date >=` the prior season's Jan 1 range-scans
idx_player_game_log_date (cost 15610). Same rows the rolling windows can
see — last 20 games and a one-season fallback — not a cut.
"""
from __future__ import annotations

import inspect

from features import prop_feature_engine as fe
from features.prop_feature_engine import build_batter_scoring_rows
from models.scorer import run_batter_prop_scorer


class _Rec:
    def __init__(self):
        self.calls: list[tuple[str, object]] = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return []


def _log_sql(seasons, needle: str) -> tuple[str, object]:
    rec = _Rec()
    fe._build_bulk_batter_lookups(rec, seasons)
    hits = [(sql, params) for sql, params in rec.calls if needle in sql]
    assert len(hits) == 1, [sql[:80] for sql, _ in hits]
    return hits[0]


def test_batter_log_scan_is_pinned_to_the_lookback_not_the_catalog():
    """The statement Postgres cancelled had no date predicate at all."""
    sql, params = _log_sql([2026], "at_bats >= 1")
    where = sql.split("WHERE", 1)[1]
    assert "game_date >= %s" in where, sql
    assert "player_type = 'batter'" in where, sql
    assert params == ("2025-01-01",)
    # Bisect needs player_id, game_date order. This ORDER BY is load-bearing.
    assert "ORDER BY player_id, game_date" in sql, sql
    assert "hits IS NOT NULL\n        ORDER BY" not in sql


def test_starter_log_inside_the_batter_loader_uses_the_same_floor():
    """The next statement in the same loader is the seq scan that took 42s
    in that refresh. HR/9 is last-3 plus one prior season, so the same floor
    is the same rows. It does not feed umpire career totals."""
    sql, params = _log_sql([2026], "is_starter = TRUE")
    where = sql.split("WHERE", 1)[1]
    assert "game_date >= %s" in where, sql
    assert params == ("2025-01-01",)
    assert "ORDER BY player_id, game_date" in sql, sql


def test_training_from_the_tables_first_season_still_reads_the_prior_year():
    """A pass that asks for 2019 (the earliest season stored) binds 2018-01-01,
    which is the whole log. The floor is one season of reach-back, not a
    slate-only cut that would drop training history."""
    _, params = _log_sql([2019, 2020, 2021, 2022, 2023], "at_bats >= 1")
    assert params == ("2018-01-01",)


class _ScoringConn:
    """Lineups exist; every other read is empty. Counts the cancelled scan."""

    log_scans = 0

    def __init__(self):
        self.sql = ""

    def execute(self, sql, params=None):
        self.sql = sql
        if "at_bats >= 1" in sql and "player_game_log" in sql:
            _ScoringConn.log_scans += 1
        return self

    def fetchall(self):
        if "lineup_slots" in self.sql:
            return [("1", "A Hitter", "NYY", "MLB_2026-09-24_BOS_NYY", 1)]
        return []

    def close(self):
        pass


def test_five_models_share_one_log_load(monkeypatch):
    _ScoringConn.log_scans = 0
    monkeypatch.setattr(fe, "get_connection", lambda: _ScoringConn())
    cache: dict = {}
    build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_hits", bulk_cache=cache)
    build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_tb", bulk_cache=cache)
    build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_runs", bulk_cache=cache)
    build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_sb", bulk_cache=cache)
    build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_walks", bulk_cache=cache)
    assert _ScoringConn.log_scans == 1
    assert 2026 in cache


def test_no_lineup_does_not_scan_the_log(monkeypatch):
    class _Empty(_ScoringConn):
        def fetchall(self):
            return []

    _ScoringConn.log_scans = 0
    monkeypatch.setattr(fe, "get_connection", lambda: _Empty())
    cache: dict = {}
    out = build_batter_scoring_rows("2026-09-24", "mlb_prop_batter_hits",
                                    bulk_cache=cache)
    assert out.empty
    assert _ScoringConn.log_scans == 0
    assert cache == {}


def test_the_batter_loop_hands_one_cache_to_every_model():
    src = inspect.getsource(run_batter_prop_scorer)
    assert "bulk_cache: dict = {}" in src, src
    assert "bulk_cache=bulk_cache" in src, src
    assert src.count("build_batter_scoring_rows(") == 1
