"""
run_pipeline.py — Master daily pipeline orchestrator.

Runs the full sequence each morning:
  07:00  injuries     — ESPN + MLB Stats API
  07:05  odds (open)  — The Odds API (DraftKings opening lines)
  07:10  mlb_stats    — pybaseball team + pitcher stats
  07:10  nhl_stats    — NHL API team + goalie stats
  07:20  scoring      — Generate BET/AVOID picks for today's games
  07:25  settle       — Settle yesterday's picks (after scores are final)

The script can be run manually or scheduled via cron / Windows Task Scheduler.

Usage:
    python run_pipeline.py                    # full daily run
    python run_pipeline.py --step injuries    # run one step
    python run_pipeline.py --step scoring
    python run_pipeline.py --step settle
    python run_pipeline.py --date 2025-04-15  # override date
    python run_pipeline.py --dry-run          # scoring preview only

Cron example (daily at 7:00 AM):
    0 7 * * * cd /path/to/betting-model && python run_pipeline.py >> logs/pipeline.log 2>&1

Windows Task Scheduler:
    Program: python
    Arguments: run_pipeline.py
    Start in: C:\\path\\to\\betting-model
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ── Logging Setup ─────────────────────────────────────────────────────────────

LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logger.remove()
sys.stdout.reconfigure(encoding="utf-8")
logger.add(sys.stdout, level="INFO", colorize=True,
           format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")
logger.add(LOG_DIR / "pipeline_{time:YYYY-MM-DD}.log",
           level="DEBUG", rotation="1 day", retention="30 days",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}")


# ── Imports (lazy to surface missing dependencies clearly) ────────────────────

def _import_step(step_name: str):
    """Import a pipeline step with clear error messages."""
    try:
        if step_name == "injuries":
            from data.ingestors.injury_ingestor import run_injury_ingestor
            return run_injury_ingestor
        elif step_name == "odds":
            from data.ingestors.odds_ingestor import run_odds_ingestor
            return run_odds_ingestor
        elif step_name == "mlb_stats":
            from data.ingestors.mlb_stats_ingestor import run_mlb_stats_ingestor
            return run_mlb_stats_ingestor
        elif step_name == "nhl_stats":
            from data.ingestors.nhl_stats_ingestor import run_nhl_stats_ingestor
            return run_nhl_stats_ingestor
        elif step_name == "scoring":
            from models.scorer import run_scorer
            return run_scorer
        elif step_name == "settle":
            from tracking.paper_tracker import settle_picks
            return settle_picks
        else:
            raise ValueError(f"Unknown step: {step_name}")
    except ImportError as exc:
        logger.error(f"Cannot import step '{step_name}': {exc}")
        logger.error("Run: pip install -r requirements.txt --break-system-packages")
        raise


# ── Pipeline Steps ────────────────────────────────────────────────────────────

def step_refresh_outcomes(run_date: str) -> bool:
    """Refresh mv_scored_pick_outcomes — the graded every-pick universe the
    mobile custom-model builder backtests against (custom_model_backtest /
    custom_model_picks RPCs). Runs right after settle so the day's finals are
    graded; CONCURRENTLY so readers never block (needs autocommit — REFRESH
    CONCURRENTLY refuses to run inside a transaction). Non-fatal: a failed
    refresh just leaves backtests one day stale."""
    try:
        from data.db import get_connection
        conn = get_connection()
        try:
            conn._conn.autocommit = True
            conn.execute(
                "REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_scored_pick_outcomes"
            )
            # Keep planner stats current so the RPCs hold their ~50ms plans.
            conn.execute("ANALYZE public.mv_scored_pick_outcomes")
        finally:
            conn.close()
        logger.success("✓ Scored-pick outcomes refreshed")
        return True
    except Exception as exc:
        logger.error(f"✗ Scored-pick outcomes refresh failed: {exc}")
        return False


def step_sync_thresholds(run_date: str) -> bool:
    """Mirror config.py thresholds → model_action_thresholds (drives the public
    track record + the mobile app's server-side action filter). Keeps the table
    from drifting from config; cheap (~51-row upsert)."""
    try:
        from data.threshold_sync import sync_action_thresholds
        n = sync_action_thresholds()
        logger.success(f"✓ Threshold sync: {n} models")
        return True
    except Exception as exc:
        logger.error(f"✗ Threshold sync failed: {exc}")
        return False


def step_prune_odds(run_date: str) -> bool:
    """
    Retention for line-shop (non-DraftKings) odds snapshots.

    Both odds tables are append-only, but nothing ever reads a non-DK row other
    than the newest one per book (the DISTINCT ON all-books views). At 5 books
    that unread history would grow ~2.7 GB/month, so this prunes it to a flat
    working set. draftkings + sbr_consensus are never touched, and today's rows
    are left alone so this can't race with an ingest. Non-fatal: a failed prune
    costs disk, never picks.
    """
    try:
        from data.prune_odds import run_prune_odds
        summary = run_prune_odds(run_date)
        total = sum(t["deleted"] for t in summary["tables"])
        logger.success(f"✓ Odds prune: {total:,} line-shop rows removed")
        return True
    except Exception as exc:
        logger.warning(f"⚠ Odds prune failed (non-fatal): {exc}")
        return True


def step_injuries(run_date: str) -> bool:
    fn = _import_step("injuries")
    try:
        result = fn(report_date=run_date)
        logger.success(f"✓ Injuries: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Injuries failed: {exc}")
        return False


def step_odds(run_date: str, snapshot_type: str = "open") -> bool:
    fn = _import_step("odds")
    try:
        result = fn(snapshot_type=snapshot_type, target_date=run_date)
        logger.success(f"✓ Odds ({snapshot_type}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Odds failed: {exc}")
        return False


def step_mlb_stats(run_date: str) -> bool:
    fn = _import_step("mlb_stats")
    try:
        year  = int(run_date[:4])
        result = fn(season=year, as_of_date=run_date)
        logger.success(f"✓ MLB stats: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ MLB stats failed: {exc}")
        return False


def step_health_check(run_date: str) -> bool:
    """
    Daily system health check — verifies every API feed / data table is fresh
    (odds, prop odds, MLB stats/bullpen/weather/logs, basketball local-job
    output, final scores, model artifacts, picks, settlement). Cadence-aware:
    offseason/off-day sports are SKIPPED. A CRITICAL stale feed fails this
    step so the Actions run shows red. Results are written to
    system_health_checks (anon-readable — query from Claude mobile).
    """
    try:
        from tracking.system_health import run_system_health
        result = run_system_health(run_date)
        if result["ok"]:
            logger.success(f"✓ System health: {result['warn']} warning(s), 0 critical")
            return True
        logger.error(f"✗ System health: {result['crit']} CRITICAL failure(s), "
                     f"{result['warn']} warning(s) — see system_health_checks")
        return False
    except Exception as exc:
        logger.error(f"✗ System health check failed to run: {exc}")
        return False


def step_bullpen(run_date: str) -> bool:
    """
    Ingest reliever appearances (bullpen workload) up through yesterday.
    Self-healing: catches up from the last ingested date, so a missed run
    backfills automatically. Feeds home/away_bullpen_ip_last1/3 — without
    this step the features read 0.0 ("fully rested") for every game, which
    biases the totals model low (the Apr–Jul 2026 outage).
    """
    try:
        from data.ingestors.mlb_stats_ingestor import run_bullpen_ingestor
        result = run_bullpen_ingestor(run_date)
        logger.success(f"✓ Bullpen workload: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Bullpen workload failed: {exc}")
        return False


def step_nhl_stats(run_date: str) -> bool:
    fn = _import_step("nhl_stats")
    try:
        year  = int(run_date[:4])
        month = int(run_date[5:7])
        # NHL seasons run Oct–Jun, labeled by ENDING year (Nov 2026 → 2027).
        season = year + 1 if month >= 10 else year
        result = fn(season=season, as_of_date=run_date)
        logger.success(f"✓ NHL stats: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NHL stats failed: {exc}")
        return False


def step_nhl_results(run_date: str) -> bool:
    """
    Ingest NHL final scores + regulation outcomes for the trailing few days.
    Must run BEFORE settlement — paper_tracker reads games.home_score, and
    the MLB statsapi score fetch in paper_tracker only covers MLB. No-ops
    cleanly in the offseason (no games). The NHL analog of step_ufc_results.
    """
    try:
        from data.ingestors.nhl_stats_ingestor import ingest_nhl_scores_for_date
        # run_date, not yesterday: window_days=3 walks backwards from here, so
        # today covers yesterday too, and only today's date can pick up a game
        # that finished this evening.
        n = ingest_nhl_scores_for_date(run_date)
        logger.success(f"✓ NHL results: {n} final games upserted")
        return True
    except Exception as exc:
        logger.error(f"✗ NHL results failed: {exc}")
        return False


def step_weather(run_date: str) -> bool:
    """Fetch and store weather data for today's games from Open-Meteo."""
    try:
        from data.ingestors.weather_ingestor import fetch_and_store_weather_for_date
        from data.db import get_connection
        conn = get_connection()
        try:
            result = fetch_and_store_weather_for_date(run_date, conn)
            conn.commit()
            logger.success(f"✓ Weather: {result}")
            return True
        finally:
            conn.close()
    except Exception as exc:
        logger.error(f"✗ Weather failed: {exc}")
        return False


def step_prop_odds(run_date: str, snapshot_type: str = "open") -> bool:
    """Fetch DK player prop lines for today's MLB games."""
    try:
        from data.ingestors.prop_odds_ingestor import run_prop_odds_ingestor
        result = run_prop_odds_ingestor(target_date=run_date, snapshot_type=snapshot_type)
        logger.success(f"✓ Prop odds ({snapshot_type}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Prop odds failed: {exc}")
        return False


def step_wnba_stats(run_date: str) -> bool:
    """Refresh WNBA team stats + player game logs (nba_api, LeagueID=10)."""
    try:
        from data.ingestors.wnba_stats_ingestor import run_wnba_stats_ingestor
        result = run_wnba_stats_ingestor(as_of_date=run_date)
        logger.success(f"✓ WNBA stats: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ WNBA stats failed: {exc}")
        return False


def step_wnba_prop_odds(run_date: str, snapshot_type: str = "open") -> bool:
    """Fetch DK WNBA player prop lines (points/reb/ast/threes/PRA)."""
    try:
        from data.ingestors.prop_odds_ingestor import run_wnba_prop_odds_ingestor
        result = run_wnba_prop_odds_ingestor(target_date=run_date, snapshot_type=snapshot_type)
        logger.success(f"✓ WNBA prop odds ({snapshot_type}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ WNBA prop odds failed: {exc}")
        return False


def step_wnba_game_log(run_date: str) -> bool:
    """Ingest WNBA games + player box scores for yesterday (feeds prop rolling stats)."""
    from datetime import datetime, timedelta
    yesterday = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        from data.ingestors.wnba_stats_ingestor import ingest_wnba_game_log_for_date
        result = ingest_wnba_game_log_for_date(yesterday)
        logger.success(f"✓ WNBA game log ({yesterday}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ WNBA game log failed: {exc}")
        return False


def step_wnba_results(run_date: str) -> bool:
    """
    Ingest WNBA final scores + player box scores from the ESPN hidden API for
    the trailing window (+ self-heal over recent NULL-score WNBA games), and
    rebuild the season team-stats snapshot from our own DB. Must run BEFORE
    settlement — WNBA game + prop picks settle from games / wnba_player_game_log,
    and nba_api (the local job's source) can't run in Actions. No-ops cleanly in
    the offseason. The WNBA analog of step_nhl_results / step_ufc_results.
    """
    try:
        from data.ingestors.wnba_results_ingestor import ingest_wnba_results
        result = ingest_wnba_results(run_date)
        logger.success(f"✓ WNBA results (ESPN): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ WNBA results failed: {exc}")
        return False


def step_nfl_results(run_date: str) -> bool:
    """
    Fill NFL final scores from the hosted nflverse games.csv. Must run BEFORE
    settlement — nfl_wind_totals picks (the §28 wind card, published by
    scripts/nfl_wind_publisher.py) settle through the generic game-level path
    off games scores. Skips the fetch entirely when no NFL games are pending
    (all of the off-season).
    """
    try:
        from data.ingestors.nfl_results_ingestor import run_nfl_results_ingestor
        updated = run_nfl_results_ingestor()
        logger.success(f"✓ NFL results (nflverse): {updated} final(s)")
        return True
    except Exception as exc:
        logger.error(f"✗ NFL results failed: {exc}")
        return False


def step_nfl_player_stats(run_date: str) -> bool:
    """
    NFL per-player per-game stats (nflverse weekly CSV) → nfl_player_game_log,
    feeding the mobile Stats tab NFL leaderboard. Self-healing: the first run
    backfills the last NFL_PLAYER_STATS_BACKFILL_SEASONS seasons; later runs
    refresh the current season only. Off-season the current season's CSV isn't
    published yet (404) → clean no-op. Display/stats only — no model reads it.
    """
    try:
        from data.ingestors.nfl_player_stats_ingestor import run_nfl_player_stats_ingestor
        rows = run_nfl_player_stats_ingestor()
        logger.success(f"✓ NFL player stats (nflverse): {rows} row(s) upserted")
        return True
    except Exception as exc:
        logger.error(f"✗ NFL player stats failed: {exc}")
        return False


def step_nfl_props_data(run_date: str) -> bool:
    """
    NFL prop MODELLING data (nflverse) → nfl_player_game_log (modelling columns),
    nfl_team_game_stats, nfl_snap_counts.

    Separate from step_nfl_player_stats, which fills the same player table for
    the mobile leaderboard: both parse the same source CSV and upsert on the
    same key, so they converge and may run in either order. This one also
    writes team-game context and snap share, and — importantly — writes the
    SCHEDULED-game context rows even before week 1, when the weekly stats CSV
    does not exist yet. Off-season that is the only thing it writes.
    """
    try:
        from data.ingestors.nfl_props_data_ingestor import run_nfl_props_data_ingestor
        got = run_nfl_props_data_ingestor()
        logger.success(f"✓ NFL props data (nflverse): {got}")
        return True
    except Exception as exc:
        logger.error(f"✗ NFL props data failed: {exc}")
        return False


def step_nfl_prop_scoring(run_date: str, dry_run: bool = False) -> bool:
    """Score NFL player props (12 markets) and write picks to DB."""
    try:
        from models.scorer import run_nfl_prop_scorer
        result = run_nfl_prop_scorer(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ NFL prop scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NFL prop scoring failed: {exc}")
        return False


def step_nba_stats(run_date: str) -> bool:
    """Refresh NBA team stats + player game logs (nba_api, LeagueID=00). Local only."""
    try:
        from data.ingestors.nba_stats_ingestor import run_nba_stats_ingestor
        result = run_nba_stats_ingestor(as_of_date=run_date)
        logger.success(f"✓ NBA stats: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NBA stats failed: {exc}")
        return False


def step_nba_prop_odds(run_date: str, snapshot_type: str = "open") -> bool:
    """Fetch DK NBA player prop lines (points/reb/ast/threes/PRA/blk/stl/tov/DD)."""
    try:
        from data.ingestors.prop_odds_ingestor import run_nba_prop_odds_ingestor
        result = run_nba_prop_odds_ingestor(target_date=run_date, snapshot_type=snapshot_type)
        logger.success(f"✓ NBA prop odds ({snapshot_type}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NBA prop odds failed: {exc}")
        return False


def step_nba_game_log(run_date: str) -> bool:
    """Ingest NBA games + player box scores for yesterday (feeds prop rolling stats). Local only."""
    from datetime import datetime, timedelta
    yesterday = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        from data.ingestors.nba_stats_ingestor import ingest_nba_game_log_for_date
        result = ingest_nba_game_log_for_date(yesterday)
        logger.success(f"✓ NBA game log ({yesterday}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NBA game log failed: {exc}")
        return False


def step_ufc_results(run_date: str, poll: bool = False) -> bool:
    """
    Ingest UFC fight results for any completed event in the trailing week
    (Sunday 7am run catches Saturday cards; window self-heals). Must run BEFORE
    settlement — it writes the games scores + ufc_fight_log rows that
    _settle_ufc_picks reads. No-ops cleanly on non-event days.

    Source is the Greco1899 CSV mirror (ufc_csv_loader): ufcstats.com itself is
    behind a Cloudflare challenge the scraper can't pass. The mirror refreshes
    weekly after each card, which matches the Saturday cadence.
    """
    try:
        from data.ingestors.ufc_csv_loader import (
            ingest_ufc_results_for_date_csv, mirror_unchanged)
        # poll=True is the hourly caller. The four CSVs are ~9.8 MB and are
        # fetched unconditionally, so an hourly full pull would move ~235 MB a
        # day off a volunteer's free repo. The mirror serves an ETag and honours
        # If-None-Match, so an unchanged poll costs one HEAD. The 6am run does
        # NOT take this path: if the check ever broke, a skipping poll would be
        # silent, and the daily run is the backstop that isn't.
        if poll and mirror_unchanged():
            logger.info("✓ UFC results: mirror unchanged since last ingest — skipped")
            return True
        result = ingest_ufc_results_for_date_csv(run_date)
        logger.success(f"✓ UFC results: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ UFC results failed: {exc}")
        return False


def _golf_enabled() -> bool:
    """True only when a DataGolf API key is configured. Golf is an optional data
    source (pending subscription) — when the key is absent every golf step no-ops
    cleanly instead of failing the whole pipeline / aborting the hourly refresh."""
    import config
    if not config.DATAGOLF_API_KEY:
        logger.info("Golf: DATAGOLF_API_KEY not set — skipping golf step")
        return False
    return True


def step_golf_field(run_date: str) -> bool:
    """Refresh the current PGA tournament's games + golf_tournaments rows and the
    player registry from DataGolf /field-updates. No-ops off-weeks."""
    if not _golf_enabled():
        return True
    try:
        from data.ingestors.datagolf_ingestor import ingest_golf_field, ingest_player_list
        ingest_player_list()
        result = ingest_golf_field(run_date)
        logger.success(f"✓ Golf field: {result} players")
        return True
    except Exception as exc:
        logger.error(f"✗ Golf field failed: {exc}")
        return False


def step_golf_odds(run_date: str, snapshot_type: str = "open") -> bool:
    """Snapshot live DK golf odds (win/top-N/make-cut + tournament matchups) from
    the DataGolf betting-tools feed. No-ops off-weeks."""
    if not _golf_enabled():
        return True
    try:
        from data.ingestors.datagolf_ingestor import ingest_golf_odds
        result = ingest_golf_odds(snapshot_type=snapshot_type, include_matchups=True)
        logger.success(f"✓ Golf odds: {result} snapshots")
        return True
    except Exception as exc:
        logger.error(f"✗ Golf odds failed: {exc}")
        return False


def step_golf_results(run_date: str) -> bool:
    """Ingest round-level results for recently-completed tournaments (trailing
    window). Must run BEFORE settlement — writes the golf_rounds finishes that
    _settle_golf_picks reads. No-ops when no event finished."""
    if not _golf_enabled():
        return True
    try:
        from data.ingestors.datagolf_ingestor import ingest_golf_results
        result = ingest_golf_results(run_date)
        logger.success(f"✓ Golf results: {result} round rows")
        return True
    except Exception as exc:
        logger.error(f"✗ Golf results failed: {exc}")
        return False


def step_golf_scoring(run_date: str, dry_run: bool = False) -> bool:
    """Score golf markets (outright/top-N/make-cut/matchup) for tournaments in the
    look-ahead window and write picks. No-ops off-weeks."""
    try:
        from models.scorer import run_golf_scorer
        result = run_golf_scorer(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Golf scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Golf scoring failed: {exc}")
        return False


def step_scoring(run_date: str, dry_run: bool = False) -> bool:
    fn = _import_step("scoring")
    try:
        result = fn(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Scoring failed: {exc}")
        return False


def step_game_log(run_date: str, target_date: str | None = None) -> bool:
    """
    Ingest player_game_log rows for completed MLB games.

    Defaults to YESTERDAY, which is what the morning pipeline wants: rolling
    K/hit/etc. stats current before prop scoring. Pass target_date=run_date to
    pick up TODAY's games as they go final, which is what same-day prop
    settlement needs. Idempotent per game, so repeated same-day calls fill in
    each game as it finishes and cost no boxscore call for the ones already in.
    """
    from datetime import datetime, timedelta
    yesterday = target_date or (
        datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        from data.ingestors.mlb_stats_ingestor import ingest_game_log_for_date
        result = ingest_game_log_for_date(yesterday)
        logger.success(f"✓ Game log ({yesterday}): {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Game log failed: {exc}")
        return False


def step_lineups(run_date: str) -> bool:
    """
    Fetch confirmed MLB batting lineups from the MLB live feed.
    Lineups post 60-90 min before first pitch. Safe to re-run — DELETE + INSERT.
    """
    try:
        from data.ingestors.lineup_ingestor import ingest_lineups_for_date
        result = ingest_lineups_for_date(run_date)
        logger.success(f"✓ Lineups: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Lineups failed: {exc}")
        return False


def step_umpires(run_date: str) -> bool:
    """
    Fetch HP umpire assignments from MLB Stats API — self-healing.

    MLB usually posts officials AFTER the 6am ET daily run, so fetching only
    run_date silently wrote 0 rows most days (the table froze 7/12–8/14).
    run_umpire_ingestor also re-fetches recent dates whose games still lack an
    umpire row, so yesterday's assignments always land the next morning.
    Upserts into umpires table — idempotent.
    """
    try:
        from data.ingestors.umpire_ingestor import run_umpire_ingestor
        written = run_umpire_ingestor(run_date)
        logger.success(f"✓ Umpires: {written} assignments written "
                       f"(self-heal window through {run_date})")
        return True
    except Exception as exc:
        logger.error(f"✗ Umpires failed: {exc}")
        return False


def step_public_betting(run_date: str) -> bool:
    """
    Fetch Action Network public betting splits (% of bets, % of money) for
    today's MLB games. Best-effort — failures are non-fatal. Must run before
    scoring so the scorer can attach splits to each pick.
    """
    try:
        from data.ingestors.public_betting_ingestor import run_public_betting_ingestor
        result = run_public_betting_ingestor(target_date=run_date)
        logger.success(f"✓ Public betting: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Public betting failed: {exc}")
        return False


def step_prop_scoring(run_date: str, dry_run: bool = False) -> bool:
    """Score pitcher K props + batter props (hits, TB, HR) and write picks to DB."""
    try:
        from models.scorer import run_prop_scorer
        result = run_prop_scorer(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Prop scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Prop scoring failed: {exc}")
        return False


def step_wnba_prop_scoring(run_date: str, dry_run: bool = False) -> bool:
    """Score WNBA player props (points/reb/ast/threes/PRA) and write picks to DB."""
    try:
        from models.scorer import run_wnba_prop_scorer
        result = run_wnba_prop_scorer(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ WNBA prop scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ WNBA prop scoring failed: {exc}")
        return False


def step_nba_prop_scoring(run_date: str, dry_run: bool = False) -> bool:
    """Score NBA player props (9 markets incl. double-double) and write picks to DB."""
    try:
        from models.scorer import run_nba_prop_scorer
        result = run_nba_prop_scorer(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ NBA prop scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NBA prop scoring failed: {exc}")
        return False


def step_check_lines(run_date: str) -> bool:
    """
    Re-fetch current odds and compare against scored picks.
    Flags any BET picks where the line has moved significantly since scoring.
    Run this 1-2 hours before game time: python run_pipeline.py --step check-lines
    """
    from models.scorer import check_line_movement
    from data.db import get_connection
    try:
        conn = get_connection()
        warnings = check_line_movement(conn, run_date)
        conn.close()
        if not warnings:
            logger.success(f"✓ Line check {run_date}: no significant movement — all picks stand")
        else:
            for w in warnings:
                status_icon = "⛔ SKIP" if w["status"] == "SKIP" else "⚠ CAUTION"
                logger.warning(f"  [{status_icon}] {w['pick_label']} — {w['detail']}")
        return True
    except Exception as exc:
        logger.error(f"✗ Line check failed: {exc}")
        return False


def step_cleanup_picks(run_date: str) -> bool:
    """
    RETIRED 2026-08-09 — intentionally a no-op (kept so the refresh chains and
    the --step CLI stay valid).

    This step used to DELETE NONE-signal picks for started games. That delete
    caused two serious problems (found in the losing-models reevaluation):

    1. It fed the in-play prop scoring bug: deleting a player's pre-game NONE
       row dropped his (game, model, player) key out of the first-signal lock
       set, so the next evening pass RE-SCORED him against DK's in-play prop
       prices. Hundreds of "pre-game" prop picks 2026-06-27..2026-08-08 were
       actually created mid-game (65 of batter_rbi's 67 settled BETs in that
       window). The real fix is the started-game guard in the prop scorers
       (scorer._game_started) — but this delete was the enabling half.

    2. It destroyed the graded-pick universe: dead-zone NONE rows are exactly
       what mv_scored_pick_outcomes / v_model_full_outcome_* grade to evaluate
       thresholds ("all picks settled in 1 database", session 113). Deleting
       them before the morning refresh meant every full-outcome sweep since
       July only saw BET+AVOID rows — silent selection bias.

    The app-side problem the delete solved (NONE rows crowding the picks
    fetch) is already handled by the query itself: fetchPicksForDate orders
    signal_type ASC (BET/AVOID before NONE) under its row cap, so signals can
    never be dropped by NONE volume. NONE rows now stay in the picks table
    permanently — they are the evaluation dataset, not bloat (~2-3K rows/day,
    trivial for Postgres).
    """
    logger.info("✓ Cleanup: no-op (started-game NONE pruning retired 2026-08-09 — "
                "NONE rows are kept as the graded evaluation universe)")
    return True


def step_capture_opening_signals(run_date: str, dry_run: bool = False) -> bool:
    """
    Lock the first BET cross for each game/market into opening_signals (shadow
    track). Must run LAST — after all game + prop scoring — so it sees every
    BET pick standing this refresh. Idempotent; later refreshes can't overwrite.
    """
    try:
        from tracking.opening_signals import capture_opening_signals
        n = capture_opening_signals(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Opening signals: {n} newly locked")
        return True
    except Exception as exc:
        logger.error(f"✗ Opening-signal capture failed: {exc}")
        return False


def step_capture_parlay_track_record(run_date: str, dry_run: bool = False) -> bool:
    """
    Lock the day's canonical cross-game parlay per sport (public parlay track
    record). Must run AFTER opening-signal capture (it reads the locked legs).
    Idempotent; the first run of the day wins.
    """
    try:
        from tracking.parlay_track_record import capture_parlay_track_record
        n = capture_parlay_track_record(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Parlay track record: {n} parlays locked")
        return True
    except Exception as exc:
        logger.error(f"✗ Parlay track-record capture failed: {exc}")
        return False


def step_push_notifications(run_date: str, dry_run: bool = False) -> bool:
    """
    Push a summary of new / dropped signals to opted-in devices, plus track-a-bet
    line moves and replies to in-app feedback, then post newly locked BET signals
    to their sport's Discord channel. Must run LAST — after opening-signal
    capture — so it sees this refresh's locked signals. Idempotent (push_sent
    ledger); never re-notifies or re-posts the same thing twice.
    """
    try:
        from tracking.push_notifier import (
            notify_feedback_replies,
            notify_line_changes,
            notify_signal_changes,
        )
        n = notify_signal_changes(target_date=run_date, dry_run=dry_run)
        # Track-a-bet line-change alerts run in the same step — both watch this
        # refresh's latest odds and are idempotent via the push_sent ledger.
        m = notify_line_changes(target_date=run_date, dry_run=dry_run)
        # In-app feedback replies. Date-independent (a reply written today can
        # answer a thread from last week), ledgered per message.
        f = notify_feedback_replies(dry_run=dry_run)
        logger.success(
            f"✓ Push notifications: {n} signal + {m} line-change + {f} feedback message(s) sent"
        )
    except Exception as exc:
        logger.error(f"✗ Push notifications failed: {exc}")
        return False

    # Discord webhooks share the same trigger (newly-locked signals) but are a
    # separate delivery channel — a broken webhook must not mask a working push,
    # so it gets its own try block and never fails the step.
    try:
        from tracking.discord_notifier import notify_discord_signals
        d = notify_discord_signals(target_date=run_date, dry_run=dry_run)
        if d:
            logger.success(f"✓ Discord: {d} signal(s) posted")
        return True
    except Exception as exc:
        logger.error(f"✗ Discord signal post failed (push already sent): {exc}")
        return True


def step_settle(settle_date: str) -> bool:
    fn = _import_step("settle")
    try:
        result = fn(game_date=settle_date)
        logger.success(f"✓ Settlement: {result}")
    except Exception as exc:
        logger.error(f"✗ Settlement failed: {exc}")
        return False

    # Post the day's recap to Discord once settlement has graded it. Runs here
    # rather than as its own step so it can never post ahead of the results it
    # is reporting. Ledgered per date, so the every-pass settle in
    # scripts/refresh_pass.sh posts exactly one recap per day. Never fails the
    # settle step — the grading is what matters.
    try:
        from tracking.discord_notifier import notify_discord_results
        notify_discord_results(game_date=settle_date)
    except Exception as exc:
        logger.error(f"✗ Discord results recap failed (settlement succeeded): {exc}")
    return True


# ── Full Daily Run ────────────────────────────────────────────────────────────

def run_daily_pipeline(run_date: str = None, dry_run: bool = False) -> dict:
    """
    Execute the full morning pipeline in order.

    Args:
        run_date: ISO date for scoring/ingestion (default: today)
        dry_run:  If True, scoring runs in preview mode (no DB writes)

    Returns:
        Summary dict with step statuses.
    """
    if run_date is None:
        run_date = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    # Yesterday = settlement date
    yesterday = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")

    logger.info(f"\n{'═'*60}")
    logger.info(f"  DAILY PIPELINE — {run_date}")
    logger.info(f"  Started: {datetime.now().strftime('%H:%M:%S')}")
    logger.info(f"{'═'*60}\n")

    start   = datetime.now()
    results = {}

    # ── Step 0a: UFC fight results (must precede settlement) ────────────────
    logger.info("Step 0a: Ingesting UFC results from ufcstats.com...")
    results["ufc_results"] = step_ufc_results(run_date)
    time.sleep(1)

    # ── Step 0b: NHL final scores (must precede settlement) ─────────────────
    logger.info("Step 0b: Ingesting NHL final scores...")
    results["nhl_results"] = step_nhl_results(run_date)
    time.sleep(1)

    # ── Step 0c: Golf results (must precede settlement) ─────────────────────
    logger.info("Step 0c: Ingesting completed golf results from DataGolf...")
    results["golf_results"] = step_golf_results(run_date)
    time.sleep(1)

    # ── Step 0d: MLB player game logs (MUST precede settlement) ──────────────
    # Prop picks settle from player_game_log, so yesterday's box scores have to
    # be ingested BEFORE step_settle runs — otherwise prop settlement finds no
    # log row and every prop lags a full extra day (game picks settle same-day
    # because settle fetches final scores itself; props do not).
    logger.info("Step 0d: Ingesting yesterday's MLB player game logs (pre-settle)...")
    results["game_log"] = step_game_log(run_date)
    time.sleep(1)

    # ── Step 0e: WNBA finals + box scores via ESPN (MUST precede settlement) ─
    # nba_api (stats.nba.com) blocks Actions IPs, so WNBA results used to depend
    # entirely on the local "Basketball Daily Ingest" job — when it lagged, WNBA
    # picks sat unsettled for days. ESPN's hidden API IS reachable from Actions
    # (the injuries step uses it), so this ingests finals + player box scores
    # for the trailing window (+ self-heal over any recent NULL-score WNBA game)
    # and rebuilds the season team-stats snapshot from our own DB. The local job
    # remains a redundant/authoritative source (idempotent upserts coexist).
    # NBA game logs still come from the local job (off-season until ~Oct 2026).
    logger.info("Step 0e: Ingesting WNBA finals + box scores from ESPN (pre-settle)...")
    results["wnba_results"] = step_wnba_results(run_date)
    time.sleep(1)

    # ── Step 0f: NFL finals via nflverse (MUST precede settlement) ───────────
    # nfl_wind_totals picks (the §28 wind card) settle off games scores through
    # the generic totals path. Free no-op whenever no NFL finals are pending.
    logger.info("Step 0f: Ingesting NFL finals from nflverse (pre-settle)...")
    results["nfl_results"] = step_nfl_results(run_date)
    time.sleep(1)

    # ── Step 0: Settle yesterday's picks ────────────────────────────────────
    logger.info("Step 0/6: Settling yesterday's picks...")
    results["settle"] = step_settle(yesterday)
    time.sleep(1)

    # ── Step 0c: Sync config thresholds → model_action_thresholds ────────────
    # Keeps the table (public track record + mobile action filter) in lockstep
    # with config.py so a threshold change never needs a mobile rebuild.
    logger.info("Step 0c: Syncing action thresholds...")
    results["sync_thresholds"] = step_sync_thresholds(run_date)

    # ── Step 0d: Refresh the graded every-pick universe ─────────────────────
    # Right after settle so yesterday's finals are graded into
    # mv_scored_pick_outcomes before anyone opens the custom-model builder.
    logger.info("Step 0d: Refreshing scored-pick outcomes...")
    results["refresh_outcomes"] = step_refresh_outcomes(run_date)

    # ── Step 1: Injuries ────────────────────────────────────────────────────
    logger.info("Step 1/6: Injury ingestion...")
    results["injuries"] = step_injuries(run_date)
    time.sleep(2)

    # ── Step 2: Odds ──────────────────────────────────────────────────────────
    logger.info("Step 2/7: Fetching opening odds from The Odds API...")
    results["odds"] = step_odds(run_date, snapshot_type="open")
    time.sleep(2)

    # ── Step 2b: Player prop odds ─────────────────────────────────────────────
    logger.info("Step 2b/7: Fetching DK player prop lines...")
    results["prop_odds"] = step_prop_odds(run_date, snapshot_type="open")
    time.sleep(2)

    # ── Step 2c: WNBA player prop odds ───────────────────────────────────────
    # Uses The Odds API (not stats.nba.com) — runs fine in GitHub Actions.
    logger.info("Step 2c: Fetching DK WNBA player prop lines...")
    results["wnba_prop_odds"] = step_wnba_prop_odds(run_date, snapshot_type="open")
    time.sleep(2)

    # ── Step 2c2: NBA player prop odds ───────────────────────────────────────
    # Also The Odds API — runs in GitHub Actions (only nba_stats / nba_game_log
    # need a residential IP).
    logger.info("Step 2c2: Fetching DK NBA player prop lines...")
    results["nba_prop_odds"] = step_nba_prop_odds(run_date, snapshot_type="open")
    time.sleep(2)

    # ── Step 2d: Golf field + odds (DataGolf) ────────────────────────────────
    # Reachable from GitHub Actions (paid keyed API). No-ops off-weeks.
    logger.info("Step 2d: Refreshing golf field + DK odds (DataGolf)...")
    results["golf_field"] = step_golf_field(run_date)
    results["golf_odds"]  = step_golf_odds(run_date, snapshot_type="open")
    time.sleep(2)

    # ── Step 3: Team stats (parallel-ish — run MLB then NHL) ─────────────────
    logger.info("Step 3/7: MLB team + pitcher stats...")
    results["mlb_stats"] = step_mlb_stats(run_date)
    time.sleep(1)

    # ── Step 3b: Bullpen workload (yesterday's reliever appearances) ─────────
    # Self-healing daily ingest — was missing entirely until 2026-07-03, which
    # froze mlb_bullpen_stats at 2026-04-14 and fed 0.0 bullpen-IP features to
    # every live-scored game.
    logger.info("Step 3b: MLB bullpen workload (reliever appearances)...")
    results["bullpen"] = step_bullpen(run_date)
    time.sleep(1)

    logger.info("Step 4/7: NHL team + goalie stats...")
    results["nhl_stats"] = step_nhl_stats(run_date)
    time.sleep(1)

    # ── Step 4b: NFL player stats (nflverse weekly CSV) ──────────────────────
    # Mobile Stats tab leaderboard only — self-healing (first run backfills the
    # last 3 seasons), off-season no-op (unpublished season CSV 404s).
    logger.info("Step 4b: NFL player stats (nflverse)...")
    results["nfl_player_stats"] = step_nfl_player_stats(run_date)
    time.sleep(1)

    # ── Step 4c: NFL prop modelling data (nflverse) ──────────────────────────
    # Team-game context + snap share + the modelling columns on the player log.
    # Runs even off-season: it is what writes the SCHEDULED-game rows the prop
    # scorer needs, and before week 1 those are the only rows that exist.
    logger.info("Step 4c: NFL prop modelling data (nflverse)...")
    results["nfl_props_data"] = step_nfl_props_data(run_date)
    time.sleep(1)

    # NOTE: wnba_stats/wnba_game_log AND nba_stats/nba_game_log are intentionally
    # NOT in the scheduled daily flow. nba_api calls stats.nba.com, which blocks
    # GitHub Actions datacenter IPs (consistent read timeouts). Run these manually
    # on a residential IP (the local Task Scheduler "Basketball Daily Ingest" job
    # at 7am — see scripts/basketball_daily_ingest.bat):
    #   python run_pipeline.py --step wnba_stats   / --step wnba-game-log
    #   python run_pipeline.py --step nba_stats    / --step nba-game-log
    # Without *_stats: game picks won't generate (no current-season team features).
    # Without *_game-log: prop rolling features are stale and prop picks can't be
    # settled.

    logger.info("Step 5/7: Weather data (Open-Meteo)...")
    results["weather"] = step_weather(run_date)
    time.sleep(1)

    # ── Step 5b: Lineups ──────────────────────────────────────────────────────
    logger.info("Step 5b/10: Fetching confirmed batting lineups...")
    results["lineups"] = step_lineups(run_date)
    time.sleep(1)

    # ── Step 5c: Umpires ──────────────────────────────────────────────────────
    logger.info("Step 5c/10: Fetching today's HP umpire assignments...")
    results["umpires"] = step_umpires(run_date)
    time.sleep(1)

    # ── Step 5d: Public betting splits ────────────────────────────────────────
    logger.info("Step 5d/10: Fetching Action Network public betting splits...")
    results["public_betting"] = step_public_betting(run_date)
    time.sleep(1)

    # ── Step 6: Scoring ────────────────────────────────────────────────────────
    logger.info("Step 6/10: Generating game picks...")
    results["scoring"] = step_scoring(run_date, dry_run=dry_run)

    # ── Step 7: Game log ingestion ────────────────────────────────────────────
    # Moved to Step 0d (pre-settle) so yesterday's props settle same-day. Logs
    # are already ingested by this point, so prop scoring below has current
    # rolling stats. (Left as a no-op marker for the numbered step sequence.)

    # ── Step 8: Prop scoring ───────────────────────────────────────────────────
    logger.info("Step 8/10: Generating prop picks (all 11 prop markets)...")
    results["prop_scoring"] = step_prop_scoring(run_date, dry_run=dry_run)

    # ── Step 8b: WNBA prop scoring ─────────────────────────────────────────────
    logger.info("Step 8b: Generating WNBA player prop picks...")
    results["wnba_prop_scoring"] = step_wnba_prop_scoring(run_date, dry_run=dry_run)

    # ── Step 8b2: NBA prop scoring ─────────────────────────────────────────────
    logger.info("Step 8b2: Generating NBA player prop picks...")
    results["nba_prop_scoring"] = step_nba_prop_scoring(run_date, dry_run=dry_run)

    # ── Step 8c: Golf scoring ──────────────────────────────────────────────────
    logger.info("Step 8c: Generating golf picks (outright/top-N/make-cut/matchup)...")
    results["golf_scoring"] = step_golf_scoring(run_date, dry_run=dry_run)

    # ── Step 8d: Prune stale NONE picks for started games (table safety net) ───
    if not dry_run:
        logger.info("Step 8d: Pruning stale NONE picks for started games...")
        results["cleanup_picks"] = step_cleanup_picks(run_date)

    # ── Step 9: Lock opening signals (shadow track — must run last) ────────────
    logger.info("Step 9: Locking opening signals (first BET cross per market)...")
    results["opening_signals"] = step_capture_opening_signals(run_date, dry_run=dry_run)

    # ── Step 10: Lock the day's canonical parlay (public parlay track record) ──
    logger.info("Step 10: Locking the daily tracked parlay (public record)...")
    results["parlay_track_record"] = step_capture_parlay_track_record(run_date, dry_run=dry_run)

    # ── Step 11: Push notifications (new / dropped signals — must run last) ─────
    logger.info("Step 11: Sending signal-flip push notifications...")
    results["push_notifications"] = step_push_notifications(run_date, dry_run=dry_run)

    # ── Step 11b: Prune line-shop odds history ────────────────────────────────
    # Runs AFTER settle (which captures DK closing lines for CLV) so nothing can
    # be pruned out from under a reader. Only touches non-DraftKings rows on
    # games before today — see data/prune_odds.py.
    logger.info("Step 11b: Pruning line-shop (non-DK) odds history...")
    results["prune_odds"] = step_prune_odds(run_date)

    # ── Step 12: System health check (feed freshness — after all ingestion) ────
    # CRIT failure returns False → the Actions run shows red. Results land in
    # system_health_checks (anon-readable) for Claude mobile / the app.
    logger.info("Step 12: Running system health check (all API + data feeds)...")
    results["health_check"] = step_health_check(run_date)

    # ── Summary ───────────────────────────────────────────────────────────────
    duration  = (datetime.now() - start).total_seconds()
    n_success = sum(1 for v in results.values() if v)
    n_total   = len(results)

    logger.info(f"\n{'═'*60}")
    logger.info(f"  PIPELINE COMPLETE — {n_success}/{n_total} steps OK")
    logger.info(f"  Duration: {duration:.1f}s")
    for step, ok in results.items():
        icon = "✓" if ok else "✗"
        logger.info(f"    {icon} {step}")
    logger.info(f"{'═'*60}\n")

    if n_success < n_total:
        logger.warning("⚠️  Some steps failed — check logs for details")

    return {"run_date": run_date, "duration_s": duration, **results}


# ── Setup / First-Run Helpers ─────────────────────────────────────────────────

def setup_database():
    """Initialize the database schema. Safe to re-run."""
    from data.db_setup import setup_database as _setup
    _setup()
    logger.success("Database initialized")


def check_env():
    """Verify required environment variables are set."""
    from config import ODDS_API_KEY
    issues = []

    if not ODDS_API_KEY:
        issues.append("ODDS_API_KEY not set — copy .env.example to .env and add your key")

    if issues:
        logger.warning("⚠️  Configuration issues:")
        for issue in issues:
            logger.warning(f"   • {issue}")
        return False

    logger.success("✓ Environment configuration OK")
    return True


def first_time_setup():
    """
    Guided first-time setup. Run once before your first daily pipeline.

    Steps:
    1. Initialize database
    2. Download SBR historical data (manual — see instructions in sbr_loader.py)
    3. Load SBR data into DB
    4. Backfill team stats for training seasons
    5. Train all models
    6. Run backtest to verify go-live readiness
    """
    logger.info("\n🚀 FIRST TIME SETUP")
    logger.info("=" * 60)

    # 1. DB setup
    logger.info("Step 1: Initializing database...")
    setup_database()

    # 2. Check SBR data
    from config import SPORTS, ROOT as PROJ_ROOT
    mlb_sbr = PROJ_ROOT / "data" / "raw" / "sbr" / "mlb"
    nhl_sbr = PROJ_ROOT / "data" / "raw" / "sbr" / "nhl"

    mlb_files = list(mlb_sbr.glob("*.xlsx")) + list(mlb_sbr.glob("*.xls"))
    nhl_files = list(nhl_sbr.glob("*.xlsx")) + list(nhl_sbr.glob("*.xls"))

    if not mlb_files and not nhl_files:
        logger.warning("\n⚠️  No SBR data files found.")
        logger.info("To load historical odds for model training:")
        logger.info("  1. Go to: https://www.sportsbookreviewsonline.com/scoresoddsarchives/")
        logger.info("  2. Download MLB files (2019–2024) → save to: data/raw/sbr/mlb/")
        logger.info("  3. Download NHL files (2019–2024) → save to: data/raw/sbr/nhl/")
        logger.info("  4. Re-run: python run_pipeline.py --setup")
        return

    # 3. Load SBR data
    if mlb_files or nhl_files:
        logger.info("Step 2: Loading SBR historical data...")
        from data.ingestors.sbr_loader import load_to_db
        for f in mlb_files:
            logger.info(f"  Loading MLB: {f.name}")
            load_to_db(str(f), "MLB")
        for f in nhl_files:
            logger.info(f"  Loading NHL: {f.name}")
            load_to_db(str(f), "NHL")

    # 4. Backfill stats
    logger.info("Step 3: Backfilling team stats (this takes ~5 minutes)...")
    try:
        from data.ingestors.mlb_stats_ingestor import backfill_mlb_stats
        backfill_mlb_stats(2019, 2024)
    except Exception as exc:
        logger.error(f"MLB backfill failed: {exc}")

    try:
        from data.ingestors.nhl_stats_ingestor import backfill_nhl_stats
        backfill_nhl_stats(2019, 2024)
    except Exception as exc:
        logger.error(f"NHL backfill failed: {exc}")

    try:
        from data.ingestors.wnba_stats_ingestor import backfill_wnba_stats
        backfill_wnba_stats(2019, 2025)
    except Exception as exc:
        logger.error(f"WNBA backfill failed: {exc}")

    try:
        from data.ingestors.nba_stats_ingestor import backfill_nba_stats
        backfill_nba_stats(2019, 2025)
    except Exception as exc:
        logger.error(f"NBA backfill failed: {exc}")

    try:
        from data.ingestors.datagolf_ingestor import backfill_golf_rounds
        backfill_golf_rounds(2017, 2025)
    except Exception as exc:
        logger.error(f"Golf backfill failed: {exc}")

    # 5. Train models
    logger.info("Step 4: Training models (this takes 10–30 minutes)...")
    try:
        from models.trainer import train_model
        from config import MODELS as ALL_MODELS
        for model_id in ALL_MODELS:
            logger.info(f"  Training {model_id}...")
            try:
                train_model(model_id)
            except Exception as exc:
                logger.error(f"  {model_id} failed: {exc}")
    except Exception as exc:
        logger.error(f"Training failed: {exc}")

    # 6. Backtest
    logger.info("Step 5: Running backtest...")
    try:
        from models.backtester import run_full_backtest
        run_full_backtest()
    except Exception as exc:
        logger.error(f"Backtest failed: {exc}")

    logger.success("\n✅ First-time setup complete!")
    logger.info("To start the dashboard: streamlit run dashboard/app.py")
    logger.info("To run daily: python run_pipeline.py")


# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Betting Model Daily Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py                     Full daily run
  python run_pipeline.py --dry-run           Preview picks (no DB writes)
  python run_pipeline.py --step injuries     Run just the injury ingestor
  python run_pipeline.py --step scoring      Run just the scorer
  python run_pipeline.py --step settle       Settle yesterday's picks
  python run_pipeline.py --date 2025-04-15   Run for a specific date
  python run_pipeline.py --setup             First-time setup (train models)
  python run_pipeline.py --check             Check environment config
        """
    )

    parser.add_argument("--date",    dest="run_date",
                        help="Override date (default: today) YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run scoring in preview mode (no DB writes)")
    parser.add_argument("--step",
                        choices=["sync-thresholds", "refresh-outcomes",
                                 "injuries", "odds", "prop-odds", "mlb_stats", "bullpen",
                                 "nhl_stats", "wnba_stats", "nba_stats", "weather", "lineups",
                                 "umpires", "public-betting", "scoring",
                                 "game-log", "game-log-today", "wnba-game-log", "wnba-prop-odds",
                                 "nba-game-log", "nba-prop-odds",
                                 "prop-scoring", "wnba-prop-scoring", "nba-prop-scoring",
                                 "ufc-results", "ufc-results-poll",
                                 "nhl-results", "wnba-results", "nfl-results",
                                 "nfl-player-stats", "nfl-props-data", "nfl-prop-scoring",
                                 "golf-field", "golf-odds", "golf-results", "golf-scoring",
                                 "opening-signals", "parlay-track-record",
                                 "push-notifications", "cleanup-picks", "prune-odds",
                                 "check-lines", "settle", "health-check"],
                        help="Run a single pipeline step")
    parser.add_argument("--setup",   action="store_true",
                        help="Run first-time setup (DB init + train models)")
    parser.add_argument("--check",   action="store_true",
                        help="Check environment configuration")

    args = parser.parse_args()
    run_date = args.run_date or datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")

    if args.check:
        check_env()
        sys.exit(0)

    if args.setup:
        first_time_setup()
        sys.exit(0)

    if args.step:
        # Run a single step
        step_fns = {
            "sync-thresholds": lambda: step_sync_thresholds(run_date),
            "refresh-outcomes": lambda: step_refresh_outcomes(run_date),
            "injuries":     lambda: step_injuries(run_date),
            "odds":         lambda: step_odds(run_date),
            "prop-odds":    lambda: step_prop_odds(run_date),
            "mlb_stats":    lambda: step_mlb_stats(run_date),
            "bullpen":      lambda: step_bullpen(run_date),
            "nhl_stats":    lambda: step_nhl_stats(run_date),
            "wnba_stats":   lambda: step_wnba_stats(run_date),
            "nba_stats":    lambda: step_nba_stats(run_date),
            "weather":      lambda: step_weather(run_date),
            "lineups":      lambda: step_lineups(run_date),
            "umpires":      lambda: step_umpires(run_date),
            "public-betting": lambda: step_public_betting(run_date),
            "scoring":      lambda: step_scoring(run_date, dry_run=args.dry_run),
            "game-log":     lambda: step_game_log(run_date),
            "game-log-today": lambda: step_game_log(run_date, run_date),
            "wnba-game-log": lambda: step_wnba_game_log(run_date),
            "wnba-prop-odds": lambda: step_wnba_prop_odds(run_date),
            "nba-game-log": lambda: step_nba_game_log(run_date),
            "nba-prop-odds": lambda: step_nba_prop_odds(run_date),
            "prop-scoring": lambda: step_prop_scoring(run_date, dry_run=args.dry_run),
            "wnba-prop-scoring": lambda: step_wnba_prop_scoring(run_date, dry_run=args.dry_run),
            "nba-prop-scoring": lambda: step_nba_prop_scoring(run_date, dry_run=args.dry_run),
            "ufc-results":  lambda: step_ufc_results(run_date),
            "ufc-results-poll": lambda: step_ufc_results(run_date, poll=True),
            "nhl-results":  lambda: step_nhl_results(run_date),
            "wnba-results": lambda: step_wnba_results(run_date),
            "nfl-results":  lambda: step_nfl_results(run_date),
            "nfl-player-stats": lambda: step_nfl_player_stats(run_date),
            "nfl-props-data": lambda: step_nfl_props_data(run_date),
            "nfl-prop-scoring": lambda: step_nfl_prop_scoring(run_date, dry_run=args.dry_run),
            "golf-field":   lambda: step_golf_field(run_date),
            "golf-odds":    lambda: step_golf_odds(run_date),
            "golf-results": lambda: step_golf_results(run_date),
            "golf-scoring": lambda: step_golf_scoring(run_date, dry_run=args.dry_run),
            "opening-signals": lambda: step_capture_opening_signals(run_date, dry_run=args.dry_run),
            "parlay-track-record": lambda: step_capture_parlay_track_record(run_date, dry_run=args.dry_run),
            "push-notifications": lambda: step_push_notifications(run_date, dry_run=args.dry_run),
            "cleanup-picks": lambda: step_cleanup_picks(run_date),
            "prune-odds":   lambda: step_prune_odds(run_date),
            "check-lines":  lambda: step_check_lines(run_date),
            "health-check": lambda: step_health_check(run_date),
            # TODAY, not yesterday. settle_picks walks a 14-day trailing window
            # for both game and prop picks, so "today" is a strict superset of
            # "yesterday" — passing yesterday only ever excluded games that had
            # already finished today. That exclusion is what kept a night's
            # results waiting for the next morning.
            "settle":       lambda: step_settle(run_date),
        }
        success = step_fns[args.step]()
        sys.exit(0 if success else 1)

    # Full pipeline
    result = run_daily_pipeline(run_date=run_date, dry_run=args.dry_run)
    all_ok = all(v for k, v in result.items() if k not in ("run_date", "duration_s"))
    sys.exit(0 if all_ok else 1)
