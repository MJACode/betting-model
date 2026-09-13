"""
load_context marks each game FBS-vs-FBS by the pre-game models' own rule.

The live loop used to price every NCAAF game with a DraftKings pregame line,
FBS-vs-FCS included, while every pre-game NCAAF model declines those games at
features.ncaaf_feature_engine._is_fbs. 24 of 43 ncaaf_live_total BETs in the
week of 2026-09-07 were FBS-vs-FCS. This pins the context half of the gate
(the pricing half is in test_serve.py): the SQL's rating columns reach
GameContext.fbs_matchup, and the rule is the SAME one -- SP+ necessary,
classification may only veto -- so a registry row wrongly saying "fbs" with no
SP+ (North Dakota State, 2026-08-29) does not pass.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ncaaf_live import gameday  # noqa: E402


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, rows):
        self.rows = rows
        self.sql = None

    def execute(self, sql, params=None):
        self.sql = sql
        return _Result(self.rows)

    def close(self):
        pass


def _row(gid, home, away, h_sp, h_cls, a_sp, a_cls):
    return (gid, home, away, "2026-09-12T19:00:00Z", "2026-09-12",
            -7.5, 55.5, 4.0, 0, h_sp, h_cls, a_sp, a_cls)


def test_context_carries_the_fbs_rule_for_both_teams():
    conn = _Conn([
        _row("g_fbs", "TCU", "North Carolina", 12.1, "fbs", 3.4, "fbs"),
        _row("g_fcs", "Wisconsin", "Western Illinois", 15.0, "fbs", None, "fcs"),
        _row("g_wrong_registry", "Air Force", "North Dakota State",
             -2.0, "fbs", None, "fbs"),
        _row("g_null_class", "Nevada", "Utah State", -8.0, None, -1.0, None),
        _row("g_veto", "Troy", "Alabama State", 1.0, "fbs", 0.5, "fcs"),
    ])
    ctx = {c.game_id: c for c in gameday.load_context(conn=conn, date="2026-09-12").values()}

    assert ctx["g_fbs"].fbs_matchup is True
    assert ctx["g_null_class"].fbs_matchup is True, "NULL classification defers to SP+"
    assert ctx["g_fcs"].fbs_matchup is False
    assert ctx["g_wrong_registry"].fbs_matchup is False, "no SP+ settles it"
    assert ctx["g_veto"].fbs_matchup is False, "another division vetoes"
    # The pregame lines still load for every game, so nothing else changed.
    assert all(c.pregame_total == 55.5 for c in ctx.values())
    assert "ncaaf_team_stats" in conn.sql
