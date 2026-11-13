-- A pick can carry its own stake: picks.stake_units, units TO WIN, 1 to 3.
--
-- mike, 2026-11-06: "I want a pick that has a higher confidence and higher
-- long term win to be higher units, you can slice this from back testing".
-- The first writer is NCAAB (2u when a later NCAAB bet agrees with an
-- earlier NCAAB bet on the same game; docs/sports/ncaab.md, "Agreement
-- sizing"). Every other pick leaves stake_units NULL, which is the 1u to
-- win every surface has always used, so no settled record changes: a NULL
-- row grades exactly as the one- and two-argument functions grade it.
--
-- 1. picks and picks_log gain stake_units (CHECK 1..3) and stake_reason;
--    log_picks_changes() copies both.
-- 2. Three functions gain a third argument, the pick's stake_units. The
--    two-argument functions stay as they are (BYOM's backtest and anything
--    else that has no pick row call them); NULL in the third argument is
--    the two-argument function.
-- 3. open_picks passes stake_units. Its owner file recreates it with the
--    one-argument stake; this file runs after it and switches the call.
--    The two record views take stake_units from the next-but-one file,
--    published_record_units_2026_10_16.sql, which stays last.
--
-- Every statement is behind a catalog read, so a second pass changes
-- nothing and fires no DDL (tests/test_ddl_guard.py). Does not rewrite
-- picks, snapshots or push_sent. Does not post.

DO $mig$
DECLARE
  d text;
  replace_log boolean;
BEGIN
  -- 1. the columns -----------------------------------------------------------
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks'
                    AND column_name = 'stake_units') THEN
    ALTER TABLE public.picks ADD COLUMN stake_units numeric;
    ALTER TABLE public.picks ADD CONSTRAINT picks_stake_units_range
      CHECK (stake_units IS NULL OR (stake_units >= 1 AND stake_units <= 3));
    COMMENT ON COLUMN public.picks.stake_units IS
      'Units TO WIN for this pick (1..3). NULL is 1u. Risk is still capped at 3u.';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks'
                    AND column_name = 'stake_reason') THEN
    ALTER TABLE public.picks ADD COLUMN stake_reason text;
    COMMENT ON COLUMN public.picks.stake_reason IS
      'Why stake_units is above 1, in words, e.g. "agrees with the full-game total Over".';
  END IF;
  IF to_regclass('public.picks_log') IS NOT NULL THEN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'picks_log'
                      AND column_name = 'stake_units') THEN
      ALTER TABLE public.picks_log ADD COLUMN stake_units numeric;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = 'picks_log'
                      AND column_name = 'stake_reason') THEN
      ALTER TABLE public.picks_log ADD COLUMN stake_reason text;
    END IF;
  END IF;

  -- The audit trigger copies the two columns into picks_log, and only once
  -- picks_log has them (a copy into a missing column would fail every write to
  -- picks). to_regprocedure, never a ::regprocedure cast: a cast of a missing
  -- function raises even inside a false AND.
  replace_log := false;
  IF to_regprocedure('public.log_picks_changes()') IS NOT NULL
     AND EXISTS (SELECT 1 FROM information_schema.columns
                  WHERE table_schema = 'public' AND table_name = 'picks_log'
                    AND column_name = 'stake_reason') THEN
    replace_log := position('stake_units' IN pg_get_functiondef(to_regprocedure('public.log_picks_changes()'))) = 0;
  END IF;
  IF replace_log THEN
    CREATE OR REPLACE FUNCTION public.log_picks_changes()
    RETURNS trigger
    LANGUAGE plpgsql
    SET search_path = public, pg_catalog
    AS $log$
      DECLARE
        r picks%ROWTYPE;
      BEGIN
        IF TG_OP = 'DELETE' THEN
          r := OLD;
        ELSE
          r := NEW;
        END IF;

        INSERT INTO picks_log (
          logged_at, operation, pick_id, game_id, model_id, sport, game_date, game_time, run_time,
          pick_side, pick_label, model_probability, dk_implied_prob, edge, dk_odds, scored_line,
          kelly_fraction, recommended_bet, bankroll_at_pick, injury_flag, injury_detail,
          signal_type, confidence_tier, result, profit_flat, profit_kelly, settled_at, created_at,
          decision_book, decision_odds, decision_implied_prob, decision_edge, line_book,
          stake_units, stake_reason
        ) VALUES (
          NOW(), TG_OP, r.pick_id, r.game_id, r.model_id, r.sport, r.game_date, r.game_time, r.run_time,
          r.pick_side, r.pick_label, r.model_probability, r.dk_implied_prob, r.edge, r.dk_odds, r.scored_line,
          r.kelly_fraction, r.recommended_bet, r.bankroll_at_pick, r.injury_flag, r.injury_detail,
          r.signal_type, r.confidence_tier, r.result, r.profit_flat, r.profit_kelly, r.settled_at, r.created_at,
          r.decision_book, r.decision_odds, r.decision_implied_prob, r.decision_edge, r.line_book,
          r.stake_units, r.stake_reason
        );

        RETURN r;
      END;
    $log$;
    RAISE NOTICE 'log_picks_changes now copies stake_units and stake_reason';
  END IF;

  -- 2. the three-argument functions -------------------------------------------
  -- c is the conviction: stake_units when it is 1..3, else 1. risk = c / (decimal
  -- - 1) capped at 3; on a capped bet the win is recomputed from the capped
  -- risk (tracking/discord_notifier.stake_for). No price: c and c.
  IF to_regprocedure('public.published_pick_stake(numeric, numeric)') IS NULL THEN
    CREATE FUNCTION public.published_pick_stake(price numeric, units numeric,
                                                OUT risk numeric, OUT win numeric)
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $stake$
      WITH c AS (
        SELECT CASE WHEN units >= 1 AND units <= 3 THEN units ELSE 1.0 END AS c,
               CASE WHEN price IS NULL OR price = 0 THEN NULL
                    WHEN price > 0 THEN price / 100.0
                    ELSE 100.0 / abs(price) END AS d
      )
      SELECT
        CASE WHEN d IS NULL THEN c
             WHEN c / d > 3.0 THEN 3.0
             ELSE c / d END,
        CASE WHEN d IS NULL THEN c
             WHEN c / d > 3.0 THEN 3.0 * d
             ELSE c END
      FROM c
    $stake$;
  END IF;

  IF to_regprocedure('public.published_pick_unit_profit(numeric, text, numeric)') IS NULL THEN
    CREATE FUNCTION public.published_pick_unit_profit(price numeric, result text, units numeric)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $profit$
      SELECT CASE result
        WHEN 'WIN' THEN (public.published_pick_stake(price, units)).win
        WHEN 'LOSS' THEN - (public.published_pick_stake(price, units)).risk
        ELSE 0
      END
    $profit$;
  END IF;

  IF to_regprocedure('public.published_pick_unit_risked(numeric, text, numeric)') IS NULL THEN
    CREATE FUNCTION public.published_pick_unit_risked(price numeric, result text, units numeric)
    RETURNS numeric
    LANGUAGE sql
    IMMUTABLE
    PARALLEL SAFE
    SET search_path = pg_catalog
    AS $risked$
      SELECT CASE result
        WHEN 'WIN' THEN (public.published_pick_stake(price, units)).risk
        WHEN 'LOSS' THEN (public.published_pick_stake(price, units)).risk
        ELSE 0
      END
    $risked$;
  END IF;

  -- 3. open_picks passes stake_units ------------------------------------------
  IF to_regclass('public.open_picks') IS NOT NULL THEN
    d := pg_get_viewdef('public.open_picks'::regclass, true);
    IF position('p.dk_odds), p.stake_units)' IN d) = 0
       AND position('published_pick_stake(COALESCE(p.decision_odds, p.dk_odds))' IN d) > 0 THEN
      d := replace(d, 'published_pick_stake(COALESCE(p.decision_odds, p.dk_odds))',
                      'published_pick_stake(COALESCE(p.decision_odds, p.dk_odds), p.stake_units)');
      EXECUTE format('CREATE OR REPLACE VIEW public.open_picks AS %s', d);
      ALTER VIEW public.open_picks SET (security_invoker = on);
      REVOKE ALL ON public.open_picks FROM anon, authenticated;
      GRANT SELECT ON public.open_picks TO anon, authenticated;
      RAISE NOTICE 'open_picks: stake now reads the pick''s stake_units';
    END IF;
  END IF;
END $mig$;
