"""
Guards on the measurement that decides whether to pay for tick data.

The number this produces is a spending decision, so the two ways it could
mislead are worth pinning: reading movement that is not there, and reading a
still line as a moving one.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from live_model.backtest.line_churn import churn_table, verdict  # noqa: E402


def _snaps(moves_every, n=60, market="player_pass_attempts", price_step=0):
    """One player, one book, n snapshots five minutes apart."""
    ts = pd.date_range("2024-11-03T18:00:00Z", periods=n, freq="5min")
    line, price, lines, prices = 30.5, -115.0, [], []
    for i in range(n):
        if moves_every and i and i % moves_every == 0:
            line += 0.5
        price += price_step
        lines.append(line)
        prices.append(price)
    return pd.DataFrame({
        "game_id": "g1", "player_id": "p1", "market": market, "book": "dk",
        "ts_dt": ts, "line": lines, "over_price": prices,
    })


def test_a_still_line_reads_as_still():
    t = churn_table(_snaps(moves_every=0))
    assert t.iloc[0].line_moved_pct == 0.0
    assert "LOW VALUE" in " ".join(verdict(t, "player_pass_attempts"))


def test_a_line_moving_every_interval_reads_as_under_sampled():
    t = churn_table(_snaps(moves_every=1))
    assert t.iloc[0].line_moved_pct == 100.0
    assert "FINER DATA MATTERS" in " ".join(verdict(t, "player_pass_attempts"))


def test_the_rate_is_the_share_of_intervals_not_of_snapshots():
    """59 gaps between 60 snapshots; a move every 4th is 25% of intervals."""
    t = churn_table(_snaps(moves_every=4))
    assert t.iloc[0].intervals == 59
    assert 20.0 < t.iloc[0].line_moved_pct < 30.0


def test_price_churn_is_reported_separately_from_line_churn():
    """
    The price moves far more freely than the line, and it is the part a tick
    feed would really add. Collapsing them would hide that.
    """
    t = churn_table(_snaps(moves_every=0, price_step=-1.0))
    assert t.iloc[0].line_moved_pct == 0.0
    assert t.iloc[0].price_moved_pct == 100.0


def test_a_single_snapshot_contributes_no_interval():
    one = _snaps(moves_every=0, n=1)
    assert churn_table(one).empty


def test_markets_are_not_pooled():
    a = _snaps(moves_every=0, market="player_pass_attempts")
    b = _snaps(moves_every=1, market="player_receptions")
    b["player_id"] = "p2"
    t = churn_table(pd.concat([a, b], ignore_index=True))
    assert len(t) == 2
    assert t.set_index("market").loc["player_pass_attempts", "line_moved_pct"] == 0.0
    assert t.set_index("market").loc["player_receptions", "line_moved_pct"] == 100.0
