"""The NCAAB spread model (`ncaab_spread_market`): the margin table, the 15:00
UTC quote read, the pricing, the decision and the card's rows.

The evidence check is the build, not this file:
scripts/ncaab_spread_market_build.py replays the card's own path
(models.ncaab_book_quotes.snapshot -> models.ncaab_spread_market.decide) over
2021-2026 and matched the research's 613 bets game by game (2026-11-02). These
tests pin the rules that replay depends on, and the card around it.
"""
from __future__ import annotations

import math
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
import models.ncaab_spread_market as sm  # noqa: E402

UTC = timezone.utc
INSTANT = pd.Timestamp("2026-12-05 15:00", tz="UTC")
TIP = pd.Timestamp("2026-12-06 00:00", tz="UTC")


def _point_table(margin: int) -> dict:
    """Every grid row puts all its mass on one final margin."""
    pmf = np.zeros((len(md.GRID), len(md.KK)))
    pmf[:, margin - md.KLO] = 1.0
    return {"pmf": pmf, "ge": md._ge(pmf), "h": np.full(len(md.GRID), md.H0),
            "neff": np.full(len(md.GRID), 1000.0)}


def _rows(quotes, instant=INSTANT, tip=TIP):
    """quotes: (game_id, book, minutes before the instant, line, p1, p2[, order])."""
    out = []
    for i, q in enumerate(quotes):
        gid, book, mins, line, p1, p2 = q[:6]
        out.append({"game_id": gid, "bookmaker": book, "ts": instant - pd.Timedelta(minutes=mins),
                    "line": line, "p1": p1, "p2": p2, "order": q[6] if len(q) > 6 else i,
                    "instant": instant, "tip": tip, "link1": f"{book}-home", "link2": f"{book}-away"})
    return pd.DataFrame(out)


# ── registration ─────────────────────────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut_and_floor():
    m = sm.MODEL_ID
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.03}
    assert config.MODEL_EDGE_THRESHOLDS[m] == 0.03
    assert config.MODEL_PROB_THRESHOLDS[m] == 0.0
    assert config.MODEL_OWN_EV_FLOOR[m] == 0.05
    assert config.MODEL_MIN_ODDS[m] == -200
    assert m in config.MODELS_ON_OWN_PROBABILITY
    assert config.SCORING_METHODS[m] == "rule"
    assert m not in config.MODELS and m not in config.PAUSED_MODELS


def test_its_picks_settle_as_spreads_on_the_home_number():
    from tracking.paper_tracker import _compute_result, _market_for_pick
    assert _market_for_pick(sm.MODEL_ID) == "spreads"
    # home -8.0, won by 10 (overtime included in the stored final): a win
    assert _compute_result("home", "spreads", 80, 70, 1, None, 1, -110, -8.0, None, 0.0)[0] == "WIN"
    # away +8.0 (stored as home -8.0), home won by 8: a push
    assert _compute_result("away", "spreads", 78, 70, 1, None, 0, -110, -8.0, None, 0.0)[0] == "PUSH"


def test_its_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    assert "ncaab_spread_decisions" in WORKER_ONLY_TABLES


def test_its_books_are_the_bettable_books():
    # The consensus keeps betparx (fitted with it); the card's bettable= is
    # config.BEST_LINE_BOOKMAKERS, which never holds it (mike 2026-11-06).
    rest = set(bq.BOOKS) - config.STATE_LIMITED_BOOKMAKERS
    assert rest <= set(config.BEST_LINE_BOOKMAKERS)
    assert not rest & set(config.BEST_LINE_EXCLUDE_BOOKMAKERS)
    assert "betparx" in bq.BOOKS and "betparx" not in config.BEST_LINE_BOOKMAKERS


# ── the committed artifact ───────────────────────────────────────────────────

def test_the_committed_artifact_is_the_2026_27_build_with_the_research_constants():
    art = sm.load_artifact()
    assert art["season"] == 2027 and art["prior_season"] == 2026
    assert tuple(art["books"]) == bq.BOOKS
    assert art["check_hour_utc"] == 15 and art["window_min"] == 60
    assert art["cut"] == config.MODEL_EDGE_THRESHOLDS[sm.MODEL_ID]
    assert art["min_other_books"] == sm.MIN_OTHER_BOOKS == 3
    # c: fitted once on the 2012-2020 archive, never refit (the evidence's)
    assert round(art["c_by_phase"]["Nov"], 4) == 0.2494
    assert round(art["c_by_phase"]["Dec+"], 4) == -0.0815
    assert art["table_train_seasons"] == [2012, 2026]
    t = art["table"]
    assert t["pmf"].shape == (len(md.GRID), len(md.KK))
    assert np.allclose(t["pmf"].sum(axis=1), 1.0)
    rep = art["replay"]["by_season"]
    live, every = rep["live: 3+ other books"], rep["without the 3-other-books minimum"]
    assert (live["2021-2025"]["bets"], live["2021-2025"]["units"]) == (409, 44.6)
    assert (live["2026"]["bets"], live["2026"]["units"]) == (133, 30.34)
    assert (every["2021-2025"]["bets"], every["2026"]["bets"]) == (478, 135)
    # the EV floor sits under every bet the cut admitted in the replay
    assert art["replay"]["min_ev_live"] > config.MODEL_OWN_EV_FLOOR[sm.MODEL_ID]


# ── the margin table ─────────────────────────────────────────────────────────

def test_a_home_line_covers_when_margin_plus_line_is_positive():
    t = _point_table(5)
    ph, pp = md.home_cover([3.0, 3.0, 3.0], [-4.5, -5.0, -5.5], t)
    assert ph[0] == 1.0 and pp[0] == 0.0          # 5 - 4.5 > 0
    assert pp[1] == 1.0                            # 5 - 5 = 0: a push
    assert ph[2] == 0.0 and pp[2] == 0.0           # 5 - 5.5 < 0


def test_the_three_outcomes_sum_to_one_and_a_half_point_never_pushes():
    rng = np.random.default_rng(1)
    mu = rng.normal(0, 8, 4000)
    t = md.fit(np.round(mu + rng.normal(0, 11, 4000)).astype(int), mu)
    for m, th in ((0.0, 3.0), (7.3, -2.5), (-12.0, 11.0)):
        pw, pp, pl = md.probs([m], [th], t)
        assert math.isclose(pw[0] + pp[0] + pl[0], 1.0)
        assert (pp[0] == 0.0) == (th != round(th))
    hi, _ = md.home_cover([10.0], [-7.5], t)
    lo, _ = md.home_cover([5.0], [-7.5], t)
    assert hi[0] > lo[0]


def test_the_kernel_widens_until_500_games_and_not_before():
    mu = np.zeros(600)
    t = md.fit(np.arange(600) % 21 - 10, mu)
    i0 = int(np.argmin(np.abs(md.GRID)))
    assert t["h"][i0] == md.H0                    # 600 games at the mean: no widening
    assert t["h"][-1] > md.H0                     # nothing near +45: widened


def test_the_frozen_table_comes_back_identical():
    rng = np.random.default_rng(2)
    mu = rng.normal(0, 9, 3000)
    t = md.fit(np.round(mu + rng.normal(0, 10, 3000)).astype(int), mu)
    back = md.from_json(md.to_json(t))
    assert np.array_equal(back["pmf"], t["pmf"]) and np.array_equal(back["ge"], t["ge"])


# ── the 15:00 UTC read ───────────────────────────────────────────────────────

def test_a_books_quote_is_its_newest_row_stamped_in_the_hour_before_the_instant():
    r = _rows([("g", "fanduel", 50, -9.0, -110, -110),
               ("g", "fanduel", 10, -9.5, -110, -110),
               ("g", "fanduel", -2, -11.0, -110, -110),       # after 15:00
               ("g", "betmgm", 61, -7.0, -110, -110),         # 61 minutes old
               ("g", "betmgm", 30, None, -110, -110),         # no line: dropped first
               ("g", "pinnacle", 5, -10.0, -105, -105)])      # not a bettable book
    q = bq.standing_quotes(r)
    assert q[["bookmaker", "line"]].values.tolist() == [["fanduel", -9.5]]


def test_a_same_stamp_tie_takes_the_row_stored_last():
    r = _rows([("g", "fanduel", 10, -9.5, -110, -110, 7), ("g", "fanduel", 10, -10.0, -112, -108, 3)])
    assert bq.standing_quotes(r)["line"].tolist() == [-9.5]


def test_a_game_that_tips_at_the_instant_is_never_quoted():
    assert not len(bq.standing_quotes(_rows([("g", "fanduel", 10, -9.5, -110, -110)], tip=INSTANT)))
    late = _rows([("g", "fanduel", 10, -9.5, -110, -110)], tip=INSTANT - pd.Timedelta(minutes=20))
    assert not len(bq.standing_quotes(late))


def test_a_sign_crossing_quote_is_an_artefact_and_leaves_the_consensus():
    r = _rows([("a", "draftkings", 5, -2.0, -110, -110), ("a", "fanduel", 5, -2.0, -110, -110),
               ("a", "betmgm", 5, 2.0, -110, -110),                       # 2 others: artefact
               ("b", "draftkings", 5, -1.5, -110, -110), ("b", "fanduel", 5, 1.5, -110, -110),
               ("c", "draftkings", 5, 0.0, -110, -110), ("c", "fanduel", 5, -1.0, -110, -110),
               ("c", "betmgm", 5, 1.0, -110, -110)])
    q = bq.flag_and_consensus(bq.standing_quotes(r)).set_index(["game_id", "bookmaker"])
    assert q.loc[("a", "betmgm"), "flag"] == "artefact"
    assert q.loc[("a", "draftkings"), "cons"] == -2.0 and q.loc[("a", "draftkings"), "n_ok"] == 2
    assert set(q.loc["b", "flag"]) == {"ambiguous"}                       # 1 other each
    assert q.loc[("b", "draftkings"), "n_ok"] == 0
    # a 0 line never flags; LOO of betmgm is median(0, -1) = -0.5: crossing
    assert q.loc[("c", "draftkings"), "flag"] == "ok"
    assert q.loc[("c", "betmgm"), "flag"] == "artefact"


def test_the_consensus_includes_the_book_being_priced():
    r = _rows([("g", "draftkings", 5, -10.0, -110, -110), ("g", "fanduel", 5, -10.0, -110, -110),
               ("g", "betmgm", 5, -8.0, -110, -110)])
    q = bq.snapshot(r)
    assert set(q["cons"]) == {-10.0} and set(q["n_ok"]) == {3}
    r2 = _rows([("g", "draftkings", 5, -10.0, -110, -110), ("g", "betmgm", 5, -8.0, -110, -110)])
    assert set(bq.snapshot(r2)["cons"]) == {-9.0}


def test_the_check_instant_is_15z_on_the_games_date():
    assert bq.check_instant("2027-03-20") == datetime(2027, 3, 20, 15, tzinfo=UTC)


# ── pricing and the decision ─────────────────────────────────────────────────

def _snap(quotes, phase="Dec+"):
    s = bq.snapshot(_rows(quotes))
    s["phase"] = phase
    return s


C = {"Nov": 0.25, "Dec+": -0.08}


def test_the_edge_is_win_given_no_push_minus_the_sides_own_price():
    t = _point_table(5)                     # the home side always wins by 5
    z = sm.price_quotes(_snap([("g", "fanduel", 5, -4.5, -110, -110)]), C, t)
    r = z.iloc[0]
    assert r["side"] == 1 and r["prob"] == 1.0
    assert math.isclose(r["edge"], 1.0 - 1 / (1 + 100 / 110))
    z = sm.price_quotes(_snap([("g", "fanduel", 5, -5.5, -110, +120)]), C, t)
    r = z.iloc[0]
    assert r["side"] == 2 and r["price"] == 120 and math.isclose(r["edge"], 1.0 - 1 / 2.2)


def test_a_quote_whose_two_sides_tie_is_priced_as_the_home_side():
    pmf = np.zeros((len(md.GRID), len(md.KK)))
    pmf[:, 4 - md.KLO] = pmf[:, 6 - md.KLO] = 0.5          # home by 4 or by 6, evenly
    t = {"pmf": pmf, "ge": md._ge(pmf)}
    r = sm.price_quotes(_snap([("g", "fanduel", 5, -5.0, -110, -110)]), C, t).iloc[0]
    assert r["ph"] == 0.5 and r["side"] == 1


def test_a_tied_edge_goes_to_the_better_line_then_price_then_book_name():
    z = pd.DataFrame([
        {"game_id": "g", "bookmaker": "fanduel", "side": 1, "line": -8.0, "price": -110, "edge": 0.05},
        {"game_id": "g", "bookmaker": "betmgm", "side": 1, "line": -7.5, "price": -115, "edge": 0.05},
        {"game_id": "h", "bookmaker": "fanduel", "side": 2, "line": -8.0, "price": -105, "edge": 0.04},
        {"game_id": "h", "bookmaker": "betmgm", "side": 2, "line": -8.0, "price": -110, "edge": 0.04},
        {"game_id": "k", "bookmaker": "fanduel", "side": 1, "line": -8.0, "price": -110, "edge": 0.04},
        {"game_id": "k", "bookmaker": "betmgm", "side": 1, "line": -8.0, "price": -110, "edge": 0.04},
        {"game_id": "k", "bookmaker": "betrivers", "side": 1, "line": -8.0, "price": -110, "edge": 0.06},
    ])
    b = sm.best_per_game(z).set_index("game_id")["bookmaker"].to_dict()
    assert b == {"g": "betmgm", "h": "fanduel", "k": "betrivers"}
    z2 = z[z["bookmaker"] != "betrivers"]
    assert sm.best_per_game(z2).set_index("game_id").loc["k", "bookmaker"] == "betmgm"


def _art():
    a = sm.load_artifact()
    return a["c_by_phase"], a["table"]


GOOD = [("g", "draftkings", 30, -10.0, -110, -110), ("g", "fanduel", 30, -10.0, -110, -110),
        ("g", "betmgm", 30, -10.0, -110, -110), ("g", "williamhill_us", 30, -10.0, -110, -110),
        ("g", "betrivers", 30, -8.0, -110, -110)]


def test_the_best_quote_bets_above_the_cut_with_three_other_books():
    c, t = _art()
    (d,) = sm.decide(["g"], _snap(GOOD), c, t, 0.03)
    assert d.status == "bets" and d.best["bookmaker"] == "betrivers" and d.best["side"] == 1
    assert d.best["line"] == -8.0 and d.best["cons"] == -10.0 and d.best["edge"] > 0.03
    assert d.dk["line"] == -10.0 and len(d.quotes) == 5


def test_fewer_than_three_other_books_is_not_a_bet():
    c, t = _art()
    (d,) = sm.decide(["g"], _snap(GOOD[2:]), c, t, 0.03)     # betrivers + 2 others
    assert d.status == "too_few_books" and d.best["edge"] > 0.03


def test_an_artefact_is_never_the_bet():
    c, t = _art()
    (d,) = sm.decide(["g"], _snap(GOOD + [("g", "hardrockbet", 30, +10.0, -110, -110)]), c, t, 0.03)
    assert d.status == "bets" and d.best["bookmaker"] == "betrivers"
    assert {q["book"]: q["flag"] for q in d.quotes}["hardrockbet"] == "artefact"


def test_below_the_cut_no_quotes_and_a_book_no_longer_bettable():
    c, t = _art()
    flat = [(g, b, m, -10.0, p1, p2) for g, b, m, _, p1, p2 in GOOD]
    (d,) = sm.decide(["g"], _snap(flat), c, t, 0.03)
    assert d.status == "below_cut"
    (d,) = sm.decide(["x"], _snap(GOOD), c, t, 0.03)
    assert d.status == "no_quotes"
    bettable = tuple(b for b in bq.BOOKS if b != "betrivers")
    (d,) = sm.decide(["g"], _snap(GOOD), c, t, 0.03, bettable=bettable)
    assert d.status == "book_not_bettable" and d.best["bookmaker"] == "betrivers"



def test_an_exact_tie_with_a_book_that_cannot_be_bet_goes_to_the_book_that_can():
    """The same line and price at betPARX and BetRivers is the same bet, and
    betPARX is fetch-only (mike, 2026-11-06). By name betPARX sorts first, so
    without this the game was a no-bet (74 of 89 replayed betPARX bets were
    exact ties). A betPARX number that is strictly best is still not replaced."""
    c, t = _art()
    seven = tuple(b for b in bq.BOOKS if b != "betparx")
    tie = GOOD + [("g", "betparx", 30, -8.0, -110, -110)]
    (d,) = sm.decide(["g"], _snap(tie), c, t, 0.03, bettable=seven)
    assert d.status == "bets" and d.best["bookmaker"] == "betrivers" and d.best["line"] == -8.0
    (d,) = sm.decide(["g"], _snap(tie), c, t, 0.03)         # every book bettable: the evidence's order
    assert d.status == "bets" and d.best["bookmaker"] == "betparx"
    strict = GOOD + [("g", "betparx", 30, -7.5, -110, -110)]
    (d,) = sm.decide(["g"], _snap(strict), c, t, 0.03, bettable=seven)
    assert d.status == "book_not_bettable" and d.best["bookmaker"] == "betparx"

# ── the card's rows ──────────────────────────────────────────────────────────

GAMES = {"g": {"season": 2027, "game_date": "2026-12-05", "tip": TIP.to_pydatetime(),
               "instant": INSTANT.to_pydatetime(), "commence_time": "2026-12-06T00:00:00Z",
               "home": "Duke", "away": "Kansas"}}


def _bet(book="betrivers", side=1, line=-8.0, price=-110.0, prob=0.5705, dk=None):
    best = {"game_id": "g", "bookmaker": book, "side": side, "line": line, "price": price,
            "prob": prob, "edge": prob - 1 / sm.dec(price), "cons": -10.0, "n_ok": 5, "mu": 9.92,
            "link1": f"{book}-home", "link2": f"{book}-away"}
    return sm.Decision("g", "bets", "x", best=best, quotes=[], dk=dk)


def test_a_bet_off_draftkings_line_names_its_book_and_leaves_draftkings_empty():
    import scripts.ncaab_spread_card as card
    dk = {"line": -10.0, "p1": -110.0, "p2": -110.0, "flag": "ok", "link1": "dk-h", "link2": "dk-a"}
    (row,), refused = card.pick_rows([_bet(dk=dk)], GAMES, 1000.0)
    assert not refused
    assert row["pick_label"] == "Duke -8.0" and row["pick_side"] == "home" and row["scored_line"] == -8.0
    assert row["line_book"] == "betrivers" and row["dk_odds"] is None
    assert row["dk_implied_prob"] == 0.0 and row["edge"] == 0.0 and row["dk_bet_link"] is None
    assert (row["decision_book"], row["decision_odds"], row["best_book"], row["best_odds"]) == \
        ("betrivers", -110.0, "betrivers", -110.0)
    assert row["decision_edge"] == round(0.5705 - 110 / 210, 4) == row["best_edge"]
    assert row["model_probability"] == row["model_probability_cal"] == 0.5705
    assert row["best_bet_link"] == "betrivers-home" and row["signal_type"] == "BET"


def test_a_bet_on_draftkings_line_carries_draftkings_price_as_the_reference():
    import scripts.ncaab_spread_card as card
    dk = {"line": 8.0, "p1": -105.0, "p2": -115.0, "flag": "ok", "link1": "dk-h", "link2": "dk-a"}
    (row,), _ = card.pick_rows([_bet(book="fanduel", side=2, line=8.0, price=-108.0, prob=0.56, dk=dk)],
                               GAMES, 1000.0)
    assert row["pick_label"] == "Kansas -8.0" and row["pick_side"] == "away" and row["scored_line"] == 8.0
    assert row["line_book"] is None and row["dk_odds"] == -115.0 and row["dk_bet_link"] == "dk-a"
    assert row["edge"] == round(0.56 - 115 / 215, 4)
    assert row["decision_book"] == "fanduel" and row["decision_odds"] == -108.0


def test_a_price_past_the_floor_or_an_ev_under_the_floor_is_refused():
    import scripts.ncaab_spread_card as card
    rows, refused = card.pick_rows([_bet(price=-210.0, prob=0.71)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and refused["g"].startswith("below_price_floor")
    # edge 0.031 at -200: EV = 0.031 x 1.5 = 0.0465, under the 0.05 floor
    rows, refused = card.pick_rows([_bet(price=-200.0, prob=2 / 3 + 0.031)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and "g" in refused


# ── the run ──────────────────────────────────────────────────────────────────

class _NullConn:
    def close(self):
        pass


def _wire(monkeypatch, slate, ledger=True, decided=(), rows=None):
    import scripts.ncaab_spread_card as card
    import models.scorer as scorer
    got = {}
    monkeypatch.setattr(card, "get_connection", lambda: _NullConn())
    monkeypatch.setattr(card, "slate", lambda conn, now: slate)
    monkeypatch.setattr(card, "ledger_exists", lambda conn: ledger)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids: set(decided))
    monkeypatch.setattr(card, "ensure_decisions_table", lambda conn: None)
    monkeypatch.setattr(card.bq, "load_rows", lambda conn, games, instant:
                        (got.setdefault("instants", []).append(instant)
                         or (rows if rows is not None else _rows(GOOD))))
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    monkeypatch.setattr(card, "publish", lambda conn, prows, decisions, hour, games, refused:
                        got.update(rows=prows, decisions=decisions, hour=hour) or (len(prows), len(decisions)))
    return card, got


def test_the_15z_run_decides_the_days_games_on_the_15z_quotes(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert out["bets"] == 1 and got["instants"] == [datetime(2026, 12, 5, 15, tzinfo=UTC)]
    assert [d.status for d in got["decisions"]] == ["bets"]
    assert got["rows"][0]["decision_book"] == "betrivers"


def test_a_run_before_15z_reads_no_odds(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 14, 5, tzinfo=UTC))
    assert out["decided"] == 0 and "instants" not in got and "decisions" not in got


def test_a_missed_15z_is_written_as_missed_never_bet_and_fails_the_run(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES))
    with pytest.raises(card.CardIncomplete, match="missed their 15:00 UTC decision"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 16, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["missed"] and got["rows"] == []
    assert "instants" not in got                   # no later quote was even read


def test_the_first_run_ever_records_a_game_it_never_had_a_chance_at_without_failing(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES), ledger=False)
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 18, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    assert d.status == "missed" and "had not run yet" in d.detail


def test_a_decided_game_is_never_decided_again(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES), decided=["g"])
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 40, tzinfo=UTC))
    assert out["decided"] == 0 and "instants" not in got
    card, got = _wire(monkeypatch, dict(GAMES), decided=["g"])
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 19, 5, tzinfo=UTC))   # no missed either


def test_no_quote_for_any_due_game_fails_the_run_after_writing(monkeypatch):
    card, got = _wire(monkeypatch, dict(GAMES), rows=_rows([]))
    with pytest.raises(card.CardIncomplete, match="may have stopped"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["no_quotes"]


def test_an_artifact_for_another_season_fails_the_run(monkeypatch):
    g = {"g": dict(GAMES["g"], season=2028)}
    card, got = _wire(monkeypatch, g)
    with pytest.raises(card.CardIncomplete, match="artifact is for season 2027"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))


def test_a_game_that_tipped_before_the_run_is_recorded_not_bet(monkeypatch):
    g = {"g": dict(GAMES["g"], tip=datetime(2026, 12, 5, 15, 3, tzinfo=UTC))}
    card, got = _wire(monkeypatch, g)
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["tipped"] and got["rows"] == []


def test_the_kill_switch_reads_nothing(monkeypatch):
    import scripts.ncaab_spread_card as card
    monkeypatch.setenv("RUN_NCAAB_SPREAD_CARD", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.run_card(do_publish=True)["off"] is True


def test_an_incomplete_run_exits_non_zero(monkeypatch):
    import scripts.ncaab_spread_card as card
    monkeypatch.setattr(card, "run_card", lambda do_publish=False: (_ for _ in ()).throw(
        card.CardIncomplete("x")))
    with pytest.raises(SystemExit) as e:
        card.main(["--publish"])
    assert e.value.code == 1


# ── the job ──────────────────────────────────────────────────────────────────

def test_the_job_runs_hourly_at_five_past_utc_all_year_and_is_watched(monkeypatch):
    """15:00 UTC is the instant the evidence bought, so the run must stay on
    UTC across DST; and hourly, so a missed 15:05 is reported by the next run."""
    import scheduler
    from tests.test_nba_prop_window import _fires, _jobs
    from tracking.job_heartbeat import MAX_SILENCE
    job = _jobs(monkeypatch)["ncaab_spread_card"]
    assert job.max_instances == 1 and job.coalesce is True
    for start in (datetime(2026, 11, 20, 0, 0, tzinfo=UTC),     # standard time
                  datetime(2027, 3, 20, 0, 0, tzinfo=UTC)):     # after DST returns
        fires = _fires(job, start, start + timedelta(hours=23, minutes=59))
        utc = [f.astimezone(UTC) for f in fires]
        assert len(utc) == 24 and all(f.minute == 5 for f in utc) and 15 in {f.hour for f in utc}
    assert "ncaab_spread_card" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_spread_card"] == 150


def test_the_job_runs_the_card_and_publishes_and_a_failure_raises(monkeypatch):
    import scheduler
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    scheduler.run_ncaab_spread_card()
    assert ran[0][-2:] == ["scripts.ncaab_spread_card", "--publish"] and pub == ["ncaab-spread-card"]
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaab_spread_card()
    assert pub == ["ncaab-spread-card"] * 2       # a failed run still publishes what it wrote
