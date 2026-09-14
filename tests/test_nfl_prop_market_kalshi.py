"""Kalshi as a fail-closed OR exchange reference for nfl_prop_market.

Wiring (2026-09-14): the MARKET rule may price a soft quote off a Kalshi
ladder mid when Pinnacle/betonlineag cannot (different line, or no quote).
Kalshi is a reference only — never in SOFT_BOOKS — and an empty/missing
ladder board must leave the existing two-book path unchanged.
"""
from __future__ import annotations

import pytest

import models.nfl_prop_market as mk
from models.prop_ladder import Ladder, Rung


def _ladder(rows):
    return Ladder([Rung(s, b, a) for s, b, a in rows])


# Dak-shaped receiving/pass ladder; mid at 249.5 is ~0.51.
DAK = [(174.5, .80, .87), (199.5, .76, .81), (224.5, .60, .70),
       (249.5, .45, .57), (274.5, .31, .42), (299.5, .17, .28),
       (324.5, .09, .19), (349.5, .07, .12)]


def test_kalshi_is_a_reference_never_a_soft_book():
    assert mk.KALSHI_BOOK == "kalshi"
    assert mk.KALSHI_BOOK not in mk.SOFT_BOOKS
    assert mk.KALSHI_BOOK not in mk.SHARP_BOOKS, (
        "kalshi is not an Odds API bookmaker; putting it in SHARP_BOOKS would "
        "make the prop-odds pruner demand a player_prop_odds carve-out for a "
        "book that is never stored there")


def test_kalshi_is_not_graded_until_settled_history_exists():
    """Reference only. The historical grader must not join kalshi ladders.

    Measured 2026-09-14: 278,568 ladder rungs, no resolved_at column.
    docs/nfl_prop_market_2026.md.
    """
    import scripts.nfl_prop_two_sharps as ts
    assert ts.REF_A == "pinnacle" and ts.REF_B == "betonlineag"
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "scripts"
           / "nfl_prop_two_sharps.py").read_text(encoding="utf-8")
    assert "kalshi_prop_ingestor" not in src
    assert "from_kalshi" not in src


def test_without_ladders_the_pinnacle_path_is_unchanged():
    """Fail closed: omit Kalshi and the two Odds API references behave as before."""
    quotes = {
        ("G1", "dak prescott", "player_pass_yds", "pinnacle"): {
            "line": 249.5, "over_price": -110, "under_price": -110},
        ("G1", "dak prescott", "player_pass_yds", "draftkings"): {
            "line": 249.5, "over_price": 130, "under_price": -160},
    }
    a, da = mk.find_bets(quotes, min_edge=0.02, soft_books=("draftkings",))
    b, db = mk.find_bets(quotes, min_edge=0.02, soft_books=("draftkings",),
                         kalshi_ladders={}, game_dates={})
    assert [(x.side, round(x.edge, 6), x.book) for x in sorted(a, key=lambda x: x.side)] == [
        (x.side, round(x.edge, 6), x.book) for x in sorted(b, key=lambda x: x.side)]
    assert da["bets"] == db["bets"]
    assert da["pinnacle_compared"] == db["pinnacle_compared"]


def test_kalshi_prices_a_line_pinnacle_cannot():
    """The coverage claim: soft 252.5 vs sharp 249.5 is a Kalshi comparison,
    not a line_mismatch discard."""
    quotes = {
        ("G1", "dak prescott", "player_pass_yds", "pinnacle"): {
            "line": 249.5, "over_price": -110, "under_price": -110},
        ("G1", "dak prescott", "player_pass_yds", "draftkings"): {
            "line": 252.5, "over_price": 150, "under_price": -180},
    }
    none, d0 = mk.find_bets(quotes, min_edge=0.01, soft_books=("draftkings",))
    assert none == []
    assert d0["pinnacle_line_mismatch"] >= 1

    lads = {("2026-09-14", "dak prescott", "player_pass_yds"): _ladder(DAK)}
    dates = {"G1": "2026-09-14"}
    got, d1 = mk.find_bets(
        quotes, min_edge=0.01, soft_books=("draftkings",),
        kalshi_ladders=lads, game_dates=dates)
    assert got, d1
    assert all(b.line == 252.5 for b in got)
    assert d1["kalshi_compared"] >= 1
    assert d1.get("kalshi_sharp_quotes", 0) == 1


def test_kalshi_outside_the_ladder_is_refused_not_extrapolated():
    quotes = {
        ("G1", "dak prescott", "player_pass_yds", "draftkings"): {
            "line": 50.5, "over_price": -110, "under_price": -110},
    }
    lads = {("2026-09-14", "dak prescott", "player_pass_yds"): _ladder(DAK)}
    got, diag = mk.find_bets(
        quotes, min_edge=0.0, soft_books=("draftkings",),
        kalshi_ladders=lads, game_dates={"G1": "2026-09-14"})
    assert got == []
    assert diag["kalshi_line_mismatch"] >= 1


def test_missing_game_date_fails_closed_for_that_row():
    quotes = {
        ("G1", "dak prescott", "player_pass_yds", "draftkings"): {
            "line": 249.5, "over_price": 150, "under_price": -180},
    }
    lads = {("2026-09-14", "dak prescott", "player_pass_yds"): _ladder(DAK)}
    got, diag = mk.find_bets(
        quotes, min_edge=0.0, soft_books=("draftkings",),
        kalshi_ladders=lads, game_dates={})  # no date -> cannot join
    assert got == []
    assert diag["kalshi_no_sharp"] >= 1


def test_zero_vig_american_round_trips_through_devig():
    """Kalshi mids become MarketBet.sharp_price via a zero-vig American."""
    from models.market_relative import devig
    for p in (0.35, 0.51, 0.65):
        o = mk._zero_vig_american(p)
        u = mk._zero_vig_american(1.0 - p)
        fo, fu = devig(o, u)
        assert fo == pytest.approx(p, abs=1e-9)
        assert fu == pytest.approx(1.0 - p, abs=1e-9)


def test_fetch_helper_swallows_errors(monkeypatch):
    """ladders_or_empty fails closed on any exception."""
    from data.ingestors import kalshi_prop_ingestor as kpi

    monkeypatch.setattr(kpi, "ladders",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert kpi.ladders_or_empty() == {}
