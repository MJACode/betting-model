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
import re
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
    commence_time  TEXT,
    home_score_f5  REAL,
    away_score_f5  REAL,
    went_to_ot     INTEGER DEFAULT 0,
    home_win       INTEGER,
    home_win_reg   INTEGER,
    regulation_tie INTEGER DEFAULT 0,
    -- Schedule context (NCAAF today; generic enough for any football sport)
    week           INTEGER,
    neutral_site   INTEGER,
    conference_game INTEGER,
    venue_id       INTEGER,
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

-- NFL per-player per-game stats (nflverse weekly player stats) — feeds the
-- mobile Stats tab NFL leaderboard (season totals / last-N windows / hit rate).
-- game_id uses the platform "NFL_{nflverse_id}" convention but has NO FK to
-- games: only wind/opener pick games ever get a games row, while this log
-- covers the whole league. Display/stats only — no model reads it.
CREATE TABLE IF NOT EXISTS nfl_player_game_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
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
    passing_yards   REAL, passing_tds INTEGER, interceptions INTEGER,
    carries         INTEGER, rushing_yards REAL, rushing_tds INTEGER,
    receptions      INTEGER, targets INTEGER,
    receiving_yards REAL, receiving_tds INTEGER,
    def_sacks       REAL, def_interceptions INTEGER,
    -- modelling columns (NFL prop feature engine) — see
    -- data/migrations/add_nfl_prop_modeling_tables.sql
    sacks_suffered      REAL, passing_air_yards REAL, passing_epa REAL,
    rushing_first_downs INTEGER,
    receiving_air_yards REAL, receiving_yac REAL, receiving_epa REAL,
    target_share        REAL, air_yards_share REAL, wopr REAL, racr REAL,
    def_tackles_solo    REAL, def_tackle_assists REAL, def_qb_hits REAL,
    fg_made INTEGER, fg_att INTEGER, pat_made INTEGER, pat_att INTEGER,
    norm_name           TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(player_id, game_id)
);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_player ON nfl_player_game_log(player_id, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_plog_season ON nfl_player_game_log(season);

-- NFL prop modelling context. nfl_team_game_stats is one row per team per game:
-- offensive volume (the denominator behind every usage share, and the pace
-- proxy) plus the pre-game market/environment context from nflverse games.csv.
-- Opponent-defence-allowed features read the same table from the defending
-- team's side. nfl_snap_counts carries snap share — the availability signal and
-- the main driver of the tackles+assists market. nflverse keys snaps on
-- pfr_player_id with no gsis id, so both tables carry a normalised name key and
-- the join is (norm_name, team, game_id). Neither has an FK to games: only NFL
-- games with a wind/opener pick get a games row, these cover the whole league.
CREATE TABLE IF NOT EXISTS nfl_team_game_stats (
    row_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    game_date       TEXT NOT NULL,
    season          INTEGER NOT NULL,
    week            INTEGER,
    season_type     TEXT,
    is_home         INTEGER,
    pass_attempts   INTEGER, carries INTEGER, plays INTEGER,
    pass_yards      REAL, rush_yards REAL,
    completions     INTEGER, targets INTEGER,
    spread_line     REAL, total_line REAL,
    roof            TEXT, surface TEXT, temp REAL, wind REAL, div_game INTEGER,
    commence_time   TEXT,
    points_for      INTEGER, points_against INTEGER,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, team)
);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_team   ON nfl_team_game_stats(team, game_date);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_season ON nfl_team_game_stats(season, week);
CREATE INDEX IF NOT EXISTS idx_nfl_tgs_opp    ON nfl_team_game_stats(opponent, game_date);

CREATE TABLE IF NOT EXISTS nfl_snap_counts (
    row_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id         TEXT NOT NULL,
    team            TEXT NOT NULL,
    player_name     TEXT NOT NULL,
    norm_name       TEXT NOT NULL,
    pfr_player_id   TEXT,
    pos             TEXT,
    season          INTEGER NOT NULL,
    week            INTEGER,
    offense_snaps   INTEGER, offense_pct REAL,
    defense_snaps   INTEGER, defense_pct REAL,
    st_snaps        INTEGER, st_pct REAL,
    created_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(game_id, team, norm_name)
);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_join   ON nfl_snap_counts(norm_name, team, game_id);
CREATE INDEX IF NOT EXISTS idx_nfl_snaps_season ON nfl_snap_counts(season, week);

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
    updated_at      TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_teams_conf ON ncaaf_teams(conference);

-- ASOF season-to-date team snapshot. The feature engine reads the newest row
-- with as_of_date <= game_date, then SHRINKS each rate toward the prior
-- season's value by games played (config.NCAAF_PRIOR_SHRINKAGE_K) — a raw
-- season-to-date average is noise for the first month of a 12-game season.
CREATE TABLE IF NOT EXISTS ncaaf_team_stats (
    stat_id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    team                    TEXT NOT NULL,
    season                  INTEGER NOT NULL,
    as_of_date              TEXT NOT NULL,
    games_played            INTEGER,
    -- Ratings (CFBD /ratings/*) — the backbone in a 12-game sport
    sp_overall              REAL, sp_offense REAL, sp_defense REAL, sp_special_teams REAL,
    srs                     REAL, elo REAL,
    -- Program strength (recruiting + continuity), the priors that carry weeks 1-5
    talent                  REAL, returning_ppa REAL,
    -- Efficiency (CFBD /stats/season/advanced)
    epa_per_play_off        REAL, epa_per_play_def REAL,
    success_rate_off        REAL, success_rate_def REAL,
    explosiveness_off       REAL, explosiveness_def REAL,
    havoc_rate              REAL, havoc_rate_allowed REAL,
    finishing_drives_off    REAL, finishing_drives_def REAL,
    avg_field_position_off  REAL,
    third_down_rate_off     REAL, third_down_rate_def REAL,
    turnover_margin_pg      REAL,
    -- Tempo — the dominant totals signal in CFB
    plays_per_game          REAL, seconds_per_play REAL,
    -- Scoring / record
    points_per_game         REAL, points_allowed_pg REAL,
    points_last_3           REAL, point_differential REAL,
    wins                    INTEGER, losses INTEGER,
    -- Context
    conference              TEXT, classification TEXT,
    created_at              TEXT DEFAULT (datetime('now')),
    UNIQUE(team, season, as_of_date)
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_team ON ncaaf_team_stats(team, as_of_date);

-- Per-team per-game box score. Feeds rolling form + the ASOF stat rebuild.
-- No FK on game_id (the NFL precedent): the log covers every game a tracked
-- team plays, including FCS opponents that may never get a games row.
CREATE TABLE IF NOT EXISTS ncaaf_team_game_log (
    log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
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
    sacks              REAL, tackles_for_loss REAL,
    created_at         TEXT DEFAULT (datetime('now')),
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
    qb_game_id   INTEGER PRIMARY KEY AUTOINCREMENT,
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
    created_at   TEXT DEFAULT (datetime('now')),
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
    latitude     REAL,
    longitude    REAL,
    elevation_ft REAL,
    capacity     INTEGER,
    grass        INTEGER,
    dome         INTEGER,
    updated_at   TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_ncaaf_venues_name ON ncaaf_venues(name);

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
    condition_status   TEXT,               -- OK | DEGRADED | GONE (NFL locked picks)
    condition_note     TEXT,               -- why the conditions changed
    condition_checked_at TEXT,             -- last poll tick that evaluated it
    prop_market        TEXT,               -- prop market key (one model id, many markets)
    player_key         TEXT,               -- normalised player name settlement joins on
    created_at         TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_picks_date   ON picks(game_date);
CREATE INDEX IF NOT EXISTS idx_picks_model  ON picks(model_id);
CREATE INDEX IF NOT EXISTS idx_picks_signal ON picks(signal_type, result);

CREATE TABLE IF NOT EXISTS nfl_odds_history (
    snapshot_at   TEXT NOT NULL,
    game_id       TEXT        NOT NULL,
    season        INTEGER,
    week          INTEGER,
    commence_time TEXT,
    bookmaker     TEXT        NOT NULL,
    market        TEXT        NOT NULL,   -- spreads | totals | h2h
    point         REAL,                -- home handicap, or the total
    price_home    REAL,                -- home / over
    price_away    REAL,                -- away / under
    lead_hours    REAL,                -- hours to kickoff at this snapshot
    PRIMARY KEY (snapshot_at, game_id, bookmaker, market)
);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_game   ON nfl_odds_history(game_id, market);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_season ON nfl_odds_history(season, week);
CREATE INDEX IF NOT EXISTS idx_nfl_odds_hist_lead   ON nfl_odds_history(market, lead_hours);

CREATE TABLE IF NOT EXISTS nfl_pick_status_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    pick_id         INTEGER NOT NULL REFERENCES picks(pick_id),
    game_id         TEXT NOT NULL,
    model_id        TEXT NOT NULL,
    observed_at     TEXT NOT NULL,
    lead_hours      REAL,
    still_qualifies INTEGER NOT NULL,
    status          TEXT NOT NULL,
    reason          TEXT,
    current_line    REAL,
    current_price   REAL,
    current_book    TEXT,
    model_prob_now  REAL,
    edge_now        REAL,
    UNIQUE (pick_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_nfl_pick_hist_pick ON nfl_pick_status_history(pick_id);
CREATE INDEX IF NOT EXISTS idx_nfl_pick_hist_game ON nfl_pick_status_history(game_id, observed_at);

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

-- In-app feedback (mobile Settings → Send feedback). One thread per
-- conversation, owned by a device_id; feedback_messages holds the turns, with
-- sender 'user' or 'support'. Anon reaches these ONLY through the
-- device-scoped SECURITY DEFINER RPCs in the migration — RLS, policies, grants
-- and those functions are Postgres-only (supabase_schema.sql + migration
-- add_feedback_threads.sql). Mirrored here so the SQLite test schema matches.
CREATE TABLE IF NOT EXISTS feedback_threads (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id       TEXT NOT NULL,
    user_id         TEXT,
    category        TEXT NOT NULL DEFAULT 'other',
    subject         TEXT NOT NULL,
    app_version     TEXT,
    platform        TEXT,
    status          TEXT NOT NULL DEFAULT 'open',
    created_at      TEXT DEFAULT (datetime('now')),
    last_message_at TEXT DEFAULT (datetime('now')),
    last_read_at    TEXT
);
CREATE TABLE IF NOT EXISTS feedback_messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id  INTEGER NOT NULL REFERENCES feedback_threads(id) ON DELETE CASCADE,
    sender     TEXT NOT NULL CHECK (sender IN ('user', 'support')),
    body       TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_feedback_threads_device ON feedback_threads(device_id);
CREATE INDEX IF NOT EXISTS idx_feedback_threads_status ON feedback_threads(status);
CREATE INDEX IF NOT EXISTS idx_feedback_messages_thread ON feedback_messages(thread_id, id);

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
    # NCAAF schedule context (neutral-site + conference game are real CFB
    # signals; week drives the early-season prior weighting)
    ("games", "week",            "INTEGER"),
    ("games", "neutral_site",    "INTEGER"),
    ("games", "conference_game", "INTEGER"),
    ("games", "venue_id",        "INTEGER"),
    # NFL prop modelling columns (2026-08-23) — the display ingest was
    # already downloading these and throwing them away.
    ("nfl_player_game_log", "sacks_suffered", "NUMERIC"),
    ("nfl_player_game_log", "passing_air_yards", "NUMERIC"),
    ("nfl_player_game_log", "passing_epa", "NUMERIC"),
    ("nfl_player_game_log", "rushing_first_downs", "INTEGER"),
    ("nfl_player_game_log", "receiving_air_yards", "NUMERIC"),
    ("nfl_player_game_log", "receiving_yac", "NUMERIC"),
    ("nfl_player_game_log", "receiving_epa", "NUMERIC"),
    ("nfl_player_game_log", "target_share", "NUMERIC"),
    ("nfl_player_game_log", "air_yards_share", "NUMERIC"),
    ("nfl_player_game_log", "wopr", "NUMERIC"),
    ("nfl_player_game_log", "racr", "NUMERIC"),
    ("nfl_player_game_log", "def_tackles_solo", "NUMERIC"),
    ("nfl_player_game_log", "def_tackle_assists", "NUMERIC"),
    ("nfl_player_game_log", "def_qb_hits", "NUMERIC"),
    ("nfl_player_game_log", "fg_made", "INTEGER"),
    ("nfl_player_game_log", "fg_att", "INTEGER"),
    ("nfl_player_game_log", "pat_made", "INTEGER"),
    ("nfl_player_game_log", "pat_att", "INTEGER"),
    ("nfl_player_game_log", "norm_name", "TEXT"),
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
    # NFL locked-pick condition tracking. The pick is immutable once locked;
    # these say whether the conditions that justified it still hold, so a
    # collapsed forecast or a line that ran away is surfaced loudly instead of
    # silently deleting the bet.
    ("picks", "condition_status",     "TEXT"),
    ("picks", "condition_note",       "TEXT"),
    ("picks", "condition_checked_at", "TEXT"),
    # The market-relative NFL prop rule (models/nfl_prop_market) is ONE model id
    # covering many markets, so the market has to travel on the row. player_key
    # is the normalised name settlement joins on — NFL is the sport whose odds
    # feed and stat feed do not spell names the same way, and recovering the
    # player by regex out of pick_label made a display string load-bearing.
    ("picks", "prop_market", "TEXT"),
    ("picks", "player_key",  "TEXT"),
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

def _split_sql_statements(sql: str) -> list[str]:
    """
    Split a schema file into executable statements.

    The old code was `schema_sql.split(";")`, which is wrong in two ways that
    both broke this function against the real schema:

      1. A semicolon inside a `--` comment cut the comment in half and handed
         the tail to Postgres as SQL, producing "syntax error at or near
         nba_team_stats" from the prose "...leaderboard); nba_team_stats stays
         locked down." There are 20+ such commented sentences in the file.
      2. A semicolon inside a `$$ ... $$` function body split the function into
         fragments, leaving a bare `$$` as its own statement.

    Neither was ever noticed because setup_database() is only reachable from
    first_time_setup(), which nobody runs — so the Postgres schema path was
    effectively dead code until a workflow started calling it.

    This tracks single quotes, double quotes and dollar-quoting, skips `--` and
    block comments, and breaks only on a semicolon at depth zero.
    """
    stmts: list[str] = []
    buf: list[str] = []
    in_single = in_double = False
    dollar_tag: str | None = None
    i, n = 0, len(sql)

    while i < n:
        ch = sql[i]

        if dollar_tag:                            # inside $tag$ ... $tag$
            if sql.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue

        if in_single:
            buf.append(ch)
            if ch == "'":
                in_single = False
            i += 1
            continue

        if in_double:
            buf.append(ch)
            if ch == '"':
                in_double = False
            i += 1
            continue

        if sql.startswith("--", i):               # line comment
            j = sql.find(chr(10), i)
            i = n if j == -1 else j
            continue

        if sql.startswith("/*", i):               # block comment
            j = sql.find("*/", i)
            i = n if j == -1 else j + 2
            continue

        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue

        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue

        if ch == "$":
            m = re.match(r"\$[A-Za-z_0-9]*\$", sql[i:])
            if m:
                dollar_tag = m.group(0)
                buf.append(dollar_tag)
                i += len(dollar_tag)
                continue

        if ch == ";":
            stmt = "".join(buf).strip()
            if stmt:
                stmts.append(stmt)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        stmts.append(tail)
    return stmts


def setup_database() -> None:
    """Create or upgrade the Postgres schema via DATABASE_URL."""
    logger.info("Setting up Postgres database schema...")
    conn = get_connection()
    try:
        schema_sql = _load_postgres_schema()
        # Execute each statement individually so IF NOT EXISTS works correctly.
        # Comments are stripped FIRST: this file splits on ";" and the schema is
        # heavily commented in prose, so a semicolon inside a `--` comment used
        # to cut a comment in half and hand the tail to Postgres as SQL. That is
        # what made this function fail on "syntax error at or near
        # nba_team_stats" — the second half of the sentence "...leaderboard);
        # nba_team_stats stays locked down." There are 20+ such comments; the
        # bug went unseen because setup_database() is only reachable from
        # first_time_setup(), which nobody runs.
        # Commit each statement on its own and tolerate "already exists".
        #
        # The module docstring promises this is safe to re-run, and for tables
        # and indexes it is — they all use IF NOT EXISTS. Postgres has no
        # IF NOT EXISTS for CREATE POLICY (nor for several other object kinds),
        # so a second run died on
        #     policy "anon read nfl_player_game_log" ... already exists
        # even though the desired end state was already in place.
        #
        # autocommit is off, so one failed statement would poison the rest of
        # the transaction. Committing per statement keeps a tolerated duplicate
        # from rolling back the work that preceded it. Only the duplicate-object
        # SQLSTATEs are swallowed; anything else still aborts the run loudly.
        duplicate_codes = {
            "42710",   # duplicate_object   (policy, trigger, ...)
            "42P07",   # duplicate_table    (table, index, view)
            "42701",   # duplicate_column
            "42P06",   # duplicate_schema
            "42723",   # duplicate_function
        }
        applied = skipped = 0
        for stmt in _split_sql_statements(schema_sql):
            try:
                conn.execute(stmt)
                conn.commit()
                applied += 1
            except Exception as exc:            # noqa: BLE001
                conn.rollback()
                if getattr(exc, "pgcode", None) in duplicate_codes:
                    skipped += 1
                    continue
                logger.error(f"Failed statement: {stmt[:200]}")
                raise
        logger.info(f"Schema: {applied} statement(s) applied, "
                    f"{skipped} already present")

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
