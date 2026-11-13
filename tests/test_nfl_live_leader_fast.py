"""The NFL late-game leader loop, the fast way (nfl_live_leader/gameday.py;
mike, 2026-11-13: "Move everything over to the fast way").

Pinned here:
  * while DraftKings' board feed is live, a due game is evaluated on DraftKings'
    own moneyline with no provider call;
  * a game whose DraftKings score differs from our state's is not evaluated
    and its slot is NOT spent: the next tick, once the scores agree, is;
  * the 5-minute cadence (the backtest's grid) is unchanged.
"""
from __future__ import annotations

import pandas as pd

from nfl_live_leader import gameday as G
from tests.test_nfl_live_leader_gameday import CTX, _run_loop, live_state, quote_payload


class Src:
    """DraftKings' board for CTX: TB -130 at DAL +450, DraftKings showing
    `score(t)` (home, away) at loop time t."""

    def __init__(self, score):
        self.score = score
        self.reset = lambda: None

    def last_read(self):
        return pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=1), True

    def reads(self, ids):
        h, a = self.score(G.time.time())
        return pd.DataFrame([{"game_id": CTX.game_id, "read_at": pd.Timestamp.now(tz="UTC") - pd.Timedelta(seconds=5),
                              "period_label": "4th Quarter", "period": 4, "clock_s": 300.0, "home_score": h,
                              "away_score": a, "spread_home": None, "spread_home_price": None,
                              "spread_away_price": None, "total_line": None, "over_price": None,
                              "under_price": None, "home_ml": 450.0, "away_ml": -130.0}])


def script(n=12):
    e1 = live_state(eid="E1", poss="away")                      # TB up 8 (16-24), BET at -130
    e2 = live_state(eid="E2", home=20, away=14, poss="home")
    final = live_state(eid="E1", state="post", final=True, evaluable=False)
    final2 = live_state(eid="E2", state="post", final=True, evaluable=False)
    return [{"E1": e1, "E2": e2}] * n + [{"E1": final, "E2": final2}] * 4


def test_a_due_game_is_evaluated_on_the_board_with_no_provider_call(monkeypatch):
    monkeypatch.setattr(G, "dk_source", lambda conn_fn: Src(lambda t: (16, 24)))
    payload = quote_payload(-100000, 99999, home="New York Giants", away="Washington Commanders")
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, script(), payload)
    assert rc == 0
    assert len(writes) == 1 and writes[0]["pick_label"] == "TB ML (live)" and writes[0]["dk_odds"] == -130.0
    assert [t for e, t in evals if e == "E1"] == [0.0]                    # decided at its first slot
    # E2 is not on the board, so it is priced by the provider: one call per E2 slot
    assert feed.fetches == len([t for e, t in evals if e == "E2"])


def test_draftkings_ahead_of_our_state_waits_without_spending_the_slot(monkeypatch):
    """DraftKings shows the 16-24 score from t=40 only (our state has it from
    t=0): E1 waits two ticks, then is evaluated in the same slot."""
    monkeypatch.setattr(G, "dk_source", lambda conn_fn: Src(lambda t: (16, 24) if t >= 40 else (16, 17)))
    payload = quote_payload(-100000, 99999, home="New York Giants", away="Washington Commanders")
    rc, writes, notes, evals, feed = _run_loop(monkeypatch, script(), payload)
    assert [t for e, t in evals if e == "E1"] == [40.0]
    assert len(writes) == 1 and writes[0]["pick_label"] == "TB ML (live)"
