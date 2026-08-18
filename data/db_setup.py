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
    home_link     TEXT,
    away_link     TEXT,
    draw_link     TEXT,
    over_link     TEXT,
    under_link    TEXT,
    home_sid      TEXT,
    away_sid      TEXT,
    draw_sid      TEXT,
    over_sid      TEXT,
    under_sid     TEXT,
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

CREATE TABLE IF NOT EXISTS nba_team_stats (
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
CREATE INDEX IF NOT EXISTS idx_nba_team ON nba_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS nba_player_game_log (
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
CREATE INDEX IF NOT EXISTS idx_nba_plog_player ON nba_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_nba_plog_game   ON nba_player_game_log(game_id);

-- ── UFC ──────────────────────────────────────────────────────────────────────
-- Fighter identity registry. fighter_id is the ufcstats.com fighter id (the hex
-- token in http://ufcstats.com/fighter-details/{id}). slug is the normalized
-- full name (lowercase, accents stripped, hyphenated) used to join Odds API
-- fighter names to ufcstats fighters and to build UFC game_ids.
CREATE TABLE IF NOT EXISTS fighters (
    fighter_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    slug         TEXT NOT NULL,
    height_in    REAL,
    reach_in     REAL,
    stance       TEXT,
    dob          TEXT,
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_fighters_slug ON fighters(slug);

-- One row per fighter per fight (two rows per fight). The fight-level outcome
-- columns (method, end_round, end_time_sec, scheduled_rounds) are duplicated on
-- both rows; result differs ('win'/'loss'/'draw'/'nc'). Per-fighter round stats
-- come from the ufcstats fight-details page totals.
CREATE TABLE IF NOT EXISTS ufc_fight_log (
    log_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    fighter_id        TEXT NOT NULL,
    fighter_name      TEXT NOT NULL,
    opponent_id       TEXT,
    opponent_name     TEXT,
    game_id           TEXT REFERENCES games(game_id),
    game_date         TEXT NOT NULL,
    season            INTEGER NOT NULL,
    event_name        TEXT,
    weight_class      TEXT,
    is_title_fight    INTEGER DEFAULT 0,
    scheduled_rounds  INTEGER,
    result            TEXT,              -- 'win' | 'loss' | 'draw' | 'nc'
    method            TEXT,              -- 'decision' | 'ko_tko' | 'submission' | 'dq' | 'other'
    method_detail     TEXT,              -- raw ufcstats method string
    end_round         INTEGER,
    end_time_sec      INTEGER,           -- seconds into end_round at stoppage
    knockdowns        INTEGER,
    sig_strikes_landed     INTEGER,
    sig_strikes_attempted  INTEGER,
    sig_strikes_absorbed   INTEGER,
    total_strikes_landed   INTEGER,
    takedowns_landed       INTEGER,
    takedowns_attempted    INTEGER,
    sub_attempts           INTEGER,
    reversals              INTEGER,
    control_time_sec       INTEGER,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(fighter_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_fighter ON ufc_fight_log(fighter_id, game_date);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_game    ON ufc_fight_log(game_id);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_season  ON ufc_fight_log(season);

-- ── GOLF (PGA Tour) ──────────────────────────────────────────────────────────
-- DataGolf "Scratch Plus" feeds. Tournaments map to ONE games row each
-- (game_id = GOLF_{start_date}_{event_slug}, home_team = event name,
-- away_team = 'FIELD', scores stay NULL). Per-player picks FK to that row and
-- carry picks.player_id = str(dg_id).
CREATE TABLE IF NOT EXISTS golf_players (
    dg_id        INTEGER PRIMARY KEY,        -- DataGolf unified player id
    player_name  TEXT NOT NULL,              -- normalized "Scottie Scheffler" (DG sends "Scheffler, Scottie")
    slug         TEXT NOT NULL,
    country      TEXT,
    amateur      INTEGER DEFAULT 0,
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_golf_players_slug ON golf_players(slug);

CREATE TABLE IF NOT EXISTS golf_tournaments (
    tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id       TEXT NOT NULL REFERENCES games(game_id),
    tour          TEXT NOT NULL DEFAULT 'pga',
    dg_event_id   INTEGER NOT NULL,          -- DataGolf event_id (stable across years)
    season        INTEGER NOT NULL,          -- calendar year
    event_name    TEXT NOT NULL,
    course_name   TEXT,
    start_date    TEXT NOT NULL,
    end_date      TEXT,
    field_size    INTEGER,
    has_cut       INTEGER DEFAULT 1,         -- 0 = no-cut signature event (make_cut not scored)
    status        TEXT DEFAULT 'scheduled',  -- scheduled | in_progress | completed
    created_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(dg_event_id, season)
);
CREATE INDEX IF NOT EXISTS idx_golf_tourn_game ON golf_tournaments(game_id);

-- One row per player per round. Event-level outcome columns (finish_pos,
-- finish_text, made_cut) are duplicated on every round row for that player
-- (ufc_fight_log precedent). game_date = tournament start (the ASOF anchor).
CREATE TABLE IF NOT EXISTS golf_rounds (
    round_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    dg_id        INTEGER NOT NULL,
    player_name  TEXT NOT NULL,
    game_id      TEXT REFERENCES games(game_id),
    dg_event_id  INTEGER NOT NULL,
    season       INTEGER NOT NULL,
    game_date    TEXT NOT NULL,              -- tournament start date (ASOF anchor)
    round_num    INTEGER NOT NULL,
    course_num   INTEGER,
    score        INTEGER,                    -- strokes for the round
    sg_ott   REAL, sg_app REAL, sg_arg REAL, sg_putt REAL, sg_t2g REAL, sg_total REAL,
    driving_dist REAL, driving_acc REAL, gir REAL, scrambling REAL,
    finish_pos   INTEGER,                    -- numeric finish; T10 → 10; NULL for CUT/WD/DQ
    finish_text  TEXT,                       -- raw: '1','T10','CUT','WD','DQ'
    made_cut     INTEGER,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(dg_id, dg_event_id, season, round_num)
);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_player ON golf_rounds(dg_id, game_date);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_game   ON golf_rounds(game_id);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_event  ON golf_rounds(dg_event_id, season);

-- Live DK odds snapshots from the DataGolf betting-tools feed. Mirrors the
-- player_prop_odds shape. One row per player per market per snapshot; matchup
-- rows additionally carry the opponent fields.
CREATE TABLE IF NOT EXISTS golf_odds (
    odds_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    dg_id           INTEGER,
    player_name     TEXT NOT NULL,
    market          TEXT NOT NULL,           -- win | top_5 | top_10 | top_20 | make_cut | matchup_tournament
    bookmaker       TEXT NOT NULL DEFAULT 'draftkings',
    snapshot_type   TEXT NOT NULL,
    snapshot_at     TEXT NOT NULL,
    price           REAL,                    -- American odds, player / "yes" side
    datagolf_prob   REAL,                    -- DataGolf model prob (benchmark only — NOT a model feature)
    opp_dg_id       INTEGER,                 -- matchup rows only
    opp_player_name TEXT,
    opp_price       REAL,
    created_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_golf_odds_game ON golf_odds(game_id, market, dg_id, snapshot_type);

CREATE TABLE IF NOT EXISTS picks (
    pick_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    game_time          TEXT,                -- ISO-8601 scheduled start; from games.commence_time
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
    dk_bet_link        TEXT,               -- DK betslip deep link for the pick side (from The Odds API)
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
    over_link       TEXT,
    under_link      TEXT,
    over_sid        TEXT,
    under_sid       TEXT,
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
    chase_pct       REAL,
    batter_whiff_pct REAL,
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

-- ── LIVE CREDIT TELEMETRY (Phase 3 — in-play betting) ─────────────────────────
-- One row per in-play Odds API fetch. The trigger orchestrator sums today's
-- credits to enforce LIVE_DAILY_CREDIT_CAP and reads MAX(fired_at) for the
-- FG-fetch debounce. `market` holds the fetch purpose (e.g. 'fg_bulk:h2h,...').
CREATE TABLE IF NOT EXISTS live_credit_telemetry (
    telemetry_id   INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    game_id        TEXT,
    market         TEXT NOT NULL,
    credits        INTEGER NOT NULL DEFAULT 0,
    fired_at       TEXT NOT NULL,
    created_at     TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_live_credit_date ON live_credit_telemetry(date);

-- SharpSports read-only account link + synced bet history. Written by the
-- SharpSports Edge Functions (service role); the mobile app reads via the
-- sharpsports-bets Edge Function, never directly.
CREATE TABLE IF NOT EXISTS linked_sportsbook_accounts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_id        TEXT NOT NULL,
    bettor_id          TEXT,
    bettor_account_id  TEXT NOT NULL,
    book               TEXT,
    book_abbr          TEXT,
    book_region        TEXT,
    status             TEXT,
    linked_at          TEXT,
    updated_at         TEXT DEFAULT (datetime('now')),
    UNIQUE(bettor_account_id)
);
CREATE INDEX IF NOT EXISTS idx_linked_accounts_internal ON linked_sportsbook_accounts(internal_id);

CREATE TABLE IF NOT EXISTS synced_bets (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    internal_id    TEXT NOT NULL,
    bettor_id      TEXT,
    bet_id         TEXT NOT NULL,
    book           TEXT,
    type           TEXT,
    status         TEXT,
    placed_at      TEXT,
    settled_at     TEXT,
    odds_american  REAL,
    stake          REAL,
    payout         REAL,
    profit         REAL,
    settled        INTEGER DEFAULT 0,
    raw            TEXT,
    updated_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(bet_id)
);
CREATE INDEX IF NOT EXISTS idx_synced_bets_internal ON synced_bets(internal_id, placed_at);

-- Opening-signal shadow track: the FIRST refresh a game/market crosses the BET
-- threshold is locked here and never overwritten (lock_key UNIQUE). Runs beside
-- the churning `picks` table so we can compare "lock the open" vs "chase the
-- live line", and measure how the line moved (clv_pct vs our opening dk_odds)
-- and which side the public was on after we locked.
CREATE TABLE IF NOT EXISTS opening_signals (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    lock_key           TEXT NOT NULL,        -- game:model (game mkts) | game:model:player (props)
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    player_id          TEXT,                 -- props only; NULL for game-level
    pick_side          TEXT NOT NULL,
    pick_label         TEXT NOT NULL,
    -- opening snapshot (at first BET cross)
    model_probability  REAL NOT NULL,
    dk_implied_prob    REAL,
    edge               REAL,
    dk_odds            REAL,
    scored_line        REAL,
    public_bet_pct     REAL,
    public_money_pct   REAL,
    confidence_tier    TEXT,
    kelly_fraction     REAL,
    recommended_bet    REAL,
    bankroll_at_pick   REAL,
    locked_at          TEXT NOT NULL,
    -- filled at settlement (game-level markets, Phase 1)
    closing_dk_odds    REAL,                 -- DK price on our side at close
    closing_line       REAL,                 -- DK total/spread on our side at close
    clv_pct            REAL,                 -- close_ip - open_ip, pp (positive = line moved toward us)
    line_move_dir      TEXT,                 -- toward | against | flat
    public_side        TEXT,                 -- with_public | contrarian | even
    result             TEXT,                 -- WIN | LOSS | PUSH | NO_ACTION
    profit_flat        REAL,
    profit_kelly       REAL,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (datetime('now')),
    UNIQUE(lock_key)
);
CREATE INDEX IF NOT EXISTS idx_opening_signals_date  ON opening_signals(game_date);
CREATE INDEX IF NOT EXISTS idx_opening_signals_model ON opening_signals(model_id);
CREATE INDEX IF NOT EXISTS idx_opening_signals_settle ON opening_signals(result, line_move_dir, public_side);

-- Parlay leg-correlation coefficients (parlay copula engine, Phase 2).
-- One canonical "+offense x +offense" rho per (sport, market-class pair, team
-- relationship). market_class_a <= market_class_b lexicographically so lookups
-- are order-independent. source='empirical' (estimated from history) overlays
-- the bundled 'prior' values in the app; see scripts/estimate_parlay_correlations.py.
CREATE TABLE IF NOT EXISTS parlay_correlations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    sport           TEXT NOT NULL,
    market_class_a  TEXT NOT NULL,
    market_class_b  TEXT NOT NULL,
    relationship    TEXT NOT NULL,   -- team relationship: 'same' | 'opp' | 'na'
    rho             REAL NOT NULL,   -- canonical correlation, clamped [-0.6, 0.6]
    source          TEXT NOT NULL DEFAULT 'empirical',  -- 'empirical' | 'prior'
    n_pairs         INTEGER,
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(sport, market_class_a, market_class_b, relationship)
);

-- Public parlay track record. One canonical cross-game parlay per (sport, day),
-- legs referencing opening_signals lock_keys (stable, already settled). Settled
-- by tracking/parlay_track_record.settle_parlay_track_record from those legs.
CREATE TABLE IF NOT EXISTS parlay_track_record (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    parlay_key        TEXT NOT NULL,        -- '{sport}:{game_date}'
    sport             TEXT NOT NULL,
    game_date         TEXT NOT NULL,
    n_legs            INTEGER NOT NULL,
    leg_keys          TEXT NOT NULL,        -- JSON array of opening_signals lock_keys
    leg_labels        TEXT NOT NULL,        -- JSON array of pick labels (display)
    leg_odds          TEXT NOT NULL,        -- JSON array of American odds per leg
    combined_decimal  REAL NOT NULL,
    combined_american REAL NOT NULL,
    model_prob        REAL NOT NULL,        -- product of leg model probabilities
    dk_implied_prob   REAL NOT NULL,
    edge              REAL NOT NULL,
    locked_at         TEXT NOT NULL,
    result            TEXT,                 -- WIN | LOSS | PUSH (null = pending)
    profit_flat       REAL,                 -- flat 1-unit P&L
    settled_at        TEXT,
    created_at        TEXT DEFAULT (datetime('now')),
    UNIQUE(parlay_key)
);
CREATE INDEX IF NOT EXISTS idx_parlay_track_date  ON parlay_track_record(game_date);
CREATE INDEX IF NOT EXISTS idx_parlay_track_sport ON parlay_track_record(sport);

-- Signal-flip push notifications (see tracking/push_notifier.py). device_push_tokens
-- holds opted-in Expo tokens; push_sent is the ledger that prevents double-notifying
-- a (lock_key, kind). RLS/policies are Postgres-only (supabase_schema.sql + migration).
CREATE TABLE IF NOT EXISTS device_push_tokens (
    token       TEXT PRIMARY KEY,
    platform    TEXT,
    device_id   TEXT,
    enabled     INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now')),
    last_seen   TEXT DEFAULT (datetime('now'))
);
-- Track-a-bet: a device opts to be notified of big DK line moves on one pick.
-- UI "tracked" state is local on-device; this table tells the notifier what to
-- watch (tracking/push_notifier.notify_line_changes). device_id → token via
-- device_push_tokens. RLS/policies are Postgres-only (supabase_schema.sql).
CREATE TABLE IF NOT EXISTS tracked_bets (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT NOT NULL,
    pick_id      INTEGER NOT NULL,
    game_id      TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    pick_side    TEXT,
    player_id    TEXT,
    pick_label   TEXT,
    locked_odds  REAL,
    locked_line  REAL,
    game_date    TEXT,
    created_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(device_id, pick_id)
);
CREATE TABLE IF NOT EXISTS push_sent (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    lock_key  TEXT NOT NULL,
    kind      TEXT NOT NULL,
    sent_at   TEXT DEFAULT (datetime('now')),
    UNIQUE(lock_key, kind)
);
CREATE INDEX IF NOT EXISTS idx_push_sent_kind ON push_sent(kind);

-- Daily system health check results (tracking/system_health.py). One row per
-- (run_date, check_name); re-runs upsert. CRIT+STALE/EMPTY/ERROR fails the
-- daily pipeline step so the Actions run shows red. RLS/policies are
-- Postgres-only (supabase_schema.sql + migration).
CREATE TABLE IF NOT EXISTS system_health_checks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_date    TEXT NOT NULL,
    check_name  TEXT NOT NULL,
    status      TEXT NOT NULL,          -- OK | STALE | EMPTY | SKIPPED | ERROR
    severity    TEXT NOT NULL,          -- CRIT | WARN
    detail      TEXT,
    latest_seen TEXT,
    checked_at  TEXT NOT NULL,
    UNIQUE(run_date, check_name)
);
CREATE INDEX IF NOT EXISTS idx_health_run_date ON system_health_checks(run_date);

-- Odds API credit telemetry: latest x-requests-used/-remaining observation per
-- UTC day (last write wins — see data/ingestors/odds_quota.py). Feeds the
-- odds_api_credits health check so quota exhaustion warns BEFORE the feed dies
-- (the 2026-08-14 incident: credits ran out, odds/games/picks dead 2.5 days).
CREATE TABLE IF NOT EXISTS odds_api_quota (
    quota_date         TEXT PRIMARY KEY,   -- UTC date of the observation
    requests_used      NUMERIC,
    requests_remaining NUMERIC,
    observed_at        TEXT NOT NULL
);
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
    ("player_savant_stats", "chase_pct", "NUMERIC"),
    ("player_savant_stats", "batter_whiff_pct", "NUMERIC"),
    ("picks", "game_time",          "TEXT"),
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
    # DraftKings betslip deep links (The Odds API includeLinks/includeSids)
    ("odds", "home_link",  "TEXT"),
    ("odds", "away_link",  "TEXT"),
    ("odds", "draw_link",  "TEXT"),
    ("odds", "over_link",  "TEXT"),
    ("odds", "under_link", "TEXT"),
    ("odds", "home_sid",   "TEXT"),
    ("odds", "away_sid",   "TEXT"),
    ("odds", "draw_sid",   "TEXT"),
    ("odds", "over_sid",   "TEXT"),
    ("odds", "under_sid",  "TEXT"),
    ("player_prop_odds", "over_link",  "TEXT"),
    ("player_prop_odds", "under_link", "TEXT"),
    ("player_prop_odds", "over_sid",   "TEXT"),
    ("player_prop_odds", "under_sid",  "TEXT"),
    ("picks", "dk_bet_link", "TEXT"),
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
