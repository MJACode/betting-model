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
  * Failures are logged and swallowed. A view refinement must never take down
    settlement or scoring — the same rule run_ledger follows.
"""
from __future__ import annotations
from pathlib import Path

from loguru import logger

from data.db import get_connection

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

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
    "track_record_clv_no_vig_2026_09_14.sql",
    # 2026-09-15 (mike): MLB game-market gate log. Live default (despite
    # no §7 cut) — does not ALTER picks; the scorer writes NONE itself.
    "add_game_market_gate_2026_09_15.sql",
    # 2026-09-19: daily model-quality findings (one-sided slates, fade
    # concentration, CLV/ROI, volume). Report only; never pauses.
    "add_model_quality_checks_2026_09_19.sql",
]


def apply_view_migrations(conn=None) -> int:
    """Run each ACTIVE_MIGRATIONS file. Returns how many applied cleanly.
    Never raises — observability and schema polish must not break the pass."""
    owns = conn is None
    applied = 0
    try:
        conn = conn or get_connection()
    except Exception as exc:                      # no DB — nothing to do
        logger.warning(f"View migrations skipped (no connection): {exc}")
        return 0

    try:
        for name in ACTIVE_MIGRATIONS:
            path = MIGRATIONS_DIR / name
            if not path.exists():
                logger.warning(f"View migration missing on disk: {name}")
                continue
            try:
                # conn.execute, NOT conn.executescript: executescript splits on
                # ";" and would shred a dollar-quoted DO $$...$$ block into
                # fragments at every semicolon in its body. Each migration here
                # must therefore be a SINGLE statement (a DO block), which is
                # also what makes the idempotency check atomic.
                conn.execute(path.read_text(encoding="utf-8"))
                conn.commit()
                applied += 1
                logger.info(f"View migration OK: {name}")
            except Exception as exc:
                # Roll back so one bad migration cannot poison the next.
                try:
                    conn.rollback()
                except Exception:
                    pass
                logger.error(f"View migration FAILED ({name}): {exc}")
    finally:
        if owns:
            try:
                conn.close()
            except Exception:
                pass
    return applied


if __name__ == "__main__":
    n = apply_view_migrations()
    print(f"{n}/{len(ACTIVE_MIGRATIONS)} view migration(s) applied")
