"""ncaab_first_half_spread: the model's rules, its frozen artifact, its label,
its settlement, its card rows and its registration.

The model (models/ncaab_first_half_spread.py) is the NCAAB research's round 4,
family A, spreads_h1, close, best book, cut 0.02, every game. Its build
(scripts/ncaab_first_half_spread_build.py) replayed 2023-24..2025-26 through the
functions tested here and matched the research's 1,253 bets game by game (side,
book, line, price); the replay's numbers are pinned below through the artifact.
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
import models.ncaab_first_half_spread as fh  # noqa: E402

UTC = timezone.utc
HOME, AWAY = "Kansas", "Duke"


def _table(seed=7, n=6000):
    """A first-half margin table fitted on a synthetic sample: margin ~ round
    of a normal around 0.56 x M, the key the same map."""
    rng = np.random.default_rng(seed)
    m = rng.uniform(-20, 20, n)
    key = 0.56 * m
    out = np.round(key + rng.normal(0, 8.5, n)).astype(int)
    return fh.fit_table(out, key)


T = _table()


# ── pricing ──────────────────────────────────────────────────────────────────

def test_the_three_outcomes_add_to_one_and_a_whole_number_carries_the_push():
    for mu in (-12.3, -0.4, 0.0, 3.25, 17.9):
        for th in (-3.5, -3.0, 0.0, 0.5, 6.0):
            pw, pp, pl = fh.probs(mu, th, T)
            assert abs(float(pw + pp + pl) - 1) < 1e-12
            assert (float(pp) > 0) == (th == round(th))


def test_a_level_first_half_has_real_mass_at_an_even_mean():
    """First halves end level; the table keeps whatever history shows (no
    smoothing over outcomes), so a pick'em line pushes on a tie."""
    _, pp, _ = fh.probs(0.0, 0.0, T)
    assert 0.02 < float(pp) < 0.08


def test_home_covers_when_the_margin_beats_minus_the_home_number():
    # mean +4: a home -3.5 covers more often than not, an away +3.5 less
    side, edge, p = fh.price_quote(4.0, -3.5, -110, -110, T)
    assert int(side) == 1 and float(p) > 0.5
    pw, pp, pl = fh.probs(4.0, 3.5, T)
    assert abs(float(p) - float(pw / (pw + pl))) < 1e-12
    assert abs(float(edge) - (float(p) - 1 / 1.9090909090909092)) < 1e-12
    side, _, p = fh.price_quote(-4.0, -3.5, -110, -110, T)
    assert int(side) == 2 and float(p) > 0.5


def test_the_edge_is_raw_against_each_side_s_own_price():
    """Edge = P(win | no push) - 1/decimal of that side's price, vig left in;
    the side is the larger edge."""
    side, edge, p = fh.price_quote(0.0, 0.5, -105, -125, T)
    q1 = float(fh.probs(0.0, -0.5, T)[0] / (1 - fh.probs(0.0, -0.5, T)[1]))
    e_home = q1 - 1 / fh.dec(-105)
    e_away = (1 - q1) - 1 / fh.dec(-125)
    assert abs(float(edge) - max(e_home, e_away)) < 1e-12
    assert int(side) == (1 if e_home >= e_away else 2)


def test_a_tie_between_the_two_sides_goes_home():
    """fh_lib.price_quote: side = 1 when e1 >= e2."""
    side, edge, p = fh.price_quote(0.0, 0.5, -110, -110, fh.fit_table([1, -1] * 300, [0.0] * 600))
    assert float(p) == 0.5
    assert int(side) == 1


def test_a_count_weighted_sample_rebuilds_the_same_table():
    """The artifact stores (spread, margin, count); one row per game and one
    row per distinct pair must give the same table."""
    rng = np.random.default_rng(3)
    cons = rng.choice(np.arange(-15, 15.5, 0.5), 3000)
    marg = np.round(-0.56 * cons + rng.normal(0, 8, 3000)).astype(int)
    key = 0.56 * -cons + 0.01
    full = fh.fit_table(marg, key)
    s = pd.DataFrame({"c": cons, "m": marg}).groupby(["c", "m"]).size().reset_index(name="n")
    packed = fh.fit_table(s["m"], 0.56 * -s["c"] + 0.01, weight=s["n"])
    assert np.abs(full["pmf"] - packed["pmf"]).max() < 1e-12


# ── the best quote and the decision ─────────────────────────────────────────

def _quotes(*rows):
    return pd.DataFrame([{"bookmaker": b, "spread_home": ln, "home_price": hp, "away_price": ap,
                          "home_link": f"{b}/h", "away_link": f"{b}/a"} for b, ln, hp, ap in rows])


def _art():
    return {"map": {"a": 0.0, "b": 0.56}, "_T": T}


def test_ties_between_books_go_to_the_alphabetically_first_key():
    o = [fh.Offer("fanduel", -2.5, -110, -110, "home", 0.031, 0.55),
         fh.Offer("betmgm", -2.5, -110, -110, "home", 0.031, 0.55),
         fh.Offer("draftkings", -2.5, -110, -110, "home", 0.030, 0.55)]
    assert fh.best_offer(o).book == "betmgm"


def test_a_game_with_no_full_game_consensus_is_decided_without_a_bet():
    d = fh.decide("g", _quotes(("fanduel", -2.5, -110, -110)), None, None, _art(), 0.02)
    assert d.status == "no_fg_line" and d.best is None


def test_no_bettable_first_half_quote_is_no_quote():
    d = fh.decide("g", _quotes(("pinnacle", -2.5, -110, -110)), {"cons": -5.0, "nb": 4}, None,
                  _art(), 0.02)
    assert d.status == "no_quote"


def test_the_cut_is_strict_and_the_best_quote_decides():
    fg = {"cons": -8.0, "nb": 5}       # M = +8, mu = 4.48: home -1.5 at even money is generous
    q = _quotes(("fanduel", -1.5, +100, -120), ("draftkings", -1.5, -110, -110),
                ("pinnacle", -1.5, +150, -180))
    d = fh.decide("g", q, fg, {"tau_home": 0.0, "tau_away": 0.0}, _art(), 0.02)
    assert d.status == "bets" and d.best.book == "fanduel" and d.best.side == "home"
    assert d.price == 100 and "pinnacle" not in {o.book for o in d.offers}
    assert abs(d.mu - (0.56 * 8.0)) < 1e-12
    at_cut = fh.decide("g", q, fg, None, _art(), d.best.edge)
    assert at_cut.status == "below_cut"


def test_the_team_term_moves_the_mean_by_half_the_difference():
    d = fh.decide("g", _quotes(("fanduel", -1.5, -110, -110)), {"cons": -4.0, "nb": 3},
                  {"tau_home": 0.2, "tau_away": -0.1}, _art(), 0.02)
    assert abs(d.mu - (0.56 * 4.0 + 0.15)) < 1e-12


# ── the consensus and the team term ──────────────────────────────────────────

def _t(h, m=0):
    return pd.Timestamp(datetime(2026, 11, 10, h, m, tzinfo=UTC))


def test_the_consensus_is_each_bettable_book_s_newest_line_by_the_moment():
    rows = pd.DataFrame([
        ("g", "draftkings", _t(12), -3.0), ("g", "draftkings", _t(18), -4.0),
        ("g", "draftkings", _t(23), -9.0),     # after the cutoff: not seen
        ("g", "fanduel", _t(14), -5.0), ("g", "pinnacle", _t(19), -20.0),   # not bettable
        ("g", "betmgm", _t(15), None)],        # no number
        columns=["game_id", "bookmaker", "ts", "line"])
    c = fh.asof_consensus(rows, pd.DataFrame({"game_id": ["g"], "cutoff": [_t(22)]}))
    assert c.iloc[0]["cons"] == -4.5 and c.iloc[0]["nb"] == 2


def _tg(rows):
    return pd.DataFrame(rows, columns=list(fh.TEAM_GAME_COLS))


def test_a_team_term_counts_only_games_that_ended_and_shrinks_by_k():
    tip1, tip2 = _t(0), _t(20)
    tg = _tg([("g1", 2027, tip1, HOME, AWAY, 40, 30, 35, 35, -5.0, 140.0),   # dm = 10 - 0
              ("g2", 2027, tip2, HOME, "Iona", 30, 30, 30, 30, -2.0, 140.0),
              ("g3", 2027, tip1, HOME, "Yale", 30, 30, 30, 30, None, 140.0)])  # no close: out
    res = fh.team_game_residuals(tg, alpha=0.0, beta=0.0)
    assert set(res["game_id"]) == {"g1", "g2"}
    targets = pd.DataFrame({"game_id": ["x"], "home_team": [HOME], "away_team": [AWAY],
                            "stamp": [_t(21)]})    # g2 tipped at 20:00, ends 22:30: not yet
    out = fh.team_effects(res, 2027, {HOME: [4.0, 10], AWAY: [0.0, 0]}, targets, k=782.2,
                          w_prev=0.5).iloc[0]
    assert out["n_home"] == 1 and out["n_away"] == 1
    assert abs(out["tau_home"] - (10 + 0.5 * 4.0) / (1 + 0.5 * 10 + 782.2)) < 1e-12
    assert abs(out["tau_away"] - (-10) / (1 + 782.2)) < 1e-12


def test_the_tilt_residual_removes_the_line_s_expected_tilt():
    tg = _tg([("g1", 2027, _t(0), HOME, AWAY, 40, 30, 35, 35, -5.0, 140.0)])
    res = fh.team_game_residuals(tg, alpha=-0.2, beta=0.13)
    home = res[res["team"] == HOME].iloc[0]["r"]
    assert abs(home - (10 - (0.13 * 5.0 - 0.2))) < 1e-12
    assert abs(res[res["team"] == AWAY].iloc[0]["r"] + home) < 1e-12


def test_halves_exclude_overtime_and_refuse_a_game_that_does_not_add_up():
    per = pd.DataFrame([("ot", 1, 30, 32), ("ot", 2, 35, 33), ("ot", 3, 10, 6),
                        ("gap", 1, 30, 30), ("gap", 3, 5, 5),
                        ("bad", 1, 30, 30), ("bad", 2, 30, 31)],
                       columns=["game_id", "period", "home_points", "away_points"])
    fin = pd.DataFrame([("ot", 75, 71), ("gap", 35, 35), ("bad", 60, 60)],
                       columns=["game_id", "home_score", "away_score"])
    h = fh.valid_halves(per, fin).set_index("game_id")
    assert list(h.index) == ["ot"]
    assert tuple(h.loc["ot"]) == (30, 32, 35, 33)


# ── the frozen artifact ──────────────────────────────────────────────────────

def test_the_committed_2027_artifact_loads_and_carries_the_replay():
    art = fh.load_artifact(2027)
    assert art["season"] == 2027 and art["prior_season"] == 2026
    assert art["map"]["train_seasons"] == [2021, 2026]
    assert 0.5 < art["map"]["b"] < 0.6 and abs(art["map"]["a"]) < 0.2
    assert art["tilt"]["k"] == 782.2 and art["tilt"]["w_prev"] == 0.5
    assert len(art["prior_team_sums"]) > 300
    assert sum(n for _, n in art["prior_team_sums"].values()) > 10000
    assert tuple(art["books"]) == fh.BOOKS
    _, pp, _ = fh.probs(0.0, 0.0, art["_T"])
    assert 0.035 < float(pp) < 0.055          # the research's tie mass, 0.0437 for 2025-26
    rp = art["replay"]
    assert rp["pooled"]["bets"] == 1253 and rp["pooled"]["units"] == 68.07
    assert rp["vs_research"]["identical_game_side_book_line_price"] == 1253
    assert rp["vs_research"]["n_only_research"] == 0 and rp["vs_research"]["n_only_replay"] == 0
    assert (rp["2024"]["bets"], rp["2025"]["bets"], rp["2026"]["bets"]) == (477, 533, 243)


def test_the_artifact_for_another_season_is_refused():
    with pytest.raises(ValueError):
        fh.load_artifact(2028, path=fh.artifact_path(2027))


def test_the_ev_floor_sits_under_the_smallest_ev_the_cut_admitted():
    art = fh.load_artifact(2027)
    assert config.min_ev_for(fh.MODEL_ID) <= art["replay"]["min_ev"]
    assert art["replay"]["pooled"]["price_min"] >= config.min_odds_for(fh.MODEL_ID)


# ── the label, and the check that guards it ──────────────────────────────────

def test_the_label_leads_with_the_matchup_and_says_first_half():
    from models.scorer import _build_pick_label
    assert _build_pick_label("home", HOME, AWAY, "spreads_h1", -3.5) == \
        "Duke @ Kansas — First Half Kansas -3.5"
    assert _build_pick_label("away", HOME, AWAY, "spreads_h1", -3.5) == \
        "Duke @ Kansas — First Half Duke +3.5"


def test_the_integrity_check_reads_a_first_half_spread_as_a_spread():
    from tracking.pick_integrity import pick_problems
    mid = fh.MODEL_ID
    assert pick_problems("Duke @ Kansas — First Half Duke +3.5", "away", -3.5, mid, HOME, AWAY) == []
    assert pick_problems("Duke @ Kansas — First Half Kansas -3.5", "home", -3.5, mid, HOME, AWAY) == []
    # the sign read off the home number for an away pick
    assert pick_problems("Duke @ Kansas — First Half Duke -3.5", "away", -3.5, mid, HOME, AWAY)
    # the other team named
    assert pick_problems("Duke @ Kansas — First Half Kansas +3.5", "away", -3.5, mid, HOME, AWAY)
    # no "First Half": it reads as the full game's spread
    probs = pick_problems("Duke @ Kansas — Duke +3.5", "away", -3.5, mid, HOME, AWAY)
    assert any("First Half" in p for p in probs)


def test_a_first_half_total_label_still_passes():
    from tracking.pick_integrity import pick_problems
    assert pick_problems("BOS @ MIL — First Half Over 112.5", "over", 112.5,
                         "nba_first_half_total_luck", "MIL", "BOS") == []


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


def test_it_settles_on_the_first_half_and_a_level_half_pushes():
    from tracking.paper_tracker import _compute_result, _market_for_pick, first_half_points
    assert _market_for_pick(fh.MODEL_ID) == "spreads_h1"
    conn = _Conn([(1, 30, 33), (2, 40, 30), (3, 8, 6)])     # OT game: first half 30-33
    assert first_half_points(conn, "NCAAB_2026-11-10_duke_kansas", 78, 69) == (30, 33)
    h, a = 30, 33
    assert _compute_result("away", "spreads_h1", h, a, None, None, 0, -110, -1.5, None, 0)[0] == "WIN"
    assert _compute_result("home", "spreads_h1", h, a, None, None, 0, -110, -1.5, None, 0)[0] == "LOSS"
    assert _compute_result("home", "spreads_h1", 31, 34, None, None, 0, -110, 3.0, None, 0)[0] == "PUSH"


def test_a_first_half_with_no_trustworthy_periods_never_settles_on_the_final():
    from tracking.paper_tracker import first_half_points
    gid = "NCAAB_2026-11-10_duke_kansas"
    assert first_half_points(_Conn([]), gid, 70, 60) is None
    assert first_half_points(_Conn([(1, 30, 30)]), gid, 70, 60) is None           # no period 2
    assert first_half_points(_Conn([(1, 30, 30), (2, 30, 30)]), gid, 70, 60) is None  # not the final


def test_the_settler_routes_a_first_half_spread_through_the_first_half():
    src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    i = src.index("def _settle_game_picks(")
    body = src[i:src.index("def _settle_game_picks_window", i)]
    assert 'elif market in ("totals_h1", "spreads_h1"):' in body
    assert "first_half_points(conn, game_id, home_score, away_score)" in body


def test_an_ncaab_first_half_close_is_a_later_pre_tip_row():
    """The feed files every pull 'open'. NBA first half still wants a 'close' row.
    The decision pull is not the close."""
    src = (ROOT / "tracking" / "paper_tracker.py").read_text(encoding="utf-8")
    close_only = src[src.index("def _close_rows_only"):src.index("def _real_close")]
    assert "team_totals" in close_only
    assert "_ncaab_first_half_market" in close_only
    assert "snapshot_at::timestamptz >" in src[src.index("def _closing_odds"):src.index("def _sharp_close_book")]
    sql = (ROOT / "data/migrations/clv_standard_v2_2026_10_14.sql").read_text(encoding="utf-8")
    assert sql.count(
        "s.sport_prefix = 'NCAAB' AND s.game_market IN ('totals_h1', 'spreads_h1')") == 3
    assert sql.count("o.snapshot_at::timestamptz > s.created_at") == 3
    # The NBA close-only rule also names the first-quarter spread (models/nba_q1_trend.py); the NCAAB rule above
    # is unchanged.
    assert sql.count(
        "s.sport_prefix = 'NBA' AND s.game_market IN ('totals_h1', 'spreads_h1', 'spreads_q1')") == 3


# ── the card's rows ──────────────────────────────────────────────────────────

GAMES = {"g": {"home": HOME, "away": AWAY, "game_date": "2026-11-10",
               "commence_time": "2026-11-11T00:00:00Z"}}


def _decision(book="fanduel", side="away", line=-3.5, hp=-120, ap=+100, dk=None, edge=0.05, p=0.55):
    offers = [fh.Offer(book, line, hp, ap, side, edge, p, f"{book}/h", f"{book}/a")]
    if dk is not None:
        offers.append(fh.Offer("draftkings", dk[0], dk[1], dk[2], side, 0.01, p, "dk/h", "dk/a"))
    d = fh.Decision("g", "bets", "x", mu=2.0, fg_spread=-4.0, fg_books=5, best=offers[0], offers=offers)
    return d


def test_a_bet_at_another_book_names_it_and_carries_draftkings_only_at_the_same_number():
    from scripts.ncaab_first_half_spread_card import pick_rows
    rows, refused = pick_rows([_decision(dk=(-3.5, -125, +105))], GAMES, 1000.0)
    r = rows[0]
    assert not refused
    assert (r["pick_side"], r["scored_line"], r["pick_label"]) == (
        "away", -3.5, "Duke @ Kansas — First Half Duke +3.5")
    assert (r["decision_book"], r["decision_odds"], r["best_book"]) == ("fanduel", 100, "fanduel")
    assert r["dk_odds"] == 105 and r["line_book"] is None and r["dk_bet_link"] == "dk/a"
    assert abs(r["decision_edge"] - round(0.55 - 0.5, 4)) < 1e-9
    assert r["model_probability"] == 0.55 and r["signal_type"] == "BET"
    rows, _ = pick_rows([_decision(dk=(-2.5, -110, -110))], GAMES, 1000.0)
    r = rows[0]
    assert r["dk_odds"] is None and r["edge"] == 0.0 and r["line_book"] == "fanduel"


def test_a_bet_at_draftkings_has_no_best_book():
    from scripts.ncaab_first_half_spread_card import pick_rows
    rows, _ = pick_rows([_decision(book="draftkings")], GAMES, 1000.0)
    r = rows[0]
    assert r["decision_book"] == "draftkings" and r["dk_odds"] == 100 and r["best_book"] is None
    assert r["dk_bet_link"] == "draftkings/a"


def test_the_price_floor_and_the_ev_floor_refuse_a_bet():
    from scripts.ncaab_first_half_spread_card import pick_rows
    rows, refused = pick_rows([_decision(ap=-250, p=0.75, edge=0.04)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and refused["g"].startswith("below_price_floor")
    rows, refused = pick_rows([_decision(ap=+100, p=0.51, edge=0.01)], GAMES, 1000.0)
    # A refused bet is still a scored game: a NONE row, no stake.
    assert [(r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) for r in rows] == [("NONE", 0.0, 0.0)] and "g" in refused


def test_the_card_bets_only_at_books_config_still_lists(monkeypatch):
    from scripts import ncaab_first_half_spread_card as card
    monkeypatch.setattr(config, "BEST_LINE_BOOKMAKERS", [b for b in config.BEST_LINE_BOOKMAKERS
                                                         if b != "fanduel"])
    assert "fanduel" not in card.bet_books() and "draftkings" in card.bet_books()


def test_the_model_s_books_are_bettable_today():
    # betparx stays in the fitted consensus set and is never a betting book
    # (config.STATE_LIMITED_BOOKMAKERS, mike 2026-11-06).
    assert set(fh.BOOKS) - config.STATE_LIMITED_BOOKMAKERS <= set(config.BEST_LINE_BOOKMAKERS)
    from scripts.ncaab_first_half_spread_card import bet_books
    assert "betparx" in fh.BOOKS and "betparx" not in bet_books()


# ── registration ─────────────────────────────────────────────────────────────

def test_it_is_registered_where_every_rule_card_is():
    mid = fh.MODEL_ID
    # The cut moved 0.02 -> 0.025 on 2026-11-07 (mike: fewer picks).
    assert config.ACTION_THRESHOLDS[mid] == {"min_prob": 0.0, "min_edge": 0.025}
    assert config.MODEL_EDGE_THRESHOLDS[mid] == 0.025 and config.MODEL_PROB_THRESHOLDS[mid] == 0.0
    assert config.min_odds_for(mid) == -200 and config.min_ev_for(mid) == 0.03
    assert mid in config.MODELS_ON_OWN_PROBABILITY and config.scoring_method(mid) == "rule"
    assert mid not in config.PAUSED_MODELS and mid not in config.RETIRED_MODELS
    assert mid not in config.MODELS


def test_its_tables_are_worker_only_and_its_rows_are_kept_by_the_prune():
    from data import prune_odds
    from data.anon_readable import WORKER_ONLY_TABLES
    from data.ingestors import ncaab_first_half_odds as feed
    from scripts import ncaab_first_half_spread_card as card
    for t in (feed.LEDGER_TABLE, card.DECISIONS_TABLE, card.TEAM_TABLE):
        assert t in WORKER_ONLY_TABLES, t
    assert feed.SOURCE in prune_odds.PROTECTED_SOURCES
    params: dict = {}
    prune_odds._unprotected(params, table="odds")
    assert feed.SOURCE in params["protected_sources"]


def test_the_scheduler_runs_it_every_minute_on_the_pipeline_service():
    import scheduler
    from tracking.job_heartbeat import MAX_SILENCE
    assert "ncaab_first_half_window" in scheduler._PIPELINE_JOBS
    assert MAX_SILENCE["ncaab_first_half_window"] == 20
    src = (ROOT / "scheduler.py").read_text(encoding="utf-8")
    assert 'id="ncaab_first_half_window"' in src
    i = src.index("def run_ncaab_first_half_window")
    body = src[i:src.index("\ndef ", i + 10)]
    # the bets the card wrote go out before a failed step raises
    assert body.index("_publish_new_signals") < body.index("raise RuntimeError")


def test_a_game_priced_below_the_cut_is_a_none_row_and_one_with_no_quote_is_no_row():
    """The All board shows every scored game (Matt, 2026-11-04): a priced game
    under the cut is written as NONE at the same book, side and number with no
    stake. Nothing publishes or settles a NONE row (they select BETs)."""
    from scripts.ncaab_first_half_spread_card import pick_rows
    d = _decision(edge=0.01)
    d.status = "below_cut"
    (r,), refused = pick_rows([d], GAMES, 1000.0)
    assert not refused
    assert (r["signal_type"], r["kelly_fraction"], r["recommended_bet"]) == ("NONE", 0.0, 0.0)
    assert (r["pick_side"], r["scored_line"], r["decision_book"]) == ("away", -3.5, "fanduel")
    assert r["pick_label"] == "Duke @ Kansas — First Half Duke +3.5"
    unpriced = fh.Decision("g", "no_quote", "x")
    assert pick_rows([unpriced], GAMES, 1000.0) == ([], {})
