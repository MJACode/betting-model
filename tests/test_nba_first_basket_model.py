"""NBA first basket (nba_prop_first_basket): the decision is the graded rule, settlement is each
book's own rule, and the pick row survives every publisher's checks.

The rule (models/nba_first_basket.py, test 2b of data/local/research/nba_research/first_basket/
prereg.md): 0.25 x the model + 0.75 x the median no-vig of the OTHER deciding books quoting that
starter (three or more), EV at that book's price, one bet a game, EV >= 0.05.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

import config
import models.nba_first_basket as fbm
from tracking.pick_integrity import pick_problems

TIP = datetime(2026, 11, 21, 0, 10, tzinfo=timezone.utc)
GAME = {"game_id": "NBA_2026-11-20_CHA_ATL", "game_date": "2026-11-20", "tip": TIP,
        "home": "ATL", "away": "CHA"}
HOME = ["Trae Young", "Dyson Daniels", "Zaccharie Risacher", "Jalen Johnson", "Onyeka Okongwu"]
AWAY = ["LaMelo Ball", "Brandon Miller", "Miles Bridges", "Kon Knueppel", "Ryan Kalkbrenner"]
BOOKS = ("draftkings", "fanduel", "betmgm", "williamhill_us")


def _names():
    by_team = {("ATL", fbm.name_norm(n)): 100 + i for i, n in enumerate(HOME)}
    by_team.update({("CHA", fbm.name_norm(n)): 200 + i for i, n in enumerate(AWAY)})
    return fbm.Names(by_team, {})


def _quotes(prices: dict[str, dict[str, float]]):
    return [{"book": b, "player": p, "price": v, "fetch": "2026-11-20T23:58:00+00:00"}
            for b, d in prices.items() for p, v in d.items()]


def _flat(price=900.0, books=BOOKS):
    return {b: {p: price for p in HOME + AWAY} for b in books}


def _state():
    return fbm.State(pd.DataFrame(columns=["game_id", "espn_id", "side", "team", "name", "starter", "pts"]))


def test_the_market_alone_at_a_flat_board_does_not_bet():
    # Every book the same price: the median no-vig equals each book's own, so EV is the margin.
    bet, why = fbm.decide(GAME, _quotes(_flat()), _state(), _names())
    assert bet is None and why.startswith("best_ev")


def test_one_book_out_of_line_is_the_bet_at_the_blend_the_grade_used():
    prices = _flat(900.0)
    prices["fanduel"]["Trae Young"] = 2000.0          # FanDuel hangs him far longer than the rest
    bet, why = fbm.decide(GAME, _quotes(prices), _state(), _names())
    assert bet is not None, why
    assert (bet.player, bet.book, bet.price) == ("Trae Young", "fanduel", 2000.0)
    # the reference is the three OTHER books' median no-vig, not FanDuel's own
    imp = 1 / fbm.american_to_decimal(900.0)
    assert bet.p_market == pytest.approx(imp / (10 * imp))
    assert bet.prob == pytest.approx(fbm.W_MODEL * bet.p_model + (1 - fbm.W_MODEL) * bet.p_market)
    assert bet.ev == pytest.approx(bet.prob * fbm.american_to_decimal(2000.0) - 1)
    assert bet.ev >= config.min_ev_for(fbm.MODEL_ID) == 0.05


def test_a_starter_two_other_books_quote_has_no_reference():
    prices = _flat(900.0, BOOKS[:3])                   # three books: the bet book has only two others
    prices["fanduel"]["Trae Young"] = 3000.0
    bet, why = fbm.decide(GAME, _quotes(prices), _state(), _names(), books=BOOKS)
    assert bet is None and why == "no_reference"


def test_the_floor_is_the_models_own_and_its_probability_is_its_own():
    assert fbm.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.min_ev_for(fbm.MODEL_ID) == 0.05
    assert fbm.MODEL_ID in config.ACTION_THRESHOLDS
    assert config.SCORING_METHODS[fbm.MODEL_ID] == "rule"


def test_a_pick_names_only_a_book_config_lets_a_pick_name():
    assert set(fbm.deciding_books()) <= set(config.BEST_LINE_BOOKMAKERS)
    assert "betparx" not in fbm.deciding_books() and "bovada" not in fbm.deciding_books()


# ── the starters ──────────────────────────────────────────────────────────────

def _listed(names, n=4):
    return {fbm.name_norm(x): list(BOOKS[:n]) for x in names}


def test_a_name_neither_history_has_fills_the_one_side_short():
    rookie = "Brand New Rookie"
    names = _names()
    listed = _listed(HOME + AWAY[:4] + [rookie])
    sides, why = fbm.assign_starters(listed, GAME, names)
    assert why is None
    assert fbm.name_norm(rookie) in {nm for nm, _ in sides["A"]}
    assert dict(sides["A"])[fbm.name_norm(rookie)] == fbm.new_player_id(fbm.name_norm(rookie)) < 0


def test_a_side_listing_six_keeps_the_five_the_most_books_list():
    extra = "Garrison Mathews"
    names = _names()
    names.by_team[("ATL", fbm.name_norm(extra))] = 999
    listed = _listed(HOME + AWAY)
    listed[fbm.name_norm(extra)] = list(BOOKS[:3])     # one book fewer than the five starters
    sides, why = fbm.assign_starters(listed, GAME, names)
    assert why is None and 999 not in {pid for _, pid in sides["H"]}


def test_a_side_at_four_takes_its_thinly_listed_name_else_a_stand_in():
    names = _names()
    listed = _listed(HOME[:4] + AWAY)
    thin = {fbm.name_norm(HOME[4]): ["draftkings"]}
    sides, why = fbm.assign_starters(listed, GAME, names, thin)
    assert why is None and 104 in {pid for _, pid in sides["H"]}
    sides, why = fbm.assign_starters(listed, GAME, names, {})
    assert why is None and min(pid for _, pid in sides["H"]) < 0


def test_a_side_at_three_is_declined():
    sides, why = fbm.assign_starters(_listed(HOME[:3] + AWAY), GAME, _names(), {})
    assert sides == {} and why.startswith("starters_listed home=3")


# ── settlement, each book's own rule ──────────────────────────────────────────

def test_field_goal_books_pay_the_first_made_field_goal_the_rest_the_first_points():
    ft_shooter, fg_maker = 1, 2
    for book in ("draftkings", "betmgm", "fanatics", "betrivers"):
        assert fbm.first_basket_outcome(book, True, fg_maker, ft_shooter, fg_maker) == 1
        assert fbm.first_basket_outcome(book, True, ft_shooter, ft_shooter, fg_maker) == 0
    for book in ("fanduel", "williamhill_us", "hardrockbet"):
        assert fbm.first_basket_outcome(book, True, ft_shooter, ft_shooter, fg_maker) == 1
        assert fbm.first_basket_outcome(book, True, fg_maker, ft_shooter, fg_maker) == 0
    assert set(fbm.deciding_books()) <= fbm.FIELD_GOAL_BOOKS | fbm.ANY_SCORE_BOOKS


def test_a_non_starter_is_no_action_at_every_book():
    for book in fbm.GRADED_BOOKS:
        assert fbm.first_basket_outcome(book, False, 1, 1, 1) is None


def test_facts_take_a_free_throw_first_and_the_first_field_goal_apart():
    gmap = {401: "NBA_2026-11-18_ATL_OKC"}
    plays = [(401, 5, 77, "Free Throw - 1 of 2", True, "H"),
             (401, 9, 88, "Driving Layup Shot", True, "A")]
    box = [(401, 77, "Shai Gilgeous-Alexander", True), (401, 88, "Trae Young", True),
           (401, 55, "Bench Guy", False)]
    f = fbm.facts_from_rows(gmap, plays, box)["NBA_2026-11-18_ATL_OKC"]
    assert (f["first_any"], f["first_fg"]) == (77, 88)
    assert fbm.name_norm("Bench Guy") not in f["starters"] and f["played"][fbm.name_norm("Bench Guy")] == 55


def test_a_game_with_no_field_goal_yet_has_no_facts():
    assert fbm.facts_from_rows({401: "G"}, [(401, 5, 77, "Free Throw - 1 of 2", True, "H")], []) == {}


class _FakeConn:
    """Routes the settler's reads by table; records every UPDATE."""

    def __init__(self, picks, books):
        self.picks, self.books, self.updates, self._rows = picks, books, [], []

    def execute(self, sql, params=None):
        s = " ".join(sql.split())
        if s.upper().startswith("UPDATE"):
            # the result is a parameter, or (a no-action) a literal in the statement
            res = "NO_ACTION" if "'NO_ACTION'" in s else params[0]
            self.updates.append((res, params[-1]))
            self._rows = []
        elif "SELECT decision_book FROM picks" in s:
            self._rows = [(self.books[params[0]],)]
        elif "FROM picks p" in s:
            self._rows = self.picks
        elif "FROM nba_pbp_games" in s:
            self._rows = [(401, "NBA_2026-11-18_ATL_OKC")]
        elif "FROM nba_pbp " in s or "FROM nba_pbp WHERE" in s:
            self._rows = [(401, 5, 77, "Free Throw - 1 of 2", True, "H"),
                          (401, 9, 88, "Driving Layup Shot", True, "A")]
        elif "FROM nba_pbp_box" in s:
            self._rows = [(401, 77, "Shai Gilgeous-Alexander", True), (401, 88, "Trae Young", True),
                          (401, 55, "Bench Guy", False)]
        else:
            self._rows = []
        return self

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._rows[0] if self._rows else None


def test_the_settler_grades_each_pick_at_its_own_books_rule():
    from tracking import paper_tracker as pt
    gid = "NBA_2026-11-18_ATL_OKC"

    def pick(pid, name):
        return (pid, gid, fbm.MODEL_ID, "over", 900.0, 1.0, 0.5, "espn:1", f"{name} Over 0.5 First Basket",
                fbm.MARKET, name)
    picks = [pick(1, "Shai Gilgeous-Alexander"), pick(2, "Shai Gilgeous-Alexander"),
             pick(3, "Bench Guy"), pick(4, "Nobody Here")]
    conn = _FakeConn(picks, {1: "fanduel", 2: "draftkings", 3: "fanduel", 4: "fanduel"})
    pt._settle_prop_picks(conn, "2026-11-18", "2026-11-19T12:00:00Z")
    result = {pid: res for res, pid in conn.updates}
    assert result[1] == "WIN"        # FanDuel pays the free throw that opened the scoring
    assert result[2] == "LOSS"       # DraftKings pays the first made field goal: Trae Young's
    assert result[3] == "NO_ACTION"  # did not start
    assert result[4] == "NO_ACTION"  # did not play


# ── the pick row ──────────────────────────────────────────────────────────────

def test_the_pick_row_passes_the_label_check_and_carries_the_book_taken():
    from scripts.nba_first_basket_card import pick_label, pick_rows
    prices = _flat(900.0)
    prices["fanduel"]["Trae Young"] = 2000.0
    bet, _ = fbm.decide(GAME, _quotes(prices), _state(), _names())
    assert pick_label(bet) == "Trae Young Over 0.5 First Basket"
    assert not pick_problems(pick_label(bet), fbm.SIDE, fbm.LINE, fbm.MODEL_ID, prop_market=fbm.MARKET)
    row = pick_rows([bet], 1000.0)[0]
    assert (row["decision_book"], row["decision_odds"], row["dk_odds"]) == ("fanduel", 2000.0, 900.0)
    assert row["line_book"] is None and row["best_book"] == "fanduel"
    assert row["player_id"] == f"espn:{bet.espn_id}" and row["prop_market"] == "player_first_basket"
    assert row["model_probability"] == round(bet.prob, 4)
    assert row["model_id"] == "nba_prop_first_basket" and row["signal_type"] == "BET"


def test_newest_fetch_keeps_one_fetch_inside_the_window_and_none_after_tip():
    from scripts.nba_first_basket_card import newest_fetch
    t = lambda m: (TIP - timedelta(minutes=m)).isoformat()   # noqa: E731
    rows = [(GAME["game_id"], "Trae Young", "fanduel", 900, t(30), None),   # before the window
            (GAME["game_id"], "Trae Young", "fanduel", 950, t(15), None),
            (GAME["game_id"], "Trae Young", "fanduel", 1000, t(8), None),   # the newest in window
            (GAME["game_id"], "Trae Young", "fanduel", 1100, t(-1), None)]  # after tip
    got = newest_fetch(rows, {GAME["game_id"]: GAME}, TIP - timedelta(minutes=6))
    assert [q["price"] for q in got[GAME["game_id"]]] == [1000.0]


def test_the_model_is_a_prop_to_every_settler_and_view_that_reads_the_name():
    # The settlers select props by name, `nba_prop_%` (tracking/paper_tracker._settle_prop_picks),
    # and the game settlers leave the same names out; the app types a model a player prop by `_prop_`.
    assert re.fullmatch(r"nba_prop_.+", fbm.MODEL_ID)


# ── the five-minute window job ───────────────────────────────────────────────

def test_the_window_plans_undecided_games_3_to_22_minutes_out(monkeypatch, tmp_path):
    import scripts.nba_first_basket_card as fb_card
    from tests.test_nba_prop_window import _PlanConn, _game, _plan
    monkeypatch.setattr(fb_card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(fb_card, "CACHE_DIR", tmp_path)
    conn = _PlanConn([_game("AT2", 2), _game("AT3", 3), _game("AT22", 22), _game("AT23", 23),
                      _game("BET", 10), _game("AT50", 50)], taken={"BET"})
    p = _plan(conn, monkeypatch)
    assert p.first_basket == ["AT22", "AT3"] and p.publish
    # no prepared state for today and a game 22-62 minutes out: warm it
    assert p.first_basket_warm


def test_the_window_does_not_warm_a_state_already_prepared(monkeypatch, tmp_path):
    import scripts.nba_first_basket_card as fb_card
    import scripts.nba_prop_window as win
    from tests.test_nba_prop_window import NOW, _PlanConn, _game, _plan
    monkeypatch.setattr(fb_card, "ensure_decisions_table", lambda c: None)
    monkeypatch.setattr(fb_card, "CACHE_DIR", tmp_path)
    fb_card.cache_path(NOW.astimezone(win._ET).date().isoformat()).write_bytes(b"x")
    assert not _plan(_PlanConn([_game("AT50", 50)]), monkeypatch).first_basket_warm


def test_a_tick_decides_first_basket_before_the_stat_props_and_warms_after_publishing(monkeypatch):
    import scripts.nba_prop_window as win
    from tests.test_nba_prop_window import _tick
    ran, published = _tick(monkeypatch, win.Plan(decide=["G1"], close=[], first_basket=["G5"],
                                                 first_basket_warm=True))
    labels = [label for label, _, _ in ran]
    assert labels == ["nba-first-basket-fetch", "nba-first-basket", "nba-prop-window-fetch",
                      "nba-props", "nba-first-basket-warm"]
    assert ran[0][1][-2:] == ["--fetch", "G5"] and ran[1][1][-2:] == ["--step", "nba-first-basket"]
    assert published == ["nba-prop-window"]



def test_the_app_names_first_basket_as_sold_everywhere_it_titles_a_pick():
    """The stored label keeps "Over 0.5" (every reader keyed on "Over" parses it); the app titles it
    "<player> First Basket" through one helper, and the Signals card's own table agrees."""
    from pathlib import Path
    lib = Path(__file__).resolve().parent.parent / "mobile" / "src" / "lib"
    markets = (lib / "markets.ts").read_text(encoding="utf-8")
    signals = (lib / "signalsCard.ts").read_text(encoding="utf-8")
    assert "if (market === 'player_first_basket') return 'First Basket';" in markets
    assert "if (market === 'player_first_basket') return side === 'under';" in markets
    assert "player_first_basket: 'First Basket'," in signals
    assert "nba_prop_first_basket: 'player_first_basket'," in markets
