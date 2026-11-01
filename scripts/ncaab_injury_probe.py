"""Are the two NCAAB injury pages reachable, and do they parse?

Runs on the worker, which has open egress. Writes nothing. Prints a status
line per source and a compact summary last, the same shape as
scripts/ncaab_feed_probe.py, so the job card shows the summary. A non-200
or a body that is not the report shape exits 1. Zero player rows is still
a successful reachability check: an empty report is a result, and the
polling job is what alerts on that during a game day.

    python -m scripts.ncaab_injury_probe
"""
from __future__ import annotations

import sys

from data.ingestors.ncaab_injury_feed import (
    COVERS_URL,
    ROTOWIRE_URL,
    ParseError,
    fetch_url,
    parse_covers,
    parse_rotowire,
)

SUMMARY_MARK = "== SUMMARY =="
_SOURCES = (("rotowire", ROTOWIRE_URL, parse_rotowire),
            ("covers", COVERS_URL, parse_covers))


def _install() -> None:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-injury-probe")
    except Exception:  # noqa: BLE001
        pass


def probe(fetch=fetch_url) -> int:
    """Print one line per source. Return 0 only when both parse."""
    summaries = []
    failed = False
    for name, url, parser in _SOURCES:
        fetched = fetch(url)
        if fetched.error or fetched.status != 200:
            why = fetched.error or f"HTTP {fetched.status}"
            print(f"{name}: {why}")
            summaries.append(f"{name}: {why}")
            failed = True
            continue
        try:
            rows = parser(fetched.body)
        except ParseError as exc:
            print(f"{name}: HTTP {fetched.status}, {len(fetched.body):,} bytes, parse error ({exc})")
            summaries.append(f"{name}: HTTP {fetched.status} parse error")
            failed = True
            continue
        print(f"{name}: HTTP {fetched.status}, {len(fetched.body):,} bytes, {len(rows)} players")
        summaries.append(f"{name}: HTTP {fetched.status}, {len(rows)} players")
    print(SUMMARY_MARK)
    for line in summaries:
        print(line)
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    _install()
    return probe()


if __name__ == "__main__":
    sys.exit(main())
