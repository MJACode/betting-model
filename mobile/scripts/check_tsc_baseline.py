"""Fail when `tsc --noEmit` reports a diagnostic the PR baseline does not list.

PR CI is stricter than the OTA Typecheck step on purpose. `mobile-ota.yml`
ignores `src/lib/queries.ts` and every `scripts/` file: the harnesses are not
in the bundle, and the queries.ts casts are the tolerated publish baseline.
An error in a screen still blocks Publish. This gate catches that, and it
also catches a new diagnostic inside `queries.ts`, which OTA would ignore.

Keys (line and column are never part of the key):

  * `scripts/`: file and TS code only. The message names the type shape, so a
    new field on Pick, ParlayLeg, or TrackRecordSummary rewrites it and must
    not fail an unrelated PR. A new file, a new code, or another copy of the
    same code still fails.
  * Everything else, including `src/`: file, TS code, and message. Another
    copy, or the same code with a different message, fails.

A baseline entry tsc no longer reports is a warning (`::warning::`), not a
failure. Delete it in the same PR. A fixed diagnostic can otherwise return
unseen.

#846 (open) is a different mechanism: `mobile/ci/tsc-baseline.txt` and
`scripts/mobile_ci_gate.py`. That gate also runs the verify scripts, places
each error by source text, and fails when an entry disappears. This script
does not read `mobile/ci/tsc-baseline.txt`.

Usage:
  python scripts/check_tsc_baseline.py tsc.log tsc-baseline.txt
  python scripts/check_tsc_baseline.py --write tsc.log tsc-baseline.txt
"""

from __future__ import annotations

import re
import sys
from collections import Counter

HEADER = """\
# Known `npx tsc --noEmit` diagnostics for the PR CI gate.
# Regenerate with: python scripts/check_tsc_baseline.py --write tsc.log tsc-baseline.txt
# Do not hand-edit. Line and column are omitted.
#
# PR CI is stricter than the OTA Typecheck step on purpose.
# mobile-ota.yml ignores src/lib/queries.ts and every scripts/ file: scripts
# are not in the bundle, and the queries.ts casts are the tolerated baseline.
# An error in a screen still blocks Publish. PR CI must catch that, and it
# must also catch a new diagnostic inside queries.ts, which OTA would ignore.
#
# Keys:
#   src/ and any other non-scripts file: file, TS code, and message.
#     Another copy, or the same code with a different message, fails.
#   scripts/: file and TS code only. The message names the type shape, so a
#     new field on Pick, ParlayLeg, or TrackRecordSummary rewrites it and
#     must not fail an unrelated PR. A new file, a new code, or another copy
#     of the same code still fails.
#
# A baseline entry tsc no longer reports is a warning (::warning::), not a
# failure. Delete it in the same PR. A fixed diagnostic can otherwise return
# unseen.
#
# #846 (open) is a different mechanism: mobile/ci/tsc-baseline.txt and
# scripts/mobile_ci_gate.py. That gate also runs the verify scripts, places
# each error by source text, and fails when an entry disappears. This file
# is not that baseline. This gate does not read mobile/ci/tsc-baseline.txt.
"""

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
    code = match.group("code")
    # scripts/: file and TS code only. The message embeds the type shape.
    if path.startswith("scripts/"):
        return f"{path} {code}"
    return f"{path} {code} {match.group('msg').strip()}"


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


def stale(current: Counter[str], baseline: Counter[str]) -> list[str]:
    """Baseline entries tsc no longer reports. Warning only."""
    gone: list[str] = []
    for key in sorted(baseline):
        over = baseline[key] - current.get(key, 0)
        if over > 0:
            gone.append(f"{over}x {key}")
    return gone


def log_is_compiler_failure(text: str, current: Counter[str]) -> bool:
    """A non-empty log with no diagnostic is tsc failing to run, not a clean compile."""
    return bool(text.strip()) and not current


def render_baseline(current: Counter[str]) -> str:
    lines = [key for key in sorted(current) for _ in range(current[key])]
    body = "\n".join(lines)
    if body:
        body += "\n"
    return HEADER + body


def main(argv: list[str]) -> int:
    args = argv[1:]
    write = False
    if args and args[0] == "--write":
        write = True
        args = args[1:]
    if len(args) != 2:
        print(
            "usage: python scripts/check_tsc_baseline.py [--write] tsc.log tsc-baseline.txt",
            file=sys.stderr,
        )
        return 2
    log_path, baseline_path = args
    log_text = open(log_path, encoding="utf-8").read()
    current = parse_log(log_text)
    if log_is_compiler_failure(log_text, current):
        print("::error::tsc produced no diagnostics; the compiler did not run cleanly")
        sys.stdout.write(log_text if log_text.endswith("\n") else log_text + "\n")
        return 1
    if write:
        open(baseline_path, "w", encoding="utf-8").write(render_baseline(current))
        print(f"wrote {sum(current.values())} diagnostics to {baseline_path}")
        return 0
    baseline_text = open(baseline_path, encoding="utf-8").read()
    baseline = parse_baseline(baseline_text)
    extra = unexpected(current, baseline)
    gone = stale(current, baseline)
    print(
        f"tsc diagnostics: {sum(current.values())}  "
        f"baseline: {sum(baseline.values())}  "
        f"not in baseline: {sum(int(row.split('x ', 1)[0]) for row in extra)}  "
        f"stale: {sum(int(row.split('x ', 1)[0]) for row in gone)}"
    )
    for row in gone:
        print(f"::warning::stale baseline entry no longer reported: {row}")
    if extra:
        print("::error::typecheck errors not in mobile/tsc-baseline.txt")
        print("\n".join(extra))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
