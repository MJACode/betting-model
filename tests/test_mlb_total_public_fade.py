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
    assert fade.fade_rule() == fade.RULE_STEAM
    assert fade.DEFAULT_STEAM_TICKETS == 75.0
    assert config.MLB_TOTAL_PUBLIC_FADE_STEAM_TICKETS == 75.0
    assert fade.steam_ticket_threshold() == 75.0
    assert fade.require_money_steam() is True
    assert fade.min_under_price_floor() is None
    assert fade.max_bets_per_slate() == 2
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False


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


# ── slate concentration (2026-09-19: 12/12 under) ────────────────────────────


def _slate(tickets: list[float]):
    """N games, each with a DK open and the given over-ticket pct."""
    splits = {}
    quotes = {}
    games = {}
    for i, tix in enumerate(tickets, start=1):
        gid = f"G{i}"
        splits[gid] = _split(gid=gid, ticket=tix)
        key, row = _quote(gid, "draftkings")
        quotes[key] = row
        games[gid] = {
            "home": "NYY", "away": "BOS",
            "game_date": "2026-06-15",
            "commence_time": COMMENCE,
        }
    return splits, quotes, games


class _EmptyConn:
    """No existing picks. Records what _insert_picks would have been given."""

    def __init__(self):
        self.inserted = []

    def execute(self, _sql, _params=None):
        return type("R", (), {"fetchone": staticmethod(lambda: None)})()

    def commit(self):
        return None


def test_ten_game_all_under_slate_inserts_zero_bets(monkeypatch):
    """The 2026-09-19 shape: every game ≥70% public over → every under.

    Finder still flags them. The guard must make INSERT a no-op.
    """
    from scripts.mlb_total_public_fade_card import pick_rows, publish, rows_for_insert

    tickets = [75.0, 80.0, 82.0, 90.0, 88.0, 77.0, 95.0, 71.0, 73.0, 85.0]
    splits, quotes, games = _slate(tickets)
    bets, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    assert len(bets) == 10, diag
    assert all(b.over_ticket_pct >= 70 for b in bets)

    # Without the guard this slate is 10 BET rows — the 2026-09-19 card.
    unguarded = pick_rows(bets, games, quotes, bankroll=10_000)
    assert len(unguarded) == 10
    assert all(r["signal_type"] == "BET" and r["pick_side"] == "under"
               for r in unguarded)

    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert rows == []
    assert not any(r.get("signal_type") == "BET" for r in rows)

    recorded = []
    monkeypatch.setattr(
        "scripts.mlb_total_public_fade_card._insert_picks",
        lambda _conn, keep: recorded.extend(keep),
    )
    n = publish(_EmptyConn(), rows)
    assert n == 0
    assert recorded == []


def test_mixed_slate_three_unders_of_eight_still_allows_qualifying_unders():
    """8 games, only 3 clear the ticket cut. n_bet=3 < 4 → guard is silent."""
    from scripts.mlb_total_public_fade_card import rows_for_insert

    tickets = [80.0, 75.0, 90.0, 55.0, 40.0, 60.0, 50.0, 65.0]
    splits, quotes, games = _slate(tickets)
    bets, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    assert len(bets) == 3, diag
    assert {b.game_id for b in bets} == {"G1", "G2", "G3"}

    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert len(rows) == 3
    assert {r["game_id"] for r in rows} == {"G1", "G2", "G3"}
    assert all(r["pick_side"] == "under" for r in rows)
    assert all(r["signal_type"] == "BET" for r in rows)
    assert all("Under" in r["pick_label"] for r in rows)


def test_publish_stays_off_and_xgboost_stays_paused_after_the_guard():
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    assert fade.publish_enabled() is False
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS


# ── steam selector (2026-09-19) ──────────────────────────────────────────────


def _steam_split(gid, ticket, money, **extra):
    return _split(gid=gid, ticket=ticket, public_money_pct=money,
                  over_money_pct=money, game_date="2026-06-15", **extra)


def test_steam_requires_money_at_or_above_tickets():
    quotes = _dk_board()
    steam, diag = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 81)}, quotes, rule=fade.RULE_STEAM)
    assert len(steam) == 1
    assert steam[0].over_money_pct == 81.0
    faded, diag2 = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 79)}, quotes, rule=fade.RULE_STEAM)
    assert faded == []
    assert diag2["not_steam"] == 1


def test_steam_missing_money_fails_closed():
    quotes = _dk_board()
    bets, diag = fade.select_fade_bets(
        {"G1": _split(ticket=90)}, quotes, rule=fade.RULE_STEAM)
    assert bets == []
    assert diag["not_steam"] == 1
    assert fade.is_public_steam(90, None) is False


def test_steam_ticket_cut_is_seventy_five_not_seventy():
    quotes = _dk_board()
    low, diag = fade.select_fade_bets(
        {"G1": _steam_split("G1", 74.9, 80)}, quotes, rule=fade.RULE_STEAM)
    assert low == []
    assert diag["below_cut"] == 1
    ok, _ = fade.select_fade_bets(
        {"G1": _steam_split("G1", 75.0, 75.0)}, quotes, rule=fade.RULE_STEAM)
    assert len(ok) == 1


def test_juice_floor_is_opt_in_and_drops_minus_120():
    quotes = _dk_board(under=-120)
    no_floor, _ = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 85)}, quotes,
        rule=fade.RULE_STEAM, min_under_price=None)
    assert len(no_floor) == 1
    floored, diag = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 85)}, quotes,
        rule=fade.RULE_STEAM, min_under_price=-115)
    assert floored == []
    assert diag["juice_floor"] == 1
    keep, _ = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 85)},
        _dk_board(under=-110),
        rule=fade.RULE_STEAM, min_under_price=-115)
    assert len(keep) == 1


def test_steam_slate_caps_at_two_ranked_by_tix_then_juice():
    """Highest over_tix first; juice (lower implied) breaks ties."""
    splits = {
        "G1": _steam_split("G1", 90, 92),
        "G2": _steam_split("G2", 88, 90),
        "G3": _steam_split("G3", 80, 81),
        "G4": _steam_split("G4", 95, 96),
    }
    quotes = {}
    # G4 95 tix @-110, G1 90 @-105 (better juice), G2 88, G3 80.
    for gid, under in (("G1", -105), ("G2", -110), ("G3", -102), ("G4", -110)):
        key, row = _quote(gid, "draftkings", under=under)
        quotes[key] = row
    bets, diag = fade.select_fade_bets(
        splits, quotes, rule=fade.RULE_STEAM, max_per_slate=2)
    assert {b.game_id for b in bets} == {"G4", "G1"}
    assert diag["capped"] == 2
    # Same tix: better juice wins.
    tied = {
        "A": _steam_split("A", 80, 80),
        "B": _steam_split("B", 80, 80),
    }
    tied["A"]["game_date"] = "2026-06-16"
    tied["B"]["game_date"] = "2026-06-16"
    tq = {}
    for gid, under in (("A", -120), ("B", -105)):
        key, row = _quote(gid, "draftkings", under=under)
        tq[key] = row
    picks, _ = fade.select_fade_bets(
        tied, tq, rule=fade.RULE_STEAM, max_per_slate=1)
    assert [b.game_id for b in picks] == ["B"]


def test_steam_ten_game_slate_inserts_two_not_twelve():
    """Anti-spam: steam + cap 2. Suppress-all does not fire (n=2 < 4)."""
    from scripts.mlb_total_public_fade_card import rows_for_insert

    tickets = [75.0, 80.0, 82.0, 90.0, 88.0, 77.0, 95.0, 76.0, 78.0, 85.0]
    splits, quotes, games = _slate(tickets)
    for gid, tix in zip(splits, tickets):
        splits[gid]["public_money_pct"] = tix + 1
        splits[gid]["over_money_pct"] = tix + 1
        splits[gid]["game_date"] = "2026-06-15"
    bets, diag = fade.select_fade_bets(
        splits, quotes, rule=fade.RULE_STEAM)
    assert len(bets) == 2, diag
    assert {b.game_id for b in bets} == {"G7", "G4"}  # 95, 90
    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert len(rows) == 2
    assert all(r["pick_side"] == "under" and r["signal_type"] == "BET"
               for r in rows)


def test_blunt_ten_game_slate_still_suppresses_all():
    """RULE=blunt keeps the 2026-09-19 guard: 10 unders → INSERT []."""
    from scripts.mlb_total_public_fade_card import rows_for_insert

    tickets = [75.0, 80.0, 82.0, 90.0, 88.0, 77.0, 95.0, 71.0, 73.0, 85.0]
    splits, quotes, games = _slate(tickets)
    bets, diag = fade.select_fade_bets(
        splits, quotes, rule=fade.RULE_BLUNT, max_per_slate=None)
    assert len(bets) == 10, diag
    assert rows_for_insert(bets, games, quotes, bankroll=10_000) == []


def test_grade_under_matches_paper_tracker_units():
    assert fade.grade_under(7, 8.5, -110) == ("WIN", pytest.approx(100 / 110))
    assert fade.grade_under(9, 8.5, -110) == ("LOSS", -1.0)
    assert fade.grade_under(8.5, 8.5, -110) == ("PUSH", 0.0)
    assert fade.grade_under(7, 8.5, 120) == ("WIN", pytest.approx(1.20))


def test_top1_keeps_highest_tix_only():
    """RULE=top1 is the searched alternate: t70 pool, cap 1, no steam filter."""
    splits = {
        "G1": _steam_split("G1", 90, 70),  # tix high, money below tix
        "G2": _steam_split("G2", 80, 90),
        "G3": _steam_split("G3", 71, 80),
        "G4": _steam_split("G4", 69, 90),  # below t70
    }
    quotes = {}
    for gid, under in (("G1", -110), ("G2", -105), ("G3", -102), ("G4", -100)):
        key, row = _quote(gid, "draftkings", under=under)
        quotes[key] = row
    bets, diag = fade.select_fade_bets(splits, quotes, rule=fade.RULE_TOP1)
    assert [b.game_id for b in bets] == ["G1"]
    assert diag["rule"] == fade.RULE_TOP1
    assert diag["capped"] == 2  # G2 and G3 dropped by cap; G4 never entered
    # Same tix: better juice wins.
    tied = {
        "A": _steam_split("A", 80, 80),
        "B": _steam_split("B", 80, 80),
    }
    tq = {}
    for gid, under in (("A", -120), ("B", -105)):
        key, row = _quote(gid, "draftkings", under=under)
        tq[key] = row
    picks, _ = fade.select_fade_bets(tied, tq, rule=fade.RULE_TOP1)
    assert [b.game_id for b in picks] == ["B"]


def test_unknown_rule_coerces_to_steam():
    assert fade.fade_rule() == fade.RULE_STEAM
    quotes = _dk_board()
    bets, diag = fade.select_fade_bets(
        {"G1": _steam_split("G1", 80, 81)}, quotes, rule="not-a-rule")
    assert diag["rule"] == fade.RULE_STEAM
    assert len(bets) == 1


def test_card_still_does_not_publish_on_steam():
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    assert fade.publish_enabled() is False
    assert fade.fade_rule() == fade.RULE_STEAM
    assert fade.RULE_TOP1 in fade.KNOWN_RULES


def test_bootstrap_and_holdout_helpers_are_deterministic():
    from scripts.mlb_total_public_fade_select import bootstrap_roi, month_holdout

    units = [0.91, -1.0, 0.91, -1.0, 0.87]
    a = bootstrap_roi(units, n=200, seed=19)
    b = bootstrap_roi(units, n=200, seed=19)
    assert a == b
    mean, lo, hi, ppos = a
    assert lo <= mean <= hi
    assert 0.0 <= ppos <= 1.0
    rows = [
        {"month": "2026-06", "result": "WIN", "units": 0.9},
        {"month": "2026-06", "result": "LOSS", "units": -1.0},
        {"month": "2026-07", "result": "WIN", "units": 0.9},
    ]
    holds = month_holdout(rows)
    assert [h["hold"] for h in holds] == ["2026-06", "2026-07"]
    assert holds[0]["test"]["n"] == 2
    assert holds[1]["train"]["n"] == 2
