"""Named constants for the NFL Build Your Own Model facts.

The two lock windows are UNCONFIRMED placeholders. They are not a measured
cut and they are not check constraints. The row records the window that
built it, so a later number does not need a migration.
"""

# UNCONFIRMED. The grade lock is the first DraftKings pre-game snapshot at
# or under this many hours before kickoff.
LOCK_WINDOW_HOURS = 120

# UNCONFIRMED. A second snapshot, captured the same way. It is stored and
# it is not the grade.
NEAR_LOCK_WINDOW_HOURS = 24

# Measured 2026-10-16: min(season) in nfl_odds_history for bookmaker
# 'draftkings' is 2020. games holds 2015-2019. Those seasons are not built.
DK_HISTORY_START_SEASON = 2020

SOURCE_HISTORY = "nfl_odds_history"
SOURCE_ODDS = "odds"
SPORT = "NFL"

# How far before the DraftKings lock a book's own quote may be and still
# be stored as reference next to that lock. It is not the grade. The grade
# is DraftKings' own price on the lock snapshot. Not a spread, price, or
# line filter.
SHOP_LAG_MINUTES = 30
