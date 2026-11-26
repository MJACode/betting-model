-- Build Your Own Model: a bet locks on a game-week line only.
--
-- Matt, 2026-11-26, after "Tets" (home favorite, spread, primetime) showed
-- 20 open bets through Jan 5, all locked on 2026-08-31: DraftKings posts a
-- whole season's lines in August, and the official lock was "the first
-- DraftKings quote that fits", so a bet locked on a look-ahead line weeks
-- before its game. Measured the same day on that model's record: 2026, 23
-- of 27 bets locked more than 14 days before kickoff (median 48.3 days);
-- 2025, median 52.9 days; 2024, 53.0 days. Chosen: "Game week only": only
-- DraftKings lines from the 7 days before kickoff count, for the record and
-- for alerts.
--
-- How. The lock search already waits for a last-game filter: a candidate
-- counts when it is still the quote in force at the wait, and the bet is
-- official at that moment, at that quote (byom_trend_filters_2026_11_05).
-- Game week is one more wait: wait_at becomes the later of that wait and
-- kickoff minus 7 days. So a line posted in August and unchanged into game
-- week locks at the moment game week opens, at that line; a line that moved
-- inside game week locks at its first fitting quote there. The closing
-- timing is unchanged. On 'open' (alerts, byom_alerts_2026_11_25.sql) a bet
-- whose lock moment is still ahead is not open yet.
--
-- byom_alerts gains lock_rule: rows already written under the first-line
-- rule keep 'first_line' and are no longer shown; new rows are 'week_of'.
-- No row is changed or deleted (CLAUDE.md 1b, 1c). The one-per-bet key
-- includes lock_rule, so the week-of bet can be written beside the old row.
--
-- byom_legs is the sum of several files, so this reads the live definition,
-- checks each anchor occurs exactly once (or raises and changes nothing) and
-- re-runs it, as byom_no_half_yards_2026_11_17.sql does. Every earlier
-- marker stays. Returns before any DDL once everything below is in place.
-- In ACTIVE_MIGRATIONS after byom_alerts_2026_11_25.sql. Does not write picks.

DO $mig$
DECLARE
  v_proc regprocedure := to_regprocedure('public.byom_legs(integer, jsonb, text)');
  v_def text;
  v_anchor text;
  v_marker text := '-- byom_trend_filters_v1';
  v_wait_open text := E'CASE\n                   WHEN NOT v_needs_prev THEN NULL';
  v_wait_close text := 'END + interval ''4 hours'' AS wait_at,';
  v_open text := 'AND r.kick > pg_catalog.now()';
BEGIN
  IF v_proc IS NULL OR to_regclass('public.byom_alerts') IS NULL THEN
    RAISE NOTICE 'byom_legs or byom_alerts is not on this database - skipping';
    RETURN;
  END IF;
  IF (SELECT position('byom_week_of_lock_v1' in p.prosrc) > 0
        FROM pg_proc p WHERE p.oid = v_proc)
     AND EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'byom_alerts'
                    AND column_name = 'lock_rule')
     AND EXISTS (SELECT 1 FROM pg_proc p
                  WHERE p.oid = to_regprocedure('public.byom_my_open_bets()')
                    AND position('byom_week_of_lock_v1' in p.prosrc) > 0)
  THEN
    RETURN;
  END IF;

  -- 1. byom_legs: game week is a wait.
  IF NOT (SELECT position('byom_week_of_lock_v1' in p.prosrc) > 0
            FROM pg_proc p WHERE p.oid = v_proc) THEN
    v_def := pg_get_functiondef(v_proc);
    FOREACH v_anchor IN ARRAY ARRAY[v_marker, v_wait_open, v_wait_close, v_open] LOOP
      IF (length(v_def) - length(replace(v_def, v_anchor, ''))) / length(v_anchor) <> 1 THEN
        RAISE EXCEPTION 'byom_week_of_lock: anchor not found exactly once: %', v_anchor;
      END IF;
    END LOOP;
    v_def := replace(v_def, v_marker, v_marker || E'\n    -- byom_week_of_lock_v1');
    v_def := replace(v_def, v_wait_open,
      E'greatest(\n                 -- byom_week_of_lock_v1: game week opens 7 days before kickoff.\n                 '
      || v_wait_open);
    v_def := replace(v_def, v_wait_close,
      E'END + interval ''4 hours'',\n                 g.commence_time - interval ''7 days'') AS wait_at,');
    -- An open bet whose lock moment is still ahead is not open yet.
    v_def := replace(v_def, v_open, v_open || ' AND r.lock_at <= pg_catalog.now()');
    EXECUTE v_def;
  END IF;

  -- 2. byom_alerts: which lock rule wrote the row.
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'byom_alerts'
                    AND column_name = 'lock_rule') THEN
    ALTER TABLE public.byom_alerts
      ADD COLUMN lock_rule text NOT NULL DEFAULT 'first_line';
    ALTER TABLE public.byom_alerts ALTER COLUMN lock_rule SET DEFAULT 'week_of';
    ALTER TABLE public.byom_alerts DROP CONSTRAINT IF EXISTS byom_alerts_one_per_bet;
    ALTER TABLE public.byom_alerts ADD CONSTRAINT byom_alerts_one_per_bet
      UNIQUE (model_id, canonical_key, market, leg_side, player_name, lock_rule);
  END IF;

  -- 3. byom_my_open_bets shows week-of rows only.
  IF NOT EXISTS (SELECT 1 FROM pg_proc p
                  WHERE p.oid = to_regprocedure('public.byom_my_open_bets()')
                    AND position('byom_week_of_lock_v1' in p.prosrc) > 0) THEN
    v_proc := to_regprocedure('public.byom_my_open_bets()');
    v_def := pg_get_functiondef(v_proc);
    FOREACH v_anchor IN ARRAY ARRAY['       WHERE a.user_id = v_uid',
                                    '      -- byom_alerts_members_v1'] LOOP
      IF (length(v_def) - length(replace(v_def, v_anchor, ''))) / length(v_anchor) <> 1 THEN
        RAISE EXCEPTION 'byom_week_of_lock: anchor not found exactly once: %', v_anchor;
      END IF;
    END LOOP;
    v_anchor := '       WHERE a.user_id = v_uid';
    v_def := replace(v_def, '      -- byom_alerts_members_v1',
      E'      -- byom_alerts_members_v1\n      -- byom_week_of_lock_v1');
    v_def := replace(v_def, v_anchor, v_anchor || E'\n         AND a.lock_rule = ''week_of''');
    EXECUTE v_def;
  END IF;
END
$mig$;
