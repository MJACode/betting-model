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


def _as_et(today: date | datetime | None) -> date | datetime:
    if today is None:
        return datetime.now(_ET)
    if isinstance(today, datetime):
        if today.tzinfo is None:
            return today.replace(tzinfo=_ET)
        return today.astimezone(_ET)
    return today


def current_nfl_season(today: date | datetime | None = None) -> int:
    today = _as_et(today)
    year = today.year
    if today.month >= 9:
        return year
    return year - 1


def current_nba_season(today: date | datetime | None = None) -> int:
    """Ending year. October through December are next year's label.

    January through September stay on the calendar year, including the
    offseason, so a default of "current" does not jump to a season that
    has not tipped. 2026-10-29 is 2027. 2027-01-15 is 2027. 2026-09-01
    is 2026. The same rule is in byom_backtest when sport is NBA and
    season is null. data.ingestors.nba_stats_ingestor._nba_season_for_date
    is the same split.
    """
    today = _as_et(today)
    year = today.year
    if today.month >= 10:
        return year + 1
    return year
