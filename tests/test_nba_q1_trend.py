"""nba_q1_trend (models/nba_q1_trend.py): the rule is the eighth NBA search's own, the live quotes are read at the
right instant, the bet is the hot team's at the best offer, it settles on the first quarter alone, and its label and
fetch carry the HOME number the right way round.

The replay that reproduces all 88 graded bets through decide() reads the research cache, so it is a script
(scripts/nba_q1_trend_replay.py), not a test; its result is in docs/sports/nba.md."""
from __future__ import annotations

import os

import numpy as np
import pandas as pd
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.nba_q1_trend as q1  # noqa: E402
from scripts import nba_game8_q1_trends as G8  # noqa: E402

TIP = pd.Timestamp("2026-11-20T00:10:00Z")
T = TIP - pd.Timedelta(minutes=55)


@pytest.fixture(scope="module")
def art():
    return q1.load_artifact()


def _team_rows(team: str, venue: str, results: list[int], start: str, season: int = 2027,
               pf: float = 30.0, pa: float = 27.0) -> list[dict]:
    """One team's earlier games at one venue, oldest first: ats per game (+1 cover, -1 not)."""
    d0 = pd.Timestamp(start)
    return [{"game_id": f"G_{team}_{venue}_{i}", "season": season,
             "game_date": (d0 + pd.Timedelta(days=2 * i)).date().isoformat(),
             "tip": (d0 + pd.Timedelta(days=2 * i, hours=23)).tz_localize("UTC"),
             "team": team, "venue": venue, "ats": float(r), "ou": 0.0, "pf": pf, "pa": pa}
            for i, r in enumerate(results)]


def _history(home_last10, away_last10, home_pf=30.0, home_pa=27.0, away_pf=27.0, away_pa=30.0):
    rows = (_team_rows("DEN", "home", home_last10, "2026-10-21", pf=home_pf, pa=home_pa)
            + _team_rows("LAC", "away", away_last10, "2026-10-22", pf=away_pf, pa=away_pa))
    return pd.DataFrame(rows)


def _target():
    return pd.DataFrame([{"game_id": "NBA_2026-11-19_LAC_DEN", "season": 2027, "game_date": "2026-11-19",
                          "home_team": "DEN", "away_team": "LAC"}])


def _quotes(rows):
    """rows: (book, home number, home price, away price) at T."""
    out = []
    for book, line, ph, pa in rows:
        out.append({"game_id": "NBA_2026-11-19_LAC_DEN", "season": 2027, "game_date": "2026-11-19", "tip": TIP,
                    "market": q1.MARKET, "book": book, "snapshot_at": T, "fetch_at": T, "line": float(line),
                    "price_a": float(ph), "price_b": float(pa), "coherent": True,
                    "link_a": f"{book}-home", "link_b": f"{book}-away", "book_update_at": T})
    return pd.DataFrame(out)


TIMES = pd.DataFrame({"game_id": ["NBA_2026-11-19_LAC_DEN"], "T": [T]})
# DEN at home: last 10 = 3-7 earlier, then 5-0 in the last 5 -> last-5 net +5, last-10 net +... ; LAC on the road
HOT_HOME = [1, -1, 1, 1, -1, 1, 1, 1, 1, 1]            # last 5: +5; last 10: +6
COLD_AWAY = [-1, -1, 1, -1, -1, 1, -1, 1, -1, -1]      # last 5: -1 (2-3); last 10: -4


def test_the_signal_is_the_labs_own(art):
    """signals() against scripts.nba_game8_q1_trends.signals on the same inputs, for the step window."""
    rng = np.random.default_rng(5)
    n = 400
    inp = pd.DataFrame({"game_id": [f"g{i}" for i in range(n)], "season": 2027, "game_date": "2026-11-19"})
    for c in ("h_ats5", "a_ats5"):
        inp[c] = rng.choice([-5, -3, -2, -1, 1, 3, 5, np.nan], n)
    for c in ("h_ats10", "a_ats10"):
        inp[c] = rng.integers(-8, 9, n).astype(float)
    for c in ("h_ou5", "a_ou5", "h_ou10", "a_ou10"):
        inp[c] = 0.0
    for c in ("h_n", "a_n"):
        inp[c] = rng.integers(3, 12, n).astype(float)
    # whole first-quarter averages, so a projection lands exactly on a half-point number and the check's strict
    # inequality is tested on its edge
    for c in ("h_pf", "h_pa", "a_pf", "a_pa"):
        inp[c] = rng.integers(24, 33, n).astype(float)
    for c in ("h_pn", "a_pn", "h_pace", "a_pace", "lg_pace"):
        inp[c] = 1.0
    numbers = pd.DataFrame({"game_id": inp["game_id"], "market": q1.MARKET,
                            "number": rng.choice([-2.5, -1.5, -0.5, 0.5, 1.5, 2.5], n)})
    lab = G8.signals(inp, numbers)
    mine = q1.signals(inp, numbers)
    w = q1.WINDOW
    home = lab[f"pick_{w}"] == "home"
    hot_number = np.where(home, numbers["number"], -numbers["number"])
    proj = ((inp["h_pf"] + inp["a_pa"]) - (inp["a_pf"] + inp["h_pa"])) / 2.0
    edge = lab[f"pick_{w}"].notna() & np.isclose(np.where(home, proj, -proj) + hot_number, 0.0)
    assert edge.sum() > 0                     # games exactly on the check's edge are in the sample
    assert (lab[f"pick_{w}"].fillna("none").astype(str).to_numpy()
            == mine[f"pick_{w}"].fillna("none").astype(str).to_numpy()).all()
    np.testing.assert_array_equal(lab[f"k_{w}"].to_numpy(float), mine[f"k_{w}"].to_numpy(float))
    np.testing.assert_array_equal(lab[f"chk_{w}"].to_numpy(bool), mine[f"chk_{w}"].to_numpy(bool))
    assert mine[f"chk_{w}"].sum() > 10 and (mine[f"pick_{w}"] == "home").sum() > 5


def test_a_step_game_bets_the_hot_team_at_the_best_offer(art):
    hist = _history(HOT_HOME, COLD_AWAY)
    quotes = _quotes([("pinnacle", -1.5, -110, -110), ("draftkings", -1.5, -115, -105),
                      ("fanduel", -1.5, -105, -115), ("betmgm", -1.5, -112, -108)])
    bets, decisions, diag = q1.decide(_target(), quotes, hist, TIMES, art)
    assert diag["bets"] == 1, (diag, decisions)
    b = bets[0]
    assert b.side == "home" and b.book == "fanduel" and b.price == -105 and b.line == -1.5
    assert b.dk_price == -115                         # DraftKings' own home price at this number
    assert b.p_model == pytest.approx(b.p_fair + q1.uplift(art, 2027))
    assert b.link == "fanduel-home"


def test_the_away_team_is_bet_at_its_own_price_and_the_home_number(art):
    hist = _history([1, -1, -1, -1, -1, 1, -1, 1, -1, -1], [1, 1, -1, 1, 1, 1, 1, 1, 1, 1],
                    home_pf=27.0, home_pa=30.0, away_pf=30.0, away_pa=27.0)
    quotes = _quotes([("pinnacle", 1.5, -110, -110), ("draftkings", 1.5, -108, -112),
                      ("fanduel", 1.5, -115, -104)])
    bets, decisions, diag = q1.decide(_target(), quotes, hist, TIMES, art)
    assert diag["bets"] == 1, (diag, [d.detail for d in decisions])
    b = bets[0]
    assert b.side == "away" and b.book == "fanduel" and b.price == -104
    assert b.line == 1.5                                # the HOME number, not the away team's -1.5
    assert b.dk_price == -112 and b.link == "fanduel-away"


def test_k_under_two_is_no_bet(art):
    # last 5 still 5-0 against 2-3, but the last 10 only +1 against -1 (a push among the away team's earlier five):
    # k = 1, a step game one short of the cut
    hist = _history([-1, -1, -1, -1, 1, 1, 1, 1, 1, 1], [1, -1, 1, -1, 0, 1, -1, 1, -1, -1])
    quotes = _quotes([("pinnacle", -1.5, -110, -110), ("fanduel", -1.5, -105, -115)])
    bets, decisions, diag = q1.decide(_target(), quotes, hist, TIMES, art)
    assert not bets and diag["below_cut"] == 1 and decisions[0].detail.startswith("below_cut")
    assert decisions[0].k == 1.0 and decisions[0].pick == "home"


def test_the_season_average_check_can_refuse(art):
    # the hot home team scores 24 and allows 31 a first quarter: its projection does not cover -1.5
    hist = _history(HOT_HOME, COLD_AWAY, home_pf=24.0, home_pa=31.0, away_pf=31.0, away_pa=24.0)
    quotes = _quotes([("pinnacle", -1.5, -110, -110), ("fanduel", -1.5, -105, -115)])
    bets, decisions, diag = q1.decide(_target(), quotes, hist, TIMES, art)
    assert not bets and diag["check_fails"] == 1


def test_a_record_reads_only_earlier_games(art):
    """A game on today's date at the venue is not in the record: with only nine earlier home games DEN has no
    last-10 record, whatever today's own row says."""
    h = _team_rows("DEN", "home", HOT_HOME[1:], "2026-10-21")
    today = _team_rows("DEN", "home", [1], "2026-11-19")
    hist = pd.DataFrame(h + today + _team_rows("LAC", "away", COLD_AWAY, "2026-10-22"))
    quotes = _quotes([("pinnacle", -1.5, -110, -110), ("fanduel", -1.5, -105, -115)])
    bets, decisions, diag = q1.decide(_target(), quotes, hist, TIMES, art)
    assert not bets and diag["no_record"] == 1


def test_a_live_rows_fetch_instant_is_its_created_at_and_a_purchased_rows_its_snapshot():
    games = pd.DataFrame({"game_id": ["G1", "G2"], "season": 2027, "game_date": "2026-11-19", "tip": [TIP, TIP]})
    rows = pd.DataFrame([
        {"game_id": "G1", "bookmaker": "fanduel", "market": q1.MARKET, "snapshot_type": "open",
         "snapshot_at": (T - pd.Timedelta(minutes=30)).isoformat(), "created_at": T.isoformat(),
         "source": q1.LIVE_SOURCE, "spread_home": -1.5, "home_price": -110, "away_price": -110,
         "home_link": None, "away_link": None},
        {"game_id": "G2", "bookmaker": "fanduel", "market": q1.MARKET, "snapshot_type": "open",
         "snapshot_at": (TIP - pd.Timedelta(minutes=60)).isoformat(), "created_at": "2026-11-21T09:00:00+00:00",
         "source": q1.HISTORY_SOURCE, "spread_home": -1.5, "home_price": -110, "away_price": -110,
         "home_link": None, "away_link": None}])
    f = q1.quote_frame(rows, games).set_index("game_id")
    assert f.loc["G1", "fetch_at"] == T                                   # the live fetch instant
    assert f.loc["G2", "fetch_at"] == TIP - pd.Timedelta(minutes=60)      # the purchase's snapshot, not its storing
    assert f.loc["G1", "line"] == -1.5 and f.loc["G1", "price_a"] == -110


def test_it_settles_on_the_first_quarter_against_the_home_number():
    from data.ingestors.nba_period_scores import first_quarter_from_periods
    from tracking.paper_tracker import _compute_result, _market_for_pick
    assert _market_for_pick(q1.MODEL_ID) == "spreads_q1"
    rows = [(1, 30, 27), (2, 25, 28), (3, 27, 26), (4, 24, 29)]
    assert first_quarter_from_periods(rows, 106, 110) == (30, 27)
    assert first_quarter_from_periods(rows, 106, 111) is None          # does not add up to the final: pending
    assert first_quarter_from_periods(rows[:3], 82, 81) is None         # a quarter missing: pending
    # home -1.5 at a 30-27 first quarter: home covers, away loses; home -3 is a push
    r_home = _compute_result("home", "spreads_q1", 30, 27, None, None, None, -110, -1.5, None, 1.0)
    r_away = _compute_result("away", "spreads_q1", 30, 27, None, None, None, -110, -1.5, None, 1.0)
    r_push = _compute_result("home", "spreads_q1", 30, 27, None, None, None, -110, -3.0, None, 1.0)
    assert r_home[0] == "WIN" and r_away[0] == "LOSS" and r_push[0] == "PUSH"


def test_the_label_says_first_quarter_and_the_sides_own_number():
    from models.scorer import _build_pick_label
    from tracking.pick_integrity import pick_problems
    away = _build_pick_label("away", "LAC", "DEN", "spreads_q1", 1.5)
    home = _build_pick_label("home", "LAC", "DEN", "spreads_q1", -2.5)
    assert away == "DEN @ LAC — First Quarter DEN -1.5"
    assert home == "DEN @ LAC — First Quarter LAC -2.5"
    assert pick_problems(away, "away", 1.5, q1.MODEL_ID, "LAC", "DEN") == []
    assert pick_problems(home, "home", -2.5, q1.MODEL_ID, "LAC", "DEN") == []
    assert pick_problems("DEN @ LAC — DEN -1.5", "away", 1.5, q1.MODEL_ID, "LAC", "DEN")       # no First Quarter
    assert pick_problems("DEN @ LAC — First Quarter DEN +1.5", "away", 1.5, q1.MODEL_ID, "LAC", "DEN")  # sign


def test_the_live_fetch_keys_each_pair_on_the_home_number():
    from data.ingestors.nba_first_quarter_odds import parse_first_quarter
    markets = [{"key": "spreads_q1", "outcomes": [
        {"name": "Los Angeles Clippers", "point": -1.5, "price": -110},
        {"name": "Denver Nuggets", "point": 1.5, "price": -110},
        {"name": "Los Angeles Clippers", "point": -2.5, "price": 120},
        {"name": "Denver Nuggets", "point": 2.5, "price": -150}]}]
    rows = {r["spread_home"]: r for r in parse_first_quarter(markets, "Los Angeles Clippers", "Denver Nuggets")}
    assert set(rows) == {-1.5, -2.5}
    assert rows[-1.5]["home_price"] == -110 and rows[-1.5]["away_price"] == -110
    assert rows[-2.5]["home_price"] == 120 and rows[-2.5]["away_price"] == -150


def test_a_game_that_is_not_the_pattern_records_no_pick_and_says_why(art):
    """A night with one pattern game and one that is not. The second has no hot team, and its decision row must carry
    pick None and say not_a_step. With a text pick in the same column pandas files the missing one as NaN, which the
    rule read as a pick: the game was recorded "below_cut: k None" and its ledger row stored pick 'NaN' as text
    (measured in a temp table: Postgres casts the float to text on insert, so nothing failed and no bet changed).
    Found 2026-11-07 on tonight's real lines, where six of seven games were not the pattern."""
    hist = pd.concat([_history(HOT_HOME, COLD_AWAY),
                      pd.DataFrame(_team_rows("MIA", "home", [1, -1] * 5, "2026-10-21")
                                   + _team_rows("BOS", "away", [1, -1] * 5, "2026-10-22"))], ignore_index=True)
    targets = pd.concat([_target(), pd.DataFrame([{"game_id": "NBA_2026-11-19_BOS_MIA", "season": 2027,
                                                   "game_date": "2026-11-19", "home_team": "MIA",
                                                   "away_team": "BOS"}])], ignore_index=True)
    q = _quotes([("pinnacle", -1.5, -110, -110), ("fanduel", -1.5, -105, -115)])
    q2 = q.assign(game_id="NBA_2026-11-19_BOS_MIA")
    times = pd.DataFrame({"game_id": ["NBA_2026-11-19_LAC_DEN", "NBA_2026-11-19_BOS_MIA"], "T": [T, T]})
    bets, decisions, diag = q1.decide(targets, pd.concat([q, q2], ignore_index=True), hist, times, art)
    by = {d.game_id: d for d in decisions}
    assert diag["bets"] == 1 and diag["not_a_step"] == 1, diag
    d = by["NBA_2026-11-19_BOS_MIA"]
    assert d.pick is None and d.detail.startswith("not_a_step"), (d.pick, d.detail)
    assert by["NBA_2026-11-19_LAC_DEN"].pick == "home"
    assert all(not (isinstance(v, float) and v != v) for v in (d.pick, d.number))
