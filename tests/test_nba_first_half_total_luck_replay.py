"""The NBA first-half overs model's LIVE code, replayed on 2023-24 .. 2025-26
against the lab.

models/nba_first_half_total_luck.decide -- the code the card bets with -- is run
on the research cache at the lab's own decision instants (decision point D, the
per-game purchase 45-75 minutes before tip), on the archived first-half rows passed
through the LIVE write-time split (models.nba_book_numbers.split_main_rungs) and
the live shaping (quote_frame), with the committed artifact's pricing, and the
season's games, box scores and owed games read by the totals card's own load
(scripts/nba_first_half_total_luck_replay.py). It must reproduce, game for game:

  * the lab's gap on every game it priced (scripts.nba_game4_p3.f4_signal over
    scripts.nba_game2_luck's projection of every graded season). The ratings code
    itself is pinned against the fourth search's own copy by
    tests/test_nba_team_total_luck_replay.py;
  * the lab's bets for the shipped cell, C1 (P3_F4, D, totals_h1, over, cut 2.0):
    same game, book, line, price and decision instant, same market-fair probability;
  * the lab's rows: what the split stores under totals_h1 is exactly the lab's own
    load. The purchase kept one pair per book, so this says nothing about whether
    those rows are main numbers, and at three books they are not (see below);
  * the lab's result on every bet, settled by the LIVE settlement code
    (tracking.paper_tracker._first_half_points and _compute_result) from the
    cache's nba_period_scores.

Measured 2026-10-31 (`python -m scripts.nba_first_half_total_luck_replay`): 595 of
595 bets matched (244, 188, 163), none on one side only; 3,202 gaps identical
(largest difference 0.0); the artifact's distributions identical to the lab's
period_market_pricing for 2024-2026; 333-259-3, +51.49 units on 643.19 risk; every
bet decided 49.4 to 64.4 minutes before tip, a 'decide' under the live timing. The
one difference from the lab, by design: the EV floor at the 2026-27 uplift removes
two bets, NBA_2024-11-18_IND_TOR and NBA_2025-01-02_BOS_MIN, both wins.

WHAT THE MATCH DOES NOT PROVE. Every archived fetch holds one number per book, so
the main-number rule chooses nothing here (rungs_listed). The test below pins that
the replay reports it, and test_the_quotes_the_replay_cannot_vouch_for pins the rows
behind THE GRADED QUOTES of models/nba_first_half_total_luck.py.

Needs the research cache (NBA_RESEARCH_CACHE, written by
scripts/nba_research_cache.py) and the lab's bet file; SKIPS where either is
absent. It took 1,244 seconds on 2026-10-31 with other jobs holding the machine's
CPU at 100%: the load, and the first-half distributions of three seasons, each
built twice.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts import nba_first_half_total_luck_replay as R  # noqa: E402
from scripts import nba_game_harness as H  # noqa: E402

NEEDS = [H.CACHE / f for f in ("nba_odds.parquet", "nba_fetch_ledger.parquet",
                               "nba_player_game_log.parquet", "nba_games.parquet",
                               "nba_schedule.parquet", "nba_period_scores.parquet")] + [R.BETS]
needs_cache = pytest.mark.skipif(not all(p.exists() for p in NEEDS),
                                 reason="the NBA research cache or the lab's bet file is not here")

LAB_BETS = {2024: 244, 2025: 188, 2026: 163}
BELOW_FLOOR = {2024: [], 2025: ["NBA_2024-11-18_IND_TOR", "NBA_2025-01-02_BOS_MIN"], 2026: []}


@pytest.fixture(scope="module")
def ld():
    return R.load()


@pytest.fixture(scope="module")
def art():
    return R.fh.load_artifact()


@pytest.fixture(scope="module")
def results(ld, art):
    return {s: R.replay(ld, s, art) for s in R.REPLAY_SEASONS}


@needs_cache
@pytest.mark.parametrize("season", sorted(LAB_BETS))
def test_the_live_code_reproduces_the_lab_game_for_game(results, season):
    r = results[season]
    assert r["gap_compared"] > 1000 and r["gap_max_abs_diff"] == 0.0, r
    assert r["gap_only_lab"] == [] and r["gap_only_live"] == [], r
    assert r["lab_bets"] == LAB_BETS[season], r
    assert r["bets_matched"] == r["lab_bets"] == r["live_bets"], (r["lab_only"], r["live_only"])
    assert r["decision_time_identical"] and r["fair_probability_identical"], r
    # what the live split stores under totals_h1 is the lab's own row. True of any
    # file with one number per book, so it is not reported as a main-number check.
    assert r["split_keeps_the_labs_rows"], season
    assert "main_rungs_are_the_labs" not in r
    # the card's own season load returns the lab's population, scores included,
    # and the completeness check declines nothing on the lab's own data
    assert r["load_season_is_the_lab_population"], (r["load_season_games"], r["lab_games"])
    d = r["diag"]
    assert (d["score_missing"], d["box_missing"], d["box_mismatch"], d["presumed_unplayed"]) == (
        0, 0, 0, []), d
    assert (d["no_fair_line"], d["no_offer"]) == (0, 0), d
    # every graded bet is a 'decide' under the live timing (45-66 minutes out)
    assert r["every_bet_decides_under_live_timing"], r["lead_min"]
    assert [b["game_id"] for b in r["below_ev_floor_at_2026_27_uplift"]] == BELOW_FLOOR[season]
    # the live settlement grades every bet as the lab did
    assert r["settled_differently"] == [] and r["settled_pending"] == [], r


@needs_cache
def test_the_three_seasons_grade_as_the_lab_graded(results):
    wins = sum(r["record"].get("W", 0) for r in results.values())
    losses = sum(r["record"].get("L", 0) for r in results.values())
    pushes = sum(r["record"].get("P", 0) for r in results.values())
    assert (wins, losses, pushes) == (333, 259, 3)
    assert round(sum(r["units"] for r in results.values()), 2) == 51.49
    assert round(sum(r["risk"] for r in results.values()), 2) == 643.19
    below = [b for r in results.values() for b in r["below_ev_floor_at_2026_27_uplift"]]
    assert [(b["book"], b["line"], b["price"]) for b in below] == [
        ("hardrockbet", 118.5, -110.0), ("draftkings", 109.0, -110.0)]


@needs_cache
def test_the_artifact_prices_as_the_lab_priced(ld, art):
    """RULE: the live distribution for each graded season is the lab's own
    period_market_pricing, table for table."""
    assert R.pricing_matches(ld, art, R.REPLAY_SEASONS) == {2024: True, 2025: True, 2026: True}


@needs_cache
def test_the_artifact_holds_the_lab_s_rows_in_order(ld, art):
    from scripts.nba_game4_p3 import period_close_rows
    data = ld["data"]
    x = period_close_rows(H.pinnacle_close(data), ld["games_p"])
    rows = pd.DataFrame(art["h1_rows"], columns=["season", "close_total", "h1_total"])
    assert rows["season"].tolist() == [int(s) for s in x["season"]]
    assert rows["close_total"].tolist() == [float(v) for v in x["totals"]]
    assert rows["h1_total"].tolist() == [float(v) for v in x["total_h1"]]


@needs_cache
def test_the_split_stores_one_main_rung_per_book_and_fetch(ld):
    s = ld["split"]
    assert s["main"] + s["alternate"] == s["rows"]
    rows = ld["rows"]
    main = rows[rows["market"] == R.fh.MARKET]
    assert not main.duplicated(["game_id", "bookmaker", "created_at"]).any()


@needs_cache
def test_the_quotes_the_replay_cannot_vouch_for(ld):
    """RULE: the record says the split chose nothing and three books' rows are not
    main numbers. This pins the counts it quotes, on the archived rows."""
    assert R.rungs_listed(ld["rows"]) == {
        "most_per_book_and_fetch": 1, "fetches_with_a_choice": 0,
        "the_main_rule_chose_anything": False}
    assert ld["split"]["alternate"] == 0
    c = R.quote_census(ld["rows"])
    assert c.loc["betrivers", "far"] == 84.6 and c.loc["betparx", "far"] == 82.7
    assert c.loc["hardrockbet", "far"] == 34.0
    deciding = set(R.fh.config.BEST_LINE_BOOKMAKERS) - set(R.OFF_MAIN_BOOKS)
    assert c[c.index.isin(deciding)]["far"].max() <= 1.1
    p = R.lab_prices()
    assert p["all"] == (-130.0, 114.0, 595) and p["main_number_books"] == (-118.0, 105.0, 517)


# ── needs neither the cache nor the bets: what a replay may claim ───────────────

def _one_pair_per_book():
    return pd.DataFrame([
        {"game_id": "G", "bookmaker": "betrivers", "created_at": "T", "market": "totals_h1",
         "total_line": 120.5, "snapshot_at": "T"},
        {"game_id": "G", "bookmaker": "draftkings", "created_at": "T", "market": "totals_h1",
         "total_line": 113.5, "snapshot_at": "T"},
        {"game_id": "G", "bookmaker": "pinnacle", "created_at": "T", "market": "totals_h1",
         "total_line": 113.5, "snapshot_at": "T"}])


def test_a_file_with_one_number_per_book_gave_the_main_rule_nothing_to_choose():
    """RULE: a match against the main-number rule on such a file is true of any file,
    so the replay must say so instead of reporting it as evidence."""
    assert R.rungs_listed(_one_pair_per_book()) == {
        "most_per_book_and_fetch": 1, "fetches_with_a_choice": 0,
        "the_main_rule_chose_anything": False}
    two = pd.concat([_one_pair_per_book(), _one_pair_per_book().assign(total_line=119.5)])
    assert R.rungs_listed(two)["the_main_rule_chose_anything"] is True


def test_the_census_shows_a_row_far_from_pinnacle_s_number():
    c = R.quote_census(_one_pair_per_book())
    assert c.loc["betrivers", "far"] == 100.0 and c.loc["betrivers", "on"] == 0.0
    assert c.loc["draftkings", "far"] == 0.0 and c.loc["draftkings", "on"] == 100.0


def test_the_record_states_both_price_ranges_and_the_re_grades():
    """RULE: the graded quotes' caveat is written where the rule is read, with the
    re-grades that bound it, and not only in the search's write-up."""
    root = Path(__file__).resolve().parent.parent
    model = (root / "models/nba_first_half_total_luck.py").read_text(encoding="utf-8")
    doc = (root / "docs/nba_models_2026.md").read_text(encoding="utf-8")
    assert "THE GRADED QUOTES ARE NOT ALL MAIN NUMBERS" in model
    for text in (model, doc):
        for figure in ("-118 to +105", "-130 to +114", "+48.12", "-0.04%"):
            assert figure in text, figure
    assert "proven on the shape the live fetch stores" not in R.__doc__
