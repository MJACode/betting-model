"""The NCAAF moneyline model (models/ncaaf_moneyline_market.py), its card
(scripts/ncaaf_moneyline_card.py) and its build
(scripts/ncaaf_moneyline_market_build.py).

LIVE, real money (mike, 2026-11-10: "ML model yes"). The rule is a port of the
market audit's research code, and the build's replay matched its 311 bets game
for game; these tests pin each step of the rule on small hand-made games, so a
change to any of them fails here and not only at the next rebuild. The card
end to end against a real Postgres is tests/test_ncaaf_moneyline_card_pg.py.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.ncaab_book_quotes as bq  # noqa: E402
import models.ncaab_margin_dist as md  # noqa: E402
import models.ncaaf_moneyline_market as mm  # noqa: E402

UTC = timezone.utc
INSTANT = pd.Timestamp("2026-11-14 14:00", tz="UTC")
KICK = pd.Timestamp("2026-11-14 20:30", tz="UTC")
BOOKS4 = ("draftkings", "fanduel", "betmgm", "betrivers")


@pytest.fixture(scope="module")
def art():
    return mm.load_artifact()


def _rows(quotes, instant=INSTANT, tip=KICK):
    """quotes: (game, book, minutes before the instant, line, p1, p2)."""
    out = []
    for i, (gid, book, mins, line, p1, p2) in enumerate(quotes):
        out.append({"game_id": gid, "bookmaker": book, "ts": instant - pd.Timedelta(minutes=mins),
                    "line": line, "p1": p1, "p2": p2, "order": i, "instant": instant, "tip": tip,
                    "link1": f"{book}-home", "link2": f"{book}-away"})
    cols = ["game_id", "bookmaker", "ts", "line", "p1", "p2", "order", "instant", "tip", "link1", "link2"]
    return pd.DataFrame(out, columns=cols)


def _ph(art, cons):
    """The home side's fair chance at a consensus spread, as the model prices it."""
    pw, pp, pl = md.probs(np.array([-cons + art["offset"]]), np.zeros(1), art["table"])
    return float(pw[0] / (pw[0] + pl[0]))


def _american(p):
    """The American price whose implied chance is nearest p."""
    return float(round(-100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p))


def _implied(price):
    return float(1 / mm.dec(price))


def _spreads(gid="g", books=BOOKS4, line=-3.5):
    return [(gid, b, 20, line, -110.0, -110.0) for b in books]


def _moneylines(art, gid="g", books=BOOKS4, cons=-3.5, best="betrivers", edge=0.04, side="home"):
    """Every book a little short of fair on both sides, and `best` offering
    `side` at `edge` over its implied chance (its other side shorter by as
    much and 0.03 more, so its two implied chances still sum above 1)."""
    p = _ph(art, cons)
    out = []
    for b in books:
        home, away = _american(p + 0.02), _american(1 - p + 0.02)
        if b == best and side == "home":
            home, away = _american(p - edge), _american(1 - p + edge + 0.03)
        if b == best and side == "away":
            home, away = _american(p + edge + 0.03), _american(1 - p - edge)
        out.append((gid, b, 10, None, home, away))
    return out


def _at(book, home_implied, away_implied, mins=10, gid="g"):
    """One book's moneyline, from the implied chance of each side."""
    return (gid, book, mins, None, _american(home_implied), _american(away_implied))


def _decide(art, ml, sp, games=("g",), **kw):
    q = mm.quotes_at(_rows(ml), _rows(sp))
    return mm.decide(list(games), q, art["table"], art["offset"], **kw)


# ── config and the artifact ──────────────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut_and_floors():
    m = mm.MODEL_ID
    assert m == "ncaaf_moneyline_market"
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.02}
    assert config.MODEL_EDGE_THRESHOLDS[m] == mm.CUT == 0.02
    assert config.MODEL_PROB_THRESHOLDS[m] == 0.0
    assert config.scoring_method(m) == "rule"
    assert m in config.MODELS_ON_OWN_PROBABILITY
    # Not in the registries the scorer and the trainer iterate: a model there
    # with no feature map stops scoring for every sport.
    assert m not in config.MODELS and m not in config.PROP_MODELS and m not in config.LIVE_MODELS
    assert m not in config.PAUSED_MODELS and m not in config.RETIRED_MODELS


def test_the_price_floor_is_minus_200_and_pinned(monkeypatch):
    assert config.MODEL_MIN_ODDS[mm.MODEL_ID] == mm.MIN_PRICE == -200
    monkeypatch.setattr(config, "DEFAULT_MIN_ODDS", -500.0)
    assert config.min_odds_for(mm.MODEL_ID) == -200


def test_the_ev_floor_sits_just_under_the_smallest_ev_the_cut_admitted(art):
    floor = config.MODEL_OWN_EV_FLOOR[mm.MODEL_ID]
    assert floor == 0.04 == config.min_ev_for(mm.MODEL_ID)
    assert floor < art["replay"]["by_season"]["2023-2025"]["ev_min"] < floor + 0.005


def test_the_old_classifier_stays_paused_and_is_another_model():
    assert "ncaaf_moneyline" in config.PAUSED_MODELS
    assert config.ACTION_THRESHOLDS["ncaaf_moneyline"] == {"min_prob": 0.62, "min_edge": 0.08}
    assert config.MODEL_MIN_ODDS["ncaaf_moneyline"] == -250
    assert config.MODELS["ncaaf_moneyline"][:2] == ("NCAAF", "h2h")


def test_the_pinned_books_are_the_ones_config_fetches_and_decides_at(monkeypatch):
    """The model pins its books so an environment override cannot change who is
    in the consensus. This holds them to config's own defaults."""
    for var in ("LINE_SHOP_BOOKMAKERS", "BEST_LINE_BOOKMAKERS", "BEST_LINE_EXCLUDE_BOOKMAKERS"):
        assert not os.environ.get(var), f"{var} is set in this environment"
    assert set(mm.CONS_BOOKS) == set(config.LINE_SHOP_BOOKMAKERS) and len(mm.CONS_BOOKS) == 10
    assert set(mm.DECIDING_BOOKS) == set(config.BEST_LINE_BOOKMAKERS) and len(mm.DECIDING_BOOKS) == 6
    assert not set(mm.DECIDING_BOOKS) & set(config.STATE_LIMITED_BOOKMAKERS)
    assert list(mm.CLOSE_PRIORITY) == config.NCAAF_LINE_BOOKMAKER_PRIORITY[:4]


def test_the_artifact_is_for_2026_and_holds_the_replay_that_matched_the_research(art):
    assert (art["kind"], art["model_id"], art["season"], art["prior_season"]) == \
        (mm.ARTIFACT_KIND, mm.MODEL_ID, 2026, 2025)
    assert (art["check_hour_utc"], art["window_min"], art["min_lead_min"]) == (14, 60, 5)
    assert (art["cut"], art["min_price"], art["min_other_books"]) == (0.02, -200, 3)
    assert art["isum_range"] == [1.0, 1.15] and art["max_abs_line"] == 70.0
    # the research printed: 10,123 games, offset -0.138
    assert art["table_train_games"] == 10123 and art["table_train_seasons"] == [2014, 2025]
    assert round(art["offset"], 3) == -0.138
    assert art["table"]["pmf"].shape == (len(md.GRID), len(md.KK))
    # Rebuilt 2026-11-13 on six deciding books: Hard Rock left them (mike: it
    # cannot be bet in Massachusetts). The research chose from seven, so 265
    # of its 311 bets replay exactly and the rest were games Hard Rock priced
    # best, which now bet at the next book or not at all.
    chk = art["research_check"]
    assert (chk["research_bets"], chk["replay_bets"], chk["same_game_side_book_price"]) == (311, 287, 265)
    assert chk["replay_only"] == [] and chk["max_abs_edge_diff"] == 0.0
    r = art["replay"]["by_season"]
    assert (r["2023-2025"]["bets"], r["2023-2025"]["record"], r["2023-2025"]["units"]) == (287, "112-175", 10.57)
    assert [(r[s]["bets"], r[s]["units"]) for s in ("2023", "2024", "2025")] == \
        [(140, -2.77), (72, 11.94), (75, 1.41)]
    assert (r["2023-2025"]["price_min"], r["2023-2025"]["price_median"], r["2023-2025"]["price_max"]) == \
        (110.0, 145.0, 430.0)
    assert r["2023-2025"]["favourites"] == 0 and r["2023-2025"]["road_teams"] == 273
    assert art["replay"]["control_offset_zero"]["bets"] == 180
    assert art["replay"]["control_offset_zero"]["units"] == -14.16
    assert art["replay"]["control_road_teams_in_price_range"]["bets"] == 817
    assert art["replay"]["control_road_teams_in_price_range"]["units"] == 5.92


def test_an_artifact_built_on_other_books_or_of_another_kind_is_refused(tmp_path):
    raw = json.loads((mm.ROOT / mm.ARTIFACT_PATH).read_text(encoding="utf-8"))
    bad = dict(raw, consensus_books=raw["consensus_books"][:-1])
    p = tmp_path / "a.json"
    p.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError, match="built on books"):
        mm.load_artifact(p)
    p.write_text(json.dumps(dict(raw, kind="ncaab_spread_market")), encoding="utf-8")
    with pytest.raises(ValueError, match="not an ncaaf_moneyline_market artifact"):
        mm.load_artifact(p)


# ── when ─────────────────────────────────────────────────────────────────────

def test_the_check_is_14z_on_the_games_eastern_date():
    # A night game: 00:30 UTC on the 15th is 7:30pm Eastern on the 14th.
    assert mm.eastern_date("2026-11-15T00:30:00Z") == "2026-11-14"
    assert mm.eastern_date(pd.Timestamp("2026-11-14 17:00", tz="UTC")) == "2026-11-14"
    assert mm.check_instant("2026-11-14") == datetime(2026, 11, 14, 14, tzinfo=UTC)
    # the same clock hour in summer time: 14:00 UTC, never an Eastern hour
    assert mm.check_instant("2026-09-05") == datetime(2026, 9, 5, 14, tzinfo=UTC)


def test_a_game_kicking_off_within_five_minutes_of_14z_is_not_priced():
    assert mm.too_close(INSTANT + pd.Timedelta(minutes=4), INSTANT)
    assert not mm.too_close(INSTANT + pd.Timedelta(minutes=5), INSTANT)


# ── the consensus ────────────────────────────────────────────────────────────

def test_the_consensus_is_the_median_home_line_over_the_spreads_that_count():
    sp = [("g", "draftkings", 20, -3.0, -110.0, -110.0), ("g", "fanduel", 20, -3.5, -110.0, -110.0),
          ("g", "betmgm", 20, -3.5, -112.0, -108.0), ("g", "pinnacle", 20, -4.0, -105.0, -105.0),
          ("g", "bovada", 20, -6.0, -110.0, -110.0)]
    m = mm.mark(mm.quotes_at(_rows([]), _rows(sp)))
    assert set(m["cons"]) == {-3.5} and set(m["n_ok"]) == {5}
    assert m["sp_ok"].all()


def test_a_spread_counts_only_with_its_line_both_prices_a_line_within_70_and_a_sane_overround():
    sp = _spreads() + [
        ("g", "fanatics", 20, -70.5, -110.0, -110.0),        # line beyond 70
        ("g", "hardrockbet", 20, -3.5, 105.0, 105.0),        # implied sum 0.976: under 1.00
        ("g", "williamhill_us", 20, -3.5, -150.0, -150.0),   # implied sum 1.20: over 1.15
        ("g", "pinnacle", 20, -70.0, -110.0, -110.0),        # exactly 70 counts
    ]
    m = mm.mark(mm.quotes_at(_rows([]), _rows(sp))).set_index("bookmaker")
    assert not m.loc[["fanatics", "hardrockbet", "williamhill_us"], "sp_ok"].any()
    assert m.loc["pinnacle", "sp_ok"] and set(m["n_ok"]) == {5}
    # four at -3.5 and one at -70: the median is still -3.5
    assert set(m["cons"]) == {-3.5}


def test_a_spread_row_with_a_price_missing_is_no_quote_at_all():
    sp = _spreads() + [("g", "fanatics", 20, -3.5, -110.0, None)]
    q = mm.quotes_at(_rows([]), _rows(sp))
    assert "fanatics" not in set(q["bookmaker"])


# ── the moneylines priced ────────────────────────────────────────────────────

def test_a_moneyline_is_priced_only_when_its_implied_chances_sum_to_100_to_115():
    ml = [("g", "draftkings", 10, None, -150.0, 130.0),      # 0.600 + 0.435 = 1.035
          ("g", "fanduel", 10, None, -150.0, 160.0),         # 0.600 + 0.385 = 0.985
          ("g", "betmgm", 10, None, -220.0, -120.0)]         # 0.688 + 0.545 = 1.233
    m = mm.mark(mm.quotes_at(_rows(ml), _rows(_spreads()))).set_index("bookmaker")
    assert m.loc["draftkings", "ml_ok"] and not m.loc["fanduel", "ml_ok"] and not m.loc["betmgm", "ml_ok"]


def test_a_favourite_alone_against_two_other_books_is_dropped_and_against_one_is_kept(art):
    ml = [("g", "draftkings", 10, None, -150.0, 130.0), ("g", "pinnacle", 10, None, -155.0, 140.0),
          ("g", "betrivers", 10, None, 120.0, -140.0)]                 # away favourite, alone
    m = mm.mark(mm.quotes_at(_rows(ml), _rows(_spreads()))).set_index("bookmaker")
    assert m.loc["betrivers", "fav_alone"] and not m.loc["draftkings", "fav_alone"]
    # Pinnacle is never bet, and it still counts as one of the other books
    (d,) = _decide(art, ml, _spreads())
    assert d.best["bookmaker"] == "draftkings"
    m = mm.mark(mm.quotes_at(_rows(ml[:1] + ml[2:]), _rows(_spreads()))).set_index("bookmaker")
    assert not m["fav_alone"].any()                                     # one other book: kept


def test_even_prices_count_as_the_away_side_being_favourite():
    """The research's coding (fav_home = home price shorter than away), ported
    as written: a pick'em moneyline sits with the away favourites."""
    ml = [("g", "draftkings", 10, None, -110.0, -110.0), ("g", "fanduel", 10, None, -125.0, 105.0),
          ("g", "betmgm", 10, None, -125.0, 105.0)]
    m = mm.mark(mm.quotes_at(_rows(ml), _rows(_spreads()))).set_index("bookmaker")
    assert m.loc["draftkings", "fav_alone"] and not m.loc["fanduel", "fav_alone"]


# ── the fair chance and the pick ─────────────────────────────────────────────

def test_the_fair_chance_is_the_margin_tables_at_minus_the_consensus_plus_the_offset(art):
    assert _ph(art, -3.5) > 0.5 > _ph(art, 3.5)
    (d,) = _decide(art, _moneylines(art), _spreads())
    assert d.status == "bets" and d.best["side"] == "home" and d.best["bookmaker"] == "betrivers"
    assert d.best["prob"] == pytest.approx(_ph(art, -3.5), abs=1e-12)
    assert d.best["mu"] == pytest.approx(3.5 + art["offset"], abs=1e-12)
    assert d.best["edge"] == pytest.approx(_ph(art, -3.5) - _implied(d.best["price"]), abs=1e-12)
    assert d.best["cons"] == -3.5 and d.best["n_ok"] == 4
    # the offset is part of the price: without it the same quotes give another chance
    q = mm.quotes_at(_rows(_moneylines(art)), _rows(_spreads()))
    (z,) = mm.decide(["g"], q, art["table"], 0.0)
    assert z.best["prob"] != d.best["prob"] and z.best["mu"] == 3.5


def test_the_away_side_is_bet_at_one_minus_the_home_chance(art):
    (d,) = _decide(art, _moneylines(art, side="away"), _spreads())
    assert d.status == "bets" and d.best["side"] == "away"
    assert d.best["prob"] == pytest.approx(1 - _ph(art, -3.5), abs=1e-12)
    assert d.best["edge"] == pytest.approx(1 - _ph(art, -3.5) - _implied(d.best["price"]), abs=1e-12)
    assert 0.03 < d.best["edge"] < 0.05
    assert d.best["link"] == "betrivers-away"


def test_a_minus_201_side_is_never_bet_and_minus_200_is(art):
    cons = -7.5
    p = _ph(art, cons)
    assert p - _implied(-200.0) > 0.02                # the home side at -200 clears the cut
    sp = _spreads(line=cons)
    ml = [("g", b, 10, None, -260.0, 190.0) for b in BOOKS4[:3]]
    (d,) = _decide(art, ml + [("g", "betrivers", 10, None, -201.0, 170.0)], sp)
    assert d.best is None or d.best["side"] == "away"
    assert d.status != "bets"
    (d,) = _decide(art, ml + [("g", "betrivers", 10, None, -200.0, 170.0)], sp)
    assert d.status == "bets" and (d.best["side"], d.best["price"]) == ("home", -200.0)


def test_a_game_whose_best_side_is_too_short_is_decided_on_its_next_best_side(art):
    cons = -7.5
    p = _ph(art, cons)
    ml = [("g", b, 10, None, -260.0, 190.0) for b in BOOKS4[:3]]
    # betrivers' home price is the largest edge of the game and too short to
    # bet; fanatics' away price is the next one.
    away = _american(1 - p - 0.03)
    ml += [("g", "betrivers", 10, None, -205.0, 170.0), ("g", "fanatics", 10, None, -340.0, away)]
    (d,) = _decide(art, ml, _spreads(line=cons))
    assert d.status == "bets" and (d.best["bookmaker"], d.best["side"]) == ("fanatics", "away")


def test_the_largest_edge_wins_and_a_tie_goes_to_the_book_name(art):
    p = _ph(art, -3.5)
    home = _american(p - 0.04)
    ml = [_at("draftkings", p + 0.02, 1 - p + 0.02), _at("fanduel", p - 0.03, 1 - p + 0.07),
          _at("hardrockbet", p - 0.04, 1 - p + 0.07), _at("betmgm", p - 0.04, 1 - p + 0.07)]
    (d,) = _decide(art, ml, _spreads())
    assert d.status == "bets" and d.best["bookmaker"] == "betmgm" and d.best["price"] == home
    # and the larger edge beats the earlier name
    (d,) = _decide(art, ml + [_at("williamhill_us", p - 0.05, 1 - p + 0.08)], _spreads())
    assert d.best["bookmaker"] == "williamhill_us"


def test_the_edge_must_be_above_the_cut(art):
    (d,) = _decide(art, _moneylines(art, edge=0.04), _spreads())
    edge = d.best["edge"]
    assert d.status == "bets" and edge > 0.02
    (d,) = _decide(art, _moneylines(art, edge=0.04), _spreads(), cut=edge)      # not above
    assert d.status == "below_cut" and d.best["edge"] == edge
    (d,) = _decide(art, _moneylines(art, edge=0.04), _spreads(), cut=edge - 1e-9)
    assert d.status == "bets"


def test_a_bet_needs_three_other_books_in_the_consensus(art):
    (d,) = _decide(art, _moneylines(art), _spreads(books=BOOKS4[:3]))
    assert d.status == "too_few_books" and d.best["n_ok"] == 3 and d.best["edge"] > 0.02
    (d,) = _decide(art, _moneylines(art), _spreads(books=BOOKS4))
    assert d.status == "bets" and d.best["n_ok"] == 4
    # the count is of spreads in the consensus, whoever posts them
    (d,) = _decide(art, _moneylines(art), _spreads(books=("pinnacle", "bovada", "betparx", "fanatics")))
    assert d.status == "bets"


def test_pinnacle_bovada_and_betparx_are_read_and_never_bet(art):
    p = _ph(art, -3.5)
    ml = _moneylines(art, best=None)
    ml += [_at(b, p - 0.06, 1 - p + 0.09) for b in ("pinnacle", "bovada", "betparx")]
    m = mm.mark(mm.quotes_at(_rows(ml), _rows(_spreads()))).set_index("bookmaker")
    assert m.loc[["pinnacle", "bovada", "betparx"], "ml_ok"].all()      # priced, and still not bet
    (d,) = _decide(art, ml, _spreads())
    assert d.status == "below_cut" and d.best["bookmaker"] in mm.DECIDING_BOOKS
    assert {"pinnacle", "bovada", "betparx"} <= {x["book"] for x in d.quotes}


def test_quotes_outside_the_hour_before_14z_are_not_read(art):
    p = _ph(art, -3.5)
    ml = _moneylines(art, best=None) + [
        _at("fanatics", p - 0.05, 1 - p + 0.08, mins=61),        # 61 minutes old
        _at("hardrockbet", p - 0.05, 1 - p + 0.08, mins=-1),     # stamped after 14:00
    ]
    (d,) = _decide(art, ml, _spreads())
    assert d.status == "below_cut"
    assert not {"fanatics", "hardrockbet"} & {x["book"] for x in d.quotes}
    (d,) = _decide(art, ml[:-2] + [_at("fanatics", p - 0.05, 1 - p + 0.08, mins=60)], _spreads())
    assert d.status == "bets" and d.best["bookmaker"] == "fanatics"         # exactly an hour: read


def test_a_books_newest_row_in_the_hour_is_its_quote(art):
    p = _ph(art, -3.5)
    ml = _moneylines(art, best=None)
    old, new = _at("fanatics", p - 0.05, 1 - p + 0.08, mins=40), _at("fanatics", p + 0.02, 1 - p + 0.02, mins=5)
    (d,) = _decide(art, ml + [old], _spreads())
    assert d.status == "bets" and d.best["bookmaker"] == "fanatics"
    (d,) = _decide(art, ml + [old, new], _spreads())
    assert d.status == "below_cut"                    # the older, better price is gone


def test_a_book_no_longer_bettable_is_not_replaced_by_the_next(art):
    ml = _moneylines(art, best="betrivers", edge=0.05)
    p = _ph(art, -3.5)
    ml[1] = _at("fanduel", p - 0.03, 1 - p + 0.06)                        # the next best, also a bet
    (d,) = _decide(art, ml, _spreads(), bettable=tuple(b for b in mm.DECIDING_BOOKS if b != "betrivers"))
    assert d.status == "book_not_bettable" and d.best["bookmaker"] == "betrivers"


def test_a_game_with_no_moneyline_no_consensus_or_no_side_long_enough_says_which(art):
    (d,) = _decide(art, [("g", "pinnacle", 10, None, -150.0, 130.0)], _spreads())
    assert d.status == "no_quotes"                    # no DECIDING book quoted a moneyline
    (d,) = _decide(art, _moneylines(art), [])
    assert d.status == "no_consensus" and d.best is None
    (d,) = _decide(art, [("g", b, 10, None, -150.0, 160.0) for b in BOOKS4], _spreads())
    assert d.status == "no_clean_quote"               # every moneyline's overround is out of range
    (d,) = _decide(art, [], [], games=("g",))
    assert d.status == "no_quotes" and d.quotes == []


def test_the_decision_keeps_every_books_quote_and_draftkings_as_the_reference(art):
    (d,) = _decide(art, _moneylines(art), _spreads() + [("g", "pinnacle", 20, -3.5, -105.0, -105.0)])
    by = {x["book"]: x for x in d.quotes}
    assert set(by) == set(BOOKS4) | {"pinnacle"}
    assert by["pinnacle"]["flags"] == ["no_moneyline"] and by["pinnacle"]["in_consensus"] is True
    assert by["betrivers"]["p1"] == d.best["price"] and by["betrivers"]["spread"] == -3.5
    assert d.dk == {"p1": by["draftkings"]["p1"], "p2": by["draftkings"]["p2"],
                    "link1": "draftkings-home", "link2": "draftkings-away"}


# ── the card's rows ──────────────────────────────────────────────────────────

GAMES = {"g": {"season": 2026, "game_date": "2026-11-14", "tip": KICK.to_pydatetime(),
               "instant": INSTANT.to_pydatetime(), "commence_time": "2026-11-14T20:30:00Z",
               "home": "Ohio State", "away": "Michigan"}}


def _bet(status="bets", book="betrivers", side="away", price=150.0, prob=0.44, dk=None):
    best = {"game_id": "g", "bookmaker": book, "side": side, "price": price, "prob": prob,
            "edge": prob - _implied(price), "cons": -3.5, "n_ok": 8, "mu": 3.36, "ph": 1 - prob,
            "link": f"{book}-{side}"}
    return mm.Decision("g", status, "x", best=best, quotes=[], dk=dk)


def test_a_bet_row_is_a_moneyline_at_the_bet_books_price_and_the_flat_stake():
    import scripts.ncaaf_moneyline_card as card
    dk = {"p1": -170.0, "p2": 140.0, "link1": "dk-h", "link2": "dk-a"}
    (row,), refused = card.pick_rows([_bet(dk=dk)], GAMES, 1000.0)
    assert not refused
    assert (row["model_id"], row["sport"], row["game_date"]) == ("ncaaf_moneyline_market", "NCAAF", "2026-11-14")
    assert row["pick_label"] == "Michigan ML" and row["pick_side"] == "away"
    assert row["scored_line"] is None and row["line_book"] is None
    assert row["dk_odds"] == 140.0 and row["dk_bet_link"] == "dk-a"
    assert row["edge"] == round(0.44 - 100 / 240, 4)
    assert (row["decision_book"], row["decision_odds"], row["best_book"], row["best_odds"]) == \
        ("betrivers", 150.0, "betrivers", 150.0)
    assert row["decision_edge"] == round(0.44 - 0.4, 4) == row["best_edge"]
    assert row["model_probability"] == row["model_probability_cal"] == 0.44
    assert row["best_bet_link"] == "betrivers-away" and row["signal_type"] == "BET"
    assert row["kelly_fraction"] > 0
    # the flat stake: the row carries no stake of its own
    assert "stake_units" not in row and "stake_units" not in card._COLS


def test_with_no_priced_draftkings_moneyline_the_reference_is_empty():
    import scripts.ncaaf_moneyline_card as card
    (row,), _ = card.pick_rows([_bet(side="home", price=-150.0, prob=0.64)], GAMES, 1000.0)
    assert row["pick_label"] == "Ohio State ML" and row["pick_side"] == "home"
    assert row["dk_odds"] is None and row["dk_implied_prob"] == 0.0 and row["edge"] == 0.0


def test_a_game_priced_and_not_bet_is_a_row_with_no_stake():
    import scripts.ncaaf_moneyline_card as card
    for status in ("below_cut", "too_few_books"):
        (row,), refused = card.pick_rows([_bet(status=status)], GAMES, 1000.0)
        assert (row["signal_type"], row["kelly_fraction"], row["recommended_bet"]) == ("NONE", 0.0, 0.0)
        assert not refused
    for status in ("book_not_bettable", "no_clean_quote", "missed", "other_model_bet"):
        assert card.pick_rows([_bet(status=status)], GAMES, 1000.0) == ([], {})


def test_an_ev_under_the_floor_is_refused():
    import scripts.ncaaf_moneyline_card as card
    floor = config.MODEL_OWN_EV_FLOOR[mm.MODEL_ID]
    prob = (1 + floor - 0.002) / float(mm.dec(-150.0))      # EV just under the floor at -150
    assert prob - _implied(-150.0) > 0.02                   # and still over the edge cut
    rows, refused = card.pick_rows([_bet(side="home", price=-150.0, prob=prob)], GAMES, 1000.0)
    assert [(r["signal_type"], r["kelly_fraction"]) for r in rows] == [("NONE", 0.0)] and "g" in refused
    prob = (1 + floor + 0.002) / float(mm.dec(-150.0))
    rows, refused = card.pick_rows([_bet(side="home", price=-150.0, prob=prob)], GAMES, 1000.0)
    assert [r["signal_type"] for r in rows] == ["BET"] and not refused


def test_a_price_shorter_than_the_floor_is_refused_here_too():
    import scripts.ncaaf_moneyline_card as card
    rows, refused = card.pick_rows([_bet(side="home", price=-210.0, prob=0.75)], GAMES, 1000.0)
    assert [r["signal_type"] for r in rows] == ["NONE"] and refused == {"g": "below_price_floor:-210"}


def test_every_python_reader_treats_the_id_as_a_moneyline():
    from tracking.paper_tracker import _RULE_MODEL_MARKETS, _compute_result, _market_for_pick
    from tracking.pick_integrity import pick_problems
    assert _RULE_MODEL_MARKETS[mm.MODEL_ID] == "h2h" == _market_for_pick(mm.MODEL_ID)
    # settles on home_win, overtime included; a NULL scored_line is fine
    assert _compute_result("away", "h2h", 27, 30, 0, None, 1, 150, None, None, 10.0)[0] == "WIN"
    assert _compute_result("away", "h2h", 31, 30, 1, None, 1, 150, None, None, 10.0)[0] == "LOSS"
    assert pick_problems("Michigan ML", "away", None, mm.MODEL_ID, "Ohio State", "Michigan") == []
    assert pick_problems("Ohio State ML", "away", None, mm.MODEL_ID, "Ohio State", "Michigan")


def test_the_app_names_the_model_and_reads_it_as_a_moneyline():
    """The id has no 'spread' in it, so the app's substring rules already read
    it as a moneyline; it needs only its name."""
    lib = mm.ROOT / "mobile" / "src" / "lib"
    meta = (lib / "modelMeta.ts").read_text(encoding="utf-8")
    assert "ncaaf_moneyline_market: {\n    shortLabel: 'ML',\n    longLabel: 'NCAAF Moneyline'" in \
        meta.replace("\r\n", "\n")
    gen = (lib / "thresholds.generated.ts").read_text(encoding="utf-8")
    assert "ncaaf_moneyline_market: { min_prob: 0, min_edge: 0.02, min_odds: -200 }," in gen
    assert "spread" not in mm.MODEL_ID and "moneyline" in mm.MODEL_ID
    view = (mm.ROOT / "data" / "migrations" / "open_picks_view_2026_11_04.sql").read_text(encoding="utf-8")
    assert "WHEN 'ncaaf_moneyline_market' THEN 'NCAAF Moneyline'" in view


# ── the run ──────────────────────────────────────────────────────────────────

class _NullConn:
    def close(self):
        pass


def _wire(monkeypatch, art, slate, ledger=True, decided=(), ml=None, sp=None, spread_bet=()):
    import models.scorer as scorer
    import scripts.ncaaf_moneyline_card as card
    got = {}
    ml = ml if ml is not None else _moneylines(art)
    sp = sp if sp is not None else _spreads()
    monkeypatch.setattr(card, "get_connection", lambda: _NullConn())
    monkeypatch.setattr(card, "slate", lambda conn, now: slate)
    monkeypatch.setattr(card, "ledger_exists", lambda conn: ledger)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids: set(decided))
    monkeypatch.setattr(card, "side_model_bets", lambda conn, ids: set(spread_bet) & set(ids))
    monkeypatch.setattr(card, "ensure_decisions_table", lambda conn: None)

    def load_rows(conn, games, instant, market="spreads", window_min=None, books=None):
        got.setdefault("reads", []).append((market, instant, window_min, tuple(books)))
        return _rows(ml) if market == "h2h" else _rows(sp)
    monkeypatch.setattr(card.bq, "load_rows", load_rows)
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    monkeypatch.setattr(card, "publish", lambda conn, prows, decisions, hour, games, refused:
                        got.update(rows=prows, decisions=decisions, hour=hour) or (len(prows), len(decisions)))
    return card, got


def test_the_14z_run_decides_the_days_games_on_the_14z_quotes(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    at = datetime(2026, 11, 14, 14, tzinfo=UTC)
    assert out["bets"] == 1
    assert got["reads"] == [("h2h", at, 60, mm.CONS_BOOKS), ("spreads", at, 60, mm.CONS_BOOKS)]
    assert [d.status for d in got["decisions"]] == ["bets"]
    assert got["rows"][0]["decision_book"] == "betrivers"
    assert got["rows"][0]["pick_label"] == "Ohio State ML"


def test_a_run_before_14z_reads_no_odds(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 13, 5, tzinfo=UTC))
    assert out["decided"] == 0 and "reads" not in got and "decisions" not in got


def test_a_missed_14z_is_written_as_missed_never_bet_and_fails_the_run(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES))
    with pytest.raises(card.CardIncomplete, match="missed their 14:00 UTC decision"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["missed"] and got["rows"] == []
    assert "reads" not in got                      # no later quote was even read


def test_the_first_run_ever_records_a_game_it_never_had_a_chance_at_without_failing(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES), ledger=False)
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 18, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    assert d.status == "missed" and "had not run yet" in d.detail


def test_a_decided_game_is_never_decided_again(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES), decided=["g"])
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 40, tzinfo=UTC))
    assert out["decided"] == 0 and "reads" not in got
    card, got = _wire(monkeypatch, art, dict(GAMES), decided=["g"])
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 19, 5, tzinfo=UTC))   # no missed either


def test_a_game_the_spread_model_has_bet_is_recorded_and_not_priced(monkeypatch, art):
    """One game never carries two bets that cannot both win."""
    card, got = _wire(monkeypatch, art, dict(GAMES), spread_bet=["g"])
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert out["bets"] == 0 and "reads" not in got
    assert [d.status for d in got["decisions"]] == ["other_model_bet"] and got["rows"] == []
    # and a later hour does not call it missed
    card, got = _wire(monkeypatch, art, dict(GAMES), spread_bet=["g"])
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 16, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["other_model_bet"]


def test_the_other_side_models_are_the_two_spread_models_and_a_void_or_paused_bet_holds_nothing():
    import scripts.ncaaf_moneyline_card as card
    assert card.OTHER_SIDE_MODELS == ("ncaaf_spread", "ncaaf_spread_premium")
    assert all(config.MODELS[m][:2] == ("NCAAF", "spreads") for m in card.OTHER_SIDE_MODELS)
    seen = {}

    class Conn:
        def execute(self, sql, params):
            seen.update(sql=" ".join(sql.split()), params=params)
            return type("R", (), {"fetchall": lambda self: [("g",)]})()
    assert card.side_model_bets(Conn(), ["g", "h"]) == {"g"}
    assert "signal_type = 'BET'" in seen["sql"]
    assert "condition_status IS DISTINCT FROM 'VOID'" in seen["sql"]
    assert seen["params"] == (["ncaaf_spread", "ncaaf_spread_premium"], ["g", "h"], config.PAUSED_NOTE)


def test_two_rows_of_one_game_are_decided_once_on_the_row_that_holds_the_quotes(monkeypatch, art):
    twin = dict(GAMES["g"], game_date="2026-11-15")
    games = {"g": dict(GAMES["g"]), "g_twin": twin,
             "other": dict(GAMES["g"], home="Texas", away="Baylor")}
    ml = _moneylines(art) + _moneylines(art, gid="other", best=None) + _moneylines(art, gid="g_twin")[:1]
    sp = _spreads() + _spreads("other")
    card, got = _wire(monkeypatch, art, games, ml=ml, sp=sp)
    out = card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    status = {d.game_id: d.status for d in got["decisions"]}
    assert status == {"g": "bets", "g_twin": "duplicate_game", "other": "below_cut"}
    assert out["bets"] == 1 and [r["game_id"] for r in got["rows"] if r["signal_type"] == "BET"] == ["g"]


def test_one_game_is_the_same_two_teams_kicking_off_within_a_day():
    import scripts.ncaaf_moneyline_card as card
    a = dict(GAMES["g"])
    flipped = dict(a, home="Michigan", away="Ohio State", tip=a["tip"] + timedelta(hours=20))
    rematch = dict(a, tip=a["tip"] + timedelta(days=21))
    assert card.same_game_groups({"a": a, "b": flipped}) == [["a", "b"]]
    assert card.same_game_groups({"a": a, "c": rematch}) == []
    assert card.same_game_groups({"a": a, "d": dict(a, away="Penn State")}) == []


def test_no_moneyline_for_any_due_game_fails_the_run_after_writing(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES), ml=[])
    with pytest.raises(card.CardIncomplete, match="may have stopped"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["no_quotes"]


def test_an_artifact_for_another_season_fails_the_run(monkeypatch, art):
    card, got = _wire(monkeypatch, art, {"g": dict(GAMES["g"], season=2027)})
    with pytest.raises(card.CardIncomplete, match="artifact is for season 2026"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert "reads" not in got


def test_a_best_side_at_a_book_config_no_longer_lists_fails_the_run(monkeypatch, art):
    card, got = _wire(monkeypatch, art, dict(GAMES))
    monkeypatch.setattr(card.config, "BEST_LINE_BOOKMAKERS",
                        [b for b in card.config.BEST_LINE_BOOKMAKERS if b != "betrivers"])
    with pytest.raises(card.CardIncomplete, match="book_not_bettable"):
        card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert got["rows"] == []


def test_a_game_that_kicked_off_before_the_run_is_recorded_not_bet(monkeypatch, art):
    g = {"g": dict(GAMES["g"], tip=datetime(2026, 11, 14, 14, 3, tzinfo=UTC))}
    card, got = _wire(monkeypatch, art, g)
    card.run_card(do_publish=True, now=datetime(2026, 11, 14, 14, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["kicked_off"] and got["rows"] == []


def test_the_kill_switch_reads_nothing(monkeypatch):
    import scripts.ncaaf_moneyline_card as card
    monkeypatch.setenv("RUN_NCAAF_MONEYLINE_CARD", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.run_card(do_publish=True)["off"] is True


def test_an_incomplete_run_exits_non_zero(monkeypatch):
    import scripts.ncaaf_moneyline_card as card
    monkeypatch.setattr(card, "run_card", lambda do_publish=False: (_ for _ in ()).throw(
        card.CardIncomplete("x")))
    with pytest.raises(SystemExit) as e:
        card.main(["--publish"])
    assert e.value.code == 1


# ── the job ──────────────────────────────────────────────────────────────────

def test_the_job_runs_hourly_at_five_past_utc_all_year_and_is_watched(monkeypatch):
    import scheduler
    from tests.test_nba_prop_window import _fires, _jobs
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaaf_moneyline_card"]
    assert job.max_instances == 1 and job.coalesce is True
    for start in (datetime(2026, 11, 14, 0, 0, tzinfo=UTC),     # standard time
                  datetime(2026, 9, 5, 0, 0, tzinfo=UTC)):      # summer time
        fires = _fires(job, start, start + timedelta(hours=23, minutes=59))
        utc = [f.astimezone(UTC) for f in fires]
        assert len(utc) == 24 and all(f.minute == 5 for f in utc) and 14 in {f.hour for f in utc}
    assert "ncaaf_moneyline_card" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaaf_moneyline_card"] == 150


def test_the_job_runs_the_card_and_publishes_and_a_failure_raises(monkeypatch):
    import scheduler
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    scheduler.run_ncaaf_moneyline_card()
    assert ran[0][-2:] == ["scripts.ncaaf_moneyline_card", "--publish"] and pub == ["ncaaf-moneyline-card"]
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaaf_moneyline_card()
    assert pub == ["ncaaf-moneyline-card"] * 2    # a failed run still publishes what it wrote


def test_the_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    import scripts.ncaaf_moneyline_card as card
    assert card.DECISIONS_TABLE == "ncaaf_moneyline_decisions" in WORKER_ONLY_TABLES


# ── the build ────────────────────────────────────────────────────────────────

def _odds(rows):
    cols = ["game_id", "market", "bookmaker", "snapshot_type", "snapshot_at", "created_at", "source",
            "home_price", "away_price", "spread_home"]
    o = pd.DataFrame(rows, columns=cols)
    o["order"] = np.arange(len(o), dtype="int64")
    return o


def _games(rows):
    g = pd.DataFrame(rows, columns=["game_id", "season", "game_date", "home_team", "away_team",
                                    "home_score", "away_score", "commence_time"])
    g["kick"] = pd.to_datetime(g["commence_time"], utc=True)
    g["margin"] = g["home_score"] - g["away_score"]
    g["et_date"] = g["kick"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
    return g


def test_the_closing_spread_is_the_first_cfbd_provider_that_has_one():
    import scripts.ncaaf_moneyline_market_build as b
    o = _odds([
        ("a", "spreads", "cfbd_bovada", "open", "x", "c", None, None, None, "-6.5"),
        ("a", "spreads", "cfbd_draftkings", "open", "x", "c", None, None, None, "-7"),
        ("b", "spreads", "cfbd_teamrankings", "open", "x", "c", None, None, None, "3"),
        ("b", "spreads", "cfbd_consensus", "open", "x", "c", None, None, None, "2.5"),
        ("c", "spreads", "cfbd_draftkings", "open", "x", "c", None, None, None, None),
        ("c", "spreads", "cfbd_bovada", "open", "x", "c", None, None, None, "1"),
        ("d", "spreads", "draftkings", "open", "x", "c", None, "-110", "-110", "-9"),     # not CFBD's
        ("e", "totals", "cfbd_draftkings", "open", "x", "c", None, None, None, "55"),     # not a spread
    ])
    assert b.closing_spreads(o).to_dict() == {"a": -7.0, "b": 2.5, "c": 1.0}


def test_an_unscored_odds_row_takes_its_one_scored_twins_result():
    import scripts.ncaaf_moneyline_market_build as b
    g = _games([
        # a night game stored twice: the odds row (Eastern date, no score) and CFBD's (UTC date)
        ("odds_night", 2025, "2025-10-04", "Utah", "BYU", None, None, "2025-10-05T02:15:00Z"),
        ("cfbd_night", 2025, "2025-10-05", "Utah", "BYU", 20.0, 27.0, "2025-10-05T02:15:00Z"),
        # a neutral-site game the feed lists the other way round
        ("odds_flip", 2025, "2025-12-13", "Navy", "Army", None, None, "2025-12-13T20:00:00Z"),
        ("cfbd_flip", 2025, "2025-12-13", "Army", "Navy", 17.0, 10.0, "2025-12-13T20:00:00Z"),
        # the same two teams a season earlier: not a twin
        ("odds_old", 2025, "2025-09-06", "Iowa", "Iowa State", None, None, "2025-09-06T19:30:00Z"),
        ("cfbd_old", 2024, "2024-09-07", "Iowa", "Iowa State", 19.0, 20.0, "2024-09-07T19:30:00Z"),
        # no odds: stays unscored whatever else matches
        ("no_odds", 2025, "2025-10-04", "Utah", "BYU", None, None, "2025-10-05T02:15:00Z"),
        # the same two teams ten weeks earlier in the SAME season: a rematch, not a twin
        ("odds_rematch", 2025, "2025-12-06", "Georgia", "Alabama", None, None, "2025-12-06T21:00:00Z"),
        ("cfbd_first", 2025, "2025-09-27", "Georgia", "Alabama", 21.0, 24.0, "2025-09-27T23:30:00Z"),
    ])
    g["close_spread"] = g["game_id"].map({"cfbd_night": -3.5, "cfbd_flip": -6.5})
    out = b.with_twins(g, {"odds_night", "odds_flip", "odds_old", "odds_rematch"}).set_index("game_id")
    assert pd.isna(out.loc["odds_rematch", "margin"]) and out.loc["odds_rematch", "twin_of"] is None
    assert (out.loc["odds_night", "margin"], out.loc["odds_night", "twin_of"],
            out.loc["odds_night", "close_spread"]) == (-7.0, "cfbd_night", -3.5)
    assert (out.loc["odds_flip", "margin"], out.loc["odds_flip", "twin_of"],
            out.loc["odds_flip", "close_spread"]) == (-7.0, "cfbd_flip", 6.5)
    assert pd.isna(out.loc["odds_old", "margin"]) and out.loc["odds_old", "twin_of"] is None
    assert pd.isna(out.loc["no_odds", "margin"])
    # two scored rows that both match: the row is left unscored, not guessed
    g2 = pd.concat([g, _games([("cfbd_night2", 2025, "2025-10-04", "BYU", "Utah", 27.0, 20.0,
                                "2025-10-05T02:15:00Z")])], ignore_index=True)
    out2 = b.with_twins(g2, {"odds_night"}).set_index("game_id")
    assert pd.isna(out2.loc["odds_night", "margin"])


def test_a_seasons_table_is_fitted_on_earlier_seasons_own_scores_in_date_then_id_order(monkeypatch):
    import scripts.ncaaf_moneyline_market_build as b
    g = _games([                       # stored in neither date nor id order
        ("same_season", 2024, "2024-09-07", "A", "B", 10.0, 7.0, "2024-09-07T19:00:00Z"),
        ("b_later", 2023, "2023-09-09", "E", "F", 28.0, 24.0, "2023-09-09T19:00:00Z"),
        ("twin_row", 2023, "2023-09-23", "A", "F", 7.0, 0.0, "2023-09-23T19:00:00Z"),
        ("a_later", 2023, "2023-09-09", "C", "D", 14.0, 21.0, "2023-09-09T19:00:00Z"),
        ("no_close", 2023, "2023-09-16", "A", "D", 3.0, 0.0, "2023-09-16T19:00:00Z"),
        ("z_first", 2023, "2023-09-02", "A", "B", 30.0, 20.0, "2023-09-02T19:00:00Z"),
    ])
    g["close_spread"] = g["game_id"].map({"z_first": -7.0, "a_later": 3.0, "b_later": -6.5,
                                          "same_season": -3.0, "twin_row": -1.0})
    g["twin_of"] = [None, None, "somewhere", None, None, None]
    assert list(b.train_rows(g, 2024)["game_id"]) == ["z_first", "a_later", "b_later"]
    assert list(b.train_rows(g, 2025)["game_id"]) == ["z_first", "a_later", "b_later", "same_season"]
    seen = {}
    monkeypatch.setattr(b.md, "fit", lambda margin, mu: seen.update(margin=list(margin), mu=list(mu)) or {})
    table, offset, n = b.table_for(g, 2024)
    assert seen == {"margin": [10, -7, 4], "mu": [7.0, -3.0, 6.5]} and n == 3
    assert offset == pytest.approx(((10 - 7) + (-7 + 3) + (4 - 6.5)) / 3)


def _pull(game, book, market, stamp, batch, hp, ap, line=None, source="odds_api_historical|x", stype="open"):
    return (game, market, book, stype, stamp, batch, source, hp, ap, line)


def test_the_replay_reads_the_game_day_morning_pull_and_each_books_latest_one():
    import scripts.ncaaf_moneyline_market_build as b
    # 8pm Eastern on the 15th: the evening pull of game day is before kickoff too
    g = _games([("g", 2025, "2025-11-15", "Ohio State", "Michigan", 30.0, 27.0, "2025-11-16T01:00:00Z")])
    g["close_spread"] = -3.5
    g["twin_of"] = None
    day = "2025-11-15"
    o = _odds([
        # the morning pull, bought twice: the later batch is the one read
        _pull("g", "draftkings", "h2h", f"{day}T13:54:00Z", "batch1", "-160", "140"),
        _pull("g", "draftkings", "h2h", f"{day}T13:55:00Z", "batch2", "-165", "145"),
        _pull("g", "draftkings", "spreads", f"{day}T13:55:00Z", "batch2", "-110", "-110", "-3.5"),
        # fanduel is in the first batch only: its latest morning pull is that one
        _pull("g", "fanduel", "h2h", f"{day}T13:54:00Z", "batch1", "-170", "150"),
        # the later batch holds only a total for betmgm: its moneyline of the
        # earlier batch is not read (the research took the later pull's row)
        _pull("g", "betmgm", "h2h", f"{day}T13:54:00Z", "batch1", "-150", "130"),
        _pull("g", "betmgm", "totals", f"{day}T13:55:00Z", "batch2", None, None),
        # the morning and the evening before, game-day evening (before kickoff),
        # an in-play row, another source, a book not read
        _pull("g", "betrivers", "h2h", "2025-11-14T13:55:00Z", "batchM", "-185", "160"),
        _pull("g", "betrivers", "h2h", "2025-11-14T22:55:00Z", "batch0", "-180", "155"),
        _pull("g", "betrivers", "h2h", f"{day}T22:55:00Z", "batch3", "-190", "160"),
        _pull("g", "hardrockbet", "h2h", f"{day}T13:55:00Z", "batch2", "-175", "150", stype="in_play"),
        _pull("g", "fanatics", "h2h", f"{day}T13:55:00Z", "batch4", "-175", "150", source=None),
        _pull("g", "espnbet", "h2h", f"{day}T13:55:00Z", "batch2", "-175", "150"),
    ])
    ml, sp, games = b.morning_rows(g, o, [2025])
    assert sorted(zip(ml["bookmaker"], ml["p1"], ml["p2"])) == \
        [("draftkings", -165.0, 145.0), ("fanduel", -170.0, 150.0)]
    assert list(zip(sp["bookmaker"], sp["line"])) == [("draftkings", -3.5)]
    assert list(games["game_id"]) == ["g"]
    assert set(ml["instant"]) == {pd.Timestamp("2025-11-15 14:00", tz="UTC")}
    assert set(ml["tip"]) == {pd.Timestamp("2025-11-16 01:00", tz="UTC")}


def test_the_replay_keeps_one_odds_row_per_real_game_and_only_scored_games():
    import scripts.ncaaf_moneyline_market_build as b
    g = _games([
        ("cfbd", 2025, "2025-11-16", "Utah", "BYU", 20.0, 27.0, "2025-11-16T02:15:00Z"),
        ("odds_a", 2025, "2025-11-15", "Utah", "BYU", None, None, "2025-11-16T02:15:00Z"),
        ("odds_b", 2025, "2025-11-15", "BYU", "Utah", None, None, "2025-11-16T02:15:00Z"),
        ("unscored", 2025, "2025-11-15", "Texas", "Baylor", None, None, "2025-11-15T20:00:00Z"),
    ])
    g["close_spread"] = np.nan
    day = "2025-11-15"
    rows = [_pull(gid, book, "h2h", f"{day}T13:55:00Z", "batch", "-150", "130")
            for gid, books in (("odds_a", ("draftkings", "fanduel")), ("odds_b", ("draftkings",)),
                               ("unscored", ("draftkings",)))
            for book in books]
    o = _odds(rows)
    g = b.with_twins(g, set(o["game_id"]))
    ml, sp, games = b.morning_rows(g, o, [2025])
    assert set(ml["game_id"]) == {"odds_a"} and list(games["game_id"]) == ["odds_a"]


def test_the_bet_check_compares_game_side_book_and_price(tmp_path):
    import scripts.ncaaf_moneyline_market_build as b
    research = pd.DataFrame({"game_id": ["a", "b", "c", "d"], "bookmaker": ["betmgm"] * 4,
                             "side": [2, 1, 2, 2], "price": [150.0, -120.0, 200.0, 130.0],
                             "edge": [0.03, 0.025, 0.04, 0.021]})
    p = tmp_path / "bets.pkl"
    pd.to_pickle({"keep": {0.02: research}}, p)
    mine = pd.DataFrame({"game_id": ["a", "b", "c", "e"], "bookmaker": ["betmgm", "betmgm", "fanduel", "betmgm"],
                         "side": ["away", "away", "away", "home"], "price": [150.0, -120.0, 200.0, 110.0],
                         "edge": [0.03, 0.025, 0.04, 0.05]})
    out = b.check_bets(mine, p, 0.02)
    assert (out["replay_bets"], out["research_bets"], out["same_game"]) == (4, 4, 3)
    assert out["same_game_side_book_price"] == 1                 # only 'a'
    assert out["same_game_other_side_book_or_price"] == ["b", "c"]
    assert out["replay_only"] == ["e"] and out["research_only"] == ["d"]


def test_a_moneyline_is_graded_on_the_final_margin_at_one_unit_to_win_risk_capped_at_three():
    import scripts.ncaaf_moneyline_market_build as b
    bets = pd.DataFrame({"game_id": list("abcd"), "side": ["away", "away", "home", "home"],
                         "price": [150.0, 150.0, -200.0, -400.0], "prob": [0.45, 0.45, 0.7, 0.85],
                         "margin": [-3.0, 3.0, 7.0, -1.0]})
    out = b.grade(bets).set_index("game_id")
    assert list(out["result"]) == ["W", "L", "W", "L"]
    assert out.loc["a", "units"] == pytest.approx(1.0) and out.loc["b", "units"] == pytest.approx(-1 / 1.5)
    assert out.loc["c", "units"] == pytest.approx(1.0) and out.loc["c", "risk"] == pytest.approx(2.0)
    assert out.loc["d", "risk"] == pytest.approx(3.0) and out.loc["d", "units"] == pytest.approx(-3.0)
