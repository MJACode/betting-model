-- CFBD NCAAF play-by-play, one row per play, RAW as the API serves it.
--
-- WHY IT EXISTS (session 287, 2026-09-12). The NCAAF live lanes are paused and
-- the unpause condition is a replay of the production rule over the 2025 season
-- of bought DraftKings in-play snapshots (57,979 rows on 736 games, bought
-- 2026-09-11). The replay needs the GAME STATE on the field at each snapshot,
-- and the only source of that is play-by-play with wallclocks.
--
-- THE PLAYS LIVED ONLY AS PARQUET ON ONE LAPTOP. `ncaaf_live/backtest/pull_pbp`
-- writes `ncaaf_live/data/pbp/plays_<season>.parquet`, which is gitignored, and
-- that directory is EMPTY in this checkout -- so the states corpus the engine
-- was trained on cannot be rebuilt on any machine that does not already have
-- it. CLAUDE.md section 1b: EXTRACTED DATA BELONGS IN SUPABASE. The parquet
-- path still works and is still the fast local cache; this is the copy that
-- survives a machine.
--
-- IT IS ALSO THE ONLY WAY THIS RUNS WITHOUT A KEY ON THE LAPTOP. CFBD_API_KEY
-- is a Railway variable and is NOT in the local .env; the Railway connector
-- returns variable names with values redacted, and there is no Railway CLI
-- here. api.collegefootballdata.com IS reachable from the laptop (401, not a
-- network block), so the split is: the worker holds the key and fetches, this
-- table carries the result, and any machine can build states from it.
--
-- RAW COLUMN NAMES, DELIBERATELY. `states.py` is emphatic that every
-- home/away relabelling lives in exactly one place, so this table stores what
-- CFBD returns -- offense/defense relative scores, the per-drive playNumber,
-- the wallclock -- and `load_pbp` renames back to the CFBD spelling on read.
-- Storing a transformed play here would put a second transformation in the
-- system and the score-convention bug this package already caught once
-- (playNumber is PER DRIVE; sorting by it scrambles games) would have somewhere
-- new to hide.
--
-- GROWTH: ~180 plays x ~1,300 games = ~235k rows a season, ~2.4M for the full
-- 2015-2025 corpus. Written once per season and then read; not pruned, because
-- a season's plays are immutable history and re-pulling them costs CFBD calls
-- against a metered plan.
--
-- NO APP SURFACE. RLS on, privileges revoked, no read policy.
DO $$
BEGIN
  IF to_regclass('public.ncaaf_plays') IS NULL THEN
    CREATE TABLE public.ncaaf_plays (
      -- CFBD's own play id. Text because it is the only per-play-unique
      -- column and the dedupe key states.py uses; its width is CFBD's to
      -- change, not ours.
      play_id           TEXT PRIMARY KEY,
      game_id_cfbd      TEXT NOT NULL,
      drive_id          TEXT,
      -- PER-DRIVE counter, not a game ordinal. The canonical sort is
      -- (drive order, play_number) -- see states._ORDER_COLS.
      play_number       INTEGER,
      period            INTEGER,
      clock_minutes     INTEGER,
      clock_seconds     INTEGER,
      offense           TEXT,
      defense           TEXT,
      home              TEXT,
      away              TEXT,
      -- OFFENSE/DEFENSE relative, not home/away. states.py does the relabel.
      offense_score     INTEGER,
      defense_score     INTEGER,
      offense_timeouts  INTEGER,
      defense_timeouts  INTEGER,
      down              INTEGER,
      distance          INTEGER,
      yards_to_goal     INTEGER,
      yards_gained      INTEGER,
      play_type         TEXT,
      scoring           BOOLEAN,
      -- ISO with mixed fractional seconds; the pandas inference trap the NFL
      -- build hit. Parsed with an explicit format on read.
      wallclock         TEXT,
      season            INTEGER NOT NULL,
      week              INTEGER,
      season_type       TEXT,
      ingested_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );

    -- The read: one season, in canonical order.
    CREATE INDEX ncaaf_plays_season ON public.ncaaf_plays (season, game_id_cfbd);
    -- Snapshot alignment walks a game's plays by wallclock.
    CREATE INDEX ncaaf_plays_game ON public.ncaaf_plays (game_id_cfbd, wallclock);

    ALTER TABLE public.ncaaf_plays ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.ncaaf_plays FROM anon, authenticated;
  END IF;
END $$;
