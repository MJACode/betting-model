"""Scheduler entry for the NCAAB pre-tip injury feed.

The tick lives in data/ingestors/ncaab_injury_feed.py. This wrapper is what
the scheduler launches, so the HTTP calls show up on the live monitor.
"""
from __future__ import annotations

import sys


def _install() -> None:
    try:
        from monitoring.probe import install as _install_api_probe
        _install_api_probe("ncaab-injury-feed")
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    _install()
    from data.ingestors.ncaab_injury_feed import main as run
    return run()


if __name__ == "__main__":
    sys.exit(main())
