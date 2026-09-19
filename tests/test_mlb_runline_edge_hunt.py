"""MLB runline edge hunt: grading, as-of garbage filter, ship bar.

Measure-only. These tests pin the math the 2026-09-19 tables were
taken at — HOME scored_line (§4), the July-1 Action Network both-sides
~100 drop, and the n≥40 / 2-green-month / max-4-per-day clear bar
that refused the +1.2%/42 peak.
"""
from __future__ import annotations

from pathlib import Path

import config
from scripts.mlb_runline_edge_hunt import (
    _sane_split,
    american_units,
    attach_steam,
    fade_home_dog,
    fade_money_side,
    grade_rl,
    is_runline,
    overlay_public_steam,
    summarize,
)


def test_runline_is_plus_or_minus_one_and_a_half():
    assert is_runline(-1.5) is True
    assert is_runline(1.5) is True
    assert is_runline(-2.5) is False
    assert is_runline(None) is False


def test_home_minus_one_five_covers_only_a_two_run_win():
    """scored_line is the HOME number. Home −1.5 needs a 2-run win."""
    result, _ = grade_rl("home", -1.5, hs=3, aws=1)
    assert result == "WIN"
    result, _ = grade_rl("home", -1.5, hs=2, aws=1)
    assert result == "LOSS"
    result, _ = grade_rl("away", -1.5, hs=2, aws=1)
    assert result == "WIN"
    result, _ = grade_rl("away", -1.5, hs=3, aws=1)
    assert result == "LOSS"


def test_missing_score_is_not_a_push():
    result, units = grade_rl("home", -1.5, hs=None, aws=4)
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
    assert s["green_months"] == 3
    assert s["max_per_day"] <= 4 or s["max_per_day"] > 4
    # 20 bets on one day fails the selective cap.
    assert s["max_per_day"] == 20
    assert s["clears"] is False
    # Same units, one bet per calendar day so max/day ≤ 4.
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
        "hs": 5, "aws": 1, "line": -1.5,
        "home_tix": 80.0, "away_tix": 20.0,
        "home_money": 70.0, "away_money": 30.0,
        "public_side": "home", "public_tix": 80.0,
        "home_book": "draftkings", "home_price": -110.0,
        "away_book": "draftkings", "away_price": -110.0,
        "fav": "home", "dog": "away",
        "fav_tix": 80.0, "fav_money": 70.0, "fav_rlm": -10.0,
        "home_rlm": -10.0,
        "move_home_pp": None,
    }
    base.update(kw)
    return base


def test_overlay_oppose_fades_public_when_steam_leaves_them():
    """Public home + steam away → fade home. Same side as follow-steam oppose."""
    b = _board(move_home_pp=-2.5)
    fade = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="oppose", follow_steam=False)
    follow = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="oppose", follow_steam=True)
    assert len(fade) == 1 and fade[0]["side"] == "away"
    assert len(follow) == 1 and follow[0]["side"] == "away"
    agree = overlay_public_steam(
        [b], tix_cut=70, pp_cut=2.0, mode="agree", follow_steam=False)
    assert agree == []


def test_money_heavy_fades_the_money_pile_not_tickets():
    b = _board(home_tix=55.0, away_tix=45.0, home_money=80.0, away_money=20.0,
               public_side="home", public_tix=55.0)
    rows = fade_money_side([b], cut=70.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "away"


def test_home_dog_only_when_dk_plus_one_five():
    fav = _board(line=-1.5, away_tix=80.0)
    dog = _board(line=1.5, away_tix=80.0, home_tix=20.0, public_side="away",
                 public_tix=80.0)
    assert fade_home_dog([fav], away_tix_cut=70.0) == []
    rows = fade_home_dog([dog], away_tix_cut=70.0)
    assert len(rows) == 1
    assert rows[0]["side"] == "home"


def test_attach_steam_copies_move_pp_by_game_id():
    b = _board()
    attach_steam([b], [{"game_id": b["game_id"], "move_home_pp": 3.1}])
    assert b["move_home_pp"] == 3.1


def test_hunt_does_not_unpause_or_publish():
    src = Path("scripts/mlb_runline_edge_hunt.py").read_text(encoding="utf-8")
    assert "PAUSED_MODELS" not in src
    assert "PUBLISH=1" not in src
    assert "mlb_runline" in config.PAUSED_MODELS
    assert config.MLB_SPREAD_MARKET_PUBLISH is False
    assert "MLB_RUNLINE_PUBLIC_FADE_PUBLISH" not in dir(config)
    # I24 totals guards stay where the totals card left them.
    assert config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT == 70
    assert config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE == 0
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MIN is None
    assert config.MLB_TOTAL_PUBLIC_FADE_UNDER_ODDS_MAX is None
    fade_src = Path("models/mlb_total_public_fade.py").read_text(encoding="utf-8")
    assert "UNDER_ODDS_MIN" in fade_src
    assert "MAX_PER_SLATE" in fade_src
