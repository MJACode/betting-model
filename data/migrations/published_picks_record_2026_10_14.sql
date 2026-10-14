-- The published record is the picks Discord still has.
--
-- Daily, the 7-day restatement, and all-time (Discord, X, results_snapshots,
-- v_public_track_record and v_public_track_record_daily) were counting every
-- settled BET. Measured 2026-10-14 on the 2026-10-13 all-time snapshot:
-- 472-443-2, -15.5373u. 109 of those bets have no row in v_discord_published
-- (41-68): MLB 81, NHL 23, WNBA 2, UFC 2, NFL 1. nfl_live_prop stays struck.
--
-- Units are stake_for: 1u to win at COALESCE(decision_odds, dk_odds), risk
-- capped at 3, and a missing price is the bare 1u rather than a made-up -110.
-- That is the same pair the recap's _tally adds. W-L moves with the population.
--
-- The lock is v_discord_published (discord_signal / discord_live, minus a
-- newer discord_void notice). Same key as tracking/publish_keys.posted_sql.
-- A voided pick is also result NO_ACTION and fails the WIN/LOSS/PUSH filter.
--
-- Idempotent. Before totals are inserted once, from the latest all-time rows.
-- The snapshot UPDATE runs once, until results_snapshot_published_backfill
-- records clv_rule = 'no_vig' (the same CLV predicate as v_public_track_record:
-- clv_pct IS NOT NULL AND clv_method IN ('no_vig','zero_vig')). A later pass
-- does not recompute history. The one pass that does run also skips a row
-- whose wins, losses, pushes, settled, units, risked, roi and CLV already
-- match. The view patch skips once v_discord_published is already in the live
-- text. published_at is left as the original post. This statement does not
-- write push_sent.
--
-- ONE statement, so data/view_migrations.py can execute it.

DO $mig$
DECLARE
  view_name text;
  d text;
  as_of text;
  pred text;
  rewrite boolean;
BEGIN
  -- CREATE and the lock run once. ENABLE ROW LEVEL SECURITY takes ACCESS
  -- EXCLUSIVE and reloads the API schema cache on every call (data/ddl_guard.py).
  IF to_regclass('public.results_snapshot_published_backfill') IS NULL THEN
    CREATE TABLE public.results_snapshot_published_backfill (
      sport text PRIMARY KEY,
      as_of_date text NOT NULL,
      before_wins integer,
      before_losses integer,
      before_pushes integer,
      before_settled integer,
      before_units numeric,
      before_risked numeric,
      after_wins integer,
      after_losses integer,
      after_pushes integer,
      after_settled integer,
      after_units numeric,
      after_risked numeric,
      clv_rule text
    );
    ALTER TABLE public.results_snapshot_published_backfill ENABLE ROW LEVEL SECURITY;
    REVOKE ALL ON public.results_snapshot_published_backfill FROM anon, authenticated;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'results_snapshot_published_backfill'
      AND column_name = 'clv_rule'
  ) THEN
    ALTER TABLE public.results_snapshot_published_backfill ADD COLUMN clv_rule text;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM public.results_snapshot_published_backfill) THEN
    SELECT MAX(game_date) INTO as_of
    FROM public.results_snapshots
    WHERE scope = 'all_time';

    IF as_of IS NOT NULL THEN
      INSERT INTO public.results_snapshot_published_backfill (
        sport, as_of_date, before_wins, before_losses, before_pushes,
        before_settled, before_units, before_risked)
      SELECT COALESCE(sport, ''), game_date, wins, losses, pushes,
             settled, units, risked
      FROM public.results_snapshots
      WHERE scope = 'all_time' AND game_date = as_of;
    END IF;
  END IF;

  SELECT NOT EXISTS (
    SELECT 1
    FROM public.results_snapshot_published_backfill
    WHERE clv_rule = 'no_vig'
  ) INTO rewrite;

  IF rewrite THEN
  -- STAKE_EXPR_RISK
  -- CASE WHEN price IS NULL OR price = 0 THEN 1.0 ELSE LEAST(1.0 / (CASE WHEN price > 0 THEN price / 100.0 ELSE 100.0 / abs(price) END), 3.0) END
  -- END_STAKE_EXPR_RISK
  -- STAKE_EXPR_WIN
  -- CASE WHEN price IS NULL OR price = 0 THEN 1.0 WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0 ELSE 100.0 / abs(price) END)) > 3.0 THEN 3.0 * (CASE WHEN price > 0 THEN price / 100.0 ELSE 100.0 / abs(price) END) ELSE 1.0 END
  -- END_STAKE_EXPR_WIN
  -- SNAPSHOT_REWRITE_BEGIN
  CREATE TEMP TABLE _published_record_picks ON COMMIT DROP AS
  SELECT sport, game_date, result, clv_pct, clv_method, price,
         CASE
           WHEN price IS NULL OR price = 0 THEN 1.0
           ELSE LEAST(
             1.0 / (CASE WHEN price > 0 THEN price / 100.0
                         ELSE 100.0 / abs(price) END),
             3.0)
         END AS risk,
         CASE
           WHEN price IS NULL OR price = 0 THEN 1.0
           WHEN (1.0 / (CASE WHEN price > 0 THEN price / 100.0
                             ELSE 100.0 / abs(price) END)) > 3.0
             THEN 3.0 * (CASE WHEN price > 0 THEN price / 100.0
                              ELSE 100.0 / abs(price) END)
           ELSE 1.0
         END AS win_u
  FROM (
    SELECT p.sport, p.game_date, p.result, p.clv_pct, p.clv_method,
           COALESCE(p.decision_odds, p.dk_odds) AS price
    FROM public.picks p
    WHERE p.signal_type = 'BET'
      AND (p.is_live IS NOT TRUE OR p.model_id LIKE '%\_live\_%')
      AND p.result IN ('WIN', 'LOSS', 'PUSH')
      AND p.downgrade_reason IS DISTINCT FROM 'model paused'
      AND p.condition_status IS DISTINCT FROM 'DUPLICATE'
      AND NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')
      AND p.model_id <> 'nfl_live_prop'
      AND EXISTS (
        SELECT 1 FROM public.v_discord_published pub
        WHERE pub.lock_key = CASE WHEN p.is_live THEN
          'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
          || COALESCE(':' || p.player_id, '')
          || COALESCE(':' || p.player_key, '')
          || COALESCE(':' || p.prop_market, '')
        ELSE
          p.game_id || ':' || p.model_id
          || COALESCE(':' || p.player_id, '')
          || COALESCE(':' || p.player_key, '')
          || COALESCE(':' || p.prop_market, '')
        END)
  ) priced;

  UPDATE public.results_snapshots s
  SET wins = c.wins,
      losses = c.losses,
      pushes = c.pushes,
      settled = c.settled,
      units = c.units,
      risked = c.risked,
      roi_pct = c.roi_pct,
      clv_graded = c.clv_graded,
      clv_beat = c.clv_beat,
      clv_pct = c.clv_pct
  FROM (
    SELECT
      s2.snapshot_id,
      COALESCE(COUNT(*) FILTER (WHERE g.result = 'WIN'), 0)::integer AS wins,
      COALESCE(COUNT(*) FILTER (WHERE g.result = 'LOSS'), 0)::integer AS losses,
      COALESCE(COUNT(*) FILTER (WHERE g.result = 'PUSH'), 0)::integer AS pushes,
      COALESCE(COUNT(*) FILTER (
        WHERE g.result IN ('WIN', 'LOSS', 'PUSH')), 0)::integer AS settled,
      round(COALESCE(SUM(
        CASE g.result
          WHEN 'WIN' THEN g.win_u
          WHEN 'LOSS' THEN -g.risk
          ELSE 0
        END), 0), 4) AS units,
      round(COALESCE(SUM(
        CASE WHEN g.result IS DISTINCT FROM 'PUSH' THEN g.risk ELSE 0 END
      ), 0), 4) AS risked,
      CASE
        WHEN COALESCE(SUM(
          CASE WHEN g.result IS DISTINCT FROM 'PUSH' THEN g.risk ELSE 0 END
        ), 0) > 0
        THEN round(
          COALESCE(SUM(
            CASE g.result
              WHEN 'WIN' THEN g.win_u
              WHEN 'LOSS' THEN -g.risk
              ELSE 0
            END), 0)
          / SUM(CASE WHEN g.result IS DISTINCT FROM 'PUSH' THEN g.risk ELSE 0 END)
          * 100, 4)
        ELSE NULL
      END AS roi_pct,
      COALESCE(COUNT(*) FILTER (
        WHERE g.clv_pct IS NOT NULL AND g.clv_method IN ('no_vig', 'zero_vig')), 0)::integer AS clv_graded,
      COALESCE(COUNT(*) FILTER (
        WHERE g.clv_pct IS NOT NULL AND g.clv_pct > 0
          AND g.clv_method IN ('no_vig', 'zero_vig')), 0)::integer AS clv_beat,
      CASE
        WHEN COUNT(*) FILTER (
          WHERE g.clv_pct IS NOT NULL AND g.clv_method IN ('no_vig', 'zero_vig')) > 0
        THEN round(
          COUNT(*) FILTER (
            WHERE g.clv_pct IS NOT NULL AND g.clv_pct > 0
              AND g.clv_method IN ('no_vig', 'zero_vig'))::numeric
          / COUNT(*) FILTER (
            WHERE g.clv_pct IS NOT NULL AND g.clv_method IN ('no_vig', 'zero_vig'))
          * 100, 4)
        ELSE NULL
      END AS clv_pct
    FROM public.results_snapshots s2
    LEFT JOIN _published_record_picks g
      ON (
           (s2.scope = 'daily' AND g.game_date = s2.game_date)
           OR (s2.scope = 'all_time'
               AND g.game_date >= '2026-09-01'
               AND g.game_date <= s2.game_date)
         )
     AND (s2.sport IS NULL OR g.sport = s2.sport)
    GROUP BY s2.snapshot_id
  ) c
  WHERE s.snapshot_id = c.snapshot_id
    AND (
      s.wins IS DISTINCT FROM c.wins
      OR s.losses IS DISTINCT FROM c.losses
      OR s.pushes IS DISTINCT FROM c.pushes
      OR s.settled IS DISTINCT FROM c.settled
      OR s.units IS DISTINCT FROM c.units
      OR s.risked IS DISTINCT FROM c.risked
      OR s.roi_pct IS DISTINCT FROM c.roi_pct
      OR s.clv_graded IS DISTINCT FROM c.clv_graded
      OR s.clv_beat IS DISTINCT FROM c.clv_beat
      OR s.clv_pct IS DISTINCT FROM c.clv_pct
    );

  UPDATE public.results_snapshot_published_backfill b
  SET after_wins = s.wins,
      after_losses = s.losses,
      after_pushes = s.pushes,
      after_settled = s.settled,
      after_units = s.units,
      after_risked = s.risked
  FROM public.results_snapshots s
  WHERE s.scope = 'all_time'
    AND s.game_date = b.as_of_date
    AND COALESCE(s.sport, '') = b.sport;

  UPDATE public.results_snapshot_published_backfill
  SET clv_rule = 'no_vig';
  IF NOT EXISTS (SELECT 1 FROM public.results_snapshot_published_backfill) THEN
    INSERT INTO public.results_snapshot_published_backfill
      (sport, as_of_date, clv_rule)
    VALUES ('', '1970-01-01', 'no_vig');
  END IF;
  -- SNAPSHOT_REWRITE_END
  END IF;

  pred := $pred$
    AND EXISTS (
      SELECT 1 FROM public.v_discord_published pub
      WHERE pub.lock_key = CASE WHEN p.is_live THEN
        'live:' || p.game_id || ':' || p.model_id || ':' || p.pick_side
        || COALESCE(':' || p.player_id, '')
        || COALESCE(':' || p.player_key, '')
        || COALESCE(':' || p.prop_market, '')
      ELSE
        p.game_id || ':' || p.model_id
        || COALESCE(':' || p.player_id, '')
        || COALESCE(':' || p.player_key, '')
        || COALESCE(':' || p.prop_market, '')
      END)
  $pred$;

  FOREACH view_name IN ARRAY ARRAY[
    'v_public_track_record', 'v_public_track_record_daily'
  ] LOOP
    d := pg_get_viewdef(('public.' || view_name)::regclass, true);
    IF position('v_discord_published' in d) > 0 THEN
      RAISE NOTICE '%: published lock already present - skipping', view_name;
      CONTINUE;
    END IF;
    IF position('FROM picks p' in d) = 0 THEN
      RAISE EXCEPTION '%: no picks alias p to attach the publish lock', view_name;
    END IF;
    IF d !~ '\s+GROUP BY ' THEN
      RAISE EXCEPTION '%: no GROUP BY to anchor the publish lock', view_name;
    END IF;
    d := regexp_replace(rtrim(d, E'; \n'), '\s+GROUP BY ', pred || E'\n  GROUP BY ');
    IF position('v_discord_published' in d) = 0 THEN
      RAISE EXCEPTION '%: publish lock was not inserted', view_name;
    END IF;
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', view_name, d);
    EXECUTE format('ALTER VIEW public.%I SET (security_invoker = on)', view_name);
    EXECUTE format('GRANT SELECT ON public.%I TO anon, authenticated', view_name);
    RAISE NOTICE '%: published lock added', view_name;
  END LOOP;
END $mig$;
