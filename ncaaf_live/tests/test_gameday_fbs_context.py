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


def _row(gid, home, away, h_sp, h_cls, a_sp, a_cls,
         gd="2026-09-12", ct="2026-09-12T19:00:00Z",
         spread=-7.5, total=55.5):
    return (gid, home, away, ct, gd,
            spread, total, 4.0, 0, h_sp, h_cls, a_sp, a_cls)


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


# ── (home, away) collisions — session 301 / Reviewer after #696 ──────────────
#
# Night-game twins are by design (docs/sports/ncaaf.md): the odds ingestor
# dates by ET, CFBD by UTC, so a ~8pm-ET kick exists twice. load_context
# used to last-wins overwrite on the folded pair. live_slate_dates() includes
# yesterday until 6am ET — exactly when a Saturday night game is still live.
# Picks attach to the odds row (the one with pregame DK lines). A silent pick
# of the other row prices on the wrong game_id / the wrong line / no line.


def _night_twin(live_spread=-3.5, live_total=54.5,
                cfbd_spread=None, cfbd_total=None):
    """Designed ET/UTC twin (docs/sports/ncaaf.md). Same folded (home, away),
    adjacent dates. Session 301's 32-matchup window is this shape
    (e.g. NCAAF_2026-09-12_north-dakota-state_air-force live vs
    ..._2026-09-13_... cfbd). Fixture uses an FBS pair so the collision
    is one serve.price would actually price."""
    return [
        _row("NCAAF_2026-08-29_memphis_unlv",
             "UNLV", "Memphis", 4.0, "fbs", 8.0, "fbs",
             gd="2026-08-29", ct="2026-08-30T02:19:00Z",
             spread=live_spread, total=live_total),
        _row("NCAAF_2026-08-30_memphis_unlv",
             "UNLV", "Memphis", 4.0, "fbs", 8.0, "fbs",
             gd="2026-08-30", ct="2026-08-30T02:19:00Z",
             spread=cfbd_spread, total=cfbd_total),
    ]


def _pair_key():
    return (gameday._fold("UNLV"), gameday._fold("Memphis"))


def test_a_twin_does_not_silently_take_the_row_without_lines():
    """The designed twin: odds/live row has the DK lines, CFBD row does not.

    Last-wins (the old assignment) keeps whichever row the query returned
    last. This fixture puts the empty CFBD row last, so last-wins would
    keep a context with no pregame total — serve.price then declines, and
    a live game is silently not priced. The odds row is the only one that
    can be priced; using it is not a guess. docs/sports/ncaaf.md: picks
    attach to the odds row.

    Reversed order is the first-wins twin of the same bug: a `out[key] =
    ctx` in either direction would fail one of these two.
    """
    for rows in (_night_twin(), list(reversed(_night_twin()))):
        ctx = gameday.load_context(conn=_Conn(rows), date="2026-08-29")
        key = _pair_key()
        assert key in ctx
        assert ctx[key].game_id == "NCAAF_2026-08-29_memphis_unlv"
        assert ctx[key].pregame_total == 54.5
        assert ctx[key].pregame_spread == -3.5


def test_two_priceable_rows_for_one_pair_are_refused():
    """Both rows have lines: that is not the designed twin, and picking
    one writes a BET to a guessed game_id. NFL live resolve_game_id
    refuses when it finds two rows. Same here.

    Last-wins would keep the CFBD row's 48.0 total. This test fails on
    that assignment whether the assertion is 'absent' or 'not 48.0'.
    """
    conn = _Conn(_night_twin(
        live_spread=-3.5, live_total=54.5,
        cfbd_spread=-4.0, cfbd_total=48.0))
    ctx = gameday.load_context(conn=conn, date="2026-08-29")
    key = _pair_key()
    assert key not in ctx
    assert all(c.pregame_total != 48.0 for c in ctx.values())


def test_neither_twin_having_lines_is_also_dropped():
    """No silent game_id attachment when neither row can be priced."""
    conn = _Conn(_night_twin(
        live_spread=None, live_total=None,
        cfbd_spread=None, cfbd_total=None))
    ctx = gameday.load_context(conn=conn, date="2026-08-29")
    assert _pair_key() not in ctx


def test_an_unrelated_game_is_unaffected_by_a_collision():
    """A refused pair must not empty the rest of the slate."""
    rows = _night_twin(cfbd_spread=-4.0, cfbd_total=48.0)
    rows.append(_row("g_fbs", "TCU", "North Carolina", 12.1, "fbs", 3.4, "fbs"))
    ctx = gameday.load_context(conn=_Conn(rows), date="2026-08-29")
    tcu = (gameday._fold("TCU"), gameday._fold("North Carolina"))
    assert tcu in ctx and ctx[tcu].game_id == "g_fbs"
    assert _pair_key() not in ctx
