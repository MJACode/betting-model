-- Migration: 20260429120511_fix_security_advisors
-- Applied via Supabase MCP apply_migration on 2026-04-29.
--
-- Resolves three Supabase security advisor lints flagged on project
-- vvprgnrmzeekokzkrkfu:
--   1. ERROR  rls_disabled_in_public      — public.picks_log
--   2. ERROR  security_definer_view       — public.confirmed_picks
--   3. WARN   function_search_path_mutable — public.log_picks_changes
--
-- The pipeline connects via DATABASE_URL as the postgres role, which has
-- BYPASSRLS, so enabling RLS without policies blocks anonymous PostgREST
-- access while leaving run_pipeline.py, the Streamlit dashboard, and the
-- Claude Mobile MCP integration unaffected. Same posture as the other 12
-- public tables (games, picks, odds, …) which already have RLS enabled
-- without policies.

-- 1. picks_log — append-only audit log. Lock down PostgREST access.
ALTER TABLE public.picks_log ENABLE ROW LEVEL SECURITY;

-- 2. confirmed_picks — drop SECURITY DEFINER, run as the querying user instead.
CREATE OR REPLACE VIEW public.confirmed_picks
WITH (security_invoker = true) AS
WITH run_order AS (
    SELECT picks_log.log_id,
           picks_log.logged_at,
           picks_log.operation,
           picks_log.pick_id,
           picks_log.game_id,
           picks_log.model_id,
           picks_log.sport,
           picks_log.game_date,
           picks_log.game_time,
           picks_log.run_time,
           picks_log.pick_side,
           picks_log.pick_label,
           picks_log.model_probability,
           picks_log.dk_implied_prob,
           picks_log.edge,
           picks_log.dk_odds,
           picks_log.scored_line,
           picks_log.kelly_fraction,
           picks_log.recommended_bet,
           picks_log.bankroll_at_pick,
           picks_log.injury_flag,
           picks_log.injury_detail,
           picks_log.signal_type,
           picks_log.confidence_tier,
           picks_log.result,
           picks_log.profit_flat,
           picks_log.profit_kelly,
           picks_log.settled_at,
           picks_log.created_at,
           CASE picks_log.run_time
               WHEN '7am'    THEN 1
               WHEN '12pm'   THEN 2
               WHEN '3:30pm' THEN 3
               WHEN '6pm'    THEN 4
               WHEN '8pm'    THEN 5
               ELSE 0
           END AS run_rank
      FROM picks_log
     WHERE picks_log.signal_type = 'BET' AND picks_log.operation <> 'DELETE'
), game_last_run AS (
    SELECT run_order.game_date,
           run_order.game_id,
           CASE
               WHEN run_order.game_time IS NULL OR run_order.game_time >= '20:00' THEN '8pm'
               WHEN run_order.game_time >= '18:00' THEN '6pm'
               WHEN run_order.game_time >= '15:30' THEN '3:30pm'
               WHEN run_order.game_time >= '12:00' THEN '12pm'
               ELSE '7am'
           END AS cutoff_run
      FROM run_order
     GROUP BY run_order.game_date, run_order.game_id, run_order.game_time
), latest_log AS (
    SELECT ro.*
      FROM run_order ro
      JOIN game_last_run glr
        ON ro.game_id = glr.game_id AND ro.game_date = glr.game_date
     WHERE ro.run_rank = (
            SELECT max(ro2.run_rank)
              FROM run_order ro2
             WHERE ro2.game_id = ro.game_id
               AND ro2.game_date = ro.game_date
               AND ro2.run_rank <= CASE glr.cutoff_run
                                       WHEN '7am'    THEN 1
                                       WHEN '12pm'   THEN 2
                                       WHEN '3:30pm' THEN 3
                                       WHEN '6pm'    THEN 4
                                       WHEN '8pm'    THEN 5
                                       ELSE NULL
                                   END
           )
)
SELECT pick_label,
       model_id,
       game_date,
       game_time,
       run_time AS final_run,
       edge,
       dk_odds,
       recommended_bet,
       confidence_tier,
       model_probability,
       result,
       profit_flat,
       profit_kelly
  FROM latest_log;

-- 3. log_picks_changes — pin search_path so the trigger can't be hijacked
--    by a role that shadows built-ins in their own schema.
ALTER FUNCTION public.log_picks_changes() SET search_path = public, pg_catalog;
