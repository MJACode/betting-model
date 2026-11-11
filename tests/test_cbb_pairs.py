"""An under and a big favourite's spread bet are not held on one college
basketball game (models/cbb_pairs.py; mike, 2026-11-11).

Pinned here:
  * what "big favourite" is: 12 points on a first-half spread, 20 on a full
    game, read off the HOME number and the side bet;
  * the pair is an UNDER with a spread bet on that favourite, in either order,
    and nothing else (an over, an underdog, a small favourite, a moneyline);
  * the later bet gives way: a card's BET becomes a NONE row with the reason,
    an in-play loop's decision is `declined`; the standing bet is not touched;
  * the men's first-half total model does not bet an under at all when the
    favourite lays 12 or more in the half (it decides before the spread model);
  * every college basketball writer asks.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
from models import cbb_pairs as P  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402


class Conn:
    """`picks` as the pair check reads it: (model_id, pick_side, scored_line, pick_label)."""

    def __init__(self, standing=()):
        self.standing, self.reads = list(standing), 0

    def execute(self, sql, params=None):
        self.reads += 1
        game_id, models = params
        rows = [r for r in self.standing if r[0] in models]
        return type("Cur", (), {"fetchall": lambda _s: rows})()


FAV_1H = ("ncaab_first_half_spread", "home", -14.5, "Butler -14.5 (First Half)")
UNDER_1H = ("ncaab_first_half_total", "under", 74.5, "First Half Under 74.5")


# ── what a big favourite is ──────────────────────────────────────────────────

def test_points_laid_come_off_the_home_number_and_the_side():
    assert P.points_laid("home", -14.5) == 14.5          # the home favourite lays 14.5
    assert P.points_laid("away", -14.5) == -14.5         # its underdog gets them
    assert P.points_laid("away", 21.0) == 21.0           # an away favourite
    assert P.points_laid("home", 21.0) == -21.0


def test_big_is_twelve_in_the_half_and_twenty_on_the_game():
    assert P.BIG_FAVOURITE == {"full": 20.0, "first_half": 12.0}
    assert P.big_favourite("ncaab_first_half_spread", "home", -12.0)
    assert not P.big_favourite("ncaab_first_half_spread", "home", -11.5)
    assert not P.big_favourite("ncaab_first_half_spread", "away", -14.5)       # the underdog's side
    assert P.big_favourite("ncaab_spread_market", "away", 20.0)
    assert not P.big_favourite("ncaab_spread_market", "home", -19.5)
    # the in-play spreads are bets on the full game, whenever they are placed
    assert P.big_favourite("ncaab_live_spread_h1", "home", -20.5)
    assert not P.big_favourite("ncaab_live_spread_h2", "home", -14.5)
    # a moneyline is not a spread, and a total is not either
    assert not P.big_favourite("ncaab_moneyline_own_spread", "home", -30.0)
    assert not P.big_favourite("ncaab_first_half_total", "under", 74.5)
    assert not P.big_favourite("ncaab_first_half_spread", "home", None)


def test_every_listed_model_is_a_real_one():
    known = set(config.ACTION_THRESHOLDS)
    assert set(P.SPREADS) <= known and set(P.TOTALS) <= known
    # every college basketball total and spread model is listed: a new one joins here
    cbb = {m for m in known if m.startswith(("ncaab_", "ncaabw_"))}
    assert {m for m in cbb if "total" in m} == set(P.TOTALS)
    assert {m for m in cbb if "spread" in m and "moneyline" not in m} == set(P.SPREADS)


# ── the pair ─────────────────────────────────────────────────────────────────

def bet(model_id, side, line):
    return {"model_id": model_id, "side": side, "line": line}


def test_the_pair_is_an_under_with_a_big_favourite_in_either_order():
    under = bet("ncaab_first_half_total", "under", 74.5)
    fav = bet("ncaab_first_half_spread", "home", -14.5)
    assert P.pair(under, fav) and P.pair(fav, under)
    # across the half and the game, and across the pre-game and in-play models
    assert P.pair(bet("ncaab_live_total_h2", "under", 150.5), bet("ncaab_spread_market", "home", -28.5))
    assert P.pair(bet("ncaabw_live_total_ht", "under", 131.5), bet("ncaab_spread_market", "away", 22.0))


def test_nothing_else_is_the_pair():
    fav = bet("ncaab_first_half_spread", "home", -14.5)
    assert not P.pair(bet("ncaab_first_half_total", "over", 74.5), fav)                  # an over
    assert not P.pair(bet("ncaab_first_half_total", "under", 74.5),
                      bet("ncaab_first_half_spread", "away", -14.5))                     # the underdog
    assert not P.pair(bet("ncaab_first_half_total", "under", 74.5),
                      bet("ncaab_first_half_spread", "home", -6.5))                      # a small favourite
    assert not P.pair(bet("ncaab_first_half_total", "under", 74.5),
                      bet("ncaab_total_blend", "under", 150.5))                          # two unders
    assert not P.pair(fav, bet("ncaab_spread_market", "home", -28.5))                    # two favourites


# ── the check against what the game holds ────────────────────────────────────

def test_an_under_is_stopped_by_a_standing_big_favourite_and_names_it():
    c = Conn([FAV_1H])
    why = P.clash(c, "g", "ncaab_first_half_total", "under", 74.5)
    assert why == "paired_with:Butler -14.5 (First Half) (a big favourite's spread on the same game)"
    assert P.clash(Conn([("ncaab_first_half_spread", "away", -14.5, "x")]), "g", "ncaab_first_half_total",
                   "under", 74.5) is None                                                # the underdog stands
    assert P.clash(Conn([("ncaab_first_half_spread", "home", -8.5, "x")]), "g", "ncaab_first_half_total",
                   "under", 74.5) is None


def test_a_big_favourite_is_stopped_by_a_standing_under_and_names_it():
    c = Conn([UNDER_1H])
    why = P.clash(c, "g", "ncaab_first_half_spread", "home", -14.5)
    assert why == "paired_with:First Half Under 74.5 (an under on the same game)"
    assert P.clash(Conn([("ncaab_first_half_total", "over", 74.5, "x")]), "g", "ncaab_first_half_spread",
                   "home", -14.5) is None


def test_a_bet_that_cannot_be_half_of_the_pair_reads_nothing():
    c = Conn([FAV_1H, UNDER_1H])
    assert P.clash(c, "g", "ncaab_first_half_total", "over", 74.5) is None
    assert P.clash(c, "g", "ncaab_first_half_spread", "away", -14.5) is None
    assert P.clash(c, "g", "ncaab_first_half_spread", "home", -6.5) is None
    assert P.clash(c, "g", "ncaab_moneyline_own_spread", "home", -30.0) is None
    assert c.reads == 0


def test_the_standing_read_skips_void_picks_and_is_one_game():
    sql = " ".join(P._STANDING_SQL.split())
    assert "game_id = %s" in sql and "signal_type = 'BET'" in sql and "model_id = ANY(%s)" in sql
    assert "condition_status IS NULL OR condition_status <> 'VOID'" in sql


def test_a_cards_bet_that_would_make_the_pair_becomes_a_none_row():
    rows = [{"game_id": "g1", "model_id": "ncaab_first_half_spread", "pick_side": "home", "scored_line": -14.5,
             "signal_type": "BET", "kelly_fraction": 0.02, "recommended_bet": 20.0},
            {"game_id": "g2", "model_id": "ncaab_first_half_spread", "pick_side": "away", "scored_line": -14.5,
             "signal_type": "BET", "kelly_fraction": 0.02, "recommended_bet": 20.0},
            {"game_id": "g3", "model_id": "ncaab_first_half_spread", "pick_side": "home", "scored_line": -14.5,
             "signal_type": "NONE", "kelly_fraction": 0.0, "recommended_bet": 0.0}]
    refused = {}
    assert P.hold_back(Conn([UNDER_1H]), rows, refused) == 1
    assert (rows[0]["signal_type"], rows[0]["kelly_fraction"], rows[0]["recommended_bet"]) == ("NONE", 0.0, 0.0)
    assert rows[0]["scored_line"] == -14.5 and rows[0]["pick_side"] == "home"            # still priced
    assert refused == {"g1": "paired_with:First Half Under 74.5 (an under on the same game)"}
    assert rows[1]["signal_type"] == "BET" and rows[2]["signal_type"] == "NONE"


# ── the first-half under, decided before the spread model ────────────────────

def _table(seed=7, n=8000):
    import numpy as np
    rng = np.random.default_rng(seed)
    key = rng.uniform(55.0, 80.0, n)
    return ft.fit_table(np.round(key + rng.normal(0, 9.0, n)), key)


def _quotes(*rows):
    return pd.DataFrame([{"bookmaker": b, "total_line": ln, "over_price": op, "under_price": up,
                          "over_link": f"{b}/o", "under_link": f"{b}/u"} for b, ln, op, up in rows])


ART = {"map": {"a": -2.0, "b": 0.485}, "_T": _table()}
FG = {"cons": 140.0, "nb": 5}                           # the model expects 65.9 in the half
UNDER_Q = _quotes(("fanduel", 69.5, -120, +100), ("draftkings", 69.5, -110, -110))
OVER_Q = _quotes(("fanduel", 61.5, +100, -120), ("draftkings", 61.5, -110, -110))


def test_an_under_is_not_bet_when_the_favourite_lays_twelve_in_the_half():
    assert ft.UNDER_BIG_FAVOURITE == P.BIG_FAVOURITE["first_half"] == 12.0
    plain = ft.decide("g", UNDER_Q, FG, None, ART, 0.02)
    assert plain.status == "bets" and plain.best.side == "under"                         # the replay's call
    assert ft.decide("g", UNDER_Q, FG, None, ART, 0.02, fav_lays=11.5).status == "bets"
    d = ft.decide("g", UNDER_Q, FG, None, ART, 0.02, fav_lays=12.0)
    assert d.status == "big_favourite" and d.best.side == "under"
    assert "the favourite lays 12 in the half" in d.detail
    assert ft.decide("g", UNDER_Q, FG, None, ART, 0.02, fav_lays=14.5).status == "big_favourite"


def test_an_over_and_a_game_under_the_cut_are_untouched_by_it():
    over = ft.decide("g", OVER_Q, FG, None, ART, 0.02, fav_lays=14.5)
    assert over.status == "bets" and over.best.side == "over"
    low = ft.decide("g", UNDER_Q, FG, None, ART, 0.90, fav_lays=14.5)
    assert low.status == "below_cut"                                                     # not a bet anyway


def test_the_set_aside_under_is_still_written_as_a_priced_none_row():
    from scripts.ncaab_first_half_total_card import SCORED_NO_BET, pick_rows
    assert "big_favourite" in SCORED_NO_BET
    d = ft.decide("NCAAB_g", UNDER_Q, FG, None, ART, 0.02, fav_lays=14.5)
    games = {"NCAAB_g": {"home": "Kansas", "away": "Duke", "game_date": "2026-11-12",
                         "commence_time": "2026-11-13T00:00:00Z"}}
    (r,), refused = pick_rows([d], games, 1000.0)
    assert r["signal_type"] == "NONE" and r["pick_side"] == "under" and r["scored_line"] == 69.5
    assert r["kelly_fraction"] == 0.0 and not refused


def test_the_card_reads_the_favourites_number_off_its_own_decision_fetch():
    from scripts.ncaab_first_half_total_card import favourite_lays
    cut = datetime(2026, 11, 12, 23, 0, tzinfo=timezone.utc)

    class C:
        def execute(self, sql, params):
            self.sql, self.params = " ".join(sql.split()), params
            rows = [("g1", -14.5), ("g1", -15.0), ("g1", -14.0), ("g2", 3.5), ("g3", "99")]
            return type("Cur", (), {"fetchall": lambda _s: rows})()

    c = C()
    got = favourite_lays(c, {"g1": cut, "g2": cut, "g3": cut})
    assert got == {"g1": 14.5, "g2": 3.5}                                                # the median; a typo dropped
    assert "o.market = 'spreads_h1'" in c.sql and "o.created_at::timestamptz = t.cut" in c.sql
    assert favourite_lays(c, {}) == {}


# ── every writer asks ────────────────────────────────────────────────────────

CARDS = ("ncaab_first_half_total_card", "ncaab_first_half_spread_card", "ncaab_spread_card",
         "ncaab_total_card", "ncaabw_total_card")


@pytest.mark.parametrize("card", CARDS)
def test_each_card_holds_the_pair_back_before_it_publishes(card):
    src = (ROOT / "scripts" / f"{card}.py").read_text(encoding="utf-8")
    assert "from models import cbb_pairs" in src
    i = src.index("refused = pick_rows(")
    j = src.index("cbb_pairs.hold_back(conn, ", i)
    k = src.index("publish(conn, ", i)
    assert i < j < k, f"{card}: the pair check must sit between the rows and the write"


def test_the_first_half_total_card_passes_the_favourites_number_to_the_decision():
    src = (ROOT / "scripts" / "ncaab_first_half_total_card.py").read_text(encoding="utf-8")
    assert "lays = favourite_lays(conn, cuts)" in src
    assert "books=books, min_price=floor, fav_lays=lays.get(gid))" in src


def test_the_womens_loop_declines_an_under_beside_a_big_favourites_spread(monkeypatch):
    from tests import test_ncaabw_live_loop as T
    from tests import _ncaabw_live_synth as S
    import models.ncaabw_live_ht as M
    art = M.load_artifact()
    half = S.half_end(S.build_plays())
    # 152.5 at the half of a 40-30 game against a pre-game 130: the model takes the under
    loop, db, clock, half, slot = T.standard(
        art, monkeypatch, books_at=lambda now: T.books(half + timedelta(seconds=120), total=(152.5, -110, -110)))
    db.spread_bet = "Iowa -24.5"
    loop.tick()
    row = db.final[S.GAME_ID]
    assert row["side"] == "under" and row["outcome"] == "declined"
    assert row["reason"].startswith("paired_with:Iowa -24.5") and db.picks == []


def test_the_womens_loop_still_bets_an_over_beside_that_spread(monkeypatch):
    from tests import test_ncaabw_live_loop as T
    from tests import _ncaabw_live_synth as S
    import models.ncaabw_live_ht as M
    loop, db, clock, half, slot = T.standard(M.load_artifact(), monkeypatch)
    db.spread_bet = "Iowa -24.5"
    loop.tick()
    assert db.final[S.GAME_ID]["outcome"] == "bet" and db.picks[0]["pick_side"] == "over"


def test_the_womens_loop_asks_the_shared_check_with_its_own_bet():
    import inspect
    import models.ncaabw_live_loop as LP
    src = inspect.getsource(LP.Loop.decide)
    assert 'paired_bet(\n                    self.c(), c.game_id, M.MODEL_ID, b["side"], float(b["line"]))' in src
    assert "cbb_pairs.clash(conn, game_id, model_id, side, line)" in inspect.getsource(LP.paired_bet)


def test_the_mens_loop_declines_the_second_of_the_pair(monkeypatch):
    from tests import test_ncaab_live_loop as T
    import models.ncaab_live_ig as M
    art = M.load_artifact()
    loop, db, clock, w, slot = T.standard(art, monkeypatch)
    db.paired = "paired_with:First Half Under 74.5 (an under on the same game)"
    loop.tick()
    row = db.ledger[(T.S.GAME_ID, M.SPREAD_H1)]
    assert row["outcome"] == "declined" and row["reason"].startswith("paired_with:First Half Under 74.5")
    assert db.picks == []


def test_the_mens_loop_asks_the_shared_check_with_its_own_bet():
    import inspect
    import models.ncaab_live_loop as LP
    src = inspect.getsource(LP.Loop.decide)
    assert 'paired_bet(\n                    self.c(), c.game_id, rule.model_id, b["side"], float(b["line"]))' in src
    assert "cbb_pairs.clash(conn, game_id, model_id, side, line)" in inspect.getsource(LP.paired_bet)
    # a bet of this pass is in `picks` before the next decision is taken: the write and its
    # commit sit inside the loop over the decisions, after the check
    assert src.index("paired_bet(") < src.index("write_bet(self.c(), pick)") < src.index("self.c().commit()")
