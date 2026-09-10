"""The 2026-09-09 recap went out without the NFL.

WHAT HAPPENED. The 6am run on 2026-09-10 settled 2026-09-09 at 06:02 ET and
posted the recap to Discord and X seconds later: MLB 3-4, nothing else. The
three NFL prop BETs from NE @ SEA could not settle then -- they grade off
nfl_player_game_log, and the two steps that fill it (4b player stats, 4c prop
modelling data) ran AFTER settle, at 06:06 and 06:11. The 07:17 refresh pass
found "3 unsettled prop picks for 2026-09-09" and settled them at 07:24, an
hour after the recap had been ledgered, so nothing re-posted. mike: "nFL
results were missed."

Every other sport's box scores are ingested BEFORE settle for exactly this
reason (Step 0d MLB game logs, 0e WNBA, 0f NFL finals, 0g NCAAF finals). The
NFL player log was the one left on the wrong side of settle.

The recovery runs on the worker as a `publish_results` job -- both surfaces,
one job, seconds apart -- because the Discord webhook and the X credentials
live there and nowhere else (CLAUDE.md 1b).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from tracking import job_queue as jq  # noqa: E402

ROOT = Path(__file__).parent.parent
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")


def _daily():
    daily = PIPE[PIPE.index("def run_daily_pipeline("):]
    return daily[:daily.index("\ndef ")]


def test_nfl_box_scores_are_ingested_before_settle():
    """NFL prop picks settle off nfl_player_game_log. Both steps that fill it
    must run before Step 0 settle, or every NFL prop BET lags a full pass and
    the recap publishes without the sport."""
    daily = _daily()
    settle = daily.index('results["settle"]')
    assert daily.index('results["nfl_player_stats"]') < settle, (
        "NFL player stats must be ingested BEFORE settle")
    assert daily.index('results["nfl_props_data"]') < settle, (
        "NFL prop modelling data (the step that actually wrote the 09-09 "
        "box-score rows) must be ingested BEFORE settle")


def test_nfl_finals_still_precede_the_box_scores():
    """Step 0f fills games.home_score / away_score; the player-log steps key
    their rows on those games. Moving 4b/4c earlier must not leapfrog 0f."""
    daily = _daily()
    assert daily.index('results["nfl_results"]') < daily.index('results["nfl_props_data"]')


# ── the publish_results job ──────────────────────────────────────────────────

def _job_body():
    src = (ROOT / "tracking" / "job_queue.py").read_text(encoding="utf-8")
    i = src.index("def _job_publish_results(")
    return src[i:src.index("\ndef ", i + 10)]


def test_the_job_type_is_registered_and_validated():
    fn, validator = jq.JOBS["publish_results"]
    assert callable(fn) and callable(validator)


@pytest.mark.parametrize("bad", [{}, {"game_date": ""}, {"game_date": "nope"},
                                 {"game_date": "2026/09/09"}])
def test_a_malformed_date_is_refused_before_anything_runs(bad):
    with pytest.raises(ValueError):
        jq.JOBS["publish_results"][1](bad)


def test_the_job_posts_both_surfaces_through_the_ordinary_paths():
    """mike, 2026-09-02: the two surfaces "need to be the same and fired at
    the same time." One job, both notifiers, Discord first (its ledger row is
    the one X's free pick reads back), and neither guard bypassed: a date that
    is not over still posts nothing."""
    body = _job_body()
    assert "notify_discord_results(game_date)" in body
    assert "notify_x_results(game_date)" in body
    assert body.index("notify_discord_results(game_date)") < body.index(
        "notify_x_results(game_date)")
    code = body.split('"""')[-1]
    for bypass in ("datetime", "today", "force", "restate"):
        assert bypass not in code, f"the job manipulates {bypass}"


def test_the_job_only_clears_its_own_two_ledger_kinds():
    """A DELETE on push_sent that is not tightly scoped can silently un-post
    Discord signals, push notifications and the free pick."""
    body = _job_body()
    deletes = [seg for seg in body.split("DELETE FROM push_sent")[1:]]
    assert len(deletes) == 1, "one scoped DELETE, not one per guess"
    clause = deletes[0][:deletes[0].index("(keys")]
    assert "lock_key = ANY(%s)" in clause or "lock_key IN" in clause
    assert "kind IN ('discord_results', 'x_results')" in clause


def test_the_job_does_not_read_rowcount_off_the_cursor():
    code = "".join(l for l in _job_body().splitlines(keepends=True)
                   if not l.strip().startswith("#"))
    assert ").rowcount" not in code
