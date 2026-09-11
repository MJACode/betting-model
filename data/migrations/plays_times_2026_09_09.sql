-- plays.start_time / plays.end_time (2026-09-09)
--
-- Clock time of each plate appearance from the MLB Stats API
-- (about.startTime / about.endTime, ISO UTC). The ingestor always had these
-- fields in hand and dropped them; they are what lets a play be aligned to a
-- priced moment. The historical in-play backtest pairs each DK quote with the
-- last play STARTED at or before the quote and uses that play's BEFORE state
-- (scripts/inplay_history_backtest.py).
--
-- Idempotent. Existing rows stay NULL until
--   python -m data.ingestors.mlb_pbp_ingestor --fill-times 2025 2025
-- runs, which UPDATEs by (game_id, play_index) and never re-inserts.
-- Applied to production 2026-09-09.
ALTER TABLE plays ADD COLUMN IF NOT EXISTS start_time text;
ALTER TABLE plays ADD COLUMN IF NOT EXISTS end_time text;
