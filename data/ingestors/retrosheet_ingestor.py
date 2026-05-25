"""
retrosheet_ingestor.py — Phase 2 of the live (in-play) betting build.

One-time backfill of Retrosheet play-by-play event files (free, 1918+) into a
new `plays` table. Each row = one play in a historical game, with the state
vector before the play (inning, outs, bases) and the resulting state +
final game outcome.

This is the training corpus for live win-probability models:

    P(home_win | state_vector, pitcher_features, batter_features)

Once trained, runtime scoring compares the model probability to the current DK
live-line implied probability and computes edge.

Status: SCAFFOLD — schema for `plays` not yet defined. Add to db_setup.py +
supabase_schema.sql before implementing.

Source
------
Retrosheet event files: https://www.retrosheet.org/game.htm
License: free for non-commercial use; attribution required ("The information
used here was obtained free of charge from and is copyrighted by Retrosheet").

Build sequence (Phase 2)
------------------------
    1. Add `plays` schema (game_id, inning, half_inning, outs_before,
       bases_before, score_diff_before, pitcher_id, batter_id, event_type,
       runs_on_play, outs_added, base_state_after).
    2. Download event files for target seasons (2008+ recommended — pre-2008
       has different runner-tracking conventions).
    3. Parse event-file syntax (RetroSheet uses a compact play notation: "S8/G"
       = single to CF on a grounder, etc.). Existing parsers: pybaseball has
       `retrosheet` helpers, or use the cwgame / cwevent C tools.
    4. Join each play to games.home_win to label.
    5. Write to plays table.

Critical files when implementing:
    - data/supabase_schema.sql        (add plays table)
    - data/db_setup.py SCHEMA_SQL     (add plays table for tests)
    - features/live_game_features.py  (state-vector feature builder)
    - models/trainer.py               (extend to support live WP target)
"""

# TODO(phase-2):
#   - download_retrosheet_event_files(start_year, end_year)
#   - parse_event_file(path) → list[Play]
#   - backfill_retrosheet(start_year=2008, end_year=2025) — idempotent, skip seasons already loaded
#   - Optional: pybaseball.retrosheet helpers may save building the parser from scratch
