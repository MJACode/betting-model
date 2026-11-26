"""nba_prop_market_early: nba_prop_market's rule decided 10 hours before tip, a paper test
(mike, 2026-11-26; scripts/nba_prop_market_early_card.py).

What these pin: the live rule's window is untouched (a game 10 hours out is still too early for
it); the paper card decides that same game inside its own 9.5-10.5 hour window; only the three
markets graded at 10 hours are priced; the EV gate and the odds floor are read under the paper
id; and every row the card builds carries the paper id and the pause marker, so nothing posts it.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import config
import models.nba_prop_market as mk
import scripts.nba_prop_market_card as rule_card
import scripts.nba_prop_market_early_card as early

TIP = datetime(2026, 12, 2, 0, 0, tzinfo=timezone.utc)
NOW = TIP - timedelta(minutes=600)
FETCH = (NOW - timedelta(minutes=3)).isoformat()
GID = "NBA_2026-12-01_GSW_LAL"
GAMES = {GID: {"home": "LAL", "away": "GSW", "game_date": "2026-12-01", "season": 2027, "tip": TIP}}
ROSTER = mk.Roster([("201939", "Stephen Curry", "GSW"), ("2544", "LeBron James", "LAL")])


def q(book, over, under, line=24.5, player="Stephen Curry", market="player_points"):
    return {"game_id": GID, "player": player, "market": market, "book": book, "line": line,
            "over_price": over, "under_price": under, "over_link": f"{book}-o",
            "under_link": f"{book}-u", "snapshot_at": FETCH, "book_last_update": FETCH,
            "snapshot_type": "open"}


QUOTES = [q("pinnacle", -115, -105), q("fanduel", -125, +105),
          q("pinnacle", -115, -105, line=7.5, market="player_assists"),
          q("fanduel", -125, +105, line=7.5, market="player_assists")]


def test_the_live_rule_still_waits_for_its_own_window():
    bets, diag, decisions = mk.find_bets(QUOTES, GAMES, ROSTER, NOW)
    assert bets == [] and decisions == [] and diag["too_early"] == 1


def test_the_paper_card_decides_the_game_ten_hours_out_on_its_three_markets():
    bets, diag, decisions = mk.find_bets(QUOTES, GAMES, ROSTER, NOW, window=early.WINDOW_MIN,
                                         model_id=early.MODEL_ID, markets=early.MARKETS)
    assert len(decisions) == 1 and decisions[0].game_id == GID
    assert [(b.market, b.book, b.price) for b in bets] == [("player_points", "fanduel", 105.0)]


def test_the_ev_gate_and_the_floor_are_read_under_the_paper_id(monkeypatch):
    import models.honest_ev as he
    seen = []
    real = he.gate

    def spy(model_id, prob, odds):
        seen.append(model_id)
        return real(model_id, prob, odds)
    monkeypatch.setattr(he, "gate", spy)
    mk.find_bets(QUOTES, GAMES, ROSTER, NOW, window=early.WINDOW_MIN,
                 model_id=early.MODEL_ID, markets=early.MARKETS)
    assert seen and set(seen) == {early.MODEL_ID}


def test_its_rows_carry_its_id_and_the_pause_marker():
    bets, _, _ = mk.find_bets(QUOTES, GAMES, ROSTER, NOW, window=early.WINDOW_MIN,
                              model_id=early.MODEL_ID, markets=early.MARKETS)
    rows = rule_card.pick_rows(bets, 1000.0, model_id=early.MODEL_ID)
    assert [r["model_id"] for r in rows] == [early.MODEL_ID]
    assert rows[0]["downgrade_reason"] == config.PAUSED_NOTE
    assert rows[0]["pick_label"] == "Stephen Curry Under 24.5 Pts"


def test_it_is_registered_paused_on_its_own_number_and_settles_like_the_rule():
    from tracking import clv_close, paper_tracker as pt
    assert early.MODEL_ID in config.PAUSED_MODELS
    assert early.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.min_odds_for(early.MODEL_ID) == config.min_odds_for(mk.MODEL_ID)
    assert config.min_ev_for(early.MODEL_ID) == config.min_ev_for(mk.MODEL_ID)
    assert pt._PROP_MARKET_STAT_BY_MODEL[early.MODEL_ID] is pt._PROP_MARKET_STAT_BY_MODEL[mk.MODEL_ID]
    assert early.MODEL_ID in clv_close._ROW_MARKET_MODELS
