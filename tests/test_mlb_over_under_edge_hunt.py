"""MLB totals edge hunt: grading, I24 identity, ship bar.

Measure-only. These tests pin the math the 2026-09-19 tables were
taken at — over/under vs the posted total, the n≥40 / 2-green-month /
max-4-per-day clear bar that refused the #757 +1.2%/42 peak, and that
I24 env defaults are unchanged.
"""
from __future__ import annotations

from pathlib import Path

import config
from scripts.mlb_over_under_edge_hunt import (
    american_units,
    attach_steam,
    fade_over_tickets,
    fade_under_tickets,
    grade_total,
    is_i24_row,
    juice_band,
    overlay_public_steam,
    rlm_fade_over,
    summarize,
    top_k,
)


def test_over_wins_only_when_runs_clear_the_total():
    result, _ = grade_total("over", 8.5, hs=5, aws=4)
    assert result == "WIN"
    result, _ = grade_total("over", 8.5, hs=5, aws=3)
    assert result == "LOSS"
    result, _ = grade_total("under", 8.5, hs=5, aws=3)
    assert result == "WIN"
    result, _ = grade_total("under", 8.5, hs=5, aws=4)
    assert result == "LOSS"


def test_push_is_exact_total_not_missing_score():
    result, units = grade_total("under", 8.5, hs=4, aws=4.5)
    assert result == "PUSH"
    assert units == 0.0
    result, units = grade_total("under", 8.5, hs=None, aws=4)
    assert result is None
    assert units is None


def test_flat_unit_minus_110_is_one_over_one_one():
    assert american_units(-110, True) == 100.0 / 110.0
    assert american_units(-110, False) == -1.0
    assert american_units(150, True) == 1.5


def test_plus_one_point_two_percent_peak_does_not_clear():
    """Jun+Jul green and Sep red is not month-stable even at n=42."""
    rows = (
        [{"game_date": "2026-06-15", "result": "WIN", "units": 0.91}] * 13
        + [{"game_date": "2026-06-16", "result": "LOSS", "units": -1.0}] * 10
        + [{"game_date": "2026-07-03", "result": "WIN", "units": 0.91}] * 7
        + [{"game_date": "2026-07-04", "result": "LOSS", "units": -1.0}] * 6
        + [{"game_date": "2026-09-16", "result": "LOSS", "units": -1.0}] * 4
        + [{"game_date": "2026-09-17", "result": "WIN", "units": 0.91}] * 2
    )
    s = summarize(rows)
    assert s["n"] == 42
    assert s["green_months"] == 2
    assert s["red_months"] == 1
    assert s["months"]["2026-09"]["roi"] < 0
    assert s["roi"] > 0
    assert s["clears"] is False


def test_a_true_clear_needs_n_two_green_months_and_no_red_month():
    rows = []
    for day, n_win, n_loss in (
        ("2026-06-10", 12, 8),
        ("2026-07-10", 12, 8),
        ("2026-09-16", 8, 4),
    ):
        rows.extend(
            [{"game_date": day, "result": "WIN", "units": 0.91}] * n_win
        )
        rows.extend(
            [{"game_date": day, "result": "LOSS", "units": -1.0}] * n_loss
        )
    s = summarize(rows)
    assert s["n"] == 52
    assert s["max_per_day"] == 20
    assert s["clears"] is False
    per_month = {}
    spread = []
    for r in rows:
        m = r["game_date"][:7]
        per_month[m] = per_month.get(m, 0) + 1
        spread.append({**r, "game_date": f"{m}-{per_month[m]:02d}"})
    s2 = summarize(spread)
    assert s2["n"] == 52
    assert s2["green_months"] == 3
    assert s2["max_per_day"] <= 4
    assert s2["roi"] > 0
    assert s2["clears"] is True


def _board(**kw):
    base = {
        "game_id": "MLB_2026-06-15_AAA_BBB",
        "game_date": "2026-06-15",
        "hs": 3, "aws": 4, "line": 8.5,
        "over_tix": 85.0, "under_tix": 15.0,
        "over_money": 70.0, "under_money": 30.0,
        "over_rlm": -15.0,
        "under_book": "draftkings", "under_price": -105.0,
        "over_book": "draftkings", "over_price": -115.0,
        "public_side": "over", "public_tix": 85.0,
        "move_over_pp": None,
        "pin_fair_over": None, "pin_gap_s": None,
    }
    base.update(kw)
    return base


def test_fade_over_bets_under_and_grades_the_total():
    rows = fade_over_tickets([_board()], cut=80.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "under"
    assert rows[0]["result"] == "WIN"  # 7 < 8.5
    assert is_i24_row(rows[0]) is True


def test_i24_row_rejects_heavy_juice_and_plus_money():
    heavy = fade_over_tickets([_board(under_price=-120.0)], cut=80.0)[0]
    plus = fade_over_tickets([_board(under_price=105.0)], cut=80.0)[0]
    light = fade_over_tickets([_board(over_tix=75.0, under_tix=25.0)], cut=70.0)[0]
    assert is_i24_row(heavy) is False
    assert is_i24_row(plus) is False
    assert is_i24_row(light) is False
    even = fade_over_tickets([_board(under_price=100.0)], cut=80.0)[0]
    assert is_i24_row(even) is True  # +100 == −100 implied


def test_fade_under_bets_over():
    b = _board(over_tix=40.0, under_tix=60.0, hs=6, aws=4)
    rows = fade_under_tickets([b], cut=55.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "over"
    assert rows[0]["result"] == "WIN"  # 10 > 8.5


def test_rlm_fade_over_requires_money_behind_tickets():
    behind = rlm_fade_over([_board(over_tix=85.0, over_rlm=-12.0)],
                           tix_cut=80.0, rlm_max=-10.0)
    ahead = rlm_fade_over([_board(over_tix=85.0, over_rlm=5.0)],
                          tix_cut=80.0, rlm_max=-10.0)
    assert len(behind) == 1 and behind[0]["side"] == "under"
    assert ahead == []


def test_overlay_oppose_fades_public_when_steam_leaves_over():
    b = _board(move_over_pp=-2.5)
    fade = overlay_public_steam(
        [b], tix_cut=80, pp_cut=2.0, mode="oppose", follow_steam=False)
    follow = overlay_public_steam(
        [b], tix_cut=80, pp_cut=2.0, mode="oppose", follow_steam=True)
    assert len(fade) == 1 and fade[0]["side"] == "under"
    assert len(follow) == 1 and follow[0]["side"] == "under"
    agree = overlay_public_steam(
        [b], tix_cut=80, pp_cut=2.0, mode="agree", follow_steam=False)
    assert agree == []


def test_attach_steam_copies_equal_line_move_by_game_id():
    b = _board()
    attach_steam([b], [{"game_id": b["game_id"], "move_over_pp": 2.4,
                        "total_move": 0.5}])
    assert b["move_over_pp"] == 2.4
    assert b["total_move"] == 0.5


def test_juice_band_and_top_k_are_composable():
    rows = [
        {**fade_over_tickets([_board(game_id="G1", over_tix=95.0,
                                     game_date="2026-06-15")], cut=80)[0]},
        {**fade_over_tickets([_board(game_id="G2", over_tix=82.0,
                                     under_price=-120.0,
                                     game_date="2026-06-15")], cut=80)[0]},
        {**fade_over_tickets([_board(game_id="G3", over_tix=90.0,
                                     game_date="2026-06-16")], cut=80)[0]},
    ]
    kept = juice_band(top_k(rows, 2, lambda r: r["fade_tix"]), -110, -100)
    assert {r["game_id"] for r in kept} == {"G1", "G3"}


def test_hunt_does_not_unpause_or_publish_or_weaken_i24():
    src = Path("scripts/mlb_over_under_edge_hunt.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" not in src
    assert "PUBLISH=1" not in src
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS
    assert config.MLB_TOTAL_MARKET_PUBLISH is False
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    # I24 plumbing stays where the totals card left it (env, not a silent recut).
    assert config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT == 70
    assert config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE == 0
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN is None
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX is None
    fade_src = Path("models/mlb_total_public_fade.py").read_text(encoding="utf-8")
    assert "UNDER_ODDS_MIN" in fade_src
    assert "MAX_PER_SLATE" in fade_src
