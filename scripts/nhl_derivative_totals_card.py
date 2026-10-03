"""NHL derivative-totals card.

The backtest and this card share `models/nhl_derivative_totals`. A side is
publishable only by being named in that module's `PUBLISHED` tuple. The
walk-forward left the tuple empty (docs/nhl_derivative_totals.md), so this
card writes nothing and does not open a connection.

It is not a pipeline step. Wiring it into `run_pipeline.py` would publish a
side that did not clear.

    python -m scripts.nhl_derivative_totals_card
"""
from __future__ import annotations

import models.nhl_derivative_totals as dt


def run() -> int:
    """Return 0 and write nothing while nothing is published."""
    if not dt.PUBLISHED:
        print("PUBLISHED = () — nothing cleared, not publishing")
        return 0
    raise RuntimeError(
        "PUBLISHED names a side, and this card has no writer. Nothing was written."
    )


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
