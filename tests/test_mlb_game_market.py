"""MLB game-line market rule: Pinnacle vs bettable soft books, equal lines.

The 1.8pp cut is measured in docs/mlb_runline_ou_edge_search.md. These tests
pin the traps that would manufacture a fake edge: mismatched lines, a 6-hour
quote gap, Bovada as a "soft" book, two bets on the same game, a totals path
that publishes under the wall default.
"""
from __future__ import annotations

import config
import models.mlb_game_market as mk
from tracking.pick_integrity import pick_problems


def _q(gid, book, spread, home, away, snap="2026-09-15T16:00:00Z", **extra):
    row = {
        "game_id": gid, "book": book,
        "spread_home": spread, "home_price": home, "away_price": away,
        "snapshot_at": snap,
        "home_link": None, "away_link": None,
    }
    row.update(extra)
    return (gid, book), row


def _quotes(*pairs):
    return dict(pairs)


PIN = _q("G1", "pinnacle", -1.5, -150, 130)
# FanDuel lays the same −1.5 at a worse number than Pinnacle's de-vig —
# home is the cheap side at FD relative to PIN.
FD = _q("G1", "fanduel", -1.5, -120, 100)


def test_soft_books_are_exactly_the_bettable_set():
    assert mk.SHARP_BOOK == "pinnacle"
    assert mk.SHARP_BOOK not in mk.SOFT_BOOKS
    assert "bovada" not in mk.SOFT_BOOKS
    assert "espnbet" not in mk.SOFT_BOOKS
    missing = [b for b in mk.SOFT_BOOKS if b not in config.BEST_LINE_BOOKMAKERS]
    assert not missing, missing
    assert "draftkings" in mk.SOFT_BOOKS
    assert "fanduel" in mk.SOFT_BOOKS


def test_equal_lines_only():
    quotes = _quotes(
        PIN,
        _q("G1", "fanduel", -2.5, -110, -110),
    )
    bets, diag = mk.find_spread_bets(quotes, min_edge=0.01,
                                     soft_books=("fanduel",))
    assert bets == []
    assert diag["line_mismatch"] >= 1


def test_a_six_hour_gap_is_not_a_disagreement():
    quotes = _quotes(
        PIN,
        _q("G1", "fanduel", -1.5, -120, 100, snap="2026-09-15T22:00:00Z"),
    )
    bets, diag = mk.find_spread_bets(quotes, min_edge=0.01,
                                     soft_books=("fanduel",))
    assert bets == []
    assert diag["not_simultaneous"] >= 1


def test_one_bet_per_game_keeps_the_largest_edge():
    quotes = _quotes(
        PIN,
        FD,
        _q("G1", "betmgm", -1.5, -105, -115),
    )
    bets, diag = mk.find_spread_bets(
        quotes, min_edge=0.01, soft_books=("fanduel", "betmgm"))
    assert len(bets) == 1
    assert bets[0].game_id == "G1"
    assert bets[0].book in ("fanduel", "betmgm")


def test_runline_filter_drops_alternate_numbers():
    quotes = _quotes(
        _q("G1", "pinnacle", -2.5, -150, 130),
        _q("G1", "fanduel", -2.5, -120, 100),
    )
    bets, _ = mk.find_spread_bets(quotes, min_edge=0.01,
                                  soft_books=("fanduel",))
    assert bets == []
    bets, _ = mk.find_spread_bets(quotes, min_edge=0.01,
                                  soft_books=("fanduel",),
                                  runline_only=False)
    assert len(bets) == 1


def test_the_measured_cut_is_eighteen_tenths():
    assert mk.MIN_EDGE_SPREADS == 0.018
    assert config.ACTION_THRESHOLDS["mlb_spread_market"] == {
        "min_prob": 0.0, "min_edge": 0.018,
    }
    assert config.MODEL_EDGE_THRESHOLDS["mlb_spread_market"] == 0.018
    assert config.MODEL_PROB_THRESHOLDS["mlb_spread_market"] == 0.0
    assert config.scoring_method("mlb_spread_market") == "rule"
    assert "mlb_spread_market" not in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_spread_market" not in config.GAME_MARKET_GATE_MODELS


def test_totals_default_is_a_wall():
    """2026 totals are negative at every threshold. The default must not fire."""
    assert mk.MIN_EDGE_TOTALS >= 1.0
    quotes = {
        ("G1", "pinnacle"): {
            "total_line": 8.5, "over_price": -110, "under_price": -110,
            "snapshot_at": "2026-09-15T16:00:00Z",
        },
        ("G1", "fanduel"): {
            "total_line": 8.5, "over_price": -102, "under_price": -118,
            "snapshot_at": "2026-09-15T16:00:00Z",
        },
    }
    bets, _ = mk.find_total_bets(quotes, soft_books=("fanduel",))
    assert bets == []


def test_pick_label_agrees_with_the_home_number():
    from scripts.mlb_game_market_card import pick_rows
    from models.mlb_game_market import GameMarketBet

    bet = GameMarketBet(
        game_id="MLB_2026-09-15_NYY_BOS", market="spreads",
        side="away", book="fanduel", line=-1.5, price=100.0,
        fair=0.56, edge=0.03, sharp_price=130.0,
    )
    games = {"MLB_2026-09-15_NYY_BOS": {
        "home": "NYY", "away": "BOS", "game_date": "2026-09-15",
        "commence_time": "2026-09-15T23:00:00Z",
    }}
    rows = pick_rows([bet], games, {}, bankroll=10_000)
    assert len(rows) == 1
    r = rows[0]
    assert r["pick_label"].startswith("BOS +1.5")
    assert r["scored_line"] == -1.5
    assert r["pick_side"] == "away"
    assert r["decision_book"] == "fanduel"
    assert r["injury_flag"] is None
    problems = pick_problems(
        r["pick_label"], r["pick_side"], r["scored_line"],
        r["model_id"], "NYY", "BOS")
    assert problems == [], problems


def test_house_juice_floor_drops_a_minus_250():
    from scripts.mlb_game_market_card import pick_rows
    from models.mlb_game_market import GameMarketBet

    bet = GameMarketBet(
        game_id="G1", market="spreads", side="home", book="fanduel",
        line=-1.5, price=-250.0, fair=0.75, edge=0.04, sharp_price=-200.0,
    )
    games = {"G1": {"home": "NYY", "away": "BOS", "game_date": "2026-09-15",
                    "commence_time": "t"}}
    rows = pick_rows([bet], games, {}, bankroll=10_000)
    assert rows == []


def test_settlement_grades_spreads_not_h2h():
    """Without this map the generic settler falls to h2h and stamps NO_ACTION."""
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick("mlb_spread_market") == "spreads"
    fetched = {b.strip().lower()
               for b in config.ODDS_API_BOOKMAKERS_PARAM.split(",") if b.strip()}
    missing = [b for b in mk.SOFT_BOOKS if b not in fetched]
    assert not missing, missing
    assert mk.SHARP_BOOK in fetched
