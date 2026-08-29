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


-- ── NBA TEAM + PLAYER STATS ───────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS nba_team_stats (
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
CREATE INDEX IF NOT EXISTS idx_nba_team ON nba_team_stats(team, as_of_date);

CREATE TABLE IF NOT EXISTS nba_player_game_log (
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
CREATE INDEX IF NOT EXISTS idx_nba_plog_player ON nba_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_nba_plog_game   ON nba_player_game_log(game_id);

-- Internal-only — pipeline writes via DATABASE_URL (service role bypasses RLS).
-- nba_player_game_log gets an anon SELECT policy below (backs the mobile Stats
-- leaderboard); nba_team_stats stays locked down.
ALTER TABLE nba_team_stats       ENABLE ROW LEVEL SECURITY;
ALTER TABLE nba_player_game_log  ENABLE ROW LEVEL SECURITY;


-- ── NFL PLAYER STATS ──────────────────────────────────────────────────────────
-- Per-player per-game stats from nflverse's weekly player-stats export
-- (stats_player_week_{season}.csv), ingested by
-- data/ingestors/nfl_player_stats_ingestor.py. Backs the mobile Stats tab NFL
-- leaderboard via v_player_season_totals_nfl + player_window_totals_nfl +
-- player_recent_games_nfl. game_id is "NFL_{nflverse_id}" (platform convention)
-- with NO FK to games — only wind/opener pick games ever get a games row, while
-- this log covers the whole league. Display/stats only — no model reads it.
-- Migration: add_nfl_player_stats_leaderboard (applied 2026-08-19).

CREATE TABLE IF NOT EXISTS nfl_player_game_log (
    log_id          BIGSERIAL PRIMARY KEY,
    player_id       TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    pos             TEXT,
    team            TEXT NOT NULL,
    opponent        TEXT,
    game_id         TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    completions     INTEGER, attempts INTEGER,
    passing_yards   NUMERIC, passing_tds INTEGER, interceptions INTEGER,
    carries         INTEGER, rushing_yards NUMERIC, rushing_tds INTEGER,
    receptions      INTEGER, targets INTEGER,
    receiving_yards NUMERIC, receiving_tds INTEGER,
    def_sacks       NUMERIC, def_interceptions INTEGER,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_player ON nfl_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_season ON nfl_player_game_log(season);

-- Pipeline writes via DATABASE_URL (service role bypasses RLS); the mobile
-- anon key reads through the invoker view/RPCs, so it needs SELECT.
ALTER TABLE nfl_player_game_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read nfl_player_game_log"
    ON nfl_player_game_log FOR SELECT TO anon, authenticated USING (true);

-- ── NFL player-prop modelling data (2026-08-23) ─────────────────────────────
-- Applied by data/migrations/add_nfl_prop_modeling_tables.sql.
-- NFL player-prop modelling data (2026-08-23).
--
-- Three changes, all additive:
--   1. nfl_player_game_log gains the modelling columns the display ingest was
--      already downloading and discarding (usage shares, air yards, EPA, the
--      solo/assist tackle split, kicking splits). The mobile views and RPCs
--      select explicit column lists, so they are unaffected. The table's
--      docstring said "no model reads this table" — as of this migration the
--      NFL prop feature engine does.
--   2. nfl_team_game_stats — one row per team per game: offensive volume (the
--      denominator every usage share is taken against), plus the pre-game
--      market and environment context (spread, total, roof, wind, temp, rest).
--      Also the source of opponent-defence-allowed features, read from the
--      defending team's perspective.
--   3. nfl_snap_counts — snap share, the cleanest availability signal and the
--      main driver of the tackles+assists market. nflverse keys snaps on
--      pfr_player_id with no gsis id, so rows carry a normalised name key and
--      the feature engine joins on (norm_name, team, game_id) — verified 98-100%
--      coverage against the weekly stats on every pool that matters, with zero
--      duplicate keys.
--
-- No FK to games: only NFL games with a wind/opener pick ever get a games row,
-- while these tables cover the whole league (the nfl_player_game_log precedent).

ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS sacks_suffered      NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS passing_air_yards   NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS passing_epa         NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS rushing_first_downs INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_air_yards NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_yac       NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS receiving_epa       NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS target_share        NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS air_yards_share     NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS wopr                NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS racr                NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_tackles_solo    NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_tackle_assists  NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS def_qb_hits         NUMERIC;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS fg_made             INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS fg_att              INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS pat_made            INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS pat_att             INTEGER;
ALTER TABLE nfl_player_game_log ADD COLUMN IF NOT EXISTS norm_name           TEXT;

CREATE INDEX IF NOT EXISTS idx_nfl_plog_normname
    ON nfl_player_game_log(norm_name, team, game_id);

CREATE TABLE IF NOT EXISTS nfl_team_game_stats (
    row_id          BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    game_date       DATE NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    is_home         INTEGER,
    -- offensive volume (the share denominator + the pace proxy)
    pass_attempts   INTEGER,
    carries         INTEGER,
    plays           INTEGER,
    pass_yards      NUMERIC,
    rush_yards      NUMERIC,
    completions     INTEGER,
    targets         INTEGER,
    -- pre-game market + environment context (nflverse games.csv)
    spread_line     NUMERIC,   -- home-relative, as nflverse publishes it
    total_line      NUMERIC,
    roof            TEXT,
    surface         TEXT,
    temp            NUMERIC,
    wind            NUMERIC,
    div_game        INTEGER,
    -- kickoff as a UTC ISO timestamp (gameday + gametime from the nflverse
    -- schedule). The scorer needs it to refuse to price a prop after the
    -- game has started — NFL games have no row in `games` unless they carry
    -- a wind/opener pick, so it cannot come from there.
    commence_time   TIMESTAMPTZ,
    points_for      INTEGER,
    points_against  INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, team)
);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_team   ON nfl_team_game_stats(team, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_season ON nfl_team_game_stats(season, week);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_opp    ON nfl_team_game_stats(opponent, game_date);

CREATE TABLE IF NOT EXISTS nfl_snap_counts (
    row_id          BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    norm_name       TEXT NOT NULL,
    pfr_player_id   TEXT,
    pos             TEXT,
    season          INTEGER NOT NULL,
    week            INTEGER,
    offense_snaps   INTEGER,
    offense_pct     NUMERIC,
    defense_snaps   INTEGER,
    defense_pct     NUMERIC,
    st_snaps        INTEGER,
    st_pct          NUMERIC,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(game_id, team, norm_name)
);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_join   ON nfl_snap_counts(norm_name, team, game_id);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_season ON nfl_snap_counts(season, week);

-- RLS on, no anon policy: modelling inputs, written by the pipeline via the
-- service-role DATABASE_URL. Matches nhl_team_stats / nba_team_stats /
-- ncaaf_team_stats. (nfl_player_game_log keeps its existing anon read policy —
-- the mobile Stats tab reads it.)
ALTER TABLE nfl_team_game_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE nfl_snap_counts     ENABLE ROW LEVEL SECURITY;


-- ── NCAAF (college football, FBS) ────────────────────────────────────────────
-- Source: CollegeFootballData.com (free API key). The canonical team id is the
-- CFBD SCHOOL NAME ("Ohio State", "Miami (OH)"), not a 3-letter abbrev — 136
-- FBS programs collide badly in 3 letters, and CFBD is the source of truth for
-- both the stats and the historical lines. games.home_team/away_team store the
-- school name; game_id uses a slug. Season = calendar year of the FALL (a
-- January bowl belongs to the PRIOR season) and is always threaded explicitly.

-- School registry — also powers Odds API name -> CFBD school resolution
-- (The Odds API lists NCAAF teams with the mascot appended).
CREATE TABLE IF NOT EXISTS ncaaf_teams (
    school          TEXT PRIMARY KEY,
    abbreviation    TEXT,
    mascot          TEXT,
    conference      TEXT,
    division        TEXT,
    classification  TEXT,
    alt_names       TEXT,
    updated_at      TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_teams_conf ON ncaaf_teams(conference);

-- ASOF season-to-date team snapshot. The feature engine reads the newest row
-- with as_of_date <= game_date, then SHRINKS each rate toward the prior
-- season's value by games played (config.NCAAF_PRIOR_SHRINKAGE_K) — a raw
-- season-to-date average is noise for the first month of a 12-game season.
CREATE TABLE IF NOT EXISTS ncaaf_team_stats (
    stat_id                 BIGSERIAL PRIMARY KEY,
    team                    TEXT NOT NULL,
    season                  INTEGER NOT NULL,
    as_of_date              TEXT NOT NULL,
    games_played            INTEGER,
    -- Ratings (CFBD /ratings/*) — the backbone in a 12-game sport
    sp_overall              NUMERIC, sp_offense NUMERIC, sp_defense NUMERIC, sp_special_teams NUMERIC,
    srs                     NUMERIC, elo NUMERIC,
    -- Program strength (recruiting + continuity), the priors that carry weeks 1-5
    talent                  NUMERIC, returning_ppa NUMERIC,
    -- Efficiency (CFBD /stats/season/advanced)
    epa_per_play_off        NUMERIC, epa_per_play_def NUMERIC,
    success_rate_off        NUMERIC, success_rate_def NUMERIC,
    explosiveness_off       NUMERIC, explosiveness_def NUMERIC,
    havoc_rate              NUMERIC, havoc_rate_allowed NUMERIC,
    finishing_drives_off    NUMERIC, finishing_drives_def NUMERIC,
    avg_field_position_off  NUMERIC,
    third_down_rate_off     NUMERIC, third_down_rate_def NUMERIC,
    turnover_margin_pg      NUMERIC,
    -- Tempo — the dominant totals signal in CFB
    plays_per_game          NUMERIC, seconds_per_play NUMERIC,
    -- Scoring / record
    points_per_game         NUMERIC, points_allowed_pg NUMERIC,
    points_last_3           NUMERIC, point_differential NUMERIC,
    wins                    INTEGER, losses INTEGER,
    -- Context
    conference              TEXT, classification TEXT,
    created_at              TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_team ON ncaaf_team_stats(team, as_of_date);

-- Per-team per-game box score. Feeds rolling form + the ASOF stat rebuild.
-- No FK on game_id (the NFL precedent): the log covers every game a tracked
-- team plays, including FCS opponents that may never get a games row.
CREATE TABLE IF NOT EXISTS ncaaf_team_game_log (
    log_id             BIGSERIAL PRIMARY KEY,
    game_id            TEXT NOT NULL,
    team               TEXT NOT NULL,
    opponent           TEXT,
    season             INTEGER NOT NULL,
    week               INTEGER,
    season_type        TEXT,
    game_date          TEXT NOT NULL,
    is_home            INTEGER,
    is_neutral_site    INTEGER,
    is_conference_game INTEGER,
    points             INTEGER, points_allowed INTEGER,
    total_yards        INTEGER, rushing_yards INTEGER, passing_yards INTEGER,
    plays              INTEGER, possession_seconds INTEGER,
    first_downs        INTEGER,
    third_down_conv    INTEGER, third_down_att INTEGER,
    turnovers          INTEGER, penalties INTEGER, penalty_yards INTEGER,
    sacks              NUMERIC, tackles_for_loss NUMERIC,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(team, game_id)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_glog_team ON ncaaf_team_game_log(team, game_date);
CREATE INDEX IF NOT EXISTS idx_ncaaf_glog_game ON ncaaf_team_game_log(game_id);

-- NCAAF quarterback game log (CFBD /games/players, passing + rushing).
-- One row per passer per team-game. `is_primary` flags the QB who threw the
-- most passes for that team in that game -- our proxy for "the starter", since
-- CFBD's box score names participants, not the depth chart.
--
-- WHY THIS EXISTS: a backup QB moves a college line 4-7 points, and QB identity
-- was the one major CFB information channel never ingested. What this table
-- supports is QB CONTINUITY and QUALITY (who has been taking the snaps, how
-- well, and whether that changed) -- NOT "is the starter out this week", which
-- is unknowable pre-kickoff without an injury feed college football does not
-- reliably publish.
CREATE TABLE IF NOT EXISTS ncaaf_qb_game (
    qb_game_id   BIGSERIAL PRIMARY KEY,
    game_id      TEXT NOT NULL,
    team         TEXT NOT NULL,
    opponent     TEXT,
    season       INTEGER NOT NULL,
    week         INTEGER,
    season_type  TEXT,
    game_date    TEXT NOT NULL,
    player_id    TEXT NOT NULL,
    player_name  TEXT,
    is_primary   INTEGER,
    attempts     INTEGER, completions INTEGER,
    pass_yards   INTEGER, pass_td INTEGER, interceptions INTEGER,
    rush_att     INTEGER, rush_yards INTEGER, rush_td INTEGER,
    created_at   TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(game_id, team, player_id)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_team ON ncaaf_qb_game(team, game_date);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_game ON ncaaf_qb_game(game_id);
CREATE INDEX IF NOT EXISTS idx_ncaaf_qb_player ON ncaaf_qb_game(player_id, game_date);


-- NCAAF venues (CFBD /venues) — unlocks travel distance, timezone shift,
-- altitude, surface and crowd size, and gives the weather ingestor coordinates.
CREATE TABLE IF NOT EXISTS ncaaf_venues (
    venue_id     INTEGER PRIMARY KEY,
    name         TEXT,
    city         TEXT,
    state        TEXT,
    latitude     NUMERIC,
    longitude    NUMERIC,
    elevation_ft NUMERIC,
    capacity     INTEGER,
    grass        INTEGER,
    dome         INTEGER,
    updated_at   TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_venues_name ON ncaaf_venues(name);

-- Pipeline writes via the service role (DATABASE_URL) which bypasses RLS.
-- RLS on, no anon policy: nothing in the mobile app reads NCAAF stats directly
-- (picks/games/odds already carry their own anon policies). Add a SELECT
-- policy here if a Stats-tab NCAAF leaderboard is ever built.
ALTER TABLE ncaaf_teams          ENABLE ROW LEVEL SECURITY;
ALTER TABLE ncaaf_team_stats     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ncaaf_team_game_log  ENABLE ROW LEVEL SECURITY;



-- ── UFC ───────────────────────────────────────────────────────────────────────
-- Fighter identity registry. fighter_id is the ufcstats.com fighter id (the hex
-- token in http://ufcstats.com/fighter-details/{id}). slug is the normalized
-- full name (lowercase, accents stripped, hyphenated) used to join Odds API
-- fighter names to ufcstats fighters and to build UFC game_ids.
CREATE TABLE IF NOT EXISTS fighters (
    fighter_id   TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    slug         TEXT NOT NULL,
    height_in    NUMERIC,
    reach_in     NUMERIC,
    stance       TEXT,
    dob          TEXT,
    updated_at   TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_fighters_slug ON fighters(slug);

-- One row per fighter per fight (two rows per fight). Fight-level outcome
-- columns (method, end_round, end_time_sec, scheduled_rounds) are duplicated on
-- both rows; result differs ('win'/'loss'/'draw'/'nc'). Per-fighter stats come
-- from the ufcstats fight-details page totals. Settlement for all three UFC
-- models reads this table (paper_tracker._settle_ufc_picks).
CREATE TABLE IF NOT EXISTS ufc_fight_log (
    log_id            BIGSERIAL PRIMARY KEY,
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
    created_at        TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(fighter_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_fighter ON ufc_fight_log(fighter_id, game_date);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_game    ON ufc_fight_log(game_id);
CREATE INDEX IF NOT EXISTS idx_ufc_flog_season  ON ufc_fight_log(season);

-- Pipeline writes via DATABASE_URL (service role bypasses RLS). ufc_fight_log
-- gets an anon SELECT policy for the mobile Stats fighter leaderboard (mirrors
-- the anon read on player_game_log / wnba_player_game_log); fighters got an
-- anon SELECT policy in migration anon_read_context_tables_and_latest_odds_view
-- for the mobile Tale of the Tape card (session 50).
ALTER TABLE fighters      ENABLE ROW LEVEL SECURITY;
ALTER TABLE ufc_fight_log ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "anon read ufc_fight_log" ON ufc_fight_log
--     FOR SELECT TO anon, authenticated USING (true);
-- (Policy applied via Supabase migration — kept here as documentation.)

-- Mobile Stats fighter leaderboard (applied via migration
-- add_ufc_fighter_totals_view_and_rpc — documented here):
--   • v_fighter_season_totals_ufc — per (fighter_id, season) totals:
--     games_played (fights), wins, ko_wins, sub_wins, sig_strikes, takedowns,
--     knockdowns, sub_attempts; player_name/team(=weight class) = most recent.
--     security_invoker, SELECT granted to anon/authenticated.
--   • fighter_window_totals_ufc(p_season int, p_window int) — same shape over
--     each fighter's last N fights CAREER-WIDE (fighters fight ~3x/year, so a
--     within-season window would be empty; p_season applies only when
--     p_window IS NULL = season-totals mode). SECURITY INVOKER,
--     search_path pinned, EXECUTE granted to anon/authenticated.


-- ── GOLF (PGA Tour) ──────────────────────────────────────────────────────────
-- DataGolf "Scratch Plus" feeds. Each tournament maps to ONE games row
-- (game_id = GOLF_{start_date}_{event_slug}, home_team = event name,
-- away_team = 'FIELD', scores stay NULL). Per-player picks FK to that row and
-- carry picks.player_id = str(dg_id). All four markets price against real DK
-- odds via the DataGolf betting-tools feed (golf_odds).
CREATE TABLE IF NOT EXISTS golf_players (
    dg_id        INTEGER PRIMARY KEY,
    player_name  TEXT NOT NULL,
    slug         TEXT NOT NULL,
    country      TEXT,
    amateur      INTEGER DEFAULT 0,
    updated_at   TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_golf_players_slug ON golf_players(slug);

CREATE TABLE IF NOT EXISTS golf_tournaments (
    tournament_id BIGSERIAL PRIMARY KEY,
    game_id       TEXT NOT NULL REFERENCES games(game_id),
    tour          TEXT NOT NULL DEFAULT 'pga',
    dg_event_id   INTEGER NOT NULL,
    season        INTEGER NOT NULL,
    event_name    TEXT NOT NULL,
    course_name   TEXT,
    start_date    TEXT NOT NULL,
    end_date      TEXT,
    field_size    INTEGER,
    has_cut       INTEGER DEFAULT 1,
    status        TEXT DEFAULT 'scheduled',
    created_at    TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(dg_event_id, season)
);
CREATE INDEX IF NOT EXISTS idx_golf_tourn_game ON golf_tournaments(game_id);

-- One row per player per round. Event-level outcome columns (finish_pos,
-- finish_text, made_cut) are duplicated on every round row for that player
-- (ufc_fight_log precedent). game_date = tournament start (the ASOF anchor).
-- Settlement for all golf models reads this table (_settle_golf_picks).
CREATE TABLE IF NOT EXISTS golf_rounds (
    round_id     BIGSERIAL PRIMARY KEY,
    dg_id        INTEGER NOT NULL,
    player_name  TEXT NOT NULL,
    game_id      TEXT REFERENCES games(game_id),
    dg_event_id  INTEGER NOT NULL,
    season       INTEGER NOT NULL,
    game_date    TEXT NOT NULL,
    round_num    INTEGER NOT NULL,
    course_num   INTEGER,
    score        INTEGER,
    sg_ott   NUMERIC, sg_app NUMERIC, sg_arg NUMERIC, sg_putt NUMERIC, sg_t2g NUMERIC, sg_total NUMERIC,
    driving_dist NUMERIC, driving_acc NUMERIC, gir NUMERIC, scrambling NUMERIC,
    finish_pos   INTEGER,
    finish_text  TEXT,
    made_cut     INTEGER,
    created_at   TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(dg_id, dg_event_id, season, round_num)
);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_player ON golf_rounds(dg_id, game_date);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_game   ON golf_rounds(game_id);
CREATE INDEX IF NOT EXISTS idx_golf_rounds_event  ON golf_rounds(dg_event_id, season);

-- Live DK odds snapshots from the DataGolf betting-tools feed (player_prop_odds
-- shape). Matchup rows additionally carry the opponent columns. datagolf_prob is
-- DataGolf's own model probability — a benchmark column, NOT a model feature.
CREATE TABLE IF NOT EXISTS golf_odds (
    odds_id         BIGSERIAL PRIMARY KEY,
    game_id         TEXT NOT NULL REFERENCES games(game_id),
    game_date       TEXT NOT NULL,
    dg_id           INTEGER,
    player_name     TEXT NOT NULL,
    market          TEXT NOT NULL,
    bookmaker       TEXT NOT NULL DEFAULT 'draftkings',
    snapshot_type   TEXT NOT NULL,
    snapshot_at     TEXT NOT NULL,
    price           NUMERIC,
    datagolf_prob   NUMERIC,
    opp_dg_id       INTEGER,
    opp_player_name TEXT,
    opp_price       NUMERIC,
    created_at      TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_golf_odds_game ON golf_odds(game_id, market, dg_id, snapshot_type);

-- RLS: pipeline writes via DATABASE_URL (service role bypasses RLS). Mobile reads
-- players / tournaments / rounds for pick rendering + a future stats leaderboard;
-- golf_odds stays locked down v1 (picks carry what mobile needs). Anon SELECT
-- policies for the three read tables are applied via the Supabase migration
-- add_golf_tables (kept here as documentation).
ALTER TABLE golf_players     ENABLE ROW LEVEL SECURITY;
ALTER TABLE golf_tournaments ENABLE ROW LEVEL SECURITY;
ALTER TABLE golf_rounds      ENABLE ROW LEVEL SECURITY;
ALTER TABLE golf_odds        ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "anon read golf_players"     ON golf_players     FOR SELECT TO anon, authenticated USING (true);
-- CREATE POLICY "anon read golf_tournaments" ON golf_tournaments FOR SELECT TO anon, authenticated USING (true);
-- CREATE POLICY "anon read golf_rounds"      ON golf_rounds      FOR SELECT TO anon, authenticated USING (true);


-- ── PICKS — Paper Trading Log ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS picks (
    pick_id            BIGSERIAL PRIMARY KEY,
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    game_time          TEXT,                -- ISO-8601 scheduled start; from games.commence_time
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
    best_book          TEXT,               -- book offering the best price on this side at score time
    best_odds          NUMERIC,            -- that book's American price (what the bettor should take)
    best_implied_prob  NUMERIC,            -- implied probability of best_odds
    best_edge          NUMERIC,            -- model_probability - best_implied_prob (informational; `edge` still qualifies)
    best_bet_link      TEXT,               -- betslip deep link at best_book, when the feed carries one
    prop_market        TEXT,               -- prop market key; the NFL market rule is one model id over many markets
    player_key         TEXT,               -- normalised player name settlement joins on (NFL: the two feeds disagree on spelling)
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
    chase_pct       NUMERIC,                     -- chase rate (out-of-zone swing %, batter) — plate discipline
    batter_whiff_pct NUMERIC,                    -- batter swing-and-miss rate — contact proxy for hits-allowed
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

-- NBA season totals per (player_id, season) — backs the mobile Stats leaderboard.
-- security_invoker = on, so anon needs SELECT on the base table:
CREATE POLICY "anon read nba_player_game_log"
    ON nba_player_game_log FOR SELECT TO anon, authenticated USING (true);

CREATE OR REPLACE VIEW v_player_season_totals_nba
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
FROM nba_player_game_log
GROUP BY player_id, season;

GRANT SELECT ON v_player_season_totals_nba TO anon, authenticated;

-- NFL season totals per (player_id, season) — backs the mobile Stats leaderboard.
-- (The anon SELECT policy on nfl_player_game_log lives in the table section
-- above; rush_rec_tds = rushing + receiving TDs, the "anytime TD" style stat.)
-- The matching last-N RPCs (player_window_totals_nfl, player_recent_games_nfl)
-- follow the identical ranked-CTE pattern as the MLB/WNBA/NBA ones below —
-- full definitions in data/migrations/add_nfl_player_stats_leaderboard.sql.
CREATE OR REPLACE VIEW v_player_season_totals_nfl
WITH (security_invoker = on) AS
SELECT
    player_id,
    (array_agg(player_name ORDER BY game_date DESC))[1] AS player_name,
    season,
    (array_agg(team ORDER BY game_date DESC))[1] AS team,
    (array_agg(pos ORDER BY game_date DESC))[1]  AS pos,
    COUNT(DISTINCT game_id)              AS games_played,
    COALESCE(SUM(completions), 0)        AS completions,
    COALESCE(SUM(attempts), 0)           AS attempts,
    COALESCE(SUM(passing_yards), 0)      AS passing_yards,
    COALESCE(SUM(passing_tds), 0)        AS passing_tds,
    COALESCE(SUM(interceptions), 0)      AS interceptions,
    COALESCE(SUM(carries), 0)            AS carries,
    COALESCE(SUM(rushing_yards), 0)      AS rushing_yards,
    COALESCE(SUM(rushing_tds), 0)        AS rushing_tds,
    COALESCE(SUM(receptions), 0)         AS receptions,
    COALESCE(SUM(targets), 0)            AS targets,
    COALESCE(SUM(receiving_yards), 0)    AS receiving_yards,
    COALESCE(SUM(receiving_tds), 0)      AS receiving_tds,
    COALESCE(SUM(COALESCE(rushing_tds,0) + COALESCE(receiving_tds,0)), 0) AS rush_rec_tds,
    COALESCE(SUM(def_sacks), 0)          AS def_sacks,
    COALESCE(SUM(def_interceptions), 0)  AS def_interceptions
FROM nfl_player_game_log
GROUP BY player_id, season;

GRANT SELECT ON v_player_season_totals_nfl TO anon, authenticated;


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

CREATE OR REPLACE FUNCTION public.player_window_totals_nba(
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
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM nba_player_game_log n
        WHERE n.season = p_season
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
GRANT EXECUTE ON FUNCTION public.player_window_totals_nba(integer, integer)        TO anon, authenticated;


-- ── RECENT PER-GAME ROWS (Stats tab "Hit Rate" mode) ──────────────────────────
-- Raw last-N game-log rows per player (NOT aggregated). The mobile Stats tab
-- computes hit-rate ("X of last N games over the line") + the per-game dot strip
-- for any stat/threshold from these. Same ranked-CTE pattern as
-- player_window_totals_* but selects the rows instead of grouping. N capped at 25.

CREATE OR REPLACE FUNCTION public.player_recent_games_mlb(
    p_season integer,
    p_player_type text,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text, player_type text,
    game_id text, game_date text, season integer, rn integer,
    at_bats int, hits int, doubles int, triples int, home_runs int,
    total_bases int, rbi int, runs int, walks int, strikeouts int, stolen_bases int,
    p_strikeouts int, p_walks int, p_hits_allowed int, p_earned_runs int,
    p_home_runs int, innings_pitched numeric, pitches int
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
        player_id, player_name, team, player_type, game_id, game_date,
        season, rn::int,
        at_bats, hits, doubles, triples, home_runs, total_bases, rbi, runs,
        walks, strikeouts, stolen_bases, p_strikeouts, p_walks, p_hits_allowed,
        p_earned_runs, p_home_runs, innings_pitched, pitches
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

CREATE OR REPLACE FUNCTION public.player_recent_games_wnba(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    game_id text, game_date text, season integer, rn integer,
    minutes numeric, points int, rebounds int, assists int, threes int,
    steals int, blocks int, turnovers int, pra int
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
        player_id, player_name, team, game_id, game_date, season, rn::int,
        minutes, points, rebounds, assists, fg3_made AS threes, steals, blocks,
        turnovers,
        (COALESCE(points,0) + COALESCE(rebounds,0) + COALESCE(assists,0))::int AS pra
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

CREATE OR REPLACE FUNCTION public.player_recent_games_nba(
    p_season integer,
    p_window integer DEFAULT 10
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    game_id text, game_date text, season integer, rn integer,
    minutes numeric, points int, rebounds int, assists int, threes int,
    steals int, blocks int, turnovers int, pra int
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH ranked AS (
        SELECT n.*,
               ROW_NUMBER() OVER (PARTITION BY n.player_id
                                  ORDER BY n.game_date DESC, n.game_id DESC) AS rn
        FROM nba_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        player_id, player_name, team, game_id, game_date, season, rn::int,
        minutes, points, rebounds, assists, fg3_made AS threes, steals, blocks,
        turnovers,
        (COALESCE(points,0) + COALESCE(rebounds,0) + COALESCE(assists,0))::int AS pra
    FROM ranked
    WHERE rn <= LEAST(COALESCE(p_window, 10), 25)
    ORDER BY player_id, rn;
$$;

GRANT EXECUTE ON FUNCTION public.player_recent_games_mlb(integer, text, integer) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_wnba(integer, integer)       TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_recent_games_nba(integer, integer)        TO anon, authenticated;


-- ── SEASON STAT VALUE ARRAYS (Stats tab "Hit Rate" mode, Season window) ───────
-- The recent-games RPCs above cap at 25 games, and a whole season of raw rows
-- would be ~35-50K rows for MLB — too heavy for the phone. These return ONE row
-- per player: that player's full-season per-game values for a single
-- whitelisted stat as an ordered array (newest first, nulls excluded), so the
-- client computes the season hit rate for any line/direction instantly.
-- p_stat goes through a CASE whitelist — unknown keys return zero rows.
-- "values" is quoted because it's a reserved word; the JSON key is still
-- `values`. Applied 2026-08-19 as migration add_player_season_stat_values_rpcs
-- (full definitions in data/migrations/add_player_season_stat_values_rpcs.sql).
-- The NFL variant player_season_stat_values_nfl (same shape, whitelist over the
-- NFL stat keys incl. derived rush_rec_tds) is in migration
-- add_player_season_stat_values_nfl.sql — applied the same day.

CREATE OR REPLACE FUNCTION public.player_season_stat_values_mlb(
    p_season integer,
    p_player_type text,
    p_stat text
)
RETURNS TABLE (
    player_id text, player_name text, team text, player_type text,
    games integer, "values" numeric[]
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH vals AS (
        SELECT
            pgl.player_id, pgl.player_name, pgl.team, pgl.player_type,
            pgl.game_date, pgl.game_id,
            CASE p_stat
                -- batting
                WHEN 'hits'            THEN pgl.hits::numeric
                WHEN 'home_runs'       THEN pgl.home_runs::numeric
                WHEN 'total_bases'     THEN pgl.total_bases::numeric
                WHEN 'rbi'             THEN pgl.rbi::numeric
                WHEN 'runs'            THEN pgl.runs::numeric
                WHEN 'walks'           THEN pgl.walks::numeric
                WHEN 'stolen_bases'    THEN pgl.stolen_bases::numeric
                WHEN 'doubles'         THEN pgl.doubles::numeric
                WHEN 'triples'         THEN pgl.triples::numeric
                WHEN 'strikeouts'      THEN pgl.strikeouts::numeric
                WHEN 'at_bats'         THEN pgl.at_bats::numeric
                -- pitching
                WHEN 'p_strikeouts'    THEN pgl.p_strikeouts::numeric
                WHEN 'p_walks'         THEN pgl.p_walks::numeric
                WHEN 'p_hits_allowed'  THEN pgl.p_hits_allowed::numeric
                WHEN 'p_earned_runs'   THEN pgl.p_earned_runs::numeric
                WHEN 'p_home_runs'     THEN pgl.p_home_runs::numeric
                WHEN 'innings_pitched' THEN pgl.innings_pitched::numeric
                WHEN 'pitches'         THEN pgl.pitches::numeric
                ELSE NULL
            END AS val
        FROM player_game_log pgl
        WHERE pgl.season = p_season AND pgl.player_type = p_player_type
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        (array_agg(v.player_type ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_type,
        count(v.val)::int AS games,
        (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values"
    FROM vals v
    GROUP BY v.player_id
    HAVING count(v.val) > 0;
$$;

CREATE OR REPLACE FUNCTION public.player_season_stat_values_wnba(
    p_season integer,
    p_stat text
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    games integer, "values" numeric[]
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH vals AS (
        SELECT
            w.player_id, w.player_name, w.team, w.game_date, w.game_id,
            CASE p_stat
                WHEN 'points'    THEN w.points::numeric
                WHEN 'rebounds'  THEN w.rebounds::numeric
                WHEN 'assists'   THEN w.assists::numeric
                WHEN 'threes'    THEN w.fg3_made::numeric
                WHEN 'steals'    THEN w.steals::numeric
                WHEN 'blocks'    THEN w.blocks::numeric
                WHEN 'turnovers' THEN w.turnovers::numeric
                WHEN 'minutes'   THEN w.minutes::numeric
                WHEN 'pra'       THEN (COALESCE(w.points,0) + COALESCE(w.rebounds,0)
                                       + COALESCE(w.assists,0))::numeric
                ELSE NULL
            END AS val
        FROM wnba_player_game_log w
        WHERE w.season = p_season
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        count(v.val)::int AS games,
        (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values"
    FROM vals v
    GROUP BY v.player_id
    HAVING count(v.val) > 0;
$$;

CREATE OR REPLACE FUNCTION public.player_season_stat_values_nba(
    p_season integer,
    p_stat text
)
RETURNS TABLE (
    player_id text, player_name text, team text,
    games integer, "values" numeric[]
)
LANGUAGE sql STABLE SECURITY INVOKER SET search_path = public, pg_temp AS $$
    WITH vals AS (
        SELECT
            n.player_id, n.player_name, n.team, n.game_date, n.game_id,
            CASE p_stat
                WHEN 'points'    THEN n.points::numeric
                WHEN 'rebounds'  THEN n.rebounds::numeric
                WHEN 'assists'   THEN n.assists::numeric
                WHEN 'threes'    THEN n.fg3_made::numeric
                WHEN 'steals'    THEN n.steals::numeric
                WHEN 'blocks'    THEN n.blocks::numeric
                WHEN 'turnovers' THEN n.turnovers::numeric
                WHEN 'minutes'   THEN n.minutes::numeric
                WHEN 'pra'       THEN (COALESCE(n.points,0) + COALESCE(n.rebounds,0)
                                       + COALESCE(n.assists,0))::numeric
                ELSE NULL
            END AS val
        FROM nba_player_game_log n
        WHERE n.season = p_season
    )
    SELECT
        v.player_id,
        (array_agg(v.player_name ORDER BY v.game_date DESC, v.game_id DESC))[1] AS player_name,
        (array_agg(v.team        ORDER BY v.game_date DESC, v.game_id DESC))[1] AS team,
        count(v.val)::int AS games,
        (array_agg(v.val ORDER BY v.game_date DESC, v.game_id DESC)
             FILTER (WHERE v.val IS NOT NULL)) AS "values"
    FROM vals v
    GROUP BY v.player_id
    HAVING count(v.val) > 0;
$$;

GRANT EXECUTE ON FUNCTION public.player_season_stat_values_mlb(integer, text, text) TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_wnba(integer, text)      TO anon, authenticated;
GRANT EXECUTE ON FUNCTION public.player_season_stat_values_nba(integer, text)       TO anon, authenticated;


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

-- Freshest in-play snapshot per game — drives the live score + inning shown on
-- the mobile pick cards while a game is in progress (games.home_score/away_score
-- stay NULL until next-morning settlement, so this is the only in-game source).
-- Applied via migration add_live_game_state_latest_view; the base table also
-- carries an anon SELECT policy so the security_invoker view is readable:
--   CREATE POLICY "anon read live_game_state"
--     ON live_game_state FOR SELECT TO anon, authenticated USING (true);

CREATE OR REPLACE VIEW v_live_game_state_latest
WITH (security_invoker = on) AS
SELECT DISTINCT ON (s.game_id)
    s.game_id, g.game_date, s.snapshot_at,
    s.inning, s.inning_half, s.outs, s.bases_state,
    s.home_score, s.away_score, s.abstract_game_state
FROM live_game_state s
JOIN games g ON g.game_id = s.game_id
ORDER BY s.game_id, s.snapshot_at DESC, s.state_id DESC;

GRANT SELECT ON v_live_game_state_latest TO anon, authenticated;

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


-- ── LIVE CREDIT TELEMETRY (Phase 3 — in-play betting) ─────────────────────────
-- One row per in-play Odds API fetch. The trigger orchestrator sums today's
-- credits to enforce LIVE_DAILY_CREDIT_CAP and reads MAX(fired_at) for the
-- FG-fetch debounce. `market` holds the fetch purpose (e.g. 'fg_bulk:h2h,...').
-- (Created in Supabase by the add_live_betting_phase1_schema migration.)
CREATE TABLE IF NOT EXISTS live_credit_telemetry (
    telemetry_id   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date           TEXT NOT NULL,
    game_id        TEXT,
    market         TEXT NOT NULL,
    credits        INTEGER NOT NULL DEFAULT 0,
    fired_at       TEXT NOT NULL,
    created_at     TEXT DEFAULT (NOW()::TEXT)
);

CREATE INDEX IF NOT EXISTS idx_live_credit_date ON live_credit_telemetry(date);

-- Internal-only — pipeline writes via DATABASE_URL (service role bypasses RLS).
ALTER TABLE live_credit_telemetry ENABLE ROW LEVEL SECURITY;


-- ── SHARPSPORTS: ACCOUNT LINK + SYNCED BET HISTORY ───────────────────────────
-- Read-only sportsbook bet sync via SharpSports (https://sharpsports.io).
-- Written by the SharpSports Edge Functions (supabase/functions/sharpsports-*)
-- using the service role. RLS is enabled with NO anon policy on purpose:
-- real-money bet history is sensitive, so the mobile app never reads these
-- tables directly — it calls the sharpsports-bets Edge Function, scoped to the
-- device's internal_id (an unguessable UUID).

CREATE TABLE IF NOT EXISTS linked_sportsbook_accounts (
    id                 BIGSERIAL PRIMARY KEY,
    internal_id        TEXT NOT NULL,                 -- device-scoped id sent to SharpSports as the bettor's internalId
    bettor_id          TEXT,                          -- SharpSports bettor id
    bettor_account_id  TEXT NOT NULL,                 -- SharpSports bettorAccount id (one per linked book/region)
    book               TEXT,                          -- display name, e.g. 'DraftKings'
    book_abbr          TEXT,                          -- 'draftkings' | 'fanduel'
    book_region        TEXT,                          -- e.g. 'DraftKings-Colorado'
    status             TEXT,                          -- 'verified' | 'unverified'
    linked_at          TEXT,
    updated_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(bettor_account_id)
);
CREATE INDEX IF NOT EXISTS idx_linked_accounts_internal ON linked_sportsbook_accounts(internal_id);

CREATE TABLE IF NOT EXISTS synced_bets (
    id             BIGSERIAL PRIMARY KEY,
    internal_id    TEXT NOT NULL,
    bettor_id      TEXT,
    bet_id         TEXT NOT NULL,                     -- SharpSports betSlip id
    book           TEXT,
    type           TEXT,                              -- 'single' | 'parlay'
    status         TEXT,                              -- 'pending' | 'won' | 'lost' | 'push' | 'cashout' | ...
    placed_at      TEXT,
    settled_at     TEXT,
    odds_american  NUMERIC,
    stake          NUMERIC,
    payout         NUMERIC,
    profit         NUMERIC,
    settled        BOOLEAN DEFAULT FALSE,
    raw            JSONB,                             -- full SharpSports betSlip payload (shape-tolerant)
    updated_at     TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(bet_id)
);
CREATE INDEX IF NOT EXISTS idx_synced_bets_internal ON synced_bets(internal_id, placed_at);

ALTER TABLE linked_sportsbook_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE synced_bets ENABLE ROW LEVEL SECURITY;


-- ── OPENING-SIGNAL SHADOW TRACK ──────────────────────────────────────────────
-- Applied via migration add_opening_signals_shadow_track.
-- Locks the FIRST refresh a game/market crosses the BET threshold so it stops
-- churning, runs beside the live `picks` table, and records how the line moved
-- (clv_pct vs our opening dk_odds) and which side the public was on after lock.
CREATE TABLE IF NOT EXISTS opening_signals (
    id                 BIGSERIAL PRIMARY KEY,
    lock_key           TEXT NOT NULL,        -- game:model | game:model:player (props)
    game_id            TEXT REFERENCES games(game_id),
    model_id           TEXT NOT NULL,
    sport              TEXT NOT NULL,
    game_date          TEXT NOT NULL,
    player_id          TEXT,
    pick_side          TEXT NOT NULL,
    pick_label         TEXT NOT NULL,
    model_probability  NUMERIC NOT NULL,
    dk_implied_prob    NUMERIC,
    edge               NUMERIC,
    dk_odds            NUMERIC,
    scored_line        NUMERIC,
    public_bet_pct     NUMERIC,
    public_money_pct   NUMERIC,
    confidence_tier    TEXT,
    kelly_fraction     NUMERIC,
    recommended_bet    NUMERIC,
    bankroll_at_pick   NUMERIC,
    locked_at          TEXT NOT NULL,
    closing_dk_odds    NUMERIC,
    closing_line       NUMERIC,
    clv_pct            NUMERIC,              -- positive = line moved toward us after lock
    line_move_dir      TEXT,                 -- toward | against | flat
    public_side        TEXT,                 -- with_public | contrarian | even
    result             TEXT,                 -- WIN | LOSS | PUSH | NO_ACTION
    profit_flat        NUMERIC,
    profit_kelly       NUMERIC,
    settled_at         TEXT,
    created_at         TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(lock_key)
);
CREATE INDEX IF NOT EXISTS idx_opening_signals_date   ON opening_signals(game_date);
CREATE INDEX IF NOT EXISTS idx_opening_signals_model  ON opening_signals(model_id);
CREATE INDEX IF NOT EXISTS idx_opening_signals_settle ON opening_signals(result, line_move_dir, public_side);
ALTER TABLE opening_signals ENABLE ROW LEVEL SECURITY;
-- Pipeline writes via service-role DATABASE_URL (bypasses RLS). Anon read so the
-- mobile/website comparison report can surface the opening-vs-live record.
CREATE POLICY "anon read opening_signals" ON opening_signals
    FOR SELECT TO anon, authenticated USING (true);

-- Comparison views (migration add_opening_signal_comparison_views; security_invoker,
-- anon SELECT). v_opening_vs_live: two rows (opening | live) of game-level settled
-- record since paper start. v_opening_signal_slices: opening track grouped by
-- line_move_dir + public_side. Both power the mobile "Opening vs Live" screen.

-- ── PARLAY CORRELATIONS (parlay copula engine, Phase 2) ──────────────────────
-- Applied via migration add_parlay_correlations. One canonical "+offense x
-- +offense" rho per (sport, market-class pair, team relationship); the mobile
-- copula engine multiplies it by each leg's offense polarity to get the directed
-- correlation. market_class_a <= market_class_b lexicographically (order-free
-- lookups). source='empirical' (scripts/estimate_parlay_correlations.py) overlays
-- the app's bundled 'prior' values. RLS on; anon SELECT (read-only reference data;
-- pipeline writes via service-role DATABASE_URL).
CREATE TABLE IF NOT EXISTS parlay_correlations (
    id              BIGSERIAL PRIMARY KEY,
    sport           TEXT NOT NULL,
    market_class_a  TEXT NOT NULL,
    market_class_b  TEXT NOT NULL,
    relationship    TEXT NOT NULL,   -- 'same' | 'opp' | 'na'
    rho             NUMERIC NOT NULL,
    source          TEXT NOT NULL DEFAULT 'empirical',
    n_pairs         BIGINT,
    updated_at      TEXT DEFAULT (now()::text),
    UNIQUE (sport, market_class_a, market_class_b, relationship)
);
ALTER TABLE parlay_correlations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read parlay_correlations" ON parlay_correlations
    FOR SELECT TO anon, authenticated USING (true);

-- ── PARLAY TRACK RECORD (public parlay record) ───────────────────────────────
-- Applied via migration add_parlay_track_record. One canonical cross-game parlay
-- per (sport, game_date); legs reference opening_signals lock_keys (stable +
-- already settled by settle_opening_signals). Settled by
-- tracking/parlay_track_record.settle_parlay_track_record. RLS on; anon SELECT
-- so the mobile Track Record screen can publish the record. The app aggregates
-- the rows client-side (headline + equity curve) — no view needed.
CREATE TABLE IF NOT EXISTS parlay_track_record (
  id                BIGSERIAL PRIMARY KEY,
  parlay_key        TEXT NOT NULL,
  sport             TEXT NOT NULL,
  game_date         TEXT NOT NULL,
  n_legs            INTEGER NOT NULL,
  leg_keys          TEXT NOT NULL,
  leg_labels        TEXT NOT NULL,
  leg_odds          TEXT NOT NULL,
  combined_decimal  NUMERIC NOT NULL,
  combined_american NUMERIC NOT NULL,
  model_prob        NUMERIC NOT NULL,
  dk_implied_prob   NUMERIC NOT NULL,
  edge              NUMERIC NOT NULL,
  locked_at         TEXT NOT NULL,
  result            TEXT,
  profit_flat       NUMERIC,
  settled_at        TEXT,
  created_at        TIMESTAMP DEFAULT now(),
  UNIQUE (parlay_key)
);
CREATE INDEX IF NOT EXISTS idx_parlay_track_date  ON parlay_track_record(game_date);
CREATE INDEX IF NOT EXISTS idx_parlay_track_sport ON parlay_track_record(sport);
ALTER TABLE parlay_track_record ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read parlay_track_record" ON parlay_track_record
    FOR SELECT TO anon, authenticated USING (true);


-- ── PUSH NOTIFICATIONS ───────────────────────────────────────────────────────
-- Applied via migration add_push_notifications. device_push_tokens holds opted-in
-- Expo tokens (anon INSERT/UPDATE only — no SELECT, so tokens can't be enumerated);
-- push_sent is the ledger preventing double-notification. Pipeline writes push_sent
-- + reads tokens via service-role DATABASE_URL.
CREATE TABLE IF NOT EXISTS device_push_tokens (
    token       TEXT PRIMARY KEY,
    platform    TEXT,
    device_id   TEXT,                       -- maps a token to a device (track-a-bet)
    enabled     BOOLEAN DEFAULT TRUE,
    created_at  TEXT DEFAULT (NOW()::TEXT),
    last_seen   TEXT DEFAULT (NOW()::TEXT)
);
-- Pipeline run ledger. One row per pipeline invocation (daily run or refresh
-- pass), written by tracking/run_ledger.py. Exists because until 2026-08-27
-- NOTHING recorded that a pass had run: a NameError killed every hourly pass
-- at step 9 of 24 for three days and left no trace except missing side-effects,
-- while the once-a-day health check stayed green. A pass that starts and never
-- finishes leaves finished_at NULL, so a hang or a killed worker is detectable
-- too. Read by the refresh_pass_completion / refresh_pass_steps health checks.
CREATE TABLE IF NOT EXISTS pipeline_runs (
    run_id       TEXT PRIMARY KEY,
    run_kind     TEXT NOT NULL,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    steps_total  INTEGER,
    steps_failed INTEGER,
    failed_steps TEXT,
    ok           BOOLEAN
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started ON pipeline_runs(started_at);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_kind ON pipeline_runs(run_kind, started_at);

CREATE TABLE IF NOT EXISTS push_sent (
    id        BIGSERIAL PRIMARY KEY,
    lock_key  TEXT NOT NULL,
    kind      TEXT NOT NULL,
    sent_at   TEXT DEFAULT (NOW()::TEXT),
    -- Which Discord message this post went out in. Lets a later correction
    -- DELETE or edit it instead of stacking a second slate underneath. NULL for
    -- mobile-push rows and for anything posted before 2026-08-28, when ids were
    -- first captured (?wait=true) -- the delete path skips those rather than
    -- guessing. Added live by data/migrations/add_message_id_to_push_sent.sql.
    message_id TEXT,
    UNIQUE(lock_key, kind)
);
CREATE INDEX IF NOT EXISTS idx_push_sent_kind ON push_sent(kind);
ALTER TABLE device_push_tokens ENABLE ROW LEVEL SECURITY;
ALTER TABLE push_sent ENABLE ROW LEVEL SECURITY;
-- pipeline-internal: written by the worker via DATABASE_URL (owner
-- bypasses RLS), never read by the app. RLS on, no anon policy.
-- NOTE: this table is created at RUNTIME by tracking/run_ledger.py, not by this
-- file, so the line below never reached production until
-- data/migrations/enable_rls_on_pipeline_runs.sql (2026-08-29). run_ledger now
-- issues both statements itself. The REVOKE names the roles because Supabase's
-- default privileges grant anon/authenticated by name.
ALTER TABLE pipeline_runs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON pipeline_runs FROM anon, authenticated;
CREATE POLICY "anon insert device token" ON device_push_tokens
    FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon update device token" ON device_push_tokens
    FOR UPDATE TO anon, authenticated USING (true) WITH CHECK (true);

-- Track-a-bet (migration add_tracked_bets). A device opts to be notified of big
-- DK line moves on a specific pick. UI "tracked" state is local on-device; this
-- table just tells tracking/push_notifier.notify_line_changes what to watch.
-- device_id → token via device_push_tokens. Anon writes its own tracks (no
-- SELECT — UI state is local); pipeline reads via service-role DATABASE_URL.
CREATE TABLE IF NOT EXISTS tracked_bets (
    id           BIGSERIAL PRIMARY KEY,
    device_id    TEXT NOT NULL,
    pick_id      BIGINT NOT NULL,
    game_id      TEXT NOT NULL,
    model_id     TEXT NOT NULL,
    pick_side    TEXT,
    player_id    TEXT,
    pick_label   TEXT,
    locked_odds  NUMERIC,
    locked_line  NUMERIC,
    game_date    TEXT,
    created_at   TEXT DEFAULT (NOW()::TEXT),
    UNIQUE(device_id, pick_id)
);
CREATE INDEX IF NOT EXISTS idx_tracked_bets_date ON tracked_bets(game_date);
CREATE INDEX IF NOT EXISTS idx_tracked_bets_device ON tracked_bets(device_id);
ALTER TABLE tracked_bets ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon insert tracked_bets" ON tracked_bets
    FOR INSERT TO anon, authenticated WITH CHECK (true);
CREATE POLICY "anon delete tracked_bets" ON tracked_bets
    FOR DELETE TO anon, authenticated USING (true);


-- ── IN-APP FEEDBACK (two-way) ────────────────────────────────────────────────
-- Applied via migration add_feedback_threads (+ add_feedback_rpcs,
-- add_feedback_reply_support_fn, restrict_feedback_reply_to_service_role).
-- The mobile Settings "Send feedback" row used to open a mailto:; it now opens
-- an in-app conversation. One feedback_threads row per conversation, owned by a
-- device_id (and a user_id once auth is on); feedback_messages holds the turns.
--
-- ACCESS MODEL — read this before adding a policy. The app uses the anon key
-- with no session, so a policy has no identity to filter on and `USING (true)`
-- would expose every user's feedback to every anon key. So: RLS on, NO policies,
-- anon's default table grants REVOKEd, and the only way in is the device-scoped
-- SECURITY DEFINER RPCs. Same trust model as tracked_bets / SharpSports — the
-- per-install device_id UUID acts as a bearer token.
--   feedback_submit(device, message, category, app_version, platform, thread_id, user_id) → thread_id
--   feedback_threads_for_device(device)              → threads + unread_count
--   feedback_messages_for_thread(device, thread_id)  → the turns (ownership-checked)
--   feedback_mark_read(device, thread_id)            → clears the unread badge
--   feedback_unread_count(device)                    → scalar for the Settings badge
--   feedback_reply(thread_id, body, close)           → SUPPORT side, service_role ONLY
-- feedback_reply must never be granted to anon/authenticated — that is what
-- stops a client posting as 'support'. Note a PUBLIC-only revoke does NOT do it
-- (Supabase default privileges name anon/authenticated explicitly).
--
-- The older, empty `feedback` table (message/app_version/created_at, website
-- era) is unrelated and unused — nothing reads or writes it.
CREATE TABLE IF NOT EXISTS feedback_threads (
    id              BIGSERIAL PRIMARY KEY,
    device_id       TEXT NOT NULL,
    user_id         UUID,                            -- set when signed in
    category        TEXT NOT NULL DEFAULT 'other',   -- bug|idea|picks|billing|other
    subject         TEXT NOT NULL,                   -- derived from the first message
    app_version     TEXT,
    platform        TEXT,
    status          TEXT NOT NULL DEFAULT 'open',    -- open|answered|closed
    created_at      TEXT DEFAULT (NOW()::TEXT),
    last_message_at TEXT DEFAULT (NOW()::TEXT),
    last_read_at    TEXT                             -- device's last open (unread badge)
);
CREATE TABLE IF NOT EXISTS feedback_messages (
    id         BIGSERIAL PRIMARY KEY,
    thread_id  BIGINT NOT NULL REFERENCES feedback_threads(id) ON DELETE CASCADE,
    sender     TEXT NOT NULL CHECK (sender IN ('user', 'support')),
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (NOW()::TEXT)
);
CREATE INDEX IF NOT EXISTS idx_feedback_threads_device ON feedback_threads(device_id);
CREATE INDEX IF NOT EXISTS idx_feedback_threads_status ON feedback_threads(status);
CREATE INDEX IF NOT EXISTS idx_feedback_messages_thread ON feedback_messages(thread_id, id);
ALTER TABLE feedback_threads  ENABLE ROW LEVEL SECURITY;
ALTER TABLE feedback_messages ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE feedback_threads  FROM anon, authenticated;
REVOKE ALL ON TABLE feedback_messages FROM anon, authenticated;
-- Function bodies live in data/migrations/add_feedback_threads.sql.


-- ── SUBSCRIPTIONS (app billing — Stripe + IAP/RevenueCat) ────────────────────
-- Applied via migrations add_stripe_subscriptions, tighten_subscriptions_grants,
-- add_iap_columns_to_subscriptions. One row per auth user (their current
-- subscription). ONLY the billing webhooks write it (stripe-webhook /
-- revenuecat-webhook Edge Functions, service role) — the mobile app never
-- does, which is what makes entitlement unforgeable client-side.
-- NOT mirrored into the SQLite schema in db_setup.py: it references
-- auth.users (no SQLite analog) and the Python pipeline never reads it.
-- RLS: users SELECT their own row; anon has been REVOKEd table-wide (Supabase
-- default privileges over-grant anon on new public tables — session-113 lesson).
CREATE TABLE IF NOT EXISTS subscriptions (
    user_id                 UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    stripe_customer_id      TEXT UNIQUE,
    stripe_subscription_id  TEXT UNIQUE,
    status                  TEXT NOT NULL DEFAULT 'incomplete',  -- Stripe vocabulary: trialing|active|past_due|canceled|…
    plan                    TEXT,                                -- monthly | semiannual | annual
    price_id                TEXT,                                -- Stripe price id or store product id
    current_period_end      TIMESTAMPTZ,
    trial_end               TIMESTAMPTZ,
    cancel_at_period_end    BOOLEAN NOT NULL DEFAULT FALSE,
    store                   TEXT,                                -- 'stripe' | 'app_store' | 'play_store'
    rc_app_user_id          TEXT,                                -- RevenueCat app user id (= user_id by construction)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_customer ON subscriptions (stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status   ON subscriptions (status);
ALTER TABLE subscriptions ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users read own subscription" ON subscriptions
    FOR SELECT TO authenticated USING (auth.uid() = user_id);
-- REVOKE ALL ON TABLE subscriptions FROM anon; GRANT SELECT TO authenticated;
-- Plus public.has_active_subscription() (SECURITY INVOKER, authenticated) —
-- the honest entitlement check for future server-side signal gating.


-- ── SYSTEM HEALTH CHECKS ─────────────────────────────────────────────────────
-- Applied via migration add_system_health_checks. Daily feed-freshness results
-- from tracking/system_health.py (final daily pipeline step). One row per
-- (run_date, check_name); re-runs upsert. Anon SELECT so Claude mobile / the
-- app can surface today's system status; pipeline writes via service role.
CREATE TABLE IF NOT EXISTS system_health_checks (
    id          BIGSERIAL PRIMARY KEY,
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
ALTER TABLE system_health_checks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read system_health_checks" ON system_health_checks
    FOR SELECT TO anon, authenticated USING (true);

-- Applied via migration add_odds_api_quota (2026-08-18). Latest Odds API
-- x-requests-used/-remaining observation per UTC day (last write wins) —
-- written by data/ingestors/odds_quota.py from both odds ingestors, read by
-- the odds_api_credits health check so quota exhaustion warns BEFORE the feed
-- dies (the 2026-08-14 incident). Daily burn = day-over-day diff of
-- requests_used (resets each billing period).
CREATE TABLE IF NOT EXISTS odds_api_quota (
    quota_date         TEXT PRIMARY KEY,   -- UTC date of the observation
    requests_used      NUMERIC,
    requests_remaining NUMERIC,
    observed_at        TEXT NOT NULL
);
ALTER TABLE odds_api_quota ENABLE ROW LEVEL SECURITY;
CREATE POLICY "anon read odds_api_quota" ON odds_api_quota
    FOR SELECT TO anon, authenticated USING (true);


-- ── MOBILE READ-ONLY CONTEXT (session 50) ────────────────────────────────────
-- Applied via migration anon_read_context_tables_and_latest_odds_view.
-- Read-only anon SELECT policies so the mobile app can surface data the models
-- already use as features (prop matchup context, model card, tale of the tape):
--
--   CREATE POLICY "anon read player_savant_stats" ON player_savant_stats FOR SELECT TO anon, authenticated USING (true);
--   CREATE POLICY "anon read umpires"             ON umpires             FOR SELECT TO anon, authenticated USING (true);
--   CREATE POLICY "anon read lineup_slots"        ON lineup_slots        FOR SELECT TO anon, authenticated USING (true);
--   CREATE POLICY "anon read player_handedness"   ON player_handedness   FOR SELECT TO anon, authenticated USING (true);
--   CREATE POLICY "anon read model_registry"      ON model_registry      FOR SELECT TO anon, authenticated USING (true);
--   CREATE POLICY "anon read fighters"            ON fighters            FOR SELECT TO anon, authenticated USING (true);
--
-- Latest DK snapshot per game+market, used by the mobile line-movement chip.
-- One row per (game_id, market); game_date included for cheap day filtering.
-- security_invoker so it respects caller RLS (odds + games have anon SELECT).

CREATE OR REPLACE VIEW v_latest_dk_odds
WITH (security_invoker = on) AS
SELECT DISTINCT ON (o.game_id, o.market)
    o.game_id, g.game_date, o.market,
    o.home_price, o.away_price, o.spread_home, o.total_line,
    o.over_price, o.under_price, o.snapshot_at
FROM odds o
JOIN games g ON g.game_id = o.game_id
WHERE o.bookmaker = 'draftkings'
ORDER BY o.game_id, o.market, o.snapshot_at DESC;

GRANT SELECT ON v_latest_dk_odds TO anon, authenticated;


-- ── PUBLIC TRACK RECORD (session: competitor-analysis-disruption) ────────────
-- Applied via migrations add_public_track_record_views + track_record_current_criteria.
-- The verifiable, public-facing proof of performance: every settled BET pick
-- since paper-trading start (2026-04-14) that meets the CURRENT action criteria,
-- aggregated for the mobile Track Record screen and the website proof page.
-- Nothing cherry-picked — losing models are included.
--
-- model_action_thresholds is the DB source of truth for the public views' prob/
-- edge cuts. It MIRRORS mobile/src/lib/thresholds.ts (ACTION_THRESHOLDS +
-- PROB_ONLY_MODELS) and config.py — KEEP IT IN SYNC when thresholds change so
-- the app's passesActionFilter and the website agree.
--
--   CREATE TABLE model_action_thresholds (
--     model_id text PRIMARY KEY, min_prob numeric NOT NULL,
--     min_edge numeric NOT NULL DEFAULT 0, prob_only boolean NOT NULL DEFAULT false,
--     min_odds numeric,  -- 2026-07-11 (migration add_min_odds_price_floor):
--                        -- floor on the acceptable DK price (American). NULL = no
--                        -- floor. Mirrors config.MODEL_MIN_ODDS (-140 on
--                        -- pitcher_k / batter_rbi / batter_walks / batter_runs).
--     updated_at timestamptz NOT NULL DEFAULT now());
--   ALTER TABLE model_action_thresholds ENABLE ROW LEVEL SECURITY;
--   CREATE POLICY "anon read model_action_thresholds"
--     ON model_action_thresholds FOR SELECT TO anon, authenticated USING (true);
--
-- Both views are security_invoker (read picks via its existing anon SELECT policy)
-- and grant SELECT to anon, authenticated. A pick "counts" when:
--   signal_type='BET' AND NOT is_live AND game_date >= '2026-04-14'
--   AND model_probability >= t.min_prob AND (t.prob_only OR edge >= t.min_edge)
--   AND (t.min_odds IS NULL OR dk_odds IS NULL OR dk_odds >= t.min_odds)
-- (the min_odds price-floor condition was spliced into all 4 track-record views —
-- v_model_full_outcome_record / _picks + v_public_track_record / _daily — by the
-- add_min_odds_price_floor migration, 2026-07-11)
--
--   v_public_track_record        -- per (sport, model_id): picks/wins/losses/pushes,
--                                   profit_flat, staked_flat, clv_settled, clv_beat,
--                                   avg_clv_pct, first_date, last_date.
--                                   2026-06-28: MLB **and WNBA** use the FULL-OUTCOME
--                                   grading (v_model_full_outcome_record) instead of
--                                   the settled-BET-only undercount; NBA/UFC/NHL/golf
--                                   + CLV unchanged (migrations *_full_outcome_mlb then
--                                   *_add_wnba). Removes the HR -110 artifact (HR =
--                                   0 priced bets → 0/0). Per-sport: MLB +10.0%,
--                                   WNBA +10.8% (was -2.2% on the old method).
--   v_public_track_record_daily  -- per (game_date, sport): daily totals for the
--                                   equity curve (client cumulates). 2026-06-28:
--                                   MLB + WNBA days use the same full-outcome grading
--                                   so the cumulative curve matches the per-model
--                                   headline. NBA/UFC/NHL/golf unchanged.
--
--   2026-07-04 (migration exclude_batter_hr_from_public_track_record): BOTH
--   views exclude mlb_prop_batter_hr from the aggregates. HR is a prob-only
--   longshot market where ~99% of picks carry no DK price — they added W-L
--   drag (15-73) with no ROI meaning to the overall record. HR keeps its own
--   full record in v_model_full_outcome_record (Models tab stays honest).
--   2026-07-05 (migration full_outcome_record_hr_record_only): HR is now
--   record-only in v_model_full_outcome_record too — units forced to 0 and
--   roi_pct to NULL (its 1-2 priced longshot bets rendered as "-100% ROI" on
--   the Models tab). The W-L record still displays; it just carries no money.


-- ── TONIGHT MATCHUP VIEWS (2026-07-04, migration add_tonight_matchup_views) ──
-- Stats-tab "Tonight" filter + opponent-strength lines. One row per team side
-- of today's (ET) games:
--   v_mlb_tonight_matchups   -- opposing probable starter (latest DK pitcher-K
--                               prop snapshot, stats from his latest
--                               mlb_pitcher_stats row, hand from
--                               player_handedness) + opposing team offense
--                               (k_pct/woba/team_era from mlb_team_stats).
--   v_wnba_tonight_matchups  -- opposing team def_rating / pace /
--                               points_allowed_pg from wnba_team_stats.
-- Both security_invoker + anon SELECT. Read-only anon SELECT policies were
-- added to mlb_pitcher_stats, mlb_team_stats, wnba_team_stats (the
-- player_savant_stats precedent) so the invoker views work for the app.

-- ── LINE SHOPPING (session: competitor-analysis-disruption) ──────────────────
-- Applied via migration add_latest_odds_all_books_view.
-- The odds ingestor now stores GAME-market lines for every book in
-- config.LINE_SHOP_BOOKMAKERS (draftkings + fanduel by default), not just DK.
-- The models still SCORE against draftkings; the extra books are display-only so
-- the app can show the best available price per pick side. Specifying the Odds
-- API `bookmakers` param counts as ONE region, so this adds no credit cost.
--
-- v_latest_odds_all_books — latest pre-game snapshot per (game_id, market,
-- bookmaker) across all real books (excludes synthetic sbr_consensus + in_play).
-- security_invoker; anon SELECT. The mobile client computes the best price per
-- pick side and shows a "Best FD +145" chip when a non-DK book beats DK.
--
--   CREATE VIEW v_latest_odds_all_books WITH (security_invoker = on) AS
--     SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker) o.game_id, g.game_date,
--            o.market, o.bookmaker, o.home_price, o.away_price, o.over_price,
--            o.under_price, o.spread_home, o.total_line, o.home_link, o.away_link,
--            o.over_link, o.under_link, o.snapshot_at
--     FROM odds o JOIN games g ON g.game_id = o.game_id
--     WHERE o.bookmaker <> 'sbr_consensus'
--       AND (o.snapshot_type IS NULL OR o.snapshot_type <> 'in_play')
--     ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at DESC;
--   GRANT SELECT ON v_latest_odds_all_books TO anon, authenticated;

-- ── MULTI-BOOK EXPANSION (session: multiple-betting-lines) ───────────────────
-- Applied via migration add_latest_prop_odds_all_books_view.
-- config.LINE_SHOP_BOOKMAKERS went from 2 books to the US top 5:
--   draftkings, fanduel, betmgm, williamhill_us (Caesars), espnbet
-- and PLAYER PROPS became multi-book too (prop_odds_ingestor now parses every
-- returned book, not just DK). Still no extra credit cost — the Odds API counts
-- the `bookmakers` param as ONE region on the bulk and per-event endpoints alike.
--
-- The models are UNAFFECTED and must stay that way: scorer._get_prop_dk_odds and
-- _get_dk_odds, paper_tracker._closing_dk_odds, and all four feature engines
-- hard-filter to draftkings. tests/test_multi_book_odds.py asserts this so a
-- refactor can't silently let a line-shop price into scoring or training.
--
-- v_latest_prop_odds_all_books — the prop analog of v_latest_odds_all_books:
-- latest pre-game line per (game_id, market, player_name, bookmaker), excluding
-- in_play snapshots. security_invoker; anon SELECT (player_prop_odds already has
-- an anon SELECT policy from session 18b). Reads game_date off the table directly
-- — unlike the game-market view, no join to games is needed.
--
--   CREATE OR REPLACE VIEW v_latest_prop_odds_all_books
--   WITH (security_invoker = on) AS
--     SELECT DISTINCT ON (p.game_id, p.market, p.player_name, p.bookmaker)
--            p.game_id, p.game_date, p.market, p.player_name, p.team, p.bookmaker,
--            p.line, p.over_price, p.under_price, p.over_link, p.under_link,
--            p.snapshot_at
--     FROM player_prop_odds p
--     WHERE p.snapshot_type IS NULL OR p.snapshot_type <> 'in_play'
--     ORDER BY p.game_id, p.market, p.player_name, p.bookmaker, p.snapshot_at DESC;
--   GRANT SELECT ON v_latest_prop_odds_all_books TO anon, authenticated;
--
-- ── IN-PLAY MULTI-BOOK (session: sportsbook-betting-line) ───────────────
-- Applied via migration add_latest_inplay_odds_all_books_view.
--
-- The live loop reuses odds_ingestor._get_odds, which already requests every
-- book in config.LINE_SHOP_BOOKMAKERS, so in-play rows for all five books were
-- already being written with snapshot_type='in_play'. But BOTH all-book views
-- above deliberately EXCLUDE in_play (the pre-game / in-play isolation
-- invariant), so the app had no way to read them: a FanDuel bettor on the Live
-- tab saw DraftKings prices and a "Bet on DraftKings" button. This view exposes
-- the in-play rows, and only them.
--
-- Scoring is unaffected -- live_scorer still hard-filters bookmaker='draftkings'.
-- The mobile client additionally drops any snapshot older than
-- config.LIVE_ODDS_MAX_AGE_SEC (300s): a stale in-play price is worse than none.
--
--   CREATE OR REPLACE VIEW v_latest_inplay_odds_all_books
--   WITH (security_invoker = on) AS
--     SELECT DISTINCT ON (o.game_id, o.market, o.bookmaker) o.game_id, g.game_date,
--            o.market, o.bookmaker, o.home_price, o.away_price, o.over_price,
--            o.under_price, o.spread_home, o.total_line, o.home_link, o.away_link,
--            o.over_link, o.under_link, o.snapshot_at
--     FROM odds o JOIN games g ON g.game_id = o.game_id
--     WHERE o.snapshot_type = 'in_play'
--     ORDER BY o.game_id, o.market, o.bookmaker, o.snapshot_at DESC;
--   GRANT SELECT ON v_latest_inplay_odds_all_books TO anon, authenticated;

-- NOTE ON VOLUME: player_prop_odds ran ~86K DK rows / 3 days at one book. At five
-- books expect ~5x (~430K / 3 days). Reads stay bounded (the view is DISTINCT ON),
-- but watch disk growth and consider a retention policy on old prop snapshots.

-- v_model_full_outcome_record (migration add_model_full_outcome_record_view, 2026-06-28):
--   Per-model FULL-OUTCOME record for the Models tab. Grades EVERY scored MLB pick
--   (BET + dead-zone NONE + AVOID) from final scores / player_game_log actuals at
--   the CURRENT model_action_thresholds cut — fixing the undercount where only
--   historically-BET-classified picks were settled (a looser current cut showed 2
--   picks when the true sample is 44). One row per model_id with bets/wins/losses/
--   pushes/priced_bets/units/roi_pct (+ paused, prob_only passthrough). ROI is over
--   priced_bets only (dk_odds present), so HR shows an honest record with no
--   fabricated ROI. security_invoker; GRANT SELECT TO anon, authenticated.
--   Covers MLB (game + 12 props) AND WNBA (moneyline + 5 props, added 2026-06-28
--   migration full_outcome_record_add_wnba); other sports fall back to the
--   client-side computeBuiltInModelStats in the app.
--
--   2026-07-02 FIX (migration fix_runline_away_grading_in_full_outcome_views):
--   away-side mlb_runline picks were graded with (away-home) + scored_line, but
--   scored_line is the HOME spread — the away team's spread is its negation, so
--   the correct test is (away-home) - scored_line > 0. The bug flipped every
--   one-run game on an away-side runline pick (validated fix: 30/31 match vs
--   stored settlements; the 1 mismatch was a genuine settlement error, repaired).
--   Fixed in BOTH v_model_full_outcome_record and v_public_track_record_daily
--   (which inlines the same grading); v_public_track_record reads from the first
--   and inherited the fix. Impact: runline flipped from a phantom +15.2% to a
--   real -20.6% at the then-live 0.55/0.10 cut, and the overall MLB headline
--   from +10.2% to +6.9%. The 2026-06-28 runline re-cut to 0.55/0.10 was made
--   on the buggy numbers and was corrected to 0.68/0.11 the same day as this fix.
--   Full SQL: data/migrations/fix_runline_away_grading_in_full_outcome_views.sql
--
--   2026-07-11 HONEST-ERA GATE (migration ou_record_views_honest_era_gate):
--   mlb_over_under is graded only from game_date >= '2026-07-05' in ALL FOUR
--   views (record, picks, public_track_record + _daily). Live O/U scoring
--   before the 7/5 NaN-total_line fix predicted with the line missing from
--   the feature vector, so pre-fix O/U probabilities are garbage — 211 of the
--   216 picks the Models tab graded at the current cut were from that era.
--   Same precedent as the 2026-04-14 evaluation start. If the gate ever needs
--   changing, the WHERE fragment to look for is
--   "NOT (p.model_id = 'mlb_over_under' AND p.game_date < '2026-07-05')".
--   Full SQL: data/migrations/ou_record_views_honest_era_gate.sql

-- v_model_full_outcome_picks (migration add_model_full_outcome_picks_view, 2026-07-02):
--   Per-pick companion to v_model_full_outcome_record — ONE ROW PER GRADED PICK
--   using the identical base grading + current-threshold passes logic (incl. the
--   runline away-side sign fix), filtered to decided outcomes (W/L/P). Powers the
--   "All picks in this record" list on the mobile model detail screen, so the
--   pick-by-pick history reconciles row-for-row with the aggregate record (the
--   old settled-BET-only history missed dead-zone picks that clear today's cut).
--   Columns: pick_id, model_id, game_date, game_id, pick_label, pick_side,
--   model_probability, edge, dk_odds, scored_line, result ('WIN'|'LOSS'|'PUSH'),
--   profit_units (1-unit flat at dk_odds; NULL when no real price — prob-only HR).
--   Validated at creation: bets/wins/units reconcile exactly with
--   v_model_full_outcome_record for all 22 covered models. security_invoker;
--   GRANT SELECT TO anon, authenticated.
--   Full SQL: data/migrations/add_model_full_outcome_picks_view.sql
--   MAINTENANCE: this view inlines the same grading CASE as
--   v_model_full_outcome_record — any future grading fix or new sport/model
--   added there must be mirrored here or the detail list will drift from the record.

-- mv_scored_pick_outcomes + custom_model_backtest/custom_model_picks RPCs
-- (migrations materialize_scored_pick_outcomes + custom_model_backtest_rpcs,
-- 2026-08-08): the graded EVERY-PICK universe behind the mobile custom-model
-- builder. One row per completed scored pick since paper start — BET, AVOID,
-- and dead-zone NONE alike (~100k rows vs ~3k settled BETs) — graded from
-- final scores / player_game_log with the same CASEs as
-- v_model_full_outcome_picks, but WITHOUT the model_action_thresholds join, so
-- a custom model can finally test cuts LOOSER than the built-in thresholds.
-- Derived filter columns bet_kind ('game'|'prop'), price_side ('fav'|'dog'),
-- time_slot ('day'|'early'|'prime'|'late', ET, hours 0-4 = late) are the
-- canonical bucket definitions — the mobile customModelFilters.ts mirrors them
-- for the live board only. Refreshed CONCURRENTLY by run_pipeline Step 0d
-- (--step refresh-outcomes) right after settle; a missed refresh just leaves
-- backtests one day stale. The RPCs take the mobile rules/filters JSON
-- verbatim and answer in ~50ms (plpgsql with filters as locals — the sql-fn
-- version planned the jsonb per row and took ~4.5s). Parity validated at
-- creation: at each model's current cut the RPC reproduces
-- v_model_full_outcome_record exactly (6/6 models).
-- Full SQL: data/migrations/materialize_scored_pick_outcomes.sql +
-- data/migrations/custom_model_backtest_rpcs.sql
-- v2 (migration custom_model_rpcs_ev_day_line, 2026-08-22): rules gain an
-- optional min_ev (EV-per-$1 floor at the DK price — model_probability ×
-- decimal(dk_odds) − 1; no DK price = never clears); filters gain dayTypes
-- (weekday/weekend from game_date ISODOW) and minLine/maxLine (scored_line
-- range; NULL line = excluded when set). The mobile app no longer sends the
-- signals filter (removed from the builder) though the RPC still parses it.
-- MAINTENANCE: a THIRD copy of the grading CASE (after the record + picks
-- views) — mirror any grading fix or new sport here too, and extend
-- isOutcomeGraded() in mobile/src/lib/customModelFilters.ts when a sport
-- gains grading.

-- ── NFL pick condition history ───────────────────────────────────────────────
-- One row per locked NFL pick per poll tick. The pick itself is IMMUTABLE once
-- locked: this table records what the market and the model looked like
-- afterwards, so "it stopped qualifying" is recorded rather than acted on.
-- The bet was placed at the locked number; nothing here can retract it.
CREATE TABLE IF NOT EXISTS nfl_pick_status_history (
    history_id      BIGSERIAL PRIMARY KEY,
    pick_id         BIGINT NOT NULL REFERENCES picks(pick_id) ON DELETE CASCADE,
    game_id         TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    observed_at     TIMESTAMPTZ NOT NULL,
    lead_hours      NUMERIC,
    still_qualifies BOOLEAN NOT NULL,
    status          TEXT NOT NULL,          -- OK | DEGRADED | GONE
    reason          TEXT,
    current_line    NUMERIC,
    current_price   NUMERIC,
    current_book    TEXT,
    model_prob_now  NUMERIC,
    edge_now        NUMERIC,
    UNIQUE (pick_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_nfl_pick_hist_pick ON nfl_pick_status_history(pick_id);
CREATE INDEX IF NOT EXISTS idx_nfl_pick_hist_game ON nfl_pick_status_history(game_id, observed_at);

-- Pipeline-internal: written by scripts/nfl_pick_monitor.py via DATABASE_URL
-- (owner `postgres`, bypasses RLS). Never read by the app -> RLS on, NO policy.
ALTER TABLE nfl_pick_status_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nfl_pick_status_history FROM anon, authenticated;

-- ── NFL odds history (research/training archive) ─────────────────────────────
-- The NFL package's snapshot cache, made queryable. ~100,000 Odds API credits
-- of spend that until now existed only as JSON files on an ephemeral disk.
--
-- SEPARATE FROM `odds` ON PURPOSE. `odds` is the app's hot path: it is capped
-- by data/prune_odds.py, which DELETES every non-DraftKings row once a game
-- ages out. Putting 47 books of NFL history there would have it silently
-- pruned away, and would add ~230MB to a ~2GB database that is already
-- managing growth. This table is append-only, never pruned, and is read by
-- models and backtests rather than by the app.
--
-- Grain: one row per (snapshot, game, book, market) carrying BOTH sides, which
-- is the shape every downstream consumer already wants — it is what
-- dev_long.parquet holds and what backtest_opener reads.
CREATE TABLE IF NOT EXISTS nfl_odds_history (
    snapshot_at   TIMESTAMPTZ NOT NULL,
    game_id       TEXT        NOT NULL,
    season        SMALLINT,
    week          SMALLINT,
    commence_time TIMESTAMPTZ,
    bookmaker     TEXT        NOT NULL,
    market        TEXT        NOT NULL,   -- spreads | totals | h2h
    point         NUMERIC,                -- home handicap, or the total
    price_home    NUMERIC,                -- home / over
    price_away    NUMERIC,                -- away / under
    lead_hours    NUMERIC,                -- hours to kickoff at this snapshot
    PRIMARY KEY (snapshot_at, game_id, bookmaker, market)
);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_game   ON nfl_odds_history(game_id, market);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_season ON nfl_odds_history(season, week);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_lead   ON nfl_odds_history(market, lead_hours);

-- Pipeline-internal, and IRREPLACEABLE (~100k Odds API credits of spend).
-- RLS on with NO policy + grants revoked by name: Supabase's default privileges
-- hand anon/authenticated ALL on new public tables, which left DELETE on 2.2M
-- archive rows reachable with the app's public anon key until 2026-08-26.
ALTER TABLE nfl_odds_history ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON nfl_odds_history FROM anon, authenticated;


-- ── TEAM STATS BOARD (2026-08-27, migration add_team_stats_board) ────────────
-- Backs the Stats tab's Teams board — the team-level counterpart to the player
-- leaderboard, for every team sport (MLB / NBA / WNBA / NHL / NFL / NCAAF).
--
-- team_stats_board(p_sport text, p_season int) -> one row per team, merging:
--   1. EFFICIENCY, read from that sport's *_team_stats snapshot at its latest
--      as_of_date for the season (wRC+/ERA/bullpen ERA; off/def rating, pace,
--      eFG%, TOV%; Corsi/PP%/PK%; SP+/EPA per play/success rate/explosiveness/
--      havoc). NFL has no *_team_stats table — its yards-per-play numbers are
--      aggregated from nfl_team_game_stats in the same pass.
--   2. BETTING RECORDS, derived from final scores + the stored pre-game line:
--      ATS, over/under, home/away, favourite/underdog, and rest splits
--      (rest advantage vs the opponent, and short rest — a back-to-back in the
--      nightly leagues, a short week in football).
--
-- security_invoker + EXECUTE granted to anon/authenticated. Read-only anon
-- SELECT policies were added to nba_team_stats, nhl_team_stats,
-- ncaaf_team_stats, ncaaf_teams and nfl_team_game_stats (they had RLS on with
-- NO policy, so the app could not read a row) — the mlb_team_stats /
-- wnba_team_stats precedent from the tonight-matchup views above.
--
-- FOUR THINGS THAT MUST NOT BE BROKEN:
--
--  * PRE-GAME LINE ONLY. The evening refresh loop keeps fetching odds after
--    first pitch and stores them as snapshot_type='open' (session 106), so the
--    newest snapshot for a finished game is often post-start or in-play. Using
--    it produced impossible splits (a team 29-80 to the under). The line is the
--    newest snapshot that is BOTH not in_play AND at or before commence_time,
--    failing open when either timestamp is missing (archive rows carry no
--    commence_time and no in-play risk). Mirrors _is_pregame_snapshot.
--
--  * TWO SPREAD CONVENTIONS. odds.spread_home is standard form (negative =
--    home laying points; verified — home teams listed negative win 78.5% SU).
--    nflverse spread_line is the OPPOSITE (positive = home favored; verified —
--    reading it as standard form made "favorites" win 32%). Both are normalised
--    to team_spread in standard form, so a cover is margin + team_spread > 0.
--
--  * THE ATS IDENTITY IS THE SANITY CHECK. Summed over every team in a closed
--    league, ATS wins must exactly equal ATS losses (verified: MLB 1752-1752,
--    NFL 284-284). It legitimately breaks only for NCAAF, where the FBS filter
--    excludes the FCS side of FBS-vs-FCS games.
--
--  * NCAAF IS FBS-ONLY. `games` carries the FCS opponents FBS teams schedule;
--    without the classification='fbs' filter the board returns 312 teams, ~178
--    of them stat-less.
--
-- Deliberately absent: NHL xgf_pct (0% populated — the free NHL API does not
-- expose expected goals) and NFL EPA/DVOA (proprietary or needing play-by-play
-- we do not ingest).
--
-- Performance: the line is resolved with ONE DISTINCT ON pass over the season's
-- odds slice. Two correlated LIMIT-1 subqueries per game ran 3.5s for MLB; the
-- single pass picks identical rows in ~0.5s (NCAAF ~85ms).
