"""I24 remesure helpers: tighten-only bar, implied vs numeric band.

The remesure (`scripts.mlb_total_public_fade_i24`) must call the fade
finder — not invent a shop — and must refuse a looser ticket, a wider
juice band, or a larger K than the live I24 card. These tests pin that
bar. They do not flip PUBLISH and do not unpause mlb_over_under /
mlb_runline.
"""
from __future__ import annotations

import config
import models.mlb_total_public_fade as fade
from models.market_relative import implied
from scripts.mlb_total_public_fade_i24 import (
    LIVE_K,
    LIVE_ODDS_MAX,
    LIVE_ODDS_MIN,
    LIVE_TICKET,
    apply_live_card,
    build_finder_candidates,
    cell_clears,
    is_tighter,
    numeric_band,
)
from scripts.mlb_total_public_fade_topk import american_units


def test_publish_default_and_paused_xgboost_untouched():
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN is None
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX is None
    assert int(config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE) == 0
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS


def test_live_guards_are_the_documented_i24_cell():
    assert LIVE_TICKET == 80.0
    assert LIVE_ODDS_MIN == -110.0
    assert LIVE_ODDS_MAX == -100.0
    assert LIVE_K == 2
    assert implied(100) == implied(-100)


def test_is_tighter_refuses_anything_looser_than_live():
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-100, k=2, conc_min=4) is False
    assert is_tighter(ticket=70, odds_min=-110, odds_max=-100, k=2, conc_min=4) is False
    assert is_tighter(ticket=80, odds_min=-115, odds_max=-100, k=2, conc_min=4) is False
    assert is_tighter(ticket=80, odds_min=-110, odds_max=100, k=2, conc_min=4) is False
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-100, k=3, conc_min=4) is False
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-100, k=0, conc_min=4) is False


def test_is_tighter_accepts_higher_ticket_narrower_band_or_smaller_k():
    assert is_tighter(ticket=85, odds_min=-110, odds_max=-100, k=2, conc_min=4) is True
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-105, k=2, conc_min=4) is True
    assert is_tighter(ticket=80, odds_min=-108, odds_max=-100, k=2, conc_min=4) is True
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-100, k=1, conc_min=4) is True
    assert is_tighter(ticket=80, odds_min=-110, odds_max=-100, k=2, conc_min=2) is True


def test_numeric_band_drops_plus_100_implied_keeps_it():
    """The +9.51u claim and the shop-replay disagree on +100.

    Finder band is implied-space (+100 == −100). A numeric
    −110 ≤ price ≤ −100 drops the even-money plus post.
    """
    rows = [
        {"price": -110.0, "game_id": "a"},
        {"price": -105.0, "game_id": "b"},
        {"price": 100.0, "game_id": "c"},
        {"price": -115.0, "game_id": "d"},
    ]
    kept = numeric_band(rows, -110.0, -100.0)
    assert [r["game_id"] for r in kept] == ["a", "b"]
    assert fade.under_in_odds_band(100, -110.0, -100.0) is True
    assert fade.under_in_odds_band(-115, -110.0, -100.0) is False


def test_build_finder_candidates_uses_find_fade_bets_not_a_new_shop():
    """Same DK line, shopped under, I24 band — identical to find_fade_bets."""
    splits = [{
        "game_id": "G1", "over_tix": 90.0, "over_money": 80.0,
        "public_snap": "2026-06-15T16:00:00-04:00",
        "commence_time": "2026-06-15T23:10:00+00:00",
        "game_date": "2026-06-15", "hs": 3.0, "aws": 2.0,
    }]
    quotes = [
        {"game_id": "G1", "book": "draftkings", "line": 8.5,
         "under_price": -110.0, "over_price": -110.0},
        {"game_id": "G1", "book": "fanduel", "line": 8.5,
         "under_price": -102.0, "over_price": -118.0},
    ]
    rows, diag = build_finder_candidates(
        splits, quotes, min_over_tickets=80,
        under_odds_min=-110, under_odds_max=-100)
    assert diag["bets"] == 1
    assert len(rows) == 1
    assert rows[0]["book"] == "fanduel"
    assert rows[0]["price"] == -102.0
    assert rows[0]["result"] == "WIN"
    assert rows[0]["units"] == american_units(-102.0, True)

    # Shop picks the best in-band under. DK −110 would still flag if FD
    # is −120, so both books have to sit outside the band.
    rows_j, diag_j = build_finder_candidates(
        splits,
        [
            {**quotes[0], "under_price": -120.0},
            {**quotes[1], "under_price": -125.0},
        ],
        min_over_tickets=80,
        under_odds_min=-110, under_odds_max=-100)
    assert rows_j == []
    assert diag_j["odds_band"] == 1


def test_apply_live_card_caps_at_two_and_guard_is_noop():
    """After ticket top-2 the n≥4 suppress-all never fires."""
    rows = []
    for i, tix in enumerate((97, 95, 90, 88, 81)):
        rows.append({
            "game_id": f"G{i}", "game_date": "2026-06-15", "month": "2026-06",
            "bet": fade.PublicFadeBet(
                game_id=f"G{i}", book="draftkings", line=8.5,
                price=-110.0, over_ticket_pct=float(tix)),
            "result": "WIN", "units": 0.91, "over_tix": float(tix),
            "over_money": 80.0, "price": -110.0, "line": 8.5,
            "book": "draftkings", "implied": implied(-110), "has_over": True,
        })
    kept = apply_live_card(rows, k=2)
    assert [r["game_id"] for r in kept] == ["G0", "G1"]


def test_cell_clears_requires_n40_every_month_green_and_cap2():
    def _rows(n, month, units_each):
        out = []
        for i in range(n):
            out.append({
                "game_id": f"{month}-{i}", "game_date": f"{month}-0{1 + (i % 2)}",
                "month": month, "result": "WIN" if units_each > 0 else "LOSS",
                "units": units_each,
            })
        return out

    green = _rows(20, "2026-06", 0.2) + _rows(20, "2026-07", 0.1)
    # 20+20 = 40, two months +, but max/day = 20.
    from scripts.mlb_total_public_fade_i24 import summarize
    s = summarize(green)
    assert s["n"] == 40
    assert s["max_per_day"] > 2
    assert cell_clears(s, green) is False

    # Spread across 20 days so max/day=2, still n=40, both months +.
    thin = []
    for i in range(20):
        thin.append({"game_id": f"a{i}", "game_date": f"2026-06-{i+1:02d}",
                     "month": "2026-06", "result": "WIN", "units": 0.1})
        thin.append({"game_id": f"b{i}", "game_date": f"2026-07-{i+1:02d}",
                     "month": "2026-07", "result": "WIN", "units": 0.1})
    st = summarize(thin)
    assert st["n"] == 40 and st["max_per_day"] == 1
    assert cell_clears(st, thin) is True

    # July red → miss.
    red_jul = [r for r in thin if r["month"] == "2026-06"]
    for i in range(20):
        red_jul.append({
            "game_id": f"c{i}", "game_date": f"2026-07-{i+1:02d}",
            "month": "2026-07", "result": "LOSS", "units": -1.0,
        })
    assert cell_clears(summarize(red_jul), red_jul) is False
