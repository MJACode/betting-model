"""Today's card file, and removing it when a run finds nothing.

The wind and opener cards each write `data/cards/<prefix>_YYYY-MM-DD.csv` when
a run has bets, and scripts/nfl_wind_publisher.py reads that path on every
pass. Until 2026-09-20 a run with NO bets returned without touching the file,
so the publisher kept reading an earlier run's card for the rest of the day.

Measured 2026-09-20: the 15:40 UTC wind run forecast MIN @ CHI at 13.3 mph and
wrote the card; from 15:50 the forecast was 10.0 mph and every run printed "No
qualifying bets", while the publisher re-evaluated the 15:40 row (Under 47.5 at
-114) every ten minutes until kickoff. Nothing was bet only because the EV
floor dropped it. A row the model no longer produces must not still be on disk
for the publisher to bet at a price from an earlier read.

Removing the file retracts nothing: a pick already published is a row in
`picks`, locked insert-once, and the publisher never deletes.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

CARDS_DIR = Path("data/cards")


def card_path(prefix: str, now: datetime | None = None) -> Path:
    now = now or datetime.now(timezone.utc)
    return CARDS_DIR / f"{prefix}_{now:%Y-%m-%d}.csv"


def clear_card(prefix: str, now: datetime | None = None) -> bool:
    """Remove today's card for `prefix`. True when a file was removed."""
    p = card_path(prefix, now)
    if not p.exists():
        return False
    p.unlink()
    print(f"removed {p}: this run has no qualifying bets, and an earlier "
          f"run's card must not be published")
    return True
