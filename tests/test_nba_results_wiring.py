"""The NBA results step runs where settlement can use it.

NBA picks settle off games.home_score and nba_player_game_log. Nothing on the
worker wrote either until the nba-results step (2026-10-15), so its position is
the point: it must run on every refresh pass BEFORE settle, and in the daily
pipeline before Step 1 (settlement).
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")
PIPE = (ROOT / "run_pipeline.py").read_text(encoding="utf-8")


def _order(name: str) -> int:
    m = re.search(rf"^(?:step|par) {re.escape(name)}$", SH, re.M)
    assert m, f"step {name!r} is not in the refresh chain"
    return m.start()


def test_nba_results_runs_before_settle_on_every_pass():
    assert _order("nba-results") < _order("settle")
    # Not inside the hourly-only block: the evening passes are when NBA games
    # finish, and the step makes no ESPN call when nothing is pending.
    hourly = SH[SH.index('if [ "$MODE" = "hourly" ]; then'):]
    hourly = hourly[:hourly.index("\nfi")]
    assert not re.search(r"^\s*(?:step|par) nba-results\s*$", hourly, re.M)


def test_nba_results_is_waited_on_before_settle():
    """A parallel step must be collected by a par_wait before settle reads."""
    pos = _order("nba-results")
    between = SH[pos:_order("settle")]
    if SH[pos:pos + 3] == "par":
        assert re.search(r"^par_wait$", between, re.M), "no par_wait before settle"


def test_the_step_is_a_cli_choice_and_dispatches():
    assert '"nba-results"' in PIPE
    assert re.search(r'"nba-results":\s*lambda: step_nba_results\(run_date\)', PIPE)


def test_the_daily_pipeline_runs_it_before_settlement():
    daily = PIPE[PIPE.index("def run_daily_pipeline"):]
    call = daily.index('results["nba_results"] = step_nba_results(run_date)')
    settle = daily.index("step_settle(")
    assert call < settle
