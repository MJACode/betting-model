"""The daily recap waits on bet games, not on every game that sport played.

2026-11-03: NCAAB_2026-11-03_warren-wilson_north-carolina-a-t was never bet
and never received a final. window_still_live treated any BET on that sport
and date as a slate, so the unscored exhibition held the whole NCAAB day
after all 21 counted picks were graded. X was posted by hand
(push_sent id 5000, x_results:2026-11-03). Discord (discord_results) was not.

The gate now holds only a game that itself carries a pick the recap publishes
or counts. The X ledger check stays in front of the tweet.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import discord_notifier as dn  # noqa: E402
from tracking import x_publisher as xp  # noqa: E402

DAY = "2026-11-03"
EXHIBITION = "NCAAB_2026-11-03_warren-wilson_north-carolina-a-t"
BET_GAME = "NCAAB_2026-11-03_duke_north-carolina"
MORNING = datetime(2026, 11, 4, 9, 45, tzinfo=dn.ET)
X_LOCK = "x_results:2026-11-03"


class _Gate:
    """Answers window_still_live the way the SQL it sends would.

    A query that still keys the hold on "any BET that sport, that date"
    blocks whenever the date has a counted pick. A query that keys the hold
    on the unfinished game's own published or counted pick blocks only when
    that game is one of `bet_games`.
    """

    def __init__(self, unfinished: tuple[str, ...], bet_games: tuple[str, ...]):
        self.unfinished = unfinished
        self.bet_games = set(bet_games)
        self.sql = ""
        self._row = None

    def execute(self, sql, params=()):
        self.sql = sql
        game_level = "p.game_id = g.game_id" in sql
        published = "push_sent" in sql and "signal_type = 'BET'" in sql
        if game_level and published:
            hit = any(game in self.bet_games for game in self.unfinished)
        else:
            hit = bool(self.bet_games)
        self._row = (1,) if hit else None
        return self

    def fetchone(self):
        return self._row


def test_an_unbet_game_that_is_not_final_does_not_block():
    """The date has a counted pick on another game. The unscored game does not."""
    conn = _Gate(unfinished=(EXHIBITION,), bet_games=(BET_GAME,))
    assert dn.window_still_live(conn, DAY, DAY, ("NCAAB",)) is False
    assert "p.game_id = g.game_id" in conn.sql
    assert "p.game_date = g.game_date AND p.sport = g.sport" not in conn.sql


def test_a_bet_game_that_is_not_final_does_block():
    conn = _Gate(unfinished=(BET_GAME,), bet_games=(BET_GAME,))
    assert dn.window_still_live(conn, DAY, DAY, ("NCAAB",)) is True
    assert "p.game_id = g.game_id" in conn.sql


def test_the_nov_3_x_results_ledger_blocks_a_second_tweet(monkeypatch):
    """push_sent x_results:2026-11-03 returns before a tweet is built.

    The gate is open: the only unscored game was not bet, and a counted pick
    has graded. A second tweet is still refused.
    """
    monkeypatch.setenv("RUN_X_PUBLISHER", "1")
    for name in ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN",
                 "X_ACCESS_TOKEN_SECRET"):
        monkeypatch.setenv(name, "test-value")
    tweets = []
    monkeypatch.setattr(xp, "post_tweet", lambda *a, **k: tweets.append(a[0]) or "999")

    class _Conn:
        def __init__(self):
            self.sql = ""
            self.params = ()

        def execute(self, sql, params=()):
            self.sql = sql
            self.params = tuple(params or ())
            return self

        def fetchone(self):
            if (self.params[:2] == (X_LOCK, "x_results")
                    and "FROM push_sent" in self.sql):
                return (1,)
            return None

        def fetchall(self):
            if "p.result IS NULL" in self.sql:
                return []
            return [("NCAAB", "ncaab_spread_market", "WIN", 0.02, -110.0,
                     None, False, 1.0, 1.1)]

        def commit(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr("data.db.get_connection", lambda *a, **k: _Conn())
    assert xp.notify_x_results(DAY, now=MORNING) == 0
    assert tweets == []
