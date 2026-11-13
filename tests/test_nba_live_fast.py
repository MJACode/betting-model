"""The NBA in-play loop, the fast way (models/nba_live_loop.py; mike,
2026-11-13: "Move everything over to the fast way").

Pinned here:
  * while DraftKings' board feed is live, a window is decided as soon as
    ESPN's newest play carries DraftKings' current score: no 170 s + 60 s
    waits; the provider call stays (Pinnacle is the rule's pair);
  * ESPN behind DraftKings is re-read every few seconds until it catches up,
    and the game is decided then, on the full play list;
  * DraftKings' quote is the board's, and DraftKings is the only book a fast
    decision bets; the ledger reason says the board decided it;
  * a stale feed is the slow way, exactly as before.
"""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from data.ingestors.nba_live_feed import newest_play_score
from tests import _nba_live_synth as S
from tests.test_nba_live_loop import Clock, Db, books, make_loop
import models.nba_live_ig2 as M
import models.nba_live_loop as LP


@pytest.fixture(scope="module")
def art():
    return M.load_artifact()


class FakeDk:
    def __init__(self, clock, rows, age=1.0):
        self.clock, self.rows, self.age = clock, rows, age

    def last_read(self):
        return pd.Timestamp(self.clock.now) - pd.Timedelta(seconds=self.age), True

    def reads(self, ids):
        return pd.DataFrame([r for r in self.rows if r["game_id"] in ids])


def board_row(at, score, spread=(-3.5, -105.0, -115.0)):
    return {"game_id": S.GAME_ID, "read_at": pd.Timestamp(at), "period_label": "2nd Quarter", "period": 2,
            "clock_s": 415.0, "home_score": score[0], "away_score": score[1], "spread_home": spread[0],
            "spread_home_price": spread[1], "spread_away_price": spread[2], "total_line": None,
            "over_price": None, "under_price": None}


def fast(art, monkeypatch, *, lag=0.0, age=1.0, dk_spread=(-3.5, -105.0, -115.0)):
    plays = S.build_plays()
    w = S.wall_of(plays, 2, 420.0)                 # the quarter-2 7:00 made shot
    slot = w + timedelta(seconds=20)
    db = Db().install(monkeypatch)
    clock = Clock(slot)
    score = newest_play_score(S.summary(plays, known_until=slot))     # after the 7:00 basket
    loop = make_loop(art, plays, clock, lambda now: books(w + timedelta(seconds=5)), db, slot, lag=lag)
    loop.dk = FakeDk(clock, [board_row(w + timedelta(seconds=4), score, dk_spread)], age=age)
    return loop, db, clock, w, slot


def test_the_window_is_decided_on_the_board_without_the_espn_wait(art, monkeypatch):
    loop, db, clock, w, slot = fast(art, monkeypatch)
    loop.tick()
    assert clock.now == slot                                     # no wait, no recheck
    assert loop.feed.calls == 1                                  # Pinnacle still comes from the provider
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert row["outcome"] == "bet" and "DraftKings board" in row["reason"]
    p, = db.picks
    # DraftKings is the only book a fast decision bets: FanDuel's +2.5 at +100,
    # the slow way's choice, is not on the table
    assert (p["pick_label"], p["decision_book"], p["decision_odds"]) == ("NYK +3.5 (live)", "draftkings", -115.0)
    assert p["scored_line"] == -3.5                              # the HOME number


def test_espn_behind_draftkings_is_re_read_until_it_shows_the_score(art, monkeypatch):
    """ESPN serves plays 30 s late: at the window it lacks the 7:00 basket
    DraftKings already shows, so the loop re-reads it every 3 s until it does."""
    loop, db, clock, w, slot = fast(art, monkeypatch, lag=30.0)
    loop.tick()
    waited = (clock.now - slot).total_seconds()
    assert 0 < waited <= LP.DK_CATCHUP_MAX_SEC and waited % LP.DK_CATCHUP_GAP_SEC == 0
    assert (S.GAME_ID, M.SPREAD_Q12) in db.ledger
    assert "DraftKings board" in db.ledger[(S.GAME_ID, M.SPREAD_Q12)]["reason"]


def test_a_stale_feed_is_the_slow_way_as_before(art, monkeypatch):
    loop, db, clock, w, slot = fast(art, monkeypatch, age=60.0)
    loop.tick()
    assert (clock.now - slot).total_seconds() >= 45.0 + 30.0    # the graded waits
    row = db.ledger[(S.GAME_ID, M.SPREAD_Q12)]
    assert "DraftKings board" not in row["reason"] and row["outcome"] == "bet"
    assert db.picks[0]["decision_book"] == "fanduel"            # the slow way's best line, as graded


def test_the_board_quote_replaces_the_providers_draftkings_row():
    fetched = pd.Timestamp("2026-11-05T01:00:00Z")
    rows = [{"game_id": "g", "sport": "NBA", "market": "spreads", "bookmaker": "draftkings",
             "snapshot_type": "in_play", "snapshot_at": "2026-11-05T00:59:00+00:00", "spread_home": -3.5,
             "home_price": -105.0, "away_price": -115.0},
            {"game_id": "g", "sport": "NBA", "market": "spreads", "bookmaker": "pinnacle",
             "snapshot_type": "in_play", "snapshot_at": "2026-11-05T00:59:30+00:00", "spread_home": -3.5,
             "home_price": -110.0, "away_price": -110.0}]
    reads = pd.DataFrame([{"game_id": "g", "read_at": fetched - pd.Timedelta(seconds=8), "period_label": "1st Quarter",
                           "period": 1, "clock_s": 300.0, "home_score": 20, "away_score": 18, "spread_home": -4.5,
                           "spread_home_price": -110.0, "spread_away_price": -110.0, "total_line": None,
                           "over_price": None, "under_price": None}])
    out, games = LP.overlay_dk_rows(rows, reads, fetched, fetched)
    dk = [r for r in out if r["bookmaker"] == "draftkings"]
    assert games == {"g"} and len(dk) == 1 and dk[0]["spread_home"] == -4.5
    assert pd.Timestamp(dk[0]["snapshot_at"]) == fetched - pd.Timedelta(seconds=8)
    assert [r for r in out if r["bookmaker"] == "pinnacle"][0]["spread_home"] == -3.5
