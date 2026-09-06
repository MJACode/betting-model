"""
The refresh pass runs its independent steps concurrently — without losing a
failure, and without breaking the orderings that are load-bearing.

The pass took ~12 minutes against a 10-minute evening tick, so 18 passes ran in
a 5-hour window instead of 30 and the rest were silently skipped. mike:
"we absolutely need to get the 12 minutes down."

Nothing in the pass is CPU-bound — the worker peaks at 1.1GB of 8GB and 1.4 of
8 CPUs. Every slow step waits on a socket. That is also why more Railway
workers would not have helped: a second machine does not make a socket answer
faster.

TWO THINGS COULD GO WRONG, and both are tested here.

  1. A FAILURE GOES MISSING. A background job runs in a subshell and cannot
     append to the parent's FAILED_STEPS array, so a naive `step ... &` would
     report every pass as clean. That is precisely the blindness the run ledger
     was built to end, and it would be worse than the slow pass.

  2. AN ORDERING BREAKS. Scoring must read the ingests, settle must follow the
     results ingests, opening-signals must follow every scorer. Those comments
     in refresh_pass.sh are load-bearing; parallelising across one of them
     would produce a quietly wrong board rather than an error.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SH = (ROOT / "scripts" / "refresh_pass.sh").read_text(encoding="utf-8")


def _order(name: str) -> int:
    """Position of a step invocation in the chain, however it is invoked."""
    m = re.search(rf"^(?:step|par) {re.escape(name)}$", SH, re.M)
    assert m, f"step {name!r} is not in the chain"
    return m.start()


# ── a failure must survive the subshell ───────────────────────────────────────

@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_a_parallel_step_that_fails_is_still_recorded():
    """
    The bug this guards: `cmd &` runs in a subshell, so FAILED_STEPS+=() inside
    it mutates a copy that dies with the subshell. Every pass would report
    clean. The marker-file collection in par_wait is what makes it real, and
    this runs the SHIPPED functions rather than a paraphrase of them.
    """
    with tempfile.TemporaryDirectory() as tmp:
        fake = Path(tmp) / "fake_step.sh"
        fake.write_text('#!/usr/bin/env bash\ncase "$1" in BAD-*) exit 1;; *) exit 0;; esac\n')
        fake.chmod(0o755)

        # POSIX paths, and the stub run THROUGH bash. This harness feeds
        # paths into a bash string, and on Windows -- where this repo's only
        # quality gate is actually run (section 7) -- a native path arrives
        # with backslashes, which bash eats as escapes. sed was handed a path
        # that did not exist, printed nothing, and `eval ""` defined no par()
        # at all: the harness reported TOTAL=0 and the test failed for a
        # reason with nothing to do with the pass it guards. Running the stub
        # via `bash` also drops the dependency on an exec bit that a Windows
        # filesystem does not carry.
        sh_path = (ROOT / "scripts" / "refresh_pass.sh").as_posix()
        fake_sh = fake.as_posix()
        harness = f'''
set -uo pipefail
FAILED_STEPS=()
STEPS_TOTAL=0
PAR_DIR="$(mktemp -d)"
trap 'rm -rf "$PAR_DIR"' EXIT
eval "$(sed -n '/^par() {{/,/^}}/p' "{sh_path}" \
        | sed 's|python run_pipeline.py --step "$1"|bash "{fake_sh}" "$1"|')"
eval "$(sed -n '/^par_wait() {{/,/^}}/p' "{sh_path}")"
par ok-one
par BAD-one
par ok-two
par BAD-two
par_wait
echo "TOTAL=$STEPS_TOTAL"
echo "FAILED=${{FAILED_STEPS[*]:-none}}"
'''
        r = subprocess.run(["bash", "-c", harness], capture_output=True, text=True)
        out = r.stdout
        assert "TOTAL=4" in out, f"steps miscounted: {out!r}"
        assert "BAD-one" in out and "BAD-two" in out, (
            f"a parallel failure went missing — this is the whole bug: {out!r}")
        assert "ok-one" not in out.split("FAILED=")[1], "a passing step reported failed"


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_the_script_is_syntactically_valid():
    r = subprocess.run(["bash", "-n", str(ROOT / "scripts" / "refresh_pass.sh")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_no_sequential_step_runs_while_a_parallel_group_is_open():
    """
    An unwaited group lets the next step read half-written ingests — a quietly
    wrong board, which is worse than a slow one.

    The first version of this test walked the file and asserted only the FINAL
    state, so deleting a par_wait in the MIDDLE passed cleanly: a later group's
    wait reset the flag. It has to be checked at every `step`, not at the end.
    """
    open_group = []
    for i, raw in enumerate(SH.splitlines(), 1):
        ln = raw.strip()
        if ln == "par_wait":
            open_group.clear()
        elif ln.startswith("par ") :
            open_group.append(ln.split()[1])
        elif ln.startswith("step "):
            assert not open_group, (
                f"line {i}: `{ln}` runs while {open_group} are still in "
                f"flight — it may read half-written data")
    assert not open_group, (
        f"the pass ends with {open_group} never waited on")


def test_par_and_par_wait_both_exist_and_par_counts_the_step():
    assert "\npar() {" in SH and "\npar_wait() {" in SH
    par_body = SH[SH.index("\npar() {"):SH.index("\npar_wait() {")]
    assert "STEPS_TOTAL=$((STEPS_TOTAL + 1))" in par_body, (
        "a parallel step must still count toward the pass total")
    assert ".failed" in par_body, "no marker file — the failure cannot escape"


# ── the orderings that must not be parallelised across ────────────────────────

def test_scoring_follows_every_ingest():
    """Fresher inputs landing after the scorer would be pure cost."""
    for ingest in ("odds", "prop-odds", "lineups", "injuries-refresh",
                   "weather-refresh", "public-betting"):
        assert _order(ingest) < _order("scoring"), f"{ingest} must precede scoring"


def test_settle_follows_every_results_ingest():
    """Otherwise there is nothing new for it to grade."""
    for res in ("game-log-today", "nfl-results", "nhl-results", "ufc-results-poll"):
        assert _order(res) < _order("settle")


def test_opening_signals_follows_every_scorer():
    for scorer in ("scoring", "prop-scoring", "wnba-prop-scoring",
                   "nba-prop-scoring", "golf-scoring"):
        assert _order(scorer) < _order("opening-signals")


def test_parlay_follows_opening_signals():
    """It reads the locked legs."""
    assert _order("opening-signals") < _order("parlay-track-record")


def test_the_scorers_stay_sequential():
    """
    They share the picks table AND the same look-ahead delete window.
    Concurrent deletes over overlapping windows is exactly how a board gets
    emptied (§7), and the measured cost of running them in series is ~25s —
    not worth the risk.
    """
    for scorer in ("scoring", "prop-scoring", "wnba-prop-scoring",
                   "nba-prop-scoring"):
        assert re.search(rf"^step {re.escape(scorer)}$", SH, re.M), (
            f"{scorer} must be sequential, not parallel")


def test_view_migrations_run_first_and_alone():
    """A schema fix must land before anything reads the schema."""
    assert _order("apply-view-migrations") < _order("odds")
    assert re.search(r"^step apply-view-migrations$", SH, re.M)
