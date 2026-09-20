"""Season labels derived from a DATE, for the sports where the two disagree.

NHL seasons are labeled by their ENDING year (CLAUDE.md §4). Four call sites
derived that label with `year + 1 if month >= 10 else year`, which held while
every season opened in October. The 2026-27 regular season opens 2026-09-29
(`api-web.nhle.com/v1/schedule/2026-09-29` -> regularSeasonStartDate), so that
rule filed the 09-29 and 09-30 games under season 2026 and the rest of opening
week under 2027: one season split in two, and the September games joined to the
PREVIOUS season's final stats with `games_played = 82`, which the early-season
guard reads as a mid-season team.

September is never part of a finished season — the Cup is awarded in June —
with one exception that is a matter of record: the 2020 bubble playoffs ran
through 2020-09-28 and belong to season 2020.

Use this only where the source carries no season of its own. The NHL API does
(`season: 20262027`), and `parse_nhl_game` reads that first.
"""
from __future__ import annotations

# First month that belongs to the NEXT ending-year label.
NHL_NEW_SEASON_MONTH = 9


def nhl_season_label(game_date: str) -> int:
    """Ending-year season label for an ISO date (YYYY-MM-DD...)."""
    year, month = int(game_date[:4]), int(game_date[5:7])
    if year == 2020 and month == 9:
        return 2020          # bubble playoffs, Stanley Cup awarded 2020-09-28
    return year + 1 if month >= NHL_NEW_SEASON_MONTH else year
