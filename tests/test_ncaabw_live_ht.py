"""The women's halftime total model (models/ncaabw_live_ht.py), its
play-by-play parser (data/ingestors/ncaabw_pbp.py) and its registration.

Pinned here:
  * THE WOMEN'S CLOCK: four 10-minute quarters, halftime at 1,200 game seconds;
  * THE SCORE IS THE HIGHEST LOGGED SO FAR: a first-quarter play ESPN enters
    during the break, carrying 2-2, does not make the halftime score 2-2 (the
    research's reading did, on 54 of its 689 bets of 2025-26);
  * the break: nothing before the half ends, a decision inside it, 'past' once
    the third quarter is under way;
  * every eligibility check, one at a time;
  * the committed artifact is the one the build pinned, and the model is
    registered everywhere a live model has to be.
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
from data.ingestors import ncaabw_pbp as P  # noqa: E402
from models import ncaabw_live_ht as M  # noqa: E402
from tests import _ncaabw_live_synth as S  # noqa: E402

BOOKS = ("draftkings", "fanduel", "betmgm")
MODEL = M.TotalModel((1.03, 0.0, 0.32, 5.5), (33.0, 180.0, 58.0))


def rows_of(plays, until=None):
    return P.summary_rows(S.summary(plays, until or datetime(2027, 1, 1, tzinfo=timezone.utc)),
                          espn_game_id=S.EVENT_ID, game_id=S.GAME_ID, season=S.SEASON,
                          home_espn_id=S.HOME_ID, away_espn_id=S.AWAY_ID)


def quotes(stamp, books=None):
    """One game's total quotes: {book: (line, over, under)} at one stamp."""
    books = books or {"draftkings": (131.5, -110, -110), "fanduel": (131.5, -112, -108),
                      "betmgm": (132.5, -110, -110)}
    return pd.DataFrame([{"book": b, "stamp": pd.Timestamp(stamp), "total_line": v[0], "over_price": v[1],
                          "under_price": v[2]} for b, v in books.items()])


@pytest.fixture(scope="module")
def game():
    plays = S.build_plays()
    return plays, M.states_from_rows(rows_of(plays)), S.half_end(plays), S.third_start(plays)


# ── the clock and the parser ─────────────────────────────────────────────────

def test_game_seconds_are_on_the_womens_clock():
    assert P.game_seconds(1, 600.0, 2027) == 0.0
    assert P.game_seconds(2, 0.0, 2027) == 1200.0            # the half ends
    assert P.game_seconds(3, 600.0, 2027) == 1200.0          # the third quarter has not started
    assert P.game_seconds(4, 0.0, 2027) == 2400.0
    assert P.game_seconds(5, 300.0, 2027) == 2400.0 and P.game_seconds(5, 0.0, 2027) == 2700.0
    assert P.game_seconds(2, 0.0, 2015) == 2400.0            # two halves before 2015-16
    assert P.game_seconds(None, 10.0, 2027) is None and P.game_seconds(2, None, 2027) is None


def test_the_summary_parser_puts_plays_on_that_clock_in_our_orientation():
    plays = S.build_plays()
    rows = rows_of(plays)
    end = next(r for r in rows if r["period"] == 2 and r["text"] == "End Period")
    assert end["game_s"] == 1200.0 and (end["home_score"], end["away_score"]) == S.HALF_SCORE
    assert end["source"] == P.LIVE_SOURCE
    # ESPN lists the sides the other way round: the scores come back as OURS
    sw = P.summary_rows(S.summary(plays, S.half_end(plays), swapped=True), espn_game_id=S.EVENT_ID,
                        game_id=S.GAME_ID, season=S.SEASON, home_espn_id=S.HOME_ID, away_espn_id=S.AWAY_ID)
    assert (sw[-1]["home_score"], sw[-1]["away_score"]) == (S.HALF_SCORE[1], S.HALF_SCORE[0])


def test_the_tables_are_the_womens_and_declared_worker_only():
    from data.anon_readable import WORKER_ONLY_TABLES
    from data.ingestors import ncaab_pbp as men
    # the men's columns exactly, under the women's names
    assert P.PBP_DDL.replace("ncaabw_pbp", "ncaab_pbp") == men.PBP_DDL
    assert P.GAMES_DDL.replace("ncaabw_pbp_games", "ncaab_pbp_games") == men.GAMES_DDL
    assert "CREATE TABLE IF NOT EXISTS ncaabw_pbp (" in P.PBP_DDL
    for t in (P.PBP_TABLE, P.GAMES_TABLE):
        assert t in WORKER_ONLY_TABLES
    assert "womens-college-basketball" in P.SUMMARY_URL and "espn_womens_college_basketball_pbp" in P.PBP_URL


def test_a_release_game_with_other_teams_or_no_event_is_left_out():
    frame = pd.DataFrame([{"game_id": 1, "game_play_number": k, "period_number": 1,
                           "clock_display_value": "9:00", "wallclock": "2026-11-12T00:10:00Z", "home_score": 0,
                           "away_score": 0, "home_team_id": 10, "away_team_id": 20} for k in (1, 2)]
                         + [{"game_id": 2, "game_play_number": 1, "period_number": 1,
                             "clock_display_value": "9:00", "wallclock": "2026-11-12T00:10:00Z", "home_score": 0,
                             "away_score": 0, "home_team_id": 10, "away_team_id": 20}])
    ev = {1: {"game_id": "g1", "home_espn_id": 99, "away_espn_id": 98}}
    stats: dict = {}
    assert list(P.parsed_games(frame, ev, 2027, stats)) == []
    assert stats == {"games_in_file": 2, "team_mismatch": 1, "no_event": 1}
    ev[1] = {"game_id": "g1", "home_espn_id": 20, "away_espn_id": 10}           # swapped: still ours
    got = list(P.parsed_games(frame, ev, 2027, {}))
    assert len(got) == 1 and got[0][1] is True and got[0][2][0]["source"] == P.SOURCE


# ── the state ────────────────────────────────────────────────────────────────

def test_the_state_at_the_break_is_the_halftime_score(game):
    plays, st, half, third = game
    j = int(st.at(M._ns([half + timedelta(minutes=3)]))[0])
    assert st.gs[j] == M.HALF_S and (st.h[j], st.a[j]) == S.HALF_SCORE


def test_a_late_logged_early_play_does_not_lower_the_score():
    """ESPN enters a first-quarter substitution two minutes into the break,
    with the 2-2 of its own moment. The state stays 40-30."""
    base = S.build_plays()
    half = S.half_end(base)
    late = [{"period": 1, "clock_s": 381.0, "wallclock": half + timedelta(minutes=2), "score": (2, 2)}]
    rows = rows_of(S.build_plays(extra=late))
    st = M.states_from_rows(rows)
    j = int(st.at(M._ns([half + timedelta(minutes=3)]))[0])
    assert (st.h[j], st.a[j]) == S.HALF_SCORE and st.gs[j] == M.HALF_S
    assert st.ver[j] == st.ver[int(st.at(M._ns([half]))[0])]                    # and it is not a score
    # the research's reading takes the play's own score: the halftime "2-2" its replay bet on
    raw = M.states_from_rows(rows, as_logged=True)
    assert (raw.h[j], raw.a[j]) == (2.0, 2.0)


def test_plays_are_read_in_wallclock_order_not_play_number(game):
    plays, st, half, third = game
    late = [{"period": 2, "clock_s": 300.0, "wallclock": S.FIRST + timedelta(seconds=45), "score": (0, 0)}]
    st2 = M.states_from_rows(rows_of(S.build_plays(extra=late)))
    assert np.all(np.diff(st2.wall) >= 0) and np.all(np.diff(st2.gs) >= 0)
    assert len(st2.wall) == len(st.wall) + 1


def test_a_thin_play_list_is_no_state():
    assert M.states_from_rows(rows_of(S.build_plays())[:M.MIN_PLAYS - 1]) is None


# ── the model's arithmetic ───────────────────────────────────────────────────

def test_the_mean_at_the_half_is_the_pregame_share_plus_the_surprise():
    mu, sd = MODEL.predict(0.5, 10.0, 70.0, 130.0)          # 5 points over half the pre-game total
    assert mu[0] == pytest.approx(1.03 * 0.5 * 130.0 + (0.0 * 0.5 + 0.32 * 0.25) * 5.0)
    assert sd[0] == pytest.approx(np.sqrt(33.0 + 180.0 * 0.5 + 58.0 * 0.25))
    late = M.design(0.1, 4.0, 110.0, 130.0)
    assert late[0, 3] == 1.0 and M.design(0.1, 9.0, 110.0, 130.0)[0, 3] == 0.0   # late and close only


def test_a_whole_number_total_can_push():
    pw, pp = M.p_over(np.array([60.0]), np.array([12.0]), np.array([60.0]))
    assert pp[0] > 0 and pw[0] + pp[0] < 1
    pw2, pp2 = M.p_over(np.array([60.0]), np.array([12.0]), np.array([60.5]))
    assert pp2[0] == 0.0 and pw2[0] == pytest.approx(0.4834, abs=1e-3)


def test_fit_recovers_a_planted_model():
    rng = np.random.default_rng(7)
    n = 40_000
    f = rng.uniform(0.02, 0.98, n)
    prior = rng.uniform(110, 150, n)
    cur_t = prior * (1 - f) + rng.normal(0, 8, n)
    cur_m = rng.normal(0, 10, n)
    X = M.design(f, cur_m, cur_t, prior)
    b = np.array([1.02, 0.05, 0.30, 4.0])
    y = X @ b + rng.normal(0, 1, n) * np.sqrt(30 + 150 * f)
    got = M.fit(pd.DataFrame({"f": f, "cur_m": cur_m, "cur_t": cur_t, "prior_t": prior, "rem_t": y}))
    assert np.allclose(got.b[:3], b[:3], atol=0.03) and got.b[3] == pytest.approx(4.0, abs=0.6)
    assert got.s[0] == pytest.approx(30, abs=6) and got.s[1] + got.s[2] == pytest.approx(150, abs=15)


def test_units_are_one_to_win_with_risk_capped_and_a_push_returns_the_stake():
    assert M.units("over", 131.5, -110, 140) == (pytest.approx(1.0), pytest.approx(1.1))
    assert M.units("under", 131.5, -110, 140)[0] == pytest.approx(-1.1)
    assert M.units("over", 132.0, +150, 132)[0] == 0.0
    assert M.units("over", 131.5, -400, 100)[0] == pytest.approx(-M.MAX_RISK)


def test_the_prior_is_the_median_of_the_books_last_pregame_numbers():
    rows = [("spreads", "draftkings", -7.5, None), ("spreads", "fanduel", -8.5, None),
            ("spreads", "betmgm", -8.0, None), ("spreads", "typo", -700.0, None),
            ("totals", "draftkings", None, 131.5), ("totals", "fanduel", None, 132.5),
            ("totals", "typo", None, 1315.0), ("totals", "none", None, float("nan"))]
    assert M.prior_from_closes(rows) == (8.0, 132.0)
    assert M.prior_from_closes([r for r in rows if r[0] == "totals"]) is None      # the grade had both
    assert M.prior_from_closes([]) is None


# ── one game at one read ─────────────────────────────────────────────────────

def read(game, at_, q, books=BOOKS, prior=130.0):
    return M.read_break(q, game[1], at_, prior, MODEL, books)


def test_before_the_half_ends_nothing_is_read(game):
    plays, st, half, third = game
    r = read(game, half - timedelta(seconds=40), quotes(half - timedelta(seconds=60)))
    assert r.status == "early" and r.best is None


def test_a_read_in_the_break_decides_on_the_best_quote(game):
    plays, st, half, third = game
    r = read(game, half + timedelta(minutes=3), quotes(half + timedelta(minutes=2)))
    assert r.status == "decided" and r.state == {"h_pts": 40, "a_pts": 30, "game_s": 1200.0}
    b = r.best
    # 70 at the half against a pre-game 130: about 67 more expected, so over 131.5
    assert b["side"] == "over" and b["line"] == 131.5 and b["book"] == "fanduel" and b["price"] == -108.0 \
        or (b["book"], b["price"]) == ("draftkings", -110.0)
    assert b["ev"] == pytest.approx(b["prob"] * float(M.decimal(b["price"])) - 1) and b["ev"] > 0.05
    assert set(r.offers.columns) >= set(M.OFFER_COLS) and int(r.offers["eligible"].sum()) == 3


def test_the_best_price_on_the_side_wins_and_ties_go_to_the_first_book(game):
    plays, st, half, third = game
    q = quotes(half + timedelta(minutes=2), {"draftkings": (131.5, -110, -110), "fanduel": (131.5, -105, -115),
                                             "betmgm": (131.5, -110, -110)})
    assert read(game, half + timedelta(minutes=3), q).best["book"] == "fanduel"
    q = quotes(half + timedelta(minutes=2), {"betmgm": (131.5, -110, -110), "draftkings": (131.5, -110, -110),
                                             "fanduel": (131.5, -110, -110)})
    assert read(game, half + timedelta(minutes=3), q).best["book"] == "draftkings"     # BOOKS order, not row order


def test_once_the_third_quarter_is_under_way_the_break_is_past(game):
    plays, st, half, third = game
    r = read(game, third + timedelta(seconds=5), quotes(half + timedelta(minutes=2)))
    assert r.status == "past" and r.best is None
    # a third-quarter play still at 10:00 (the starters walking on) is the break
    start = next(S.at(p["wallclock"]) for p in plays if p["period"]["number"] == 3)
    assert read(game, start + timedelta(seconds=1), quotes(half + timedelta(minutes=2))).status == "decided"


def test_a_quote_stamped_before_the_half_ended_is_not_bet():
    """The half's last two minutes are scoreless, so a quote stamped 20 s
    before the horn is as fresh as any: it is out because the book had not
    seen the half end, and for no other reason."""
    plays = S.build_plays(quiet_last=True)
    half = S.half_end(plays)
    g = (plays, M.states_from_rows(rows_of(plays)))
    r = read(g, half + timedelta(minutes=3), quotes(half - timedelta(seconds=20)))
    assert r.status == "none" and r.state["h_pts"] == 38
    assert r.offers["fresh"].all() and not r.offers["half_over"].any() and not r.offers["eligible"].any()
    assert read(g, half + timedelta(minutes=3), quotes(half + timedelta(seconds=20))).status == "decided"


def test_a_point_logged_between_the_stamp_and_the_read_spoils_the_quote():
    base = S.build_plays()
    half = S.half_end(base)
    buzzer = [{"period": 2, "clock_s": 0.0, "wallclock": half + timedelta(seconds=40), "team": "A", "points": 1,
               "score": (40, 31), "text": "made free throw"}]
    st = M.states_from_rows(rows_of(S.build_plays(extra=buzzer)))
    g = (None, st)
    stale = read(g, half + timedelta(minutes=3), quotes(half + timedelta(seconds=20)))
    assert stale.status == "none" and not stale.offers["fresh"].any()
    assert stale.state["a_pts"] == 31
    fresh = read(g, half + timedelta(minutes=3), quotes(half + timedelta(seconds=60)))
    assert fresh.status == "decided" and fresh.best["a_pts"] == 31


def test_a_total_far_from_the_others_is_not_bet(game):
    plays, st, half, third = game
    q = quotes(half + timedelta(minutes=2), {"draftkings": (120.5, -110, -110), "fanduel": (131.5, -110, -110),
                                             "betmgm": (131.5, -110, -110)})
    r = read(game, half + timedelta(minutes=3), q)
    assert r.status == "decided" and r.best["book"] != "draftkings"            # 11 points off the median
    assert not bool(r.offers.set_index("book").at["draftkings", "eligible"])


def test_two_other_books_must_quote_the_total(game):
    plays, st, half, third = game
    two = {"draftkings": (131.5, -110, -110), "fanduel": (131.5, -110, -110)}
    assert read(game, half + timedelta(minutes=3), quotes(half + timedelta(minutes=2), two)).status == "none"
    # a book listed twice by the feed is one book
    q = pd.concat([quotes(half + timedelta(minutes=2), two)] * 2, ignore_index=True)
    assert read(game, half + timedelta(minutes=3), q).status == "none"
    # a third book that cannot be bet still counts as another book quoting
    three = {**two, "lowvig": (131.5, -108, -108)}
    r = read(game, half + timedelta(minutes=3), quotes(half + timedelta(minutes=2), three))
    assert r.status == "decided" and r.best["book"] in ("draftkings", "fanduel")


def test_the_price_band_and_the_line_range_hold(game):
    plays, st, half, third = game
    q = quotes(half + timedelta(minutes=2), {"draftkings": (131.5, +260, -330), "fanduel": (131.5, -110, -110),
                                             "betmgm": (131.5, -110, -110)})
    o = read(game, half + timedelta(minutes=3), q).offers.set_index("book")
    assert not bool(o.at["draftkings", "eligible"]) and bool(o.at["fanduel", "eligible"])
    q = quotes(half + timedelta(minutes=2), {b: (270.5, -110, -110) for b in BOOKS})
    assert read(game, half + timedelta(minutes=3), q).status == "none"


def test_a_decision_under_the_cut_is_still_the_decision(game):
    plays, st, half, third = game
    q = quotes(half + timedelta(minutes=2), {b: (137.5, -110, -110) for b in BOOKS})
    r = read(game, half + timedelta(minutes=3), q)
    assert r.status == "decided" and r.best["ev"] < 0.05


# ── the artifact and the registration ────────────────────────────────────────

def test_the_committed_artifact_is_the_one_the_build_pinned():
    import scripts.build_ncaabw_live_ht_artifact as B
    art = M.load_artifact()
    raw = art.raw
    assert raw["kind"] == M.ARTIFACT_KIND and raw["season"] == M.SEASON and raw["model_id"] == M.MODEL_ID
    assert art.cut == B.CUT == 0.05 and raw["version"] == B.VERSION
    assert max(raw["fitted_on"]["seasons"]) < M.SEASON                           # walk-forward
    assert raw["rule"]["cadence_min"] == M.CADENCE_MIN and raw["rule"]["fetch_after_sec"] == M.FETCH_AFTER_SEC
    for reading, by in B.EXPECTED.items():
        for season, (bets, won, lost, units) in by.items():
            got = raw["replay"][reading][str(season)]
            assert (got["bets"], got["won"], got["lost"], got["units"]) == (bets, won, lost, units)
    # the loop's population is the corrected one, and it never laid a price shorter than -150
    assert raw["replay"]["production"]["2026"]["price_min"] >= -150
    with pytest.raises(ValueError):
        M.artifact_from_dict({**raw, "kind": "something_else"})
    with pytest.raises(ValueError):
        M.artifact_from_dict({**raw, "total": {"b": [1.0], "s": [1.0, 2.0, 3.0]}})


def test_the_artifact_is_plain_json_under_models_saved():
    p = ROOT / M.ARTIFACT_PATH
    assert p.parent.name == "saved" and json.loads(p.read_text(encoding="utf-8"))["total"]["b"]


def test_the_model_is_registered_everywhere_a_live_model_must_be():
    m = M.MODEL_ID
    assert config.LIVE_MODELS[m][:3] == ("NCAABW", "totals", "engine")
    assert config.ACTION_THRESHOLDS[m] == {"min_prob": 0.0, "min_edge": 0.0}
    assert config.MODEL_EDGE_THRESHOLDS[m] == 0.0 and config.MODEL_PROB_THRESHOLDS[m] == 0.0
    assert config.min_ev_for(m) == M.load_artifact().cut                         # the floor IS the rule's cut
    assert config.min_odds_for(m) == -200
    assert m in config.MODELS_ON_OWN_PROBABILITY and config.SCORING_METHODS[m] == "rule"
    assert m not in config.PAUSED_MODELS
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick(m) == "totals"
    from models.ncaabw_quote_bounds import EDGE_CAP, edge_problem
    assert EDGE_CAP[m] == 0.40 and edge_problem(0.41, m) and edge_problem(0.39, m) is None
    names = set(config.ACTION_THRESHOLDS) | set(config.LIVE_MODELS) | set(config.MODEL_MIN_ODDS)
    assert {n for n in names if n.startswith("ncaabw_live_")} == {m}             # the spread is not here


def test_live_picks_post_only_to_the_womens_live_channel_while_the_game_is_on():
    assert "NCAABW" in config.DISCORD_LIVE_CHANNEL_REQUIRED
    assert "NCAABW" in config.LIVE_ANNOUNCE_WHILE_IN_PROGRESS


def test_the_label_passes_the_publishing_guard():
    from tracking.pick_integrity import pick_problems
    lab = M.pick_label("over", 131.5, "Iowa", "Drake")
    assert lab == "Drake @ Iowa Over 131.5 (live)"
    assert pick_problems(lab, "over", 131.5, M.MODEL_ID, "Iowa", "Drake") == []
    assert M.pick_label("under", 132.0, "Iowa", "Drake") == "Drake @ Iowa Under 132 (live)"


def test_the_scheduler_runs_the_loop_on_the_poller_service(monkeypatch):
    import importlib
    import scheduler
    monkeypatch.delenv("RUN_NCAABW_LIVE", raising=False)
    importlib.reload(scheduler)
    assert scheduler.RUN_NCAABW_LIVE is True and "ncaabw_live" in scheduler._POLLER_JOBS
    assert "ncaabw_live" not in scheduler._PIPELINE_JOBS
    monkeypatch.setenv("RUN_NCAABW_LIVE", "0")
    importlib.reload(scheduler)
    assert scheduler.RUN_NCAABW_LIVE is False
    monkeypatch.delenv("RUN_NCAABW_LIVE", raising=False)
    importlib.reload(scheduler)
    from tracking.job_heartbeat import ACTIVE_HOURS_ET, MAX_SILENCE
    assert MAX_SILENCE["ncaabw_live"] == 700 and ACTIVE_HOURS_ET["ncaabw_live"] == (11, 23, 30)


def test_the_decision_ledger_migration_runs_on_every_pass():
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "ncaabw_live_decisions_2026_11_11.sql"
    assert name in ACTIVE_MIGRATIONS
    sql = (ROOT / "data" / "migrations" / name).read_text(encoding="utf-8")
    assert "uq_ncaabw_live_decisions_one_decision" in sql and "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.ncaabw_live_decisions FROM anon" in sql
    assert "REVOKE ALL ON public.ncaabw_live_decisions FROM authenticated" in sql
    assert "WHERE outcome IN ('bet', 'no_bet', 'declined', 'missed')" in sql
    import models.ncaabw_live_loop as LP
    for col in LP.LEDGER_COLS:
        assert f"\n    {col} " in sql, col


def test_the_feed_buys_the_books_the_history_was_bought_at():
    from data.ingestors import ncaabw_live_feed as W
    from data.ingestors.odds_ingestor import sport_bookmakers_param
    assert W.feed_books() == sport_bookmakers_param("NCAABW").split(",")
    assert len(W.feed_books()) == 17 and set(config.NCAABW_EXTRA_BOOKMAKERS) <= set(W.feed_books())
    assert W.MARKETS == ("h2h", "spreads", "totals") and W.SPORT_KEY == "basketball_wncaab"
    assert "womens-college-basketball" in W.SCOREBOARD_URL
