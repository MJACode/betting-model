"""
Apply idempotent view migrations from the running worker.

WHY THIS EXISTS. The Supabase MCP available to development sessions is
read-only, and setup_database() only runs at first-time setup — so a change to
a VIEW has no path into production without someone opening the SQL editor by
hand. The same gap is why tracking/run_ledger.py creates its own table with
CREATE TABLE IF NOT EXISTS on every start.

This closes it for views: the migrations listed below are written to be
idempotent (each checks whether it has already been applied and skips), so the
pipeline can run them on every pass and the change lands on the first run after
a merge.

Deliberate constraints:

  * ONLY files named here are executed, never a directory glob. A migrations
    directory is an archive of history — replaying all of it on every pass
    would be both slow and dangerous. Removing a file from this list once it is
    applied everywhere is the intended lifecycle.
  * Every migration must be safe to run repeatedly. A file that raises on a
    second run would red the pipeline forever.
  * Every migration must be a SINGLE statement -- in practice a DO $$...$$
    block. See the comment at the execute() call for why.
  * Failures are logged and swallowed here (this function does not raise).
    The step reports them and returns False; later steps still run. A view
    refinement must never take down settlement or scoring — the same rule
    run_ledger follows.
  * An already-applied file must not take AccessExclusiveLock. PostgreSQL
    locks first and checks IF NOT EXISTS second, so the SQL itself returns
    on a catalog read. A lock that is still required (a real change, under
    contention) uses a short lock_timeout and a few retries, then fails
    the step with the filename in the error.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from data.db import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# How long one attempt will sit in the lock queue. statement_timeout on the
# worker role is 2min and lock_timeout is 0, so an AccessExclusive waiter
# used to block new readers for the whole two minutes (lock-queue fairness)
# and pin every later lock request behind it. Five seconds is long enough
# for a short transaction to finish and short enough that a miss releases
# the queue. The work AFTER the lock is acquired still has the server
# statement_timeout; this does not cancel a real index build.
# Retries are only lock_timeout (55P03) and deadlock (40P01). A statement
# timeout (57014) means the file already held its lock for the full 2min,
# so it is not run again.
MIGRATION_LOCK_TIMEOUT = "5s"
# Same value. The helper and the lock-noop tests use this name.
LOCK_TIMEOUT = MIGRATION_LOCK_TIMEOUT
LOCK_ATTEMPTS = 3
# Sleep after attempt 1 and attempt 2. The third failure does not sleep.
LOCK_BACKOFF_S = (0.5, 1.5)

# 55P03 lock_not_available (lock_timeout), 40P01 deadlock_detected.
_TRANSIENT_PGCODES = frozenset({"55P03", "40P01"})
_STATEMENT_TIMEOUT_PGCODE = "57014"

# Idempotent view migrations to keep applied. Order matters only if one
# depends on another.
ACTIVE_MIGRATIONS: list[str] = [
    "require_price_for_published_units.sql",
    "units_precision_for_public_record.sql",
    "add_message_id_to_push_sent.sql",
    "add_results_snapshots.sql",
    "add_player_news.sql",
    # 2026-09-08: Kalshi prop ladders. Recording only -- nothing scores off it.
    # A reference cannot be graded until a record exists, and Kalshi NFL prop
    # settled history reaches back only to 2026 preseason, so every week without
    # this is a week of evidence that cannot be recovered afterwards.
    "add_kalshi_prop_ladders.sql",
    # 2026-09-10 (session 280, mike): Kalshi NCAAF GAME markets -- winner,
    # total and spread ladders. Recording only. The 13-book search found one
    # number across every bookmaker; an exchange price is the one kind of
    # college number that record has never held.
    "add_kalshi_game_markets.sql",
    # 2026-09-11 (session 280): the event-code -> games-row join for the table
    # above, refreshed by the recorder after every snapshot.
    "add_kalshi_ncaaf_events.sql",
    # 2026-09-12 (session 287): CFBD NCAAF play-by-play. The states corpus the
    # live engine was trained on lived only as gitignored parquet on one
    # laptop, and the laptop that needs it for the 2025 in-play replay has no
    # CFBD key. The worker fetches, this table carries it, any machine reads.
    "add_ncaaf_plays.sql",
    # 2026-09-12: int32 was an arbitrary ceiling on a third-party feed's
    # numbers, and Postgres does not name the column when one overflows.
    "widen_ncaaf_plays_ints.sql",
    # 2026-09-12: BIGINT was not enough either -- a CFBD value exceeds 2^63.
    # NUMERIC has no ceiling, which ends the guessing rather than raising it.
    "ncaaf_plays_numeric_not_bigint.sql",
    # 2026-09-19 (Delaware): the game state the NCAAF live loop priced on,
    # one row per change. The loop bet a 0-0 state 15s before the scoreboard
    # reported the touchdown the book had already priced, and the state it
    # saw was never stored -- so the same question could not be asked of the
    # other bets. Beside the in-play quotes in `odds`, keyed by game and time.
    "add_ncaaf_live_states.sql",
    # 2026-09-10 (session 280, mike): point-in-time ISSUED weather forecasts
    # for NCAAF games, the train/serve repair for the totals model's wx_*
    # features (it trained on reanalysis and is served a forecast).
    "add_game_weather_issued.sql",
    # 2026-09-20: the hourly Open-Meteo ISSUED series per NFL stadium, the
    # content of nfl/data/weather_cache (44 files on one laptop, the store
    # tests/test_everything_in_supabase.py had failed on since 2026-09-12).
    # Written by data/ingestors/nfl_weather_cache_import.py.
    "add_nfl_stadium_weather_hourly.sql",
    # 2026-09-20: per-game NHL team / goalie / skater logs from the NHL's free
    # stats API. The NHL models read one SEASON-FINAL row per goalie and
    # carried-forward team rates; an as-of-date feature needs the games it is
    # summed from. Written by data/ingestors/nhl_game_logs.py.
    "add_nhl_game_logs.sql",
    # 2026-09-21: goals by period, one row per game, from the same archive the
    # NHL opening/closing lines came from. The ingestor validated its parse on
    # them and discarded them; they settle the first-period and regulation
    # markets. Written by data/ingestors/nhl_sbr_archive.py.
    "add_nhl_period_scores.sql",
    # 2026-09-09 (mike: "remove DK only - we want best lines for us
    # regardless"): picks carry the price each pick was DECIDED at
    # (decision_*); the graded matview, the record views and the custom-model
    # RPCs cut and grade there. Runs BEFORE the two view files below, which now
    # cut on those columns. Applied to production by hand the same day, before
    # the code that writes the columns deployed; every guard then no-ops.
    "decide_on_best_price_2026_09_09.sql",
    "score_off_any_book_line_2026_09_12.sql",
    # 2026-09-02: the record views read the graded matview instead of
    # re-grading 126k picks per read (the Record tab was timing out at 8s).
    # Its daily-view branch was removed on 2026-09-04 -- see below.
    "track_record_reads_graded_matview.sql",
    # 2026-09-04: the published record starts at the official live date, in BOTH
    # views. This must run AFTER track_record_reads_graded_matview, which used to
    # own the daily view and reverted it to the 2026-04-14 window on every pass.
    "live_record_start_views_2026_09_01.sql",
    # 2026-09-12: a settled pick stays in the published record whatever the
    # model does next. Drops `paused` and the re-application of today's
    # thresholds from both published views — a pause had erased 55 settled
    # NCAAF bets overnight. MUST run after live_record_start_views_2026_09_01,
    # which owns these two views and would otherwise restore the paused clause
    # on the next pass.
    "settled_record_survives_a_pause_2026_09_12.sql",
    # 2026-09-05: one row per pick, enforced by a unique index. No-ops (with a
    # NOTICE) until scripts/dedupe_picks.py has cleared the 63 rows a released
    # lock wrote, then creates the index on the next pass.
    "picks_one_row_per_pick.sql",
    # 2026-09-13 (Matt / Reviewer #699 A2): the index above keyed only on
    # player_id, so nfl_prop_market's null-player_id rows collapsed per side
    # and DAL@NYG aborted the card. Widens with player_key + prop_market
    # (publish_keys.KEY_PARTS). MUST run after picks_one_row_per_pick.sql,
    # which owns the original name and would otherwise leave the narrow index.
    "widen_picks_one_row_per_pick_2026_09_13.sql",
    # 2026-09-07: the promoted calibration slot, corrected on the day the
    # decision path reached player props. One-off; guards on "every promoted row
    # carries its own method" and skips forever after.
    "promotions_endorsed_only_2026_09_07.sql",
    # 2026-09-07: nine NCAAF games rows named an FCS visitor as the FBS school
    # its name starts with; 27 pick labels carried it. Renames the visitor,
    # writes CFBD's final onto the row so the same pass settles the six live
    # BETs, and corrects each label once. Every step guards on its own
    # property and no-ops forever after.
    "ncaaf_fcs_visitor_names_2026_09_07.sql",
    # 2026-09-14: UL Monroe 2026-09-19 has two games rows for one matchup —
    # CFBD's SE Louisiana vs The Odds API's Southeastern Louisiana Lions.
    # Consolidates children onto the CFBD id and deletes the live alias.
    # The resolver map that stops a new alias row is in config.py in the
    # same PR. Guards on both names still being the measured split; no-ops
    # after once. Never deletes a pick.
    "ncaaf_se_louisiana_ul_monroe_alias_2026_09_14.sql",
    # 2026-10-16: five Citadel matchups (2023-09-02 to 2026-10-17) each have a
    # CFBD "The Citadel" row and a live "Citadel Bulldogs" alias the resolver
    # minted because The Odds API drops the article. Moves odds, latest_odds
    # and weather onto the CFBD id and deletes the unscored alias. Map entry
    # in config.py in the same PR. Guards on the measured names; no-ops after
    # once. Never deletes a pick.
    "ncaaf_citadel_alias_2026_10_16.sql",
    # 2026-09-07: three MLB games rows that are the previous night's game filed
    # again under its UTC date. Relabelled data_source='duplicate_utc', never
    # deleted or scored (five voided picks point at them). No-ops after once.
    "mlb_phantom_utc_rows_2026_09_07.sql",
    # 2026-09-08: partial index for the scorer's housekeeping sweep, which
    # seq-scanned 137k open non-BET rows every pass. Created on production
    # CONCURRENTLY the same night; this is the recoverable copy (IF NOT EXISTS).
    "picks_open_nonbet_index_2026_09_08.sql",
    # 2026-09-09: player_recent_games_* gain p_teams so the Stats board can ask
    # for one slate's players instead of the league (54,687 NCAAF rows against a
    # 1,000-row cap). Filters on the rn=1 team, which is what the board groups
    # to -- a request-level team filter would filter GAMES and truncate a traded
    # player's window. Applied to production the same evening; this is the
    # recoverable copy, and it guards on its own property so it runs once.
    "player_recent_games_slate_teams.sql",
    # 2026-09-20 (Matt): the Stats tab's H2H window and the player page's
    # "vs OPP · last 2 seasons" card — five player_h2h_stat_values_* RPCs, one
    # row per slate player carrying that player's values against the team he is
    # about to play. MLB/NBA/WNBA derive the opponent by joining `games` (their
    # logs have no opponent column); NFL/NCAAF read it off the log row. Guards
    # on all five existing, so the DDL fires once and skips forever after —
    # this file runs on every refresh pass and each DDL statement forces a
    # PostgREST schema reload.
    "add_player_h2h_stat_values_rpcs.sql",
    # 2026-10-05 (Matt): the player page's "WRs vs ATL" card — how other
    # players at the same position have done against tonight's opponent, with
    # the defence's league rank. NFL first (the only log with pos + opponent);
    # MLB and the basketball/NCAAF position ingest follow. Guards on the
    # function existing, so the DDL fires once.
    "add_position_vs_opponent_nfl.sql",
    # 2026-10-05 (Matt): phase 2 — MLB batters by lineup spot (1-3/4-6/7-9)
    # and starting pitchers, same row shape as the NFL function.
    "add_position_vs_opponent_mlb.sql",
    # 2026-10-06 (Matt, phase 3): NBA/WNBA/NCAAF positions for the same card,
    # written by data/ingestors/player_positions_ingestor.py. Guards on the
    # table existing.
    "add_player_positions.sql",
    # 2026-10-06 (Matt, phase 3): the card's NBA / WNBA / NCAAF functions,
    # joining player_positions. MUST run after add_player_positions.sql.
    "add_position_vs_opponent_bball_ncaaf.sql",
    # 2026-09-14 (mike): leftover nfl_wind_totals opening_signals rows whose
    # picks were VOIDED 09-07 / DELETED 09-11 after MAX_FIRE_LEAD. Capture
    # stayed (ON CONFLICT DO NOTHING). Deletes captures with no standing
    # non-VOID BET; pins DEN@KC (pick_id 1969489). No-ops after once.
    # Lands on the next Railway ACTIVE_MIGRATIONS pass after merge (Step 0c2
    # / refresh_pass apply-view-migrations). Does not Discord re-announce.
    "drop_voided_nfl_wind_opening_signals_2026_09_14.sql",
    # 2026-09-14 (mike): same residue for nfl_prop_market — three captures
    # whose picks were in the 09-11 26-row delete (written 137-180h early vs
    # NFL_PROP_MAX_LEAD_HOURS=24). Deletes those exact lock_keys; standing
    # skip is lock_key_sql (KEY_PARTS), never player_id — that join false-
    # matched 3/2/2 other props on the same games. No Discord re-announce.
    "drop_voided_nfl_prop_market_opening_signals_2026_09_14.sql",
    # 2026-09-14: ESPN injury `date` on injuries.status_ts. The NFL prop
    # Out/Doubtful veto compares this to the quote's snapshot_at; NULL
    # fails open. ADD COLUMN IF NOT EXISTS.
    "add_injuries_status_ts_2026_09_14.sql",
    # 2026-09-22 (mike): was a pick actually placeable at the book? One row
    # per pick, written by scripts/mark_placeable.py, for the opener's fresh
    # numbers ("NEW 0m"): a book error is the model's best case if it can be
    # placed, a feed ghost if not, and only a person at the book can say.
    # CREATE TABLE IF NOT EXISTS + REVOKE anon/authenticated + RLS.
    "pick_placement_checks_2026_09_22.sql",
    # 2026-09-14 (mike): NOTHING AUTOPAUSES. The 250-bet review wrote
    # mlb_prop_batter_runs and mlb_prop_pitcher_k into model_auto_pauses
    # on 2026-09-11 with no approval. Measured: those two were the only
    # rows. Clears the table. After this pass they are live again unless
    # listed in config.PAUSED_MODELS. The review still reports; it never
    # writes this table.
    "clear_unauthorized_auto_pauses_2026_09_14.sql",
    # 2026-09-14: CLV is no-vig two-way close, sharp book when present.
    # Columns first so the view filter cannot run against a missing clv_method.
    "add_clv_method_2026_09_14.sql",
    # 2026-10-08 (mike): grade CLV at the price taken. picks.clv_bet_book, and
    # the graded_at_dk_legacy stamp on rows graded at DraftKings although taken
    # elsewhere, which _backfill_clv re-measures once. MUST run after
    # add_clv_method (it reads clv_method). Guarded: the no-op pass is DML only.
    "clv_price_taken_2026_10_08.sql",
    "track_record_clv_no_vig_2026_09_14.sql",
    # 2026-09-28 (Matt via CoS; Michael-gated): a paused model keeps its real
    # verdict (scorer._paused_signal), so a paused BET can exist; it is not a
    # signal and stays out of both published views, keyed on the row's
    # 'model paused' marker. MUST run after track_record_clv_no_vig.
    "record_excludes_paused_rows_2026_09_28.sql",
    # 2026-09-15 (mike): MLB game-market gate log. Live default (despite
    # no §7 cut) — does not ALTER picks; the scorer writes NONE itself.
    "add_game_market_gate_2026_09_15.sql",
    # 2026-09-19: daily model-quality findings (one-sided slates, fade
    # concentration, CLV/ROI, volume). Report only; never pauses.
    "add_model_quality_checks_2026_09_19.sql",
    # 2026-09-23 (Matt): Discord is the board. The app joins this view to
    # decide which bets are still in the channel. VOID does not delete the
    # post. push_sent stays closed except lock_key + kind on the two
    # channel kinds. No Discord mutation.
    "discord_publish_state_2026_09_23.sql",
    # 2026-10-09: a void notice (push_sent kind discord_void) drops that lock
    # from v_discord_published while the notice is strictly newer, and widens
    # anon_read_discord_publish so the security_invoker subquery can see the
    # notice. Anon SELECT on push_sent is lock_key, kind, and sent_at (the
    # WHERE reads the stamp). message_id stays ungranted. The original
    # message is not deleted. Must run after discord_publish_state, which
    # returns early once the view text contains discord_void (its keyword
    # check) so the narrower definition is not put back on the next pass.
    "discord_void_notice_2026_10_09.sql",
    # 2026-09-26 (mike / Michael Alksninis): demote the ncaaf_over_under
    # Platt map promoted 2026-09-19 17:45 ET (a=1, b=-0.281555). The
    # decision goes back to the raw probability, which is ~0.650 at the
    # validated +8 gate. Pinned to that promotion so a later map is left
    # alone. Does not pause, does not move the 0.65 floor or the ±8 gate.
    "demote_ncaaf_over_under_platt_2026_09_26.sql",
    # 2026-09-28: NCAAF 2026 team board refresh cancelled at statement_timeout
    # (daily run 51e965f8023c4b0e86e03fe075af1f9c, 10:15:00Z). The closing-line
    # CTE seq-scanned odds because `bookmaker = 'draftkings' OR LIKE 'cfbd\_%'`.
    # Replaces team_stats_board_compute with per-game index probes. Guards on
    # the probe marker so the DDL runs once.
    "team_stats_board_line_probe_2026_09_28.sql",
    # 2026-09-30: MLB 2026 team board refresh cancelled at statement_timeout
    # (daily runs 873cb1fe2e1e487d975ae3367f219a3f and
    # fd57b13575f04d63b219134d62f434dc). The 09-28 probe still starts at the
    # newest in-play row because the commence cutoff is a timestamptz cast
    # on a text snapshot_at. Bounds the same index at commence. Must run
    # after team_stats_board_line_probe_2026_09_28, which owns the function
    # and would otherwise restore the unbounded scan on the next pass.
    "team_stats_board_commence_bound_2026_09_30.sql",
    # 2026-10-04 (mike): nfl_live_prop retired and its settled record struck
    # (config.RECORD_EXCLUSIONS). Patches the LIVE view text with one clause,
    # so it must run after every migration that owns the two record views.
    "record_strikes_nfl_live_prop_2026_10_04.sql",
    # 2026-10-09 (mike, "Count each fight once"): two UFC fights were bet
    # twice by ufc_total_rounds under two game ids each. The extra copies are
    # marked condition_status='DUPLICATE' (result untouched; no-ops after
    # once), and the two record views stop counting a marked copy. The view
    # patch reads the LIVE view text, so it runs after every owner above.
    "record_counts_each_event_once_2026_10_09.sql",
    "record_views_count_each_event_once_2026_10_09.sql",
    # 2026-10-12 (mike: buy the NFL in-game history): a source column on
    # nfl_odds_history and a ledger of paid calls, so the purchase resumes.
    "add_nfl_odds_history_source_and_pulls_2026_10_12.sql",
    # 2026-10-12 (mike: "5) yes"): the free data the NFL edge search fetched,
    # one gzipped row per file (scripts/nfl_research_backup.py).
    "add_nfl_research_data_backup_2026_10_12.sql",
    # 2026-10-14: units and the W-L are the same graded picks, at the price
    # the bet was taken at. Rewrites results_snapshots and drops the column
    # that counted a pick in the record and left it out of the units.
    # The view patch removes the one-model units zeroing. It reads the live
    # view, so it runs after every migration that owns that view.
    "recompute_snapshot_units_2026_10_14.sql",
    "home_run_units_follow_graded_profit_2026_10_14.sql",
    # 2026-10-14: 35 extra picks rows behind one Discord lock are marked
    # DUPLICATE (kept row untouched; none of the extras is a graded
    # WIN/LOSS/PUSH). Two unique indexes stop a second standing BET on a
    # publish lock and a second live row on the same side. Skips the
    # create, and does not raise, when a duplicate of that identity remains.
    "discord_post_one_pick_2026_10_14.sql",
    # 2026-10-14: the published record is the picks Discord still has.
    # Rewrites results_snapshots (W-L and stake_for units) and adds the
    # same lock to the two app views. Reads the live view text, so it
    # runs after every migration that owns those views, including the
    # duplicate-row pass above. Does not post.
    "published_picks_record_2026_10_14.sql",
    # 2026-10-16: the 03:50Z evening pass was still unfinished after the
    # deploy (the only open pipeline_runs row). Same aborted stamp as
    # run_ledger._abort_orphans, this run_id only, and only while it is
    # still unfinished. Boot closes the next one; this closes the one
    # already open. Does not touch picks, thresholds, or pauses.
    # Sits before clv_standard_v2: that file reads the live view. Anything
    # after clv must not recreate that view (tests/test_published_record.py).
    "abort_deploy_killed_evening_2026_10_16.sql",
    # 2026-10-14: same-book raw CLV is the headline; Pinnacle power de-vig
    # is the market-edge column. Recomputes rows not yet standard_v2 and
    # patches v_public_track_record. Reads the live view, so it runs after
    # every migration that owns that view. Does not touch units or pauses.
    "clv_standard_v2_2026_10_14.sql",
    # 2026-10-16: Build Your Own Model facts. Empty tables, anon SELECT,
    # catalog return on the second pass. Does not touch picks, the record
    # views, or a live model. Unapplied until the worker's next pass.
    # The 120h/24h windows are UNCONFIRMED and are not in this file.
    "byom_facts_schema_2026_10_16.sql",
]


@dataclass(frozen=True)
class ViewMigrationResult:
    """applied is how many files committed. failed is (filename, error)."""

    applied: int
    failed: tuple[tuple[str, str], ...] = ()

    @property
    def failed_names(self) -> tuple[str, ...]:
        return tuple(name for name, _err in self.failed)


def _is_transient_lock_error(exc: BaseException) -> bool:
    """True for a lock timeout (55P03) or a deadlock (40P01) only.

    A statement timeout (57014, "canceling statement due to statement
    timeout") is NOT retried: the statement got its lock and ran for the
    whole server statement_timeout, and running it twice more would hold
    that lock for three times as long. Anything else (missing column,
    syntax, a guard that raised) fails the file on the first attempt too.
    Retrying those would hide a real migration bug behind three identical
    errors.
    """
    code = getattr(exc, "pgcode", None)
    if code in _TRANSIENT_PGCODES:
        return True
    if code == _STATEMENT_TIMEOUT_PGCODE:
        return False
    # No SQLSTATE (a wrapped error): only the lock_timeout wording retries.
    # "statement timeout" also contains the words "timeout" but not
    # "lock timeout", so it does not match.
    return "lock timeout" in str(exc).lower()


def format_view_migration_failure(
    applied: int,
    total: int,
    failed: tuple[tuple[str, str], ...] | list[tuple[str, str]],
) -> str:
    """The line step_apply_view_migrations logs. pipeline_log keeps the last
    ERROR, truncated at 360 characters, so the filenames lead."""
    if not failed:
        return (
            f"✗ View migrations: {applied}/{total} applied — "
            f"FAILED: {total - applied} file(s) did not apply"
        )
    names = ", ".join(name for name, _err in failed)
    head = f"✗ View migrations: {applied}/{total} applied — FAILED: {names}"
    reason = " ".join(str(failed[0][1]).split())
    if reason:
        extra = f" — {reason[:120]}"
        if len(head) + len(extra) <= 320:
            head += extra
    return head


def _with_lock_timeout(sql: str) -> str:
    """The migration with its SET LOCAL lock_timeout in the SAME execute.

    data/db counts any statement that is not plainly a read as a write, so
    a SET LOCAL sent on its own marked the clean transaction dirty. A pooler
    drop during the migration then raised ConnectionLost (the file failed)
    instead of reconnecting and re-running it. Sent together, the
    connection is still clean when the statement starts, so a drop
    reconnects and replays BOTH: the replayed migration keeps its 5s
    lock_timeout instead of waiting behind the 2min statement_timeout on
    the new backend. SET LOCAL dies with the transaction, so a passed-in
    connection (the CLV backfill job) does not keep the short timeout
    after we return.
    """
    return f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}';\n{sql}"


def _apply_one(conn, name: str, sql: str) -> str | None:
    """Run one file. None means it committed. A string is the error that
    survived the retries. Never raises.

    `time.sleep` is looked up on each retry so a test can patch it. A
    default argument would bind the real sleep at import and ignore the patch.
    """
    last = ""
    for attempt in range(1, LOCK_ATTEMPTS + 1):
        try:
            # conn.execute, NOT conn.executescript: executescript splits on
            # ";" and would shred a dollar-quoted DO $$...$$ block into
            # fragments at every semicolon in its body. Each migration here
            # must therefore be a SINGLE statement (a DO block), which is
            # also what makes the idempotency check atomic. The only other
            # statement in this execute is the SET LOCAL in front of it.
            conn.execute(_with_lock_timeout(sql))
            conn.commit()
            return None
        except Exception as exc:
            try:
                conn.rollback()
            except Exception:
                pass
            last = str(exc)
            if attempt < LOCK_ATTEMPTS and _is_transient_lock_error(exc):
                delay = LOCK_BACKOFF_S[min(attempt - 1, len(LOCK_BACKOFF_S) - 1)]
                logger.warning(
                    f"View migration lock wait ({name}), "
                    f"attempt {attempt}/{LOCK_ATTEMPTS}: {exc}"
                )
                time.sleep(delay)
                continue
            logger.error(f"View migration FAILED ({name}): {exc}")
            return last
    return last


def apply_view_migrations(conn=None) -> ViewMigrationResult:
    """Run each ACTIVE_MIGRATIONS file. Never raises — observability and
    schema polish must not break the pass. The caller turns `failed` into
    the step's error line."""
    owns = conn is None
    applied = 0
    failed: list[tuple[str, str]] = []
    try:
        conn = conn or get_connection()
    except Exception as exc:                      # no DB — nothing to do
        logger.warning(f"View migrations skipped (no connection): {exc}")
        return ViewMigrationResult(0, (("(connection)", str(exc)),))

    try:
        for name in ACTIVE_MIGRATIONS:
            path = MIGRATIONS_DIR / name
            if not path.exists():
                logger.warning(f"View migration missing on disk: {name}")
                failed.append((name, "missing on disk"))
                continue
            err = _apply_one(conn, name, path.read_text(encoding="utf-8"))
            if err is None:
                applied += 1
                logger.info(f"View migration OK: {name}")
            else:
                failed.append((name, err))
    finally:
        if owns:
            try:
                conn.close()
            except Exception:
                pass
    return ViewMigrationResult(applied, tuple(failed))


if __name__ == "__main__":
    result = apply_view_migrations()
    print(f"{result.applied}/{len(ACTIVE_MIGRATIONS)} view migration(s) applied")
    if result.failed:
        print(format_view_migration_failure(
            result.applied, len(ACTIVE_MIGRATIONS), result.failed))
