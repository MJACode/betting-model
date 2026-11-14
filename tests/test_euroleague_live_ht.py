"""The EuroLeague halftime spread's decision (models/euroleague_live_ht.py),
its artifact, its pre-game number and its platform entries.

Pinned here:
  * the price of a quote is the research's: k = -spread_home - the half-time
    margin, P(home covers) = pw / (pw + pl) on a whole-number normal, EV per
    side, home on a tie (scripts/euroleague_research/r4_lib.price);
  * every eligibility rule of the grade, one at a time: a bookable book, in
    play, fresh (re-hung after the half's last shot), real prices, the side's
    price inside -250..+250, two other in-play books, within 6 points of the
    read's median, |line| <= 70; the reference books count toward the median
    and the count but are never bet; equal EV goes by the research's book order;
  * the read sits a minute inside the break at each end, and no later than 25
    minutes after the half's last shot;
  * the pre-game number is Pinnacle's LAST coherent spread and total before
    min(tip, first shot): an out-of-range last quote is no number, never an
    older one;
  * the committed artifact is the 2026-27 fold and the replay it records is
    the research's (364 bets, +45.34 units); it refuses another season;
  * the label carries the side's number (the HOME number, sign turned for
    away), and tracking.pick_integrity agrees;
  * config: the model's cut, EV floor, price floor, settlement market, and the
    sport's live-channel routing.
"""
from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import models.euroleague_live_ht as M  # noqa: E402

FS = pd.Timestamp("2026-11-13T19:15:57Z")          # the game's first shot
Q2 = pd.Timestamp("2026-11-13T20:09:38Z")          # the half's last shot
Q3 = pd.Timestamp("2026-11-13T20:26:52Z")          # the third quarter's first shot
READ = Q2 + pd.Timedelta(minutes=3)
FRESH = Q2 + pd.Timedelta(minutes=2)
HALF = M.Half(FS, Q2, 33, 32, Q3)
MODEL = M.MarginModel((0.89, -0.74, 0.41), (6.9, 189.0, -67.9))
PRIOR_M = 4.5


def quotes(rows):
    """rows: (book, stamp, home line, home price, away price)."""
    return pd.DataFrame(rows, columns=["book", "stamp", "spread_home", "home_price", "away_price"])


def board(dk=(-5.5, -110, -110), fd=None, extra=()):
    """DraftKings and FanDuel fresh, Pinnacle and Unibet (reference books) fresh."""
    rows = [("draftkings", FRESH, *dk),
            ("fanduel", FRESH, *(fd or dk)),
            ("pinnacle", FRESH, -5.5, -105, -115),
            ("unibet", FRESH, -5.0, -110, -110)]
    return quotes(rows + list(extra))


def read(q, at=READ, half=HALF, books=M.DECIDABLE):
    return M.read_break(q, at, half, PRIOR_M, MODEL, books)


# ─── the price ────────────────────────────────────────────────────────────────

def test_the_price_is_the_researchs_formula():
    r = read(board())
    o = r.offers.set_index("book").loc["draftkings"]
    cur_m, f = 1.0, 0.5
    sur = cur_m - PRIOR_M * (1 - f)
    mu = f * PRIOR_M * 0.89 + f * sur * -0.74 + f * f * sur * 0.41
    sd = math.sqrt(6.9 + 189.0 * f - 67.9 * f * f)
    k = 5.5 - cur_m                                    # -(-5.5) - 1
    p_home = norm.sf((k - mu) / sd)                    # not a whole number: no push
    assert o["mean"] == pytest.approx(mu) and o["sd"] == pytest.approx(sd)
    ev_home, ev_away = p_home * (1 + 100 / 110) - 1, (1 - p_home) * (1 + 100 / 110) - 1
    assert o["side"] == ("home" if ev_home >= ev_away else "away")
    assert o["ev"] == pytest.approx(max(ev_home, ev_away))
    assert o["prob"] == pytest.approx(p_home if o["side"] == "home" else 1 - p_home)


def test_a_whole_number_line_removes_the_push():
    r = read(board(dk=(-4.0, -110, -110)))
    o = r.offers.set_index("book").loc["draftkings"]
    k, mu, sd = 4.0 - 1.0, float(o["mean"]), float(o["sd"])
    pw = norm.sf((k + 0.5 - mu) / sd)
    pp = norm.cdf((k + 0.5 - mu) / sd) - norm.cdf((k - 0.5 - mu) / sd)
    assert o["p_push"] == pytest.approx(pp) and pp > 0.03
    p_home = pw / (1 - pp)
    assert o["prob"] == pytest.approx(p_home if o["side"] == "home" else 1 - p_home)


def test_equal_ev_takes_home():
    pw, pp = M.p_over(np.array([0.0]), np.array([9.0]), np.array([-0.0 - 0.0]))
    assert pp[0] > 0 and pw[0] == pytest.approx(norm.sf(0.5 / 9.0))
    # a home line equal to minus the half-time margin with the margin to come centred at zero
    model = M.MarginModel((0.0, 0.0, 0.0), (81.0, 0.0, 0.0))
    q = quotes([("draftkings", FRESH, -1.0, -110, -110), ("pinnacle", FRESH, -1.0, -110, -110),
                ("unibet", FRESH, -1.0, -110, -110)])
    r = M.read_break(q, READ, HALF, PRIOR_M, model)
    assert r.best["side"] == "home" and r.best["ev"] == pytest.approx(r.offers["ev"].iloc[0])


# ─── who may decide ───────────────────────────────────────────────────────────

def test_the_best_ev_at_a_bookable_book_decides():
    r = read(board(fd=(-5.5, -102, -118)))
    assert r.status == "decided" and r.best["side"] == "away"
    assert r.best["book"] == "draftkings"             # -110 on the away side beats FanDuel's -118


def test_equal_ev_goes_by_the_research_book_order():
    r = read(board())                                  # DraftKings and FanDuel identical
    assert r.best["book"] == "draftkings"
    q = board()
    q = q.iloc[[1, 0, 2, 3]].reset_index(drop=True)    # FanDuel listed first
    assert read(q).best["book"] == "draftkings"


def test_a_reference_book_is_never_bet():
    q = board(extra=[("bovada", FRESH, -9.5, -110, -110)])
    r = read(q)
    assert r.best["book"] in M.DECIDABLE
    o = r.offers.set_index("book")
    assert bool(o.loc["pinnacle", "eligible"]) is False and bool(o.loc["bovada", "eligible"]) is False


def test_a_quote_not_re_hung_after_the_half_is_not_eligible():
    q = board()
    q.loc[q["book"].isin(["draftkings", "fanduel"]), "stamp"] = Q2 - pd.Timedelta(seconds=30)
    r = read(q)
    assert r.status == "none"
    o = r.offers.set_index("book")
    assert not o.loc["draftkings", "fresh"] and o.loc["draftkings", "inplay"]


def test_a_pregame_stamp_is_not_in_play_and_does_not_count():
    q = board()
    q.loc[q["book"] == "unibet", "stamp"] = FS - pd.Timedelta(minutes=5)
    q.loc[q["book"] == "pinnacle", "stamp"] = FS - pd.Timedelta(minutes=5)
    r = read(q)
    o = r.offers.set_index("book")
    assert not o.loc["unibet", "inplay"]
    assert int(o.loc["draftkings", "others"]) == 1      # FanDuel only: the two stale books do not count
    assert r.status == "none"


def test_two_other_in_play_books_are_needed():
    q = quotes([("draftkings", FRESH, -5.5, -110, -110), ("pinnacle", FRESH, -5.5, -105, -115)])
    assert read(q).status == "none"
    q2 = quotes([("draftkings", FRESH, -5.5, -110, -110), ("pinnacle", FRESH, -5.5, -105, -115),
                 ("unibet", FRESH, -5.0, -110, -110)])
    assert read(q2).status == "decided"


def test_a_line_more_than_six_points_off_the_reads_median_is_not_bet():
    q = board(dk=(-12.5, -110, -110), fd=(-5.5, -110, -110))
    r = read(q)
    o = r.offers.set_index("book")
    assert float(o.loc["draftkings", "off"]) > M.OUTLIER_PTS and not o.loc["draftkings", "eligible"]
    assert r.best["book"] == "fanduel"


def test_the_side_price_must_sit_inside_minus_250_to_plus_250():
    q = board(dk=(-5.5, 300, -400), fd=(-5.5, 300, -400))
    r = read(q)
    o = r.offers.set_index("book")
    assert o.loc["draftkings", "side"] == "home" and o.loc["draftkings", "price"] == 300
    assert not o.loc["draftkings", "eligible"]
    assert r.status == "none"


def test_a_price_under_100_is_not_a_price():
    q = board(dk=(-5.5, -110, 50), fd=(-5.5, -110, 50))
    assert read(q).status == "none"


def test_a_stamp_after_the_read_is_dropped():
    q = board()
    q.loc[q["book"] == "unibet", "stamp"] = READ + pd.Timedelta(seconds=5)
    r = read(q)
    assert "unibet" not in set(r.offers["book"])


# ─── when ─────────────────────────────────────────────────────────────────────

def test_the_read_sits_a_minute_inside_the_break():
    q = board()
    q["stamp"] = Q2 + pd.Timedelta(seconds=30)
    assert read(q, at=Q2 + pd.Timedelta(seconds=60)).status == "early"
    assert read(q, at=Q2 + pd.Timedelta(seconds=61)).status == "decided"
    assert read(q, at=Q3 - pd.Timedelta(seconds=60)).status == "past"
    assert read(q, at=Q3 - pd.Timedelta(seconds=61)).status == "decided"


def test_a_read_more_than_25_minutes_after_the_half_is_past():
    half = M.Half(FS, Q2, 33, 32, None)
    q = board()
    assert read(q, at=Q2 + pd.Timedelta(minutes=24, seconds=59), half=half).status == "decided"
    assert read(q, at=Q2 + pd.Timedelta(minutes=25, seconds=1), half=half).status == "past"


# ─── the pre-game number ──────────────────────────────────────────────────────

TIP = pd.Timestamp("2026-11-13T19:15:00Z")


def rows(*r):
    """(market, at, spread_home, total, home price, away price, over price, under price)."""
    return list(r)


def test_the_prior_is_pinnacles_last_coherent_quote():
    rs = rows(("spreads", TIP - pd.Timedelta(hours=3), -3.5, None, -110, -110, None, None),
              ("spreads", TIP - pd.Timedelta(minutes=10), -4.5, None, -108, -112, None, None),
              ("spreads", TIP - pd.Timedelta(minutes=5), -6.5, None, -110, 400, None, None),   # incoherent: 1.11 + 0.20
              ("totals", TIP - pd.Timedelta(minutes=20), None, 160.5, None, None, -110, -110))
    assert M.prior_from_pinnacle(rs, before=TIP) == (4.5, 160.5)


def test_a_quote_after_the_bound_is_not_the_prior():
    rs = rows(("spreads", TIP - pd.Timedelta(minutes=10), -4.5, None, -110, -110, None, None),
              ("spreads", TIP + pd.Timedelta(seconds=30), -2.5, None, -110, -110, None, None),
              ("totals", TIP - pd.Timedelta(minutes=20), None, 160.5, None, None, -110, -110))
    assert M.prior_from_pinnacle(rs, before=TIP) == (4.5, 160.5)
    assert M.prior_from_pinnacle(rs, before=TIP + pd.Timedelta(minutes=1)) == (2.5, 160.5)


def test_an_out_of_range_last_quote_is_no_prior_not_an_older_one():
    rs = rows(("spreads", TIP - pd.Timedelta(minutes=10), -4.5, None, -110, -110, None, None),
              ("totals", TIP - pd.Timedelta(minutes=30), None, 160.5, None, None, -110, -110),
              ("totals", TIP - pd.Timedelta(minutes=20), None, 1605.0, None, None, -110, -110))
    assert M.prior_from_pinnacle(rs, before=TIP) is None


def test_both_numbers_are_needed():
    rs = rows(("spreads", TIP - pd.Timedelta(minutes=10), -4.5, None, -110, -110, None, None))
    assert M.prior_from_pinnacle(rs, before=TIP) is None


def test_the_prior_sql_reads_pinnacle_pre_game_rows_bounded_on_the_tip():
    sql = " ".join(M.PRIOR_CLOSE_SQL.split())
    assert "o.bookmaker = 'pinnacle'" in sql
    assert "snapshot_type <> 'in_play'" in sql
    assert "o.snapshot_at::timestamptz <= g.commence_time::timestamptz" in sql


# ─── settlement, units ────────────────────────────────────────────────────────

def test_covers_reads_the_home_number():
    assert M.covers("home", -6.5, 7) == 1 and M.covers("away", -6.5, 7) == -1
    assert M.covers("home", -6.0, 6) == 0 and M.covers("away", 3.5, -3) == -1 and M.covers("home", 3.5, -3) == 1


def test_units_are_the_posted_stake_and_the_research_stake():
    assert M.units("home", -6.5, -150, 10) == pytest.approx((1.0, 1.5))
    assert M.units("home", -6.5, 105, 10) == pytest.approx((1.0, 1 / 1.05))
    assert M.units("home", -6.5, -400, 1) == pytest.approx((-3.0, 3.0))
    assert M.research_units("home", -6.5, 105, 10) == pytest.approx((1.05, 1.0))
    assert M.research_units("away", -6.5, -150, 10) == pytest.approx((-1.5, 1.5))
    assert M.units("home", -6.0, -110, 6) == (0.0, 0.0)


# ─── the artifact ─────────────────────────────────────────────────────────────

def test_the_committed_artifact_is_the_2026_27_fold_and_records_the_researchs_replay():
    art = M.load_artifact()
    raw = art.raw
    assert raw["model_id"] == M.MODEL_ID and raw["season"] == 2027 and art.cut == 0.05
    assert raw["fitted_on_seasons"] == [2022, 2023, 2024, 2025, 2026]
    rep = raw["replay"]
    assert rep["cut_0.05"]["bets"] == 364 and rep["cut_0.05"]["units"] == pytest.approx(45.34, abs=0.005)
    assert rep["matches_research"] is True
    assert {k: v["bets"] for k, v in rep["by_season"].items()} == {"2023": 107, "2024": 61, "2025": 58,
                                                                   "2026": 107, "2027": 31}
    assert rep["prices"]["shortest"] >= -135 and rep["prices"]["longest"] <= 105
    # at the half: about 45% of Pinnacle's margin still to come, a quarter of the surprise given back
    b = art.margin.b
    assert 0.40 < 0.5 * b[0] < 0.50 and -0.32 < 0.5 * b[1] + 0.25 * b[2] < -0.20


def test_an_artifact_for_another_season_or_kind_is_refused(tmp_path):
    raw = json.loads((ROOT / M.ARTIFACT_PATH).read_text(encoding="utf-8"))
    with pytest.raises(ValueError, match="season"):
        M.artifact_from_dict({**raw, "season": 2026})
    with pytest.raises(ValueError, match="not an"):
        M.artifact_from_dict({**raw, "kind": "ncaabw_live_ht"})
    with pytest.raises(ValueError):
        M.artifact_from_dict({**raw, "margin": {"b": [1, 2], "s": [1, 2, 3]}})


def test_the_fit_recovers_known_constants():
    rng = np.random.default_rng(7)
    f = rng.uniform(0.02, 0.98, 80_000)
    pm = rng.normal(4, 6, len(f))
    cur = rng.normal(0, 8, len(f))
    sur = cur - pm * (1 - f)
    mu = f * pm * 0.9 - 0.7 * f * sur + 0.4 * f * f * sur
    y = mu + rng.normal(0, 1, len(f)) * np.sqrt(5 + 180 * f - 60 * f * f)
    m = M.fit(pd.DataFrame({"f": f, "cur_m": cur, "prior_m": pm, "rem_m": y}))
    # what the half reads off them: the share of the prior still to come, and of the surprise carried
    assert 0.5 * m.b[0] == pytest.approx(0.45, abs=0.02)
    assert 0.5 * m.b[1] + 0.25 * m.b[2] == pytest.approx(-0.25, abs=0.02)


def test_states_take_the_running_maximum_in_wall_clock_order():
    shots = pd.DataFrame({"num_anot": [3, 1, 2], "minute": [20, 19, 20], "console": ["01:00", "00:30", "00:10"],
                          "points_home": [33, 30, 31], "points_away": [32, 30, 32],
                          "shot_utc": pd.to_datetime(["2026-11-13T20:09:38Z", "2026-11-13T20:07:00Z",
                                                      "2026-11-13T20:09:00Z"])})
    st = M.states_from_shots(shots)
    assert list(st.gs) == [1170.0, 1190.0, 1190.0]     # the 01:00 placeholder never runs the clock back
    assert list(st.h) == [30, 31, 33] and list(st.a) == [30, 32, 32]


# ─── the pick ─────────────────────────────────────────────────────────────────

def test_the_label_carries_the_sides_number_and_integrity_agrees():
    from tracking.pick_integrity import pick_problems
    assert M.pick_label("home", -5.5, "PAN", "BAR") == "PAN -5.5 (live)"
    assert M.pick_label("away", -5.5, "PAN", "BAR") == "BAR +5.5 (live)"
    assert M.pick_label("away", 0.0, "PAN", "BAR") == "BAR PK (live)"
    for side in ("home", "away"):
        lab = M.pick_label(side, -5.5, "PAN", "BAR")
        assert pick_problems(lab, side, -5.5, M.MODEL_ID, "PAN", "BAR") == []
    assert pick_problems("BAR -5.5 (live)", "away", -5.5, M.MODEL_ID, "PAN", "BAR")


# ─── the platform ─────────────────────────────────────────────────────────────

def test_config_carries_the_models_cut_floors_and_settlement():
    import config
    assert config.LIVE_MODELS[M.MODEL_ID][:3] == ("EUROLEAGUE", "spreads", "engine")
    assert config.ACTION_THRESHOLDS[M.MODEL_ID] == {"min_prob": 0.0, "min_edge": 0.0}
    assert config.MODEL_EDGE_THRESHOLDS[M.MODEL_ID] == 0.0 and config.MODEL_PROB_THRESHOLDS[M.MODEL_ID] == 0.0
    assert config.MODEL_OWN_EV_FLOOR[M.MODEL_ID] == 0.05 == M.load_artifact().cut
    assert config.MODEL_MIN_ODDS[M.MODEL_ID] == -200
    assert M.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.SCORING_METHODS[M.MODEL_ID] == "rule"
    assert M.MODEL_ID not in config.PAUSED_MODELS
    assert "EUROLEAGUE" in config.DISCORD_SPORTS
    assert "EUROLEAGUE" in config.DISCORD_LIVE_CHANNEL_REQUIRED
    assert "EUROLEAGUE" in config.LIVE_ANNOUNCE_WHILE_IN_PROGRESS
    from tracking.paper_tracker import _market_for_pick
    assert _market_for_pick(M.MODEL_ID) == "spreads"


def test_the_ten_history_books_are_the_live_feed_and_the_five_bookable_ones_are_the_researchs():
    import config
    from data.ingestors.euroleague_live_feed import feed_books
    assert feed_books() == list(config.EUROLEAGUE_HISTORY_BOOKMAKERS)
    assert set(M.DECIDABLE) | set(M.REFERENCE) == set(feed_books()) and len(feed_books()) == 10
    assert M.DECIDABLE == ("draftkings", "fanduel", "betmgm", "betrivers", "fanatics")


def test_the_edge_cap_sits_far_above_every_graded_bet():
    from models.euroleague_quote_bounds import EDGE_CAP, edge_problem
    art = M.load_artifact()
    assert EDGE_CAP[M.MODEL_ID] > 2 * art.raw["replay"]["decision_edge_max"]
    assert edge_problem(0.166, M.MODEL_ID) is None and edge_problem(0.41, M.MODEL_ID)
    with pytest.raises(KeyError):
        edge_problem(0.1, "euroleague_some_other_model")


def test_the_ledger_migration_is_registered_and_locked_down():
    from data.anon_readable import WORKER_ONLY_TABLES
    from data.view_migrations import ACTIVE_MIGRATIONS
    name = "euroleague_live_decisions_2026_11_13.sql"
    assert name in ACTIVE_MIGRATIONS
    assert ACTIVE_MIGRATIONS.index(name) < ACTIVE_MIGRATIONS.index("published_pick_units_2026_10_17.sql")
    sql = (ROOT / "data" / "migrations" / name).read_text(encoding="utf-8")
    assert "uq_euroleague_live_decisions_one_decision" in sql and "ENABLE ROW LEVEL SECURITY" in sql
    assert "REVOKE ALL ON public.euroleague_live_decisions FROM anon" in sql
    assert "REVOKE ALL ON public.euroleague_live_decisions FROM authenticated" in sql
    assert "WHERE outcome IN ('bet', 'no_bet', 'declined', 'missed')" in sql
    # locked down by the migration itself; like the other in-play ledgers it has no
    # Python create site, so it is not in WORKER_ONLY_TABLES (tests/test_anon_readable.py)
    assert "euroleague_live_decisions" not in WORKER_ONLY_TABLES
    from models.euroleague_live_loop import LEDGER_COLS
    for c in LEDGER_COLS:
        assert f"    {c} " in sql, c
