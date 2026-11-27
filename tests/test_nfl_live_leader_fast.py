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


# ─── best line: another book's own page on the fast path (issue #1652) ───────
#
# mike, 2026-11-26/27: "We want best line". Pinned: a better moneyline on the
# leader's side at another book's own page takes the bet, with DraftKings'
# own price kept as the reference; a worse one leaves DraftKings' bet as it
# was; a number set before the last score, a young one and an unconfirmed one
# never count; a failed read leaves the loop DraftKings only.

class Books:
    def __init__(self, away=-115.0, home=400.0, held=True, shown_ago=30.0, stamp_ago=32.0, fail=False):
        self.away, self.home, self.held = away, home, held
        self.shown_ago, self.stamp_ago, self.fail = shown_ago, stamp_ago, fail
        self.calls = 0

    def quotes(self, game_ids, at, markets=("h2h",)):
        self.calls += 1
        if self.fail:
            raise RuntimeError("book_live_reads unreachable")
        from models import book_live_quotes as OB
        now = pd.Timestamp.now(tz="UTC")
        return pd.DataFrame([{"game_id": CTX.game_id, "market": "h2h", "book": "fanduel",
                              "stamp": now - pd.Timedelta(seconds=self.stamp_ago),
                              "shown": now - pd.Timedelta(seconds=self.shown_ago), "held": self.held,
                              "spread_home": float("nan"), "home_price": self.home, "away_price": self.away,
                              "total_line": float("nan"), "over_price": float("nan"),
                              "under_price": float("nan")}], columns=OB.QUOTE_COLS)


def run_with_books(monkeypatch, books):
    monkeypatch.setattr(G, "dk_source", lambda conn_fn: Src(lambda t: (16, 24)))
    monkeypatch.setattr(G, "book_source", lambda conn_fn: books)
    payload = quote_payload(-100000, 99999, home="New York Giants", away="Washington Commanders")
    return _run_loop(monkeypatch, script(), payload)


def test_a_better_moneyline_on_another_books_own_page_takes_the_bet(monkeypatch):
    rc, writes, notes, evals, feed = run_with_books(monkeypatch, Books(away=-115.0))
    assert rc == 0 and len(writes) == 1
    p = writes[0]
    assert p["pick_label"] == "TB ML (live)" and p["pick_side"] == "away"
    assert (p["decision_book"], p["decision_odds"], p["dk_odds"]) == ("fanduel", -115.0, -130.0)
    assert p["best_book"] == "fanduel" and p["decision_edge"] > p["edge"]


def test_a_worse_moneyline_elsewhere_leaves_draftkings_bet_as_it_was(monkeypatch):
    rc, writes, notes, evals, feed = run_with_books(monkeypatch, Books(away=-150.0))
    p = writes[0]
    assert p["dk_odds"] == -130.0 and p.get("decision_book") in (None, "draftkings")


def test_young_unconfirmed_or_unreadable_numbers_leave_it_draftkings(monkeypatch):
    for books in (Books(shown_ago=4.0, stamp_ago=6.0), Books(held=False), Books(fail=True)):
        rc, writes, notes, evals, feed = run_with_books(monkeypatch, books)
        assert len(writes) == 1 and writes[0].get("decision_book") in (None, "draftkings"), books.__dict__


def test_a_number_set_before_the_last_score_we_saw_is_never_counted():
    now = pd.Timestamp("2026-10-09T02:00:00Z")
    q = pd.DataFrame([{"game_id": CTX.game_id, "market": "h2h", "book": "fanduel",
                       "stamp": now - pd.Timedelta(seconds=40), "shown": now - pd.Timedelta(seconds=30),
                       "held": True, "home_price": 400.0, "away_price": -115.0}])
    score_at = (now - pd.Timedelta(seconds=35)).to_pydatetime()
    assert G.other_book_prices(q, CTX, score_at, now, books=("fanduel",)) == {}
    later = (now - pd.Timedelta(seconds=45)).to_pydatetime()
    assert G.other_book_prices(q, CTX, later, now, books=("fanduel",)) == {"fanduel": (400.0, -115.0)}
    assert G.other_book_prices(q, CTX, later, now, books=("betrivers",)) == {}     # a book a pick may not name
