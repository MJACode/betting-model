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
    home_score_f5  REAL,
    away_score_f5  REAL,
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

CREATE TABLE IF NOT EXISTS wnba_team_stats (
    stat_id             INTEGER PRIMARY KEY AUTOINCREMENT,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    points_per_game     REAL, points_allowed_pg REAL, pace REAL,
    off_rating          REAL, def_rating REAL,
    efg_pct             REAL, fg_pct REAL, fg3_pct REAL, ft_pct REAL,
    reb_per_game        REAL, ast_per_game REAL, tov_pct REAL,
    points_last_3       REAL, points_last_5 REAL,
    points_home         REAL, points_away REAL,
    wins                INTEGER, losses INTEGER, point_differential REAL,
    created_at          TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_wnba_team ON wnba_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS wnba_player_game_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    minutes         REAL, is_starter INTEGER,
    points          INTEGER, rebounds INTEGER,
    offensive_reb   INTEGER, defensive_reb INTEGER,
    assists         INTEGER, steals INTEGER, blocks INTEGER, turnovers INTEGER,
    fg_made         INTEGER, fg_att INTEGER,
    fg3_made        INTEGER, fg3_att INTEGER,
    ft_made         INTEGER, ft_att INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_wnba_plog_player ON wnba_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_wnba_plog_game   ON wnba_player_game_log(game_id);

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
    dk_odds            REAL,
    scored_line        REAL,
    kelly_fraction     REAL NOT NULL,
    recommended_bet    REAL NOT NULL,
    bankroll_at_pick   REAL NOT NULL,
    injury_flag        TEXT,
    injury_detail      TEXT,
    signal_type        TEXT NOT NULL DEFAULT 'BET',
    confidence_tier    TEXT,
    public_bet_pct     REAL,
    public_money_pct   REAL,
    closing_dk_odds    REAL,               -- DK American price on the pick side at close (CLV)
    closing_line       REAL,               -- DK total/spread on the pick side at close (NULL for ML)
    clv_pct            REAL,               -- closing_implied_prob - bet_implied_prob, in pp (positive = beat the close)
    clv_captured_at    TEXT,               -- when CLV was recorded (at settlement)
    result             TEXT,
    profit_flat        REAL,
    profit_kelly       REAL,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_picks_date   ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model  ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal ON picks(signal_type, result);

CREATE TABLE IF NOT EXISTS public_betting (
    split_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id          TEXT NOT NULL REFERENCES games(game_id),
    game_date        TEXT NOT NULL,
    market           TEXT NOT NULL,
    side             TEXT NOT NULL,
    book             TEXT NOT NULL DEFAULT 'consensus',
    public_bet_pct   REAL,
    public_money_pct REAL,
    source           TEXT NOT NULL DEFAULT 'action_network',
    snapshot_at      TEXT NOT NULL,
    created_at       TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, market, side, book)
);
CREATE INDEX IF NOT EXISTS idx_public_betting_game ON public_betting(game_id, market, side);
CREATE INDEX IF NOT EXISTS idx_public_betting_date ON public_betting(game_date);

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

CREATE TABLE IF NOT EXISTS player_game_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_type     TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    innings_pitched REAL, pitches INTEGER, is_starter INTEGER,
    p_strikeouts    INTEGER, p_walks INTEGER, p_hits_allowed INTEGER,
    p_earned_runs   INTEGER, p_home_runs INTEGER,
    at_bats         INTEGER, hits INTEGER, doubles INTEGER, triples INTEGER,
    home_runs       INTEGER, rbi INTEGER, runs INTEGER, walks INTEGER,
    strikeouts      INTEGER, stolen_bases INTEGER, total_bases INTEGER,
    batting_order   INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_id, player_type)
);

CREATE TABLE IF NOT EXISTS player_prop_odds (
    prop_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT,
    market          TEXT NOT NULL,
    bookmaker       TEXT NOT NULL DEFAULT 'draftkings',
    snapshot_type   TEXT NOT NULL,
    snapshot_at     TEXT NOT NULL,
    line            REAL,
    over_price      REAL,
    under_price     REAL,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS player_savant_stats (
    stat_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT,
    player_type     TEXT NOT NULL,
    season          INTEGER NOT NULL,
    k_pct           REAL, bb_pct REAL, whiff_pct REAL, swstr_pct REAL,
    csw_pct         REAL, xera REAL, ff_pct REAL, sl_pct REAL,
    ch_pct          REAL, cu_pct REAL, si_pct REAL, fc_pct REAL,
    avg_velocity    REAL, batter_k_pct REAL, batter_bb_pct REAL,
    batting_avg     REAL, slg_pct REAL, obp REAL, woba REAL,
    xwoba           REAL, xba REAL, xslg REAL, barrel_pct REAL,
    hard_hit_pct    REAL, launch_angle REAL, exit_velocity REAL,
    sprint_speed    REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, season, player_type)
);

CREATE TABLE IF NOT EXISTS umpires (
    umpire_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    umpire_name     TEXT NOT NULL,
    umpire_source   TEXT,
    k_per_game      REAL, k_plus_minus REAL, favor_score REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id)
);

CREATE TABLE IF NOT EXISTS lineup_slots (
    slot_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_id       TEXT,
    player_name     TEXT NOT NULL,
    batting_order   INTEGER,
    position        TEXT,
    hand            TEXT,
    is_confirmed    INTEGER DEFAULT 0,
    snapshot_at     TEXT NOT NULL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, team, batting_order, snapshot_at)
);

-- ── LIVE GAME STATE (Phase 1 — in-play betting) ──────────────────────────────
-- One row per snapshot of an in-progress game. Written by live_game_state_poller
-- every LIVE_POLL_INTERVAL_SEC. Drives trigger detection (inning_change,
-- score_change, pitching_change, due_up_change) for the orchestrator.
CREATE TABLE IF NOT EXISTS live_game_state (
    state_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id             TEXT NOT NULL REFERENCES games(game_id),
    snapshot_at         TEXT NOT NULL,
    inning              INTEGER,
    inning_half         TEXT,             -- 'top' | 'bottom'
    outs                INTEGER,
    bases_state         TEXT,             -- e.g. '101' = 1B+3B, '111' = loaded
    home_score          INTEGER,
    away_score          INTEGER,
    current_pitcher_id  TEXT,
    current_batter_id   TEXT,
    on_deck_batter_id   TEXT,
    abstract_game_state TEXT,             -- 'Preview' | 'Live' | 'Final'
    raw_state           TEXT,             -- JSON blob (truncated linescore for debug)
    created_at          TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_live_state_game ON live_game_state(game_id, snapshot_at);

-- One row per detected state-change trigger. Consumed by the trigger
-- orchestrator (Phase 3) to decide when to fire Odds API calls.
CREATE TABLE IF NOT EXISTS live_trigger_events (
    trigger_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    fired_at        TEXT NOT NULL,
    trigger_type    TEXT NOT NULL,        -- 'inning_change' | 'score_change' | 'pitching_change' | 'due_up_change'
    detail          TEXT,                 -- short description for telemetry
    prev_state_id   INTEGER REFERENCES live_game_state(state_id),
    new_state_id    INTEGER REFERENCES live_game_state(state_id),
    dispatched_at   TEXT,                 -- when orchestrator acted on it (NULL = pending)
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_live_trigger_game ON live_trigger_events(game_id, fired_at);
CREATE INDEX IF NOT EXISTS idx_live_trigger_pending ON live_trigger_events(dispatched_at);

-- ── PLAYS (Phase 2 — live win-probability training corpus) ────────────────────
-- One row per play in a completed game. Sourced from MLB Stats API
-- /api/v1.1/game/{gamePk}/feed/live → liveData.plays.allPlays[]. The state
-- *before* the play (inning, outs, bases, score) is the model input; the game's
-- final outcome (home_won) is the label.
CREATE TABLE IF NOT EXISTS plays (
    play_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    season             INTEGER NOT NULL,
    play_index         INTEGER NOT NULL,   -- 0-based ordinal within game
    inning             SMALLINT,
    half_inning        TEXT,               -- 'top' | 'bottom'
    -- State BEFORE the play (the model input)
    outs_before        SMALLINT,
    bases_before       TEXT,               -- '000' .. '111' (1B-2B-3B)
    score_home_before  SMALLINT,
    score_away_before  SMALLINT,
    -- The play itself
    batter_id          TEXT,
    pitcher_id         TEXT,
    bat_side           TEXT,               -- 'L' | 'R' | 'S'
    pitch_hand         TEXT,               -- 'L' | 'R'
    event_type         TEXT,               -- e.g. 'single', 'strikeout', 'walk', 'home_run'
    description        TEXT,
    runs_on_play       SMALLINT,
    outs_added         SMALLINT,
    -- State AFTER the play (denormalised for fast feature lookups)
    outs_after         SMALLINT,
    bases_after        TEXT,
    score_home_after   SMALLINT,
    score_away_after   SMALLINT,
    -- Eventual game outcome (the label)
    home_won           INTEGER,            -- 1 if home team won game, else 0; NULL if incomplete
    created_at         TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, play_index)
);
CREATE INDEX IF NOT EXISTS idx_plays_game   ON plays(game_id, play_index);
CREATE INDEX IF NOT EXISTS idx_plays_season ON plays(season);
"""


# ── Postgres schema (loaded from supabase_schema.sql) ────────────────────────

_SCHEMA_FILE = Path(__file__).parent / "supabase_schema.sql"


def _load_postgres_schema() -> str:
    return _SCHEMA_FILE.read_text()


# ── Postgres migrations (additive) ────────────────────────────────────────────

_MIGRATIONS = [
    # (table, column, definition)
    ("games", "commence_time", "TEXT"),
    ("games", "home_score_f5", "NUMERIC"),
    ("games", "away_score_f5", "NUMERIC"),
    ("player_savant_stats", "gb_pct", "NUMERIC"),
    ("picks", "player_id",          "TEXT"),
    ("picks", "pitcher_throw_hand", "TEXT"),
    # Live (in-play) betting — Phase 1 scaffolding
    ("picks", "is_live",             "BOOLEAN DEFAULT FALSE"),
    ("picks", "inning_at_pick",      "SMALLINT"),
    ("picks", "score_diff_at_pick",  "SMALLINT"),
    # Public betting coverage (Action Network) — BAB-58
    ("picks", "public_bet_pct",      "NUMERIC"),
    ("picks", "public_money_pct",    "NUMERIC"),
    # Closing line value (CLV) — captured at settlement from the last pre-game DK snapshot
    ("picks", "closing_dk_odds",     "NUMERIC"),
    ("picks", "closing_line",        "NUMERIC"),
    ("picks", "clv_pct",             "NUMERIC"),
    ("picks", "clv_captured_at",     "TEXT"),
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
