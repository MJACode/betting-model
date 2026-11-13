"""ncaab_first_half_total: the model's rules, its frozen artifact, its label,
its settlement, its card rows, its decision fetch and its registration.

The model (models/ncaab_first_half_total.py) is the NCAAB research's round 5,
family A_to, totals_h1, tip60, best book, cut 0.02, every game. Its build
(scripts/ncaab_first_half_total_build.py) replayed 2023-24..2025-26 through the
functions tested here and matched the research's bets game by game (side,
book, line, price): 2,529 of 2,529 without the -200 floor and 2,527 of 2,527
with it. The replay's numbers are pinned below through the artifact.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import data.ingestors.ncaab_first_half_odds as feed  # noqa: E402
import models.ncaab_first_half_spread as fh  # noqa: E402
import models.ncaab_first_half_total as ft  # noqa: E402

UTC = timezone.utc
HOME, AWAY = "Kansas", "Duke"


def _table(seed=7, n=8000):
    """A first-half total table on a synthetic sample: the total ~ round of a
    normal around 0.485 x T - 2, the key the same map."""
    rng = np.random.default_rng(seed)
    tot = rng.uniform(120, 165, n)
    key = 0.485 * tot - 2.0
    out = np.round(key + rng.normal(0, 9.0, n)).astype(int)
    return ft.fit_table(out, key)


T = _table()


# ── pricing ──────────────────────────────────────────────────────────────────

def test_the_table_is_the_research_s_total_grid_not_the_margin_s():
    assert T["grid"][0] == 30.0 and T["grid"][-1] == 110.0 and T["step"] == 0.25
    assert (T["klo"], T["khi"]) == (0, 200)
    # the spread model's own table keeps its margin grid
    m = fh.fit_table([0, 1, -1] * 200, [0.0] * 600)
    assert m["grid"][0] == -30.0 and (m["klo"], m["khi"]) == (-80, 80)


def test_the_three_outcomes_add_to_one_and_a_whole_number_carries_the_push():
    for mu in (55.3, 66.0, 71.25):
        for line in (64.5, 66.0, 70.5, 71.0):
            pw, pp, pl = ft.probs(mu, line, T)
            assert abs(float(pw + pp + pl) - 1) < 1e-12
            assert (float(pp) > 0) == (line == round(line))


def test_the_over_wins_when_the_first_half_s_points_are_above_the_line():
    side, edge, p = ft.price_quote(70.0, 65.5, -110, -110, T)
    assert int(side) == 1 and float(p) > 0.5           # mean above the line: the over
    pw, pp, pl = ft.probs(70.0, 65.5, T)
    assert abs(float(p) - float(pw / (pw + pl))) < 1e-12
    assert abs(float(edge) - (float(p) - 1 / 1.9090909090909092)) < 1e-12
    side, _, p = ft.price_quote(60.0, 65.5, -110, -110, T)
    assert int(side) == 2 and float(p) > 0.5           # mean below: the under


def test_the_edge_is_raw_against_each_side_s_own_price():
    side, edge, p = ft.price_quote(66.0, 66.0, -105, -125, T)
    pw, pp, pl = ft.probs(66.0, 66.0, T)
    q1 = float(pw / (pw + pl))
    e_over, e_under = q1 - 1 / ft.dec(-105), (1 - q1) - 1 / ft.dec(-125)
    assert abs(float(edge) - max(e_over, e_under)) < 1e-12
    assert int(side) == (1 if e_over >= e_under else 2)


def test_a_count_weighted_sample_rebuilds_the_same_table():
    rng = np.random.default_rng(3)
    tot = rng.choice(np.arange(125, 160.5, 0.5), 3000)
    h1 = np.round(0.485 * tot - 2 + rng.normal(0, 9, 3000)).astype(int)
    full = ft.fit_table(h1, 0.485 * tot - 2)
    s = pd.DataFrame({"t": tot, "h": h1}).groupby(["t", "h"]).size().reset_index(name="n")
    packed = ft.fit_table(s["h"], 0.485 * s["t"] - 2, weight=s["n"])
    assert np.abs(full["pmf"] - packed["pmf"]).max() < 1e-12


# ── the best quote and the decision ─────────────────────────────────────────

def _quotes(*rows):
    return pd.DataFrame([{"bookmaker": b, "total_line": ln, "over_price": op, "under_price": up,
                          "over_link": f"{b}/o", "under_link": f"{b}/u"} for b, ln, op, up in rows])


def _art():
    return {"map": {"a": -2.0, "b": 0.485}, "_T": T}


def test_ties_between_books_go_to_the_alphabetically_first_key():
    o = [ft.Offer("fanduel", 66.5, -110, -110, "under", 0.031, 0.55),
         ft.Offer("betmgm", 66.5, -110, -110, "under", 0.031, 0.55),
         ft.Offer("draftkings", 66.5, -110, -110, "under", 0.030, 0.55)]
    assert ft.best_offer(o).book == "betmgm"


def test_a_side_shorter_than_the_floor_is_set_aside_before_the_pick():
    """after_fact.py AF1: the quote's edge is -inf, so the next book takes the
    game; it is not refused afterwards."""
    o = [ft.Offer("betmgm", 76.5, +190, -250, "under", 0.20, 0.92),
         ft.Offer("fanduel", 69.5, -110, -110, "under", 0.10, 0.63)]
    assert ft.best_offer(o).book == "betmgm"
    assert ft.best_offer(o, min_price=-200).book == "fanduel"
    assert ft.best_offer(o[:1], min_price=-200) is None
    # -200 itself is allowed
    o[0].under_price = -200
    assert ft.best_offer(o, min_price=-200).book == "betmgm"


def test_a_game_whose_every_quote_is_too_short_is_decided_below_the_floor():
    fg = {"cons": 120.0, "nb": 4}          # mu = 56.2: an under at 70.5 is a lock
    d = ft.decide("g", _quotes(("fanduel", 70.5, +300, -400)), fg, None, _art(), 0.02,
                  min_price=-200)
    assert d.status == "below_floor" and d.best is None and len(d.offers) == 1


def test_a_game_with_no_full_game_consensus_is_decided_without_a_bet():
    d = ft.decide("g", _quotes(("fanduel", 66.5, -110, -110)), None, None, _art(), 0.02)
    assert d.status == "no_fg_line" and d.best is None


def test_no_bettable_first_half_quote_is_no_quote():
    d = ft.decide("g", _quotes(("pinnacle", 66.5, -110, -110)), {"cons": 140.0, "nb": 4}, None,
                  _art(), 0.02)
    assert d.status == "no_quote"


def test_the_cut_is_strict_and_the_best_quote_decides():
    fg = {"cons": 140.0, "nb": 5}          # mu = 65.9
    q = _quotes(("fanduel", 69.5, -120, +100), ("draftkings", 69.5, -110, -110),
                ("pinnacle", 69.5, -180, +150))
    d = ft.decide("g", q, fg, {"tau_home": 0.0, "tau_away": 0.0}, _art(), 0.02)
    assert d.status == "bets" and d.best.book == "fanduel" and d.best.side == "under"
    assert d.price == 100 and "pinnacle" not in {o.book for o in d.offers}
    assert abs(d.mu - (0.485 * 140.0 - 2.0)) < 1e-12
    at_cut = ft.decide("g", q, fg, None, _art(), d.best.edge)
    assert at_cut.status == "below_cut"


def test_the_two_teams_tendencies_are_added_not_subtracted():
    d = ft.decide("g", _quotes(("fanduel", 66.5, -110, -110)), {"cons": 140.0, "nb": 3},
                  {"tau_home": 0.4, "tau_away": 0.2}, _art(), 0.02)
    assert abs(d.mu - (0.485 * 140.0 - 2.0 + 0.3)) < 1e-12


# ── the team term ────────────────────────────────────────────────────────────

def _t(h, m=0):
    return pd.Timestamp(datetime(2026, 11, 10, h, m, tzinfo=UTC))


def _tg(rows):
    return pd.DataFrame(rows, columns=list(fh.TEAM_GAME_COLS))


def test_both_teams_carry_the_same_residual_and_the_line_s_tilt_comes_out():
    tg = _tg([("g1", 2027, _t(0), HOME, AWAY, 40, 30, 35, 30, -5.0, 140.0),   # dt = 70 - 65
              ("g3", 2027, _t(0), HOME, "Yale", 30, 30, 30, 30, None, 140.0)])  # no spread close: out
    res = ft.team_game_residuals(tg, alpha=-6.6, beta=-0.007)
    assert set(res["game_id"]) == {"g1"}
    want = 5 - (-0.007 * 140.0 - 6.6)
    assert np.allclose(res["r"], [want, want])


def test_a_team_term_counts_only_games_that_ended_and_shrinks_by_236():
    tg = _tg([("g1", 2027, _t(0), HOME, AWAY, 40, 30, 35, 30, -5.0, 140.0),
              ("g2", 2027, _t(20), HOME, "Iona", 30, 30, 30, 30, -2.0, 140.0)])
    res = ft.team_game_residuals(tg, alpha=0.0, beta=0.0)
    targets = pd.DataFrame({"game_id": ["x"], "home_team": [HOME], "away_team": [AWAY],
                            "stamp": [_t(21)]})    # g2 ends 22:30: not yet
    out = ft.team_effects(res, 2027, {HOME: [4.0, 10], AWAY: [-2.0, 4]}, targets,
                          k=ft.K_TOTAL, w_prev=ft.W_PREV).iloc[0]
    assert out["n_home"] == 1 and out["n_away"] == 1
    assert abs(out["tau_home"] - (5 + 0.5 * 4.0) / (1 + 0.5 * 10 + 236.0)) < 1e-12
    assert abs(out["tau_away"] - (5 + 0.5 * -2.0) / (1 + 0.5 * 4 + 236.0)) < 1e-12


# ── the frozen artifact ──────────────────────────────────────────────────────

def test_the_committed_2027_artifact_loads_and_carries_the_replay():
    art = ft.load_artifact(2027)
    assert art["season"] == 2027 and art["prior_season"] == 2026
    assert art["map"]["train_seasons"] == [2021, 2026]
    assert 0.47 < art["map"]["b"] < 0.50 and -2.5 < art["map"]["a"] < -1.0
    assert art["tilt"]["k"] == 236.0 and art["tilt"]["w_prev"] == 0.5
    assert len(art["prior_team_sums"]) > 300
    assert tuple(art["books"]) == ft.BOOKS and art["min_price"] == -200
    T27 = art["_T"]
    assert T27["grid"][0] == 30.0 and (T27["klo"], T27["khi"]) == (0, 200)
    # the table's mean sits on its key (a first-half total near 66 at T = 140)
    mu = ft.first_half_mean(140.0, 0.0, 0.0, art)
    pw, pp, pl = ft.probs(mu, round(mu) + 0.5, T27)
    assert 0.35 < float(pw) < 0.5


def test_the_replay_matched_the_research_game_by_game_and_its_maps_are_the_research_s():
    rp = ft.load_artifact(2027)["replay"]
    maps = {m["season"]: m for m in rp["maps"]}
    # r5_lib.season_models, the research's maps_db.csv
    assert abs(maps[2026]["a"] - -1.9748874924167727) < 1e-9
    assert abs(maps[2026]["b"] - 0.4855872048552734) < 1e-9 and maps[2026]["n"] == 26343
    assert abs(maps[2024]["a"] - -1.2958745940175829) < 1e-9 and maps[2024]["n"] == 14853
    # The replay is graded at the live cut (config, 0.025 from 2026-11-06; it
    # was 2,527 bets / +123.78 at 0.02). The research's own -200 version, cut
    # at the same 0.025, matches it game by game.
    assert rp["cut"] == config.MODEL_EDGE_THRESHOLDS[ft.MODEL_ID] == 0.025
    w = rp["with_floor"]
    assert w["pooled"]["bets"] == 1887 and w["pooled"]["units"] == 127.31
    vs = w["vs_research"]
    assert vs["identical_game_side_book_line_price"] == 1887
    assert vs["n_only_research"] == 0 and vs["n_only_replay"] == 0
    assert vs["max_edge_gap"] < 1e-12
    assert w["pooled"]["ci95"] == [1.51, 10.33]
    assert (w["2024"]["units"], w["2025"]["units"], w["2026"]["units"]) == (54.28, 44.03, 29.01)
    assert w["pooled"]["price_min"] >= -200
    assert rp["without_floor"]["pooled"]["bets"] == 1887


def test_the_artifact_for_another_season_is_refused():
    with pytest.raises(ValueError):
        ft.load_artifact(2028, path=ft.artifact_path(2027))
    with pytest.raises(ValueError):
        ft.load_artifact(path=fh.artifact_path(2027))       # the spread model's


def test_the_ev_floor_sits_under_the_smallest_ev_the_cut_admitted():
    art = ft.load_artifact(2027)
    assert config.min_ev_for(ft.MODEL_ID) <= art["replay"]["with_floor"]["min_ev"]
    assert art["replay"]["with_floor"]["pooled"]["price_min"] >= config.min_odds_for(ft.MODEL_ID)


# ── the label, and the check that guards it ──────────────────────────────────

def test_the_label_leads_with_the_matchup_and_says_first_half():
    from models.scorer import _build_pick_label
    assert _build_pick_label("under", HOME, AWAY, "totals_h1", 70.5) == \
        "Duke @ Kansas — First Half Under 70.5"


def test_the_integrity_check_reads_a_first_half_total_as_a_total():
    from tracking.pick_integrity import pick_problems
    mid = ft.MODEL_ID
    assert pick_problems("Duke @ Kansas — First Half Under 70.5", "under", 70.5, mid, HOME, AWAY) == []
    assert pick_problems("Duke @ Kansas — First Half Over 70.5", "under", 70.5, mid, HOME, AWAY)
    assert pick_problems("Duke @ Kansas — First Half Under 71.5", "under", 70.5, mid, HOME, AWAY)
    probs = pick_problems("Duke @ Kansas — Under 70.5", "under", 70.5, mid, HOME, AWAY)
    assert any("First Half" in p for p in probs)


# ── settlement ───────────────────────────────────────────────────────────────

class _Conn:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, sql, params=None):
        assert "ncaab_period_scores" in sql
        rows = self.rows

        class C:
            def fetchall(self_inner):
                return rows
        return C()


def test_it_settles_on_the_first_half_s_points_never_the_final():
    from tracking.paper_tracker import _compute_result, _market_for_pick, first_half_points
    assert _market_for_pick(ft.MODEL_ID) == "totals_h1"
    conn = _Conn([(1, 30, 33), (2, 40, 30), (3, 8, 6)])     # OT game: first half 30-33
    assert first_half_points(conn, "NCAAB_2026-11-10_duke_kansas", 78, 69) == (30, 33)
    h, a = 30, 33                                          # 63 first-half points, 147 in the game
    assert _compute_result("under", "totals_h1", h, a, None, None, 0, -110, None, 70.5, 0)[0] == "WIN"
    assert _compute_result("over", "totals_h1", h, a, None, None, 0, -110, None, 70.5, 0)[0] == "LOSS"
    assert _compute_result("under", "totals_h1", h, a, None, None, 0, -110, None, 63.0, 0)[0] == "PUSH"


def test_the_settler_routes_a_first_half_total_through_the_first_half():
    src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    i = src.index("def _settle_game_picks(")
    body = src[i:src.index("def _settle_game_picks_window", i)]
    assert 'elif market in ("totals_h1", "spreads_h1"):' in body
    assert "first_half_points(conn, game_id, home_score, away_score)" in body


# ── the card's rows ──────────────────────────────────────────────────────────

GAMES = {"g": {"home": HOME, "away": AWAY, "game_date": "2026-11-10",
               "commence_time": "2026-11-11T00:00:00Z"}}


def _decision(book="fanduel", side="under", line=70.5, op=-120, up=+100, dk=None, edge=0.05, p=0.55):
    offers = [ft.Offer(book, line, op, up, side, edge, p, f"{book}/o", f"{book}/u")]
    if dk is not None:
        offers.append(ft.Offer("draftkings", dk[0], dk[1], dk[2], side, 0.01, p, "dk/o", "dk/u"))
    return ft.Decision("g", "bets", "x", mu=66.0, fg_total=140.0, fg_books=5, best=offers[0],
                       offers=offers)


def test_a_bet_at_another_book_names_it_and_carries_draftkings_only_at_the_same_number():
    from scripts.ncaab_first_half_total_card import pick_rows
    rows, refused = pick_rows([_decision(dk=(70.5, -125, +105))], GAMES, 1000.0)
    r = rows[0]
    assert not refused
    assert (r["pick_side"], r["scored_line"], r["pick_label"]) == (
        "under", 70.5, "Duke @ Kansas — First Half Under 70.5")
    assert (r["decision_book"], r["decision_odds"], r["best_book"]) == ("fanduel", 100, "fanduel")
    assert r["dk_odds"] == 105 and r["line_book"] is None and r["dk_bet_link"] == "dk/u"
    assert abs(r["decision_edge"] - round(0.55 - 0.5, 4)) < 1e-9
    assert r["model_probability"] == 0.55 and r["signal_type"] == "BET" and r["sport"] == "NCAAB"
    rows, _ = pick_rows([_decision(dk=(69.5, -110, -110))], GAMES, 1000.0)
    r = rows[0]
    assert r["dk_odds"] is None and r["edge"] == 0.0 and r["line_book"] == "fanduel"


def test_a_bet_at_draftkings_has_no_best_book():
    from scripts.ncaab_first_half_total_card import pick_rows
    rows, _ = pick_rows([_decision(book="draftkings", side="over", op=+100, up=-120)], GAMES, 1000.0)
    r = rows[0]
    assert r["decision_book"] == "draftkings" and r["dk_odds"] == 100 and r["best_book"] is None
    assert r["dk_bet_link"] == "draftkings/o" and r["pick_label"].endswith("First Half Over 70.5")


def test_the_price_floor_and_the_ev_floor_refuse_a_bet():
    from scripts.ncaab_first_half_total_card import pick_rows
    rows, refused = pick_rows([_decision(up=-250, p=0.75, edge=0.04)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and refused["g"].startswith("below_price_floor")
    rows, refused = pick_rows([_decision(up=+100, p=0.51, edge=0.01)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and "g" in refused


def test_the_card_passes_the_floor_into_the_decision():
    src = (ROOT / "scripts" / "ncaab_first_half_total_card.py").read_text(encoding="utf-8")
    assert "floor = config.min_odds_for(MODEL_ID)" in src
    assert "books=books, min_price=floor, fav_lays=lays.get(gid))" in src


def test_the_book_ages_are_the_total_s_own_update_times():
    from scripts.ncaab_first_half_total_card import book_ages
    q = pd.DataFrame({"bookmaker": ["fanduel", "draftkings"],
                      "snapshot_at": ["2026-11-10T23:00:00Z", None]})
    assert book_ages(q, datetime(2026, 11, 10, 23, 2, 30, tzinfo=UTC)) == {"fanduel": 2.5}


# ── the decision fetch ───────────────────────────────────────────────────────

TIP = datetime(2026, 11, 11, 0, 0, tzinfo=UTC)
DATE = "2026-11-10"


def test_a_failed_tip_minus_60_call_is_retried_every_minute():
    t60 = TIP - timedelta(minutes=60)
    assert feed.due_mark(DATE, TIP, t60, None) == ("T-60", t60)
    # it failed: still due the next minute, unlike a history time
    assert feed.due_mark(DATE, TIP, t60 + timedelta(minutes=1), None, t60 + timedelta(seconds=3)) == ("T-60", t60)
    t50 = TIP - timedelta(minutes=50)
    assert feed.due_mark(DATE, TIP, t50 + timedelta(minutes=1), None, t50 + timedelta(seconds=3)) is None
    # an ok call after it satisfies it
    assert feed.due_mark(DATE, TIP, t60 + timedelta(minutes=2), t60 + timedelta(seconds=40)) is None


def test_an_11am_tip_s_15z_call_is_its_tip_minus_60_call():
    """15:00 UTC on the date is 60 minutes before an 11am ET tip: one fetch
    time, named for the decision so it is retried and decided on."""
    tip = datetime(2026, 11, 10, 16, 0, tzinfo=UTC)
    s = dict((t, m) for m, t in feed.slots(DATE, tip))
    assert s[datetime(2026, 11, 10, 15, 0, tzinfo=UTC)] == "T-60"
    assert len(s) == 8
    # and a 10:10am ET tip's 15:00 UTC call is the spread's tip minus 10
    tip = datetime(2026, 11, 10, 15, 10, tzinfo=UTC)
    assert dict((t, m) for m, t in feed.slots(DATE, tip))[tip - timedelta(minutes=10)] == "T-10"


def test_the_decision_calls_go_first():
    src = (ROOT / "data/ingestors/ncaab_first_half_odds.py").read_text(encoding="utf-8")
    assert "key=lambda g: (marks[g] not in DECISION_MARKS, games[g][\"tip\"], g)" in src
    assert feed.DECISION_MARKS == ("T-10", "T-60") and feed.TOTAL_DECISION_MARK == "T-60"


def test_the_window_plans_the_total_card_an_hour_out(monkeypatch):
    from scripts import ncaab_first_half_spread_card as spread_card
    from scripts import ncaab_first_half_total_card as total_card
    from scripts import ncaab_first_half_window as win
    now = TIP - timedelta(minutes=59, seconds=30)
    games = {"g": {"season": 2027, "game_date": DATE, "tip": TIP, "commence_time": "x",
                   "home": HOME, "away": AWAY},
             "late": {"season": 2027, "game_date": DATE, "tip": TIP + timedelta(hours=2),
                      "commence_time": "x", "home": "Yale", "away": "Iona"}}
    monkeypatch.setattr(win, "slate", lambda conn, t: games)
    monkeypatch.setattr(win, "listed", lambda conn, ids: set(ids))
    monkeypatch.setattr(feed, "last_fetches", lambda conn, ids, ok_only=True: {})
    monkeypatch.setattr(spread_card, "decided_games", lambda conn, ids: set())
    seen = []
    monkeypatch.setattr(total_card, "decided_games", lambda conn, ids: seen.append(list(ids)) or set())
    p = win.plan(None, now)
    assert p.total_card == ["g"] and p.card == [] and bool(p)
    assert p.marks["g"] == "T-60" and seen == [["g"]]
    monkeypatch.setattr(total_card, "decided_games", lambda conn, ids: {"g"})
    assert win.plan(None, now).total_card == []


def test_the_card_decides_on_a_call_55_to_60_point_5_minutes_out():
    from scripts import ncaab_first_half_total_card as card
    assert card.DECISION_LEAD_MIN == (55.0, 60.5) and card.MAX_DECISION_DELAY_MIN == 5.0
    from scripts.ncaab_first_half_window import TOTAL_CARD_LEAD_MIN
    assert TOTAL_CARD_LEAD_MIN == card.DECISION_LEAD_MIN[1]


# ── the job, the alert, the registration ─────────────────────────────────────

def test_the_first_half_job_runs_the_total_card_as_its_own_step():
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    i = src.index("def run_ncaab_first_half_window")
    body = src[i:src.index("\ndef ", i + 10)]
    assert '"scripts.ncaab_first_half_total_card", "--publish"' in body
    assert "if plan.total_card:" in body
    assert body.index("_publish_new_signals") < body.index("raise RuntimeError")


def test_the_alerter_names_a_game_either_first_half_model_lost(monkeypatch):
    from scripts import ncaab_first_half_window as win
    from tracking import failure_alerter as fa
    asked = []

    def fake(conn, now, model="ncaab_first_half_spread"):
        asked.append(model)
        return ["NCAAB_x"] if model == ft.MODEL_ID else []
    monkeypatch.setattr(win, "undecided_games", fake)
    out = fa._ncaab_first_half_undecided(None, datetime(2026, 11, 11, tzinfo=UTC))
    assert asked == ["ncaab_first_half_spread", ft.MODEL_ID]
    assert list(out) == [f"undecided:{ft.MODEL_ID}"]
    assert out[f"undecided:{ft.MODEL_ID}"][0] == "CRIT"
    assert "tip-minus-60" in out[f"undecided:{ft.MODEL_ID}"][2]


def test_it_is_registered_where_every_rule_card_is():
    mid = ft.MODEL_ID
    # The cut moved 0.02 -> 0.025 on 2026-11-06 (mike); the EV floor 0.03 -> 0.037.
    assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.025}
    assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.025 and config.MODEL_PROB_THRESHOLDS[mid] == 0.0
    assert config.min_odds_for(mid) == -200 and config.min_ev_for(mid) == 0.037


def test_the_ev_floor_never_removes_a_bet_the_cut_takes():
    """EV = edge x decimal. At the shortest price the model may lay (-200,
    decimal 1.5) an edge just over the cut is EV just over cut x 1.5. The
    floor must sit at or under that, or it removes bets the cut admitted,
    silently (the GLOBAL_MIN_EV failure, CLAUDE.md §1b)."""
    for mid in (ft.MODEL_ID, "ncaab_first_half_spread", "ncaab_total_blend"):
        shortest = 1 + 100 / abs(config.min_odds_for(mid))
        assert config.min_ev_for(mid) <= config.MODEL_EDGE_THRESHOLDS[mid] * shortest, mid
    assert mid in config.MODELS_ON_OWN_PROBABILITY and config.scoring_method(mid) == "rule"
    assert mid not in config.PAUSED_MODELS and mid not in config.RETIRED_MODELS
    assert mid not in config.MODELS


def test_its_ledger_is_worker_only_and_its_rows_are_kept_by_the_prune():
    from data import prune_odds
    from data.anon_readable import WORKER_ONLY_TABLES
    from scripts import ncaab_first_half_total_card as card
    assert card.DECISIONS_TABLE in WORKER_ONLY_TABLES
    assert feed.SOURCE in prune_odds.PROTECTED_SOURCES


def test_the_model_s_books_are_bettable_today():
    # betparx stays in the fitted consensus set and is never a betting book
    # (config.STATE_LIMITED_BOOKMAKERS, mike 2026-11-06).
    assert set(ft.BOOKS) - config.STATE_LIMITED_BOOKMAKERS <= set(config.BEST_LINE_BOOKMAKERS)
    from scripts.ncaab_first_half_total_card import bet_books
    assert "betparx" in ft.BOOKS and "betparx" not in bet_books()


def test_a_game_priced_below_the_cut_is_a_none_row_and_one_with_no_quote_is_no_row():
    """The All board shows every scored game (Matt, 2026-11-04): a priced game
    under the cut is written as NONE at the same book, side and number with no
    stake. Nothing publishes or settles a NONE row (they select BETs)."""
    from scripts.ncaab_first_half_total_card import pick_rows
    d = _decision(edge=0.01)
    d.status = "below_cut"
    (r,), refused = pick_rows([d], GAMES, 1000.0)
    assert not refused
    assert (r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) == ("NONE", 0.0, 0.0)
    assert (r["pick_side"], r["scored_line"], r["decision_book"], r["decision_odds"]) == (
        "under", 70.5, "fanduel", 100)
    assert r["pick_label"] == "Duke @ Kansas — First Half Under 70.5"
    unpriced = ft.Decision("g", "no_quote", "x")
    assert pick_rows([unpriced], GAMES, 1000.0) == ([], {})
