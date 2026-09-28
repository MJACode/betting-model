#!/usr/bin/env python3
"""
Mobile CI gate: `tsc --noEmit` and the mobile verify scripts, gated on
"nothing NEW, nothing GONE", not on zero.

    python -m scripts.mobile_ci_gate tsc              # gate
    python -m scripts.mobile_ci_gate verify           # gate
    python -m scripts.mobile_ci_gate tsc --write      # refresh baseline
    python -m scripts.mobile_ci_gate verify --write   # refresh baseline

WHY A BASELINE. On master (2026-09-28, 14c39862) tsc reports 31 errors and 13
of the 54 verify scripts exit non-zero. Gating on zero would make every PR red
until all of that is fixed; not gating at all is how the 31 accumulated. So each
check compares against a COMMITTED baseline, as a multiset:

  mobile/ci/tsc-baseline.txt          one line per known error, as
                                      "<file>: <TScode>: <first message line>
                                      @ <source line text>". The source text,
                                      not the line number, places the error:
                                      an edit above it doesn't move it, but a
                                      fixed copy swapped for a new identical
                                      one elsewhere in the file does show.
  mobile/ci/verify-known-failing.txt  one line per [FAIL] line a failing
                                      verify script prints, as
                                      "<script>: <FAIL line>" (repo paths, ms
                                      timings, @<source offset> normalised). A failing script
                                      with no FAIL line is recorded as
                                      "<script>: (exit N, no FAIL line)".

THE GATE FAILS ON:
  * any entry seen more often than baselined (a new tsc error, a new or extra
    FAIL line inside an already-failing script, a newly failing script);
  * any baseline entry that no longer occurs -- remove it from the baseline in
    the same PR, so a fix can't later regress unseen;
  * tsc missing, or exiting non-zero with nothing parsed, or printing an
    `error TS` line it can't parse (TS5058 and friends count as new);
  * a baseline that GREW relative to origin/master, unless acknowledged:
    MOBILE_CI_BASELINE_ACK=1 in the environment, or the token
    [mobile-baseline-ack] in a commit message in origin/master..HEAD. CI needs
    origin/master and the PR's commits for this (checkout fetch-depth: 0).

Needs `npm ci` in mobile/ first. No package.json change: tsc and tsx both come
from mobile's existing devDependencies (via npx).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
CI = MOBILE / "ci"
TSC_BASELINE = CI / "tsc-baseline.txt"
VERIFY_BASELINE = CI / "verify-known-failing.txt"
VERIFY_TIMEOUT_S = 180
ACK_ENV = "MOBILE_CI_BASELINE_ACK"
ACK_TOKEN = "[mobile-baseline-ack]"

_TSC_LINE = re.compile(r"^(?P<file>[^\s(][^(]*)\((?P<line>\d+),\d+\): error (?P<code>TS\d+): (?P<msg>.*)$")
_TSC_MISSING = re.compile(r"tsc: not found|command not found|could not determine executable",
                          re.IGNORECASE)
_FAIL_LINE = re.compile(r"^\s*\[?FAIL\]?(?=[\s:])")


def _read_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return _parse_list(path.read_text(encoding="utf-8"))


def _parse_list(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _write_list(path: Path, header: str, items: list[str]) -> None:
    CI.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "".join(f"{i}\n" for i in items), encoding="utf-8")


def _source_line(file: str, line: int) -> str:
    try:
        lines = (MOBILE / file).read_text(encoding="utf-8").splitlines()
        return " ".join(lines[line - 1].split())
    except (OSError, IndexError):
        return "?"


def tsc_fingerprints(output: str) -> list[str]:
    """Line-number-free fingerprints of every error in tsc's output. An
    `error TS` line that doesn't parse is kept whole, so it can only be new."""
    out = []
    for ln in output.splitlines():
        m = _TSC_LINE.match(ln.rstrip())
        if m:
            f = m["file"].replace(chr(92), "/")
            out.append(f"{f}: {m['code']}: {m['msg'].strip()} @ "
                       f"{_source_line(f, int(m['line']))}")
        elif "error TS" in ln:
            out.append(f"(unparsed): {ln.strip()}")
    return out


def new_vs_baseline(current: list[str], baseline: list[str]) -> tuple[list[str], list[str]]:
    """(new, gone) as multisets: a known entry seen more often than baselined is new."""
    cur, base = Counter(current), Counter(baseline)
    new = sorted((cur - base).elements())
    gone = sorted((base - cur).elements())
    return new, gone


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def baseline_growth(path: Path) -> tuple[list[str] | None, bool]:
    """(entries added vs origin/master, acknowledged). None = can't compare."""
    rel = path.relative_to(ROOT).as_posix()
    if _git("rev-parse", "--verify", "-q", "origin/master").returncode:
        return None, False
    shown = _git("show", f"origin/master:{rel}")
    master = _parse_list(shown.stdout) if shown.returncode == 0 else []
    grown = sorted((Counter(_read_list(path)) - Counter(master)).elements())
    acked = os.environ.get(ACK_ENV) == "1" or \
        ACK_TOKEN in _git("log", "--format=%B", "origin/master..HEAD").stdout
    return grown, acked


def _report(label: str, baseline: Path, new: list[str], gone: list[str]) -> int:
    rel = baseline.relative_to(ROOT).as_posix()
    for g in gone:
        print(f"  baseline entry no longer occurs; remove it from {rel}: {g}")
    for n in new:
        print(f"  NEW {label}: {n}")
    grown, acked = baseline_growth(baseline)
    bad = bool(new or gone)
    if grown is None:
        print(f"  cannot check {rel} for growth: origin/master not fetched "
              f"(git fetch origin master)")
        bad = True
    elif grown:
        print(f"  {rel} grew by {len(grown)} entr{'y' if len(grown) == 1 else 'ies'} "
              f"vs origin/master{' (acknowledged)' if acked else ''}:")
        for g in grown:
            print(f"    + {g}")
        if not acked:
            print(f"  a baseline may only grow with {ACK_ENV}=1 or {ACK_TOKEN} "
                  f"in a commit message, explained in the PR")
            bad = True
    return 1 if bad else 0


def run_tsc() -> tuple[int, str]:
    try:
        r = subprocess.run(["npx", "--no-install", "tsc", "--noEmit", "--pretty", "false"],
                           cwd=MOBILE, capture_output=True, text=True)
    except FileNotFoundError as exc:
        return 127, f"tsc: not found ({exc})"
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def gate_tsc(write: bool) -> int:
    rc, out = run_tsc()
    fps = tsc_fingerprints(out)
    broken = ""
    if _TSC_MISSING.search(out) or rc == 127:
        broken = "tsc not found (run `npm ci` in mobile/)"
    elif rc != 0 and not fps:
        broken = (f"tsc exited {rc} with no parseable errors"
                  f"{' and no output' if not out.strip() else ''}")
    if broken:
        print(f"tsc: FAILED -- {broken}\n{out[-4000:]}")
        return 1
    if write:
        _write_list(TSC_BASELINE,
                    "# Known tsc errors on master (scripts/mobile_ci_gate.py). One per\n"
                    "# error, placed by source text. Shrink this file; never grow it silently.\n",
                    sorted(fps))
        print(f"wrote {len(fps)} known tsc error(s) to {TSC_BASELINE.relative_to(ROOT)}")
        return 0
    base = _read_list(TSC_BASELINE)
    new, gone = new_vs_baseline(fps, base)
    print(f"tsc: exit {rc}, {len(fps)} error(s); baseline {len(base)}; "
          f"{len(new)} new, {len(gone)} gone")
    return _report("tsc error", TSC_BASELINE, new, gone)


def verify_scripts() -> list[Path]:
    return sorted((MOBILE / "scripts").glob("verify_*.ts"))


def run_verify(script: Path) -> tuple[bool, str]:
    try:
        r = subprocess.run(["npx", "--no-install", "tsx", str(script.relative_to(MOBILE))],
                           cwd=MOBILE, capture_output=True, text=True,
                           timeout=VERIFY_TIMEOUT_S)
        out = (r.stdout or "") + (r.stderr or "")
        return r.returncode == 0, out if r.returncode == 0 else f"{out}\n(exit {r.returncode})"
    except subprocess.TimeoutExpired as exc:
        return False, f"timed out after {VERIFY_TIMEOUT_S}s\n{exc.stdout or ''}"


def _normalise(line: str) -> str:
    line = line.replace(str(ROOT), "<repo>")
    line = re.sub(r"\b\d+(?:\.\d+)?\s?ms\b", "<n>ms", line)
    line = re.sub(r"@\d+\b", "@<offset>", line)      # source offsets (verify_row_cap)
    return " ".join(line.split())


def verify_fingerprints(name: str, ok: bool, out: str) -> list[str]:
    """The failing script's FAIL lines, as baseline entries (none if it passed)."""
    if ok:
        return []
    fails = [f"{name}: {_normalise(ln)}" for ln in out.splitlines() if _FAIL_LINE.match(ln)]
    if fails:
        return fails
    m = re.search(r"\(exit (\d+)\)\s*$", out)
    why = "timed out" if out.startswith("timed out") else f"exit {m[1] if m else '?'}"
    return [f"{name}: ({why}, no FAIL line)"]


def gate_verify(write: bool) -> int:
    known = _read_list(VERIFY_BASELINE)
    known_scripts = {k.split(": ", 1)[0] for k in known}
    entries: list[str] = []
    outputs: dict[str, str] = {}
    scripts = verify_scripts()
    for script in scripts:
        ok, out = run_verify(script)
        name = script.name
        print(f"[{'pass' if ok else 'FAIL'}] {name}"
              f"{'  (known)' if not ok and name in known_scripts else ''}")
        entries += verify_fingerprints(name, ok, out)
        outputs[name] = out
    if write:
        _write_list(VERIFY_BASELINE,
                    "# FAIL lines of the verify scripts that already fail on master\n"
                    "# (scripts/mobile_ci_gate.py). Shrink this file; never grow it silently.\n",
                    sorted(entries))
        print(f"wrote {len(entries)} known FAIL line(s) to "
              f"{VERIFY_BASELINE.relative_to(ROOT)}")
        return 0
    new, gone = new_vs_baseline(entries, known)
    failing = {e.split(": ", 1)[0] for e in entries}
    print(f"\nverify: {len(scripts)} script(s); {len(failing)} failing; "
          f"{len(entries)} FAIL line(s) vs {len(known)} baselined; "
          f"{len(new)} new, {len(gone)} gone")
    rc = _report("FAIL line", VERIFY_BASELINE, new, gone)
    for name in sorted({n.split(": ", 1)[0] for n in new}):
        print(f"\n===== {name} (new FAIL lines) =====\n{outputs.get(name, '')[-4000:]}")
    return rc


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("check", choices=("tsc", "verify"))
    ap.add_argument("--write", action="store_true", help="rewrite the baseline from this tree")
    a = ap.parse_args(argv)
    return gate_tsc(a.write) if a.check == "tsc" else gate_verify(a.write)


if __name__ == "__main__":
    raise SystemExit(main())
