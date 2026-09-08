"""A cache refresh must never delete history the database has already lost.

WHAT HAPPENED (2026-09-08). `data/local/nfl_prop_odds.parquet` is tracked in
git and is the board every NFL prop analysis reads. Refreshing it from Supabase
replaced 916,965 rows with a fresh SELECT -- and the fresh SELECT came back
without a single sharp-book quote for season 2025, because `player_prop_odds`
is pruned and the prop-table carve-out had never been extended to betonlineag.
117,048 sharp snapshots spanning 2023-2025 existed only in that file.

THE PART THAT MAKES IT DANGEROUS is what happened next: the market-relative
rule re-graded at -2.81% on the replacement board, down from +6.89%. That is a
plausible-looking number with a clean methodology behind it, and nothing about
it announces that every 2025 sharp quote had been deleted an hour earlier. A
refresh that quietly narrows the evidence does not fail loudly -- it produces a
WRONG RESULT THAT NOBODY QUESTIONS.

Two fixes, and both are needed:
  * data/prune_odds._prop_reference_books stops new history being deleted, by
    deriving the protected set from the models instead of a second hand-kept
    list. tests/test_sharp_book_retention.py covers that half.
  * scripts.pull_local_cache._merge_with_cache stops old history being
    overwritten, by making the pull additive. This file covers that half.
"""
from __future__ import annotations

import pandas as pd
import pytest

import scripts.pull_local_cache as plc


def _frame(n: int, book: str, snap: str, season_tag: str) -> pd.DataFrame:
    return pd.DataFrame({
        "game_id": [f"NFL_{season_tag}_W1_G{i}" for i in range(n)],
        "game_date": ["2024-09-08"] * n,
        "player_name": [f"Player {i}" for i in range(n)],
        "market": ["player_reception_yds"] * n,
        "line": [40.5] * n,
        "over_price": [-110] * n,
        "under_price": [-110] * n,
        "bookmaker": [book] * n,
        "snapshot_at": [f"2024-09-0{1 + i % 8}T12:00:00Z" for i in range(n)],
        "snapshot_type": [snap] * n,
    })


@pytest.fixture()
def cached(tmp_path, monkeypatch):
    """Point the cache at a temp parquet and return its path."""
    path = tmp_path / "nfl_prop_odds.parquet"
    monkeypatch.setattr(plc.local_store, "_path", lambda table: path)
    return path


def test_a_pull_that_lost_rows_keeps_them(cached):
    """The actual 2026-09-08 shape: the DB comes back missing a whole slice."""
    history = _frame(50, "pinnacle", "open", "2025")
    fresh = _frame(20, "pinnacle", "t48", "2023")
    history.to_parquet(cached, index=False)

    merged = plc._merge_with_cache(fresh)

    assert len(merged) == 70, "the pull must ADD to the cache, not replace it"
    kept = merged[(merged.snapshot_type == "open")]
    assert len(kept) == 50, (
        "rows the database no longer has were dropped -- this is the bug that "
        "turned +6.89% into -2.81% with no error and no warning")
    assert set(merged.snapshot_type) == {"open", "t48"}


def test_rows_present_in_both_are_kept_once(cached):
    """Additive must not mean duplicated: a re-pull of unchanged data is a
    no-op, or every refresh doubles the board and every count is wrong."""
    history = _frame(30, "pinnacle", "open", "2025")
    history.to_parquet(cached, index=False)

    merged = plc._merge_with_cache(history.copy())

    assert len(merged) == 30


def test_a_first_ever_pull_still_works(cached):
    """No cache yet is not an error -- it is Tuesday."""
    fresh = _frame(10, "pinnacle", "open", "2025")
    assert len(plc._merge_with_cache(fresh)) == 10


def test_an_unreadable_cache_refuses_rather_than_overwrites(cached):
    """Silently treating a corrupt cache as empty would destroy it. The whole
    lesson here is that losing history quietly is worse than stopping."""
    cached.write_bytes(b"this is not a parquet file")

    with pytest.raises(RuntimeError, match="Refusing to overwrite"):
        plc._merge_with_cache(_frame(5, "pinnacle", "open", "2025"))


class _FakeConn:
    """Returns the shrunken board the real database returned on 2026-09-08."""

    def __init__(self, rows):
        self._rows = rows

    def execute(self, *_a, **_k):
        return self

    def fetchall(self):
        return self._rows


def test_the_pull_ITSELF_is_additive(cached):
    """THE WIRING, not just the helper.

    The first version of this file tested _merge_with_cache directly and passed
    with the fix deleted from _pull_odds -- a guard the dead code satisfied. The
    call site is the thing that has to hold, so this drives the real entry point
    with a database that has lost its history.
    """
    history = _frame(40, "pinnacle", "open", "2025")
    history.to_parquet(cached, index=False)

    fresh = _frame(15, "pinnacle", "t48", "2023")
    rows = [tuple(r) for r in fresh[plc._ODDS_COLS].itertuples(index=False)]

    out = plc._pull_odds(_FakeConn(rows))

    assert len(out) == 55, (
        "_pull_odds returned only what the database still holds; the cached "
        "history was dropped on the way through")
    assert (out.snapshot_type == "open").sum() == 40
    assert "season" in out.columns, "the season label must survive the merge"
