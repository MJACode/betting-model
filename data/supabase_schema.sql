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
    -- DraftKings betslip deep links + selection ids (The Odds API includeLinks/includeSids)
    home_link      TEXT,
    away_link      TEXT,
    draw_link      TEXT,
    over_link      TEXT,
    under_link     TEXT,
    home_sid       TEXT,
    away_sid       TEXT,
    draw_sid       TEXT,
    over_sid       TEXT,
    under_sid      TEXT,
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


-- ── WNBA TEAM + PLAYER STATS ──────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS wnba_team_stats (
    stat_id             BIGSERIAL PRIMARY KEY,
    team                TEXT NOT NULL,
    season              INTEGER NOT NULL,
    as_of_date          TEXT NOT NULL,
    games_played        INTEGER,
    points_per_game     NUMERIC,
    points_allowed_pg   NUMERIC,
    pace                NUMERIC,
    off_rating          NUMERIC,
    def_rating          NUMERIC,
    efg_pct             NUMERIC,
    fg_pct              NUMERIC,
    fg3_pct             NUMERIC,
    ft_pct              NUMERIC,
    reb_per_game        NUMERIC,
    ast_per_game        NUMERIC,
    tov_pct             NUMERIC,
    points_last_3       NUMERIC,
    points_last_5       NUMERIC,
    points_home         NUMERIC,
    points_away         NUMERIC,
    wins                INTEGER,
    losses              INTEGER,
    point_differential  NUMERIC,
    created_at          TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_wnba_team ON wnba_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS wnba_player_game_log (
    log_id          BIGSERIAL PRIMARY KEY,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    team            TEXT NOT NULL,
    game_id         TEXT REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    minutes         NUMERIC,
    is_starter      INTEGER,
    points          INTEGER,
    rebounds        INTEGER,
    offensive_reb   INTEGER,
    defensive_reb   INTEGER,
    assists         INTEGER,
    steals          INTEGER,
    blocks          INTEGER,
    turnovers       INTEGER,
    fg_made         INTEGER,
    fg_att          INTEGER,
    fg3_made        INTEGER,
    fg3_att         INTEGER,
    ft_made         INTEGER,
    ft_att          INTEGER,
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_wnba_plog_player ON wnba_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_wnba_plog_game   ON wnba_player_game_log(game_id);

-- Internal-only — pipeline writes via DATABASE_URL (service role bypasses RLS).
-- Add an anon SELECT policy later only if the website needs WNBA stats.
ALTER TABLE wnba_team_stats      ENABLE ROW LEVEL SECURITY;
ALTER TABLE wnba_player_game_log ENABLE ROW LEVEL SECURITY;


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
    public_bet_pct     NUMERIC,            -- % of public bets/tickets on this side (Action Network)
    public_money_pct   NUMERIC,            -- % of public money/handle on this side (Action Network)
    closing_dk_odds    NUMERIC,            -- DK American price on the pick side at close (CLV)
    closing_line       NUMERIC,            -- DK total/spread on the pick side at close (NULL for moneyline)
    clv_pct            NUMERIC,            -- closing_implied_prob - bet_implied_prob, in pp (positive = beat the close)
    clv_captured_at    TEXT,               -- when CLV was recorded (at settlement)
    dk_bet_link        TEXT,               -- DK betslip deep link for the pick side (The Odds API)
    result             TEXT,               -- 'WIN' | 'LOSS' | 'PUSH' | 'NO_ACTION' | NULL
    profit_flat        NUMERIC,
    profit_kelly       NUMERIC,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_picks_date   ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model  ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal ON picks(signal_type, result);


-- ── PUBLIC BETTING ────────────────────────────────────────────────────────────
-- Public betting splits (% of bets, % of money) per game × market × side.
-- Sourced from Action Network at the daily model run. Staging table — the
-- scorer joins the latest snapshot per (game_id, market, side) and copies the
-- two percentages onto each pick row so the daily picks output can show them.
-- market uses our internal full-game keys: 'h2h' | 'spreads' | 'totals'.

CREATE TABLE IF NOT EXISTS public_betting (
    split_id         BIGSERIAL PRIMARY KEY,
    game_id          TEXT NOT NULL REFERENCES games(game_id),
    game_date        TEXT NOT NULL,
    market           TEXT NOT NULL,          -- 'h2h' | 'spreads' | 'totals'
    side             TEXT NOT NULL,          -- 'home' | 'away' | 'over' | 'under'
    book             TEXT NOT NULL DEFAULT 'consensus',  -- Action Network book id / 'consensus'
    public_bet_pct   NUMERIC,                -- % of bets/tickets on this side (0-100)
    public_money_pct NUMERIC,                -- % of money/handle on this side (0-100)
    source           TEXT NOT NULL DEFAULT 'action_network',
    snapshot_at      TEXT NOT NULL,          -- ISO-8601 datetime of this fetch
    created_at       TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, market, side, book)
);

CREATE INDEX IF NOT EXISTS idx_public_betting_game ON public_betting(game_id, market, side);
CREATE INDEX IF NOT EXISTS idx_public_betting_date ON public_betting(game_date);


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
    over_link       TEXT,                        -- DK betslip deep link (over)
    under_link      TEXT,                        -- DK betslip deep link (under)
    over_sid        TEXT,
    under_sid       TEXT,
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
    gb_pct          NUMERIC,                     -- groundball rate (pitcher) — HR suppression signal
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
    batting_order   INTEGER,                     -- 1-9 (NULL for SP not in batting lineup)
    position        TEXT,                        -- 'SP' | 'C' | '1B' | 'SS' | etc.
    hand            TEXT,                        -- batting hand: 'L' | 'R' | 'S'
    is_confirmed    BOOLEAN DEFAULT FALSE,
    snapshot_at     TEXT NOT NULL,
    created_at      TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, team, batting_order, snapshot_at)
);

CREATE INDEX IF NOT EXISTS idx_lineup_game ON lineup_slots(game_id, team);
CREATE INDEX IF NOT EXISTS idx_lineup_date ON lineup_slots(game_date);


-- ── PLAYER HANDEDNESS ─────────────────────────────────────────────────────────
-- Static bat/throw hand per player. One row per player, static across seasons.
-- Used for platoon advantage feature in batter prop models.
-- Populated by: python -m data.ingestors.mlb_stats_ingestor --backfill-hands

CREATE TABLE IF NOT EXISTS player_handedness (
    player_id   TEXT PRIMARY KEY,
    bat_hand    TEXT,   -- 'L', 'R', 'S' (switch)
    throw_hand  TEXT,   -- 'L', 'R', 'S'
    updated_at  TEXT DEFAULT (NOW()::TEXT)
);


-- ── SEASON STATS VIEWS (website) ──────────────────────────────────────────────
-- Aggregated read-only views exposed to the Lovable website via anon SELECT.
-- security_invoker = on so they respect the caller's RLS on the base tables.
-- The base tables (player_game_log, games) have anon SELECT policies.

CREATE OR REPLACE VIEW v_player_season_totals_mlb
WITH (security_invoker = on) AS
SELECT
    player_id,
    (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
    player_type,                                     -- 'batter' | 'pitcher'
    season,
    (array_agg(team ORDER BY game_date DESC))[1] AS team,
    COUNT(DISTINCT game_id)                          AS games_played,
    COALESCE(SUM(CASE WHEN is_starter THEN 1 ELSE 0 END), 0) AS starts,
    COALESCE(SUM(at_bats), 0)        AS at_bats,
    COALESCE(SUM(hits), 0)           AS hits,
    COALESCE(SUM(doubles), 0)        AS doubles,
    COALESCE(SUM(triples), 0)        AS triples,
    COALESCE(SUM(home_runs), 0)      AS home_runs,
    COALESCE(SUM(total_bases), 0)    AS total_bases,
    COALESCE(SUM(rbi), 0)            AS rbi,
    COALESCE(SUM(runs), 0)           AS runs,
    COALESCE(SUM(walks), 0)          AS walks,
    COALESCE(SUM(strikeouts), 0)     AS strikeouts,
    COALESCE(SUM(stolen_bases), 0)   AS stolen_bases,
    COALESCE(SUM(p_strikeouts), 0)   AS p_strikeouts,
    COALESCE(SUM(p_walks), 0)        AS p_walks,
    COALESCE(SUM(p_hits_allowed), 0) AS p_hits_allowed,
    COALESCE(SUM(p_earned_runs), 0)  AS p_earned_runs,
    COALESCE(SUM(p_home_runs), 0)    AS p_home_runs,
    COALESCE(SUM(innings_pitched), 0) AS innings_pitched,
    COALESCE(SUM(pitches), 0)        AS pitches
FROM player_game_log
GROUP BY player_id, player_type, season;

CREATE OR REPLACE VIEW v_team_season_record_mlb
WITH (security_invoker = on) AS
WITH team_games AS (
    SELECT
        season,
        home_team AS team,
        home_score AS runs_scored,
        away_score AS runs_allowed,
        CASE WHEN home_win = 1 THEN 1 ELSE 0 END AS won,
        CASE WHEN home_win = 0 THEN 1 ELSE 0 END AS lost
    FROM games
    WHERE sport = 'MLB' AND home_score IS NOT NULL AND home_win IS NOT NULL
    UNION ALL
    SELECT
        season,
        away_team AS team,
        away_score AS runs_scored,
        home_score AS runs_allowed,
        CASE WHEN home_win = 0 THEN 1 ELSE 0 END AS won,
        CASE WHEN home_win = 1 THEN 1 ELSE 0 END AS lost
    FROM games
    WHERE sport = 'MLB' AND home_score IS NOT NULL AND home_win IS NOT NULL
)
SELECT
    team,
    season,
    COUNT(*)                                  AS games_played,
    SUM(won)                                  AS wins,
    SUM(lost)                                 AS losses,
    SUM(runs_scored)::NUMERIC                 AS runs_scored,
    SUM(runs_allowed)::NUMERIC                AS runs_allowed,
    SUM(runs_scored - runs_allowed)::NUMERIC  AS run_differential
FROM team_games
GROUP BY team, season;

GRANT SELECT ON v_player_season_totals_mlb TO anon, authenticated;
GRANT SELECT ON v_team_season_record_mlb   TO anon, authenticated;

-- WNBA season totals per (player_id, season) — backs the mobile Stats leaderboard.
-- security_invoker = on, so anon needs SELECT on the base table:
CREATE POLICY "anon read wnba_player_game_log"
    ON wnba_player_game_log FOR SELECT TO anon, authenticated USING (true);

CREATE OR REPLACE VIEW v_player_season_totals_wnba
WITH (security_invoker = on) AS
SELECT
    player_id,
    (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
    season,
    (array_agg(team ORDER BY game_date DESC))[1] AS team,
    COUNT(DISTINCT game_id)      AS games_played,
    COALESCE(SUM(minutes), 0)    AS minutes,
    COALESCE(SUM(points), 0)     AS points,
    COALESCE(SUM(rebounds), 0)   AS rebounds,
    COALESCE(SUM(assists), 0)    AS assists,
    COALESCE(SUM(fg3_made), 0)   AS threes,
    COALESCE(SUM(steals), 0)     AS steals,
    COALESCE(SUM(blocks), 0)     AS blocks,
    COALESCE(SUM(turnovers), 0)  AS turnovers,
    COALESCE(SUM(COALESCE(points,0) + COALESCE(rebounds,0) + COALESCE(assists,0)), 0) AS pra
FROM wnba_player_game_log
GROUP BY player_id, season;

GRANT SELECT ON v_player_season_totals_wnba TO anon, authenticated;


-- ── PLAYER LAST-N-GAME WINDOW TOTALS (mobile Stats leaderboard) ───────────────
-- Rank every player by a stat over their last N games (3/5/10/20) or the full
-- season. p_window = NULL → whole season. Same column shape as the
-- v_player_season_totals_* views, so the mobile client reuses SeasonTotalsRow.
-- SECURITY INVOKER → respects the anon SELECT policies on the base tables.
-- Migration: add_player_window_totals_rpcs

CREATE OR REPLACE FUNCTION public.player_window_totals_mlb(
    p_season integer,
    p_player_type text,
    p_window integer DEFAULT NULL
)
RETURNS TABLE (
    player_id text, player_name text, player_type text, season integer, team text,
    games_played bigint, starts bigint, at_bats bigint, hits bigint, doubles bigint,
    triples bigint, home_runs bigint, total_bases bigint, rbi bigint, runs bigint,
    walks bigint, strikeouts bigint, stolen_bases bigint, p_strikeouts bigint,
    p_walks bigint, p_hits_allowed bigint, p_earned_runs bigint, p_home_runs bigint,
    innings_pitched numeric, pitches bigint
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT pgl.*,
               ROW_NUMBER() OVER (PARTITION BY pgl.player_id
                                  ORDER BY pgl.game_date DESC, pgl.game_id DESC) AS rn
        FROM player_game_log pgl
        WHERE pgl.season = p_season AND pgl.player_type = p_player_type
    )
    SELECT
        player_id,
        (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
        player_type, p_season AS season,
        (array_agg(team ORDER BY game_date DESC))[1] AS team,
        COUNT(DISTINCT game_id) AS games_played,
        COALESCE(SUM(CASE WHEN is_starter THEN 1 ELSE 0 END), 0) AS starts,
        COALESCE(SUM(at_bats),0), COALESCE(SUM(hits),0), COALESCE(SUM(doubles),0),
        COALESCE(SUM(triples),0), COALESCE(SUM(home_runs),0), COALESCE(SUM(total_bases),0),
        COALESCE(SUM(rbi),0), COALESCE(SUM(runs),0), COALESCE(SUM(walks),0),
        COALESCE(SUM(strikeouts),0), COALESCE(SUM(stolen_bases),0),
        COALESCE(SUM(p_strikeouts),0), COALESCE(SUM(p_walks),0), COALESCE(SUM(p_hits_allowed),0),
        COALESCE(SUM(p_earned_runs),0), COALESCE(SUM(p_home_runs),0),
        COALESCE(SUM(innings_pitched),0), COALESCE(SUM(pitches),0)
    FROM ranked
    WHERE p_window IS NULL OR rn <= p_window
    GROUP BY player_id, player_type;
$$;

CREATE OR REPLACE FUNCTION public.player_window_totals_wnba(
    p_season integer,
    p_window integer DEFAULT NULL
)
RETURNS TABLE (
    player_id text, player_name text, season integer, team text, games_played bigint,
    minutes numeric, points bigint, rebounds bigint, assists bigint, threes bigint,
    steals bigint, blocks bigint, turnovers bigint, pra bigint
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT w.*,
               ROW_NUMBER() OVER (PARTITION BY w.player_id
                                  ORDER BY w.game_date DESC, w.game_id DESC) AS rn
        FROM wnba_player_game_log w
        WHERE w.season = p_season
    )
    SELECT
        player_id,
        (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
        p_season AS season,
        (array_agg(team ORDER BY game_date DESC))[1] AS team,
        COUNT(DISTINCT game_id) AS games_played,
        COALESCE(SUM(minutes),0), COALESCE(SUM(points),0), COALESCE(SUM(rebounds),0),
        COALESCE(SUM(assists),0), COALESCE(SUM(fg3_made),0), COALESCE(SUM(steals),0),
        COALESCE(SUM(blocks),0), COALESCE(SUM(turnovers),0),
        COALESCE(SUM(COALESCE(points,0)+COALESCE(rebounds,0)+COALESCE(assists,0)),0) AS pra
    FROM ranked
    WHERE p_window IS NULL OR rn <= p_window
    GROUP BY player_id;
$$;

GRANT EXECUTE ON FUNCTION public.player_window_totals_mlb(integer, text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_window_totals_wnba(integer, integer)       TO anon, authenticated;


-- ── LIVE (IN-PLAY) BETTING ────────────────────────────────────────────────────
-- Phase 1: game-state poller writes one snapshot per in-progress game every
-- LIVE_POLL_INTERVAL_SEC. Comparing consecutive snapshots produces
-- live_trigger_events, which a later phase consumes to fire Odds API calls.
-- All free — MLB Stats API only.

CREATE TABLE IF NOT EXISTS live_game_state (
    state_id            BIGSERIAL PRIMARY KEY,
    game_id             TEXT NOT NULL REFERENCES games(game_id),
    snapshot_at         TEXT NOT NULL,
    inning              SMALLINT,
    inning_half         TEXT,
    outs                SMALLINT,
    bases_state         TEXT,                  -- '000' .. '111'
    home_score          SMALLINT,
    away_score          SMALLINT,
    current_pitcher_id  TEXT,
    current_batter_id   TEXT,
    on_deck_batter_id   TEXT,
    abstract_game_state TEXT,                  -- 'Preview' | 'Live' | 'Final'
    raw_state           JSONB,                 -- truncated linescore for debug
    created_at          TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_live_state_game ON live_game_state(game_id, snapshot_at);

CREATE TABLE IF NOT EXISTS live_trigger_events (
    trigger_id     BIGSERIAL PRIMARY KEY,
    game_id        TEXT NOT NULL REFERENCES games(game_id),
    fired_at       TEXT NOT NULL,
    trigger_type   TEXT NOT NULL,              -- inning_change | score_change | pitching_change | due_up_change
    detail         TEXT,
    prev_state_id  BIGINT REFERENCES live_game_state(state_id),
    new_state_id   BIGINT REFERENCES live_game_state(state_id),
    dispatched_at  TEXT,                       -- NULL = pending dispatch
    created_at     TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_live_trigger_game    ON live_trigger_events(game_id, fired_at);
CREATE INDEX IF NOT EXISTS idx_live_trigger_pending ON live_trigger_events(dispatched_at);


-- ── PLAYS (Phase 2 — live win-probability training corpus) ────────────────────
-- One row per play in a completed game. Sourced from MLB Stats API
-- /api/v1.1/game/{gamePk}/feed/live → liveData.plays.allPlays[]. The state
-- *before* the play is the model input; the eventual home_won is the label.

CREATE TABLE IF NOT EXISTS plays (
    play_id            BIGSERIAL PRIMARY KEY,
    game_id            TEXT NOT NULL REFERENCES games(game_id),
    season             INTEGER NOT NULL,
    play_index         INTEGER NOT NULL,
    inning             SMALLINT,
    half_inning        TEXT,
    outs_before        SMALLINT,
    bases_before       TEXT,
    score_home_before  SMALLINT,
    score_away_before  SMALLINT,
    batter_id          TEXT,
    pitcher_id         TEXT,
    bat_side           TEXT,
    pitch_hand         TEXT,
    event_type         TEXT,
    description        TEXT,
    runs_on_play       SMALLINT,
    outs_added         SMALLINT,
    outs_after         SMALLINT,
    bases_after        TEXT,
    score_home_after   SMALLINT,
    score_away_after   SMALLINT,
    home_won           SMALLINT,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, play_index)
);

CREATE INDEX IF NOT EXISTS idx_plays_game   ON plays(game_id, play_index);
CREATE INDEX IF NOT EXISTS idx_plays_season ON plays(season);

-- Internal-only — pipeline writes via DATABASE_URL (service role bypasses RLS).
ALTER TABLE plays ENABLE ROW LEVEL SECURITY;
