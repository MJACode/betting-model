-- Restate results_snapshots units on the price each graded pick was taken at,
-- then drop the column that counted a pick in the W-L and left it out of the units.
--
-- The recap used to skip a pick when dk_odds was null. Those picks have a real
-- price in decision_odds (measured 2026-10-14: 44 NHL bets in the published
-- window, all of them). Units are the same stake the recap publishes
-- (1u to win, grossed by the taken price, risk capped at 3). W-L columns are
-- left as published.
--
-- Idempotent. The before totals are inserted once, from the latest all-time
-- rows, before the first rewrite. The units rewrite and the column drop run
-- only while results_snapshots.record_only still exists. The worker has no
-- applied-filename ledger: every ACTIVE_MIGRATIONS file runs on every pass,
-- and a file skips by looking at the database. Once this column is gone the
-- rewrite must not run again. published_picks_record_2026_10_14.sql owns the
-- snapshot numbers after that, and an unguarded rewrite here would commit
-- all-bets units onto rows whose W-L that later file already narrowed to
-- the picks Discord still has.
--
-- ONE statement, so data/view_migrations.py can execute it.

DO $mig$
DECLARE
  has_col boolean;
  as_of text;
BEGIN
  CREATE TABLE IF NOT EXISTS public.results_snapshot_unit_backfill (
    sport text PRIMARY KEY,
    as_of_date text NOT NULL,
    before_units numeric,
    after_units numeric,
    settled integer,
    excluded_from_units integer
  );

  SELECT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'results_snapshots'
      AND column_name = 'record_only'
  ) INTO has_col;

  IF NOT EXISTS (SELECT 1 FROM public.results_snapshot_unit_backfill) THEN
    SELECT MAX(game_date) INTO as_of
    FROM public.results_snapshots
    WHERE scope = 'all_time';

    IF as_of IS NOT NULL AND has_col THEN
      EXECUTE format($ins$
        INSERT INTO public.results_snapshot_unit_backfill
          (sport, as_of_date, before_units, settled, excluded_from_units)
        SELECT COALESCE(sport, ''), game_date, units, settled, record_only
        FROM public.results_snapshots
        WHERE scope = 'all_time' AND game_date = %L
      $ins$, as_of);
    ELSIF as_of IS NOT NULL THEN
      EXECUTE format($ins$
        INSERT INTO public.results_snapshot_unit_backfill
          (sport, as_of_date, before_units, settled, excluded_from_units)
        SELECT COALESCE(sport, ''), game_date, units, settled, 0
        FROM public.results_snapshots
        WHERE scope = 'all_time' AND game_date = %L
      $ins$, as_of);
    END IF;
  END IF;

  -- SNAPSHOT_REWRITE_BEGIN
  -- Only while the column this file exists to drop is still there. A later
  -- pass finds it gone and does not touch results_snapshots.
  IF has_col THEN
  CREATE TEMP TABLE _snapshot_unit_picks ON COMMIT DROP AS
  SELECT
    p.sport,
    p.game_date,
    p.result,
    CASE
      WHEN COALESCE(p.decision_odds, p.dk_odds) IS NULL
        OR COALESCE(p.decision_odds, p.dk_odds) = 0 THEN 1.0
      ELSE LEAST(
        1.0 / (CASE
                 WHEN COALESCE(p.decision_odds, p.dk_odds) > 0
                   THEN COALESCE(p.decision_odds, p.dk_odds) / 100.0
                 ELSE 100.0 / abs(COALESCE(p.decision_odds, p.dk_odds))
               END),
        3.0)
    END AS risk,
    CASE
      WHEN COALESCE(p.decision_odds, p.dk_odds) IS NULL
        OR COALESCE(p.decision_odds, p.dk_odds) = 0 THEN 1.0
      WHEN (1.0 / (CASE
                     WHEN COALESCE(p.decision_odds, p.dk_odds) > 0
                       THEN COALESCE(p.decision_odds, p.dk_odds) / 100.0
                     ELSE 100.0 / abs(COALESCE(p.decision_odds, p.dk_odds))
                   END)) > 3.0
        THEN 3.0 * (CASE
                      WHEN COALESCE(p.decision_odds, p.dk_odds) > 0
                        THEN COALESCE(p.decision_odds, p.dk_odds) / 100.0
                      ELSE 100.0 / abs(COALESCE(p.decision_odds, p.dk_odds))
                    END)
      ELSE 1.0
    END AS win_u
  FROM public.picks p
  WHERE p.signal_type = 'BET'
    AND p.result IN ('WIN', 'LOSS', 'PUSH')
    AND p.game_date >= '2026-09-01'
    AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
    AND p.downgrade_reason IS DISTINCT FROM 'model paused'
    AND p.condition_status IS DISTINCT FROM 'DUPLICATE'
    AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
    AND p.model_id <> 'nfl_live_prop';

  UPDATE public.results_snapshots s
  SET units = c.units,
      risked = c.risked,
      roi_pct = CASE
        WHEN c.risked > 0 THEN round(c.units / c.risked * 100, 4)
        ELSE NULL
      END
  FROM (
    SELECT
      s2.snapshot_id,
      round(COALESCE(SUM(
        CASE g.result
          WHEN 'WIN' THEN g.win_u
          WHEN 'LOSS' THEN -g.risk
          ELSE 0
        END), 0), 4) AS units,
      round(COALESCE(SUM(
        CASE WHEN g.result IS DISTINCT FROM 'PUSH' THEN g.risk ELSE 0 END
      ), 0), 4) AS risked
    FROM public.results_snapshots s2
    LEFT JOIN _snapshot_unit_picks g
      ON g.game_date <= s2.game_date
     AND (
       (s2.scope = 'daily' AND g.game_date = s2.game_date)
       OR s2.scope = 'all_time'
     )
     AND (s2.sport IS NULL OR g.sport = s2.sport)
    GROUP BY s2.snapshot_id
  ) c
  WHERE s.snapshot_id = c.snapshot_id;

  UPDATE public.results_snapshot_unit_backfill b
  SET after_units = s.units
  FROM public.results_snapshots s
  WHERE s.scope = 'all_time'
    AND s.game_date = b.as_of_date
    AND COALESCE(s.sport, '') = b.sport;

    ALTER TABLE public.results_snapshots DROP COLUMN record_only;
  END IF;
  -- SNAPSHOT_REWRITE_END
END $mig$;
