-- ============================================================================
-- Supabase / Postgres schema for the betting model.
-- Run this once in the Supabase SQL editor to create all tables.
--
-- To apply: paste into Supabase → SQL Editor → Run
-- Safe to re-run: all statements use IF NOT EXISTS.
-- ============================================================================


-- ── GAMES ────────────────────────────────────────────────────────────────────
-- One row per game. Populated by SBR loader (historical) and stats ingestors
-- (live). home_score / away_score are NULL until the game is final.

CREATE TABLE IF NOT EXISTS games (
    game_id        TEXT PRIMARY KEY,        -- "{sport}_{date}_{away}_{home}"
    sport          TEXT NOT NULL,           -- 'MLB' | 'NHL'
    season         INTEGER NOT NULL,
    game_date      TEXT NOT NULL,           -- ISO-8601 YYYY-MM-DD
    home_team      TEXT NOT NULL,           -- 3-letter abbrev
    away_team      TEXT NOT NULL,
    home_score     NUMERIC,                 -- NULL until final
    away_score     NUMERIC,
    home_score_f5  NUMERIC,                 -- runs through 5 innings (NULL until populated)
    away_score_f5  NUMERIC,
    went_to_ot     INTEGER DEFAULT 0,       -- 1 if NHL game went to OT/SO
    home_win       INTEGER,                 -- 1/0/NULL — full game result
    home_win_reg   INTEGER,                 -- 1/0/NULL — NHL regulation only
    regulation_tie INTEGER DEFAULT 0,       -- 1 if NHL game tied after 60 min
    commence_time  TEXT,                    -- ISO-8601 datetime of scheduled first pitch / puck drop
    data_source    TEXT,                    -- 'sbr' | 'sbr_csv' | 'live'
    created_at     TEXT DEFAULT (NOW()::TEXT),
    updated_at     TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_games_date  ON games(game_date);
CREATE INDEX IF NOT EXISTS idx_games_sport ON games(sport, season);


-- ── ODDS ─────────────────────────────────────────────────────────────────────
-- One row per game × market × snapshot. Multiple snapshots per game (open,
-- close, live refreshes). We always use the most recent snapshot for scoring.

CREATE TABLE IF NOT EXISTS odds (
    odds_id        BIGSERIAL PRIMARY KEY,
    game_id        TEXT NOT NULL REFERENCES games(game_id),
    sport          TEXT NOT NULL,
    market         TEXT NOT NULL,           -- 'h2h' | 'spreads' | 'totals' | 'h2h_3way'
    bookmaker      TEXT NOT NULL,           -- 'draftkings' | 'sbr_consensus'
    snapshot_type  TEXT NOT NULL,           -- 'open' | 'close' | 'live'
    snapshot_at    TEXT NOT NULL,           -- ISO-8601 datetime of this snapshot
    home_price     NUMERIC,                 -- American odds (e.g. -150, +130)
    away_price     NUMERIC,
    draw_price     NUMERIC,                 -- NHL 3-way only
    spread_home    NUMERIC,                 -- run/puck line value (e.g. -1.5)
    total_line     NUMERIC,                 -- O/U total (e.g. 8.5)
    over_price     NUMERIC,
    under_price    NUMERIC,
    created_at     TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_odds_game ON odds(game_id, market, snapshot_type);
CREATE INDEX IF NOT EXISTS idx_odds_date ON odds(snapshot_at);


-- ── INJURIES ─────────────────────────────────────────────────────────────────
-- Updated daily. One row per player per status change.

CREATE TABLE IF NOT EXISTS injuries (
    injury_id          BIGSERIAL PRIMARY KEY,
    sport              TEXT NOT NULL,
    team               TEXT NOT NULL,
    player_name        TEXT NOT NULL,
    player_id          TEXT,
    status             TEXT NOT NULL,       -- 'Out' | 'Day-To-Day' | 'IL10' | 'IL15' | 'IL60' | 'Returning'
    injury_type        TEXT,
    scenario           TEXT NOT NULL,       -- 'A' | 'B' | 'C'
    severity_weight    NUMERIC DEFAULT 1.0,
    return_ramp_factor NUMERIC,
    games_since_return INTEGER,
    activation_date    TEXT,
    report_date        TEXT NOT NULL,
    created_at         TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_injuries_team_date ON injuries(sport, team, report_date);
CREATE INDEX IF NOT EXISTS idx_injuries_player    ON injuries(player_name, sport);


-- ── MLB TEAM STATS ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mlb_team_stats (
    stat_id              BIGSERIAL PRIMARY KEY,
    team                 TEXT NOT NULL,
    season               INTEGER NOT NULL,
    as_of_date           TEXT NOT NULL,
    games_played         INTEGER,
    ops                  NUMERIC,
    wrc_plus             NUMERIC,
    woba                 NUMERIC,
    k_pct                NUMERIC,
    bb_pct               NUMERIC,
    iso                  NUMERIC,
    babip                NUMERIC,
    runs_per_game        NUMERIC,
    runs_last_5          NUMERIC,
    runs_last_10         NUMERIC,
    runs_last_15         NUMERIC,
    runs_per_game_home   NUMERIC,
    runs_per_game_away   NUMERIC,
    team_era             NUMERIC,
    bullpen_era          NUMERIC,
    team_whip            NUMERIC,
    team_fip             NUMERIC,
    wins                 INTEGER,
    losses               INTEGER,
    run_differential     INTEGER,
    created_at           TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, season, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_mlb_team ON mlb_team_stats(team, as_of_date);


-- ── MLB PITCHER STATS ─────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mlb_pitcher_stats (
    stat_id           BIGSERIAL PRIMARY KEY,
    player_name       TEXT NOT NULL,
    player_id         TEXT,
    team              TEXT NOT NULL,
    season            INTEGER NOT NULL,
    game_date         TEXT NOT NULL,
    game_id           TEXT REFERENCES games(game_id),
    innings_pitched   NUMERIC,
    strikeouts        INTEGER,
    walks             INTEGER,
    hits_allowed      INTEGER,
    earned_runs       INTEGER,
    home_runs_allowed INTEGER,
    era               NUMERIC,
    xfip              NUMERIC,
    whip              NUMERIC,
    k9                NUMERIC,
    bb9               NUMERIC,
    hr9               NUMERIC,
    swstr_pct         NUMERIC,
    csw_pct           NUMERIC,
    era_last3         NUMERIC,
    k9_last3          NUMERIC,
    xfip_last3        NUMERIC,
    created_at        TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_pitcher ON mlb_pitcher_stats(player_name, season);


-- ── MLB BULLPEN WORKLOAD ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS mlb_bullpen_stats (
    stat_id     BIGSERIAL PRIMARY KEY,
    game_date   TEXT NOT NULL,
    season      INTEGER NOT NULL,
    team        TEXT NOT NULL,
    game_pk     INTEGER NOT NULL,
    player_id   INTEGER,
    player_name TEXT,
    ip          NUMERIC,
    er          INTEGER,
    k           INTEGER,
    bb          INTEGER,
    pitches     INTEGER,
    created_at  TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_date, team)
);

CREATE INDEX IF NOT EXISTS idx_bullpen_team_date ON mlb_bullpen_stats(team, game_date);


-- ── NHL TEAM STATS ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nhl_team_stats (
    stat_id            BIGSERIAL PRIMARY KEY,
    team               TEXT NOT NULL,
    season             INTEGER NOT NULL,
    as_of_date         TEXT NOT NULL,
    games_played       INTEGER,
    goals_per_game     NUMERIC,
    shots_per_game     NUMERIC,
    corsi_for_pct      NUMERIC,
    xgf_pct            NUMERIC,
    power_play_pct     NUMERIC,
    goals_last_5       NUMERIC,
    goals_last_10      NUMERIC,
    goals_home         NUMERIC,
    goals_away         NUMERIC,
    goals_against_pg   NUMERIC,
    shots_against_pg   NUMERIC,
    penalty_kill_pct   NUMERIC,
    xga_pct            NUMERIC,
    wins               INTEGER,
    losses             INTEGER,
    ot_losses          INTEGER,
    goal_differential  INTEGER,
    regulation_wins    INTEGER,
    regulation_losses  INTEGER,
    regulation_ties    INTEGER,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, season, as_of_date)
);

CREATE INDEX IF NOT EXISTS idx_nhl_team ON nhl_team_stats(team, as_of_date);


-- ── NHL GOALIE STATS ──────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nhl_goalie_stats (
    stat_id       BIGSERIAL PRIMARY KEY,
    player_name   TEXT NOT NULL,
    player_id     TEXT,
    team          TEXT NOT NULL,
    season        INTEGER NOT NULL,
    game_date     TEXT NOT NULL,
    game_id       TEXT REFERENCES games(game_id),
    saves         INTEGER,
    shots_faced   INTEGER,
    goals_allowed INTEGER,
    save_pct      NUMERIC,
    gaa           NUMERIC,
    gsaa          NUMERIC,
    xga           NUMERIC,
    save_pct_last5 NUMERIC,
    gaa_last5     NUMERIC,
    gsaa_last5    NUMERIC,
    created_at    TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_goalie ON nhl_goalie_stats(player_name, season);


-- ── NHL SKATER STATS (Phase 2) ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nhl_skater_stats (
    stat_id         BIGSERIAL PRIMARY KEY,
    player_name     TEXT NOT NULL,
    player_id       TEXT,
    team            TEXT NOT NULL,
    position        TEXT,
    season          INTEGER NOT NULL,
    game_date       TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    goals           INTEGER DEFAULT 0,
    assists         INTEGER DEFAULT 0,
    points          INTEGER DEFAULT 0,
    shots_on_goal   INTEGER DEFAULT 0,
    time_on_ice     NUMERIC,
    goals_per_game  NUMERIC,
    shots_per_game  NUMERIC,
    points_per_game NUMERIC,
    corsi_pct       NUMERIC,
    xgf_pct         NUMERIC,
    goals_last5     NUMERIC,
    shots_last5     NUMERIC,
    toi_last5       NUMERIC,
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_date)
);

CREATE INDEX IF NOT EXISTS idx_skater ON nhl_skater_stats(player_name, season);


-- ── PICKS — Paper Trading Log ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS picks (
    pick_id            BIGSERIAL PRIMARY KEY,
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    pick_side          TEXT NOT NULL,       -- 'home' | 'away' | 'over' | 'under' | 'draw'
    pick_label         TEXT NOT NULL,
    model_probability  NUMERIC NOT NULL,
    dk_implied_prob    NUMERIC NOT NULL,
    edge               NUMERIC NOT NULL,
    dk_odds            NUMERIC NOT NULL,
    scored_line        NUMERIC,
    kelly_fraction     NUMERIC NOT NULL,
    recommended_bet    NUMERIC NOT NULL,
    bankroll_at_pick   NUMERIC NOT NULL,
    injury_flag        TEXT,
    injury_detail      TEXT,
    signal_type        TEXT NOT NULL DEFAULT 'BET',
    confidence_tier    TEXT,
    result             TEXT,               -- 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION' | NULL
    profit_flat        NUMERIC,
    profit_kelly       NUMERIC,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_picks_date   ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model  ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal ON picks(signal_type, result);


-- ── MODEL REGISTRY ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS model_registry (
    registry_id       BIGSERIAL PRIMARY KEY,
    model_id          TEXT NOT NULL,
    version           TEXT NOT NULL,
    trained_on        TEXT NOT NULL,
    train_seasons     TEXT NOT NULL,        -- JSON array
    holdout_season    INTEGER,
    holdout_accuracy  NUMERIC,
    holdout_roi       NUMERIC,
    holdout_picks     INTEGER,
    calibration_score NUMERIC,
    is_active         INTEGER DEFAULT 1,
    model_path        TEXT,
    notes             TEXT,
    created_at        TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(model_id, version)
);


-- ── PIPELINE LOG ──────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pipeline_log (
    log_id      BIGSERIAL PRIMARY KEY,
    run_date    TEXT NOT NULL,
    step        TEXT NOT NULL,
    status      TEXT NOT NULL,
    records_in  INTEGER DEFAULT 0,
    records_out INTEGER DEFAULT 0,
    duration_s  NUMERIC,
    error_msg   TEXT,
    created_at  TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_pipeline_date ON pipeline_log(run_date, step);


-- ── PLAYER GAME LOG (Props Phase 2) ──────────────────────────────────────────
-- Per-player per-game actual stats. Training backbone for all prop models.
-- Populated by: python -m data.ingestors.mlb_stats_ingestor --backfill-game-log 2019 2025

CREATE TABLE IF NOT EXISTS player_game_log (
    log_id              BIGSERIAL PRIMARY KEY,
    player_id           TEXT NOT NULL,          -- MLBAM player_id
    player_name         TEXT NOT NULL,
    team                TEXT NOT NULL,           -- 3-letter abbrev
    player_type         TEXT NOT NULL,           -- 'pitcher' | 'batter'
    game_id             TEXT REFERENCES games(game_id),
    game_date           TEXT NOT NULL,
    season              INTEGER NOT NULL,
    -- Pitcher stats (NULL for batters)
    innings_pitched     NUMERIC,
    pitches             INTEGER,
    is_starter          BOOLEAN,
    p_strikeouts        INTEGER,                 -- Ks thrown
    p_walks             INTEGER,
    p_hits_allowed      INTEGER,
    p_earned_runs       INTEGER,
    p_home_runs         INTEGER,
    -- Batter stats (NULL for pitchers)
    at_bats             INTEGER,
    hits                INTEGER,
    doubles             INTEGER,
    triples             INTEGER,
    home_runs           INTEGER,
    rbi                 INTEGER,
    runs                INTEGER,
    walks               INTEGER,
    strikeouts          INTEGER,                 -- Ks taken at the plate
    stolen_bases        INTEGER,
    total_bases         INTEGER,
    batting_order       INTEGER,                 -- lineup slot 1-9
    created_at          TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_id, player_type)
);

CREATE INDEX IF NOT EXISTS idx_player_game_log_player ON player_game_log(player_id, season);
CREATE INDEX IF NOT EXISTS idx_player_game_log_date   ON player_game_log(game_date);
CREATE INDEX IF NOT EXISTS idx_player_game_log_team   ON player_game_log(team, game_date);


-- ── PLAYER PROP ODDS ─────────────────────────────────────────────────────────
-- Live DK player prop lines collected daily from The Odds API.
-- One row per player × market × game × snapshot.
-- Populated by: python -m data.ingestors.prop_odds_ingestor

CREATE TABLE IF NOT EXISTS player_prop_odds (
    prop_id         BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    player_name     TEXT NOT NULL,               -- as returned by The Odds API
    team            TEXT,                        -- 3-letter abbrev (NULL if unmatched)
    market          TEXT NOT NULL,               -- 'pitcher_strikeouts' | 'batter_hits' | etc.
    bookmaker       TEXT NOT NULL DEFAULT 'draftkings',
    snapshot_type   TEXT NOT NULL,               -- 'open' | 'live'
    snapshot_at     TEXT NOT NULL,
    line            NUMERIC,                     -- O/U line value (e.g. 7.5)
    over_price      NUMERIC,                     -- American odds
    under_price     NUMERIC,
    created_at      TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_prop_odds_game   ON player_prop_odds(game_id, market);
CREATE INDEX IF NOT EXISTS idx_prop_odds_player ON player_prop_odds(player_name, game_date);
CREATE INDEX IF NOT EXISTS idx_prop_odds_date   ON player_prop_odds(game_date);


-- ── PLAYER SAVANT STATS ───────────────────────────────────────────────────────
-- Season-level Statcast metrics from Baseball Savant leaderboard CSV.
-- Used as features in prop models (not game-level — season aggregates).
-- Populated by: python -m data.ingestors.baseball_savant_ingestor --backfill 2019 2025

CREATE TABLE IF NOT EXISTS player_savant_stats (
    stat_id         BIGSERIAL PRIMARY KEY,
    player_id       TEXT NOT NULL,               -- MLBAM player_id
    player_name     TEXT NOT NULL,
    team            TEXT,
    player_type     TEXT NOT NULL,               -- 'pitcher' | 'batter'
    season          INTEGER NOT NULL,
    -- Pitcher Statcast metrics
    k_pct           NUMERIC,                     -- strikeout rate
    bb_pct          NUMERIC,                     -- walk rate
    whiff_pct       NUMERIC,                     -- swing-and-miss rate
    swstr_pct       NUMERIC,                     -- swinging strike rate
    csw_pct         NUMERIC,                     -- called strike + whiff rate
    xera            NUMERIC,                     -- expected ERA
    ff_pct          NUMERIC,                     -- 4-seam fastball usage %
    sl_pct          NUMERIC,                     -- slider usage %
    ch_pct          NUMERIC,                     -- changeup usage %
    cu_pct          NUMERIC,                     -- curveball usage %
    si_pct          NUMERIC,                     -- sinker usage %
    fc_pct          NUMERIC,                     -- cutter usage %
    avg_velocity    NUMERIC,                     -- avg fastball velocity (mph)
    -- Batter Statcast metrics
    batter_k_pct    NUMERIC,                     -- strikeout rate (batter)
    batter_bb_pct   NUMERIC,                     -- walk rate (batter)
    batting_avg     NUMERIC,
    slg_pct         NUMERIC,
    obp             NUMERIC,
    woba            NUMERIC,
    xwoba           NUMERIC,
    xba             NUMERIC,
    xslg            NUMERIC,
    barrel_pct      NUMERIC,                     -- barrel rate
    hard_hit_pct    NUMERIC,                     -- hard hit rate (exit velo >= 95mph)
    launch_angle    NUMERIC,                     -- avg launch angle
    exit_velocity   NUMERIC,                     -- avg exit velocity
    sprint_speed    NUMERIC,                     -- ft/s (from Statcast)
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, season, player_type)
);

CREATE INDEX IF NOT EXISTS idx_savant_player ON player_savant_stats(player_id, season);
CREATE INDEX IF NOT EXISTS idx_savant_type   ON player_savant_stats(player_type, season);


-- ── UMPIRES ───────────────────────────────────────────────────────────────────
-- Home plate umpire per game with historical K rate.
-- Used as feature in mlb_prop_pitcher_k model.
-- Populated by: python -m data.ingestors.umpire_ingestor (Phase 2)

CREATE TABLE IF NOT EXISTS umpires (
    umpire_id       BIGSERIAL PRIMARY KEY,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    umpire_name     TEXT NOT NULL,
    umpire_source   TEXT,                        -- 'umpscorecard' | 'manual'
    k_per_game      NUMERIC,                     -- historical avg total Ks per game (both teams)
    k_plus_minus    NUMERIC,                     -- vs league avg per game
    favor_score     NUMERIC,                     -- UmpScorecard favor metric if available
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id)
);

CREATE INDEX IF NOT EXISTS idx_umpires_date ON umpires(game_date);
CREATE INDEX IF NOT EXISTS idx_umpires_name ON umpires(umpire_name);


-- ── LINEUP SLOTS ─────────────────────────────────────────────────────────────
-- Confirmed batting lineups per game. Required for batter prop scoring.
-- Populated by: python -m data.ingestors.lineup_ingestor (Phase 2)
-- Runs ~1 hour before first pitch once lineups are posted.

CREATE TABLE IF NOT EXISTS lineup_slots (
    slot_id         BIGSERIAL PRIMARY KEY,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    team            TEXT NOT NULL,               -- 3-letter abbrev
    player_id       TEXT,                        -- MLBAM player_id
    player_name     TEXT NOT NULL,
    batting_order   INTEGER,                     -- 1-9; NULL for SP not in batting lineup
    position        TEXT,                        -- 'SP' | 'C' | '1B' | 'SS' | etc.
    hand            TEXT,                        -- batting hand: 'L' | 'R' | 'S'
    is_confirmed    BOOLEAN DEFAULT FALSE,
    snapshot_at     TEXT NOT NULL,
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, team, batting_order, snapshot_at)
);

CREATE INDEX IF NOT EXISTS idx_lineup_game ON lineup_slots(game_id, team);
CREATE INDEX IF NOT EXISTS idx_lineup_date ON lineup_slots(game_date);
