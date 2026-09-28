"""scripts/mobile_ci_gate.py: tsc and verify scripts gated on NOTHING NEW.

Master carries known tsc errors and known-failing verify scripts, so PR CI
compares against committed baselines (mobile/ci/). These pin the comparison:
line numbers never matter, and a second copy of a known error IS new.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import mobile_ci_gate as gate  # noqa: E402

TSC_OUT = """\
src/lib/queries.ts(656,10): error TS2352: Conversion of type 'A' to type 'B' may be a mistake.
  Type 'A' is missing the following properties from type 'B': x, y
scripts/verify_x.ts(3,1): error TS2322: Type '"a"' is not assignable to type 'B'.
Found 2 errors.
"""


def test_fingerprints_drop_line_and_column_and_continuations():
    assert gate.tsc_fingerprints(TSC_OUT) == [
        "src/lib/queries.ts: TS2352: Conversion of type 'A' to type 'B' may be a mistake.",
        "scripts/verify_x.ts: TS2322: Type '\"a\"' is not assignable to type 'B'.",
    ]


def test_a_known_error_that_moved_lines_is_not_new():
    moved = TSC_OUT.replace("(656,10)", "(700,4)")
    new, gone = gate.new_vs_baseline(gate.tsc_fingerprints(moved),
                                     gate.tsc_fingerprints(TSC_OUT))
    assert new == [] and gone == []


def test_a_second_copy_of_a_known_error_is_new():
    base = gate.tsc_fingerprints(TSC_OUT)
    cur = base + [base[0]]
    new, _ = gate.new_vs_baseline(cur, base)
    assert new == [base[0]]


def test_a_fixed_error_is_reported_not_failed():
    base = gate.tsc_fingerprints(TSC_OUT)
    new, gone = gate.new_vs_baseline(base[:1], base)
    assert new == [] and gone == base[1:]


def test_baselines_are_committed_and_name_real_scripts():
    known = gate._read_list(gate.VERIFY_BASELINE)
    assert known, "mobile/ci/verify-known-failing.txt is missing or empty"
    scripts = {p.name for p in gate.verify_scripts()}
    assert set(known) <= scripts, set(known) - scripts
    assert gate._read_list(gate.TSC_BASELINE), "mobile/ci/tsc-baseline.txt is missing"
