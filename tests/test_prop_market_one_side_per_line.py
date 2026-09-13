"""One side of one line. The market-relative prop cards never bet both.

THE BUG (2026-09-13, mike: "You posted tj hockenson twice over and under 3.5
rec??? ... why did you contradict yourself"). nfl_prop_market wrote

    T.J. Hockenson Over 3.5 Rec (FD)    edge 0.067   (over floor 0.06)
    T.J. Hockenson Under 3.5 Rec (MGM)  edge 0.050   (under floor 0.05)

in the same run, on the same line. Two different soft books were each cheap on
opposite sides against the sharp references, both cleared their floor, and
`best_per_prop` collapsed books but keyed on SIDE, so both survived. The
insert-once lock in `publish` also keyed on side, so even a correct card on a
later tick could have added the other half of a line already bet.

A bet on both sides of one line is not two opinions; it is a guaranteed hold
paid to two books. Measured over 2023-25 on the shipped rule (under 5pp / over
6pp, either reference): 75 of 2,273 propositions were bet on both sides.
Keeping one side per line moves the record from 2,348 bets / +183.5u / +7.81%
to 2,273 bets / +180.4u / +7.94% -- inside the noise, and every season's CI
unchanged in sign.

These tests FAILED on the code they were written against.
"""
from __future__ import annotations

from models.nfl_prop_market import MarketBet, best_per_prop

GID = "NFL_2026_01_GB_MIN"


def _hockenson():
    return [
        MarketBet(GID, "tjhockenson", "player_receptions", "over", "fanduel",
                  3.5, 116.0, 0.50, 0.0670, 100.0),
        MarketBet(GID, "tjhockenson", "player_receptions", "under", "betmgm",
                  3.5, -140.0, 0.5947, 0.0501, -130.0),
    ]


def test_opposite_sides_of_one_line_collapse_to_the_bigger_edge():
    out = best_per_prop(_hockenson())
    assert [(b.side, b.book) for b in out] == [("over", "fanduel")]


def test_input_order_does_not_decide_the_side():
    assert [b.side for b in best_per_prop(list(reversed(_hockenson())))] == ["over"]


def test_a_different_market_on_the_same_player_is_still_its_own_bet():
    """The fix is one side per LINE, not one bet per player -- that broader cap
    costs 32.9u over 2023-25 on this rule and is not what shipped."""
    bets = _hockenson() + [
        MarketBet(GID, "tjhockenson", "player_reception_yds", "under", "fanduel",
                  32.5, -110.0, 0.58, 0.06, -120.0)]
    assert {b.market for b in best_per_prop(bets)} == {
        "player_receptions", "player_reception_yds"}


class _Conn:
    """Holds standing picks and answers the lock query by its own params, so the
    test sees exactly what the SQL asks and not what the fake assumes."""

    def __init__(self, standing):
        self.standing = standing          # list of dicts
        self.inserted = []

    def execute(self, sql, params=None):
        up = sql.strip().upper()
        conn = self

        class R:
            def __init__(self, one=None, all_=None):
                self._one, self._all = one, all_ or []
            def fetchone(self): return self._one
            def fetchall(self): return self._all

        if up.startswith("SELECT GAME_ID FROM GAMES"):
            return R(all_=[(g,) for g in params[0]])
        if up.startswith("SELECT"):
            cols = ["game_id", "model_id", "player_key", "prop_market"]
            if "PICK_SIDE" in up:
                cols.append("pick_side")
            hit = any(all(p.get(c) == v for c, v in zip(cols, params))
                      for p in conn.standing + conn.inserted)
            return R(one=(1,) if hit else None)
        conn.inserted.append(dict(params))
        return R()

    def commit(self):
        pass


def test_nfl_publish_will_not_add_the_other_side_of_a_locked_line():
    import scripts.nfl_prop_market_card as card
    games = {GID: {"date": "2026-09-13", "kickoff": "2026-09-13T20:25:00Z",
                   "home": "MIN", "away": "GB"}}
    over, under = _hockenson()
    standing = card.pick_rows([over], games, {}, 1000.0)
    conn = _Conn(standing)
    assert card.publish(conn, card.pick_rows([under], games, {}, 1000.0)) == 0
    assert conn.inserted == []


def test_wnba_publish_will_not_add_the_other_side_of_a_locked_line():
    import scripts.wnba_prop_market_card as card
    base = {"game_id": "WNBA_X", "model_id": "wnba_prop_market",
            "player_key": "aja wilson", "prop_market": "player_points"}
    conn = _Conn([{**base, "pick_side": "over"}])
    assert card.publish(conn, [{**base, "pick_side": "under"}]) == 0
    assert conn.inserted == []
