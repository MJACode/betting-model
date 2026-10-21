"""The NBA home team-total unders model's LIVE code, replayed on 2023-24 ..
2025-26 against the lab.

models/nba_team_total_luck.decide -- the code the card bets with -- is run on
the research cache at the lab's own decision instants (decision point D, the
per-game purchase 45-75 minutes before tip), on the archived team-total rows
passed through the LIVE write-time split (models.nba_book_numbers.
split_main_rungs) and the live shaping (quote_frame), with the committed
artifact's pricing, and the season's games, box scores and owed games read by
the totals card's own load (scripts/nba_team_total_luck_replay.py). It must
reproduce, game for game:

  * the lab's home part on every game it priced (scripts.nba_game4_p3.
    f4_signal over scripts.nba_game2_luck's projection of every graded season).
    On this branch that projection IS models/nba_total_luck's, the code the
    card runs, so that comparison can only catch a change in the inputs or
    the home-part formula. The parts are also pinned to the fourth search's
    own copy of the projection (LAB_HOME_PARTS_SHA256), so a change to the
    shared ratings code fails here even when no bet crosses the cut;
  * the lab's bets for the shipped cell (P3_F4, D, team_totals_home, under,
    cut 2.0): same game, book, line, price and decision instant, same
    market-fair probability;
  * the lab's main rungs: what the split stores under team_totals_home is
    exactly the lab's main_rungs on its own load.

Measured 2026-10-19 (`python -m scripts.nba_team_total_luck_replay`): 349 of
349 bets matched (139, 112, 98), none on one side only; 3,202 home parts
identical (largest difference 0.0); 215-134, +64.72 units on 390.37 risk;
every bet decided 54.3 to 64.4 minutes before tip, a 'decide' under the live
timing; the EV floor at the 2026-27 uplift removes only NBA_2025-01-24_POR_CHA.
The same run compared the artifact's distributions with the lab's own
team_total_dist for 2024-2026 (same rows, same probabilities); that comparison
takes about 70 seconds and is left to the script. Here the artifact's
residuals are checked against the lab's rows instead, in order.

Needs the research cache (NBA_RESEARCH_CACHE, written by
scripts/nba_research_cache.py) and the lab's bet file; SKIPS where either is
absent. About 75 seconds on the build machine (30 of them the load).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_team_total_luck_replay as R  # noqa: E402

NEEDS = [H.CACHE / f for f in ("nba_odds.parquet", "nba_fetch_ledger.parquet",
                               "nba_player_game_log.parquet", "nba_games.parquet",
                               "nba_schedule.parquet", "nba_period_scores.parquet")] + [R.BETS]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDS),
                                reason="the NBA research cache or the lab's bet file is not here")

LAB_BETS = {2024: 139, 2025: 112, 2026: 98}
# The lab's home part on the 3,202 games with a decision instant (1,069, 1,069,
# 1,064), computed by the fourth search's OWN copy of the projection
# (C:/Users/micha/Documents/bm-nba-s4 at ff54a4d2, scripts/nba_game2_luck.py:
# its own team_box and f4_projections, nothing imported from models/), loaded as
# scripts.nba_game4_p3.full loads it: sha256 of the sorted "game_id,part" lines,
# the part to 6 places. Computed 2026-10-20 in that worktree, with no models
# module loaded: H.load(cache, seasons=P3.FULL_GAME_SEASONS), P3.load_derivatives,
# L.f4_projections(graded games, L.team_box(L._load_box(cache)[0], games)),
# P3.f4_signal's team_totals_home rows, kept where H.per_event_times(pe, P3.POINT)
# has the game.
LAB_HOME_PARTS_N = 3202
LAB_HOME_PARTS_SHA256 = "41028f329245a6db6c82ba4f72d09f699ee7d2fb4bacfdaa22e32cd158bd23cb"
BELOW_FLOOR = {2024: [], 2025: ["NBA_2025-01-24_POR_CHA"], 2026: []}


@pytest.fixture(scope="module")
def ld():
    return R.load()


@pytest.fixture(scope="module")
def art():
    return R.tt.load_artifact()


@pytest.fixture(scope="module")
def results(ld, art):
    return {s: R.replay(ld, s, art) for s in R.REPLAY_SEASONS}


@pytest.mark.parametrize("season", sorted(LAB_BETS))
def test_the_live_code_reproduces_the_lab_game_for_game(results, season):
    r = results[season]
    assert r["home_part_compared"] > 1000 and r["home_part_max_abs_diff"] == 0.0, r
    assert r["home_part_only_lab"] == [] and r["home_part_only_live"] == [], r
    assert r["lab_bets"] == LAB_BETS[season], r
    assert r["bets_matched"] == r["lab_bets"] == r["live_bets"], (r["lab_only"], r["live_only"])
    assert r["decision_time_identical"] and r["fair_probability_identical"], r
    # what the live split stores under team_totals_home is the lab's main rung
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


def test_the_three_seasons_grade_as_the_lab_graded(results):
    wins = sum(r["record"].get("W", 0) for r in results.values())
    losses = sum(r["record"].get("L", 0) for r in results.values())
    pushes = sum(r["record"].get("P", 0) for r in results.values())
    assert (wins, losses, pushes) == (215, 134, 0)
    assert round(sum(r["units"] for r in results.values()), 2) == 64.72
    assert round(sum(r["risk"] for r in results.values()), 2) == 390.37
    below = [b for r in results.values() for b in r["below_ev_floor_at_2026_27_uplift"]]
    assert [(b["book"], b["line"], b["price"]) for b in below] == [("fanduel", 109.5, -118.0)]


def test_the_split_stores_one_main_rung_per_book_and_fetch(ld):
    s = ld["split"]
    assert s["main"] + s["alternate"] == s["rows"]
    by = s["by_market"]
    assert by["team_totals_home"] > 15000 and by["team_totals_home_alternate"] > 15000, by
    rows = ld["rows"]
    main = rows[rows["market"] == R.tt.MARKET]
    assert not main.duplicated(["game_id", "bookmaker", "created_at"]).any()


def test_the_artifact_holds_the_lab_s_team_total_residuals_in_order(ld, art):
    from scripts.nba_game2_market import team_total_resid
    data = ld["data"]
    r = team_total_resid(H.pinnacle_close(data), data.games)
    assert [(int(s), float(v)) for s, v in zip(r["season"], r["resid"])] == art["tt_resid"]


def test_the_live_home_parts_are_the_independent_lab_copy_s(results):
    """RULE: the live ratings code (models/nba_total_luck: team_box,
    f4_projections) still gives the lab's home parts, checked against a copy
    of the lab that shares no code with it. Watched failing with the
    free-throw possession weight moved 0.44 -> 0.30, a change that flips no
    bet and passes every other test in this file."""
    import hashlib
    parts: dict = {}
    for r in results.values():
        parts.update(r["live_home_parts"])
    lines = sorted(f"{g},{float(v):.6f}" for g, v in parts.items())
    assert len(lines) == LAB_HOME_PARTS_N
    assert hashlib.sha256("\n".join(lines).encode()).hexdigest() == LAB_HOME_PARTS_SHA256
