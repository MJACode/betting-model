"""scripts/mobile_ci_gate.py: tsc and verify scripts gated on NOTHING NEW and
NOTHING GONE.

Master carries known tsc errors and known-failing verify scripts, so PR CI
compares against committed baselines (mobile/ci/), as multisets. These pin
the comparison: line numbers never matter, a second copy of a known error IS
new, a new FAIL line inside an already-failing script IS new, a baseline
entry that stops occurring fails until it's removed, a broken tsc run never
reads as "all fixed", and a baseline can't grow vs origin/master unacked.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import mobile_ci_gate as gate  # noqa: E402

TSC_OUT = """\
src/lib/queries.ts(656,10): error TS2352: Conversion of type 'A' to type 'B' may be a mistake.
  Type 'A' is missing the following properties from type 'B': x, y
scripts/verify_x.ts(3,1): error TS2322: Type '"a"' is not assignable to type 'B'.
Found 2 errors.
"""


@pytest.fixture
def tree(tmp_path, monkeypatch):
    """A throwaway mobile/ tree: source files, baselines, and no git growth."""
    mobile = tmp_path / "mobile"
    (mobile / "src" / "lib").mkdir(parents=True)
    (mobile / "scripts").mkdir()
    q = ["// filler"] * 800
    q[655] = "return data as B;"            # line 656
    q[699] = "return other as B;"           # line 700
    (mobile / "src" / "lib" / "queries.ts").write_text("\n".join(q), encoding="utf-8")
    (mobile / "scripts" / "verify_x.ts").write_text("x\n" * 5, encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    monkeypatch.setattr(gate, "MOBILE", mobile)
    monkeypatch.setattr(gate, "CI", mobile / "ci")
    monkeypatch.setattr(gate, "TSC_BASELINE", mobile / "ci" / "tsc-baseline.txt")
    monkeypatch.setattr(gate, "VERIFY_BASELINE", mobile / "ci" / "verify-known-failing.txt")
    monkeypatch.setattr(gate, "baseline_growth", lambda path: ([], False))
    return mobile


def _baseline(path: Path, entries: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# header\n" + "".join(f"{e}\n" for e in entries), encoding="utf-8")


def _tsc(monkeypatch, rc, out):
    monkeypatch.setattr(gate, "run_tsc", lambda: (rc, out))


# ── fingerprints ────────────────────────────────────────────────────────────

def test_fingerprints_place_by_source_text_not_line_number(tree):
    assert gate.tsc_fingerprints(TSC_OUT) == [
        "src/lib/queries.ts: TS2352: Conversion of type 'A' to type 'B' may be a mistake."
        " @ return data as B;",
        "scripts/verify_x.ts: TS2322: Type '\"a\"' is not assignable to type 'B'. @ x",
    ]


def test_a_known_error_that_moved_lines_is_not_new(tree, monkeypatch):
    # An edit above it: the same source text is now on line 700's neighbour.
    q = (tree / "src" / "lib" / "queries.ts").read_text().splitlines()
    q.insert(0, "// a new import")
    (tree / "src" / "lib" / "queries.ts").write_text("\n".join(q))
    base = ["src/lib/queries.ts: TS2352: Conversion of type 'A' to type 'B' may be a mistake."
            " @ return data as B;"]
    _baseline(gate.TSC_BASELINE, base)
    _tsc(monkeypatch, 2, TSC_OUT.replace("(656,10)", "(657,10)").split("scripts/")[0])
    assert gate.gate_tsc(False) == 0


def test_a_second_copy_of_a_known_error_is_new(tree):
    base = gate.tsc_fingerprints(TSC_OUT)
    new, _ = gate.new_vs_baseline(base + [base[0]], base)
    assert new == [base[0]]


# ── tsc: a broken run is never "all fixed" ─────────────────────────────────

def test_tsc_nonzero_exit_with_nothing_parsed_fails(tree, monkeypatch, capsys):
    _baseline(gate.TSC_BASELINE, gate.tsc_fingerprints(TSC_OUT))
    _tsc(monkeypatch, 1, "Something went wrong\n")
    assert gate.gate_tsc(False) == 1
    assert "exited 1 with no parseable errors" in capsys.readouterr().out


def test_tsc_empty_output_with_nonzero_exit_fails(tree, monkeypatch, capsys):
    _tsc(monkeypatch, 2, "")
    assert gate.gate_tsc(False) == 1
    assert "no output" in capsys.readouterr().out


@pytest.mark.parametrize("how", ["output", "no npx"])
def test_tsc_not_found_fails(tree, monkeypatch, capsys, how):
    if how == "output":
        _tsc(monkeypatch, 127, "sh: 1: tsc: not found\n")
    else:
        def boom(*a, **k):
            raise FileNotFoundError("npx")
        monkeypatch.setattr(subprocess, "run", boom)
    assert gate.gate_tsc(False) == 1
    assert "tsc not found" in capsys.readouterr().out


def test_an_unparsed_error_ts_line_is_new(tree, monkeypatch, capsys):
    _baseline(gate.TSC_BASELINE, [])
    _tsc(monkeypatch, 1, "error TS5058: The specified path does not exist: 'tsconfig.json'.\n")
    assert gate.gate_tsc(False) == 1
    assert "NEW tsc error: (unparsed): error TS5058" in capsys.readouterr().out


# ── baseline entries that stop occurring ───────────────────────────────────

def test_a_fixed_tsc_error_fails_until_removed(tree, monkeypatch, capsys):
    base = gate.tsc_fingerprints(TSC_OUT)
    _baseline(gate.TSC_BASELINE, base)
    _tsc(monkeypatch, 2, TSC_OUT.split("scripts/")[0])     # the verify_x error is fixed
    assert gate.gate_tsc(False) == 1
    out = capsys.readouterr().out
    assert "baseline entry no longer occurs; remove it from mobile/ci/tsc-baseline.txt" in out
    assert base[1] in out


def test_a_now_passing_verify_entry_fails_until_removed(tree, monkeypatch, capsys):
    _baseline(gate.VERIFY_BASELINE, ["verify_x.ts: [FAIL] thing"])
    monkeypatch.setattr(gate, "run_verify", lambda s: (True, "[PASS] thing\n"))
    assert gate.gate_verify(False) == 1
    assert ("baseline entry no longer occurs; remove it from "
            "mobile/ci/verify-known-failing.txt: verify_x.ts: [FAIL] thing") \
        in capsys.readouterr().out


def test_a_swapped_duplicate_fails(tree, monkeypatch):
    # Two identical errors in queries.ts; the line-700 one is fixed and an
    # identical one appears elsewhere. Same (file, code, message) counts --
    # the old per-message multiset saw nothing.
    q = (tree / "src" / "lib" / "queries.ts").read_text().splitlines()
    q[99] = "return fresh as B;"            # line 100
    (tree / "src" / "lib" / "queries.ts").write_text("\n".join(q))
    err = "error TS2352: Conversion of type 'A' to type 'B' may be a mistake."
    before = f"src/lib/queries.ts(656,10): {err}\nsrc/lib/queries.ts(700,10): {err}\n"
    after = f"src/lib/queries.ts(656,10): {err}\nsrc/lib/queries.ts(100,10): {err}\n"
    _baseline(gate.TSC_BASELINE, gate.tsc_fingerprints(before))
    _tsc(monkeypatch, 2, after)
    assert gate.gate_tsc(False) == 1


# ── verify: FAIL lines inside a known-failing script ───────────────────────

KNOWN = "[PASS] a\n[FAIL] b — got 1\n[FAIL] c\n"


def test_a_new_fail_line_inside_a_known_failing_script_fails(tree, monkeypatch, capsys):
    # Reviewer's repro shape: verify_daily_results already failed, one more
    # FAIL line appeared, and the name-only gate exited 0.
    _baseline(gate.VERIFY_BASELINE, gate.verify_fingerprints("verify_x.ts", False, KNOWN))
    monkeypatch.setattr(gate, "run_verify",
                        lambda s: (False, KNOWN + "[FAIL] d — sorted wrong\n"))
    assert gate.gate_verify(False) == 1
    assert "NEW FAIL line: verify_x.ts: [FAIL] d — sorted wrong" in capsys.readouterr().out


def test_an_extra_copy_of_a_known_fail_line_fails(tree, monkeypatch):
    _baseline(gate.VERIFY_BASELINE, gate.verify_fingerprints("verify_x.ts", False, KNOWN))
    monkeypatch.setattr(gate, "run_verify", lambda s: (False, KNOWN + "[FAIL] c\n"))
    assert gate.gate_verify(False) == 1


def test_the_same_fail_lines_pass(tree, monkeypatch):
    _baseline(gate.VERIFY_BASELINE, gate.verify_fingerprints("verify_x.ts", False, KNOWN))
    monkeypatch.setattr(gate, "run_verify", lambda s: (False, KNOWN.replace("got 1", "got  1")))
    assert gate.gate_verify(False) == 0


def test_fail_line_formats_and_normalisation():
    out = (f"  FAIL  13 books — 14\n[FAIL] v @29212: pages\nFAIL: took 812ms\n"
           f"[FAIL] at {gate.ROOT}/mobile/x.ts\n[PASS] fine\nFAILED 3\n")
    assert gate.verify_fingerprints("v.ts", False, out) == [
        "v.ts: FAIL 13 books — 14", "v.ts: [FAIL] v @<offset>: pages",
        "v.ts: FAIL: took <n>ms", "v.ts: [FAIL] at <repo>/mobile/x.ts"]
    assert gate.verify_fingerprints("v.ts", False, "TypeError: boom\n\n(exit 1)") == [
        "v.ts: (exit 1, no FAIL line)"]
    assert gate.verify_fingerprints("v.ts", True, "[FAIL] ignored on exit 0") == []


# ── a baseline may not grow vs origin/master unacknowledged ────────────────

def test_a_grown_baseline_fails_without_the_ack(tree, monkeypatch, capsys):
    _baseline(gate.VERIFY_BASELINE, ["verify_x.ts: [FAIL] b"])
    monkeypatch.setattr(gate, "run_verify", lambda s: (False, "[FAIL] b\n"))
    monkeypatch.setattr(gate, "baseline_growth",
                        lambda path: (["verify_x.ts: [FAIL] b"], False))
    assert gate.gate_verify(False) == 1
    assert "MOBILE_CI_BASELINE_ACK=1" in capsys.readouterr().out
    monkeypatch.setattr(gate, "baseline_growth",
                        lambda path: (["verify_x.ts: [FAIL] b"], True))
    assert gate.gate_verify(False) == 0


def test_baseline_growth_reads_origin_master_and_the_ack(tree, monkeypatch):
    monkeypatch.undo()                        # the real baseline_growth, fake git
    monkeypatch.setattr(gate, "ROOT", tree.parent)
    path = tree / "ci" / "tsc-baseline.txt"
    _baseline(path, ["a", "a", "b"])
    log = {"msg": "fix\n"}

    def fake_git(*args):
        out = {"show": "# h\na\nb\n", "log": log["msg"]}.get(args[0], "")
        return subprocess.CompletedProcess(args, 0, out, "")
    monkeypatch.setattr(gate, "_git", fake_git)
    monkeypatch.delenv(gate.ACK_ENV, raising=False)
    assert gate.baseline_growth(path) == (["a"], False)
    log["msg"] = f"grow it {gate.ACK_TOKEN}\n"
    assert gate.baseline_growth(path) == (["a"], True)
    log["msg"] = "fix\n"
    monkeypatch.setenv(gate.ACK_ENV, "1")
    assert gate.baseline_growth(path) == (["a"], True)


def test_no_origin_master_fails_closed(tree, monkeypatch, capsys):
    _baseline(gate.VERIFY_BASELINE, [])
    monkeypatch.setattr(gate, "run_verify", lambda s: (True, ""))
    monkeypatch.setattr(gate, "baseline_growth", lambda path: (None, False))
    assert gate.gate_verify(False) == 1
    assert "origin/master not fetched" in capsys.readouterr().out


# ── the committed baselines ────────────────────────────────────────────────

def test_baselines_are_committed_and_name_real_scripts():
    known = gate._read_list(gate.VERIFY_BASELINE)
    assert known, "mobile/ci/verify-known-failing.txt is missing or empty"
    scripts = {p.name for p in gate.verify_scripts()}
    named = {k.split(": ", 1)[0] for k in known}
    assert named <= scripts, named - scripts
    assert gate._read_list(gate.TSC_BASELINE), "mobile/ci/tsc-baseline.txt is missing"


def test_ci_fetches_history_for_the_growth_check():
    wf = (ROOT / ".github" / "workflows" / "pr-ci.yml").read_text(encoding="utf-8")
    job = wf.split("mobile-typecheck-verify:", 1)[1]
    assert "fetch-depth: 0" in job
