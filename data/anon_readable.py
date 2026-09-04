"""What the app is allowed to READ, named once.

WHY THIS FILE EXISTS. `ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON TABLES FROM
anon, authenticated` (scripts/apply_anon_grants.py) stops every NEW table and
view in `public` from arriving with Supabase's default `anon=arwdDxtm`. That
closes the recurrence that produced `model_artifacts` -- created on demand by
models/trainer.py, it came back with the full grant between two sweeps of the
schema hours apart.

It also introduces a trap, and this file is the guard for it: a new table or
view the APP needs to read now arrives with no SELECT either, and that fails
SILENTLY. PostgREST answers a permission error, the client folds it into
`error`, and the screen renders empty with nothing in any log near the cause --
the exact failure shape §7 keeps warning about.

So the read surface is declared here rather than discovered in production.
tests/test_anon_readable.py parses every `.from('...')` in mobile/src and fails
if it names something absent from these lists, which turns "someone forgot the
GRANT" from a silent empty screen into a red test before the PR opens.

KEEP IT IN SYNC BY ADDING TO IT, not by loosening the test: add the relation
here AND re-run `python -m scripts.apply_anon_grants` so the grant exists.

Measured 2026-09-03: all 34 relations below are readable today, so applying the
grants is a no-op on the current schema. The mechanism is for what comes next.
"""

from __future__ import annotations

# Readable by anon AND authenticated -- the board, the odds, the public record.
# Nothing here is user-scoped; anon is how the app reads before sign-in.
ANON_READABLE: tuple[str, ...] = (
    # ── tables ──────────────────────────────────────────────────────────────
    "device_push_tokens",
    "fighters",
    "game_weather",
    "games",
    "lineup_slots",
    "model_action_thresholds",
    "model_registry",
    "odds",
    "parlay_correlations",
    "parlay_track_record",
    "picks",
    "player_game_log",
    "player_handedness",
    "player_news",
    "player_prop_odds",
    "player_savant_stats",
    "tracked_bets",
    "ufc_fight_log",
    "umpires",
    # ── views ───────────────────────────────────────────────────────────────
    "v_fighter_season_totals_ufc",
    "v_latest_dk_odds",
    "v_latest_odds_all_books",
    "v_latest_prop_odds_all_books",
    "v_live_game_state_latest",
    "v_model_full_outcome_picks",
    "v_model_full_outcome_record",
    "v_opening_signal_slices",
    "v_opening_vs_live",
    "v_player_season_totals_mlb",
    "v_player_season_totals_nba",
    "v_player_season_totals_wnba",
    "v_public_track_record",
    "v_public_track_record_daily",
)

# Readable ONLY by a signed-in user. `anon` has never held SELECT on
# subscriptions -- its grant was write-only until 2026-09-03, so revoking the
# writes emptied the entry and Postgres dropped it. Billing state should not be
# readable before sign-in, so that is the right shape and is pinned here.
AUTHENTICATED_ONLY: tuple[str, ...] = (
    "subscriptions",
)


def all_readable() -> tuple[str, ...]:
    """Every relation the app may read, either role."""
    return ANON_READABLE + AUTHENTICATED_ONLY

# ── RPCs ────────────────────────────────────────────────────────────────────
# The same story for functions. `ALTER DEFAULT PRIVILEGES ... REVOKE ALL ON
# FUNCTIONS` closes every NEW function in `public`, and a new RPC the app calls
# then 404s through PostgREST -- the same silent failure as a missing SELECT,
# one layer up.
#
# THE LIST IS NOT WHAT A GREP FOR `.rpc('...')` RETURNS, and that is the trap
# worth writing down. Four call sites in mobile/src/lib/queries.ts build the
# name at runtime:
#
#     const fn = sport === 'NFL' ? 'player_window_totals_nfl'
#                                : 'player_window_totals_ncaaf';
#     await supabase.rpc(fn, {...})
#
# A literal grep finds 17 names; the real surface is 24. Sweeping on the literal
# list would have revoked EXECUTE on eight functions the app reaches through a
# ternary and broken the NBA, WNBA, NCAAF and NFL stats screens -- silently.
# tests/test_anon_readable.py resolves both forms.
RPC_ANON_CALLABLE: tuple[str, ...] = (
    # per-sport stats, selected by ternary as well as by literal
    "player_recent_games_mlb",
    "player_recent_games_nba",
    "player_recent_games_ncaaf",
    "player_recent_games_nfl",
    "player_recent_games_wnba",
    "player_season_stat_values_mlb",
    "player_season_stat_values_nba",
    "player_season_stat_values_ncaaf",
    "player_season_stat_values_nfl",
    "player_season_stat_values_wnba",
    "player_window_totals_mlb",
    "player_window_totals_nba",
    "player_window_totals_ncaaf",
    "player_window_totals_nfl",
    "player_window_totals_wnba",
    "fighter_window_totals_ufc",
    "team_stats_board",
    # custom model builder
    "custom_model_backtest",
    "custom_model_picks",
    # in-app feedback -- SECURITY DEFINER, device-keyed, so callable pre-sign-in
    "feedback_mark_read",
    "feedback_messages_for_thread",
    "feedback_submit",
    "feedback_threads_for_device",
    "feedback_unread_count",
    # NOT called by the app, but REQUIRED by it: custom_model_picks and
    # custom_model_backtest are SECURITY INVOKER and both call this helper, so
    # the CALLER needs EXECUTE. Revoking it breaks the custom-model screen with
    # nothing in the app's own call log to explain why.
    "_jsonb_text_array",
)

# Functions that exist and are deliberately NOT callable by anon/authenticated.
# Listed so the revoke is a decision on the record rather than a side effect.
RPC_REVOKE: tuple[str, ...] = (
    # the support-side reply path; already anon-revoked, authenticated too
    "feedback_reply",
    # superseded by has_app_access()/my_access(), which cannot see a Whop-paid
    # member (data/supabase_schema.sql). Nothing in the repo or the app calls it.
    "has_active_subscription",
)

# LEFT ALONE, deliberately: log_picks_changes(). It returns `trigger`, so
# PostgREST will not expose it and Postgres does not check EXECUTE when a
# trigger fires -- revoking gains nothing and risks the picks_log audit trail
# that made this week's deletes recoverable. An asymmetric bet with no upside.
RPC_LEFT_ALONE: tuple[str, ...] = (
    "log_picks_changes",
)

# `my_access` is called by mobile/src/lib/discord.ts and DOES NOT EXIST in
# production -- it is defined only in
# data/migrations/add_discord_link_and_whop_memberships.sql, which has never
# been applied. Deliberately absent from RPC_ANON_CALLABLE: granting on a
# missing function errors. That migration already carries its own explicit
# GRANT, so it stays correct once the default privilege is revoked. Recorded in
# docs/followups.md.
RPC_MISSING_IN_PROD: tuple[str, ...] = (
    "my_access",
)

