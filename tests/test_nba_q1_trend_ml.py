"""nba_q1_trend_ml (models/nba_q1_trend_ml.py): the spread model's rule decides the game and the side, the bet is
that team's first-quarter moneyline at the best offer, a level first quarter is a push, the label says First Quarter,
the probability's uplift leaves pushes out, and the one first-quarter call stores both markets.

The replay that reproduces all 87 graded bets through decide() reads the research cache, so it is a script
(scripts/nba_q1_trend_ml_replay.py), not a test; its result is in docs/sports/nba.md."""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pandas as pd
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_q1_trend_ml as ml  # noqa: E402
from tests.test_nba_q1_trend import (COLD_AWAY, HOT_HOME, T, TIMES, TIP, _history, _quotes,  # noqa: E402
                                     _target)

GAME = "NBA_2026-11-19_LAC_DEN"


@pytest.fixture(scope="module")
def art():
    return ml.load_artifact()


def _ml_quotes(rows):
    """rows: (book, home price, away price) at T, the first-quarter moneyline."""
    out = []
    for book, ph, pa in rows:
        out.append({"game_id": GAME, "season": 2027, "game_date": "2026-11-19", "tip": TIP, "market": ml.MARKET,
                    "book": book, "snapshot_at": T, "fetch_at": T, "line": float("nan"), "price_a": float(ph),
                    "price_b": float(pa), "coherent": True, "link_a": f"{book}-home", "link_b": f"{book}-away",
                    "book_update_at": T})
    return pd.DataFrame(out)


SPREADS = [("pinnacle", -1.5, -110, -110), ("draftkings", -1.5, -115, -105), ("fanduel", -1.5, -105, -115)]


def test_a_step_game_bets_the_hot_teams_moneyline_at_the_best_offer(art):
    hist = _history(HOT_HOME, COLD_AWAY)
    q = pd.concat([_quotes(SPREADS), _ml_quotes([("pinnacle", -150, 125), ("draftkings", -160, 130),
                                                 ("fanduel", -140, 115), ("betmgm", -155, 120)])],
                  ignore_index=True)
    bets, decisions, diag = ml.decide(_target(), q, hist, TIMES, art)
    assert diag["bets"] == 1, (diag, [d.detail for d in decisions])
    b = bets[0]
    assert b.side == "home" and b.book == "fanduel" and b.price == -140
    assert b.dk_price == -160 and b.link == "fanduel-home"
    assert b.number == -1.5                                   # the signal still reads the SPREAD number
    assert b.p_model == pytest.approx(b.p_fair + ml.uplift(art, 2027))
    d = decisions[0]
    assert d.line is None and d.price == -140 and d.pick == "home"


def test_no_spread_is_no_decision_however_good_the_moneyline(art):
    """The rule's number is the first-quarter spread: a moneyline alone decides nothing."""
    hist = _history(HOT_HOME, COLD_AWAY)
    q = _ml_quotes([("pinnacle", -150, 125), ("fanduel", -140, 115)])
    bets, decisions, diag = ml.decide(_target(), q, hist, TIMES, art)
    assert not bets and diag["no_number"] == 1


def test_a_price_under_the_floor_is_no_offer(art):
    hist = _history(HOT_HOME, COLD_AWAY)
    q = pd.concat([_quotes(SPREADS), _ml_quotes([("pinnacle", -230, 190), ("fanduel", -210, 175)])],
                  ignore_index=True)
    bets, decisions, diag = ml.decide(_target(), q, hist, TIMES, art)
    assert not bets and diag["no_offer"] == 1 and decisions[0].detail.startswith("no_offer")


def test_the_uplift_leaves_pushes_out():
    """The harness's moneyline probability is conditional on no tie, so a push is in neither part: 3 wins of 4
    decided bets at a fair 0.5 each is +0.25, whatever the two pushes."""
    art = {"bucket": {2026: {"n": 6, "wins": 3, "pushes": 2, "decided": 4, "sum_p_win_decided": 2.0}}}
    assert ml.uplift(art, 2027) == pytest.approx(0.25)


def test_a_level_first_quarter_is_a_push_and_the_winner_settles():
    from tracking.paper_tracker import _compute_result, _market_for_pick
    assert _market_for_pick(ml.MODEL_ID) == "h2h_q1"
    level = _compute_result("home", "h2h_q1", 28, 28, None, None, None, 120, None, None, 1.0)
    home = _compute_result("home", "h2h_q1", 30, 27, None, None, None, 120, None, None, 1.0)
    away = _compute_result("away", "h2h_q1", 30, 27, None, None, None, 120, None, None, 1.0)
    assert level[0] == "PUSH" and home[0] == "WIN" and away[0] == "LOSS"
    assert home[1] > 0


def test_the_label_says_first_quarter_and_the_check_refuses_one_that_does_not():
    from models.scorer import _build_pick_label
    from tracking.pick_integrity import pick_problems
    away = _build_pick_label("away", "LAC", "DEN", "h2h_q1", None)
    assert away == "DEN @ LAC — First Quarter DEN ML"
    assert pick_problems(away, "away", None, ml.MODEL_ID, "LAC", "DEN") == []
    assert pick_problems("DEN ML", "away", None, ml.MODEL_ID, "LAC", "DEN")                  # reads as the game's
    assert pick_problems("DEN @ LAC — First Quarter LAC ML", "away", None, ml.MODEL_ID, "LAC", "DEN")  # wrong team


def test_one_call_stores_both_markets_and_the_moneyline_skips_the_rung_splitter():
    from data.ingestors.nba_first_quarter_odds import API_MARKETS, event_rows
    assert API_MARKETS == ("spreads_q1", "h2h_q1")
    body = {"home_team": "Los Angeles Clippers", "away_team": "Denver Nuggets", "bookmakers": [
        {"key": "fanduel", "markets": [
            {"key": "spreads_q1", "last_update": "2026-11-20T23:14:00Z", "outcomes": [
                {"name": "Los Angeles Clippers", "point": -1.5, "price": -110},
                {"name": "Denver Nuggets", "point": 1.5, "price": -110}]},
            {"key": "h2h_q1", "last_update": "2026-11-20T23:14:30Z", "outcomes": [
                {"name": "Los Angeles Clippers", "price": -150},
                {"name": "Denver Nuggets", "price": 125}]}]},
        # a book with the moneyline and no spread still stores its moneyline
        {"key": "fanatics", "markets": [
            {"key": "h2h_q1", "last_update": "2026-11-20T23:13:00Z", "outcomes": [
                {"name": "Denver Nuggets", "price": 130}, {"name": "Los Angeles Clippers", "price": -160}]}]}]}
    main, alt, ages = event_rows(body, "NBA_2026-11-20_DEN_LAC", "open",
                                 datetime(2026, 11, 20, 23, 15, tzinfo=timezone.utc))
    by = {(r["bookmaker"], r["market"]): r for r in main}
    assert set(by) == {("fanduel", "spreads_q1"), ("fanduel", "h2h_q1"), ("fanatics", "h2h_q1")}
    assert by[("fanduel", "spreads_q1")]["spread_home"] == -1.5
    m = by[("fanatics", "h2h_q1")]
    assert m["home_price"] == -160 and m["away_price"] == 130 and m["spread_home"] is None
    assert m["snapshot_at"] == "2026-11-20T23:13:00Z" and not alt
    assert ages == {"fanduel": 1.0, "fanatics": 2.0}


def test_the_pick_row_has_no_number_and_says_first_quarter():
    from scripts.nba_q1_trend_ml_card import pick_rows
    b = ml.Q1MLBet(game_id=GAME, season=2027, side="home", price=-140.0, book="fanduel", k=4.0, number=-1.5,
                   p_fair=0.56, uplift=0.14, p_model=0.70, fair_ref="pinnacle", fetch_at=T, dk_price=-160.0,
                   link="fanduel-home", dk_link="dk-home")
    games = {GAME: {"home": "DEN", "away": "LAC", "game_date": "2026-11-19", "tip": TIP}}
    rows, refused = pick_rows([b], games, 1000.0)
    assert not refused and len(rows) == 1
    r = rows[0]
    assert r["pick_label"] == "LAC @ DEN — First Quarter DEN ML"
    assert r["scored_line"] is None and r["model_id"] == ml.MODEL_ID and r["pick_side"] == "home"
    assert r["decision_book"] == "fanduel" and r["decision_odds"] == -140.0 and r["dk_odds"] == -160.0


class _Conn:
    """Answers the window plan's reads: which games each model decided and which hold a BET."""

    def __init__(self, spread_done=(), ml_done=()):
        self.spread_done, self.ml_done = set(spread_done), set(ml_done)

    def execute(self, sql, params=()):
        class R:
            def __init__(self, rows):
                self.rows = rows

            def fetchall(self):
                return self.rows

            def fetchone(self):
                return self.rows[0] if self.rows else None
        if "information_schema.tables" in sql:
            return R([(1,)])
        ids = list(params[0]) if params and isinstance(params[0], list) else list(params[-1])
        if "nba_q1_trend_ml_decisions" in sql:
            return R([(g,) for g in ids if g in self.ml_done])
        if "nba_q1_trend_decisions" in sql:
            return R([(g,) for g in ids if g in self.spread_done])
        return R([])


def test_a_game_the_spread_decided_is_still_fetched_until_the_moneyline_has():
    import scripts.nba_q1_trend_window as w
    now = TIP - pd.Timedelta(minutes=50)
    games = {GAME: {"tip": TIP.to_pydatetime(), "home": "DEN", "away": "LAC"}}
    assert w.plan(_Conn(spread_done={GAME}), now.to_pydatetime(), games=games).decide == [GAME]
    assert w.plan(_Conn(spread_done={GAME}, ml_done={GAME}), now.to_pydatetime(), games=games).decide == []
