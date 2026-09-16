"""Paper MLB totals public-fade: as-of, ticket cut, price shop.

The card fades a consensus OVER pile and bets UNDER. These tests pin the
traps that would manufacture that fade from leaked or post-start splits,
and the cut/price window the backtest was taken at.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

import config
import models.mlb_total_public_fade as fade
from models.market_relative import implied
from tracking.pick_integrity import pick_problems


COMMENCE = "2026-06-15T23:10:00+00:00"  # 7:10pm ET
# 8:00pm ET. Text compare vs COMMENCE looks "before" (20 < 23); it is after.
POST_START_ET = "2026-06-15T20:00:00-04:00"
# 7:00pm ET. Honest pre-commence, offset-aware.
PRE_START_ET = "2026-06-15T19:00:00-04:00"
OLDER_PRE = "2026-06-15T16:00:00-04:00"


def _split(gid="G1", ticket=75.0, snap=PRE_START_ET, commence=COMMENCE, **extra):
    row = {
        "game_id": gid,
        "ticket": ticket,
        "public_bet_pct": ticket,
        "snapshot_at": snap,
        "commence_time": commence,
    }
    row.update(extra)
    return row


def _quote(gid, book, line=8.5, under=-110, over=-110, snap="2026-06-15T16:00:00Z"):
    return (gid, book), {
        "game_id": gid, "book": book,
        "total_line": line, "under_price": under, "over_price": over,
        "snapshot_at": snap, "under_link": None, "over_link": None,
    }


def _quotes(*pairs):
    return dict(pairs)


def _dk_board(gid="G1", line=8.5, under=-110):
    return _quotes(_quote(gid, "draftkings", line=line, under=under))


# ── as-of / leakage ──────────────────────────────────────────────────────────


def test_post_start_split_is_dropped_even_when_text_says_before():
    """The -04:00 vs +00:00 trap. Text compare would keep POST_START_ET."""
    assert POST_START_ET < COMMENCE  # the leak, as strings
    kept = fade.select_latest_pre_commence_over([
        _split(ticket=90, snap=POST_START_ET),
    ])
    assert kept == {}
    assert fade.is_pre_commence(POST_START_ET, COMMENCE) is False
    assert fade.is_pre_commence(PRE_START_ET, COMMENCE) is True


def test_snapshot_at_commence_is_not_pre_commence():
    kept = fade.select_latest_pre_commence_over([
        _split(ticket=90, snap=COMMENCE),
    ])
    assert kept == {}
    assert fade.is_pre_commence(COMMENCE, COMMENCE) is False


def test_newest_pre_commence_wins():
    kept = fade.select_latest_pre_commence_over([
        _split(ticket=60, snap=OLDER_PRE),
        _split(ticket=80, snap=PRE_START_ET),
    ])
    assert len(kept) == 1
    assert kept["G1"]["ticket"] == 80


def test_missing_clocks_fail_closed():
    assert fade.is_pre_commence(None, COMMENCE) is False
    assert fade.is_pre_commence(PRE_START_ET, None) is False
    assert fade.select_latest_pre_commence_over([
        _split(ticket=90, snap=None),
    ]) == {}


# ── ticket threshold ─────────────────────────────────────────────────────────


def test_default_cut_is_seventy_and_env_default_is_seventy():
    assert fade.DEFAULT_OVER_TICKETS == 70.0
    assert config.MLB_TOTAL_PUBLIC_FADE_TICKET_PCT == 70.0
    assert fade.ticket_threshold() == 70.0


def test_seventy_fires_and_just_under_does_not():
    quotes = _dk_board()
    bets, diag = fade.find_fade_bets(
        {"G1": _split(ticket=70.0)}, quotes, min_over_tickets=70)
    assert len(bets) == 1
    assert bets[0].over_ticket_pct == 70.0
    assert bets[0].game_id == "G1"
    assert bets[0].book == "draftkings"
    none, diag70 = fade.find_fade_bets(
        {"G1": _split(ticket=69.9)}, quotes, min_over_tickets=70)
    assert none == []
    assert diag70["below_cut"] == 1


def test_eighty_cut_is_supported_and_is_not_seventy():
    quotes = _dk_board()
    splits = {"G1": _split(ticket=79.9)}
    t70, _ = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    t80, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=80)
    assert len(t70) == 1
    assert t80 == []
    assert diag["below_cut"] == 1
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=80.0)}, quotes, min_over_tickets=80)
    assert len(bets) == 1


def test_decimal_ticket_pct_still_compares():
    quotes = _dk_board()
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=Decimal("70.0"))}, quotes, min_over_tickets=70)
    assert len(bets) == 1


def test_leaked_split_cannot_reach_the_finder_via_select():
    """The finder trusts select_latest_pre_commence_over; a leaked row
    that skipped that helper is not this test. The as-of helper is the bound."""
    quotes = _dk_board()
    leaked = fade.select_latest_pre_commence_over([
        _split(ticket=95, snap=POST_START_ET),
    ])
    bets, _ = fade.find_fade_bets(leaked, quotes, min_over_tickets=70)
    assert bets == []


# ── price / line ─────────────────────────────────────────────────────────────


def test_no_dk_open_is_not_a_bet():
    quotes = _quotes(_quote("G1", "fanduel", under=-105))
    bets, diag = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, quotes, min_over_tickets=70)
    assert bets == []
    assert diag["no_dk"] == 1


def test_shops_best_same_line_under_among_the_four():
    quotes = _quotes(
        _quote("G1", "draftkings", under=-110),
        _quote("G1", "fanduel", under=-102),
        _quote("G1", "betmgm", under=-108),
        _quote("G1", "williamhill_us", under=-115),
    )
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=75)}, quotes, min_over_tickets=70)
    assert len(bets) == 1
    assert bets[0].book == "fanduel"
    assert bets[0].price == -102
    assert implied(-102) < implied(-110)


def test_different_line_at_fd_is_not_shopped():
    quotes = _quotes(
        _quote("G1", "draftkings", line=8.5, under=-110),
        _quote("G1", "fanduel", line=9.0, under=-102),
    )
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=75)}, quotes, min_over_tickets=70)
    assert len(bets) == 1
    assert bets[0].book == "draftkings"
    assert bets[0].line == 8.5


def test_line_outside_main_total_window_is_dropped():
    quotes = _dk_board(line=15.0)
    bets, diag = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, quotes, min_over_tickets=70)
    assert bets == []
    assert diag["line_out"] == 1
    quotes_lo = _dk_board(line=5.0)
    bets_lo, _ = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, quotes_lo, min_over_tickets=70)
    assert bets_lo == []


def test_under_price_outside_window_is_dropped():
    juicy = _dk_board(under=-250)
    bets, diag = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, juicy, min_over_tickets=70)
    assert bets == []
    assert diag["no_price"] == 1
    longshot = _dk_board(under=250)
    bets2, _ = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, longshot, min_over_tickets=70)
    assert bets2 == []


def test_always_under_one_per_game():
    quotes = _quotes(
        _quote("G1", "draftkings", under=-110),
        _quote("G1", "fanduel", under=-105),
    )
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=80)}, quotes, min_over_tickets=70)
    assert len(bets) == 1
    assert bets[0].book == "fanduel"


# ── registry / publish / settlement ──────────────────────────────────────────


def test_publish_defaults_off_and_xgboost_stays_paused():
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    assert fade.publish_enabled() is False
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS
    assert "mlb_total_public_fade" not in config.PAUSED_MODELS
    assert "mlb_total_public_fade" not in config.GAME_MARKET_GATE_MODELS
    assert config.ACTION_THRESHOLDS["mlb_total_public_fade"] == {
        "min_prob": 0.0, "min_edge": 0.0,
    }
    assert config.scoring_method("mlb_total_public_fade") == "rule"
    assert fade.SOFT_BOOKS == ("draftkings", "fanduel", "betmgm", "williamhill_us")
    assert fade.FALLBACK_BOOK == "draftkings"


def test_settlement_grades_totals_not_h2h():
    src = (Path(__file__).resolve().parents[1] / "tracking"
           / "paper_tracker.py").read_text(encoding="utf-8")
    assert '"mlb_total_public_fade": "totals"' in src


def test_pick_label_quotes_under_and_agrees_with_the_line():
    from scripts.mlb_total_public_fade_card import pick_rows

    bet = fade.PublicFadeBet(
        game_id="MLB_2026-06-15_NYY_BOS", book="fanduel",
        line=8.5, price=-102.0, over_ticket_pct=76.0,
    )
    games = {"MLB_2026-06-15_NYY_BOS": {
        "home": "NYY", "away": "BOS", "game_date": "2026-06-15",
        "commence_time": "2026-06-15T23:10:00Z",
    }}
    rows = pick_rows([bet], games, {}, bankroll=10_000)
    assert len(rows) == 1
    r = rows[0]
    assert r["pick_side"] == "under"
    assert r["scored_line"] == 8.5
    assert "Under 8.5" in r["pick_label"]
    assert r["model_id"] == "mlb_total_public_fade"
    assert r["decision_book"] == "fanduel"
    assert r["signal_type"] == "BET"
    assert r["recommended_bet"] == 100.0
    assert r["edge"] == pytest.approx(0.26)
    assert r["pick_label"].endswith("(FD)")
    problems = pick_problems(
        r["pick_label"], r["pick_side"], r["scored_line"],
        r["model_id"], "NYY", "BOS")
    assert problems == [], problems


def test_house_juice_floor_drops_a_minus_250_even_if_finder_slipped():
    from scripts.mlb_total_public_fade_card import pick_rows

    bet = fade.PublicFadeBet(
        game_id="G1", book="draftkings",
        line=8.5, price=-250.0, over_ticket_pct=80.0,
    )
    games = {"G1": {"home": "NYY", "away": "BOS", "game_date": "2026-06-15",
                    "commence_time": "t"}}
    assert pick_rows([bet], games, {}, bankroll=10_000) == []
