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

import re

# Unquoted lower-case identifier: what every table in this repo is named, and
# narrow enough that nothing it matches can carry SQL. Used by lock_down_sql,
# which has to interpolate a table name it is sometimes handed at runtime.
_IDENT = re.compile(r"[a-z_][a-z0-9_]{0,62}")

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

# ── worker-only tables: the second lock ──────────────────────────────────────
# mike, 2026-09-04: "enable rls on those three tables."
#
# These three hold no app surface and are written only by the worker. Their
# anon/authenticated grants were revoked on 2026-09-03, which leaves ONE lock:
# an ACL. A hand-written `GRANT ... ON worker_jobs TO anon` in some future
# migration -- or a `GRANT ... ON ALL TABLES IN SCHEMA public`, which is how the
# grant arrived in the first place -- re-opens them with nothing behind it,
# because RLS is off and a table with RLS off applies no policy check at all.
#
# RLS with ZERO POLICIES is deny-all for any role that is neither the table
# owner nor BYPASSRLS. So enabling it means a re-granted ACL is no longer
# sufficient on its own: someone would also have to write a policy, which is
# hard to do by accident.
#
# MEASURED BEFORE ENABLING IT, because RLS with no policies denies everything
# and the failure mode is a worker that silently stops writing:
#
#   owner of all three                      postgres
#   postgres rolbypassrls                   true      (and owner, so twice over)
#   service_role rolbypassrls               true
#   the worker's actual connections         usename=postgres via Supavisor
#   views / matviews selecting from them    NONE
#   references in mobile/src                NONE
#   anon/authenticated privileges           NONE already
#
# So the worker is unaffected for two independent reasons, and there is no read
# path to break. `ALTER TABLE ... FORCE ROW LEVEL SECURITY` is deliberately NOT
# used: that is what would subject the owner to the policies and stop the
# worker dead.
WORKER_ONLY_TABLES: tuple[str, ...] = (
    # brand_assets joined on 2026-09-04: scripts/fetch_brand_avatar.py creates it
    # on demand and already carried its own hand-written REVOKE, so it has always
    # been this same shape -- a fixed name with a live create site.
    "brand_assets",
    "model_artifacts",
    # The 250-bet review's two tables. Created on demand by
    # tracking/threshold_review.ensure_schema, never read by the app -- the
    # pause is applied server-side by models/scorer.py through auto_paused().
    "model_auto_pauses",
    "odds_history_pulls",
    "threshold_reviews",
    "worker_jobs",
)

# Tables that must stay closed but have NO live create site under that exact
# name, so nothing recreates them and the admin sweep is the only place they
# need handling. mike, 2026-09-04: "do the remaining seven too."
#
# ALL SEVEN ARE EXTRACTED DATA, which is why they are locked rather than
# dropped: six are dated one-off backups from this week's repairs (sessions 185,
# 204 and 206) and a repair is only reversible while its backup exists, and
# nfl_odds_cache_backup holds 6,769 gzipped blobs of nfl/data/odds_cache -- the
# paid cache CLAUDE.md §1b names as still living outside Supabase, moved in on
# 2026-09-04. Whether any of them is still worth keeping is a RETENTION
# decision, and not one a grant change gets to make.
#
# A name here is checked against production by the admin script's read-back, so
# a table that gets dropped later shows up as a failure rather than rotting in
# this list.
ARCHIVE_TABLES: tuple[str, ...] = (
    "mlb_pitcher_stats_pre_rebuild_20260903",
    "mlb_team_stats_pre_rebuild_20260903",
    "nba_team_stats_pre_rebuild_20260903",
    "nfl_odds_cache_backup",
    "nhl_team_stats_pre_rebuild_20260903",
    "odds_pre_first_pitch_relabel_20260903",
    "wnba_team_stats_pre_rebuild_20260903",
)


def closed_tables() -> tuple[str, ...]:
    """Every table the admin sweep revokes and enables RLS on."""
    return WORKER_ONLY_TABLES + ARCHIVE_TABLES


# The roles PostgREST authenticates as. service_role is deliberately absent:
# the edge functions (including every billing path) use it, and the worker
# connects as postgres.
API_ROLES: tuple[str, ...] = ("anon", "authenticated")


def lock_down_sql(table: str) -> tuple[str, ...]:
    """The REVOKE + ENABLE RLS pair for a worker-only table, unconditionally.

    STATED ONCE AND CALLED FROM EACH CREATE SITE, not copied into three files.
    All three tables are created on demand by the code that writes them --
    tracking/job_queue.py, data/ingestors/odds_ingestor.py and
    models/trainer.py::_store_artifact -- so a one-off migration is undone by
    the next run against a database where the table does not yet exist. That is
    not hypothetical: `model_artifacts` came back with the full anon grant
    between two sweeps of the schema hours apart on 2026-09-03.

    PREFER lock_down() AT A WRITE-TIME CALL SITE. These statements are
    idempotent but they are NOT free: `ALTER TABLE ... ENABLE ROW LEVEL
    SECURITY` takes ACCESS EXCLUSIVE whether or not RLS is already on, and
    fires Supabase's pgrst_ddl_watch -- which makes PostgREST answer 503 to the
    whole app while it rebuilds its schema cache. That trap cost 11.6 hours of
    database time and ~3,600 forced reloads across seven modules on 2026-09-01
    (data/ddl_guard.py has the pg_stat_statements numbers). This function is for
    the admin script and the tests, where one extra reload is the point.
    """
    # THE IDENTIFIER IS VALIDATED BECAUSE IT IS NOT ALWAYS A LITERAL. Both
    # statements interpolate `table` into SQL, and one caller passes a value
    # straight from the command line: repair_bogus_first_pitch_labels.py's
    # --backup-table. psycopg2 cannot parameterise an identifier, so this is the
    # only place that check can live.
    if not _IDENT.fullmatch(table):
        raise ValueError(
            f"{table!r} is not a plain lower-case identifier, and it is "
            f"interpolated into SQL. Refusing to build a statement from it.")
    # Refusing an APP-READABLE table is the check that matters. RLS with no
    # policies denies anon regardless of the GRANT, so enabling it on something
    # the app reads renders an empty screen with a permission answer folded into
    # `error` -- the silent failure this whole module exists to prevent, one
    # layer down. Membership in the declared lists is NOT required, because the
    # repair script's backup table is named at runtime and is legitimately not
    # in any of them.
    if table in all_readable():
        raise ValueError(
            f"{table!r} is in the app's read surface. Enabling RLS with no "
            f"policies would deny anon regardless of its GRANT, so the app "
            f"would read an empty table. Remove it from ANON_READABLE first if "
            f"that is really the intent.")
    return (
        f"REVOKE ALL ON {table} FROM anon, authenticated",
        f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY",
    )


def lock_down(conn, table: str) -> tuple[str, ...]:
    """Apply lock_down_sql(table) only when the catalog says it is needed.

    Returns the statements actually executed -- empty when the table is already
    revoked and RLS-on, which is the steady state.

    THE GATE IS IN HERE RATHER THAN AT EACH CALL SITE so a new caller cannot
    forget it. data/ddl_guard.schema_is_current is one sub-millisecond indexed
    catalog SELECT that fails CLOSED: any doubt -- SQLite, a test shim, a role
    that cannot read the catalog -- returns False and the DDL runs exactly as it
    would have. So this can only ever remove redundant work.
    """
    from data.ddl_guard import schema_is_current

    if schema_is_current(conn, table, rls=True, revoked_from=API_ROLES):
        return ()
    stmts = lock_down_sql(table)
    for stmt in stmts:
        conn.execute(stmt)
    return stmts


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
    # The Teams board's compute-and-swap pair (2026-09-04, migration
    # cache_team_stats_board). team_stats_board_compute is the 31 s season
    # aggregate that used to BE team_stats_board(); refresh_team_stats_board
    # runs it and swaps the result into team_stats_board_cache. Both are
    # worker-only: the app calls team_stats_board(), which now reads the cache.
    # An anon caller holding EXECUTE on either would be free DB-CPU burn.
    "team_stats_board_compute",
    "refresh_team_stats_board",
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

