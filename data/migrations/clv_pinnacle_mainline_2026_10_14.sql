-- Game spread/total market edge was Pinnacle's last quote still on our
-- number, not Pinnacle's latest pre-start main line. Measured read-only on
-- vvprgnrmzeekokzkrkfu 2026-10-14: 78 of 301 non-null market-edge rows on
-- those markets had a later main line on a different number. Those 78
-- become NULL. A main line that is still our number is left as stored.
--
-- The copy of the affected picks lands before the UPDATE. An existing
-- backup row is not replaced. public.clv_pinnacle_mainline_once_2026_10_14
-- is the marker: the worker re-runs this file every pass, and a second
-- pass does not write. Picks 2899429 and 2911172 are not in the set.
-- Primary CLV, the grade, the stake and the signal are not written.
--
-- ONE statement. DDL only inside the marker branch, so a later pass fires
-- no pgrst_ddl_watch event.

DO $mig$
BEGIN
  IF to_regclass('public.clv_pinnacle_mainline_once_2026_10_14') IS NULL THEN
    IF to_regclass('public.clv_pinnacle_mainline_backup_2026_10_14') IS NULL THEN
      CREATE TABLE public.clv_pinnacle_mainline_backup_2026_10_14
        (LIKE public.picks INCLUDING DEFAULTS);
      ALTER TABLE public.clv_pinnacle_mainline_backup_2026_10_14
        ADD COLUMN backed_up_at timestamptz NOT NULL DEFAULT now();
      ALTER TABLE public.clv_pinnacle_mainline_backup_2026_10_14
        ADD PRIMARY KEY (pick_id);
      ALTER TABLE public.clv_pinnacle_mainline_backup_2026_10_14
        ENABLE ROW LEVEL SECURITY;
      IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
         AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        REVOKE ALL ON public.clv_pinnacle_mainline_backup_2026_10_14
          FROM anon, authenticated;
      END IF;
    END IF;

    CREATE TEMP TABLE _pin_mainline_affected ON COMMIT DROP AS
    WITH src AS (
      SELECT
        p.pick_id,
        p.game_id,
        p.scored_line,
        public.clv_game_market(p.model_id) AS game_market,
        split_part(p.game_id, '_', 1) AS sport_prefix,
        CASE
          WHEN p.game_time IS NOT NULL
           AND p.game_time::timestamptz < g.commence_time::timestamptz
          THEN p.game_time::timestamptz
          ELSE g.commence_time::timestamptz
        END AS close_bound
      FROM public.picks p
      JOIN public.games g ON g.game_id = p.game_id
      WHERE p.clv_method = 'standard_v2'
        AND p.signal_type = 'BET'
        AND p.is_live IS NOT TRUE
        AND p.market_clv_pct IS NOT NULL
        AND p.pick_id NOT IN (2899429, 2911172)
        AND public.clv_prop_key(p.model_id) IS NULL
        AND p.model_id NOT IN ('nfl_prop_market', 'wnba_prop_market')
        AND (
          public.clv_game_market(p.model_id) LIKE '%spreads%'
          OR public.clv_game_market(p.model_id) LIKE '%totals%'
        )
        AND g.commence_time IS NOT NULL
    )
    SELECT s.pick_id
    FROM src s
    JOIN LATERAL (
      SELECT o.spread_home, o.total_line
      FROM public.odds o
      WHERE o.game_id = s.game_id
        AND o.market = s.game_market
        AND o.bookmaker = 'pinnacle'
        AND o.snapshot_type <> 'in_play'
        AND o.snapshot_at::timestamptz <= s.close_bound
        AND (
          s.game_market <> 'spreads'
          OR s.sport_prefix NOT IN ('MLB', 'NHL')
          OR ABS(o.spread_home) = 1.5
        )
      ORDER BY o.snapshot_at::timestamptz DESC
      LIMIT 1
    ) l ON TRUE
    WHERE (
      s.game_market LIKE '%spreads%'
      AND l.spread_home IS NOT NULL
      AND s.scored_line IS NOT NULL
      AND abs(l.spread_home::double precision - s.scored_line::double precision) > 1e-9
    ) OR (
      s.game_market LIKE '%totals%'
      AND s.game_market NOT LIKE '%spreads%'
      AND l.total_line IS NOT NULL
      AND s.scored_line IS NOT NULL
      AND abs(l.total_line::double precision - s.scored_line::double precision) > 1e-9
    );

    INSERT INTO public.clv_pinnacle_mainline_backup_2026_10_14
    SELECT p.*, now()
    FROM public.picks p
    JOIN _pin_mainline_affected a ON a.pick_id = p.pick_id
    WHERE NOT EXISTS (
      SELECT 1
      FROM public.clv_pinnacle_mainline_backup_2026_10_14 b
      WHERE b.pick_id = p.pick_id
    );

    UPDATE public.picks p
       SET market_clv_pct = NULL,
           market_clv_pp = NULL,
           market_clv_method = NULL,
           pinnacle_close_odds = NULL
      FROM _pin_mainline_affected a
     WHERE p.pick_id = a.pick_id
       AND p.pick_id NOT IN (2899429, 2911172);

    CREATE TABLE public.clv_pinnacle_mainline_once_2026_10_14 (
      applied_at timestamptz NOT NULL DEFAULT now()
    );
    ALTER TABLE public.clv_pinnacle_mainline_once_2026_10_14
      ENABLE ROW LEVEL SECURITY;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon')
       AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
      REVOKE ALL ON public.clv_pinnacle_mainline_once_2026_10_14
        FROM anon, authenticated;
    END IF;
    INSERT INTO public.clv_pinnacle_mainline_once_2026_10_14 DEFAULT VALUES;
  END IF;
END
$mig$;
