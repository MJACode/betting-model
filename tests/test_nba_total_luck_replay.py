"""The NBA totals overs model's LIVE code, replayed on 2025-26 against the lab.

models/nba_total_luck.decide -- the code the card bets with -- is run on the
research cache at the lab's own 2025-26 decision instants (decision point C),
on quotes shaped by the live shaping (quote_frame), with the committed
artifact's pricing (scripts/nba_total_luck_replay.py). It must reproduce, game
for game:

  * the lab's gap on every game it priced (scripts.nba_game2_luck's own
    projection over every graded season at once);
  * the lab's bets for the shipped cell (F4, C, totals, over, gap >= 3): same
    game, book, line, price and decision instant, same market-fair
    probability.

Measured when this shipped (2026-10-17): 2025-26, 1,075 gaps identical (largest
difference 0.0), 82 of 82 bets matched, none on one side only. The same replay
over 2020-21 .. 2025-26 matched all 611 bets and 6,294 gaps
(`python -m scripts.nba_total_luck_replay`). Re-run 2026-10-17 with the
league-wide completeness check (the season's schedule as an input): the same
611 of 611 bets and 6,294 identical gaps, no game declined for a missing score
or box.

Since the review of 2026-10-17 the season's games, box scores and owed games
come through the CARD'S OWN load (scripts.nba_total_luck_card.load_season, its
SQL answered from the cache), not the lab's game list: the regular-season rule
and the box-integrity check are inside the replay. Re-run that day over
2020-21 .. 2025-26: load_season returned exactly the lab's games and scores in
every season (1,080, then 1,230 a season), 611 of 611 bets and 6,294 gaps
identical (largest difference 0.0), no game declined for a missing score, a
missing box or a box that does not add up.

Needs the research cache (NBA_RESEARCH_CACHE, written by
scripts/nba_research_cache.py) and the lab's bet file; SKIPS where either is
absent. About 25 seconds on the build machine.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost/db")

from scripts import nba_game_harness as H  # noqa: E402
from scripts import nba_total_luck_replay as R  # noqa: E402

NEEDS = [H.CACHE / "nba_odds.parquet", H.CACHE / "nba_fetch_ledger.parquet",
         H.CACHE / "nba_player_game_log.parquet", H.CACHE / "nba_games.parquet", R.BETS]
pytestmark = pytest.mark.skipif(not all(p.exists() for p in NEEDS),
                                reason="the NBA research cache or the lab's bet file is not here")


def test_the_live_code_reproduces_the_lab_on_2025_26():
    r = R.replay(R.load(), 2026)
    assert r["gap_compared"] > 1000 and r["gap_max_abs_diff"] == 0.0, r
    assert r["gap_only_lab"] == [] and r["gap_only_live"] == [], r
    assert r["lab_bets"] == 82, r
    assert r["bets_matched"] == r["lab_bets"] == r["live_bets"], (r["lab_only"], r["live_only"])
    assert r["decision_time_identical"] and r["fair_probability_identical"], r
    # The completeness check (every game of the season before the date, scored
    # and boxed) declines nothing on the lab's own data, where every game was.
    d = r["diag"]
    assert d["score_missing"] == 0 and d["box_missing"] == 0 and d["presumed_unplayed"] == [], d
    assert d["box_mismatch"] == 0, d
    # the card's own season load returns the lab's population, scores included
    assert r["load_season_is_the_lab_population"], (r["load_season_games"], r["lab_games"])
