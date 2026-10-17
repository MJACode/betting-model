"""Named constants for the NFL Build Your Own Model facts.

A fact is a win, a loss, or a push. The line is the last DraftKings
snapshot at or before game start. That label is stored on the row.
It is not a filter and it is not a reason to skip a game.
"""

# Shown on the row and on a screen. The wording is the label, not a
# check constraint.
LINE_BASIS = "DraftKings line at game start"

# Measured 2026-10-16: min(season) in nfl_odds_history for bookmaker
# 'draftkings' is 2020. games holds 2015-2019. Those seasons are not built.
DK_HISTORY_START_SEASON = 2020

SPORT = "NFL"
