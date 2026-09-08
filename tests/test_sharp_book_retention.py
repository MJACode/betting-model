"""
A sharp book's price is a model INPUT, so its history must survive pruning.

WHY THIS EXISTS
---------------
2026-08-31. MLB props are moving to a market-relative construction: take
Pinnacle's de-vigged number as the estimate of truth and bet where DraftKings
disagrees by more than the juice. That is the one approach in this repo with a
blind-tested positive result (models/nfl_prop_market, +10.76% on 954 bets).

Pinnacle was added to LINE_SHOP_BOOKMAKERS on 2026-08-25 in a DISPLAY role, and
data/prune_odds.py protects only the scoring book and the synthetic historical
lines. Everything else is thinned to its opening and newest snapshot after
PRUNE_NON_DK_KEEP_DAYS (2).

That retention is correct for a shopping book -- only its newest row is ever
read -- and wrong for a sharp one, whose history is the evidence a model is
built and validated on. MLB Pinnacle capture began 2026-08-27, so there is
almost none of it, and every pruned day is validation that cannot be recovered
afterwards.
"""

from __future__ import annotations

import config
from data import prune_odds


def test_every_sharp_book_is_protected_in_the_prop_table():
    for book in config.SHARP_BOOKMAKERS:
        assert book in prune_odds.protected_for("player_prop_odds"), (
            f"{book} is a sharp reference a prop model reads; pruning its "
            f"history deletes the model's evidence")


def test_pinnacle_specifically_is_protected_in_the_prop_table():
    """Named rather than derived, so removing it from SHARP_BOOKMAKERS fails
    here too and not just silently."""
    assert "pinnacle" in prune_odds.protected_for("player_prop_odds")


def test_sharp_books_are_NOT_protected_in_the_game_level_odds_table():
    """The carve-out is deliberately narrow. Nothing reads a sharp book's
    game-level history, and at ~21 snapshots per proposition per day a blanket
    protection would put back most of the storage the retention policy exists
    to save."""
    assert "pinnacle" not in prune_odds.protected_for("odds")
    assert prune_odds.protected_for("odds") == prune_odds.PROTECTED_BOOKMAKERS


def test_the_scoring_book_is_still_protected():
    """The sharp addition must not displace what was already protected."""
    assert config.ODDS_API_BOOKMAKER in prune_odds.PROTECTED_BOOKMAKERS
    assert "sbr_consensus" in prune_odds.PROTECTED_BOOKMAKERS


def test_the_prune_predicate_binds_the_TABLES_protected_set():
    """The SQL, not just the tuple. counts and both delete tiers share
    _unprotected(), so what it binds into %(protected)s is what actually
    decides which rows are deleted -- a carve-out that never reaches the
    params is not a carve-out."""
    params: dict = {}
    sql = prune_odds._unprotected(params, "player_prop_odds")
    assert "bookmaker NOT IN %(protected)s" in sql
    assert "pinnacle" in params["protected"]

    other: dict = {}
    prune_odds._unprotected(other, "odds")
    assert "pinnacle" not in other["protected"]


def test_a_shopping_book_is_still_prunable():
    """This is a targeted carve-out, not an amnesty. If every line-shop book
    became protected the storage rationale in config would be dead and nobody
    would notice."""
    shoppers = [b for b in config.LINE_SHOP_BOOKMAKERS
                if b not in prune_odds.protected_for("player_prop_odds")]
    assert shoppers, ("no line-shop book is prunable any more — the retention "
                      "win in config.PRUNE_NON_DK_KEEP_DAYS is gone")


# ── the path that actually deletes ───────────────────────────────────────────

class _RecordingConn:
    """Captures every (sql, params) prune_table issues, and answers counts."""

    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def execute(self, sql, params=None):
        self.calls.append((sql, dict(params or {})))
        return self

    def fetchone(self):
        return (0,)


def test_prune_table_binds_the_prop_tables_carve_out_into_the_DELETE():
    """The tuple and the helper are not enough — this asserts on what
    prune_table actually sends.

    Found by mutation: reverting prune_table's `_unprotected(params, table)`
    back to `_unprotected(params)` silently removed Pinnacle's protection and
    every test still passed, because they exercised the helper directly
    instead of the path that deletes rows.
    """
    conn = _RecordingConn()
    prune_odds.prune_table(
        conn, "player_prop_odds", ("game_id", "market", "player_name"),
        "game_date {op} %({param})s", keep_days=2, today="2026-08-31",
        dry_run=True)

    assert conn.calls, "prune_table issued no statements"
    protected = {tuple(p["protected"]) for _, p in conn.calls if "protected" in p}
    assert protected, "no statement bound a protected set"
    for tup in protected:
        assert "pinnacle" in tup, (
            "the DELETE path does not carry the prop-table carve-out — "
            "Pinnacle's history would be pruned despite PROTECTED_BY_TABLE")


def test_prune_table_does_NOT_carve_out_sharp_books_for_the_odds_table():
    conn = _RecordingConn()
    prune_odds.prune_table(
        conn, "odds", ("game_id", "market"),
        "game_id IN (SELECT game_id FROM games WHERE game_date {op} %({param})s)",
        keep_days=2, today="2026-08-31", dry_run=True)

    for _, p in conn.calls:
        if "protected" in p:
            assert "pinnacle" not in tuple(p["protected"])


def test_every_prop_reference_book_is_protected():
    """DERIVED from the models, so a THIRD reference is protected on the day it
    is added rather than on the day someone notices it was not.

    2026-09-08: betonlineag became a second de-vig reference in
    models/nfl_prop_market, and nothing added it here. config.SHARP_BOOKMAKERS
    still read "pinnacle" alone, the two tests above both passed, and the
    pruner kept deleting it. The measured damage is in _prop_reference_books'
    docstring; the short version is that `player_prop_odds` now holds no NFL
    sharp prop snapshot older than 2026-04-01, and the 2023-2025 history the
    rule's whole record rests on survives only in a tracked parquet.
    """
    import models.nfl_prop_market as nfl

    protected = prune_odds.protected_for("player_prop_odds")
    missing = [b for b in nfl.SHARP_BOOKS if b not in protected]
    assert not missing, (
        f"{missing} are de-vig references the rule READS but the pruner does "
        f"not protect. Their history IS the model's evidence.")


def test_the_narrow_carve_out_stays_narrow():
    """The prop-table protection must not leak into `odds`, where the retention
    rationale still holds in full and a blanket carve-out would put back most of
    the storage the policy exists to save."""
    import models.nfl_prop_market as nfl

    in_odds = prune_odds.protected_for("odds")
    for book in nfl.SHARP_BOOKS:
        assert book not in in_odds, (
            f"{book} is protected in `odds`; the carve-out is prop-only")
