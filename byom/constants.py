"""Named constants for the NFL Build Your Own Model facts.

A fact is a win, a loss, or a push. The line is the last DraftKings
snapshot at or before game start. That label is stored on the row.
It is not a filter and it is not a reason to skip a game.
"""

# Shown on the row and on a screen. The wording is the label, not a
# check constraint.
LINE_BASIS = "DraftKings line at game start"

# player_prop_odds NFL coverage used by this builder starts 2023-09-01.
# Seasons before 2023 are refused. A 2023 game dated before that day is
# not built.
PROP_HISTORY_START_SEASON = 2023
PROP_HISTORY_START_DATE = "2023-09-01"

# Measured 2026-10-16: min(season) in nfl_odds_history for bookmaker
# 'draftkings' is 2020. games holds 2015-2019. Those seasons are not built.
DK_HISTORY_START_SEASON = 2020

# Measured 2026-10-29 on games joined to odds (bookmaker draftkings,
# market h2h/spreads/totals): season 2021 is the first NBA season with
# a DraftKings game line (1080 of 1080). Seasons 2019 and 2020 are in
# games and have zero of those rows. NBA season is the ending year, so
# 2021 is 2020-21. The in-progress season stays above this floor.
NBA_DK_HISTORY_START_SEASON = 2021

SPORT = "NFL"
