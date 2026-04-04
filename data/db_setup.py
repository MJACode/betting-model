"""
db_setup.py — Creates (or upgrades) the SQLite database schema.

Run once to initialize: python -m data.db_setup
Safe to re-run — uses CREATE TABLE IF NOT EXISTS throughout.
"""

import sqlite3
import sys
from pathlib import Path

# Allow running directly OR as a module
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH
from loguru import logger


SCHEMA_SQL = """
-- ══════════════════════════════════════════════════════════════════════════════
-- GAMES
-- One row per game. Populated by SBR loader (historical) and stats ingestors
-- (live). home_score / away_score are NULL until the game is final.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS games (
    game_id        TEXT PRIMARY KEY,   -- "{sport}_{date}_{away}_{home}"
    sport          TEXT NOT NULL,      -- 'MLB' | 'NHL'
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,      -- ISO-8601 YYYY-MM-DD
    home_team      TEXT NOT NULL,      -- 3-letter abbrev (consistent across all tables)
    away_team      TEXT NOT NULL,
    home_score     REAL,               -- NULL until final
    away_score     REAL,
    went_to_ot     INTEGER DEFAULT 0,  -- 1 if NHL game went to OT/SO
    home_win       INTEGER,            -- 1/0/NULL — full game result
    home_win_reg   INTEGER,            -- 1/0/NULL — NHL regulation-only result (NULL for MLB)
    regulation_tie INTEGER DEFAULT 0,  -- 1 if NHL game tied after 60 min
    data_source    TEXT,               -- 'sbr' | 'live'
    created_at     TEXT DEFAULT (datetime('now')),
    updated_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_games_date  ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_sport ON games(sport, season);

-- ══════════════════════════════════════════════════════════════════════════════
-- ODDS
-- One row per game × market × snapshot. Multiple snapshots per game (open,
-- close, live refreshes). We always use the most recent snapshot for scoring.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS odds (
    odds_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id        TEXT NOT NULL REFERENCES games(game_id),
    sport          TEXT NOT NULL,
    market         TEXT NOT NULL,      -- 'h2h' | 'spreads' | 'totals' | 'h2h_3way'
    bookmaker      TEXT NOT NULL,      -- 'draftkings' | 'sbr_consensus'
    snapshot_type  TEXT NOT NULL,      -- 'open' | 'close' | 'live'
    snapshot_at    TEXT NOT NULL,      -- ISO-8601 datetime of this snapshot
    home_price     REAL,               -- American odds (e.g. -150, +130)
    away_price     REAL,
    draw_price     REAL,               -- NHL 3-way only
    spread_home    REAL,               -- run/puck line value (e.g. -1.5)
    total_line     REAL,               -- O/U total (e.g. 8.5)
    over_price     REAL,
    under_price    REAL,
    created_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_odds_game    ON odds(game_id, market, snapshot_type);
CREATE INDEX IF NOT EXISTS idx_odds_date    ON odds(snapshot_at);

-- ══════════════════════════════════════════════════════════════════════════════
-- INJURIES
-- Updated daily. One row per player per status change.
-- Tracks all three scenarios: active IL (A), return ramp (B), opponent edge (C).
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS injuries (
    injury_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    sport           TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    player_id       TEXT,              -- sport-specific API ID
    status          TEXT NOT NULL,     -- 'Out' | 'Day-To-Day' | 'Questionable' | 'IL10' | 'IL15' | 'IL60' | 'Returning'
    injury_type     TEXT,              -- body part / description
    scenario        TEXT NOT NULL,     -- 'A' (active) | 'B' (return_ramp) | 'C' computed at feature time
    severity_weight REAL DEFAULT 1.0,  -- IL60=1.0, IL15=0.9, IL10=0.8, DTD/Out=0.7
    return_ramp_factor REAL,           -- NULL unless scenario='B'. 0.70/0.85/1.00
    games_since_return INTEGER,        -- NULL unless scenario='B'
    activation_date TEXT,              -- date player was activated from IL (for ramp calc)
    report_date     TEXT NOT NULL,     -- date this record was pulled
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_injuries_team_date ON injuries(sport, team, report_date);
CREATE INDEX IF NOT EXISTS idx_injuries_player    ON injuries(player_name, sport);

-- ══════════════════════════════════════════════════════════════════════════════
-- MLB TEAM STATS
-- One row per team per game date (rolling snapshot).
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mlb_team_stats (
    stat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    -- Offense
    ops                 REAL,
    wrc_plus            REAL,
    woba                REAL,
    k_pct               REAL,
    bb_pct              REAL,
    iso                 REAL,
    babip               REAL,
    runs_per_game       REAL,
    -- Last N rolling windows
    runs_last_5         REAL,
    runs_last_10        REAL,
    runs_last_15        REAL,
    -- Splits
    runs_per_game_home  REAL,
    runs_per_game_away  REAL,
    -- Pitching / Bullpen
    team_era            REAL,
    bullpen_era         REAL,
    team_whip           REAL,
    team_fip            REAL,
    -- Win/loss context
    wins                INTEGER,
    losses              INTEGER,
    run_differential    INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_mlb_team ON mlb_team_stats(team, as_of_date);

-- ══════════════════════════════════════════════════════════════════════════════
-- MLB PITCHER STATS
-- One row per pitcher per game (starter appearance).
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mlb_pitcher_stats (
    stat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name    TEXT NOT NULL,
    player_id      TEXT,
    team           TEXT NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,
    game_id        TEXT REFERENCES games(game_id),
    -- Per-game
    innings_pitched REAL,
    strikeouts     INTEGER,
    walks          INTEGER,
    hits_allowed   INTEGER,
    earned_runs    INTEGER,
    home_runs_allowed INTEGER,
    -- Season rolling (as of this start)
    era            REAL,
    xfip           REAL,
    whip           REAL,
    k9             REAL,
    bb9            REAL,
    hr9            REAL,
    swstr_pct      REAL,   -- swinging strike rate
    csw_pct        REAL,   -- called+swinging strikes
    -- Last 3 starts rolling
    era_last3      REAL,
    k9_last3       REAL,
    xfip_last3     REAL,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_pitcher ON mlb_pitcher_stats(player_name, season);

-- ══════════════════════════════════════════════════════════════════════════════
-- MLB BULLPEN WORKLOAD
-- One row per reliever appearance per game (excludes starter).
-- Used to compute rolling team bullpen IP/fatigue features for model training.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS mlb_bullpen_stats (
    stat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    game_date      TEXT NOT NULL,
    season         INTEGER NOT NULL,
    team           TEXT NOT NULL,
    game_pk        INTEGER NOT NULL,   -- MLB Stats API game_id
    player_id      INTEGER,
    player_name    TEXT,
    ip             REAL,               -- innings pitched
    er             INTEGER,            -- earned runs
    k              INTEGER,            -- strikeouts
    bb             INTEGER,            -- walks
    pitches        INTEGER,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date, team)
);

CREATE INDEX IF NOT EXISTS idx_bullpen_team_date ON mlb_bullpen_stats(team, game_date);

-- ══════════════════════════════════════════════════════════════════════════════
-- NHL TEAM STATS
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nhl_team_stats (
    stat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    -- Offense
    goals_per_game      REAL,
    shots_per_game      REAL,
    corsi_for_pct       REAL,   -- CF%
    xgf_pct             REAL,   -- expected goals for %
    power_play_pct      REAL,
    -- Last N rolling
    goals_last_5        REAL,
    goals_last_10       REAL,
    -- Splits
    goals_home          REAL,
    goals_away          REAL,
    -- Defense
    goals_against_pg    REAL,
    shots_against_pg    REAL,
    penalty_kill_pct    REAL,
    xga_pct             REAL,
    -- Win context
    wins                INTEGER,
    losses              INTEGER,
    ot_losses           INTEGER,
    goal_differential   INTEGER,
    -- Regulation-specific
    regulation_wins     INTEGER,
    regulation_losses   INTEGER,
    regulation_ties     INTEGER,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_nhl_team ON nhl_team_stats(team, as_of_date);

-- ══════════════════════════════════════════════════════════════════════════════
-- NHL GOALIE STATS
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nhl_goalie_stats (
    stat_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name    TEXT NOT NULL,
    player_id      TEXT,
    team           TEXT NOT NULL,
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,
    game_id        TEXT REFERENCES games(game_id),
    -- Per-game
    saves          INTEGER,
    shots_faced    INTEGER,
    goals_allowed  INTEGER,
    -- Season rolling
    save_pct       REAL,   -- SV%
    gaa            REAL,   -- goals against average
    gsaa           REAL,   -- goals saved above average
    xga            REAL,   -- expected goals against
    -- Last 5 starts
    save_pct_last5 REAL,
    gaa_last5      REAL,
    gsaa_last5     REAL,
    created_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_goalie ON nhl_goalie_stats(player_name, season);

-- ══════════════════════════════════════════════════════════════════════════════
-- NHL SKATER STATS (for individual player props — Phase 2)
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS nhl_skater_stats (
    stat_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_name     TEXT NOT NULL,
    player_id       TEXT,
    team            TEXT NOT NULL,
    position        TEXT,   -- 'C' | 'LW' | 'RW' | 'D'
    season          INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    -- Per-game
    goals           INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    points          INTEGER DEFAULT 0,
    shots_on_goal   INTEGER DEFAULT 0,
    time_on_ice     REAL,   -- minutes
    -- Season rolling (as of this game)
    goals_per_game  REAL,
    shots_per_game  REAL,
    points_per_game REAL,
    corsi_pct       REAL,
    xgf_pct         REAL,
    -- Last 5 games
    goals_last5     REAL,
    shots_last5     REAL,
    toi_last5       REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_skater ON nhl_skater_stats(player_name, season);

-- ══════════════════════════════════════════════════════════════════════════════
-- PICKS — Paper Trading Log
-- Every BET signal gets a row. Results updated the next morning.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS picks (
    pick_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             TEXT REFERENCES games(game_id),
    model_id            TEXT NOT NULL,        -- e.g. 'mlb_moneyline'
    sport               TEXT NOT NULL,
    game_date           TEXT NOT NULL,
    pick_side           TEXT NOT NULL,        -- 'home' | 'away' | 'over' | 'under' | 'draw'
    pick_label          TEXT NOT NULL,        -- human-readable e.g. "Tampa Bay Lightning ML"
    model_probability   REAL NOT NULL,
    dk_implied_prob     REAL NOT NULL,
    edge                REAL NOT NULL,        -- model_prob - dk_implied_prob
    dk_odds             REAL NOT NULL,        -- American odds at time of scoring
    scored_line         REAL,                 -- Total line or spread at time of scoring (for line movement checks)
    kelly_fraction      REAL NOT NULL,        -- Quarter-Kelly fraction
    recommended_bet     REAL NOT NULL,        -- dollar amount (kelly_fraction × bankroll)
    bankroll_at_pick    REAL NOT NULL,
    -- Injury context
    injury_flag         TEXT,                 -- NULL | 'starter_out' | 'returning' | 'opponent_edge' | 'combined'
    injury_detail       TEXT,                 -- Human-readable description
    -- Signal classification
    signal_type         TEXT NOT NULL DEFAULT 'BET',  -- 'BET' | 'AVOID'
    confidence_tier     TEXT,                 -- 'HIGH' | 'MED' | 'LOW'
    -- Result (filled next morning)
    result              TEXT,                 -- 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION' | NULL
    profit_flat         REAL,                 -- P&L assuming $100 flat bet
    profit_kelly        REAL,                 -- P&L using recommended_bet
    settled_at          TEXT,
    created_at          TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_picks_date    ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model   ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal  ON picks(signal_type, result);

-- ══════════════════════════════════════════════════════════════════════════════
-- MODEL METADATA
-- Tracks which model version is active, training date, holdout performance.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS model_registry (
    registry_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id          TEXT NOT NULL,
    version           TEXT NOT NULL,          -- e.g. '1.0.0'
    trained_on        TEXT NOT NULL,          -- ISO date
    train_seasons     TEXT NOT NULL,          -- JSON array e.g. '[2019,2020,2021,2022,2023]'
    holdout_season    INTEGER,
    holdout_accuracy  REAL,
    holdout_roi       REAL,
    holdout_picks     INTEGER,
    calibration_score REAL,                   -- mean calibration error
    is_active         INTEGER DEFAULT 1,      -- 1 = currently used for scoring
    model_path        TEXT,                   -- relative path to .pkl file
    notes             TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(model_id, version)
);

-- ══════════════════════════════════════════════════════════════════════════════
-- PIPELINE LOG
-- One row per daily run. Used to detect failures and gaps.
-- ══════════════════════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS pipeline_log (
    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    step        TEXT NOT NULL,   -- 'injury' | 'odds' | 'mlb_stats' | 'nhl_stats' | 'features' | 'scoring' | 'tracker'
    status      TEXT NOT NULL,   -- 'success' | 'error' | 'skipped'
    records_in  INTEGER DEFAULT 0,
    records_out INTEGER DEFAULT 0,
    duration_s  REAL,
    error_msg   TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_pipeline_date ON pipeline_log(run_date, step);
"""


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Apply additive column migrations that can't be expressed in CREATE TABLE IF NOT EXISTS."""
    existing = {row[1] for row in conn.execute("PRAGMA table_info(picks)").fetchall()}
    if "scored_line" not in existing:
        conn.execute("ALTER TABLE picks ADD COLUMN scored_line REAL")


def setup_database(db_path=None) -> None:
    """Create or upgrade the database schema."""
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Setting up database at: {path}")
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        # Additive migrations for columns added after initial schema
        _run_migrations(conn)
        conn.commit()
        logger.success("Database schema created / verified successfully.")

        # Quick sanity check
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        logger.info(f"Tables present: {[t[0] for t in tables]}")
    except Exception as e:
        logger.error(f"Schema setup failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()
