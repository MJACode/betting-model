"""Ticket × juice grid helpers. Stdlib only — no dotenv / DATABASE_URL."""
from __future__ import annotations

from scripts.mlb_total_public_fade_grid import (
    attach_shop, cell_rows, grade_under, juice_allows, profit_units,
    shop_under, summarize,
)


def test_juice_floors_are_american_inclusive_and_plus_is_exclusive():
    assert juice_allows(-200, "any") is True
    assert juice_allows(-115, "ge_m115") is True
    assert juice_allows(-116, "ge_m115") is False
    assert juice_allows(-110, "ge_m110") is True
    assert juice_allows(-111, "ge_m110") is False
    assert juice_allows(100, "ge_m105") is True
    assert juice_allows(100, "plus") is True
    assert juice_allows(-105, "plus") is False


def test_shop_under_uses_dk_line_and_best_same_line_price():
    books = {
        "draftkings": {"total_line": 8.5, "under_price": -110},
        "fanduel": {"total_line": 8.5, "under_price": -102},
        "betmgm": {"total_line": 9.0, "under_price": 100},
    }
    assert shop_under(books, line=8.5) == ("fanduel", -102.0)


def test_grade_under_and_flat_units():
    assert grade_under(3, 4, 8.5) is True
    assert grade_under(5, 4, 8.5) is False
    assert grade_under(4, 4.5, 8.5) is None
    assert profit_units(-110, True) == 100.0 / 110.0
    assert profit_units(100, True) == 1.0
    assert profit_units(-110, False) == -1.0
    assert profit_units(-110, None) == 0.0


def test_slate_cap_ranks_by_tickets_then_price():
    cands = [
        {"game_id": "A", "game_date": "2026-09-16", "over_tix": 95,
         "price": -110, "won": True, "units": 0.91},
        {"game_id": "B", "game_date": "2026-09-16", "over_tix": 80,
         "price": 100, "won": True, "units": 1.0},
        {"game_id": "C", "game_date": "2026-09-16", "over_tix": 90,
         "price": -105, "won": False, "units": -1.0},
        {"game_id": "D", "game_date": "2026-09-16", "over_tix": 70,
         "price": -110, "won": True, "units": 0.91},
    ]
    keep = cell_rows(cands, ticket=70, juice="any", cap=2)
    assert {r["game_id"] for r in keep} == {"A", "C"}


def test_concentration_rejects_a_whole_slate_fade():
    rows = [
        {"game_id": f"G{i}", "game_date": "2026-09-19",
         "won": True, "units": 0.9}
        for i in range(12)
    ]
    s = summarize(rows, {"2026-09-19": 12})
    assert s["mean_conc"] == 1.0
    assert s["conc_reject"] is True


def test_attach_shop_requires_dk_and_main_total():
    games = [{
        "game_id": "G1", "game_date": "2026-06-08",
        "home_score": 3, "away_score": 4, "over_tix": 90, "over_money": 88,
    }]
    quotes = {("G1", "draftkings"): {"total_line": 8.5, "under_price": -110}}
    out = attach_shop(games, quotes)
    assert len(out) == 1
    assert out[0]["book"] == "draftkings"
    assert out[0]["won"] is True  # 7 < 8.5
    quotes_hi = {("G1", "draftkings"): {"total_line": 15.0, "under_price": -110}}
    assert attach_shop(games, quotes_hi) == []
