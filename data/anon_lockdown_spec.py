"""Step A and B of the anon-key lockdown, from the CPO spec of 2026-11-18.

Authenticated keeps every grant it has today, except tracked_bets, which
becomes owner-scoped. Steps C and D (premium gates) are not in this change.
"""

from __future__ import annotations

# 25 relations anon can read today, closed in step A. The matview is one of them.
STEP_A_RELATIONS: tuple[str, ...] = (
    "picks",
    "open_picks",
    "confirmed_picks",
    "mv_scored_pick_outcomes",
    "opening_signals",
    "model_registry",
    "model_action_thresholds",
    "model_quality_checks",
    "v_model_full_outcome_picks",
    "v_model_full_outcome_record",
    "v_model_full_record",
    "v_opening_signal_slices",
    "v_opening_vs_live",
    "parlay_correlations",
    "parlay_track_record",
    "results_snapshots",
    "v_public_track_record",
    "v_public_track_record_daily",
    "v_discord_published",
    "v_discord_void_notice",
    "byom_official_legs",
    "byom_game_facts",
    "byom_prop_facts",
    "odds_api_quota",
    "system_health_checks",
)

# Grant with no anon-visible rows. Revoked in A anyway.
STEP_A_HYGIENE: tuple[str, ...] = ("picks_log",)

# (policy name, table, roles to restore on undo). "public" is the PUBLIC role.
STEP_A_POLICIES: tuple[tuple[str, str, str], ...] = (
    ("allow anon read", "picks", "public"),
    ("anon read picks", "picks", "anon, authenticated"),
    ("anon read opening_signals", "opening_signals", "anon, authenticated"),
    ("anon read model_registry", "model_registry", "anon, authenticated"),
    ("anon read model_action_thresholds", "model_action_thresholds", "anon, authenticated"),
    ("anon read model_quality_checks", "model_quality_checks", "anon, authenticated"),
    ("anon read parlay_correlations", "parlay_correlations", "anon, authenticated"),
    ("anon read parlay_track_record", "parlay_track_record", "anon, authenticated"),
    ("anon read results_snapshots", "results_snapshots", "anon, authenticated"),
    ("anon read byom_official_legs", "byom_official_legs", "anon, authenticated"),
    ("anon read byom_game_facts", "byom_game_facts", "anon, authenticated"),
    ("anon read byom_prop_facts", "byom_prop_facts", "anon, authenticated"),
    ("anon read odds_api_quota", "odds_api_quota", "anon, authenticated"),
    ("anon read system_health_checks", "system_health_checks", "anon, authenticated"),
    ("anon_read_discord_publish", "push_sent", "anon, authenticated"),
)

# Identity arguments. OUT parameters are not part of the signature.
STEP_A_FUNCTIONS: tuple[str, ...] = (
    "public.byom_backtest(integer, jsonb)",
    "public.byom_bets(integer, jsonb, text)",
    "public.byom_leg_label(text, text, text, numeric, text)",
    "public.byom_legs(integer, jsonb, text)",
    "public.byom_line_move(text, text, numeric, numeric, numeric, numeric)",
    "public.byom_player_names(text, text)",
    "public.byom_record(integer, jsonb)",
    "public.byom_risk_units(numeric)",
    "public.byom_team_division(text, integer, text)",
    "public.byom_win_units(numeric)",
    "public.clv_american_decimal(double precision)",
    "public.clv_american_implied(double precision)",
    "public.clv_game_market(text)",
    "public.clv_label_book(text)",
    "public.clv_market_edge(double precision, double precision, double precision[], text)",
    "public.clv_power_fair(double precision[])",
    "public.clv_prop_key(text)",
    "public.clv_same_book(double precision, double precision)",
    "public.custom_model_backtest(jsonb, jsonb)",
    "public.custom_model_backtest_posted(jsonb, jsonb)",
    "public.custom_model_picks(jsonb, jsonb, integer)",
    "public.published_pick_stake(numeric)",
    "public.published_pick_stake(numeric, numeric)",
    "public.published_pick_unit_profit(numeric, text)",
    "public.published_pick_unit_profit(numeric, text, numeric)",
    "public.published_pick_unit_risked(numeric, text)",
    "public.published_pick_unit_risked(numeric, text, numeric)",
    "public.sgp_haircuts()",
)

# These 17 reach anon through PUBLIC. log_picks_changes is the 18th and is in B.
STEP_A_PUBLIC_FUNCTIONS: frozenset[str] = frozenset({
    "public.byom_line_move(text, text, numeric, numeric, numeric, numeric)",
    "public.byom_team_division(text, integer, text)",
    "public.clv_american_decimal(double precision)",
    "public.clv_american_implied(double precision)",
    "public.clv_game_market(text)",
    "public.clv_label_book(text)",
    "public.clv_market_edge(double precision, double precision, double precision[], text)",
    "public.clv_power_fair(double precision[])",
    "public.clv_prop_key(text)",
    "public.clv_same_book(double precision, double precision)",
    "public.custom_model_picks(jsonb, jsonb, integer)",
    "public.published_pick_stake(numeric)",
    "public.published_pick_stake(numeric, numeric)",
    "public.published_pick_unit_profit(numeric, text)",
    "public.published_pick_unit_profit(numeric, text, numeric)",
    "public.published_pick_unit_risked(numeric, text)",
    "public.published_pick_unit_risked(numeric, text, numeric)",
})

STEP_B_RELATIONS: tuple[str, ...] = (
    "alt_game_lines", "fighters", "games", "injury_status_current",
    "latest_odds", "latest_prop_odds", "lineup_slots",
    "mlb_pitcher_stats", "mlb_team_stats",
    "nba_first_basket_games", "nba_first_basket_players", "nba_player_dnp",
    "nba_player_game_log", "nba_team_q1_games", "nba_team_stats",
    "ncaab_player_game_log", "ncaabw_player_game_log",
    "ncaaf_player_game_log", "ncaaf_team_stats", "ncaaf_teams",
    "nfl_player_game_log", "nfl_team_game_stats",
    "nhl_goalie_game_log", "nhl_skater_game_log", "nhl_team_game_log", "nhl_team_stats",
    "odds", "player_game_log", "player_handedness", "player_news", "player_positions",
    "player_prop_odds", "player_savant_stats", "public_betting",
    "team_period_results", "team_stats_board_cache", "ufc_fight_log", "umpires",
    "v_fighter_season_totals_ufc", "v_latest_dk_odds", "v_latest_inplay_odds_all_books",
    "v_latest_odds_all_books", "v_latest_prop_odds_all_books", "v_mlb_tonight_matchups",
    "v_nba_first_basket_player_season", "v_nba_first_basket_team_season",
    "v_nba_team_q1_season", "v_nhl_player_prop_odds",
    "v_player_season_totals_mlb", "v_player_season_totals_nba",
    "v_player_season_totals_ncaab", "v_player_season_totals_ncaabw",
    "v_player_season_totals_ncaaf", "v_player_season_totals_nfl",
    "v_player_season_totals_nhl", "v_player_season_totals_wnba",
    "v_team_season_record_mlb", "v_team_season_totals_nhl", "v_wnba_tonight_matchups",
    "wnba_player_game_log", "wnba_team_stats",
    "live_scoreboard", "scoreboard_splits", "v_ncaaf_scoreboard_latest",
    "ncaaf_live_states", "live_game_state", "latest_live_game_state",
    "v_live_game_state_latest", "game_weather",
    "golf_players", "golf_rounds", "golf_tournaments",
)

STEP_B_HYGIENE: tuple[str, ...] = (
    "device_push_tokens", "dk_line_observations", "feedback", "golf_odds",
    "injuries", "linked_sportsbook_accounts", "live_credit_telemetry",
    "live_feed_probe", "live_trigger_events", "mlb_bullpen_stats",
    "ncaaf_team_game_log", "ncaaf_venues", "nfl_snap_counts",
    "nhl_goalie_stats", "nhl_skater_stats", "pipeline_log", "plays",
    "synced_bets", "tracked_bets",
)

STEP_B_POLICIES: tuple[tuple[str, str, str], ...] = (
    ("anon read alt_game_lines", "alt_game_lines", "anon, authenticated"),
    ("anon read fighters", "fighters", "anon, authenticated"),
    ("allow anon read", "games", "public"),
    ("anon read games", "games", "anon, authenticated"),
    ("anon read injury_status_current", "injury_status_current", "anon, authenticated"),
    ("anon read latest_odds", "latest_odds", "anon, authenticated"),
    ("anon read latest_prop_odds", "latest_prop_odds", "anon, authenticated"),
    ("anon read lineup_slots", "lineup_slots", "anon, authenticated"),
    ("anon read mlb_pitcher_stats", "mlb_pitcher_stats", "anon, authenticated"),
    ("anon read mlb_team_stats", "mlb_team_stats", "anon, authenticated"),
    ("anon read nba_first_basket_games", "nba_first_basket_games", "anon, authenticated"),
    ("anon read nba_first_basket_players", "nba_first_basket_players", "anon, authenticated"),
    ("anon read nba_player_dnp", "nba_player_dnp", "anon, authenticated"),
    ("anon read nba_player_game_log", "nba_player_game_log", "anon, authenticated"),
    ("anon read nba_team_q1_games", "nba_team_q1_games", "anon, authenticated"),
    ("anon read nba_team_stats", "nba_team_stats", "anon, authenticated"),
    ("anon read ncaab_player_game_log", "ncaab_player_game_log", "anon, authenticated"),
    ("anon read ncaabw_player_game_log", "ncaabw_player_game_log", "anon, authenticated"),
    ("anon read ncaaf_player_game_log", "ncaaf_player_game_log", "anon, authenticated"),
    ("anon read ncaaf_team_stats", "ncaaf_team_stats", "anon, authenticated"),
    ("anon read ncaaf_teams", "ncaaf_teams", "anon, authenticated"),
    ("anon read nfl_player_game_log", "nfl_player_game_log", "anon, authenticated"),
    ("anon read nfl_team_game_stats", "nfl_team_game_stats", "anon, authenticated"),
    ("anon read nhl_goalie_game_log", "nhl_goalie_game_log", "anon, authenticated"),
    ("anon read nhl_skater_game_log", "nhl_skater_game_log", "anon, authenticated"),
    ("anon read nhl_team_game_log", "nhl_team_game_log", "anon, authenticated"),
    ("anon read nhl_team_stats", "nhl_team_stats", "anon, authenticated"),
    ("allow anon read", "odds", "public"),
    ("anon read odds", "odds", "anon, authenticated"),
    ("anon read player_game_log", "player_game_log", "anon, authenticated"),
    ("anon read player_handedness", "player_handedness", "anon, authenticated"),
    ("anon read player_news", "player_news", "anon, authenticated"),
    ("anon read player_positions", "player_positions", "anon, authenticated"),
    ("anon read player_prop_odds", "player_prop_odds", "anon, authenticated"),
    ("anon read player_savant_stats", "player_savant_stats", "anon, authenticated"),
    ("anon read public_betting", "public_betting", "anon, authenticated"),
    ("anon read team_period_results", "team_period_results", "anon, authenticated"),
    ("team_stats_board_cache_read", "team_stats_board_cache", "anon, authenticated"),
    ("anon read ufc_fight_log", "ufc_fight_log", "anon, authenticated"),
    ("anon read umpires", "umpires", "anon, authenticated"),
    ("anon read wnba_player_game_log", "wnba_player_game_log", "anon, authenticated"),
    ("anon read wnba_team_stats", "wnba_team_stats", "anon, authenticated"),
    ("anon read live_scoreboard", "live_scoreboard", "anon, authenticated"),
    ("anon read scoreboard_splits", "scoreboard_splits", "anon, authenticated"),
    ("anon read ncaaf_live_states", "ncaaf_live_states", "anon, authenticated"),
    ("anon read live_game_state", "live_game_state", "anon, authenticated"),
    ("anon read latest_live_game_state", "latest_live_game_state", "anon, authenticated"),
    ("allow anon read", "game_weather", "public"),
    ("anon read game_weather", "game_weather", "anon, authenticated"),
    # service_role_all stays TO public. Its qual is auth.role() =
    # 'service_role', which is never true for anon, and service_role
    # bypasses RLS. Moving it to authenticated would leave a policy
    # that cannot match.
    ("anon read golf_players", "golf_players", "anon, authenticated"),
    ("anon read golf_rounds", "golf_rounds", "anon, authenticated"),
    ("anon read golf_tournaments", "golf_tournaments", "anon, authenticated"),
)

STEP_B_STATS_FUNCTIONS: tuple[str, ...] = (
    "public.fighter_window_totals_ufc(integer, integer)",
    "public.player_h2h_stat_values_mlb(integer[], text, text, text[], text[])",
    "public.player_h2h_stat_values_nba(integer[], text, text[], text[])",
    "public.player_h2h_stat_values_ncaab(integer[], text, text[], text[])",
    "public.player_h2h_stat_values_ncaabw(integer[], text, text[], text[])",
    "public.player_h2h_stat_values_ncaaf(integer[], text, text[], text[])",
    "public.player_h2h_stat_values_nfl(integer[], text, text[], text[])",
    "public.player_h2h_stat_values_wnba(integer[], text, text[], text[])",
    "public.player_recent_games_mlb(integer, text, integer, text[])",
    "public.player_recent_games_nba(integer, integer, text[])",
    "public.player_recent_games_ncaab(integer, integer, text[])",
    "public.player_recent_games_ncaabw(integer, integer, text[])",
    "public.player_recent_games_ncaaf(integer, integer, text[])",
    "public.player_recent_games_nfl(integer, integer, text[])",
    "public.player_recent_games_wnba(integer, integer, text[])",
    "public.player_season_stat_values_mlb(integer, text, text)",
    "public.player_season_stat_values_nba(integer, text)",
    "public.player_season_stat_values_ncaab(integer, text)",
    "public.player_season_stat_values_ncaabw(integer, text)",
    "public.player_season_stat_values_ncaaf(integer, text)",
    "public.player_season_stat_values_nfl(integer, text)",
    "public.player_season_stat_values_wnba(integer, text)",
    "public.player_stat_values_nhl(integer, text, text, integer)",
    "public.player_vs_defense_nba(text, text, text, integer[], integer, text)",
    "public.player_vs_defense_nfl(text, text, text, integer[], integer, text)",
    "public.player_vs_defense_wnba(text, text, text, integer[], integer, text)",
    "public.player_window_totals_mlb(integer, text, integer)",
    "public.player_window_totals_nba(integer, integer)",
    "public.player_window_totals_ncaab(integer, integer)",
    "public.player_window_totals_ncaabw(integer, integer)",
    "public.player_window_totals_ncaaf(integer, integer)",
    "public.player_window_totals_nfl(integer, integer)",
    "public.player_window_totals_nhl(integer, integer)",
    "public.player_window_totals_wnba(integer, integer)",
    "public.position_defense_ranks_nfl(integer[], text, text)",
    "public.position_vs_opponent_mlb(integer[], text, text, text)",
    "public.position_vs_opponent_nba(integer[], text, text, text)",
    "public.position_vs_opponent_ncaaf(integer[], text, text, text)",
    "public.position_vs_opponent_nfl(integer[], text, text, text)",
    "public.position_vs_opponent_wnba(integer[], text, text, text)",
    "public.team_stats_board(text, integer)",
)

STEP_B_DEVICE_FUNCTIONS: tuple[str, ...] = (
    "public._jsonb_text_array(jsonb)",
    "public.feedback_mark_read(text, bigint)",
    "public.feedback_messages_for_thread(text, bigint)",
    "public.feedback_submit(text, text, text, text, text, bigint, uuid)",
    "public.feedback_threads_for_device(text)",
    "public.feedback_unread_count(text)",
    "public.log_picks_changes()",
    "public.log_sgp_price(text, text, integer, numeric, integer, integer, jsonb, text)",
    "public.member_books_get(text)",
    "public.member_books_set(text, text[])",
    "public.save_device_push_token(text, text, text, boolean, text)",
)

STEP_B_PUBLIC_FUNCTIONS: frozenset[str] = frozenset({
    "public.log_picks_changes()",
})

ANON_KEEP_RELATIONS: frozenset[str] = frozenset({"site_public_record"})
ANON_KEEP_FUNCTIONS: frozenset[str] = frozenset({
    "log_app_error",
    "log_app_timings",
    # Signed-out opt-out. The function returns nothing and only writes a
    # row the caller already knows the token for. Revoking anon here leaves
    # a device that turned push off still enabled.
    "save_device_push_token",
})

# Measured 2026-11-18 on vvprgnrmzeekokzkrkfu. The pre-apply check aborts
# if a fresh snapshot does not match these.
EXPECTED_ANON_READABLE = 97
EXPECTED_ANON_GRANT_ONLY = 20
EXPECTED_ANON_EXECUTABLE = 82
EXPECTED_ANON_SEQUENCES = 67


def _revoke_rels(names: tuple[str, ...]) -> str:
    return "".join(f"REVOKE ALL ON public.{name} FROM anon;\n" for name in names)


def _alter_policies(rows: tuple[tuple[str, str, str], ...], roles: str) -> str:
    return "".join(
        f'ALTER POLICY "{name}" ON public.{table} TO {roles};\n'
        for name, table, _undo in rows
    )


def _functions(sigs: tuple[str, ...]) -> str:
    lines = []
    for sig in sigs:
        bare = sig.split(".", 1)[1].split("(", 1)[0]
        if bare in ANON_KEEP_FUNCTIONS:
            # PUBLIC off, anon kept. save_device_push_token is the opt-out.
            lines.append(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC;\n")
            lines.append(
                "GRANT EXECUTE ON FUNCTION "
                f"{sig} TO postgres, anon, authenticated, service_role;\n")
            continue
        lines.append(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC, anon;\n")
        # postgres is the owner. REVOKE FROM PUBLIC removes the owner's only
        # EXECUTE, and the owner has no special exemption. The worker calls
        # these as postgres.
        lines.append(
            "GRANT EXECUTE ON FUNCTION "
            f"{sig} TO postgres, authenticated, service_role;\n")
    return "".join(lines)


def _regrant_functions(sigs: tuple[str, ...], public: frozenset[str]) -> str:
    lines = []
    for sig in sigs:
        lines.append(f"GRANT EXECUTE ON FUNCTION {sig} TO anon, authenticated;\n")
        if sig in public:
            lines.append(f"GRANT EXECUTE ON FUNCTION {sig} TO PUBLIC;\n")
    return "".join(lines)


HEADER = """\
-- Signal Base anon-key lockdown. HAND APPLIED. Not in ACTIVE_MIGRATIONS.
--
-- Project vvprgnrmzeekokzkrkfu. Matt, 2026-11-18: prep steps A and B; he OKs
-- the production apply. Authenticated grants stay as they are, except
-- tracked_bets. service_role is granted EXECUTE where a function lost PUBLIC,
-- and is otherwise untouched. The worker and Discord use postgres over
-- DATABASE_URL and bypass RLS.
--
-- Idempotent where PostgreSQL allows it (REVOKE, GRANT, ADD COLUMN IF NOT
-- EXISTS, DROP POLICY IF EXISTS). ALTER POLICY is safe to re-run: it sets
-- the role list again. No EXCEPTION handler swallows an error.
"""


def site_public_record_sql(retired: tuple[str, ...]) -> str:
    values = ",\n  ".join(f"('{mid}')" for mid in retired)
    return f"""{HEADER}
-- Apply this, deploy the website, and confirm the record row BEFORE step A.
-- security_invoker is off on purpose: anon must not need SELECT on picks.
-- The Supabase linter flags that (security_definer_view). It is intentional.

BEGIN;

CREATE TABLE IF NOT EXISTS public.site_retired_models (
    model_id text PRIMARY KEY
);
ALTER TABLE public.site_retired_models ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.site_retired_models FROM PUBLIC, anon, authenticated;

INSERT INTO public.site_retired_models (model_id) VALUES
  {values}
ON CONFLICT (model_id) DO NOTHING;

CREATE OR REPLACE VIEW public.site_public_record
WITH (security_invoker = false, security_barrier = true) AS
SELECT r.sport,
       SUM(r.picks)::integer AS picks,
       SUM(r.wins)::integer AS wins,
       SUM(r.losses)::integer AS losses,
       SUM(r.pushes)::integer AS pushes,
       ROUND(SUM(r.units), 2)::numeric(12, 2) AS units,
       ROUND(SUM(r.risked), 2)::numeric(12, 2) AS risked,
       MIN(r.first_date)::date AS first_date,
       MAX(r.last_date)::date AS last_date,
       now() AS refreshed_at
  FROM public.v_public_track_record r
 WHERE NOT EXISTS (
       SELECT 1 FROM public.site_retired_models s
        WHERE s.model_id = r.model_id)
 GROUP BY r.sport;

REVOKE ALL ON public.site_public_record FROM PUBLIC, anon, authenticated;
GRANT SELECT ON public.site_public_record TO anon, authenticated;

COMMENT ON VIEW public.site_public_record IS
  'Website record row. Settled published picks, one row per sport, no model id. security_invoker off so anon does not read picks. Intentional definer view.';

NOTIFY pgrst, 'reload schema';
COMMIT;
"""


def step_a_sql() -> str:
    names = ", ".join(f"'{n}'" for n in STEP_A_RELATIONS + STEP_A_HYGIENE)
    fn_names = ", ".join(
        "'" + sig.split(".", 1)[1].split("(", 1)[0] + "'"
        for sig in STEP_A_FUNCTIONS)
    return f"""{HEADER}
-- Step A. Model, picks, record, BYOM and ops off anon.
-- site_public_record_2026_11.sql must already be applied and the website
-- pointed at it. Authenticated SELECT on every relation below is kept.
-- The matview loses anon and keeps authenticated until step D.

BEGIN;

{_revoke_rels(STEP_A_RELATIONS + STEP_A_HYGIENE)}
REVOKE SELECT (lock_key, kind, sent_at) ON public.push_sent FROM anon;

{_alter_policies(STEP_A_POLICIES, "authenticated")}
{_functions(STEP_A_FUNCTIONS)}
-- Read-back. Abort if anon can still read a step A relation or execute a
-- step A function, or if authenticated lost SELECT.
DO $guard$
DECLARE bad text;
BEGIN
  SELECT string_agg(n, ',') INTO bad FROM unnest(ARRAY[{names}]) n
   WHERE has_table_privilege('anon', 'public.' || n, 'SELECT');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'anon still reads: %', bad; END IF;
  IF has_column_privilege('anon', 'public.push_sent', 'lock_key', 'SELECT') THEN
    RAISE EXCEPTION 'anon still reads push_sent.lock_key';
  END IF;
  SELECT string_agg(p.oid::regprocedure::text, ',') INTO bad FROM pg_proc p
   WHERE p.pronamespace = 'public'::regnamespace
     AND p.proname = ANY(ARRAY[{fn_names}])
     AND has_function_privilege('anon', p.oid, 'EXECUTE');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'anon still executes: %', bad; END IF;
  SELECT string_agg(n, ',') INTO bad FROM unnest(ARRAY[{names}]) n
   WHERE to_regclass('public.' || n) IS NOT NULL
     AND NOT has_table_privilege('authenticated', 'public.' || n, 'SELECT');
  IF bad IS NOT NULL THEN RAISE EXCEPTION 'authenticated lost: %', bad; END IF;
END $guard$;

NOTIFY pgrst, 'reload schema';
COMMIT;
"""


def step_b_sql() -> str:
    return f"""{HEADER}
-- Step B. Everything else off anon, plus tracked_bets owner policies.
-- Afterwards anon keeps site_public_record, log_app_error, log_app_timings
-- and save_device_push_token (signed-out opt-out). Authenticated access is
-- unchanged apart from tracked_bets.
-- Run at least 24 hours after step A unless Matt says otherwise.

BEGIN;

{_revoke_rels(STEP_B_RELATIONS + STEP_B_HYGIENE)}
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon;
GRANT USAGE ON SEQUENCE public.tracked_bets_id_seq TO authenticated;
-- New objects from postgres must not arrive open. Tables repeat the
-- 2026-09-03 sweep. Sequences and PUBLIC function execute are new here.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
    REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC, anon;

{_alter_policies(STEP_B_POLICIES, "authenticated")}
{_functions(STEP_B_STATS_FUNCTIONS + STEP_B_DEVICE_FUNCTIONS)}
-- notification_inbox and notification_sport_prefs are authenticated-only
-- (draft PR for the inbox). If they already exist, anon loses every grant.
-- If they do not exist yet, this is a no-op.
DO $inbox$
BEGIN
  IF to_regclass('public.notification_inbox') IS NOT NULL THEN
    EXECUTE 'REVOKE ALL ON TABLE public.notification_inbox FROM anon';
  END IF;
  IF to_regclass('public.notification_sport_prefs') IS NOT NULL THEN
    EXECUTE 'REVOKE ALL ON TABLE public.notification_sport_prefs FROM anon';
  END IF;
END $inbox$;

-- tracked_bets. DEFAULT auth.uid() fills the column the shipping app does
-- not send, so builds 14401 and 14601 keep inserting. A client that sends
-- another user's id fails the check. The column is kept on undo.
-- Legacy rows with user_id NULL are filled only when that device_id maps
-- to exactly one account in app_timings or feedback_threads. Anything
-- still NULL is deleted by untrack_tracked_bet when the caller is that
-- device and no other account has used it. The worker then stops alerting.
ALTER TABLE public.tracked_bets
    ADD COLUMN IF NOT EXISTS user_id uuid NULL DEFAULT auth.uid()
    REFERENCES auth.users(id) ON DELETE CASCADE;
CREATE INDEX IF NOT EXISTS tracked_bets_user_id_idx
    ON public.tracked_bets (user_id);

DO $backfill$
DECLARE src text := '';
BEGIN
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    src := 'SELECT device_id, user_id FROM public.app_timings'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF to_regclass('public.feedback_threads') IS NOT NULL THEN
    IF src <> '' THEN src := src || ' UNION '; END IF;
    src := src || 'SELECT device_id, user_id FROM public.feedback_threads'
        || ' WHERE user_id IS NOT NULL AND device_id IS NOT NULL';
  END IF;
  IF src = '' THEN RETURN; END IF;
  EXECUTE
    'UPDATE public.tracked_bets tb SET user_id = mapped.user_id FROM ('
    || 'SELECT device_id, min(user_id::text)::uuid AS user_id FROM ('
    || src || ') seen GROUP BY device_id '
    || 'HAVING count(DISTINCT user_id) = 1) mapped '
    || 'WHERE tb.user_id IS NULL AND tb.device_id = mapped.device_id';
END $backfill$;
DROP POLICY IF EXISTS "anon insert tracked_bets" ON public.tracked_bets;
DROP POLICY IF EXISTS "anon delete tracked_bets" ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_insert ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_select ON public.tracked_bets;
DROP POLICY IF EXISTS tracked_bets_owner_delete ON public.tracked_bets;
REVOKE ALL ON public.tracked_bets FROM anon;
REVOKE ALL ON public.tracked_bets FROM authenticated;
GRANT SELECT, INSERT, DELETE ON public.tracked_bets TO authenticated;
CREATE POLICY tracked_bets_owner_insert ON public.tracked_bets
    FOR INSERT TO authenticated
    WITH CHECK (user_id = (SELECT auth.uid()));
CREATE POLICY tracked_bets_owner_select ON public.tracked_bets
    FOR SELECT TO authenticated
    USING (user_id = (SELECT auth.uid()));
CREATE POLICY tracked_bets_owner_delete ON public.tracked_bets
    FOR DELETE TO authenticated
    USING (user_id = (SELECT auth.uid()));

-- Direct DELETE cannot see a legacy NULL user_id row. This function can,
-- and only when no other account is stored for that device.
CREATE OR REPLACE FUNCTION public.untrack_tracked_bet(
    p_device_id text, p_pick_id bigint)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $fn$
DECLARE
  uid uuid := auth.uid();
  other_owner boolean := false;
BEGIN
  IF uid IS NULL THEN
    RAISE EXCEPTION 'untrack_tracked_bet: sign in required' USING ERRCODE = '42501';
  END IF;
  IF p_device_id IS NULL OR p_device_id !~ '^[A-Za-z0-9-]{{8,64}}$' THEN
    RAISE EXCEPTION 'untrack_tracked_bet: bad device id' USING ERRCODE = '22023';
  END IF;
  IF to_regclass('public.app_timings') IS NOT NULL THEN
    EXECUTE
      'SELECT EXISTS (SELECT 1 FROM public.app_timings'
      || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
      INTO other_owner USING p_device_id, uid;
  END IF;
  IF NOT other_owner AND to_regclass('public.feedback_threads') IS NOT NULL THEN
    EXECUTE
      'SELECT EXISTS (SELECT 1 FROM public.feedback_threads'
      || ' WHERE device_id = $1 AND user_id IS NOT NULL AND user_id <> $2)'
      INTO other_owner USING p_device_id, uid;
  END IF;
  IF other_owner THEN
    DELETE FROM public.tracked_bets
     WHERE pick_id = p_pick_id AND device_id = p_device_id AND user_id = uid;
    RETURN;
  END IF;
  DELETE FROM public.tracked_bets
   WHERE pick_id = p_pick_id AND device_id = p_device_id
     AND (user_id = uid OR user_id IS NULL);
END $fn$;
REVOKE ALL ON FUNCTION public.untrack_tracked_bet(text, bigint) FROM PUBLIC, anon;
GRANT EXECUTE ON FUNCTION public.untrack_tracked_bet(text, bigint)
    TO postgres, authenticated, service_role;

-- Anon may read only site_public_record and execute only the two loggers
-- plus save_device_push_token.
-- An extension function installed in public would trip this. Stop and ask
-- rather than widening the revoke.
DO $guard$
DECLARE bad text;
BEGIN
  SELECT string_agg(c.relname, ',') INTO bad
    FROM pg_class c
   WHERE c.relnamespace = 'public'::regnamespace
     AND c.relkind IN ('r', 'v', 'm', 'p', 'f')
     AND c.relname <> 'site_public_record'
     AND (has_table_privilege('anon', c.oid, 'SELECT')
          OR has_table_privilege('anon', c.oid, 'INSERT')
          OR has_table_privilege('anon', c.oid, 'UPDATE')
          OR has_table_privilege('anon', c.oid, 'DELETE'));
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still has table privs on: %', bad;
  END IF;
  SELECT string_agg(p.oid::regprocedure::text, ',') INTO bad
    FROM pg_proc p
   WHERE p.pronamespace = 'public'::regnamespace
     AND p.proname NOT IN ('log_app_error', 'log_app_timings', 'save_device_push_token')
     AND has_function_privilege('anon', p.oid, 'EXECUTE');
  IF bad IS NOT NULL THEN
    RAISE EXCEPTION 'anon still executes: %', bad;
  END IF;
  IF NOT has_table_privilege('anon', 'public.site_public_record', 'SELECT') THEN
    RAISE EXCEPTION 'anon lost site_public_record';
  END IF;
  IF NOT has_table_privilege('authenticated', 'public.games', 'SELECT') THEN
    RAISE EXCEPTION 'authenticated lost games';
  END IF;
END $guard$;

NOTIFY pgrst, 'reload schema';
COMMIT;
"""


def undo_a_sql() -> str:
    lines = [HEADER, "-- Undo step A only. Run undo B first if B was applied.\n",
             "-- site_public_record is kept.\n", "BEGIN;\n"]
    for name in STEP_A_RELATIONS + STEP_A_HYGIENE:
        lines.append(f"GRANT SELECT ON public.{name} TO anon;\n")
    lines.append(
        "GRANT SELECT (lock_key, kind, sent_at) ON public.push_sent TO anon;\n")
    for name, table, roles in STEP_A_POLICIES:
        lines.append(f'ALTER POLICY "{name}" ON public.{table} TO {roles};\n')
    lines.append(_regrant_functions(STEP_A_FUNCTIONS, STEP_A_PUBLIC_FUNCTIONS))
    lines.append("NOTIFY pgrst, 'reload schema';\nCOMMIT;\n")
    return "".join(lines)


def undo_b_sql() -> str:
    lines = [HEADER,
             "-- Undo step B. Keeps tracked_bets.user_id and its index.\n",
             "-- Does not give anon back the step A relations.\n",
             "--\n",
             "-- SEQUENCE GRANTS ARE NOT IN THIS FILE. Anon held rwU on 67\n",
             "-- sequences, not on every sequence in public. GRANT ON ALL\n",
             "-- would open the other 16. The documented rollback for\n",
             "-- sequences, and for any grant this file does not name, is:\n",
             "--   python -m scripts.restore_acl_from_snapshot --label pre_step_a_20261118\n",
             "-- which reads ops.acl_snapshot taken before step A.\n",
             "BEGIN;\n",
             "-- Inverse of the default-privilege statements in step B.\n",
             "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public\n",
             "    GRANT ALL ON TABLES TO anon;\n",
             "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public\n",
             "    GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO anon;\n",
             "ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public\n",
             "    GRANT EXECUTE ON FUNCTIONS TO PUBLIC, anon;\n",
             "-- The plain grant sweep revokes anon on new tables again.\n",
             "-- Run it after this undo if that 2026-09-03 default should stay.\n"]
    for name in STEP_B_RELATIONS + STEP_B_HYGIENE:
        if name == "tracked_bets":
            continue
        lines.append(f"GRANT SELECT ON public.{name} TO anon;\n")
    lines.append(
        "GRANT DELETE, INSERT, REFERENCES, SELECT, TRIGGER "
        "ON public.tracked_bets TO anon, authenticated;\n")
    lines.append(
        "DROP FUNCTION IF EXISTS public.untrack_tracked_bet(text, bigint);\n")
    for name, table, roles in STEP_B_POLICIES:
        lines.append(f'ALTER POLICY "{name}" ON public.{table} TO {roles};\n')
    lines.append(
        'DROP POLICY IF EXISTS tracked_bets_owner_insert ON public.tracked_bets;\n'
        'DROP POLICY IF EXISTS tracked_bets_owner_select ON public.tracked_bets;\n'
        'DROP POLICY IF EXISTS tracked_bets_owner_delete ON public.tracked_bets;\n'
        'CREATE POLICY "anon insert tracked_bets" ON public.tracked_bets\n'
        "  FOR INSERT TO anon, authenticated WITH CHECK (true);\n"
        'CREATE POLICY "anon delete tracked_bets" ON public.tracked_bets\n'
        "  FOR DELETE TO anon, authenticated USING (true);\n")
    lines.append(_regrant_functions(
        STEP_B_STATS_FUNCTIONS + STEP_B_DEVICE_FUNCTIONS,
        STEP_B_PUBLIC_FUNCTIONS))
    lines.append("NOTIFY pgrst, 'reload schema';\nCOMMIT;\n")
    return "".join(lines)


def assert_counts() -> None:
    if len(STEP_A_RELATIONS) != 25:
        raise RuntimeError(len(STEP_A_RELATIONS))
    if len(STEP_A_HYGIENE) != 1:
        raise RuntimeError(STEP_A_HYGIENE)
    if len(STEP_A_POLICIES) != 15:
        raise RuntimeError(len(STEP_A_POLICIES))
    if len(STEP_A_FUNCTIONS) != 28:
        raise RuntimeError(len(STEP_A_FUNCTIONS))
    if len(STEP_A_PUBLIC_FUNCTIONS) != 17:
        raise RuntimeError(len(STEP_A_PUBLIC_FUNCTIONS))
    if len(STEP_B_RELATIONS) != 72:
        raise RuntimeError(len(STEP_B_RELATIONS))
    if len(STEP_B_HYGIENE) != 19:
        raise RuntimeError(len(STEP_B_HYGIENE))
    if len(STEP_B_POLICIES) != 52:
        raise RuntimeError(len(STEP_B_POLICIES))
    if len(STEP_B_STATS_FUNCTIONS) != 41:
        raise RuntimeError(len(STEP_B_STATS_FUNCTIONS))
    if len(STEP_B_DEVICE_FUNCTIONS) != 11:
        raise RuntimeError(len(STEP_B_DEVICE_FUNCTIONS))
    if STEP_A_PUBLIC_FUNCTIONS - set(STEP_A_FUNCTIONS):
        raise RuntimeError("public function missing from step A")
    overlap = set(STEP_A_RELATIONS) & set(STEP_B_RELATIONS + STEP_B_HYGIENE)
    if overlap:
        raise RuntimeError(overlap)


assert_counts()
