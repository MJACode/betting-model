"""
Score a game as soon as its line opens, not when the calendar rolls over.

THE BUG THIS CLOSES. The scorer selected `game_date = target_date` — today,
and only today — with carve-outs for UFC, NCAAF and golf. So a line that
opened for TOMORROW was fetched by the 30-second pre-game poller, diffed,
stored, and then dropped, because the game was not in the day's set. Measured
per MLB slate (first stored DK odds row -> first pick, ET):

    09-04 slate   20:16 -> 00:20   4h04m
    09-05 slate   20:22 -> 00:21   3h59m
    09-06 slate   18:16 -> 00:19   6h03m

Every slate's first pick landed at 00:19-00:21: the `:17` overnight refresh,
the first pass after midnight. mike, 2026-09-06: "I want as soon as lines open
in a market we can bet."

Three things had to be true together, and each has tests here:
  1. the scorer must LOOK at tomorrow's games,
  2. it must only look at ones DraftKings has actually priced,
  3. and the data those games need must exist — MLB game models fail closed
     without a probable starter, and probables stopped at today.

Plus the fourth, found while building: the poller could not create a `games`
row, and `odds` has a foreign key to `games`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import config  # noqa: E402

_SCORER_SRC = (Path(__file__).parent.parent / "models" / "scorer.py").read_text(
    encoding="utf-8")
_ODDS_SRC = (Path(__file__).parent.parent / "data" / "ingestors"
             / "odds_ingestor.py").read_text(encoding="utf-8")


class TestTheWindow:
    def test_the_four_same_day_sports_now_have_a_look_ahead(self):
        assert set(config.GAME_SCORE_AHEAD_SPORTS) == {"MLB", "NBA", "NHL", "WNBA"}
        assert config.GAME_SCORE_AHEAD_DAYS >= 1

    def test_the_games_query_selects_them_ahead_of_today(self):
        # The clause itself, because the alternative is a database.
        q = _SCORER_SRC[_SCORER_SRC.index("SELECT game_id, sport, season, game_date"):]
        q = q[:q.index("ORDER BY sport, game_date")]
        assert "game_date = ?" in q, "today must still be selected unconditionally"
        assert "_ahead_marks" in q, "the look-ahead sports clause is missing"

    def test_ncaaf_and_ufc_horizons_are_untouched(self):
        # They had look-ahead already and their models were validated with it.
        # Widening them would be a different change riding along inside this one.
        assert config.NCAAF_SCORE_AHEAD_DAYS == 7
        assert config.UFC_SCORE_AHEAD_DAYS == 7

    def test_the_housekeeping_delete_covers_the_new_horizon(self):
        # THE TRAP. That DELETE clears non-BET rows across the look-ahead
        # window so each pass leaves exactly one current row per side. Bounded
        # to the OLD horizons it would stop short of the games this change just
        # started scoring, and they would accumulate a fresh NONE row every
        # pass with nothing ever clearing the last.
        assert "max(ncaaf_horizon, ufc_horizon, game_horizon)" in _SCORER_SRC, \
            "the non-BET delete must span every look-ahead horizon"

    def test_the_horizon_is_computed_from_the_target_date(self):
        assert "game_horizon = (" in _SCORER_SRC
        assert "timedelta(days=GAME_SCORE_AHEAD_DAYS)" in _SCORER_SRC


class TestThePriceGate:
    """A future game earns its way in with a DK price, not with a day count."""

    def test_the_gate_exists_and_is_applied_in_the_loop(self):
        assert "ahead_unpriced" in _SCORER_SRC
        assert "if game_id in ncaaf_unpriced or game_id in ahead_unpriced:" \
            in _SCORER_SRC

    def test_only_future_games_are_gated(self):
        # Today's games were scored before this change whether or not DK had
        # posted, and several models handle a missing price themselves.
        # Filtering them here would be an unrequested behaviour change hiding
        # inside a look-ahead feature.
        block = _SCORER_SRC[_SCORER_SRC.index("ahead_unpriced: set = set()"):]
        block = block[:block.index("# Check for postponed")]
        assert "g[3] > target_date" in block, \
            "the price gate must exclude today's games"

    def test_the_gate_fails_open(self):
        # §7: a filter that cannot be built must never be able to empty the
        # board. Worst case we pay the old cost.
        block = _SCORER_SRC[_SCORER_SRC.index("ahead_unpriced: set = set()"):]
        block = block[:block.index("# Check for postponed")]
        assert "ahead_unpriced = set()" in block.split("except")[1]

    def test_the_gate_uses_the_book_the_models_decide_on(self):
        block = _SCORER_SRC[_SCORER_SRC.index("ahead_unpriced: set = set()"):]
        block = block[:block.index("# Check for postponed")]
        assert "ODDS_API_BOOKMAKER" in block
        assert config.ODDS_API_BOOKMAKER == "draftkings"


class TestThePollerCanCreateAGame:
    """`odds` has an FK to `games`, and _insert_odds writes one batch."""

    def test_fetch_pregame_rows_upserts_the_games_it_sees(self):
        block = _ODDS_SRC[_ODDS_SRC.index("def fetch_pregame_rows"):]
        block = block[:block.index("\ndef ", 10)]
        assert "_upsert_games(conn, game_rows)" in block, (
            "the poller must be able to be the first writer to see a game; "
            "otherwise it waits for a refresh pass to create the row")

    def test_a_failed_upsert_drops_that_sports_odds_rather_than_the_tick(self):
        # One FK violation in a single-statement executemany takes down every
        # other sport's rows with it.
        block = _ODDS_SRC[_ODDS_SRC.index("def fetch_pregame_rows"):]
        block = block[:block.index("\ndef ", 10)]
        after = block[block.index("games upsert failed"):]
        assert "continue" in after

    def test_the_connection_it_opens_is_closed(self):
        # A 30-second loop leaking one connection per tick exhausts the pooler.
        block = _ODDS_SRC[_ODDS_SRC.index("def fetch_pregame_rows"):]
        block = block[:block.index("\ndef ", 10)]
        assert "conn.close()" in block


class TestProbablesReachTomorrow:
    """MLB game models fail closed without a starter, and probables stopped today."""

    def test_the_starter_guard_still_fails_closed(self):
        # The guard is what makes the widened window SAFE for MLB: a future
        # game with no named starter is skipped, not scored off a 0.00 ERA.
        # If this ever changes, the look-ahead becomes a way to fire picks on
        # absent data.
        assert 'if sport == "MLB" and (' in _SCORER_SRC
        assert 'features.get("home_starter_era") is None' in _SCORER_SRC

    def test_season_stats_are_fetched_once_not_once_per_date(self):
        # The two fetches are per-season and identical across the loop, and
        # they are the expensive part: a league-wide stat line plus a Savant
        # CSV. Per-date fetching turned an 8-day window into 8 of each.
        calls = {"mlb": 0, "savant": 0, "schedule": 0}

        from data.ingestors import mlb_stats_ingestor as ing

        def _fake_mlb(season):
            calls["mlb"] += 1
            return {"someone": {"era": 3.1, "player_id": 1}}

        def _fake_savant(season):
            calls["savant"] += 1
            return {}

        def _fake_rows(season, as_of, conn, season_stats=None):
            calls["schedule"] += 1
            assert season_stats is not None, \
                "the loop must hand the prefetched stats down"
            return []

        mp = pytest.MonkeyPatch()
        try:
            mp.setattr(ing, "_fetch_mlb_api_pitcher_stats", _fake_mlb)
            mp.setattr(ing, "_fetch_savant_pitcher_stats", _fake_savant)
            mp.setattr(ing, "_build_pitcher_rows", _fake_rows)
            mp.setattr(ing, "_upsert_pitcher_stats", lambda c, r: len(r))
            mp.setattr(ing, "get_connection", lambda: _FakeConn())
            ing.run_probables_refresh(days_ahead=7, season=2026, force=True)
        finally:
            mp.undo()

        assert calls["schedule"] == 8, "today plus seven days"
        assert calls["mlb"] == 1 and calls["savant"] == 1, calls

    def test_build_pitcher_rows_still_fetches_for_itself_when_not_given_stats(self):
        # The 6am path passes nothing and must keep working unchanged.
        import inspect
        from data.ingestors import mlb_stats_ingestor as ing
        sig = inspect.signature(ing._build_pitcher_rows)
        assert sig.parameters["season_stats"].default is None

    def test_a_fresh_window_skips_the_fetch(self):
        # Same self-limiting shape as injuries-refresh and weather-refresh:
        # the step runs on every pass but only opens a socket when stale.
        # ESPN has IP-blocked this worker twice.
        from data.ingestors import mlb_stats_ingestor as ing
        assert ing.PROBABLES_MAX_AGE_MIN > 0

    def test_unknown_freshness_counts_as_stale(self):
        # §7: a probe that cannot answer must not be able to switch the
        # refresh off.
        from data.ingestors import mlb_stats_ingestor as ing

        class _Boom:
            def execute(self, *a, **k):
                raise RuntimeError("no db")

        assert ing._probables_are_fresh(_Boom(), ["2026-09-07"]) is False

    def test_a_date_with_no_rows_is_stale(self):
        from data.ingestors import mlb_stats_ingestor as ing

        class _Conn:
            def execute(self, *a, **k):
                return self

            def fetchall(self):
                return [("2026-09-06",)]     # only one of the two asked for

        # 09-07 is missing entirely -> stale, even though 09-06 came back fresh.
        assert ing._probables_are_fresh(
            _Conn(), ["2026-09-06", "2026-09-07"]) is False
        assert ing._probables_are_fresh(_Conn(), ["2026-09-06"]) is True

    def test_the_age_comparison_happens_in_the_database(self):
        # THE BUG THIS PINS, caught in review before it shipped. `created_at`
        # is TEXT defaulted to `(now())::text`, so it holds UTC as
        # '2026-09-06 10:05:31.654854+00'. A cutoff from a naive local
        # `datetime.now().isoformat()` is both four hours off AND uses 'T'
        # where the column uses a space -- and 'T' > ' ' lexicographically, so
        # every row would have compared stale forever. The guard would have
        # run on all ~42 passes a day, which is the exact burn it exists to
        # prevent, while appearing to work.
        import inspect
        from data.ingestors import mlb_stats_ingestor as ing
        src = inspect.getsource(ing._probables_are_fresh)
        assert "created_at::timestamptz" in src
        assert "now() - (%s || ' minutes')::interval" in src
        # The docstring names the old expression, so look at the code only.
        body = src[src.index('"""', src.index('"""') + 3) + 3:]
        assert "datetime.now()" not in body, \
            "the cutoff must not be built in Python's clock"


class _FakeConn:
    def execute(self, *a, **k):
        return self

    def fetchall(self):
        return []

    def commit(self):
        pass

    def close(self):
        pass


class TestProbablesDoesNotExhaustThePool:
    """It opens its own connection, so it must not run in the parallel group.

    Shipped as `par probables-refresh` on 2026-09-06 and was the ninth
    concurrent connection against a Supabase session pool of FIFTEEN. Measured
    in production the same afternoon: EMAXCONNSESSION at 20:17Z and 22:40Z,
    and on the second failure it took `odds`, `prop-odds` and `health-check`
    with it — a step added to widen the board stopped the board being priced.

    The pass is not the place to discover how many sockets are already open.
    """

    def _pass_src(self):
        return (Path(__file__).parent.parent / "scripts" / "refresh_pass.sh"
                ).read_text(encoding="utf-8")

    def test_probables_runs_sequentially(self):
        src = self._pass_src()
        assert "step probables-refresh" in src
        assert "par probables-refresh" not in src, (
            "probables-refresh opens its own DB connection; running it in the "
            "parallel group exhausted the 15-connection session pool")

    def test_probables_still_precedes_scoring(self):
        # Ordering is load-bearing: MLB game models fail closed without a
        # starter, so a pass that scores before loading probables produces
        # nothing for the look-ahead window.
        src = self._pass_src()
        assert src.index("step probables-refresh") < src.index("step scoring")

    def test_probables_runs_after_the_parallel_group_completes(self):
        src = self._pass_src()
        assert src.index("par_wait") < src.index("step probables-refresh")
