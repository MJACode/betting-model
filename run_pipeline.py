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


def step_nhl_stats(run_date: str) -> bool:
    fn = _import_step("nhl_stats")
    try:
        year  = int(run_date[:4])
        month = int(run_date[5:7])
        season = year if month >= 10 else year
        result = fn(season=season, as_of_date=run_date)
        logger.success(f"✓ NHL stats: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ NHL stats failed: {exc}")
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


def step_scoring(run_date: str, dry_run: bool = False) -> bool:
    fn = _import_step("scoring")
    try:
        result = fn(target_date=run_date, dry_run=dry_run)
        logger.success(f"✓ Scoring: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Scoring failed: {exc}")
        return False


def step_game_log(run_date: str) -> bool:
    """
    Ingest player_game_log rows for yesterday's completed MLB games.

    Runs daily so rolling K/hit/etc. stats are current before prop scoring.
    Idempotent — safe to re-run if it fails mid-way.
    """
    from datetime import datetime, timedelta
    yesterday = (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
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


def step_settle(settle_date: str) -> bool:
    fn = _import_step("settle")
    try:
        result = fn(game_date=settle_date)
        logger.success(f"✓ Settlement: {result}")
        return True
    except Exception as exc:
        logger.error(f"✗ Settlement failed: {exc}")
        return False


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

    # ── Step 0: Settle yesterday's picks ────────────────────────────────────
    logger.info("Step 0/6: Settling yesterday's picks...")
    results["settle"] = step_settle(yesterday)
    time.sleep(1)

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

    # ── Step 3: Team stats (parallel-ish — run MLB then NHL) ─────────────────
    logger.info("Step 3/7: MLB team + pitcher stats...")
    results["mlb_stats"] = step_mlb_stats(run_date)
    time.sleep(1)

    logger.info("Step 4/7: NHL team + goalie stats...")
    results["nhl_stats"] = step_nhl_stats(run_date)
    time.sleep(1)

    logger.info("Step 5/7: Weather data (Open-Meteo)...")
    results["weather"] = step_weather(run_date)
    time.sleep(1)

    # ── Step 5b: Lineups ──────────────────────────────────────────────────────
    logger.info("Step 5b/9: Fetching confirmed batting lineups...")
    results["lineups"] = step_lineups(run_date)
    time.sleep(1)

    # ── Step 6: Scoring ────────────────────────────────────────────────────────
    logger.info("Step 6/9: Generating game picks...")
    results["scoring"] = step_scoring(run_date, dry_run=dry_run)

    # ── Step 7: Game log ingestion (yesterday's results) ──────────────────────
    logger.info("Step 7/9: Ingesting yesterday's player game logs...")
    results["game_log"] = step_game_log(run_date)
    time.sleep(1)

    # ── Step 8: Prop scoring ───────────────────────────────────────────────────
    logger.info("Step 8/9: Generating prop picks (pitcher Ks + batter hits/TB/HR)...")
    results["prop_scoring"] = step_prop_scoring(run_date, dry_run=dry_run)

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
                        choices=["injuries", "odds", "prop-odds", "mlb_stats",
                                 "nhl_stats", "weather", "lineups", "scoring",
                                 "game-log", "prop-scoring", "check-lines", "settle"],
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
            "injuries":     lambda: step_injuries(run_date),
            "odds":         lambda: step_odds(run_date),
            "prop-odds":    lambda: step_prop_odds(run_date),
            "mlb_stats":    lambda: step_mlb_stats(run_date),
            "nhl_stats":    lambda: step_nhl_stats(run_date),
            "weather":      lambda: step_weather(run_date),
            "lineups":      lambda: step_lineups(run_date),
            "scoring":      lambda: step_scoring(run_date, dry_run=args.dry_run),
            "game-log":     lambda: step_game_log(run_date),
            "prop-scoring": lambda: step_prop_scoring(run_date, dry_run=args.dry_run),
            "check-lines":  lambda: step_check_lines(run_date),
            "settle":       lambda: step_settle(
                (datetime.strptime(run_date, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
            ),
        }
        success = step_fns[args.step]()
        sys.exit(0 if success else 1)

    # Full pipeline
    result = run_daily_pipeline(run_date=run_date, dry_run=args.dry_run)
    all_ok = all(v for k, v in result.items() if k not in ("run_date", "duration_s"))
    sys.exit(0 if all_ok else 1)
