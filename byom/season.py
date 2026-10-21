"""Which NFL season a date belongs to.

The label is the year the season starts. January and February belong to
the previous year's label. March through August are the offseason and
still name the season that just ended, so a default of "current" does
not jump to a year that has not kicked off.

byom_backtest copies this rule in SQL (month >= 9 keeps the year,
otherwise year - 1, America/New_York). tests/test_byom_backtest.py
checks the two against the same dates.
"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

_ET = ZoneInfo("America/New_York")


def current_nfl_season(today: date | datetime | None = None) -> int:
    if today is None:
        today = datetime.now(_ET)
    elif isinstance(today, datetime):
        if today.tzinfo is None:
            today = today.replace(tzinfo=_ET)
        else:
            today = today.astimezone(_ET)
    year = today.year
    if today.month >= 9:
        return year
    return year - 1
