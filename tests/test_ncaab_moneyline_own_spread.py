"""The NCAAB moneyline model (`ncaab_moneyline_own_spread`): the 15:00 UTC read
of each book's moneyline and its own spread, the flags, the -200 floor, the
pick, the card's rows, the job, and the id that has 'spread' in it.

The evidence check is the build, not this file: scripts/ncaab_moneyline_build.py
replays the card's own path (models.ncaab_moneyline_own_spread.read -> decide)
over 2021-2026 and compares it with the research's bets game by game. These
tests pin the rules that replay depends on, and the card around it.
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
import models.ncaab_moneyline_own_spread as om  # noqa: E402

UTC = timezone.utc
INSTANT = pd.Timestamp("2026-12-05 15:00", tz="UTC")
TIP = pd.Timestamp("2026-12-06 00:00", tz="UTC")


@pytest.fixture(scope="module")
def art():
    return om.load_artifact()


@pytest.fixture(scope="module")
def table(art):
    return art["table"]


def _rows(quotes, instant=INSTANT, tip=TIP):
    """quotes: (game_id, book, minutes before the instant, line or None, p1, p2)."""
    out = []
    for i, (gid, book, mins, line, p1, p2) in enumerate(quotes):
        out.append({"game_id": gid, "bookmaker": book, "ts": instant - pd.Timedelta(minutes=mins),
                    "line": np.nan if line is None else line, "p1": p1, "p2": p2, "order": i,
                    "instant": instant, "tip": tip, "link1": f"{book}-home", "link2": f"{book}-away"})
    return pd.DataFrame(out, columns=["game_id", "bookmaker", "ts", "line", "p1", "p2", "order",
                                      "instant", "tip", "link1", "link2"])


def _ph(table, line, p1=-110.0, p2=-110.0):
    """P(home wins) from one book's own spread, the module's own arithmetic."""
    sp = om.spread_quotes(_rows([("g", "draftkings", 10, line, p1, p2)]), table)
    return float(sp["ph_own"].iloc[0])


def _american(p_implied):
    """The American price whose implied probability is p_implied."""
    return -100 * p_implied / (1 - p_implied) if p_implied >= 0.5 else 100 * (1 - p_implied) / p_implied


# The spread every book in these tests hangs unless a test says otherwise.
SPREADS = [("g", b, 20, -3.5, -110.0, -110.0) for b in ("draftkings", "fanduel", "betmgm", "betrivers")]


def _decide(table, ml, sp=SPREADS, games=("g",), **kw):
    m, s = om.read(_rows(ml), _rows(sp), table)
    return om.decide(list(games), m, s, om.CUT, **kw)


# ── registration ─────────────────────────────────────────────────────────────

def test_config_carries_the_model_as_a_rule_with_its_own_cut_and_floors(art):
    m = om.MODEL_ID
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.01}
    assert config.MODEL_EDGE_THRESHOLDS[m] == 0.01 == om.CUT == art["cut"]
    assert config.MODEL_PROB_THRESHOLDS[m] == 0.0
    assert config.SCORING_METHODS[m] == "rule"
    assert m in config.MODELS_ON_OWN_PROBABILITY
    assert m not in config.MODELS and m not in config.PAUSED_MODELS


def test_the_price_floor_is_minus_200_and_pinned():
    """mike, 2026-11-02: "-200 max". Pinned in MODEL_MIN_ODDS so a Railway
    DEFAULT_MIN_ODDS override cannot move it, and the card's own floor is the
    same number."""
    assert config.MODEL_MIN_ODDS[om.MODEL_ID] == -200
    assert config.min_odds_for(om.MODEL_ID) == -200
    assert om.MIN_PRICE == -200


def test_the_ev_floor_sits_just_under_the_smallest_ev_the_cut_admitted(art):
    floor = config.MODEL_OWN_EV_FLOOR[om.MODEL_ID]
    smallest = art["replay"]["min_ev"]
    assert floor <= smallest < floor + 0.005


def test_the_artifact_reads_the_spread_models_margin_table_and_pins_it(art):
    """The table is the spread model's own (one fit, two models); the
    artifact refuses a table whose digest moved."""
    spread = json.loads((om.ROOT / art["margin_table_from"]).read_text(encoding="utf-8"))
    assert om.table_digest(spread["margin_table"]) == art["margin_table_sha256"]
    assert int(spread["season"]) == int(art["season"]) == 2027
    t = md.from_json(spread["margin_table"])
    assert np.array_equal(t["pmf"], art["table"]["pmf"])
    assert tuple(art["books"]) == bq.BOOKS and tuple(art["ref_books"]) == om.REF_BOOKS
    assert art["min_price"] == -200


def test_an_artifact_whose_table_moved_is_refused(art, tmp_path):
    raw = json.loads((om.ROOT / om.ARTIFACT_PATH).read_text(encoding="utf-8"))
    raw["margin_table_sha256"] = "0" * 64
    p = tmp_path / "a.json"
    p.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="digest differs"):
        om.load_artifact(p)


# ── the fair probability ─────────────────────────────────────────────────────

def test_the_power_de_vig_is_the_researchs():
    a, b = om.power_fair(np.array([1 / om.dec(-110)]), np.array([1 / om.dec(-110)]))
    assert abs(a[0] - 0.5) < 1e-12 and abs(b[0] - 0.5) < 1e-12
    a, b = om.power_fair(np.array([1 / om.dec(-150)]), np.array([1 / om.dec(130)]))
    assert abs(a[0] + b[0] - 1) < 1e-12 and 0.57 < a[0] < 0.60


def test_the_own_spread_gives_a_home_favourite_a_win_chance_above_half(table):
    p35 = _ph(table, -3.5)
    p75 = _ph(table, -7.5)
    assert 0.6 < p35 < 0.7 < p75 < 0.85
    assert abs(_ph(table, 3.5) - (1 - p35)) < 0.02       # roughly symmetric
    assert _ph(table, -3.5, -120.0, 100.0) > p35          # a pricier home side means more


def test_a_spread_that_cannot_be_priced_gives_no_fair(table):
    sp = om.spread_quotes(_rows([
        ("g", "draftkings", 10, -3.5, -110.0, -110.0),
        ("g", "fanduel", 10, -3.5, -95.0, -125.0),         # a price inside -100..+100
        ("g", "betmgm", 10, -3.5, -150.0, -150.0),         # implied sum 1.20
        ("g", "betrivers", 10, 3.5, -110.0, -110.0),       # crosses zero against 3 others
        ("g", "fanatics", 10, -3.5, -110.0, -110.0),
    ]), table).set_index("bookmaker")
    assert sp.loc["draftkings", "own_ok"] and sp.loc["fanatics", "own_ok"]
    for b in ("fanduel", "betmgm", "betrivers"):
        assert not sp.loc[b, "own_ok"] and np.isnan(sp.loc[b, "ph_own"]), b
    # the crossing quote is still price-valid: the favourite check reads it
    assert sp.loc["betrivers", "sp_valid"] and sp.loc["betrivers", "flag"] == "artefact"


# ── the flags ────────────────────────────────────────────────────────────────

def _ml(table, ml, sp=SPREADS):
    m, _ = om.read(_rows(ml), _rows(sp), table)
    return m.set_index("bookmaker")


def test_an_overround_moneyline_is_flagged(table):
    m = _ml(table, [("g", "draftkings", 10, None, -150.0, -150.0),
                    ("g", "fanduel", 10, None, -150.0, 130.0)])
    assert m.loc["draftkings", "overround_bad"] and m.loc["draftkings", "flag_any"]
    assert not m.loc["fanduel", "flag_any"]


def test_a_favourite_alone_is_flagged_and_pinnacle_counts_as_another_book(table):
    away_fav = [("g", "fanduel", 10, None, 130.0, -150.0), ("g", "pinnacle", 10, None, 125.0, -140.0)]
    m = _ml(table, [("g", "draftkings", 10, None, -150.0, 130.0)] + away_fav,
            sp=[("g", "fanduel", 20, 3.5, -110.0, -110.0)])
    assert m.loc["draftkings", "fav_alone"] and m.loc["draftkings", "flag_any"]
    # one other book is not enough to call it alone
    m = _ml(table, [("g", "draftkings", 10, None, -150.0, 130.0), away_fav[0]],
            sp=[("g", "fanduel", 20, 3.5, -110.0, -110.0)])
    assert not m.loc["draftkings", "fav_alone"]


def test_a_moneyline_that_disagrees_with_its_own_spread_is_flagged(table):
    m = _ml(table, [("g", "draftkings", 10, None, 120.0, -140.0)],
            sp=[("g", "draftkings", 20, -3.5, -110.0, -110.0)])
    assert m.loc["draftkings", "spread_disagree"] and m.loc["draftkings", "flag_any"]
    m = _ml(table, [("g", "draftkings", 10, None, 120.0, -140.0)],
            sp=[("g", "draftkings", 20, -1.0, -110.0, -110.0)])      # under 1.5: no claim
    assert not m.loc["draftkings", "spread_disagree"]


def test_pinnacle_and_bovada_are_never_bet(table):
    p = _ph(table, -3.5)
    cheap = _american(p - 0.05)                        # an edge of +0.05 at that book
    (d,) = _decide(table, [("g", "pinnacle", 10, None, cheap, 120.0),
                           ("g", "bovada", 10, None, cheap, 120.0)],
                   sp=SPREADS + [("g", "pinnacle", 20, -3.5, -110.0, -110.0)])
    assert d.status == "no_quotes" and d.best is None


# ── the -200 floor and the pick ──────────────────────────────────────────────

def test_a_minus_201_side_is_never_bet_and_minus_200_is(table):
    """The floor is applied to every side BEFORE the pick: a side shorter than
    -200 cannot be the bet, however large its edge."""
    sp = [("g", "draftkings", 20, -7.5, -110.0, -110.0)]
    p = _ph(table, -7.5)
    assert p - 1 / om.dec(-201) > 0.05                 # a big edge at -201
    (d,) = _decide(table, [("g", "draftkings", 10, None, -201.0, 170.0)], sp=sp)
    assert d.status != "bets" and (d.best is None or d.best["side"] == "away")
    (d,) = _decide(table, [("g", "draftkings", 10, None, -200.0, 170.0)], sp=sp)
    assert d.status == "bets" and d.best["side"] == "home" and d.best["price"] == -200.0


def test_a_game_whose_best_side_is_too_short_is_bet_at_its_next_best_side(table):
    """The research removed the short quotes first and then picked: the -250
    side's larger edge does not block the -190 side at another book."""
    sp = [("g", "draftkings", 20, -11.5, -110.0, -110.0), ("g", "fanduel", 20, -5.5, -110.0, -110.0)]
    pa, pb = _ph(table, -11.5), _ph(table, -5.5)
    b_price = float(round(_american(pb - 0.03)))
    assert -200 <= b_price
    edge_a, edge_b = pa - 1 / om.dec(-250), pb - 1 / om.dec(b_price)
    assert edge_a > edge_b > 0.01                      # the short side is the better edge
    (d,) = _decide(table, [("g", "draftkings", 10, None, -250.0, 200.0),
                           ("g", "fanduel", 10, None, b_price, 160.0)], sp=sp)
    assert d.status == "bets" and (d.best["bookmaker"], d.best["side"], d.best["price"]) == \
        ("fanduel", "home", b_price)
    # and the card's second guard refuses a short price that reached it anyway
    import scripts.ncaab_moneyline_card as card
    bad = om.Decision("g", "bets", "x", best=dict(d.best, price=-201.0, prob=0.8))
    rows, refused = card.pick_rows([bad], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and refused["g"].startswith("below_price_floor")


def test_the_largest_edge_wins_and_a_tie_goes_to_the_book_name(table):
    p = _ph(table, -3.5)
    a = round(_american(p - 0.03))
    b = round(_american(p - 0.02))
    (d,) = _decide(table, [("g", "fanduel", 10, None, b, 120.0),
                           ("g", "draftkings", 10, None, a, 120.0)])
    assert d.status == "bets" and d.best["bookmaker"] == "draftkings"
    (d,) = _decide(table, [("g", "fanduel", 10, None, a, 120.0),
                           ("g", "betmgm", 10, None, a, 120.0)])
    assert d.best["bookmaker"] == "betmgm"            # the same bet at two books


def test_the_edge_must_be_above_the_cut(table):
    p = _ph(table, -3.5)
    (d,) = _decide(table, [("g", "draftkings", 10, None, round(_american(p - 0.005)), 120.0)])
    assert d.status == "below_cut"
    (d,) = _decide(table, [("g", "draftkings", 10, None, round(_american(p - 0.02)), 120.0)])
    assert d.status == "bets" and d.best["edge"] > 0.01


def test_a_book_with_no_usable_own_spread_is_not_priced(table):
    p = _ph(table, -3.5)
    cheap = round(_american(p - 0.05))
    (d,) = _decide(table, [("g", "fanatics", 10, None, cheap, 120.0)])     # no fanatics spread
    assert d.status == "no_clean_quote"
    (d,) = _decide(table, [("g", "fanatics", 10, None, cheap, 120.0)],
                   sp=SPREADS + [("g", "fanatics", 20, -3.5, -110.0, -110.0)])
    assert d.status == "bets" and d.best["bookmaker"] == "fanatics"


def test_quotes_outside_the_hour_before_15z_are_not_read(table):
    p = _ph(table, -3.5)
    cheap = round(_american(p - 0.05))
    (d,) = _decide(table, [("g", "draftkings", 61, None, cheap, 120.0)])   # 61 minutes old
    assert d.status == "no_quotes"
    (d,) = _decide(table, [("g", "draftkings", -2, None, cheap, 120.0)])   # after 15:00
    assert d.status == "no_quotes"


def test_a_book_no_longer_bettable_is_not_replaced_by_the_next(table):
    p = _ph(table, -3.5)
    (d,) = _decide(table, [("g", "draftkings", 10, None, round(_american(p - 0.04)), 120.0),
                           ("g", "fanduel", 10, None, round(_american(p - 0.03)), 120.0)],
                   bettable=tuple(b for b in bq.BOOKS if b != "draftkings"))
    assert d.status == "book_not_bettable" and d.best["bookmaker"] == "draftkings"



def test_an_exact_tie_with_a_book_that_cannot_be_bet_goes_to_the_book_that_can(table):
    """The same price on the same own spread at betPARX and BetRivers is the same
    bet; betPARX is fetch-only (mike, 2026-11-06), so the bettable book takes it
    (36 of 38 replayed betPARX bets were exact ties). Strictly best stays a no-bet."""
    p = _ph(table, -3.5)
    seven = tuple(b for b in bq.BOOKS if b != "betparx")
    sp = SPREADS + [("g", "betparx", 20, -3.5, -110.0, -110.0)]
    tied = round(_american(p - 0.04))
    ml = [("g", "draftkings", 10, None, round(_american(p - 0.02)), 120.0),
          ("g", "betrivers", 10, None, tied, 120.0), ("g", "betparx", 10, None, tied, 120.0)]
    (d,) = _decide(table, ml, sp=sp, bettable=seven)
    assert d.status == "bets" and d.best["bookmaker"] == "betrivers"
    (d,) = _decide(table, ml, sp=sp)                          # every book bettable: the evidence's order
    assert d.status == "bets" and d.best["bookmaker"] == "betparx"
    ml[2] = ("g", "betparx", 10, None, round(_american(p - 0.05)), 120.0)
    (d,) = _decide(table, ml, sp=sp, bettable=seven)
    assert d.status == "book_not_bettable" and d.best["bookmaker"] == "betparx"

def test_a_game_tipping_within_five_minutes_of_15z_is_not_priced():
    assert om.too_close(INSTANT + pd.Timedelta(minutes=4), INSTANT)
    assert not om.too_close(INSTANT + pd.Timedelta(minutes=5), INSTANT)


# ── the card's rows ──────────────────────────────────────────────────────────

GAMES = {"g": {"season": 2027, "game_date": "2026-12-05", "tip": TIP.to_pydatetime(),
               "instant": INSTANT.to_pydatetime(), "commence_time": "2026-12-06T00:00:00Z",
               "home": "Duke", "away": "Kansas"}}


def _bet(book="betrivers", side="home", price=-150.0, prob=0.63, dk=None):
    best = {"game_id": "g", "bookmaker": book, "side": side, "price": price, "prob": prob,
            "edge": prob - 1 / om.dec(price), "own_line": -3.5, "mu": 3.6, "ph_own": prob,
            "link": f"{book}-{side}", "dec": float(om.dec(price))}
    return om.Decision("g", "bets", "x", best=best, quotes=[], dk=dk)


def test_a_bet_row_is_a_moneyline_at_the_bet_books_price():
    import scripts.ncaab_moneyline_card as card
    dk = {"p1": -160.0, "p2": 135.0, "link1": "dk-h", "link2": "dk-a"}
    (row,), refused = card.pick_rows([_bet(dk=dk)], GAMES, 1000.0)
    assert not refused
    assert row["pick_label"] == "Duke ML" and row["pick_side"] == "home"
    assert row["scored_line"] is None and row["line_book"] is None
    assert row["dk_odds"] == -160.0 and row["dk_bet_link"] == "dk-h"
    assert row["edge"] == round(0.63 - 160 / 260, 4)
    assert (row["decision_book"], row["decision_odds"], row["best_book"], row["best_odds"]) == \
        ("betrivers", -150.0, "betrivers", -150.0)
    assert row["decision_edge"] == round(0.63 - 0.6, 4) == row["best_edge"]
    assert row["model_probability"] == row["model_probability_cal"] == 0.63
    assert row["best_bet_link"] == "betrivers-home" and row["signal_type"] == "BET"


def test_with_no_clean_draftkings_moneyline_the_reference_is_empty():
    import scripts.ncaab_moneyline_card as card
    (row,), _ = card.pick_rows([_bet(side="away", price=140.0, prob=0.45)], GAMES, 1000.0)
    assert row["pick_label"] == "Kansas ML" and row["pick_side"] == "away"
    assert row["dk_odds"] is None and row["dk_implied_prob"] == 0.0 and row["edge"] == 0.0


def test_an_ev_under_the_floor_is_refused():
    import scripts.ncaab_moneyline_card as card
    floor = config.MODEL_OWN_EV_FLOOR[om.MODEL_ID]
    prob = (1 + floor - 0.002) / float(om.dec(-200))       # EV just under the floor at -200
    rows, refused = card.pick_rows([_bet(price=-200.0, prob=prob)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and "g" in refused


# ── the id has 'spread' in it, and the pick is a moneyline everywhere ────────

def test_every_python_reader_treats_the_id_as_a_moneyline():
    from tracking.paper_tracker import _market_for_pick, _compute_result
    from tracking.pick_integrity import pick_problems
    assert _market_for_pick(om.MODEL_ID) == "h2h"
    # settles on home_win, overtime included; a NULL scored_line is fine
    assert _compute_result("home", "h2h", 81, 79, 1, None, 1, -150, None, None, 10.0)[0] == "WIN"
    assert _compute_result("away", "h2h", 81, 79, 1, None, 1, 130, None, None, 10.0)[0] == "LOSS"
    assert pick_problems("Duke ML", "home", None, om.MODEL_ID, "Duke", "Kansas") == []
    assert pick_problems("Kansas ML", "home", None, om.MODEL_ID, "Duke", "Kansas")


def test_the_app_reads_the_id_as_a_moneyline():
    src = (om.ROOT / "mobile" / "src" / "lib" / "markets.ts").read_text(encoding="utf-8")
    gm = src.index("if (modelId === 'ncaab_moneyline_own_spread') return 'h2h';")
    assert gm < src.index("modelId.includes('spread')) {\n    return 'spreads';")
    mc = src.index("if (modelId === 'ncaab_moneyline_own_spread') return 'game_ml';")
    assert mc < src.index("modelId.includes('spread')) {\n    return 'game_spread';")
    meta = (om.ROOT / "mobile" / "src" / "lib" / "modelMeta.ts").read_text(encoding="utf-8")
    assert "ncaab_moneyline_own_spread: {\n    shortLabel: 'ML',\n    longLabel: 'NCAAB Moneyline'" in meta


# ── the run ──────────────────────────────────────────────────────────────────

class _NullConn:
    def close(self):
        pass


def _wire(monkeypatch, table, slate, ledger=True, decided=(), ml=None, sp=None, first_post_bet=()):
    import scripts.ncaab_moneyline_card as card
    import models.scorer as scorer
    got = {}
    p = _ph(table, -3.5)
    ml = ml if ml is not None else [("g", "betrivers", 10, None, round(_american(p - 0.03)), 120.0)]
    sp = sp if sp is not None else SPREADS
    monkeypatch.setattr(card, "get_connection", lambda: _NullConn())
    monkeypatch.setattr(card, "slate", lambda conn, now: slate)
    monkeypatch.setattr(card, "ledger_exists", lambda conn: ledger)
    monkeypatch.setattr(card, "decided_games", lambda conn, ids: set(decided))
    # The first-post moneyline model's BETs (one bet a game across the two).
    monkeypatch.setattr(card, "first_post_bets", lambda conn, ids: set(first_post_bet))
    monkeypatch.setattr(card, "ensure_decisions_table", lambda conn: None)

    def load_rows(conn, games, instant, market="spreads", books=bq.BOOKS):
        got.setdefault("reads", []).append((market, instant, tuple(books)))
        return _rows(ml) if market == "h2h" else _rows(sp)
    monkeypatch.setattr(card.bq, "load_rows", load_rows)
    monkeypatch.setattr(scorer, "_get_current_bankroll", lambda conn: 1000.0)
    monkeypatch.setattr(card, "publish", lambda conn, prows, decisions, hour, games, refused:
                        got.update(rows=prows, decisions=decisions, hour=hour) or (len(prows), len(decisions)))
    return card, got


def test_the_15z_run_decides_the_days_games_on_the_15z_quotes(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    at = datetime(2026, 12, 5, 15, tzinfo=UTC)
    assert out["bets"] == 1
    assert got["reads"] == [("h2h", at, om.REF_BOOKS), ("spreads", at, bq.BOOKS)]
    assert [d.status for d in got["decisions"]] == ["bets"]
    assert got["rows"][0]["decision_book"] == "betrivers"
    assert got["rows"][0]["pick_label"] == "Duke ML"


def test_a_run_before_15z_reads_no_odds(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES))
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 14, 5, tzinfo=UTC))
    assert out["decided"] == 0 and "reads" not in got and "decisions" not in got


def test_a_missed_15z_is_written_as_missed_never_bet_and_fails_the_run(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES))
    with pytest.raises(card.CardIncomplete, match="missed their 15:00 UTC decision"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 16, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["missed"] and got["rows"] == []
    assert "reads" not in got                      # no later quote was even read


def test_the_first_run_ever_records_a_game_it_never_had_a_chance_at_without_failing(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES), ledger=False)
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 18, 5, tzinfo=UTC))
    (d,) = got["decisions"]
    assert d.status == "missed" and "had not run yet" in d.detail


def test_a_decided_game_is_never_decided_again(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES), decided=["g"])
    out = card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 40, tzinfo=UTC))
    assert out["decided"] == 0 and "reads" not in got
    card, got = _wire(monkeypatch, table, dict(GAMES), decided=["g"])
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 19, 5, tzinfo=UTC))   # no missed either


def test_no_moneyline_for_any_due_game_fails_the_run_after_writing(monkeypatch, table):
    card, got = _wire(monkeypatch, table, dict(GAMES), ml=[])
    with pytest.raises(card.CardIncomplete, match="may have stopped"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["no_quotes"]


def test_an_artifact_for_another_season_fails_the_run(monkeypatch, table):
    card, got = _wire(monkeypatch, table, {"g": dict(GAMES["g"], season=2028)})
    with pytest.raises(card.CardIncomplete, match="artifact is for season 2027"):
        card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))


def test_a_game_that_tipped_before_the_run_is_recorded_not_bet(monkeypatch, table):
    g = {"g": dict(GAMES["g"], tip=datetime(2026, 12, 5, 15, 3, tzinfo=UTC))}
    card, got = _wire(monkeypatch, table, g)
    card.run_card(do_publish=True, now=datetime(2026, 12, 5, 15, 5, tzinfo=UTC))
    assert [d.status for d in got["decisions"]] == ["tipped"] and got["rows"] == []


def test_the_kill_switch_reads_nothing(monkeypatch):
    import scripts.ncaab_moneyline_card as card
    monkeypatch.setenv("RUN_NCAAB_MONEYLINE_CARD", "0")
    monkeypatch.setattr(card, "get_connection", lambda: (_ for _ in ()).throw(AssertionError("read")))
    assert card.run_card(do_publish=True)["off"] is True


def test_an_incomplete_run_exits_non_zero(monkeypatch):
    import scripts.ncaab_moneyline_card as card
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
    job = _jobs(monkeypatch)["ncaab_moneyline_card"]
    assert job.max_instances == 1 and job.coalesce is True
    for start in (datetime(2026, 11, 20, 0, 0, tzinfo=UTC),     # standard time
                  datetime(2027, 3, 20, 0, 0, tzinfo=UTC)):     # after DST returns
        fires = _fires(job, start, start + timedelta(hours=23, minutes=59))
        utc = [f.astimezone(UTC) for f in fires]
        assert len(utc) == 24 and all(f.minute == 5 for f in utc) and 15 in {f.hour for f in utc}
    assert "ncaab_moneyline_card" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_moneyline_card"] == 150


def test_the_job_runs_the_card_and_publishes_and_a_failure_raises(monkeypatch):
    import scheduler
    ran, pub = [], []
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: ran.append(cmd) or "ok")
    monkeypatch.setattr(scheduler, "_publish_new_signals", lambda label: pub.append(label))
    scheduler.run_ncaab_moneyline_card()
    assert ran[0][-2:] == ["scripts.ncaab_moneyline_card", "--publish"] and pub == ["ncaab-moneyline-card"]
    monkeypatch.setattr(scheduler, "_run", lambda cmd, label, **kw: "fail")
    with pytest.raises(RuntimeError):
        scheduler.run_ncaab_moneyline_card()
    assert pub == ["ncaab-moneyline-card"] * 2    # a failed run still publishes what it wrote


def test_the_ledger_is_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    import scripts.ncaab_moneyline_card as card
    assert card.DECISIONS_TABLE in WORKER_ONLY_TABLES
