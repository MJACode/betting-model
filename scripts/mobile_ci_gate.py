#!/usr/bin/env python3
"""
Mobile CI gate: `tsc --noEmit` and the mobile verify scripts, gated on
"nothing NEW", not on zero.

    python -m scripts.mobile_ci_gate tsc              # gate
    python -m scripts.mobile_ci_gate verify           # gate
    python -m scripts.mobile_ci_gate tsc --write      # refresh baseline
    python -m scripts.mobile_ci_gate verify --write   # refresh baseline

WHY A BASELINE. On master (2026-09-28, 14c39862) tsc reports 31 errors and 13
of the 54 verify scripts exit non-zero. Gating on zero would make every PR red
until all of that is fixed; not gating at all is how the 31 accumulated. So each
check compares against a COMMITTED baseline and fails only on something new:

  mobile/ci/tsc-baseline.txt          one line per known error, as
                                      "<file>: <TScode>: <first message line>"
                                      -- line/column dropped so an unrelated
                                      edit above an old error does not read
                                      as a new one. Duplicates are counted:
                                      a second copy of a known error IS new.
  mobile/ci/verify-known-failing.txt  one verify script file name per line.

A baseline entry that no longer fails is reported (so the baseline can shrink)
but never fails the build. A PR that fixes a known failure should delete its
line; a PR that adds one must justify it in review, because the diff shows it.

Needs `npm ci` in mobile/ first. No package.json change: tsc and tsx both come
from mobile's existing devDependencies (via npx).
"""

from __future__ import annotations

import argparse
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

_TSC_LINE = re.compile(r"^(?P<file>[^\s(][^(]*)\(\d+,\d+\): error (?P<code>TS\d+): (?P<msg>.*)$")


def _read_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.lstrip().startswith("#")]


def _write_list(path: Path, header: str, items: list[str]) -> None:
    CI.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "".join(f"{i}\n" for i in items), encoding="utf-8")


def tsc_fingerprints(output: str) -> list[str]:
    """Line/column-free fingerprints of every error in tsc's output."""
    out = []
    for ln in output.splitlines():
        m = _TSC_LINE.match(ln.rstrip())
        if m:
            out.append(f"{m['file'].replace(chr(92), '/')}: {m['code']}: {m['msg'].strip()}")
    return out


def new_vs_baseline(current: list[str], baseline: list[str]) -> tuple[list[str], list[str]]:
    """(new, gone) as multisets: a known error seen more often than baselined is new."""
    cur, base = Counter(current), Counter(baseline)
    new = sorted((cur - base).elements())
    gone = sorted((base - cur).elements())
    return new, gone


def run_tsc() -> str:
    r = subprocess.run(["npx", "--no-install", "tsc", "--noEmit", "--pretty", "false"],
                       cwd=MOBILE, capture_output=True, text=True)
    return (r.stdout or "") + (r.stderr or "")


def gate_tsc(write: bool) -> int:
    fps = tsc_fingerprints(run_tsc())
    if write:
        _write_list(TSC_BASELINE,
                    "# Known tsc errors on master (scripts/mobile_ci_gate.py). One per\n"
                    "# error, line/column dropped. Shrink this file; never grow it silently.\n",
                    sorted(fps))
        print(f"wrote {len(fps)} known tsc error(s) to {TSC_BASELINE.relative_to(ROOT)}")
        return 0
    new, gone = new_vs_baseline(fps, _read_list(TSC_BASELINE))
    print(f"tsc: {len(fps)} error(s); baseline {len(_read_list(TSC_BASELINE))}; "
          f"{len(new)} new, {len(gone)} fixed")
    for g in gone:
        print(f"  fixed (delete from baseline): {g}")
    for n in new:
        print(f"  NEW: {n}")
    return 1 if new else 0


def verify_scripts() -> list[Path]:
    return sorted((MOBILE / "scripts").glob("verify_*.ts"))


def run_verify(script: Path) -> tuple[bool, str]:
    try:
        r = subprocess.run(["npx", "--no-install", "tsx", str(script.relative_to(MOBILE))],
                           cwd=MOBILE, capture_output=True, text=True,
                           timeout=VERIFY_TIMEOUT_S)
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired as exc:
        return False, f"timed out after {VERIFY_TIMEOUT_S}s\n{exc.stdout or ''}"


def gate_verify(write: bool) -> int:
    known = set(_read_list(VERIFY_BASELINE))
    failing: list[str] = []
    new: list[tuple[str, str]] = []
    for script in verify_scripts():
        ok, out = run_verify(script)
        name = script.name
        print(f"[{'pass' if ok else 'FAIL'}] {name}{'  (known)' if not ok and name in known else ''}")
        if not ok:
            failing.append(name)
            if name not in known:
                new.append((name, out))
    if write:
        _write_list(VERIFY_BASELINE,
                    "# Verify scripts that already fail on master (scripts/mobile_ci_gate.py).\n"
                    "# Shrink this file; never grow it silently.\n",
                    sorted(failing))
        print(f"wrote {len(failing)} known-failing script(s) to "
              f"{VERIFY_BASELINE.relative_to(ROOT)}")
        return 0
    now_pass = sorted(known - set(failing))
    missing = sorted(k for k in known if not (MOBILE / "scripts" / k).exists())
    print(f"\nverify: {len(verify_scripts())} script(s); {len(failing)} failing; "
          f"{len(known)} known; {len(new)} new failure(s)")
    for k in now_pass:
        print(f"  now passes (delete from baseline): {k}"
              f"{' (script gone)' if k in missing else ''}")
    for name, out in new:
        print(f"\n===== NEW FAILURE: {name} =====\n{out[-4000:]}")
    return 1 if new else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("check", choices=("tsc", "verify"))
    ap.add_argument("--write", action="store_true", help="rewrite the baseline from this tree")
    a = ap.parse_args(argv)
    return gate_tsc(a.write) if a.check == "tsc" else gate_verify(a.write)


if __name__ == "__main__":
    raise SystemExit(main())
