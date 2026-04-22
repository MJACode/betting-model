"""
db_setup.py — Creates (or upgrades) the Postgres database schema.

Run once to initialise: python -m data.db_setup

Safe to re-run — uses CREATE TABLE IF NOT EXISTS and CREATE INDEX IF NOT EXISTS
throughout.  Additive column migrations are applied automatically.

SQLite note
-----------
SCHEMA_SQL (below) is the legacy SQLite DDL kept for the unit-test suite,
which runs against an in-memory SQLite database.  Production code uses the
Postgres DDL in data/supabase_schema.sql via setup_database().
"""

import sys
from pathlib import Path

from loguru import logger

sys.path.insert(0, str(Path(__file__).parent.parent))
from data.db import get_connection


# ── Legacy SQLite schema (used ONLY by tests via conftest.py) ─────────────────
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS games (
    game_id        TEXT PRIMARY KEY,
    sport          TEXT NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,
    home_team      TEXT NOT NULL,
    away_team      TEXT NOT NULL,
    home_score     REAL,
    away_score     REAL,
    went_to_ot     INTEGER DEFAULT 0,
    home_win       INTEGER,
    home_win_reg   INTEGER,
    regulation_tie INTEGER DEFAULT 0,
    data_source    TEXT,
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_games_date  ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_sport ON games(sport, season);

CREATE TABLE IF NOT EXISTS odds (
    odds_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES games(game_id),
    sport         TEXT NOT NULL,
    market        TEXT NOT NULL,
    bookmaker     TEXT NOT NULL,
    snapshot_type TEXT NOT NULL,
    snapshot_at   TEXT NOT NULL,
    home_price    REAL,
    away_price    REAL,
    draw_price    REAL,
    spread_home   REAL,
    total_line    REAL,
    over_price    REAL,
    under_price   REAL,
    created_at    TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_id, market, snapshot_type);
CREATE INDEX IF NOT EXISTS idx_odds_date ON odds(snapshot_at);

CREATE TABLE IF NOT EXISTS injuries (
    injury_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    sport              TEXT NOT NULL,
    team               TEXT NOT NULL,
    player_name        TEXT NOT NULL,
    player_id          TEXT,
    status             TEXT NOT NULL,
    injury_type        TEXT,
    scenario           TEXT NOT NULL,
    severity_weight    REAL DEFAULT 1.0,
    return_ramp_factor REAL,
    games_since_return INTEGER,
    activation_date    TEXT,
    report_date        TEXT NOT NULL,
    created_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_injuries_team_date ON injuries(sport, team, report_date);
CREATE INDEX IF NOT EXISTS idx_injuries_player    ON injuries(player_name, sport);

CREATE TABLE IF NOT EXISTS mlb_team_stats (
    stat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    ops                 REAL, wrc_plus REAL, woba REAL, k_pct REAL, bb_pct REAL,
    iso                 REAL, babip REAL, runs_per_game REAL,
    runs_last_5         REAL, runs_last_10 REAL, runs_last_15 REAL,
    runs_per_game_home  REAL, runs_per_game_away REAL,
    team_era            REAL, bullpen_era REAL, team_whip REAL, team_fip REAL,
    wins                INTEGER, losses INTEGER, run_differential INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_mlb_team ON mlb_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS mlb_pitcher_stats (
    stat_id           INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name       TEXT NOT NULL,
    player_id         TEXT,
    team              TEXT NOT NULL,
    season            INTEGER NOT NULL,
    game_date         TEXT NOT NULL,
    game_id           TEXT REFERENCES games(game_id),
    innings_pitched   REAL, strikeouts INTEGER, walks INTEGER,
    hits_allowed      INTEGER, earned_runs INTEGER, home_runs_allowed INTEGER,
    era               REAL, xfip REAL, whip REAL, k9 REAL, bb9 REAL, hr9 REAL,
    swstr_pct         REAL, csw_pct REAL,
    era_last3         REAL, k9_last3 REAL, xfip_last3 REAL,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);
CREATE INDEX IF NOT EXISTS idx_pitcher ON mlb_pitcher_stats(player_name, season);

CREATE TABLE IF NOT EXISTS mlb_bullpen_stats (
    stat_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date   TEXT NOT NULL,
    season      INTEGER NOT NULL,
    team        TEXT NOT NULL,
    game_pk     INTEGER NOT NULL,
    player_id   INTEGER,
    player_name TEXT,
    ip          REAL, er INTEGER, k INTEGER, bb INTEGER, pitches INTEGER,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date, team)
);
CREATE INDEX IF NOT EXISTS idx_bullpen_team_date ON mlb_bullpen_stats(team, game_date);

CREATE TABLE IF NOT EXISTS nhl_team_stats (
    stat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    goals_per_game      REAL, shots_per_game REAL, corsi_for_pct REAL,
    xgf_pct             REAL, power_play_pct REAL,
    goals_last_5        REAL, goals_last_10 REAL,
    goals_home          REAL, goals_away REAL,
    goals_against_pg    REAL, shots_against_pg REAL,
    penalty_kill_pct    REAL, xga_pct REAL,
    wins                INTEGER, losses INTEGER, ot_losses INTEGER,
    goal_differential   INTEGER,
    regulation_wins     INTEGER, regulation_losses INTEGER, regulation_ties INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_nhl_team ON nhl_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS nhl_goalie_stats (
    stat_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name   TEXT NOT NULL,
    player_id     TEXT,
    team          TEXT NOT NULL,
    season        INTEGER NOT NULL,
    game_date     TEXT NOT NULL,
    game_id       TEXT REFERENCES games(game_id),
    saves         INTEGER, shots_faced INTEGER, goals_allowed INTEGER,
    save_pct      REAL, gaa REAL, gsaa REAL, xga REAL,
    save_pct_last5 REAL, gaa_last5 REAL, gsaa_last5 REAL,
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);
CREATE INDEX IF NOT EXISTS idx_goalie ON nhl_goalie_stats(player_name, season);

CREATE TABLE IF NOT EXISTS nhl_skater_stats (
    stat_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name     TEXT NOT NULL,
    player_id       TEXT,
    team            TEXT NOT NULL,
    position        TEXT,
    season          INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    goals           INTEGER DEFAULT 0, assists INTEGER DEFAULT 0,
    points          INTEGER DEFAULT 0, shots_on_goal INTEGER DEFAULT 0,
    time_on_ice     REAL,
    goals_per_game  REAL, shots_per_game REAL, points_per_game REAL,
    corsi_pct       REAL, xgf_pct REAL,
    goals_last5     REAL, shots_last5 REAL, toi_last5 REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);
CREATE INDEX IF NOT EXISTS idx_skater ON nhl_skater_stats(player_name, season);

CREATE TABLE IF NOT EXISTS picks (
    pick_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    pick_side          TEXT NOT NULL,
    pick_label         TEXT NOT NULL,
    model_probability  REAL NOT NULL,
    dk_implied_prob    REAL NOT NULL,
    edge               REAL NOT NULL,
    dk_odds            REAL NOT NULL,
    scored_line        REAL,
    kelly_fraction     REAL NOT NULL,
    recommended_bet    REAL NOT NULL,
    bankroll_at_pick   REAL NOT NULL,
    injury_flag        TEXT,
    injury_detail      TEXT,
    signal_type        TEXT NOT NULL DEFAULT 'BET',
    confidence_tier    TEXT,
    result             TEXT,
    profit_flat        REAL,
    profit_kelly       REAL,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_picks_date   ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model  ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal ON picks(signal_type, result);

CREATE TABLE IF NOT EXISTS model_registry (
    registry_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id          TEXT NOT NULL,
    version           TEXT NOT NULL,
    trained_on        TEXT NOT NULL,
    train_seasons     TEXT NOT NULL,
    holdout_season    INTEGER,
    holdout_accuracy  REAL,
    holdout_roi       REAL,
    holdout_picks     INTEGER,
    calibration_score REAL,
    is_active         INTEGER DEFAULT 1,
    model_path        TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(model_id, version)
);

CREATE TABLE IF NOT EXISTS pipeline_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL,
    records_in  INTEGER DEFAULT 0,
    records_out INTEGER DEFAULT 0,
    duration_s  REAL,
    error_msg   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_pipeline_date ON pipeline_log(run_date, step);
"""


# ── Postgres schema (loaded from supabase_schema.sql) ────────────────────────

_SCHEMA_FILE = Path(__file__).parent / "supabase_schema.sql"


def _load_postgres_schema() -> str:
    return _SCHEMA_FILE.read_text()


# ── Postgres migrations (additive) ────────────────────────────────────────────

_MIGRATIONS = [
    # (table, column, definition)
    ("games", "commence_time", "TEXT"),
]


def _run_migrations(conn) -> None:
    """Apply additive column migrations that cannot use CREATE TABLE IF NOT EXISTS."""
    for table, column, definition in _MIGRATIONS:
        existing = conn.execute("""
            SELECT 1 FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table, column)).fetchone()
        if not existing:
            logger.info(f"Migration: adding {table}.{column}")
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


# ── Public entry point ────────────────────────────────────────────────────────

def setup_database() -> None:
    """Create or upgrade the Postgres schema via DATABASE_URL."""
    logger.info("Setting up Postgres database schema...")
    conn = get_connection()
    try:
        schema_sql = _load_postgres_schema()
        # Execute each statement individually so IF NOT EXISTS works correctly
        for raw in schema_sql.split(";"):
            stmt = raw.strip()
            if stmt and not stmt.startswith("--"):
                conn.execute(stmt)

        _run_migrations(conn)
        conn.commit()
        logger.success("Database schema created / verified successfully.")

        # Quick sanity check
        tables = conn.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """).fetchall()
        logger.info(f"Tables present: {[t[0] for t in tables]}")
    except Exception as e:
        conn.rollback()
        logger.error(f"Schema setup failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
