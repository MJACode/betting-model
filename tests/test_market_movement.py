"""Market movement as a feature — the leakage rules and the missing-data rules.

The models price against the market and never read it. These features close
that, and the two ways they could go wrong are both quiet: a leaked post-start
snapshot makes a model look brilliant in backtest, and a 0.0 standing in for
"unknown" teaches it that missing data is a signal.
"""

from __future__ import annotations

import config
from features.market_movement import (MARKET_MOVEMENT_FEATURES,
                                      american_to_prob, build_market_features)


def _s(book, snap, home=-110, away=-110, total=8.5, spread=-1.5):
    return {"book": book, "snap": snap, "home_price": home, "away_price": away,
            "total_line": total, "spread_home": spread}


# ── the arithmetic ───────────────────────────────────────────────────────────

def test_american_to_prob_both_signs():
    assert round(american_to_prob(-195), 4) == 0.661
    assert round(american_to_prob(150), 4) == 0.4
    assert american_to_prob(None) is None
    assert american_to_prob(0) is None


def test_movement_is_signed_and_in_probability_points():
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z", home=-110),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-140),
    ])
    # -110 -> 0.5238, -140 -> 0.5833
    assert out["mkt_move_home_pp"] == 5.95
    assert out["mkt_move_abs_pp"] == 5.95


def test_the_sign_flips_with_the_direction():
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z", home=-140),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-110),
    ])
    assert out["mkt_move_home_pp"] == -5.95
    assert out["mkt_move_abs_pp"] == 5.95


# ── missing data is None, never zero ─────────────────────────────────────────

def test_a_single_snapshot_yields_no_movement_rather_than_zero():
    """"The line did not move" and "we saw it once" are different facts, and a
    0.0 for the second teaches the model that absence is a signal."""
    out = build_market_features([_s("draftkings", "2026-08-30T10:00:00Z")])
    assert out["mkt_move_home_pp"] is None
    assert out["mkt_move_abs_pp"] is None
    assert out["mkt_open_implied_home"] is not None      # the open IS known
    assert out["mkt_snapshots"] == 1


def test_no_snapshots_yields_every_feature_none():
    out = build_market_features([])
    assert set(out) == set(MARKET_MOVEMENT_FEATURES)
    assert all(v is None for v in out.values())


def test_a_line_that_genuinely_did_not_move_is_zero_not_none():
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z", home=-110),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-110),
    ])
    assert out["mkt_move_home_pp"] == 0.0


# ── which book, and cross-book disagreement ──────────────────────────────────

def test_the_decision_book_leads():
    """Every threshold was swept on DK-implied edge (CLAUDE.md §6), so the
    movement feature has to describe DK's line, not an average of books."""
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z", home=-110),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-110),
        # Pinnacle moves hard, and moves LAST. If the builder pooled books this
        # would become the closing price and the move would be large.
        _s("pinnacle", "2026-08-30T19:00:00Z", home=-300),
    ])
    assert out["mkt_move_home_pp"] == 0.0     # DK never moved; Pinnacle is not DK
    assert out["mkt_snapshots"] == 2          # and only DK's snapshots are counted


def test_a_game_with_no_decision_book_still_gets_features():
    """Falling back to all books beats losing the feature entirely."""
    out = build_market_features([
        _s("betmgm", "2026-08-30T10:00:00Z", home=-110),
        _s("betmgm", "2026-08-30T18:00:00Z", home=-140),
    ])
    assert out["mkt_move_home_pp"] == 5.95


def test_disagreement_uses_each_books_own_latest_price():
    """Books do not publish on the same tick. Pinning them to one timestamp
    leaves most games with a single quote and the feature null."""
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z", home=-110),
        _s("betmgm", "2026-08-30T11:00:00Z", home=-150),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-110),
    ])
    assert out["mkt_book_disagree_pp"] is not None
    assert out["mkt_book_disagree_pp"] > 0


def test_one_book_cannot_disagree_with_itself():
    out = build_market_features([
        _s("draftkings", "2026-08-30T10:00:00Z"),
        _s("draftkings", "2026-08-30T18:00:00Z"),
    ])
    assert out["mkt_book_disagree_pp"] is None


# ── the sharp prior ──────────────────────────────────────────────────────────

def test_the_sharp_prior_is_de_vigged():
    """Raw implied probabilities sum to more than 1. A prior that keeps the vig
    is not a probability, and DK's distance from it would be measured against
    the wrong number."""
    out = build_market_features([
        _s("pinnacle", "2026-08-30T17:00:00Z", home=-150, away=130),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-140, away=120),
    ])
    # -150/+130 raw = 0.600 / 0.435, sum 1.035 -> de-vigged home 0.5798
    assert out["mkt_sharp_devig_home"] == 0.5798
    assert out["mkt_dk_vs_sharp_pp"] == 0.35


def test_a_one_way_sharp_quote_yields_nothing():
    """De-vig needs both sides. Half a market gives a half-corrected number,
    which is worse than no number."""
    out = build_market_features([
        _s("pinnacle", "2026-08-30T17:00:00Z", home=-150, away=None),
        _s("draftkings", "2026-08-30T18:00:00Z", home=-140, away=120),
    ])
    assert out["mkt_sharp_devig_home"] is None
    assert out["mkt_dk_vs_sharp_pp"] is None


def test_the_sharp_book_comes_from_config():
    import inspect

    from features import market_movement

    src = inspect.getsource(market_movement.build_market_features)
    assert "config.SHARP_BOOKMAKERS" in src
    assert config.SHARP_BOOKMAKERS  # and it is actually populated


# ── leakage ──────────────────────────────────────────────────────────────────

def test_the_loader_excludes_in_play_and_post_start_rows():
    """Both filters are needed: the evening refresh keeps writing `open` rows
    after first pitch, so snapshot_type alone does not bound the window (§7)."""
    import inspect

    from features import market_movement

    src = inspect.getsource(market_movement.load_market_movement)
    assert "in_play" in src
    assert "_is_pregame_snapshot" in src


def test_the_pregame_guard_fails_open_on_a_missing_timestamp():
    """SBR and synthetic rows carry no usable snapshot time and must survive —
    they are one row per game and predate the snapshot era, so nothing leaks."""
    from features.feature_engine import _is_pregame_snapshot

    assert _is_pregame_snapshot(None, "2026-08-30T18:00:00Z") is True
    assert _is_pregame_snapshot("2026-08-30T10:00:00Z", None) is True
    assert _is_pregame_snapshot("2026-08-30T23:00:00Z", "2026-08-30T18:00:00Z") is False


def test_the_feature_list_is_the_single_source_of_names():
    """The builders, the tests and the activation patch all read this list, so
    a name can only be added in one place."""
    out = build_market_features([_s("draftkings", "2026-08-30T10:00:00Z")])
    assert set(out) == set(MARKET_MOVEMENT_FEATURES)
