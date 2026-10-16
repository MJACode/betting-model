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

# The declared job byom-nfl-game-facts-shop is enabled false and apply
# false, so a merge does not enqueue a writer. The owner turns it on by
# setting both. Once on, the cadence is daily, before prune-odds
# (run_pipeline step prune-odds, data/prune_odds.py). That prune deletes
# non-DraftKings rows from odds and player_prop_odds for games before
# today, keeping the opener and the close. It does not delete from
# nfl_odds_history. A lock quote that lives only in odds, and is neither
# the opener nor the close, is gone after the prune. The first apply has
# to land before this date: the 2026-10-17 prune of games dated 2026-10-16.
# Merging the migration only creates the empty table. The job warns when
# the America/New_York date is on or after this date and byom_lock_shop
# has no rows. A missing table counts as no rows. The warning does not
# write. The apply is a separate production write.
SHOP_FIRST_APPLY_BEFORE = "2026-10-17"
