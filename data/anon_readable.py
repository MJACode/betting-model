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
