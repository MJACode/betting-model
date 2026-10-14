"""Fail when `tsc --noEmit` reports a diagnostic the baseline does not list.

The baseline is a multiset of primary diagnostics with the line and column
removed (`file: error TSxxxx: message`). An existing diagnostic may move.
A new message, or another copy of a message already listed, is not in the
baseline and fails.

Usage: python3 scripts/check_tsc_baseline.py tsc.log tsc-baseline.txt
"""

from __future__ import annotations

import re
import sys
from collections import Counter

# Primary diagnostic only. Indented follow-ups and the "Found N errors" summary
# are not separate errors. Same lines the OTA typecheck step counts.
_DIAG = re.compile(
    r"^(?P<file>\S+\.tsx?)\((?P<line>\d+),(?P<col>\d+)\): error (?P<code>TS\d+): (?P<msg>.*)$"
)


def diagnostic_key(line: str) -> str | None:
    match = _DIAG.match(line.rstrip("\n"))
    if match is None:
        return None
    path = match.group("file").replace("\\", "/")
    return f"{path}: error {match.group('code')}: {match.group('msg')}"


def parse_log(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in text.splitlines():
        key = diagnostic_key(line)
        if key is not None:
            counts[key] += 1
    return counts


def parse_baseline(text: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        counts[stripped] += 1
    return counts


def unexpected(current: Counter[str], baseline: Counter[str]) -> list[str]:
    """Diagnostics in `current` that the baseline multiset does not cover."""
    extra: list[str] = []
    for key in sorted(current):
        over = current[key] - baseline.get(key, 0)
        if over > 0:
            extra.append(f"{over}x {key}")
    return extra


def log_is_compiler_failure(text: str, current: Counter[str]) -> bool:
    """A non-empty log with no diagnostic is tsc failing to run, not a clean compile."""
    return bool(text.strip()) and not current


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: python3 scripts/check_tsc_baseline.py tsc.log tsc-baseline.txt",
            file=sys.stderr,
        )
        return 2
    log_path, baseline_path = argv[1], argv[2]
    log_text = open(log_path, encoding="utf-8").read()
    baseline_text = open(baseline_path, encoding="utf-8").read()
    current = parse_log(log_text)
    baseline = parse_baseline(baseline_text)
    if log_is_compiler_failure(log_text, current):
        print("::error::tsc produced no diagnostics; the compiler did not run cleanly")
        sys.stdout.write(log_text if log_text.endswith("\n") else log_text + "\n")
        return 1
    extra = unexpected(current, baseline)
    print(
        f"tsc diagnostics: {sum(current.values())}  "
        f"baseline: {sum(baseline.values())}  "
        f"not in baseline: {sum(int(row.split('x ', 1)[0]) for row in extra)}"
    )
    if extra:
        print("::error::typecheck errors not in mobile/tsc-baseline.txt")
        print("\n".join(extra))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
