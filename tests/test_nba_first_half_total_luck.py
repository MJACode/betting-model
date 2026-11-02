"""The NBA first-half overs model (`nba_first_half_total_luck`): every rule it
ships on.

models/nba_first_half_total_luck.py holds the rule. Each test names the rule it
pins. The replay of the lab on the research cache is
tests/test_nba_first_half_total_luck_replay.py; the feed, the card, the window
and the settlement have their own files.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

import config  # noqa: E402
import models.nba_first_half_total_luck as fh  # noqa: E402
import models.nba_team_total_luck as tt  # noqa: E402
import models.nba_total_luck as tl  # noqa: E402
from models import nba_book_numbers as NB  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
GID = "NBA_2026-11-05_AWY_HOM"
TIP = datetime(2026, 11, 5, 19, 30, tzinfo=ET).astimezone(UTC)


def _target(day="2026-11-05"):
    return pd.DataFrame([{"game_id": f"NBA_{day}_AWY_HOM", "season": 2027, "game_date": day,
                          "home_team": "HOM", "away_team": "AWY"}])


def _rows(gid, fetch, quotes, market=fh.MARKET, book_age_min=0.5, snapshot_type="open"):
    """odds-table rows at one fetch: (book, line, over, under)."""
    out = []
    for book, line, over, under in quotes:
        out.append({"game_id": gid, "bookmaker": book, "market": market,
                    "snapshot_type": snapshot_type,
                    "snapshot_at": (fetch - timedelta(minutes=book_age_min)).isoformat(),
                    "created_at": fetch.isoformat(), "total_line": line,
                    "over_price": over, "under_price": under,
                    "over_link": f"https://{book}/over", "under_link": f"https://{book}/under"})
    return pd.DataFrame(out)


def _no_missing(monkeypatch):
    monkeypatch.setattr(fh, "missing_inputs", lambda targets, *a: {
        g: {"score_missing": [], "box_missing": [], "box_mismatch": [], "presumed_unplayed": []}
        for g in targets["game_id"]})


def _decide(art, quotes, gap, monkeypatch, lead=55.0, rows=None, **kw):
    """decide() on one target whose full-game gap is forced to `gap` (the offer
    mechanics, independent of the ratings), on a fetch `lead` minutes before tip."""
    t = _target()
    fetch = TIP - timedelta(minutes=lead)
    games = t.assign(tip=pd.Timestamp(TIP))
    q = fh.quote_frame(_rows(GID, fetch, quotes) if rows is None else rows, games)
    monkeypatch.setattr(fh, "f4_projections", lambda targets, tb: t.assign(gap_total=gap))
    _no_missing(monkeypatch)
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    empty = pd.DataFrame(columns=["game_id", "team", *fh.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team",
                                  "home_score", "away_score"])
    return fh.decide(t, q, empty, final, times, art, scheduled=final, **kw)


@pytest.fixture(scope="module")
def art():
    return fh.load_artifact()


# ── one copy: the ratings are nba_total_luck's, the window the team total's ──

def test_the_ratings_are_the_full_game_model_s_own():
    """RULE: the ratings and completeness checks are models/nba_total_luck.py's,
    imported, never copied."""
    for name in ("team_box", "f4_projections", "side_strength", "missing_inputs",
                 "scheduled_games", "regular_season", "lead_minutes"):
        assert getattr(fh, name) is getattr(tl, name), f"nba_first_half_total_luck has its own {name}"
    assert (fh.MIN_GAMES, fh.BOX_COLS) == (tl.MIN_GAMES, tl.BOX_COLS)


def test_the_decision_window_is_the_team_total_model_s():
    """RULE: the same fetch and decision window as the home team total."""
    assert fh.FETCH_LEAD_MIN == tt.FETCH_LEAD_MIN == (45.0, 56.0)
    assert fh.DECISION_LEAD_MIN == tt.DECISION_LEAD_MIN == (45.0, 66.0)
    assert fh.timing is tt.timing


def test_this_model_s_cut_is_its_own_and_the_full_game_cut_does_not_move():
    assert fh.GAP_CUT == 2.0
    assert tl.GAP_CUT == 3.0


# ── the signal: the full-game gap itself, unscaled ──────────────────────────

def test_the_signal_is_the_lab_s_first_half_signal():
    """RULE: strength = gap_total, in full-game points, unscaled
    (scripts/nba_game4_p3.py f4_signal, the definition the lab graded)."""
    from scripts import nba_game4_p3 as P3
    proj = pd.DataFrame({"game_id": ["G1", "G2"], "h_pace": [98.0, 101.0], "a_pace": [102.0, 97.0],
                         "a_drtg_raw": [112.0, 108.0], "a_drtg_adj": [109.0, 110.5],
                         "h_drtg_raw": [108.0, 111.0], "h_drtg_adj": [111.0, 107.0],
                         "gap_total": [2.25, -4.5], "gap_margin": [0.0, 0.0]})
    got = fh.signal(proj).set_index("game_id")["strength"]
    lab = P3.f4_signal(proj)
    lab = lab[lab["market"] == "totals_h1"].set_index("game_id")["strength"]
    assert got.loc[["G1", "G2"]].tolist() == lab.loc[["G1", "G2"]].tolist() == [2.25, -4.5]


@pytest.mark.parametrize("gap,bets", [(6.0, True), (2.5, True), (2.0, True),
                                      (1.99, False), (0.0, False), (-2.5, False), (-6.0, False)])
def test_the_over_is_bet_when_the_gap_is_two_or_more(monkeypatch, art, gap, bets):
    """RULE: bet the first-half OVER when gap_total >= 2.0, never the under,
    however good its price, and nothing under the cut."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, +130, -150),
         ("fanduel", 112.5, -150, +130)]
    got, decisions, diag = _decide(art, q, gap, monkeypatch)
    assert (len(got) == 1) is bets, decisions
    if bets:
        assert (got[0].book, got[0].price) == ("draftkings", 130.0)
        assert decisions[0].detail.startswith("bet:")
    else:
        assert decisions[0].detail.startswith("gap_below_cut") and diag["gap_below_cut"] == 1


# ── the offer ────────────────────────────────────────────────────────────────

def test_the_offer_is_the_best_ev_over_under_the_market_fair_line(monkeypatch, art):
    """RULE: the over at the deciding book with the highest EV under the market's
    fair line (Pinnacle's no-vig through the first half's distribution). Same
    number, the best price wins; a better number can beat a better price."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110),
         ("fanduel", 112.5, -105, -115), ("betmgm", 111.5, -118, -102),
         ("williamhill_us", 113.5, +105, -125)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    assert len(bets) == 1
    b = bets[0]
    sig = {(2027, fh.MARKET): fh.pricing_dist(art, 2027)}
    t = _target()
    fetch = TIP - timedelta(minutes=55)
    frame = fh.quote_frame(_rows(GID, fetch, q), t.assign(tip=pd.Timestamp(TIP)))
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    vis = NB.visible_numbers(frame, times)
    neutral = H.fair_offers(H.offers(vis), H.market_fair(vis, sig))
    overs = neutral[(neutral["side"] == "over")
                    & neutral["book"].isin(config.BEST_LINE_BOOKMAKERS)]
    best = overs.sort_values("ev", ascending=False).iloc[0]
    assert (b.book, b.line, b.price) == (best["book"], best["line"], best["price"])
    assert b.fair_ref == "pinnacle" and b.ev_fair == pytest.approx(float(best["ev"]))
    assert b.ev_fair >= overs["ev"].max() - 1e-12


def test_a_tie_goes_to_the_earlier_book(monkeypatch, art):
    q = [("pinnacle", 112.5, -110, -110), ("betrivers", 112.5, -105, -115),
         ("fanduel", 112.5, -105, -115)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    order = config.BEST_LINE_BOOKMAKERS
    assert order.index("fanduel") < order.index("betrivers")
    assert bets[0].book == "fanduel"


def test_without_pinnacle_the_fair_line_is_the_deciding_books_median(monkeypatch, art):
    q = [("draftkings", 112.5, -110, -110), ("fanduel", 113.5, -115, -105),
         ("betmgm", 112.5, -105, -115)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    assert bets and bets[0].fair_ref == "consensus"


def test_pinnacle_and_bovada_are_never_the_book_taken(monkeypatch, art):
    q = [("pinnacle", 112.5, +120, -140), ("bovada", 108.5, +150, -180),
         ("draftkings", 112.5, -110, -110)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    assert bets[0].book == "draftkings"


def test_an_over_worse_than_minus_200_is_never_taken_even_when_the_platform_floor_moves(
        monkeypatch, art):
    """RULE: -200 or better (config.min_odds_for), even when a Railway
    DEFAULT_MIN_ODDS override moves the harness's import-time floor."""
    assert config.min_odds_for(fh.MODEL_ID) == -200
    monkeypatch.setattr(H, "PRICE_FLOOR", -1000.0)
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 111.5, -210, +170),
         ("fanduel", 112.5, -110, -110)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    assert bets and bets[0].book == "fanduel" and bets[0].price >= -200
    only = [("pinnacle", 112.5, -110, -110), ("draftkings", 111.5, -210, +170)]
    bets, decisions, _ = _decide(art, only, 3.0, monkeypatch)
    assert not bets and decisions[0].detail == "no_offer"


@pytest.mark.parametrize("line,taken", [(110.0, False), (111.5, True)])
def test_a_rung_more_than_a_point_off_the_deciding_books_is_never_taken(
        monkeypatch, art, line, taken):
    """RULE (models/nba_book_numbers.ladder_mask): a deciding book's number more
    than 1.0 point from the median of the deciding books' main numbers is an
    alternate line, never an offer, however good the over looks there."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110),
         ("fanduel", 112.5, -110, -110), ("betmgm", line, -110, -110)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    assert (bets[0].book == "betmgm") is taken, bets


def test_the_draftkings_reference_is_its_over(monkeypatch, art):
    """RULE: the reference DraftKings price and link on an over are the over's
    (price_a / link_a), and the taken link is the over's too."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, +105, -125),
         ("fanduel", 112.5, +110, -130)]
    bets, _, _ = _decide(art, q, 3.0, monkeypatch)
    b = bets[0]
    assert b.book == "fanduel" and b.link == "https://fanduel/over"
    assert b.dk_price == 105.0 and b.dk_link == "https://draftkings/over"


def test_every_decided_game_is_recorded_with_its_best_over_offer(monkeypatch, art):
    """RULE: the best over offer is on the decision, bet or not, so the cut can
    be swept on live data (CLAUDE.md 1b)."""
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110)]
    bets, decisions, _ = _decide(art, q, 0.5, monkeypatch)
    d = decisions[0]
    assert bets == [] and d.n_bets == 0 and d.gap_total == 0.5
    assert (d.book, d.line, d.price, d.fair_ref) == ("draftkings", 112.5, -110.0, "pinnacle")


def test_one_season_per_call(monkeypatch, art):
    t = pd.concat([_target(), _target().assign(season=2026, game_id="G2")], ignore_index=True)
    with pytest.raises(ValueError, match="one season per call"):
        fh.decide(t, pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), art,
                  scheduled=pd.DataFrame())


# ── the probability, and the pricing ─────────────────────────────────────────

def test_the_probability_is_market_fair_plus_the_walk_forward_uplift(monkeypatch, art):
    """RULE: model_probability = the market-fair P(over wins) at the line + the
    bucket's uplift fitted on the graded seasons before the live one (for
    2026-27: 333 wins in 595 bets against a mean fair 0.5025, +0.0572)."""
    bucket = {int(s): v for s, v in art["bucket"].items()}
    assert {s: (v["n"], v["wins"], v["pushes"], round(v["sum_p_win"], 4))
            for s, v in bucket.items()} == {2024: (244, 132, 1, 122.4430),
                                            2025: (188, 108, 2, 94.1349),
                                            2026: (163, 93, 0, 82.4040)}
    up = fh.uplift(art, 2027)
    assert up == pytest.approx((333 - sum(v["sum_p_win"] for v in bucket.values())) / 595)
    assert up == pytest.approx(0.0572, abs=5e-5)
    assert fh.uplift(art, 2026) == pytest.approx(0.0542, abs=5e-5)     # fitted on 2024-2025
    assert fh.uplift(art, 2025) == pytest.approx(0.0392, abs=5e-5)     # fitted on 2024
    with pytest.raises(ValueError, match="no graded bucket season before 2024"):
        fh.uplift(art, 2024)
    q = [("pinnacle", 112.5, -110, -110), ("draftkings", 112.5, -110, -110)]
    b = _decide(art, q, 3.0, monkeypatch)[0][0]
    assert b.p_model == pytest.approx(b.p_fair + up) and b.uplift == pytest.approx(up)


def _art(rows, built):
    return {"kind": fh.ARTIFACT_KIND, "built_at": built, "h1_rows": rows, "bucket": {}}


def test_each_season_is_priced_on_the_seasons_before_it_only(art):
    """RULE: season S is priced on the games of seasons before S, at least 300 of
    them, and NEVER on S's own (no fallback)."""
    assert fh.newest_season(art) == 2026
    seasons = pd.Series([int(r[0]) for r in art["h1_rows"]])
    assert fh.pricing_dist(art, 2027).n == int((seasons < 2027).sum()) == 7230
    assert fh.pricing_dist(art, 2024).n == int((seasons < 2024).sum()) == 3540
    rng = np.random.default_rng(0)
    own = [(2026, 220.0, float(v)) for v in rng.normal(150.0, 11.0, 5000)]
    few = [(2025, float(x), float(x / 2 + e)) for x, e in zip(rng.normal(225.0, 10.0, 299),
                                                              rng.normal(0.0, 11.0, 299))]
    with pytest.raises(ValueError, match="299 games with a first-half total before 2026"):
        fh.pricing_dist(_art(few + own, "few"), 2026)
    d = fh.pricing_dist(_art(few + [(2024, 220.0, 110.0)] + own, "enough"), 2026)
    assert d.n == 300                       # the season's own 5,000 are not in it


def test_a_game_with_no_trustworthy_first_half_is_left_out_of_the_fit():
    """A NaN first-half total (with_periods' check failed) is not a residual, in
    the lab and here."""
    rng = np.random.default_rng(1)
    rows = [(2025, float(x), float(x / 2 + e)) for x, e in zip(rng.normal(225.0, 10.0, 400),
                                                               rng.normal(0.0, 11.0, 400))]
    d = fh.pricing_dist(_art(rows + [(2025, 225.0, float("nan"))] * 7, "nan"), 2026)
    assert d.n == 400


def test_the_artifact_is_this_model_s():
    with pytest.raises(ValueError, match="not an nba_first_half_total_luck artifact"):
        fh.load_artifact(ROOT / tt.ARTIFACT_PATH)


# ── the quotes ───────────────────────────────────────────────────────────────

def test_a_first_half_row_reads_its_line_over_and_under():
    """RULE: line = total_line, price_a = the over, price_b = the under, the fetch
    instant is created_at; only pre-game first-half main rows are read."""
    fetch = TIP - timedelta(minutes=55)
    rows = pd.concat([
        _rows(GID, fetch, [("fanduel", 112.5, -105, -115)]),
        _rows(GID, fetch, [("fanduel", 115.5, +140, -175)], market="totals_h1_alternate"),
        _rows(GID, fetch, [("fanduel", 225.5, -110, -110)], market="totals"),
        _rows(GID, fetch, [("fanduel", 113.5, -110, -110)], market="team_totals_home"),
        _rows(GID, fetch, [("draftkings", 112.5, -110, -110)], snapshot_type="in_play")],
        ignore_index=True)
    q = fh.quote_frame(rows, _target().assign(tip=pd.Timestamp(TIP)))
    assert len(q) == 1
    r = q.iloc[0]
    assert (r["book"], r["line"], r["price_a"], r["price_b"]) == ("fanduel", 112.5, -105, -115)
    assert r["link_a"] == "https://fanduel/over" and bool(r["coherent"])
    assert r["fetch_at"] == pd.Timestamp(fetch) == r["snapshot_at"]


def test_the_team_total_model_still_shapes_its_own_market():
    """The market argument defaults to the team total's: its card and replay call
    quote_frame without it."""
    fetch = TIP - timedelta(minutes=55)
    rows = pd.concat([_rows(GID, fetch, [("fanduel", 112.5, -105, -115)], market="team_totals_home"),
                      _rows(GID, fetch, [("draftkings", 112.5, -110, -110)])], ignore_index=True)
    q = tt.quote_frame(rows, _target().assign(tip=pd.Timestamp(TIP)))
    assert q["book"].tolist() == ["fanduel"]


def test_staleness_is_judged_on_the_fetch_instant_and_each_book_s_age_is_kept(monkeypatch, art):
    """RULE: a book whose own last_update is two hours old, in a fetch made at T,
    is visible at T. Its age is kept on the decision so it can be measured."""
    fetch = TIP - timedelta(minutes=55)
    rows = pd.concat([_rows(GID, fetch, [("pinnacle", 112.5, -110, -110)]),
                      _rows(GID, fetch, [("draftkings", 112.5, +105, -125)], book_age_min=120)],
                     ignore_index=True)
    bets, decisions, _ = _decide(art, None, 3.0, monkeypatch, rows=rows)
    assert bets[0].book == "draftkings"
    assert decisions[0].book_ages["draftkings"] == 120.0


def test_the_split_files_a_second_rung_under_the_first_half_alternate():
    """RULE (models/nba_book_numbers.split_main_rungs): the main rung, closest to
    even, keeps totals_h1; another rung of one book in one fetch goes under
    totals_h1_alternate, where no reader of one row per (game, market, book) lands.
    A full-game total is still refused: it is not a per-event market."""
    def row(line, over, under):
        return {"game_id": GID, "bookmaker": "fanduel", "market": fh.MARKET,
                "total_line": line, "over_price": over, "under_price": under}
    main, alt = NB.split_main_rungs([row(110.5, -140, +115), row(112.5, -110, -110),
                                     row(114.5, +120, -145)])
    assert [r["total_line"] for r in main] == [112.5]
    assert {r["market"] for r in alt} == {"totals_h1_alternate"} and len(alt) == 2
    with pytest.raises(ValueError, match="not a per-event total market"):
        NB.split_main_rungs([{**row(225.5, -110, -110), "market": "totals"}])


# ── config ───────────────────────────────────────────────────────────────────

def test_the_floor_and_the_thresholds_are_the_model_s_own():
    """RULE: its cut is the gap; prob and edge are 0.0 so every publisher shows
    what the card wrote; its EV floor is its own; it decides on its own number."""
    assert config.ACTION_THRESHOLDS[fh.MODEL_ID] == {"min_prob": 0.0, "min_edge": 0.0}
    assert config.MODEL_MIN_ODDS[fh.MODEL_ID] == -200
    assert config.MODEL_OWN_EV_FLOOR[fh.MODEL_ID] == 0.00
    assert fh.MODEL_ID in config.MODELS_ON_OWN_PROBABILITY
    assert config.SCORING_METHODS[fh.MODEL_ID] == "rule"
    assert config.MODEL_EDGE_THRESHOLDS[fh.MODEL_ID] == 0.0
    assert config.MODEL_PROB_THRESHOLDS[fh.MODEL_ID] == 0.0
    assert fh.MODEL_ID not in config.PAUSED_MODELS


def test_opening_night_declines_every_game_without_crashing(art):
    """No team has 10 games and no season game is stored: every game is recorded
    with the reason, and nothing raises."""
    t = _target()
    fetch = TIP - timedelta(minutes=55)
    games = t.assign(tip=pd.Timestamp(TIP))
    q = fh.quote_frame(_rows(GID, fetch, [("pinnacle", 112.5, -110, -110),
                                          ("draftkings", 112.5, -110, -110)]), games)
    times = pd.DataFrame({"game_id": t.game_id, "T": [pd.Timestamp(fetch)]})
    box = pd.DataFrame(columns=["game_id", "team", *fh.BOX_COLS])
    final = pd.DataFrame(columns=["game_id", "season", "game_date", "home_team", "away_team",
                                  "home_score", "away_score"])
    sched = pd.DataFrame(columns=["game_id", "game_date", "home_team", "away_team", "status_text"])
    bets, decisions, diag = fh.decide(t, q, box, final, times, art, scheduled=sched)
    assert bets == [] and diag["early_season"] == 1
    assert decisions[0].detail.startswith("early_season")
