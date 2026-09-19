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


def test_ten_game_all_under_slate_keeps_two_never_twelve(monkeypatch):
    """The 2026-09-19 shape: every game ≥70% public over → every under.

    Finder still flags all ten. The card must keep two, not ten and
    not the suppress-all empty set.
    """
    from scripts.mlb_total_public_fade_card import pick_rows, publish, rows_for_insert

    tickets = [75.0, 80.0, 82.0, 90.0, 88.0, 77.0, 95.0, 71.0, 73.0, 85.0]
    splits, quotes, games = _slate(tickets)
    bets, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    assert len(bets) == 10, diag
    assert all(b.over_ticket_pct >= 70 for b in bets)

    # Raw finder output is still the whole pile — ranking is the cap.
    unguarded = pick_rows(bets, games, quotes, bankroll=10_000)
    assert len(unguarded) == 10
    assert all(r["signal_type"] == "BET" and r["pick_side"] == "under"
               for r in unguarded)

    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert len(rows) == 2
    # Highest tickets: 95 (G7) and 90 (G4).
    assert {r["game_id"] for r in rows} == {"G7", "G4"}
    assert all(r["signal_type"] == "BET" and r["pick_side"] == "under"
               for r in rows)

    recorded = []
    monkeypatch.setattr(
        "scripts.mlb_total_public_fade_card._insert_picks",
        lambda _conn, keep: recorded.extend(keep),
    )
    n = publish(_EmptyConn(), rows)
    assert n == 2
    assert {r["game_id"] for r in recorded} == {"G7", "G4"}


def test_mixed_slate_three_unders_keeps_the_two_heaviest():
    """8 games, 3 clear the cut. Cap is 2 — never the third, never zero."""
    from scripts.mlb_total_public_fade_card import rows_for_insert

    tickets = [80.0, 75.0, 90.0, 55.0, 40.0, 60.0, 50.0, 65.0]
    splits, quotes, games = _slate(tickets)
    bets, diag = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    assert len(bets) == 3, diag
    assert {b.game_id for b in bets} == {"G1", "G2", "G3"}

    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert len(rows) == 2
    # 90 (G3) and 80 (G1). 75 (G2) is the one the cap drops.
    assert {r["game_id"] for r in rows} == {"G3", "G1"}
    assert all(r["pick_side"] == "under" for r in rows)
    assert all(r["signal_type"] == "BET" for r in rows)
    assert all("Under" in r["pick_label"] for r in rows)


def test_publish_stays_off_and_xgboost_stays_paused_after_the_guard():
    assert config.MLB_TOTAL_PUBLIC_FADE_PUBLISH is False
    assert fade.publish_enabled() is False
    assert "mlb_over_under" in config.PAUSED_MODELS
    assert "mlb_runline" in config.PAUSED_MODELS
    assert fade.max_per_slate() == 2
    assert config.MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE == 2
    assert fade.rank_kind() == fade.RANK_TICKET
    assert fade.edge_floor() == 0.0


def test_max_per_slate_clamps_to_one_or_two(monkeypatch):
    """0 is not all-pass. 99 is not a twelve-under card."""
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", 0)
    assert fade.max_per_slate() == 2
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", -3)
    assert fade.max_per_slate() == 2
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", 99)
    assert fade.max_per_slate() == 2
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", 1)
    assert fade.max_per_slate() == 1
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", 2)
    assert fade.max_per_slate() == 2


# ── top-K ranking ────────────────────────────────────────────────────────────


def _bet(gid="G1", ticket=80.0, money=70.0, price=-110.0, line=8.5):
    return fade.PublicFadeBet(
        game_id=gid, book="draftkings", line=line, price=price,
        over_ticket_pct=ticket, over_money_pct=money,
    )


def test_finder_copies_over_money_pct():
    quotes = _dk_board()
    bets, _ = fade.find_fade_bets(
        {"G1": _split(ticket=80.0, public_money_pct=72.0)},
        quotes, min_over_tickets=70)
    assert len(bets) == 1
    assert bets[0].over_money_pct == 72.0


def test_ticket_rank_picks_the_heavier_pile_not_the_lighter():
    """A lowest-ticket selector would keep G_lo. The formula must not."""
    heavy = _bet("G_hi", ticket=94.0, money=90.0, price=-110)
    light = _bet("G_lo", ticket=71.0, money=50.0, price=-110)
    assert fade.rank_score(heavy, fade.RANK_TICKET) > fade.rank_score(
        light, fade.RANK_TICKET)
    kept = fade.select_top_k(
        [light, heavy], max_per_slate=1,
        slate_of=lambda _b: "2026-06-15", kind=fade.RANK_TICKET)
    assert [b.game_id for b in kept] == ["G_hi"]


def test_juice_rank_prefers_plus_money_over_heavy_juice():
    plus = _bet("G_plus", ticket=80.0, money=80.0, price=100)
    juicy = _bet("G_juice", ticket=80.0, money=80.0, price=-130)
    assert fade.rank_score(plus, fade.RANK_JUICE) > fade.rank_score(
        juicy, fade.RANK_JUICE)
    kept = fade.select_top_k(
        [juicy, plus], max_per_slate=1,
        slate_of=lambda _b: "d", kind=fade.RANK_JUICE)
    assert [b.game_id for b in kept] == ["G_plus"]


def test_composite_can_outrank_a_higher_ticket_that_is_juiced():
    """96tix at −130 vs 90tix at +100: juice + gap can flip ticket order."""
    piled = _bet("G_pile", ticket=96.0, money=96.0, price=-130)
    clean = _bet("G_clean", ticket=90.0, money=70.0, price=100)
    assert fade.rank_score(piled, fade.RANK_TICKET) > fade.rank_score(
        clean, fade.RANK_TICKET)
    assert fade.composite_score(clean) > fade.composite_score(piled)
    kept = fade.select_top_k(
        [piled, clean], max_per_slate=1,
        slate_of=lambda _b: "d", kind=fade.RANK_COMPOSITE)
    assert [b.game_id for b in kept] == ["G_clean"]


def test_top_k_is_per_slate_and_zero_is_all_pass():
    a1 = _bet("A1", ticket=90)
    a2 = _bet("A2", ticket=80)
    b1 = _bet("B1", ticket=85)
    dates = {"A1": "2026-06-15", "A2": "2026-06-15", "B1": "2026-06-16"}
    all_pass = fade.select_top_k(
        [a1, a2, b1], max_per_slate=0,
        slate_of=lambda b: dates[b.game_id], kind=fade.RANK_TICKET)
    assert {b.game_id for b in all_pass} == {"A1", "A2", "B1"}
    top1 = fade.select_top_k(
        [a1, a2, b1], max_per_slate=1,
        slate_of=lambda b: dates[b.game_id], kind=fade.RANK_TICKET)
    assert {b.game_id for b in top1} == {"A1", "B1"}


def test_ev_without_a_lookup_ranks_as_ticket():
    """Card does not load a bucket table; RANK=ev must not invent one."""
    heavy = _bet("G_hi", ticket=94.0)
    light = _bet("G_lo", ticket=71.0)
    assert fade.rank_score(heavy, fade.RANK_EV) == fade.rank_score(
        heavy, fade.RANK_TICKET)
    kept = fade.select_top_k(
        [light, heavy], max_per_slate=1,
        slate_of=lambda _b: "d", kind=fade.RANK_EV)
    assert [b.game_id for b in kept] == ["G_hi"]


def test_edge_floor_without_rates_is_ignored():
    dear = _bet("G_no", ticket=90, price=-130)
    kept = fade.select_top_k(
        [dear], max_per_slate=0,
        slate_of=lambda _b: "d", kind=fade.RANK_TICKET,
        min_edge=0.05)
    assert [b.game_id for b in kept] == ["G_no"]


def test_edge_floor_drops_a_bet_whose_bucket_wr_does_not_clear_juice():
    cheap = _bet("G_ok", ticket=90, price=100)
    dear = _bet("G_no", ticket=90, price=-130)
    rates = {(85.0, 95.0): 0.52}
    # implied(100)≈0.500, implied(-130)≈0.565. Floor 0.01 keeps only +100.
    kept = fade.select_top_k(
        [cheap, dear], max_per_slate=2,
        slate_of=lambda _b: "d", kind=fade.RANK_TICKET,
        min_edge=0.01, bucket_win_rate=rates)
    assert [b.game_id for b in kept] == ["G_ok"]


def test_topk_sweep_grades_under_the_same_way_paper_tracker_does():
    """Units = profit_flat/100. Under wins when home+away < line."""
    from scripts.mlb_total_public_fade_topk import american_units, grade_under

    assert american_units(-110, True) == pytest.approx(100.0 / 110.0)
    assert american_units(-110, False) == -1.0
    assert american_units(100, True) == pytest.approx(1.0)
    result, units = grade_under(8.5, -110, 3, 4)
    assert result == "WIN"
    assert units == pytest.approx(100.0 / 110.0)
    assert grade_under(8.5, -110, 5, 4)[0] == "LOSS"
    assert grade_under(8.5, -110, 4, 4.5) == ("PUSH", 0.0)
    assert grade_under(8.5, -110, None, 4) == (None, None)


def test_topk_flag_one_keeps_only_the_heaviest_on_a_ten_under_slate(
        monkeypatch):
    """Env 1 is the only legal tighter cap. Still never zero, never ten."""
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_MAX_PER_SLATE", 1)
    monkeypatch.setattr(config, "MLB_TOTAL_PUBLIC_FADE_RANK", "ticket")
    from scripts.mlb_total_public_fade_card import rows_for_insert

    tickets = [75.0, 80.0, 82.0, 90.0, 88.0, 77.0, 95.0, 71.0, 73.0, 85.0]
    splits, quotes, games = _slate(tickets)
    bets, _ = fade.find_fade_bets(splits, quotes, min_over_tickets=70)
    assert len(bets) == 10
    rows = rows_for_insert(bets, games, quotes, bankroll=10_000)
    assert [r["game_id"] for r in rows] == ["G7"]
    assert rows[0]["signal_type"] == "BET" and rows[0]["pick_side"] == "under"
