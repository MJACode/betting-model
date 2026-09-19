"""MLB totals edge hunt: grading, as-of garbage filter, ship bar.

Measure-only. These tests pin the math the 2026-09-19 tables were
taken at — over/under vs the posted total, the Action Network both-sides
~100 drop, and the n≥40 / 2-green-month / max-4-per-day clear bar
that refused runline's +1.2%/42 peak. I24 fade guards stay untouched.
"""
from __future__ import annotations

from pathlib import Path

import config
from scripts.mlb_over_under_edge_hunt import (
    _sane_split,
    american_units,
    attach_steam,
    fade_money_side,
    fade_public_side,
    grade_ou,
    is_main_total,
    overlay_public_steam,
    summarize,
)


def test_main_total_is_five_five_to_fourteen_five():
    assert is_main_total(8.5) is True
    assert is_main_total(5.5) is True
    assert is_main_total(14.5) is True
    assert is_main_total(5.0) is False
    assert is_main_total(15.0) is False
    assert is_main_total(None) is False


def test_over_eight_five_wins_only_when_total_is_nine_or_more():
    result, _ = grade_ou("over", 8.5, hs=5, aws=4)
    assert result == "WIN"
    result, _ = grade_ou("over", 8.5, hs=4, aws=4)
    assert result == "LOSS"
    result, _ = grade_ou("under", 8.5, hs=4, aws=4)
    assert result == "WIN"
    result, _ = grade_ou("under", 8.5, hs=5, aws=4)
    assert result == "LOSS"


def test_exact_total_is_a_push():
    result, units = grade_ou("over", 9.0, hs=5, aws=4)
    assert result == "PUSH"
    assert units == 0.0
    result, units = grade_ou("under", 9.0, hs=5, aws=4)
    assert result == "PUSH"


def test_missing_score_is_not_a_push():
    result, units = grade_ou("under", 8.5, hs=None, aws=4)
    assert result is None
    assert units is None


def test_july_first_both_sides_near_100_is_garbage():
    assert _sane_split(100.0, 99.0) is False
    assert _sane_split(56.0, 44.0) is True
    assert _sane_split(90.0, 10.0) is True
    assert _sane_split(80.0, 4.0) is False  # sum 84, off by more than 15


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
        "hs": 5, "aws": 2, "line": 8.5,
        "over_tix": 80.0, "under_tix": 20.0,
        "over_money": 70.0, "under_money": 30.0,
        "public_side": "over", "public_tix": 80.0,
        "over_book": "draftkings", "over_price": -110.0,
        "under_book": "draftkings", "under_price": -110.0,
        "over_rlm": -10.0, "under_rlm": 10.0,
        "move_over_pp": None,
    }
    base.update(kw)
    return base


def test_overlay_oppose_fades_public_when_steam_leaves_them():
    """Public over + steam under → fade over. Same side as follow-steam oppose."""
    b = _board(move_over_pp=-2.5)
    fade = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="oppose", follow_steam=False)
    follow = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="oppose", follow_steam=True)
    assert len(fade) == 1 and fade[0]["side"] == "under"
    assert len(follow) == 1 and follow[0]["side"] == "under"
    agree = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="agree", follow_steam=False)
    assert agree == []


def test_money_heavy_fades_the_money_pile_not_tickets():
    b = _board(over_tix=55.0, under_tix=45.0, over_money=80.0, under_money=20.0,
               public_side="over", public_tix=55.0)
    rows = fade_money_side([b], cut=70.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "under"


def test_fade_over_pile_bets_under():
    b = _board(over_tix=82.0, under_tix=18.0)
    rows = fade_public_side([b], side_key="over", cut=80.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "under"


def test_attach_steam_copies_move_pp_by_game_id():
    b = _board()
    attach_steam([b], [{"game_id": b["game_id"], "move_over_pp": 3.1}])
    assert b["move_over_pp"] == 3.1


def test_hunt_does_not_unpause_or_publish_or_touch_i24():
    src = Path("scripts/mlb_over_under_edge_hunt.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" not in src
    assert "PUBLISH=1" not in src
    # Public-board steam CLEAR is refused when the full DK month is red.
    assert "−118.50u / 197" in src or "-118.50u / 197" in src
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert config.MLB_TOTAL_MARKET_PUBLISH is False
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    # I24 totals guards stay where the totals card left them.
    assert config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT == 70
    assert config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE == 0
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN is None
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX is None
    fade_src = Path("models/mlb_total_public_fade.py").read_text(encoding="utf-8")
    assert "UNDER_ODDS_MIN" in fade_src
    assert "MAX_PER_SLATE" in fade_src
    config_src = Path("config.py").read_text(encoding="utf-8")
    assert "MLB_TOTAL_PUBLIC_FADE_TICKET_PCT" in config_src
