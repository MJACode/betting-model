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
  * the lab's main rungs: what the split stores under totals_h1 is exactly the
    lab's main_rungs on its own load;
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
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDS),
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


@pytest.mark.parametrize("season", sorted(LAB_BETS))
def test_the_live_code_reproduces_the_lab_game_for_game(results, season):
    r = results[season]
    assert r["gap_compared"] > 1000 and r["gap_max_abs_diff"] == 0.0, r
    assert r["gap_only_lab"] == [] and r["gap_only_live"] == [], r
    assert r["lab_bets"] == LAB_BETS[season], r
    assert r["bets_matched"] == r["lab_bets"] == r["live_bets"], (r["lab_only"], r["live_only"])
    assert r["decision_time_identical"] and r["fair_probability_identical"], r
    # what the live split stores under totals_h1 is the lab's main rung
    assert r["main_rungs_are_the_labs"], season
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


def test_the_artifact_prices_as_the_lab_priced(ld, art):
    """RULE: the live distribution for each graded season is the lab's own
    period_market_pricing, table for table."""
    assert R.pricing_matches(ld, art, R.REPLAY_SEASONS) == {2024: True, 2025: True, 2026: True}


def test_the_artifact_holds_the_lab_s_rows_in_order(ld, art):
    from scripts.nba_game4_p3 import period_close_rows
    data = ld["data"]
    x = period_close_rows(H.pinnacle_close(data), ld["games_p"])
    rows = pd.DataFrame(art["h1_rows"], columns=["season", "close_total", "h1_total"])
    assert rows["season"].tolist() == [int(s) for s in x["season"]]
    assert rows["close_total"].tolist() == [float(v) for v in x["totals"]]
    assert rows["h1_total"].tolist() == [float(v) for v in x["total_h1"]]


def test_the_split_stores_one_main_rung_per_book_and_fetch(ld):
    s = ld["split"]
    assert s["main"] + s["alternate"] == s["rows"]
    rows = ld["rows"]
    main = rows[rows["market"] == R.fh.MARKET]
    assert not main.duplicated(["game_id", "bookmaker", "created_at"]).any()
