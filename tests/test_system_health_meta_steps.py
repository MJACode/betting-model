"""refresh_pass_steps must ignore lifecycle sentinels, not just health-check.

Regression: run_ledger._abort_orphans writes failed_steps='aborted' when it
closes a run whose worker was replaced mid-pass (a deploy). That shares a column
with real step names, so without an exclusion every deploy makes the pipeline
report "aborted" as a failing step — observed live 2026-08-28.
"""
import re
from pathlib import Path


def _meta_steps() -> set[str]:
    src = Path("tracking/system_health.py").read_text(encoding="utf-8")
    m = re.search(r"_META_STEPS = \{([^}]*)\}", src)
    assert m, "_META_STEPS not found"
    return set(re.findall(r"\"([^\"]+)\"", m.group(1)))


def test_health_check_is_excluded():
    """It returns False on any CRIT, so counting it closes a self-sustaining loop."""
    assert "health-check" in _meta_steps()


def test_aborted_sentinel_is_excluded():
    """Written by _abort_orphans; a deploy is not a failing pipeline step."""
    assert "aborted" in _meta_steps()


def test_sentinel_matches_the_writer():
    """The excluded string must be exactly what run_ledger writes — if one side
    is renamed and the other is not, the alarm silently returns."""
    ledger = Path("tracking/run_ledger.py").read_text(encoding="utf-8")
    written = re.search(r"failed_steps\s*=\s*'([a-z]+)'", ledger)
    assert written, "run_ledger no longer writes a failed_steps sentinel"
    assert written.group(1) in _meta_steps()
