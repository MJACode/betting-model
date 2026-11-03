"""The tracked-bet line-change push compares a price only at the tracked number.

tracking/push_notifier._line_change_alerts pushes when DraftKings' price on a
tracked bet moves 4+ probability points off the locked price. For a line
market (totals, team totals, spreads) DraftKings' newest row can be at another
number: a tracked Under 115.5 at -112 against DraftKings' Under 113.5 at +105
is two different bets, and pushing "moved in your favor -112 -> +105" for it
said the opposite of what happened (the number fell two points, against the
under). So a line market is compared only while DraftKings is at the tracked
number. Moneylines have no number and are unchanged.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from tracking import push_notifier  # noqa: E402


class _Res:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


class _Conn:
    """The tracked bet, and an empty push ledger."""

    def __init__(self, tracked):
        self.tracked = tracked

    def execute(self, sql, params=()):
        if "FROM tracked_bets" in sql:
            return _Res([self.tracked])
        if "FROM push_sent" in sql:
            return _Res([])
        raise AssertionError(sql[:80])


def _alerts(monkeypatch, model_id, side, locked_odds, locked_line, dk_row):
    import models.scorer as scorer
    monkeypatch.setattr(scorer, "_get_dk_odds", lambda conn, gid, market: dk_row)
    tracked = ("dev-1", 42, "NBA_2026-11-05_BOS_MIL", model_id, side, locked_odds,
               "label", locked_line, "MIL", "BOS")
    return push_notifier._line_change_alerts(_Conn(tracked), "2026-11-05")


@pytest.mark.parametrize("model_id, side, line, moved_to, col", [
    ("nba_team_total_luck", "under", 115.5, 113.5, "total_line"),
    ("nba_first_half_total_luck", "over", 112.5, 113.5, "total_line"),
    ("nba_total_luck", "over", 225.5, 227.5, "total_line"),
    ("wnba_spread", "home", -4.5, -6.5, "spread_home"),
])
def test_a_price_at_another_number_is_not_a_move(monkeypatch, model_id, side, line, moved_to, col):
    """RULE: no alert while DraftKings is at another number. Watched failing
    (an alert 'in your favor') before the number was checked."""
    price_col = {"under": "under_price", "over": "over_price", "home": "home_price"}[side]
    moved = {col: moved_to, price_col: 105}
    assert _alerts(monkeypatch, model_id, side, -112, line, moved) == []
    same = {col: line, price_col: 105}
    [a] = _alerts(monkeypatch, model_id, side, -112, line, same)
    assert (a["locked"], a["current"], a["against"]) == (-112, 105, False)


def test_a_moneyline_has_no_number_and_still_alerts(monkeypatch):
    [a] = _alerts(monkeypatch, "nba_moneyline", "home", -112, None, {"home_price": 105})
    assert a["current"] == 105
